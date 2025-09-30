import logging
from modules import *

def split_docx_pipline(input_dir, output_dir, work_dir, days_to_keep):

    # print(input_dir)
    # print(output_dir)
    # print(work_dir)

    # 设置日志路径、初始化日志、清理旧日志
    log_file = get_log_file_path(work_dir)
    setup_logger(log_file=log_file, console=False)
    clean_old_logs(work_dir, days_to_keep=days_to_keep)
    logging.info("日志设置成功")

    return
