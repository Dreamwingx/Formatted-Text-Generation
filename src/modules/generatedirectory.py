import json
import logging
import os
from typing import Optional, Dict

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


def _rewrite_treedirectory(selected_path: str) -> Optional[str]:
    """根据控制台输入的主题，生成 rewritedirectory.txt 文件。

    - 用户在控制台中输入要替换后的主题。
    - 将该主题插入提示词中的“请将主题替换为：”位置。
    - 直接调用 AI 接口，生成的结果写入 rewritedirectory.txt。
    - 不显示任何 GUI 窗口。

    返回值：写入的 rewritedirectory.txt 的路径；如果失败则返回 None。
    """

    logger = logging.getLogger(__name__)

    dirpath = os.path.dirname(selected_path)
    src_file = os.path.join(dirpath, "treedirectorynew.txt")

    if not os.path.isfile(src_file):
        logger.warning("未找到 treedirectorynew.txt 在 %s", dirpath)
        return None

    try:
        with open(src_file, "r", encoding="utf-8") as f:
            directory_text = f.read()
    except Exception as e:
        logger.error("读取文件失败 %s: %s", src_file, e)
        return None

    replacement_theme = input("请输入替换后的主题：").strip()
    if not replacement_theme:
        logger.warning("未输入替换主题，使用默认主题。")
        replacement_theme = "军事工艺模型总体框架设计与发展规划研究"

    prompt = (
        "我将给你一段文字，这是一篇任务书的目录部分。\n"
        "当前主题为：“大模型总体框架设计与发展规划研究”。\n"
        f"请将主题替换为：“{replacement_theme}”。\n"
        "\n"
        "标题后面已经附有标记：\n"
        "- 后缀为 [0]：表示该标题允许根据新主题进行替换或调整表述。\n"
        "- 后缀为 [1]：表示该标题必须原样保留，不得修改。\n"
        "\n"
        "请你逐行处理目录中的每个标题，规则如下：\n"
        "1. 对于后缀为 [0] 的标题：根据新主题进行适当替换或调整，使标题与新主题逻辑一致。\n"
        "2. 对于后缀为 [1] 的标题：必须原样保留，一个字也不改。\n"
        "3. 保持原有的层级结构、缩进或编号格式不变。\n"
        "4. 只输出修改后的目录文本，不要添加任何解释、说明、额外符号或注释。\n"
        "\n"
        "现在，输入你要处理的任务书目录：\n"
        + directory_text
    )

    try:
        ai_result = ai_chat_with_progress(prompt, log_to_console=False)
        if isinstance(ai_result, (dict, list)):
            text = json.dumps(ai_result, ensure_ascii=False, indent=2)
        else:
            text = str(ai_result)
    except Exception as e:
        logger.error("调用AI接口失败：%s", e)
        return None

    out_file = os.path.join(dirpath, "rewritedirectory.txt")
    try:
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(text)
        logger.info("已生成 %s", out_file)
    except Exception as e:
        logger.error("写入文件失败 %s: %s", out_file, e)
        return None

    return out_file


def rewrite_treenode(selected_path: str) -> Optional[str]:
    """复制 treenode.json 为 treenodenew.json，然后根据 rewritedirectory.txt 更新题目和不可修改位。

    rewritedirectory.txt 每行格式：编号 序号 题目 不可修改位
    解析时采用：第一列为编号，第二列为序号，最后一列为不可修改位，中间所有内容拼接为题目。
    返回值：写入的 treenodenew.json 路径，或 None（出错）。
    """

    logger = logging.getLogger(__name__)

    dirpath = os.path.dirname(selected_path)
    src = os.path.join(dirpath, "treenode.json")
    dst = os.path.join(dirpath, "rewritedirectorytreenode.json")

    if not os.path.isfile(src):
        logger.warning("未找到 treenode.json 在 %s", dirpath)
        return None

    try:
        with open(src, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.error("读取 treenode.json 失败 %s: %s", src, e)
        return None

    # 先写一份副本
    try:
        with open(dst, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("写入 %s 失败: %s", dst, e)
        return None

    rewrite_file = os.path.join(dirpath, "rewritedirectory.txt")
    if not os.path.isfile(rewrite_file):
        logger.warning("未找到 rewritedirectory.txt 在 %s，已生成副本但不做替换", dirpath)
        return dst

    mapping: Dict[object, Dict[str, object]] = {}
    try:
        with open(rewrite_file, "r", encoding="utf-8") as f:
            for lineno, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                parts = line.split()
                if len(parts) < 4:
                    logger.warning("rewritedirectory.txt 第 %d 行格式不符合: %s", lineno, line)
                    continue
                id_str = parts[0]
                # 最后一列为不可修改位，中间为题目（可能含空格）
                immutable_str = parts[-1]
                title = " ".join(parts[2:-1])
                try:
                    id_key = int(id_str)
                except Exception:
                    id_key = id_str
                try:
                    immutable_val = int(immutable_str)
                except Exception:
                    immutable_val = immutable_str
                mapping[id_key] = {"题目": title, "不可修改": immutable_val}
    except Exception as e:
        logger.error("读取 rewritedirectory.txt 失败 %s: %s", rewrite_file, e)
        return dst

    nodes = data.get("nodes") if isinstance(data, dict) else None
    if not isinstance(nodes, list):
        logger.warning("treenode.json 格式异常，缺少 nodes 列表")
        return dst

    # 构建节点字典
    nodes_dict = {node['编号']: node for node in nodes if isinstance(node, dict) and '编号' in node}

    # 定义计算叶节点字数的函数
    # 叶节点字数 = 当前节点向下所有层次的叶节点总字数
    # 也就是说：父节点的叶节点字数 = 所有子节点的叶节点总字数之和
    def calculate_leaf_text_count(node_id, nodes_dict):
        node = nodes_dict[node_id]
        if node['子节点'] == 0:
            # 叶节点本身不统计为自身的“叶节点字数”
            return 0
        total = 0
        child_id = node['子节点']
        while child_id != 0:
            child = nodes_dict[child_id]
            # 子节点的叶节点总字数 = 子节点的叶节点字数 + 子节点自身的正文字数
            total += child['正文字数'] + calculate_leaf_text_count(child_id, nodes_dict)
            child_id = child['兄弟节点']
        return total

    # 为每个节点添加叶节点字数属性
    for node in nodes:
        if isinstance(node, dict) and '编号' in node:
            node['叶节点字数'] = calculate_leaf_text_count(node['编号'], nodes_dict)
            node['叶节点总字数'] = node['叶节点字数'] + node['正文字数']

    changed = False
    for node in nodes:
        if not isinstance(node, dict):
            continue
        key = node.get("编号")
        if key is None:
            continue
        try:
            lookup = int(key) if not isinstance(key, int) else key
        except Exception:
            lookup = key
        if lookup in mapping:
            new = mapping[lookup]
            node["题目"] = new["题目"]
            node["不可修改"] = new["不可修改"]
            changed = True

    # 总是写入更新后的文件
    try:
        with open(dst, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        if changed:
            logger.info("已更新 %s", dst)
        else:
            logger.info("没有匹配的编号，%s 保持原样", dst)
    except Exception as e:
        logger.error("写入更新后的 %s 失败: %s", dst, e)
        return None

    return dst


def generatedirectory(output_dir: str, work_dir: str):
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
        _rewrite_treedirectory(selected_path)
        # 在目录重写后，根据 rewritedirectory.txt 更新 treenode，生成 treenodenew.json
        try:
            rewrite_treenode(selected_path)
        except Exception:
            logger.exception("rewrite_treenode 执行失败")
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

    generatedirectory(output_dir, work_dir)