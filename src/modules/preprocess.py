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


def _step_bracket_format(file_path: str, work_dir: str) -> None:
    """规范化括号格式。

    - 允许单个后括号，如“1）”。
    - 对成对出现的括号，允许英文对 ``()`` 或中文对 ``（）``。
    - 如果前括号为英文，则追踪到的后括号不得为中文，反之亦然；
      若出现混合（英文前+中文后，或中文前+英文后），则把后括号
      转换成与前括号匹配的类型。
    - 输入为 ``selected_path`` 指定的文件，直接在原文件中修改。
    """

    logger = logging.getLogger(__name__)

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
    except Exception as e:
        logger.error("读取文件失败 %s，错误：%s", file_path, e)
        return

    stack = []
    changed = False
    result_chars = []

    for ch in text:
        if ch in "(（":
            stack.append(ch)
            result_chars.append(ch)
        elif ch in ")）":
            if stack:
                opening = stack.pop()
                # mismatched pair
                if opening == "(" and ch == "）":
                    ch = ")"
                    changed = True
                elif opening == "（" and ch == ")":
                    ch = "）"
                    changed = True
            else:
                # no opening, single closing allowed
                pass
            result_chars.append(ch)
        else:
            result_chars.append(ch)
    
    if changed:
        # count mismatches by comparing output to input
        formatted = ''.join(result_chars)
        num = sum(1 for a, b in zip(text, formatted) if a != b)
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(formatted)
            logger.info("已格式化括号 %d 个", num)
        except Exception as e:
            logger.error("写回文件失败 %s，错误：%s", file_path, e)
    else:
        logger.info("未发现需要格式化的括号")


def _step_extract_level_zero(file_path: str, work_dir: str) -> None:
    """提取0级标题及其内容。

    - 查找严格匹配 "# " + 汉字开头 的行，视为0级标题。
    - 从该行开始，收集直至下一个 "#" 出现前的所有文本块。
    - 将所有这样提取的段落统一写入同目录下的 ``addition.txt`` 文件。
    - 从源文件中删除这些内容。
    """

    logger = logging.getLogger(__name__)

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        logger.error("读取文件失败 %s，错误：%s", file_path, e)
        return

    # 正则匹配：以"# "开头，第3个字符是汉字
    level_zero_re = re.compile(r'^# [\u4e00-\u9fff]')
    
    extracted_content = []
    lines_to_remove = set()  # 记录要删除的行号
    
    i = 0
    while i < len(lines):
        if level_zero_re.match(lines[i]):
            # 找到0级标题
            start = i
            # 从下一行开始，直到遇到以#开头的行
            j = i + 1
            while j < len(lines):
                if lines[j].lstrip().startswith("#"):
                    break
                j += 1
            # 收集从start到j-1的所有行
            for k in range(start, j):
                extracted_content.append(lines[k])
                lines_to_remove.add(k)
            i = j
        else:
            i += 1
    
    # 如果找到了内容，写入addition.txt并删除源文件中的内容
    if extracted_content:
        out_dir = os.path.dirname(file_path)
        try:
            with open(os.path.join(out_dir, "addition.txt"), "w", encoding="utf-8") as f:
                f.writelines(extracted_content)
            logger.info("已提取0级标题内容，共 %d 行", len(extracted_content))
        except Exception as e:
            logger.error("写入addition.txt失败 %s，错误：%s", os.path.join(out_dir, "addition.txt"), e)
            return
        
        # 从源文件中删除
        remaining = [lines[k] for k in range(len(lines)) if k not in lines_to_remove]
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.writelines(remaining)
            logger.info("已从源文件中删除0级标题内容")
        except Exception as e:
            logger.error("写回源文件失败 %s，错误：%s", file_path, e)
    else:
        logger.info("未找到0级标题")


def _step_directory_extract(file_path: str, work_dir: str) -> None:
    """从文档中提取目录/正文标题行号并输出。

    - 寻找以 `#` 开头且文本部分包含“目”和“录”汉字的行，记为目录开始行。
    - 目录行之后第一个非空行的汉字部分作为第一个标题。
    - 在该标题之后 100 行范围内，寻找以 `#` 开头且汉字部分与第一个标题忽略空格后相同的行，
      将其视为正文第一个标题。
    - 最终在控制台打印这两个行号。所有匹配均忽略空格，仅对文字部分进行比较。
    """

    logger = logging.getLogger(__name__)

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        logger.error("读取文件失败 %s，错误：%s", file_path, e)
        return

    dir_line = None
    first_title = None
    first_title_line = None
    # locate directory start
    for idx, line in enumerate(lines):
        stripped = line.lstrip()
        if stripped.startswith("#"):
            text = stripped.lstrip("#").strip()
            # remove spaces for matching
            if "目" in text and "录" in text:
                dir_line = idx + 1
                break
    if dir_line is None:
        logger.info("未找到目录开始行")
        return

    # find next non-empty line after dir_line
    for j in range(dir_line, len(lines)):
        if lines[j].strip():
            # extract Chinese characters only
            first_title = "".join(re.findall(r"[\u4e00-\u9fff]+", lines[j]))
            first_title_line = j + 1
            break
    if first_title is None:
        logger.info("目录之后未找到第一个标题")
        print(f"目录开始行: {dir_line}, 正文第一个标题行: 未找到")
        return

    # search within 100 lines for a header matching first_title
    target = re.sub(r"\s+", "", first_title)
    content_line = None
    for k in range(first_title_line, min(len(lines), first_title_line + 100)):
        stripped = lines[k].lstrip()
        if stripped.startswith("#"):
            text = stripped.lstrip("#").strip()
            text_chinese = "".join(re.findall(r"[\u4e00-\u9fff]+", text))
            if re.sub(r"\s+", "", text_chinese) == target:
                content_line = k + 1
                break
    logger.info("目录开始行: %s, 正文第一个标题行: %s", dir_line, content_line if content_line is not None else '未找到')

    # 若找到了正文第一个标题行，则提取并移除目录部分
    if content_line is not None:
        start_idx = dir_line - 1
        end_idx = content_line - 1  # up to previous line
        directory_lines = lines[start_idx:end_idx]
        # 写入 directory.txt
        out_dir = os.path.dirname(file_path)
        try:
            with open(os.path.join(out_dir, "directory.txt"), "w", encoding="utf-8") as f:
                f.writelines(directory_lines)
        except Exception as e:
            logger.error("写入目录文件失败 %s，错误：%s", os.path.join(out_dir, "directory.txt"), e)
        # 从原始文件中移除目录段
        remaining = lines[:start_idx] + lines[end_idx:]
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.writelines(remaining)
        except Exception as e:
            logger.error("写回原始文件失败 %s，错误：%s", file_path, e)


def pipeline(output_dir: str, work_dir: str) -> Optional[str]:
    """
    执行工作管线

    当前行为：
    1. 根据 ``work_dir`` 初始化日志
    2. 搜索输出目录下各文件夹中的 ``full.md``
       - 记录来源文件夹并在输出目录生成结果
       - 如果超过一个文件触发警告
    3. 对找到的 ``full.md`` 文件进行标题空格对齐处理
    4. 对文中括号进行规范化处理，避免中英文混用等问题。
    5. 提取0级标题（"# "开头）及其后续内容，写入 ``addition.txt`` 并从源文件删除。
    6. 提取目录和正文首标题行号，并从源文档中删除目录部分写入单独的
       ``directory.txt``。

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
        # _step_directory_extract(selected_path, work_dir)
        _step_bracket_format(selected_path, work_dir)
        _step_extract_level_zero(selected_path, work_dir)
        

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

