# 负责日志处理和记录


import logging
from logging.handlers import RotatingFileHandler

# 初始化根日志记录器
logger = logging.getLogger("AnkiRepository")
logger.setLevel(logging.DEBUG)

# 控制台处理器
console_handler = logging.StreamHandler()
console_formatter = logging.Formatter(
    '[%(asctime)s] %(levelname)s @ %(module)s.%(funcName)s - %(message)s'
)
console_handler.setFormatter(console_formatter)

# 文件处理器（自动轮换）
file_handler = RotatingFileHandler(
    'ankirepo.log', 
    maxBytes=1024*1024*5,  # 5MB
    backupCount=3,
    encoding='utf-8'
)
file_formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
file_handler.setFormatter(file_formatter)

# 添加处理器
logger.addHandler(console_handler)
logger.addHandler(file_handler)

