import json
import logging
import os
import re 
from typing import Optional, Dict, Tuple
import threading
from search import basequery

# basequery 在 test() 内部按包路径导入，以兼容不同的运行方式

def test():
    """测试 basequery 接口：从标准输入读取一个主题，调用 basequery(top_k=3, topic)，并把结果打印到控制台。"""
    # 统一按文件路径动态加载同目录下的 search.py，避免包导入差异
    # try:
    #     import importlib.util
    #     search_path = os.path.join(os.path.dirname(__file__), 'search.py')
    #     spec = importlib.util.spec_from_file_location('search_module', search_path)
    #     search_module = importlib.util.module_from_spec(spec)
    #     spec.loader.exec_module(search_module)
    #     basequery = getattr(search_module, 'basequery')
    # except Exception as e:
    #     logging.getLogger(__name__).exception('无法通过文件路径导入 basequery: %s', e)
    #     return

    topic = input('请输入查询主题: ').strip()
    if not topic:
        print('未输入主题，退出')
        return

    try:
        results = basequery(3, topic, False)
    except Exception as e:
        logging.getLogger(__name__).exception('调用 basequery 失败: %s', e)
        return

    try:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    except Exception:
        print(results)


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
    # 运行 test() 以交互测试 basequery
    try:
        test()
    except Exception:
        logging.getLogger(__name__).exception('运行 test() 失败')