import logging
import os
import re
from typing import Optional

# use absolute import so script can run directly
from logger import get_log_file_path, setup_logger


def _step_file_collection(output_dir: str, work_dir: str) -> Optional[str]:
    """在输出目录中搜索 ``full.md`` 文件。

    - 遍历 ``output_dir`` 下的一级子目录。
    - 找到每个子目录中是否存在名为 ``full.md`` 的文件。
    - 如果找到多个，只处理第一个并记录警告。
    - 处理意味着：
        * 日志输出哪个子目录包含被选中的文件。
        * 在 ``output_dir`` 中生成一个 ``filecollection_result.txt``，
          内容是被选中文件的文件夹名。
    - 如果根本未找到任何 ``full.md``，记录一个警告。

    返回值:
        选中的 ``full.md`` 文件的绝对路径；如果未找到则返回 ``None``。
    """

    logger = logging.getLogger(__name__)

    candidates = []  # list of (folder_name, file_path)
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

    result_file = os.path.join(output_dir, "filecollection_result.txt")
    try:
        with open(result_file, "w", encoding="utf-8") as f:
            f.write(f"{selected_folder}\n")
    except Exception as e:
        logger.error("写入结果文件失败 %s，错误：%s", result_file, e)

    return selected_path


def _step_title_space_align(file_path: str, work_dir: str) -> None:
    """对单个 `full.md` 文件中的标题进行空格对齐。

    - 识别以 `#` 开头的行为标题。
    - 对匹配“数字序号（如 1、1.1、（1）等）+ 汉字”形式的标题，
      规范为：`#` + 空格 + 数字序号 + 空格 + 汉字。
    - 仅处理由 `_step_file_collection` 返回的那个文件路径。
    """

    logger = logging.getLogger(__name__)

    heading_re = re.compile(r'^(#+)\s*(.*)$')
    number_re = re.compile(r'^([（(]?\d+(?:\.\d+)*[）)]?)[\.、．\s　]*(.*)$')

    # file_path is expected to be a single full.md file
    if not os.path.isfile(file_path):
        logger.warning("文件不存在，无法格式化标题：%s", file_path)
        return

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        logger.error("读取文件失败 %s，错误：%s", file_path, e)
        return

    new_lines = []
    changed = False
    for line in lines:
        m = heading_re.match(line)
        if m:
            prefix, rest = m.groups()
            rest = rest.strip()
            m2 = number_re.match(rest)
            if m2:
                number, text = m2.groups()
                if text and re.search(r'[\u4e00-\u9fff]', text):
                    # 去除 text 开头的多余标点或空白
                    text = text.lstrip(" .、．　")
                    new_line = f"{prefix} {number} {text}\n"
                    if new_line != line:
                        line = new_line
                        changed = True
        new_lines.append(line)

    if changed:
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
            logger.info("已格式化标题空格：%s", file_path)
        except Exception as e:
            logger.error("写回文件失败 %s，错误：%s", file_path, e)
    else:
        logger.info("未发现需要格式化的标题")


def pipeline(output_dir: str, work_dir: str) -> Optional[str]:
    """
    执行工作管线

    当前行为：
    1. 根据 ``work_dir`` 初始化日志
    2. 搜索输出目录下各文件夹中的 ``full.md``
       - 记录来源文件夹并在输出目录生成结果
       - 如果超过一个文件触发警告
    3. 对找到的 ``full.md`` 文件进行标题空格对齐处理

    返回值:
        If a ``full.md`` was found, its absolute path is returned; otherwise ``None``.
    """

    # 日志设置
    log_file = get_log_file_path(work_dir)
    setup_logger(log_file, console=True)
    logger = logging.getLogger(__name__)

    logger.info("管线开始，output_dir=%s work_dir=%s", output_dir, work_dir)

    # 执行各个处理步骤
    selected_path = _step_file_collection(output_dir, work_dir)
    if selected_path:
        _step_title_space_align(selected_path, work_dir)

    logger.info("管线执行完成")

    return selected_path


if __name__ == "__main__":
    # 输入文件位置（当前未使用，可根据需要扩展）
    input_dir = r"D:\compile\Test\input"
    # 输出文件位置
    output_dir = r"D:\compile\Test\output"
    # 代码保存位置
    work_dir = r"D:\compile\Test"

    # 确保目录存在
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(work_dir, exist_ok=True)

    pipeline(output_dir, work_dir)

