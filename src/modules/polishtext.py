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


def _step_file_collection(output_dir: str, work_dir: str) -> Optional[str]:
    """在输出目录中搜索第一个 `full.md` 文件并返回其路径。

    行为与 `generatetext._step_file_collection` 保持一致：
    - 遍历 `output_dir` 下的一层子目录，寻找每个子目录中的 `full.md`。
    - 若找到多个，仅返回第一个并记录警告。
    - 若未找到任何，返回 None。
    """

    logger = logging.getLogger(__name__)

    candidates = []  # 列表，包含 (文件夹名, 文件路径)
    if os.path.isdir(output_dir):
        for entry in sorted(os.listdir(output_dir)):
            subdir = os.path.join(output_dir, entry)
            if os.path.isdir(subdir):
                candidate = os.path.join(subdir, "full.md")
                if os.path.isfile(candidate):
                    candidates.append((entry, candidate))

    if not candidates:
        logger.warning("未找到任何full.md文件")
        return None

    selected_folder, selected_path = candidates[0]
    logger.info("选择文件 %s 来自文件夹 %s", selected_path, selected_folder)

    if len(candidates) > 1:
        logger.warning("存在复数文件，仅处理第一个")

    return selected_path


def polishtext(output_dir: str, work_dir: str):
    # 日志设置
    log_file = get_log_file_path(work_dir)
    setup_logger(log_file, console=True)
    logger = logging.getLogger(__name__)

    logger.info("管线开始，output_dir=%s work_dir=%s", output_dir, work_dir)
    # 1. 读取配置中的分段长度（支持多个可能的键名），缺省为6000
    config_path = os.path.join(work_dir, "config.ini")
    polish_length = 6000
    try:
        cfg = configparser.ConfigParser()
        cfg.read(config_path, encoding="utf-8")
        if cfg.has_section('settings'):
            # 仅使用专用配置项 polish_length，忽略旧的 max_generate_lenth
            if cfg.has_option('settings', 'polish_length'):
                try:
                    polish_length = int(cfg.get('settings', 'polish_length'))
                except Exception:
                    logger.warning('配置项 polish_length 不是有效整数，使用默认 %d', polish_length)
            else:
                logger.info('配置中未找到 polish_length，继续使用默认 %d（忽略旧配置项）', polish_length)
    except Exception as e:
        logger.warning('读取配置文件失败: %s，使用默认polish_length=%d', e, polish_length)

    logger.info('使用分段长度 polish_length=%d', polish_length)

    # 2. 使用 _step_file_collection 查找 selected_path（第一个 full.md 所在子目录），在该目录下处理 rewrite.txt
    selected_path = _step_file_collection(output_dir, work_dir)
    if not selected_path:
        logger.error('未找到 full.md，无法定位处理目录')
        return
    selected_dir = os.path.dirname(selected_path)
    rewrite_path = os.path.join(selected_dir, 'rewrite.txt')
    if not os.path.isfile(rewrite_path):
        logger.error('未找到 rewrite.txt 在 %s', selected_dir)
        return

    logger.info('找到待润色文件：%s', rewrite_path)

    # 3. 读取 rewrite.txt 内容，优先使用 utf-8，失败尝试 gbk
    text = ''
    try:
        with open(rewrite_path, 'r', encoding='utf-8') as f:
            text = f.read()
    except Exception:
        try:
            with open(rewrite_path, 'r', encoding='gbk') as f:
                text = f.read()
        except Exception as e:
            logger.error('读取文件失败: %s', e)
            return

    if not text.strip():
        logger.warning('rewrite.txt 文件为空，退出')
        return

    # 4. 分段并调用大模型进行润色
    instruction = (
        '请对以下科研课题文稿进行专业规整润色，执行要求：\n'
        '1、标题规范：修正所有不规范多级编号和重复的题目，按正规科研文档层级重新梳理；\n'
        '2、冗余标题删除：删除所有无正文直接跟随的重复标题（标题后无实质内容，仅接空行或其他标题），只保留首次出现且有正文的标题；\n'
        '3、去口语化：删除所有口语、赘述、冗余语气表述，全程使用正式严谨书面语体；\n'
        '4、去AI化：剔除所有AI模板套话、空泛铺垫、程式化排比、生硬衔接虚词，只保留实质性专业内容；\n'
        '5、排版保持原有章节结构、段落划分、图表标注、表格内容不变，仅做文字精炼与格式规整；\n'
        '6、只输出润色完成后的纯文本内容，不输出任何说明、解释、多余话术、修改备注，只给成品文稿。\n\n'
        '【待润色文本】\n'
    )

    results = []
    total_len = len(text)
    logger.info('待处理文本总长度：%d 字符', total_len)

    for i in range(0, total_len, polish_length):
        chunk = text[i:i+polish_length]
        prompt = instruction + chunk
        logger.info('正在处理第 %d 段（字符范围 %d-%d）', i//polish_length + 1, i, min(i+polish_length, total_len))
        try:
            polished = ai_chat_with_progress(prompt, task_type='default', log_to_console=False)
            if polished is None:
                logger.warning('第 %d 段返回为空结果，跳过', i//polish_length + 1)
                polished = ''
        except Exception as e:
            logger.exception('调用AI出错：%s，将段落原文写入结果以防丢失', e)
            polished = chunk

        results.append(polished)

    # 5. 将所有润色结果写入 polishedtext.txt（覆盖写入），放在与 rewrite.txt 相同的目录
    rewrite_dir = os.path.dirname(rewrite_path)
    out_path = os.path.join(rewrite_dir, 'polishedtext.txt')
    try:
        os.makedirs(rewrite_dir, exist_ok=True)
        with open(out_path, 'w', encoding='utf-8') as f:
            for piece in results:
                f.write(piece)
                f.write('\n')
        logger.info('润色结果已保存到 %s', out_path)
    except Exception as e:
        logger.exception('写入润色结果失败：%s', e)

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