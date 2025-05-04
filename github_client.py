import requests
import time
import logging
from requests.exceptions import RequestException
from email.utils import parsedate_to_datetime  # 添加这行来解析 HTTP 日期格式
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

GITHUB_API_BASE_URL = "https://api.github.com"
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds
PER_PAGE = 100 # Max items per page for GitHub API

class GitHubClient:
    def __init__(self, token):
        if not token:
            raise ValueError("GitHub token cannot be empty.")
        self._token = token
        self._headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }

    def _make_request(self, url, params=None, accept_header=None):
        """发送 GET 请求到 GitHub API

        Args:
            url: API 端点
            params: URL 参数
            accept_header: 可选的 Accept 头

        Returns:
            requests.Response: API 响应对象
        """
        retries = 0
        headers = self._headers.copy()
        if accept_header:
            headers["Accept"] = accept_header

        while retries < MAX_RETRIES:
            try:
                response = requests.get(
                    url,
                    headers=headers,
                    params=params
                )
                
                # 检查是否达到 API 速率限制
                if response.status_code == 403 and 'X-RateLimit-Remaining' in response.headers:
                    remaining = int(response.headers['X-RateLimit-Remaining'])
                    if remaining == 0:
                        reset_time = int(response.headers['X-RateLimit-Reset'])
                        wait_time = reset_time - int(time.time()) + 1
                        if wait_time > 0:
                            logger.warning(f"达到 API 速率限制，等待 {wait_time} 秒...")
                            time.sleep(wait_time)
                            continue

                response.raise_for_status()
                return response
            except RequestException as e:
                retries += 1
                logger.warning(f"请求失败 ({e}). 重试 ({retries}/{MAX_RETRIES}) 在 {RETRY_DELAY} 秒后...")
                if retries == MAX_RETRIES:
                    logger.error(f"达到最大重试次数 {url}. 错误: {e}")
                    raise
                time.sleep(RETRY_DELAY)
            except Exception as e:
                logger.error(f"请求时发生意外错误: {e}")
                raise

    def get_starred_repos(self, since=None):
        """获取用户所有 star 的仓库及其 star 时间
        
        Args:
            since: 可选的ISO 8601格式时间戳，只获取该时间之后 star 的仓库
        
        Returns:
            list: 仓库信息列表
        """
        starred_repos = []
        page = 1
        per_page = PER_PAGE
        
        # 只在函数开始时记录一次增量同步信息，而不是每个分页请求都记录
        if since:
            logger.info(f"执行增量同步：获取自 {since} 之后 star 的仓库")
            # 解析时间字符串为 datetime 对象，用于后续比较
            try:
                since_dt = datetime.fromisoformat(since.replace('Z', '+00:00'))
            except ValueError:
                logger.warning(f"无法解析时间字符串 {since}，将改为全量同步")
                since = None
                since_dt = None
        else:
            since_dt = None

        # 我们需要获取所有仓库，因为 GitHub API 没有提供按 star 时间筛选的参数
        # 'since' 参数只筛选仓库的更新时间，不是 star 时间
        all_repos = []
        
        while True:
            try:
                # 使用 star API 获取带有 star 时间的仓库列表
                url = f"{GITHUB_API_BASE_URL}/user/starred"
                params = {
                    "page": page,
                    "per_page": per_page,
                    "sort": "created",  # 按 star 时间排序
                    "direction": "desc"  # 最新的在前面
                }
                
                # 添加分页日志
                logger.debug(f"获取 starred 仓库分页: {page}, 每页 {per_page} 个")
                
                response = self._make_request(
                    url,
                    params=params,
                    accept_header="application/vnd.github.star+json"
                )
                
                if not response:
                    break

                data = response.json()
                if not data:
                    break

                logger.debug(f"收到 GitHub API 响应: {str(data[:1])[:200]}...")

                # 全部加入临时列表
                all_repos.extend(data)
                
                # 检查是否还有下一页
                if len(data) < per_page:
                    break

                page += 1
                time.sleep(1)  # 添加延迟以避免触发 API 限制

            except Exception as e:
                logger.error(f"获取 starred 仓库失败: {e}")
                break
        
        # 处理每个仓库，筛选出最近 star 的仓库
        for item in all_repos:
            try:
                repo = item["repo"]  # star API 返回的仓库信息在 repo 字段中
                starred_at = item["starred_at"]
                
                # 如果是增量同步，检查 star 时间是否在指定时间之后
                if since_dt:
                    try:
                        starred_dt = datetime.fromisoformat(starred_at.replace('Z', '+00:00'))
                        if starred_dt <= since_dt:
                            # 此仓库是在上次同步前 star 的，跳过
                            logger.debug(f"跳过较早 star 的仓库: {repo['full_name']}, Star 时间: {starred_at}")
                            continue
                    except ValueError:
                        # 时间格式解析错误，保守起见包含该仓库
                        logger.warning(f"无法解析 Star 时间 {starred_at}，将包含仓库 {repo['full_name']}")
                
                repo_data = {
                    "id": repo["id"],
                    "name": repo["name"],
                    "full_name": repo["full_name"],
                    "description": repo.get("description"),
                    "url": repo["html_url"],
                    "language": repo.get("language"),
                    "stars": repo["stargazers_count"],
                    "topics": repo.get("topics", []),
                    "last_updated": repo["updated_at"],
                    "starred_at": starred_at  # 从顶层获取 star 时间
                }
                starred_repos.append(repo_data)
                logger.debug(f"成功处理仓库: {repo_data['full_name']}, Star 时间: {repo_data['starred_at']}")
            except KeyError as e:
                logger.warning(f"处理仓库数据时出错: {e}, 数据: {str(item)[:200]}...")
                continue

        if since:
            logger.info(f"增量同步：自 {since} 以来，获取到 {len(starred_repos)} 个新 star 的仓库")
        else:
            logger.info(f"全量同步：成功获取 {len(starred_repos)} 个 starred 仓库")
            
        if starred_repos:
            logger.debug(f"第一个仓库数据示例: {str(starred_repos[0])[:200]}...")
        return starred_repos

# Example usage (requires a valid .env file with GITHUB_TOKEN)
if __name__ == '__main__':
    import os
    from dotenv import load_dotenv
    from config import load_config

    # Setup logging for testing
    logging.basicConfig(level=logging.DEBUG)

    try:
        app_config = load_config()
        client = GitHubClient(token=app_config['github_token'])
        
        # 测试全量获取
        starred = client.get_starred_repos()

        if starred:
            print(f"\n获取到 {len(starred)} 个仓库。前几个示例：")
            for i, repo in enumerate(starred[:3]):
                print(f"\n{i+1}. {repo['full_name']}")
                print(f"   描述: {repo['description'][:50]}..." if repo['description'] else "   无描述")
                print(f"   语言: {repo['language'] or '未指定'}")
                print(f"   Star数: {repo['stars']}")
                print(f"   Star时间: {repo['starred_at']}")
                print(f"   最后更新: {repo['last_updated']}")
                print(f"   主题: {', '.join(repo['topics']) if repo['topics'] else '无'}")
            
            if len(starred) > 3:
                print("\n...")
                
            # 测试增量获取（使用一周前的时间）
            from datetime import datetime, timedelta
            one_week_ago = (datetime.now() - timedelta(days=7)).isoformat()
            print(f"\n测试增量获取（自 {one_week_ago} 起）:")
            recent_starred = client.get_starred_repos(since=one_week_ago)
            print(f"过去一周内 star 的仓库数量: {len(recent_starred)}")
        else:
            print("未找到已 star 的仓库或获取失败。")

    except ValueError as e:
        print(f"配置错误: {e}")
    except RequestException as e:
        print(f"GitHub API 请求错误: {e}")
    except Exception as e:
        print(f"发生意外错误: {e}") 