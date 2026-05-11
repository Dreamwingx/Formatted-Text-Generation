import json
import logging
import os
import re 
from typing import Optional, Dict, Tuple
import threading
import tkinter as tk
from tkinter import scrolledtext

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


def generatedirectory(output_dir: str, work_dir: str):

    # 执行各个处理步骤
    # 从 output_dir 中查找第一个 full.md，并返回其路径
    selected_path = _step_file_collection(output_dir, work_dir)
    if selected_path:
        function(selected_path)


def function(selected_path: str) -> None:
    """读取 selected_path 所在目录下的 rewritedirectorytreenode.json，
    按“序号、题目、生成内容”顺序提取所有节点中存在的“生成内容”并追加写入同目录下的 temp.txt。

    - 如果未找到 JSON 或解析失败，会记录日志并返回。
    - 仅当节点包含非空的生成内容时才输出该节点。
    """

    logger = logging.getLogger(__name__)
    if not selected_path:
        logger.error("selected_path 为空")
        return

    directory = os.path.dirname(selected_path)
    if not directory or not os.path.isdir(directory):
        logger.error("selected_path 所在目录无效: %r", selected_path)
        return

    json_path = os.path.join(directory, "rewritedirectorytreenode.json")
    temp_path = os.path.join(directory, "temp.txt")

    if not os.path.isfile(json_path):
        logger.warning("未找到文件: %s", json_path)
        return

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.exception("读取 JSON 失败: %s", e)
        return

    # 获取节点列表（常见结构：data['nodes'] 或 data 为 list）
    if isinstance(data, dict):
        nodes = None
        if "nodes" in data and isinstance(data["nodes"], list):
            nodes = data["nodes"]
        elif "treenode" in data and isinstance(data["treenode"], list):
            nodes = data["treenode"]
        else:
            # 退回：把顶层作为单个节点列表处理
            # 如果顶层包含多个字典值，也尝试收集。
            maybe = [v for v in data.values() if isinstance(v, dict) or isinstance(v, list)]
            if maybe and isinstance(maybe[0], list):
                nodes = maybe[0]
            else:
                nodes = [data]
    elif isinstance(data, list):
        nodes = data
    else:
        nodes = [data]

    def extract_field(obj: dict, candidates: list[str]):
        if not isinstance(obj, dict):
            return None
        # 直接匹配
        for k in candidates:
            if k in obj and obj[k] not in (None, "", []):
                return obj[k]
        # 模糊匹配键名（包含关键字）
        for k in obj:
            if not isinstance(k, str):
                continue
            for cand in candidates:
                if cand in k and obj[k] not in (None, "", []):
                    return obj[k]
        return None

    number_keys = ["序号", "编号", "id", "number", "序列"]
    title_keys = ["题目", "title", "name", "标题"]
    content_keys = ["生成内容", "生成的内容", "生成结果", "生成", "content", "generated", "生成文本"]

    results: list[str] = []

    def walk(node: dict):
        if not isinstance(node, dict):
            return
        num = extract_field(node, number_keys)
        title = extract_field(node, title_keys)
        content = extract_field(node, content_keys)

        if content:
            if not isinstance(content, str):
                try:
                    content_str = json.dumps(content, ensure_ascii=False)
                except Exception:
                    content_str = str(content)
            else:
                content_str = content.strip()

            num_str = str(num) if num is not None else ""
            title_str = str(title).strip() if title is not None else ""
            results.append(f"{num_str}\t{title_str}\t{content_str}")

        # 递归查找子节点，常见键名
        for child_key in ("children", "child", "子节点", "nodes", "childrenNodes", "items"):
            if child_key in node and isinstance(node[child_key], list):
                for ch in node[child_key]:
                    walk(ch)

        # 额外尝试：遍历值中的列表，若为 dict 则继续遍历
        for v in node.values():
            if isinstance(v, list):
                for it in v:
                    if isinstance(it, dict):
                        walk(it)

    for n in nodes:
        walk(n)

    if not results:
        logger.info("未找到包含生成内容的节点: %s", json_path)
        return

    try:
        with open(temp_path, "a", encoding="utf-8") as out:
            for line in results:
                out.write(line + "\n")
    except Exception as e:
        logger.exception("写入 temp.txt 失败: %s", e)



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