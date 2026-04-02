import logging
import os
from pathlib import Path
from modules import *        # 包含了 fileprocess 的所有函数

def split_docx_pipline(input_dir, output_dir, work_dir, days_to_keep):

    # print(input_dir)
    # print(output_dir)
    # print(work_dir)

    # 设置日志：先启用控制台日志以便可见清理过程，再清理旧日志，最后添加文件日志
    setup_logger(console=True)
    logging.info("日志设置初始化")
    clean_old_logs(work_dir, days_to_keep=days_to_keep)
    log_file = get_log_file_path(work_dir)
    setup_logger(log_file=log_file, console=True)
    logging.info("日志设置成功")

    # 调用 fileprocess 的函数
    # logging.info("选择模板文件")
    # mineru(output_dir)
    # logging.info("文件处理成功")

    # 调用 preprocess 管线
    logging.info("开始预处理管线")
    preprocess(output_dir, work_dir)
    logging.info("预处理完成")

    # 调用 collecttree 管线
    logging.info("开始树结构收集管线")
    collecttree(output_dir, work_dir)
    logging.info("树结构收集完成")

    # print(ai_chat_with_progress("提取这段话中的数字：一去二三里，烟村四五家，亭台六七座，八九十枝花。"))
    # print(ai_chat_with_progress("提取这段话中的数字：茅檐长扫净无苔，花木成畦手自栽。一水护田将绿绕，两山排闼送青来。"))
    # print(ai_chat_with_progress("An apple a day keeps doctor away.", "translation"))


    return
