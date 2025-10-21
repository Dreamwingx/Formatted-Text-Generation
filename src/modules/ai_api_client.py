import json
import logging
import time
from tqdm import tqdm
from openai import OpenAI
from pathlib import Path


def get_config(task_type, model_name):
    """
    按照任务类型获取配置
    task_type: "summarization"、 "merging"、"translation"、 默认
    """
    if model_name == "":
        logging.warning(f"未传入正确model_name参数，请检查ai_api_config.json是否配置得当")
        return
    if task_type == "summarization":
        return {
            "system_prompt": (
                "你是一个专业的文本摘要助手。"
                "请阅读用户提供的内容，提取核心信息，生成简洁明了的摘要。"
                "摘要应覆盖关键信息，避免添加无关内容，且语言要通顺自然。"
            ),
            "model": model_name,
            "temperature": 0.3,
            "max_tokens": 1024,
            "stream": False
        }
    elif task_type == "merging":
        return {
            "system_prompt": (
                "你是一个专业的文本整合助手。"
                "请将用户提供的多段文本内容进行合并，"
                "尽量保留原文内容，保持原文表述风格，但需要去除重复信息，"
                "合并后的内容连贯、逻辑清晰、表达自然。"
            ),
            "model": model_name,
            "temperature": 0.5,
            "max_tokens": 8192,
            "stream": False
        }
    elif task_type == "translation":
        return {
            "system_prompt": (
                "你是一个专业的文档翻译专家。"
                "请将用户提供的文档内容准确翻译成目标语言，"
                "保持原文的专业术语和核心含义，同时确保翻译结果符合目标语言的表达习惯，"
                "译文应流畅自然、语义准确、风格贴切。"
            ),
            "model": model_name,
            "temperature": 0.3,
            "max_tokens": 8192,
            "stream": False
        }
    else:
        # 默认配置
        return {
            "system_prompt": "你是一个智能文档助手。",
            "model": model_name,
            "temperature": 0.7,
            "max_tokens": 4096,
            "stream": False
        }


def load_api_config():
    # 获取当前文件的上一级目录中的 ai_api_config.json
    config_path = Path(__file__).parent.parent / "ai_api_config.json"
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    return config["api_key"], config["base_url"], config["model_name"]


def ai_chat(user_input, task_type="default"):
    """"
    调用大语言模型API进行对话交互，根据任务类型使用不同配置

    Args:
        user_input (str): 用户输入的提示词或问题
        task_type (str): 任务类型，可选值包括 "summarization"（摘要）、"merging"（合并）

    Returns:
        str: 大语言模型返回的响应内容
    """

    # 1. 加载API密钥和基础URL（从配置文件或环境变量中读取）
    api_key, base_url, model_name = load_api_config()

    # 2. 根据任务类型获取对应的配置（如系统提示词、模型参数等）
    config = get_config(task_type, model_name)

    # 3. 初始化OpenAI客户端（兼容开源模型API，如DeepSeek、Qwen等）
    client = OpenAI(api_key=api_key, base_url=base_url)

    # 4. 构建对话消息列表
    messages = [
        {"role": "system", "content": config.get("system_prompt", "你是一个智能文档助手。")},
        {"role": "user", "content": user_input}
    ]

    # 5. 调用大模型API生成响应
    response = client.chat.completions.create(
        model=config.get("model", "deepseek-chat"),
        messages=messages,
        temperature=config.get("temperature", 0.7),
        max_tokens=config.get("max_tokens", 4096),
        stream=config.get("stream", False)
    )
    # 6.保存日志
    logging.info(user_input)
    logging.info(response.choices[0].message.content)

    # 7. 提取并返回模型的响应内容
    return response.choices[0].message.content


def ai_chat_with_progress(user_input, task_type="default"):
    """"
    带进度条的ai处理函数
    """
    pbar = tqdm(total=5, desc="AI处理进度", unit="步骤")

    try:
        # 步骤1: 加载配置
        pbar.set_description("加载模型配置")
        api_key, base_url, model_name = load_api_config()
        config = get_config(task_type, model_name)
        pbar.update(1)
        time.sleep(0.1)

        # 步骤2: 初始化OpenAI
        pbar.set_description("初始化OpenAI")
        client = OpenAI(api_key=api_key, base_url=base_url)
        pbar.update(1)
        time.sleep(0.1)

        # 步骤3: 构建消息
        pbar.set_description("构建对话消息")
        messages = [
            {"role": "system", "content": config.get("system_prompt", "你是一个智能文档助手。")},
            {"role": "user", "content": user_input}
        ]
        pbar.update(1)
        time.sleep(0.1)

        # 步骤4: 调用API
        pbar.set_description("调用AI模型")
        response = client.chat.completions.create(
            model=config.get("model", "deepseek-chat"),
            messages=messages,
            temperature=config.get("temperature", 0.7),
            max_tokens=config.get("max_tokens", 4096),
            stream=config.get("stream", False)
        )
        pbar.update(1)
        time.sleep(0.1)

        # 步骤5: 完成
        pbar.set_description("单次问答处理完成")
        pbar.update(1)

        # 保存日志
        logging.info(user_input)
        logging.info(response.choices[0].message.content)

        result = response.choices[0].message.content
        pbar.close()
        print("\r" + " " * 100 + "\r", end="", flush=True)

        return result


    finally:
        pbar.close()