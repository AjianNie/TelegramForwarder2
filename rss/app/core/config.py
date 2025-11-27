import os
from dotenv import load_dotenv
from pathlib import Path
import logging
import sys
from utils.constants import RSS_HOST, RSS_PORT,DEFAULT_TIMEZONE,PROJECT_NAME
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

from utils.constants import RSS_MEDIA_DIR, RSS_MEDIA_PATH, RSS_DATA_DIR, get_rule_media_dir, get_rule_data_dir

load_dotenv()

class Settings:
    PROJECT_NAME: str = PROJECT_NAME
    HOST: str = RSS_HOST
    PORT: int = RSS_PORT
    TIMEZONE: str = DEFAULT_TIMEZONE
    BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
    DATA_PATH = RSS_DATA_DIR
    
    RSS_MEDIA_PATH = RSS_MEDIA_PATH
    MEDIA_PATH = RSS_MEDIA_DIR
    
    
    @classmethod
    def get_rule_media_path(cls, rule_id):
        """获取指定规则的媒体目录"""
        return get_rule_media_dir(rule_id)
        
    @classmethod
    def get_rule_data_path(cls, rule_id):
        """获取指定规则的数据目录"""
        return get_rule_data_dir(rule_id)
    
    def __init__(self):
        os.makedirs(self.DATA_PATH, exist_ok=True)
        os.makedirs(self.MEDIA_PATH, exist_ok=True)
        logger = logging.getLogger(__name__)
        logger.info(f"RSS数据路径: {self.DATA_PATH}")
        logger.info(f"RSS媒体路径: {self.MEDIA_PATH}")

settings = Settings() 