import os
import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

TIMESTAMP_FILE = "last_sync.json"

def get_last_sync_time():
    """获取上次同步时间

    Returns:
        str: ISO 8601 格式的时间戳，如果不存在则返回 None
    """
    if not os.path.exists(TIMESTAMP_FILE):
        logger.info("未找到上次同步记录，将执行全量同步")
        return None
    
    try:
        with open(TIMESTAMP_FILE, 'r') as f:
            data = json.load(f)
            last_sync = data.get('last_sync_time')
            if last_sync:
                logger.info(f"上次同步时间: {last_sync}")
            else:
                logger.info("没有有效的上次同步记录，将执行全量同步")
            return last_sync
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"读取上次同步时间失败: {e}")
        return None

def update_sync_time():
    """更新同步时间为当前时间

    Returns:
        str: 更新后的 ISO 8601 格式时间戳
    """
    now = datetime.now(timezone.utc).isoformat()
    
    try:
        with open(TIMESTAMP_FILE, 'w') as f:
            json.dump({"last_sync_time": now}, f, indent=4)
        logger.info(f"已更新同步时间戳为: {now}")
        return now
    except IOError as e:
        logger.error(f"更新同步时间戳失败: {e}")
        return None

if __name__ == "__main__":
    # 设置日志
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # 测试时间戳管理功能
    last_time = get_last_sync_time()
    print(f"上次同步时间: {last_time or '无'}")
    
    new_time = update_sync_time()
    print(f"新的同步时间: {new_time}")
    
    # 确认更新
    updated_time = get_last_sync_time()
    print(f"更新后的同步时间: {updated_time}") 