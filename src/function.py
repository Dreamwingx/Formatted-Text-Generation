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


    print(ai_chat_with_progress("提取这段话中的数字：一去二三里，烟村四五家，亭台六七座，八九十枝花。"))
    print(ai_chat_with_progress("提取这段话中的数字：茅檐长扫净无苔，花木成畦手自栽。一水护田将绿绕，两山排闼送青来。"))


    return
