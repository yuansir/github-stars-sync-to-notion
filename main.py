import logging
import sys
import argparse

from config import load_config, logger # Use the logger from config
from github_client import GitHubClient
from notion_client import NotionClient
from sync_logic import run_sync

def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="同步 GitHub Stars 到 Notion 数据库")
    parser.add_argument('--full', action='store_true', help='强制执行全量同步')
    args = parser.parse_args()
    
    if args.full:
        logger.info("已启用强制全量同步模式")
    else:
        logger.info("使用增量同步模式（如没有历史记录则会执行全量同步）")
    
    logger.info("脚本已启动")

    # 加载配置
    try:
        config = load_config()
    except ValueError as e:
        logger.error(f"配置错误: {e}")
        sys.exit(1) # Exit if config is invalid
    except Exception as e:
        logger.exception(f"加载配置时发生意外错误: {e}")
        sys.exit(1)

    # 初始化客户端
    try:
        github_client = GitHubClient(token=config['github_token'])
        notion_client = NotionClient(
            token=config['notion_token'],
            database_id=config['notion_database_id']
        )
    except ValueError as e:
        logger.error(f"初始化客户端错误: {e}")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"初始化客户端时发生意外错误: {e}")
        sys.exit(1)

    # 执行同步流程
    try:
        run_sync(github_client, notion_client, force_full_sync=args.full)
    except Exception as e:
        # 捕获同步逻辑中的所有未处理异常
        logger.exception(f"同步过程中发生意外错误: {e}")
        sys.exit(1)

    logger.info("脚本成功完成")
    sys.exit(0)

if __name__ == "__main__":
    main() 