# logger_config.py
import logging
import os
from logging.handlers import TimedRotatingFileHandler

def get_file_logger(log_dir="logs"):
    os.makedirs(log_dir, exist_ok=True)
    logger = logging.getLogger("quality_check")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    # 控制台
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # 文件按日期轮转
    log_file = os.path.join(log_dir, "质检日志")
    fh = TimedRotatingFileHandler(log_file, when="D", interval=1, backupCount=30, encoding="utf-8")
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    return logger