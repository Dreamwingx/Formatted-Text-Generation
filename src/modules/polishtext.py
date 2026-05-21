import json
import logging
import os
import re 
from typing import Optional, Dict, Tuple
import threading
import tkinter as tk
from tkinter import scrolledtext
import configparser

if __name__ == "__main__":
    # 直接运行时，使用绝对导入
    from ai_api_client import ai_chat_with_progress
    from logger import get_log_file_path, setup_logger
else:
    # 作为模块导入时，使用相对导入
    from .ai_api_client import ai_chat_with_progress
    from .logger import get_log_file_path, setup_logger

def polishtext(output_dir: str, work_dir: str):
    # 日志设置
    log_file = get_log_file_path(work_dir)
    setup_logger(log_file, console=True)
    logger = logging.getLogger(__name__)

    logger.info("管线开始，output_dir=%s work_dir=%s", output_dir, work_dir)
    

if __name__ == "__main__":
    # 输入文件位置
    input_dir = r"D:\compile\Test\input"
    # 输出文件位置
    output_dir = r"D:\compile\Test\output"
    # 代码保存位置
    work_dir = r"D:\compile\Test"

    # 确保目录存在
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(work_dir, exist_ok=True)

    polishtext(output_dir, work_dir)  