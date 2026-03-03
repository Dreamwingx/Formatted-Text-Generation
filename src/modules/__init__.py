from .logger import get_log_file_path, setup_logger, clean_old_logs
from .ai_api_client import ai_chat, ai_chat_with_progress
# 从 fileprocess 导出
from .fileprocess import (
    select_file,
    get_token,
    apply_upload_url,
    upload_file_to_url,
    poll_extract_result,
    download_url_to_file,
    extract_zip_to_dir,
    mineru,
)

__all__ = [
    # logger 接口
    'get_log_file_path',      # 获取日志文件路径
    'setup_logger',           # 设置日志记录器
    'clean_old_logs',         # 清理旧日志文件

    # ai_api_client 接口
    'ai_chat',                # ai问答调用
    'ai_chat_with_progress',  # 带进度条的ai问答

    # fileprocess 接口
    'select_file',
    'get_token',
    'apply_upload_url',
    'upload_file_to_url',
    'poll_extract_result',
    'download_url_to_file',
    'extract_zip_to_dir',
    'mineru',
]