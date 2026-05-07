import json
import logging
import os
import re 
from typing import Optional, Dict, Tuple

if __name__ == "__main__":
    # 直接运行时，使用绝对导入
    from ai_api_client import ai_chat_with_progress
    from logger import get_log_file_path, setup_logger
else:
    # 作为模块导入时，使用相对导入
    from .ai_api_client import ai_chat_with_progress
    from .logger import get_log_file_path, setup_logger

def _step_file_collection(output_dir: str, work_dir: str) -> Optional[str]:
    """在输出目录中搜索 ``full.md`` 文件。

    - 遍历 ``output_dir`` 下的一级子目录。
    - 找到每个子目录中是否存在名为 ``full.md`` 的文件。
    - 如果找到多个，只处理第一个并记录警告。
    - 处理意味着：
        * 日志输出哪个子目录包含被选中的文件。
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

    return selected_path

def _extract_serial_and_title(title_line: str) -> Tuple[str, str, bool, str]:
    """从标题行中提取序号、题目、规范格式标志和类别。
    
    返回值:
        (serial, title, is_standard, category):
        - serial: 序号字符串（例如 "1.2", "（1）", "(1)", "①" 等）
        - title: 题目名称（#后面的汉字部分）
        - is_standard: 是否为规范格式（点分十进制）
        - category: 类别 ("standard", "bracket", "chinese_num", "other") 
    """
    # 移除#符号并去除前导空格
    content = title_line.lstrip('#').strip()
    
    if not content:
        return "", "", False, "other"
    
    # 规范格式: 1, 1.1, 1.1.1 等（数字和点的组合）
    standard_match = re.match(r'^(\d+(?:\.\d+)*)\s+(.*?)$', content)
    
    # 中文括号格式: （1）, （1.1） 等
    cn_bracket_match = re.match(r'^(（\d+(?:\.\d+)*）)\s+(.*?)$', content)
    
    # 圆括号格式: (1), (1.1) 等
    paren_match = re.match(r'^(\(\d+(?:\.\d+)*\))\s+(.*?)$', content)
    
    # 中文数字标号: ①, ②, ③ 等
    chinese_num_match = re.match(r'^([①②③④⑤⑥⑦⑧⑨⑩]+)\s+(.*?)$', content)
    
    # 右中文括号格式: 1）, 1.1） 等
    right_cn_paren_match = re.match(r'^(\d+(?:\.\d+)*\）)\s+(.*?)$', content)
    
    # 右圆括号格式: 1), 1.1) 等
    right_paren_match = re.match(r'^(\d+(?:\.\d+)*\))\s+(.*?)$', content)
    
    # 按优先级匹配
    if standard_match:
        serial = standard_match.group(1)
        title = standard_match.group(2)
        is_standard = True
        category = "standard"
    elif cn_bracket_match:
        serial = cn_bracket_match.group(1)
        title = cn_bracket_match.group(2)
        is_standard = False
        category = "bracket"
    elif paren_match:
        serial = paren_match.group(1)
        title = paren_match.group(2)
        is_standard = False
        category = "bracket"
    elif right_cn_paren_match:
        serial = right_cn_paren_match.group(1)
        title = right_cn_paren_match.group(2)
        is_standard = False
        category = "right_bracket"
    elif right_paren_match:
        serial = right_paren_match.group(1)
        title = right_paren_match.group(2)
        is_standard = False
        category = "right_bracket"
    elif chinese_num_match:
        serial = chinese_num_match.group(1)
        title = chinese_num_match.group(2)
        is_standard = False
        category = "chinese_num"
    else:
        # 没有匹配到序号格式
        serial = ""
        title = content
        is_standard = False
        category = "other"
    
    return serial, title, is_standard, category

def _get_level(category: str, last_level: int, non_standard_map: Dict[str, int]) -> int:
    """根据类别确定层级。
    
    如果类别不在 non_standard_map 中，分配层级为上一层级 + 1。
    如果在 map 中，分配为 map 中的层级，并清空 map 中更高层级的标记。
    """
    if category not in non_standard_map:
        level = last_level + 1
        non_standard_map[category] = level
    else:
        level = non_standard_map[category]
        # 清空更高层级的标记
        to_remove = [k for k, v in non_standard_map.items() if v > level]
        for k in to_remove:
            del non_standard_map[k]
    return level

def _step_generate_tree_nodes(selected_path: str, output_dir: str) -> Optional[str]:
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
    last_level = 0
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
            serial, title, is_standard, category = _extract_serial_and_title(line)
            
            # 确定层级
            if is_standard:
                level = serial.count('.') + 1
                non_standard_map.clear()
            else:
                level = _get_level(category, last_level, non_standard_map)
            
            # 创建新块
            block_count += 1
            current_block = {
                "编号": block_count,
                "序号": serial,
                "题目": title,
                "层级": str(level),
                "正文": "",
                "正文字数": 0,
                "不可修改": 0
            }
            last_level = level
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
        
        # 查找兄弟节点（同层的后一个节点）
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
    
    # 保存为json文件，生成在与 full.md 相同的文件夹中
    output_dir = os.path.dirname(selected_path)
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


def _step_output_directory(tree_json_path: str) -> Optional[str]:
    """读取 treenode.json 并生成 treedirectory.txt。

    输出格式为：
        编号 序号 题目
    """
    logger = logging.getLogger(__name__)

    try:
        with open(tree_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.error("读取treenode.json失败 %s，错误：%s", tree_json_path, e)
        return None

    nodes = data.get("nodes", [])
    if not isinstance(nodes, list):
        logger.error("treenode.json中的nodes格式不正确: %s", type(nodes).__name__)
        return None

    output_dir = os.path.dirname(tree_json_path)
    output_file = os.path.join(output_dir, "treedirectory.txt")

    try:
        with open(output_file, "w", encoding="utf-8") as f:
            for node in nodes:
                line = f"{node.get('编号', '')} {node.get('序号', '')} {node.get('题目', '')}\n"
                f.write(line)
        logger.info("成功生成目录文件 %s", output_file)
        return output_file
    except Exception as e:
        logger.error("保存目录文件失败 %s，错误：%s", output_file, e)
        return None


def _step_annotate_directory_with_ai(tree_directory_path: str) -> Optional[str]:
    """调用大模型分析 treedirectory.txt 并生成 treedirectorynew.txt。"""
    logger = logging.getLogger(__name__)

    if not os.path.isfile(tree_directory_path):
        logger.error("目录文件不存在，无法生成 treedirectorynew.txt：%s", tree_directory_path)
        return None

    try:
        with open(tree_directory_path, "r", encoding="utf-8") as f:
            directory_text = f.read()
    except Exception as e:
        logger.error("读取目录文件失败 %s，错误：%s", tree_directory_path, e)
        return None

    prompt = (
        "我将提供一个项目任务书的标题清单（按行排列）。请你逐行分析每个标题，并按照以下规则在每行末尾添加标记：\n"
        "标记为 1：该标题属于项目任务书中的通用固定结构，无论项目主题如何变化，这些标题应当保留（例如：“研究目标”、“研究内容”、“技术指标”等）。\n"
        "标记为 0：该标题在仿写其他任务书时需要被替换或重写（例如：“HZY行业特色保障措施”、“HZY专业大模型应用”等）。\n"
        # 这个继承规则可以思考一下有没有必要性
        "继承规则：若某一级标题标记为 0，则其所有下级标题必须同样标记为 0。\n"
        "请逐行输出分析结果，保持原有顺序和层级格式，仅在行末添加空格后加上 1 或 0，不要增加其他任何内容、符号、介绍。"
        "\n"
        "示例输出格式如下：\n"
        "1 1.1 研究目标 1\n"
        "0 1.2 HZY行业方案 0\n"
        "\n"
        "输入内容如下：\n"
        + directory_text
    )

    try:
        ai_result = ai_chat_with_progress(prompt, log_to_console=False)
    except Exception as e:
        logger.error("调用AI接口失败，无法生成 treedirectorynew.txt：%s", e)
        return None

    output_dir = os.path.dirname(tree_directory_path)
    output_file = os.path.join(output_dir, "treedirectorynew.txt")
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(ai_result)
        logger.info("成功生成AI标注目录文件 %s", output_file)
        return output_file
    except Exception as e:
        logger.error("保存 treedirectorynew.txt 失败 %s，错误：%s", output_file, e)
        return None


def _step_apply_nonmodifiable_flags(tree_json_path: str, annotated_directory_path: str) -> Optional[str]:
    """将 treedirectorynew.txt 中的最后标识写回 treenode.json 的不可修改字段。"""
    logger = logging.getLogger(__name__)

    if not os.path.isfile(tree_json_path):
        logger.error("treenode.json 文件不存在，无法更新不可修改标识：%s", tree_json_path)
        return None
    if not os.path.isfile(annotated_directory_path):
        logger.error("treedirectorynew.txt 文件不存在，无法更新不可修改标识：%s", annotated_directory_path)
        return None

    try:
        with open(tree_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.error("读取 treenode.json 失败 %s，错误：%s", tree_json_path, e)
        return None

    nodes = data.get("nodes", [])
    if not isinstance(nodes, list):
        logger.error("treenode.json 中的 nodes 不是列表: %s", type(nodes).__name__)
        return None

    try:
        with open(annotated_directory_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        logger.error("读取 treedirectorynew.txt 失败 %s，错误：%s", annotated_directory_path, e)
        return None

    id_to_flag = {}
    for line in lines:
        text = line.strip()
        if not text:
            continue
        parts = text.split()
        if len(parts) < 2:
            continue
        try:
            node_id = int(parts[0])
            flag = int(parts[-1])
            id_to_flag[node_id] = 1 if flag else 0
        except ValueError:
            continue

    if not id_to_flag:
        logger.warning("未从 treedirectorynew.txt 中解析到任何编号标识")

    updated_count = 0
    for node in nodes:
        node_id = node.get("编号")
        try:
            node_key = int(node_id)
        except (TypeError, ValueError):
            continue
        if node_key in id_to_flag:
            node["不可修改"] = id_to_flag[node_key]
            updated_count += 1

    if updated_count == 0:
        logger.warning("未在 treenode.json 中匹配到任何编号以更新不可修改标识")

    try:
        with open(tree_json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info("成功将 %d 个节点的不可修改标识写入 %s", updated_count, tree_json_path)
        return tree_json_path
    except Exception as e:
        logger.error("保存 treenode.json 失败 %s，错误：%s", tree_json_path, e)
        return None


def _step_visualize_tree(tree_json_path: str) -> Optional[str]:
    """从 treenode.json 生成简单字符树结构并保存到 treevisualization.txt。"""
    logger = logging.getLogger(__name__)

    if not os.path.isfile(tree_json_path):
        logger.error("treenode.json 文件不存在，无法生成 treevisualization.txt：%s", tree_json_path)
        return None

    try:
        with open(tree_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.error("读取 treenode.json 失败 %s，错误：%s", tree_json_path, e)
        return None

    nodes = data.get("nodes", [])
    if not isinstance(nodes, list):
        logger.error("treenode.json 中的 nodes 不是列表: %s", type(nodes).__name__)
        return None

    def to_int_level(value):
        try:
            return int(str(value).strip())
        except (TypeError, ValueError):
            return 1

    def has_later_sibling(start_index: int, level: int) -> bool:
        for later in nodes[start_index + 1 :]:
            later_level = to_int_level(later.get("层级"))
            if later_level < level:
                return False
            if later_level == level:
                return True
        return False

    visualization_lines = []
    for index, node in enumerate(nodes):
        level = to_int_level(node.get("层级"))
        serial = str(node.get("序号", "")).strip()
        title = str(node.get("题目", "")).strip()
        flag = str(node.get("不可修改", "")).strip()
        label = f"[{serial} {title} {flag}]".replace("  ", " ").strip()

        if level <= 1:
            visualization_lines.append(label)
            continue

        connector = "└── " if not has_later_sibling(index, level) else "├── "

        prefix_parts = []
        for ancestor_level in range(1, level):
            if has_later_sibling(index, ancestor_level):
                prefix_parts.append("│   ")
            else:
                prefix_parts.append("    ")

        prefix = "".join(prefix_parts)
        visualization_lines.append(f"{prefix}{connector}{label}")

    output_dir = os.path.dirname(tree_json_path)
    output_file = os.path.join(output_dir, "treevisualization.txt")

    try:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("\n".join(visualization_lines))
        logger.info("成功生成树结构可视化文件 %s", output_file)
        return output_file
    except Exception as e:
        logger.error("保存 treevisualization.txt 失败 %s，错误：%s", output_file, e)
        return None


def collecttree(output_dir: str, work_dir: str):
    # 日志设置
    log_file = get_log_file_path(work_dir)
    setup_logger(log_file, console=True)
    logger = logging.getLogger(__name__)

    logger.info("管线开始，output_dir=%s work_dir=%s", output_dir, work_dir)

    # 执行各个处理步骤
    # 从 output_dir 中查找第一个 full.md，并返回其路径
    selected_path = _step_file_collection(output_dir, work_dir)
    if selected_path:
        # 解析 selected_path，生成 treenode.json ：生成初步树节点
        json_path = _step_generate_tree_nodes(selected_path,  output_dir)
        if json_path:
            # 从 treenode.json 生成 treedirectory.txt ：提取树标题
            directory_path = _step_output_directory(json_path)
            if directory_path:
                # 调用AI标注 treedirectory.txt，生成 treedirectorynew.txt ：调用大模型分析树不可修改字段
                annotated_path = _step_annotate_directory_with_ai(directory_path)
                if annotated_path:
                    # 将 treedirectorynew.txt 的标记写回 treenode.json 中的不可修改字段 ：字段写回
                    _step_apply_nonmodifiable_flags(json_path, annotated_path)
            # 生成树结构可视化文件
            _step_visualize_tree(json_path)
    else:
        logger.warning("未找到可处理的 full.md 文件")


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