import requests
import time
import logging
import re
from requests.exceptions import RequestException

logger = logging.getLogger(__name__)

NOTION_API_BASE_URL = "https://api.notion.com/v1"
NOTION_API_VERSION = "2022-06-28"
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

# Notion limits page size to 100
PAGE_SIZE = 100

# Mapping Notion property names (as defined in your DB) to code variables
# IMPORTANT: Adjust these if your Notion property names are different!
PROP_REPO_ID = "GitHub Repo ID" # MUST match the Text property name for storing repo ID
PROP_FULL_NAME = "Full Name"    # Added property for storing 'owner/repo'
PROP_NAME = "Name"             # MUST match the Title property name
PROP_DESCRIPTION = "Description"
PROP_URL = "URL"
PROP_LANGUAGE = "Language"
PROP_STARS = "Stars"
PROP_TOPICS = "Topics"
PROP_STARRED_AT = "Starred At"  # 新增 Starred At 属性
PROP_LAST_SYNCED = "Last Synced" # Optional

class NotionClient:
    def __init__(self, token, database_id):
        if not token or not database_id:
            raise ValueError("Notion token and database ID cannot be empty.")
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Notion-Version": NOTION_API_VERSION,
        }
        # 格式化数据库ID为标准UUID格式（带连字符）
        self._database_id = self._format_notion_id(database_id)
        logger.info(f"Using Notion database ID: {self._database_id}")

    def _format_notion_id(self, notion_id):
        """将Notion ID格式化为带连字符的标准UUID格式"""
        # 如果已经是带连字符的格式，直接返回
        if '-' in notion_id:
            return notion_id
        
        # 无连字符格式转换为标准UUID格式
        if len(notion_id) == 32:
            formatted_id = f"{notion_id[0:8]}-{notion_id[8:12]}-{notion_id[12:16]}-{notion_id[16:20]}-{notion_id[20:]}"
            logger.info(f"Converted database ID from {notion_id} to {formatted_id}")
            return formatted_id
        
        # 如果不是标准长度，返回原始ID
        logger.warning(f"Database ID {notion_id} does not appear to be a standard Notion ID. Using as is.")
        return notion_id

    def _make_request(self, method, url, json=None):
        retries = 0
        while retries < MAX_RETRIES:
            try:
                response = requests.request(method, url, headers=self._headers, json=json)
                response.raise_for_status() # Raises HTTPError for bad responses (4XX or 5XX)
                return response.json()
            except RequestException as e:
                retries += 1
                # Log Notion specific errors if available
                error_details = ""
                try:
                    error_body = response.json()
                    error_details = f" Notion Error: {error_body.get('code')} - {error_body.get('message')}"
                except Exception: # Ignore if response is not JSON or parsing fails
                    pass
                logger.warning(f"{method} request to {url} failed ({e}).{error_details} Retrying ({retries}/{MAX_RETRIES}) in {RETRY_DELAY}s...")
                if retries == MAX_RETRIES:
                    logger.error(f"Max retries reached for {method} {url}. Last Error: {e}{error_details}")
                    raise # Re-raise the last exception
                time.sleep(RETRY_DELAY)
            except Exception as e:
                 logger.exception(f"An unexpected error occurred during {method} {url}: {e}")
                 raise # Re-raise unexpected errors immediately

    def query_database(self):
        """Fetches all pages from the database, returning a map of {repo_id: page_id}."""
        pages_map = {}
        url = f"{NOTION_API_BASE_URL}/databases/{self._database_id}/query"
        has_more = True
        start_cursor = None

        logger.info(f"Querying Notion database {self._database_id}...")

        # 首先检查并获取数据库结构，确认属性存在情况
        try:
            db_url = f"{NOTION_API_BASE_URL}/databases/{self._database_id}"
            db_info = self._make_request("GET", db_url)
            db_properties = db_info.get("properties", {}).keys()
            has_full_name = PROP_FULL_NAME in db_properties
            
            if not has_full_name:
                logger.warning(f"数据库中不存在 '{PROP_FULL_NAME}' 属性，将不使用此属性进行匹配")
        except Exception as e:
            logger.warning(f"获取数据库结构失败: {e}，将假设所有属性都存在")
            has_full_name = True

        while has_more:
            payload = {"page_size": PAGE_SIZE}
            if start_cursor:
                payload["start_cursor"] = start_cursor

            try:
                logger.debug(f"Querying Notion DB with cursor: {start_cursor}")
                response_data = self._make_request("POST", url, json=payload)

                for page in response_data.get("results", []):
                    page_id = page.get("id")
                    properties = page.get("properties", {})
                    
                    # 获取存储在 Repo ID 字段中的值
                    repo_id_prop = properties.get(PROP_REPO_ID, {}).get("rich_text", [])
                    
                    # 尝试获取全名字段（如果存在）
                    full_name = None
                    if has_full_name:
                        full_name_prop = properties.get(PROP_FULL_NAME, {}).get("rich_text", [])
                        full_name = full_name_prop[0].get("plain_text") if full_name_prop else None
                    
                    if repo_id_prop:
                        repo_id = repo_id_prop[0].get("plain_text")
                        if repo_id and page_id:
                            # 1. 如果 repo_id 是数字，用数字 ID 作为键
                            if repo_id.isdigit():
                                pages_map[repo_id] = page_id
                                logger.debug(f"使用数字 ID {repo_id} 作为键")
                            # 2. 否则，如果看起来像 owner/repo 格式，作为全名处理
                            elif "/" in repo_id:
                                # 使用特殊前缀标记这是全名
                                pages_map[f"name:{repo_id}"] = page_id
                                logger.debug(f"使用全名格式 ID '{repo_id}' 作为键")
                            # 3. 其他情况记录警告但仍将其添加到映射中
                            else:
                                pages_map[f"unknown:{repo_id}"] = page_id
                                logger.warning(f"页面 {page_id} 的 Repo ID '{repo_id}' 格式未知")
                        else:
                            logger.warning(f"Found page without valid Repo ID or Page ID: Page data: {page}")
                    # 4. 如果没有 Repo ID 但有 Full Name，使用 Full Name
                    elif full_name:
                        pages_map[f"name:{full_name}"] = page_id
                        logger.debug(f"使用 Full Name {full_name} 作为键")
                    else:
                        logger.warning(f"Found page missing both '{PROP_REPO_ID}' and '{PROP_FULL_NAME}' properties: Page ID {page_id}")

                has_more = response_data.get("has_more", False)
                start_cursor = response_data.get("next_cursor")

            except (RequestException, ValueError, KeyError) as e:
                logger.error(f"Failed to query or parse Notion database: {e}")
                break # Stop querying on error
            except Exception as e:
                logger.exception(f"An unexpected error occurred during Notion DB query: {e}")
                break

        logger.info(f"Finished querying Notion. Found {len(pages_map)} existing repo entries.")
        return pages_map

    def _build_properties(self, repo_data):
        """Helper to build the Notion properties payload from repo data."""
        properties = {
            PROP_NAME: {"title": [{"text": {"content": repo_data["name"]}}]}, # Title needs specific format
            PROP_REPO_ID: {"rich_text": [{"text": {"content": str(repo_data["id"])}}]}, # Use numeric ID as the unique ID
            PROP_URL: {"rich_text": [{"text": {"content": repo_data["url"]}}]},  # Changed to rich_text type
            PROP_STARS: {"number": repo_data["stars"]}
        }
        
        # 只有在定义了 PROP_FULL_NAME 且不是默认值时才添加
        if PROP_FULL_NAME != "Full Name":  # 默认值检查
            try:
                properties[PROP_FULL_NAME] = {"rich_text": [{"text": {"content": repo_data["full_name"]}}]}
            except Exception as e:
                logger.warning(f"Failed to set Full Name property: {e}. This is expected if the property doesn't exist in the database.")
        
        # Handle optional fields
        if repo_data.get("description"): # Check if description exists and is not None/empty
            # Truncate description if it exceeds Notion's limit (2000 characters for text)
            desc = repo_data["description"][:2000]
            properties[PROP_DESCRIPTION] = {"rich_text": [{"text": {"content": desc}}]}
        else:
            properties[PROP_DESCRIPTION] = {"rich_text": []} # Send empty array if no description

        if repo_data.get("language"):
            properties[PROP_LANGUAGE] = {"select": {"name": repo_data["language"]}}  # Changed to select type
        else:
            properties[PROP_LANGUAGE] = {"select": None}  # Changed to match select type

        if repo_data.get("topics"):
            # Multi-select expects an array of objects with names
            properties[PROP_TOPICS] = {"multi_select": [{"name": topic} for topic in repo_data["topics"]]}
        else:
             properties[PROP_TOPICS] = {"multi_select": []}

        # 添加 Starred At 时间（如果数据库中存在该属性）
        try:
            if repo_data.get("starred_at"):
                properties[PROP_STARRED_AT] = {"date": {"start": repo_data["starred_at"]}}
        except Exception as e:
            logger.warning(f"Failed to set Starred At property: {e}. This is expected if the property doesn't exist in the database.")

        # Optionally set Last Synced time
        # from datetime import datetime
        # properties[PROP_LAST_SYNCED] = {"date": {"start": datetime.utcnow().isoformat()}}

        return properties

    def create_page(self, repo_data):
        """Creates a new page in the Notion database for a repository."""
        url = f"{NOTION_API_BASE_URL}/pages"
        payload = {
            "parent": {"database_id": self._database_id},
            "properties": self._build_properties(repo_data)
        }
        try:
            logger.info(f"Creating Notion page for {repo_data['full_name']}...")
            response = self._make_request("POST", url, json=payload)
            logger.debug(f"Successfully created page with ID: {response.get('id')}")
            return response
        except (RequestException, ValueError, KeyError) as e:
            logger.error(f"Failed to create Notion page for {repo_data['full_name']}: {e}")
            return None # Indicate failure

    def update_page(self, page_id, repo_data):
        """Updates an existing page in the Notion database."""
        url = f"{NOTION_API_BASE_URL}/pages/{page_id}"
        payload = {
            "properties": self._build_properties(repo_data)
        }
        try:
            logger.info(f"Updating Notion page {page_id} for {repo_data['full_name']}...")
            response = self._make_request("PATCH", url, json=payload)
            logger.debug(f"Successfully updated page {page_id}.")
            return response
        except (RequestException, ValueError, KeyError) as e:
            logger.error(f"Failed to update Notion page {page_id} for {repo_data['full_name']}: {e}")
            return None # Indicate failure

    def delete_page(self, page_id):
        """Deletes (archives) a page in Notion."""
        url = f"{NOTION_API_BASE_URL}/pages/{page_id}"
        payload = {"archived": True}
        try:
            logger.info(f"Deleting (archiving) Notion page {page_id}...")
            response = self._make_request("PATCH", url, json=payload)
            logger.debug(f"Successfully archived page {page_id}.")
            return response
        except (RequestException, ValueError, KeyError) as e:
            logger.error(f"Failed to delete (archive) Notion page {page_id}: {e}")
            return None # Indicate failure

    def _build_page_properties(self, repo_data):
        """构建 Notion 页面属性"""
        properties = {
            "Name": {
                "title": [
                    {
                        "text": {
                            "content": repo_data["name"]
                        }
                    }
                ]
            },
            "Full Name": {
                "rich_text": [
                    {
                        "text": {
                            "content": repo_data["full_name"]
                        }
                    }
                ]
            },
            "Description": {
                "rich_text": [
                    {
                        "text": {
                            "content": repo_data.get("description", "") or ""
                        }
                    }
                ]
            },
            "URL": {
                "url": repo_data["url"]
            },
            "Language": {
                "rich_text": [
                    {
                        "text": {
                            "content": repo_data.get("language", "") or ""
                        }
                    }
                ]
            },
            "Stars": {
                "number": repo_data["stars"]
            },
            "Topics": {
                "multi_select": [
                    {"name": topic} for topic in (repo_data.get("topics", []) or [])
                ]
            },
            "Last Updated": {
                "date": {
                    "start": repo_data["last_updated"]
                }
            },
            "Starred At": {  # 添加 Starred At 字段
                "date": {
                    "start": repo_data["starred_at"]
                }
            },
            "Repository ID": {
                "rich_text": [
                    {
                        "text": {
                            "content": str(repo_data["id"])
                        }
                    }
                ]
            }
        }
        return properties

    def get_page(self, page_id):
        """获取页面数据"""
        try:
            # 获取页面数据
            url = f"{NOTION_API_BASE_URL}/pages/{page_id}"
            response = self._make_request("GET", url)
            
            if response and response.get("properties"):
                props = response["properties"]
                page_data = {
                    "repo_id": self._get_property_text(props.get("Repository ID")),
                    "name": self._get_property_title(props.get("Name")),
                    "description": self._get_property_text(props.get("Description")),
                    "language": self._get_property_select(props.get("Language")),
                    "stars": self._get_property_number(props.get("Stars")),
                    "topics": self._get_property_multi_select(props.get("Topics")),
                    "last_updated": self._get_property_date(props.get("Last Updated")),
                    "starred_at": self._get_property_date(props.get("Starred At"))
                }
                
                # 只有在属性存在时才尝试获取 Full Name
                if PROP_FULL_NAME in props:
                    page_data["full_name"] = self._get_property_text(props.get(PROP_FULL_NAME))
                
                return page_data
            
            logger.warning(f"获取页面 {page_id} 的数据为空或格式不正确")
            return None
        except Exception as e:
            logger.error(f"获取页面失败 (ID: {page_id}): {e}")
            return None
    
    def _get_property_text(self, prop):
        """从富文本属性中提取文本内容"""
        if not prop:
            return ""
        rich_text = prop.get("rich_text", [])
        if rich_text:
            return rich_text[0].get("plain_text", "")
        return ""
    
    def _get_property_title(self, prop):
        """从标题属性中提取文本内容"""
        if not prop:
            return ""
        title = prop.get("title", [])
        if title:
            return title[0].get("text", {}).get("content", "")
        return ""
    
    def _get_property_select(self, prop):
        """从选择属性中提取选项名称"""
        if not prop:
            return ""
        select = prop.get("select")
        if select:
            return select.get("name", "")
        return ""
    
    def _get_property_multi_select(self, prop):
        """从多选属性中提取选项名称列表"""
        if not prop:
            return []
        multi_select = prop.get("multi_select", [])
        return [item.get("name", "") for item in multi_select]
    
    def _get_property_number(self, prop):
        """从数字属性中提取数值"""
        if not prop:
            return 0
        return prop.get("number", 0)
    
    def _get_property_date(self, prop):
        """从日期属性中提取起始日期"""
        if not prop:
            return ""
        date = prop.get("date")
        if date:
            return date.get("start", "")
        return ""

# Example usage (requires a valid .env file)
if __name__ == '__main__':
    from config import load_config
    import random

    # Setup logging for testing
    logging.basicConfig(level=logging.DEBUG)

    try:
        app_config = load_config()
        notion_client = NotionClient(
            token=app_config['notion_token'],
            database_id=app_config['notion_database_id']
        )

        # 1. Query existing pages
        print("\nQuerying database...")
        existing_pages = notion_client.query_database()
        print(f"Found {len(existing_pages)} existing pages.")
        if existing_pages:
            print("Existing Repo IDs:", list(existing_pages.keys())[:5], "...")
            # Get a random page ID to test update/delete
            test_repo_id = random.choice(list(existing_pages.keys()))
            test_page_id = existing_pages[test_repo_id]
            print(f"Will use Page ID {test_page_id} (Repo ID: {test_repo_id}) for update/delete tests.")
        else:
            test_page_id = None
            print("Database is empty, skipping update/delete tests.")

        # 2. Create a dummy page (adapt data structure from GitHubClient)
        print("\nAttempting to create a new page...")
        dummy_repo_data = {
            "id": 123456789,
            "name": "Test Repo",
            "full_name": f"TestOwner/TestRepo_{int(time.time())}", # Unique name
            "description": "This is a test repository created by the script.",
            "url": "https://github.com/TestOwner/TestRepo",
            "language": "Python",
            "stars": 101,
            "topics": ["test", "notion-api", "example"],
            "last_updated": "2023-10-27T10:00:00Z"
        }
        created_page = notion_client.create_page(dummy_repo_data)
        if created_page:
            print(f"Successfully created page with ID: {created_page.get('id')}")
            # Update test_page_id if we didn't have one from query
            if not test_page_id:
                test_page_id = created_page.get('id')
                test_repo_id = dummy_repo_data['full_name']
                print(f"Using newly created page {test_page_id} for update/delete.")
        else:
            print("Failed to create page.")

        # 3. Update a page (if we have a page ID)
        if test_page_id:
            print(f"\nAttempting to update page {test_page_id} ({test_repo_id})...")
            update_data = dummy_repo_data.copy()
            update_data["description"] = f"Description updated at {time.strftime('%Y-%m-%d %H:%M:%S')}"
            update_data["stars"] = random.randint(100, 500)
            # Important: Use the SAME full_name (Repo ID) when updating
            update_data["full_name"] = test_repo_id
            updated_page = notion_client.update_page(test_page_id, update_data)
            if updated_page:
                print(f"Successfully updated page {test_page_id}.")
            else:
                print(f"Failed to update page {test_page_id}.")

        # 4. Delete (archive) a page (if we have a page ID)
        # Use the created page ID for deletion if available
        page_to_delete = created_page.get('id') if created_page else test_page_id
        if page_to_delete:
            print(f"\nAttempting to delete (archive) page {page_to_delete}...")
            # input("Press Enter to confirm deletion...") # Optional confirmation step
            deleted_page = notion_client.delete_page(page_to_delete)
            if deleted_page:
                print(f"Successfully archived page {page_to_delete}.")
            else:
                print(f"Failed to archive page {page_to_delete}.")

    except ValueError as e:
        print(f"Configuration error: {e}")
    except RequestException as e:
        print(f"Notion API request error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}") 