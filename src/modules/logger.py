import logging
from datetime import datetime
import os
import time

def get_log_file_path(work_dir):
    """
    按照 log/YYYY/MM/DD/run_HHMMSS.log 格式，生成日志文件路径，
    并确保目录存在。
    返回完整日志文件路径字符串。
    """
    now = datetime.now()
    log_dir = os.path.join(work_dir, "log", now.strftime("%Y"), now.strftime("%m"), now.strftime("%d"))
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, now.strftime("run_%H_%M_%S.log"))
    return log_file

def setup_logger(log_file=None, console=True):
    """
    设置日志，默认打印到控制台。
    如果传入log_file，则同时保存日志到文件。
    可选参数console控制是否打印到控制台，默认为True。
    """
    # 使用根 logger，先清除已有 handlers，确保多次调用时不会重复添加
    root_logger = logging.getLogger()
    # 移除已有 handlers
    for h in list(root_logger.handlers):
        root_logger.removeHandler(h)

    root_logger.setLevel(logging.INFO)

    fmt = logging.Formatter(
        '[%(asctime)s] %(levelname)s [%(filename)s:%(lineno)d %(funcName)s()] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    if console:
        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        root_logger.addHandler(sh)

    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        fh = logging.FileHandler(log_file, encoding='utf-8')
        fh.setFormatter(fmt)
        root_logger.addHandler(fh)

def clean_old_logs(work_dir, days_to_keep=None):
    """
    删除指定目录下的日志文件，并尝试删除空目录。

    :param log_root_dir: 日志根目录，建议传入日志最顶层目录，比如 "logs"
    :param days_to_keep: 保留多少天以内的日志，None表示删除所有日志
    """
    log_root_dir = os.path.join(work_dir, "log")

    if not os.path.exists(log_root_dir):
        logging.warning(f"{log_root_dir} 不存在，跳过删除日志操作。")
        return

    now = time.time()
    keep_seconds = days_to_keep * 86400 if days_to_keep is not None else None

    deleted_files_count = 0
    for root, dirs, files in os.walk(log_root_dir):
        for filename in files:
            file_path = os.path.join(root, filename)
            if not filename.endswith(".log"):
                continue

            try:
                if keep_seconds is None:
                    os.remove(file_path)
                    deleted_files_count += 1
                    logging.debug(f"删除日志文件: {file_path}")
                else:
                    file_mtime = os.path.getmtime(file_path)
                    if (now - file_mtime) > keep_seconds:
                        os.remove(file_path)
                        deleted_files_count += 1
                        logging.debug(f"删除日志文件: {file_path}")
            except Exception as e:
                logging.error(f"删除日志文件失败 {file_path}，错误: {e}")

    logging.info(f"日志文件清理完成，删除文件数量：{deleted_files_count}")

    # 删除空目录，从底层开始删除
    deleted_dirs_count = 0
    for root, dirs, files in os.walk(log_root_dir, topdown=False):
        # 如果目录为空则删除
        if not dirs and not files:
            try:
                os.rmdir(root)
                deleted_dirs_count += 1
                logging.debug(f"删除空目录: {root}")
            except Exception as e:
                logging.warning(f"删除目录失败 {root}，错误: {e}")

    logging.info(f"空目录清理完成，删除目录数量：{deleted_dirs_count}")
