import logging
import argparse
from sync_timestamp import get_last_sync_time, update_sync_time

logger = logging.getLogger(__name__)

def run_sync(github_client, notion_client, force_full_sync=False):
    """执行同步操作
    
    Args:
        github_client: GitHub API 客户端
        notion_client: Notion API 客户端
        force_full_sync: 是否强制执行全量同步，默认为 False
    """
    try:
        # 获取上次同步时间
        last_sync_time = None if force_full_sync else get_last_sync_time()
        
        # 获取 GitHub starred 仓库 (可能是增量也可能是全量)
        starred_repos = github_client.get_starred_repos(since=last_sync_time)
        if not starred_repos:
            if last_sync_time:
                logger.info(f"自 {last_sync_time} 以来没有新的 starred 仓库")
            else:
                logger.error("未找到任何 starred 仓库")
            return
        
        # 增量同步时只处理新 star 的仓库
        if last_sync_time:
            logger.info(f"增量同步模式：将处理自 {last_sync_time} 以来的 {len(starred_repos)} 个新 star 仓库")
            # 不删除仓库，只检查新增和更新
            to_delete = []
        else:
            # 全量同步需要获取所有 Notion 条目并比较
            logger.info(f"全量同步模式：处理所有 {len(starred_repos)} 个 starred 仓库")

        # 获取 Notion 数据库中的页面
        notion_pages = notion_client.query_database()
        if notion_pages is None:
            logger.error("获取 Notion 数据库页面失败")
            return
        logger.info(f"从 Notion 获取到 {len(notion_pages)} 个页面")

        # 构建多种 GitHub 仓库映射，用于更灵活的匹配
        github_id_repos = {str(repo["id"]): repo for repo in starred_repos}
        github_name_repos = {repo["full_name"]: repo for repo in starred_repos}
        
        # 确定需要创建、更新和删除的页面
        to_create = []
        to_update = []
        to_delete = []

        # 创建已处理标记，防止重复处理
        processed_repos = set()

        # 首先处理 Notion 中的每个页面
        for notion_key, page_id in notion_pages.items():
            # 标记是否找到匹配
            found_match = False
            
            # 尝试不同的匹配方式
            if notion_key.isdigit() and notion_key in github_id_repos:
                # 通过数字 ID 匹配
                repo_data = github_id_repos[notion_key]
                found_match = True
            elif notion_key.startswith("name:"):
                # 通过带前缀的全名匹配
                name = notion_key.replace("name:", "")
                if name in github_name_repos:
                    repo_data = github_name_repos[name]
                    found_match = True
            elif notion_key.startswith("unknown:"):
                # 尝试将未知格式当作全名处理
                unknown_value = notion_key.replace("unknown:", "")
                if unknown_value in github_name_repos:
                    repo_data = github_name_repos[unknown_value]
                    found_match = True
            
            if found_match:
                # 获取页面数据并检查是否需要更新
                page_data = notion_client.get_page(page_id)
                if page_data and needs_update(repo_data, page_data):
                    to_update.append((page_id, repo_data))
                
                # 标记为已处理
                processed_repos.add(str(repo_data["id"]))
                processed_repos.add(repo_data["full_name"])
        
        # 找出未处理的仓库（需要创建的页面）
        for repo_id, repo_data in github_id_repos.items():
            if repo_id not in processed_repos and repo_data["full_name"] not in processed_repos:
                to_create.append(repo_data)

        # 只有在全量同步模式下才查找需要删除的页面
        if not last_sync_time:
            # 找出需要删除的页面
            all_github_ids = set(github_id_repos.keys())
            all_github_full_names = set(repo['full_name'] for repo in starred_repos)
            
            for notion_key, page_id in notion_pages.items():
                is_found = False
                
                # 检查是否为数字 ID 键
                if notion_key.isdigit() and notion_key in all_github_ids:
                    is_found = True
                
                # 检查是否为全名键
                elif notion_key.startswith("name:"):
                    name = notion_key.replace("name:", "")
                    if name in all_github_full_names:
                        is_found = True
                
                # 检查是否为未知格式键，如果是，尝试作为全名处理
                elif notion_key.startswith("unknown:"):
                    unknown_value = notion_key.replace("unknown:", "")
                    if unknown_value in all_github_full_names:
                        is_found = True
                
                if not is_found:
                    to_delete.append(page_id)

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

        # 删除不再 star 的仓库页面（仅全量同步模式下）
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
        
        # 更新同步时间戳
        update_sync_time()

    except Exception as e:
        logger.error(f"同步过程中发生错误: {e}")

def needs_update(repo, page_data):
    """检查页面是否需要更新"""
    # 比较关键字段
    needs_update = False
    
    # 检查基本属性
    if (page_data.get("name") != repo["name"] or
        page_data.get("description") != repo["description"] or
        page_data.get("language") != repo["language"] or
        page_data.get("stars") != repo["stars"] or
        page_data.get("topics", []) != repo["topics"] or
        page_data.get("last_updated") != repo["last_updated"] or
        page_data.get("starred_at") != repo["starred_at"]):
        needs_update = True
    
    # 如果页面有 full_name 属性，也比较它
    if "full_name" in page_data and page_data["full_name"] != repo["full_name"]:
        needs_update = True
    
    return needs_update

# Example of how this module might be called (usually from main.py)
if __name__ == '__main__':
    # 设置命令行参数
    parser = argparse.ArgumentParser(description='同步 GitHub Stars 到 Notion')
    parser.add_argument('--full', action='store_true', help='强制执行全量同步')
    args = parser.parse_args()
    
    # 基本测试/演示
    print("这个脚本包含同步逻辑，通常通过 main.py 运行")
    print(f"同步模式: {'全量' if args.full else '增量'}")
    logging.basicConfig(level=logging.INFO)
    logger.info("同步逻辑模块已加载。运行 main.py 开始同步。") 