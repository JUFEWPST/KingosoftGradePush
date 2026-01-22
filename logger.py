import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent
def setup_logging(log_file=f"{BASE_DIR}/app.log", log_level=logging.INFO):
    """
    配置全局日志系统
    """
    # 创建 logger
    logger = logging.getLogger()
    logger.setLevel(log_level)

    # 如果已经有 handlers，说明已经被配置过，直接返回
    if logger.handlers:
        return logger

    # 创建 formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(module)s.%(funcName)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 创建 RotatingFileHandler (最大 5MB, 保留 5 个备份)
    file_handler = RotatingFileHandler(
        log_file, maxBytes=5*1024*1024, backupCount=5, encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)

    # 创建 StreamHandler (输出到控制台)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)

    # 添加 handlers 到 logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
