import os
import logging
from pathlib import Path
from dotenv import load_dotenv

def setup_logging():
    """
    配置日志系统，将所有日志输出到标准输出，
    由Docker收集并管理日志
    """
    load_dotenv()
    
    root_logger = logging.getLogger()
    
    root_logger.setLevel(logging.INFO)
    
    console_handler = logging.StreamHandler()
    
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    console_handler.setFormatter(formatter)
    
    root_logger.addHandler(console_handler)
    
    return root_logger 