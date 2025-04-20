import logging

logger = logging.getLogger(__name__)

def run_sync(github_client, notion_client):
    """执行同步操作"""
    try:
        # 获取 GitHub starred 仓库
        starred_repos = github_client.get_starred_repos()
        if not starred_repos:
            logger.error("未找到任何 starred 仓库")
            return
        logger.info(f"从 GitHub 获取到 {len(starred_repos)} 个 starred 仓库")

        # 获取 Notion 数据库中的页面
        notion_pages = notion_client.query_database()
        if notion_pages is None:
            logger.error("获取 Notion 数据库页面失败")
            return
        logger.info(f"从 Notion 获取到 {len(notion_pages)} 个页面")

        # 构建 GitHub 仓库 ID 到仓库数据的映射
        github_repos = {str(repo["id"]): repo for repo in starred_repos}
        
        # 确定需要创建、更新和删除的页面
        to_create = []
        to_update = []
        to_delete = []

        # 找出需要创建和更新的页面
        for repo_id, repo_data in github_repos.items():
            if repo_id not in notion_pages:
                to_create.append(repo_data)
            else:
                # 获取现有页面数据
                page = notion_client.get_page(notion_pages[repo_id])
                if page:
                    # 检查是否需要更新
                    if (page.get("last_updated") != repo_data["last_updated"] or
                        page.get("stars") != repo_data["stars"] or
                        page.get("topics", []) != repo_data["topics"] or
                        page.get("starred_at") != repo_data["starred_at"]):  # 添加 starred_at 的比较
                        to_update.append((notion_pages[repo_id], repo_data))

        # 找出需要删除的页面
        for notion_repo_id in notion_pages:
            if notion_repo_id not in github_repos:
                to_delete.append(notion_pages[notion_repo_id])

        # 输出同步计划
        logger.info(f"同步计划: 创建 {len(to_create)} 个页面, 更新 {len(to_update)} 个页面, 删除 {len(to_delete)} 个页面")

        # 执行同步操作
        results = {
            "created": 0,
            "updated": 0,
            "deleted": 0,
            "errors": 0
        }

        # 创建新页面
        for repo_data in to_create:
            try:
                if notion_client.create_page(repo_data):
                    results["created"] += 1
                else:
                    results["errors"] += 1
            except Exception as e:
                logger.error(f"创建页面失败 ({repo_data['full_name']}): {e}")
                results["errors"] += 1

        # 更新现有页面
        for page_id, repo_data in to_update:
            try:
                if notion_client.update_page(page_id, repo_data):
                    results["updated"] += 1
                else:
                    results["errors"] += 1
            except Exception as e:
                logger.error(f"更新页面失败 ({repo_data['full_name']}): {e}")
                results["errors"] += 1

        # 删除不再 star 的仓库页面
        for page_id in to_delete:
            try:
                if notion_client.delete_page(page_id):
                    results["deleted"] += 1
                else:
                    results["errors"] += 1
            except Exception as e:
                logger.error(f"删除页面失败 (ID: {page_id}): {e}")
                results["errors"] += 1

        # 输出同步结果
        logger.info(f"同步完成: 创建 {results['created']} 个页面, "
                   f"更新 {results['updated']} 个页面, "
                   f"删除 {results['deleted']} 个页面, "
                   f"失败 {results['errors']} 个操作")

    except Exception as e:
        logger.error(f"同步过程中发生错误: {e}")

def needs_update(repo, page_data):
    """检查页面是否需要更新"""
    # 比较关键字段
    if (page_data.get("name") != repo["name"] or
        page_data.get("description") != repo["description"] or
        page_data.get("language") != repo["language"] or
        page_data.get("stars") != repo["stars"] or
        page_data.get("topics") != repo["topics"] or
        page_data.get("last_updated") != repo["last_updated"] or
        page_data.get("starred_at") != repo["starred_at"]):  # 添加 starred_at 的比较
        return True
    return False

# Example of how this module might be called (usually from main.py)
if __name__ == '__main__':
    # This block is for basic testing/demonstration if needed
    # In a real run, github_client and notion_client would be initialized
    # and passed in from main.py
    print("This script contains the sync logic and is typically run via main.py")
    logging.basicConfig(level=logging.INFO)
    logger.info("Sync logic module loaded. Run main.py to start the synchronization.") 