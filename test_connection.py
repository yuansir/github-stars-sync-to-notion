import logging
import requests
import re
from config import load_config
from notion_client import NotionClient

# 设置详细的日志记录
logging.basicConfig(level=logging.DEBUG, 
                   format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def is_valid_notion_id(id_string):
    """验证是否是有效的 Notion ID 格式"""
    # 移除所有连字符
    clean_id = id_string.replace('-', '')
    # 检查是否是32位的十六进制字符
    hex_pattern = re.compile(r'^[0-9a-f]{32}$', re.I)
    return bool(hex_pattern.match(clean_id))

def verify_notion_integration():
    """验证 Notion 集成配置"""
    try:
        config = load_config()
        
        # 1. 验证 token 格式
        token = config['notion_token']
        if not (token.startswith('secret_') or token.startswith('ntn_')):
            logger.error("""
Notion token 格式错误！
- Token 应该以 'ntn_' 或 'secret_' 开头
- 可以在 https://www.notion.so/my-integrations 找到正确的 token
- 确保你是工作区的管理员（Settings & Members 中查看）
""")
            return False
            
        # 2. 验证数据库 ID 格式
        db_id = config['notion_database_id']
        if not is_valid_notion_id(db_id):
            logger.error("""
数据库 ID 格式错误！
- ID 应该是 32 位的十六进制字符
- 可以包含或不包含连字符(-)
- 可以从数据库页面的 Share 链接中获取
- 例如：1dba3a390bd0805da1d6c1149461fb24
""")
            return False
            
        logger.info("配置格式验证通过")
        return True
    except Exception as e:
        logger.error(f"配置验证失败: {e}")
        return False

def test_notion_connection():
    """测试 Notion 数据库连接"""
    try:
        if not verify_notion_integration():
            return False
            
        config = load_config()
        logger.info(f"成功加载配置，数据库 ID: {config['notion_database_id']}")
        
        notion_client = NotionClient(
            token=config['notion_token'],
            database_id=config['notion_database_id']
        )
        
        # 首先尝试获取用户信息，验证 token 是否有效
        users_url = "https://api.notion.com/v1/users/me"
        try:
            user_response = notion_client._make_request("GET", users_url)
            logger.info(f"认证成功！集成名称: {user_response.get('name')}")
        except Exception as e:
            logger.error("Token 验证失败，请检查 token 是否正确")
            return False
        
        # 测试数据库连接
        url = f"https://api.notion.com/v1/databases/{notion_client._database_id}"
        try:
            response = notion_client._make_request("GET", url)
            
            # 打印数据库信息
            db_title = response.get('title', [{}])[0].get('plain_text', 'Untitled')
            logger.info(f"成功连接到数据库: {db_title}")
            logger.info("""
数据库访问权限验证成功！

如果需要修改数据库权限：
1. 打开数据库页面
2. 点击右上角的 Share 按钮
3. 点击 "Add connections"
4. 搜索并选择你的集成名称

注意：确保你的集成具有适当的权限（读写权限）。
""")
            return True
            
        except requests.exceptions.HTTPError as e:
            if '404' in str(e):
                logger.error("""
数据库访问失败！根据 Notion API 文档，请检查：
1. 数据库 ID 是否正确：
   - 打开数据库页面
   - 点击 Share 按钮
   - 复制链接中的 ID 部分
2. 数据库是否已与集成共享：
   - 打开数据库页面
   - 点击右上角 "..."
   - 选择 "Add connections"
   - 添加你的集成
3. 集成权限：
   - 访问 https://www.notion.so/my-integrations
   - 确认你是工作区管理员
   - 检查集成的权限设置
""")
            elif '401' in str(e):
                logger.error("""
认证失败！请检查：
1. Token 是否正确（以 'secret_' 开头）
2. Token 是否已过期
3. 是否是管理员账户
""")
            else:
                logger.error(f"API 请求失败: {e}")
            return False
            
    except Exception as e:
        logger.error(f"连接测试失败: {e}")
        return False

if __name__ == "__main__":
    print("""
开始测试 Notion 数据库连接...
参考文档：https://developers.notion.com/reference/
""")
    test_notion_connection() 