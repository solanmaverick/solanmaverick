import logging
import sys
from pathlib import Path
from datetime import datetime

# 创建logs目录
Path("logs").mkdir(exist_ok=True)

# 创建logger
logger = logging.getLogger('discord_bot')
logger.setLevel(logging.DEBUG)

# 创建控制台处理器
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(console_format)
logger.addHandler(console_handler)

# 创建文件处理器
log_file = f'logs/discord_bot_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
file_handler = logging.FileHandler(log_file, encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_format)
logger.addHandler(file_handler)

# 禁用其他logger的传播
logger.propagate = False