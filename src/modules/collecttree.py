import json
import logging
import os
import re
from typing import Optional, Dict, Tuple

from ai_api_client import ai_chat_with_progress
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

    result_file = os.path.join(output_dir, "filecollection_result.txt")
    try:
        with open(result_file, "w", encoding="utf-8") as f:
            f.write(f"{selected_folder}\n")
    except Exception as e:
        logger.error("写入结果文件失败 %s，错误：%s", result_file, e)

    return selected_path

def _extract_serial_and_title(title_line: str) -> Tuple[str, str, bool]:
    """从标题行中提取序号、题目和规范格式标志。
    
    返回值:
        (serial, title, is_standard):
        - serial: 序号字符串（例如 "1.2", "（1）", "(1)", "①" 等）
        - title: 题目名称（#后面的汉字部分）
        - is_standard: 是否为规范格式（点分十进制）
    """
    # 移除#符号并去除前导空格
    content = title_line.lstrip('#').strip()
    
    if not content:
        return "", "", False
    
    # 规范格式: 1, 1.1, 1.1.1 等（数字和点的组合）
    standard_match = re.match(r'^(\d+(?:\.\d+)*)\s+(.*?)$', content)
    
    # 中文括号格式: （1）, （1.1） 等
    cn_bracket_match = re.match(r'^(（\d+(?:\.\d+)*）)\s+(.*?)$', content)
    
    # 圆括号格式: (1), (1.1) 等
    paren_match = re.match(r'^(\(\d+(?:\.\d+)*\))\s+(.*?)$', content)
    
    # 中文数字标号: ①, ②, ③ 等
    chinese_num_match = re.match(r'^([①②③④⑤⑥⑦⑧⑨⑩]+)\s+(.*?)$', content)
    
    # 按优先级匹配
    if standard_match:
        serial = standard_match.group(1)
        title = standard_match.group(2)
        is_standard = True
    elif cn_bracket_match:
        serial = cn_bracket_match.group(1)
        title = cn_bracket_match.group(2)
        is_standard = False
    elif paren_match:
        serial = paren_match.group(1)
        title = paren_match.group(2)
        is_standard = False
    elif chinese_num_match:
        serial = chinese_num_match.group(1)
        title = chinese_num_match.group(2)
        is_standard = False
    else:
        # 没有匹配到序号格式
        serial = ""
        title = content
        is_standard = False
    
    return serial, title, is_standard

def _get_level(serial: str, is_standard: bool, last_standard_level: int, 
               non_standard_map: Dict[str, int]) -> int:
    """根据序号格式确定层级。
    
    规范格式的层级 = 点数 + 1
    非规范格式在上一个规范层级到下一个规范层级之间，
    每出现一种新格式就分配为 last_standard_level + 1
    """
    if is_standard:
        # 规范格式：层级 = 点数 + 1
        level = serial.count('.') + 1
        return level
    else:
        # 非规范格式
        if serial not in non_standard_map:
            # 新的非规范格式，分配为上一个规范层级 + 1
            non_standard_map[serial] = last_standard_level + 1
        return non_standard_map[serial]

def function(selected_path: str, output_dir: str) -> Optional[str]:
    """解析markdown文件并生成包含结构化节点的json文件。
    
    参数:
        selected_path: 要处理的md文件路径
        output_dir: 输出目录
        
    返回值:
        生成的treenode.json文件路径；如果失败则返回None
    """
    logger = logging.getLogger(__name__)
    
    try:
        with open(selected_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        logger.error("读取文件失败 %s，错误：%s", selected_path, e)
        return None
    
    nodes = []
    current_block = None
    block_count = 0
    last_standard_level = 0
    non_standard_map: Dict[str, int] = {}
    
    # 逐行处理
    for line in lines:
        if line.strip().startswith("#"):
            # 保存前一个块
            if current_block:
                # 计算正文字数
                text = current_block["正文"].strip()
                # 统计所有非空格字符数
                char_count = sum(1 for char in text if not char.isspace())
                current_block["正文字数"] = char_count
                current_block["正文"] = text
                nodes.append(current_block)
            
            # 提取序号和题目
            serial, title, is_standard = _extract_serial_and_title(line)
            
            # 确定层级
            if is_standard:
                level = serial.count('.') + 1
                last_standard_level = level
                non_standard_map.clear()
            else:
                level = _get_level(serial, False, last_standard_level, non_standard_map)
            
            # 创建新块
            block_count += 1
            current_block = {
                "编号": block_count,
                "序号": serial,
                "题目": title,
                "层级": str(level),
                "正文": "",
                "正文字数": 0
            }
        else:
            # 添加内容到当前块的正文
            if current_block is not None:
                current_block["正文"] += line
    
    # 保存最后一个块
    if current_block:
        text = current_block["正文"].strip()
        char_count = sum(1 for char in text if not char.isspace())
        current_block["正文字数"] = char_count
        current_block["正文"] = text
        nodes.append(current_block)
    
    # 为每个节点添加指针字段
    for node in nodes:
        node["父节点"] = 0
        node["子节点"] = 0
        node["兄弟节点"] = 0
    
    # 建立层级关系和指针
    # 使用栈来追踪每个层级的最后一个节点索引
    level_stack: Dict[int, int] = {}  # level -> node_index
    
    for i, node in enumerate(nodes):
        current_level = int(node["层级"])
        current_node_num = node["编号"]
        
        # 查找父节点（上一个更浅的层级）
        parent_level = current_level - 1
        if parent_level in level_stack and parent_level > 0:
            parent_idx = level_stack[parent_level]
            parent_node = nodes[parent_idx]
            node["父节点"] = parent_node["编号"]
            
            # 如果父节点的第一个子节点编号为0，设置这个节点
            if parent_node["子节点"] == 0:
                parent_node["子节点"] = current_node_num
        
        # 查找兄弟节点（同层的前一个节点）
        if current_level in level_stack:
            sibling_idx = level_stack[current_level]
            sibling_node = nodes[sibling_idx]
            sibling_node["兄弟节点"] = current_node_num
        
        # 更新当前层级的最后一个节点索引
        level_stack[current_level] = i
        
        # 清除更深层级的记录（因为后面不再需要）
        levels_to_remove = [level for level in level_stack if level > current_level]
        for level in levels_to_remove:
            del level_stack[level]
    
    # 保存为json文件
    output_file = os.path.join(output_dir, "treenode.json")
    try:
        data = {
            "source_file": selected_path,
            "total_nodes": len(nodes),
            "nodes": nodes
        }
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info("成功处理文件，生成 %d 个节点，保存到 %s", len(nodes), output_file)
        return output_file
    except Exception as e:
        logger.error("保存json文件失败 %s，错误：%s", output_file, e)
        return None

def collecttree(output_dir: str, work_dir: str):
    # 日志设置
    log_file = get_log_file_path(work_dir)
    setup_logger(log_file, console=True)
    logger = logging.getLogger(__name__)

    logger.info("管线开始，output_dir=%s work_dir=%s", output_dir, work_dir)

    # 执行各个处理步骤
    # 寻找需要处理的文件
    selected_path = _step_file_collection(output_dir, work_dir)
    if selected_path:
        logger.info("开始处理文件：%s", selected_path)
        # 处理文件并生成treenode.json
        result = function(selected_path, output_dir)
        if result:
            logger.info("处理完成，输出文件：%s", result)
        else:
            logger.error("处理文件失败")


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

    collecttree(output_dir, work_dir)