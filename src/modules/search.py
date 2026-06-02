import json
import logging
import os
import re 
from typing import Optional, Dict, Tuple
import threading
import tkinter as tk
from tkinter import scrolledtext
import configparser
import sys

# 尝试在多种运行上下文中导入依赖（支持作为脚本运行、包导入或通过文件加载）
try:
    # 优先相对导入（当作为包导入时）
    from .ai_api_client import ai_chat_with_progress
    from .logger import get_log_file_path, setup_logger
except Exception:
    try:
        # 作为脚本直接运行或在 sys.path 中时的绝对导入
        from ai_api_client import ai_chat_with_progress
        from logger import get_log_file_path, setup_logger
    except Exception:
        # 尝试包名导入（例如 python -m src.modules.test 时）
        try:
            from src.modules.ai_api_client import ai_chat_with_progress
            from src.modules.logger import get_log_file_path, setup_logger
        except Exception:
            raise


def search(input_dir: str = None, output_dir: str = None, work_dir: str = None, interactive: bool = True, full_result: bool = True):
    # 日志设置
    # 默认路径（基于仓库根目录）
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    if input_dir is None:
        input_dir = os.path.join(repo_root, 'input')
    if output_dir is None:
        output_dir = os.path.join(repo_root, 'output')
    if work_dir is None:
        work_dir = repo_root

    log_file = get_log_file_path(work_dir)
    setup_logger(log_file, console=True)
    logger = logging.getLogger(__name__)

    logger.info("管线开始，output_dir=%s work_dir=%s", output_dir, work_dir)

    # ---- 第1步：文档加载器 ----
    def load_documents(input_dir: str):
        """遍历 input_dir/knowledgebase 下的 .md 文件，按标题 (#) 切分成块。
        返回列表：[{"content": str, "source_file": str}, ...]
        """
        kb_dir = os.path.join(input_dir, "knowledgebase")
        docs = []
        if not os.path.isdir(kb_dir):
            logger.warning("知识库目录不存在: %s", kb_dir)
            return docs

        for root, _, files in os.walk(kb_dir):
            for fname in files:
                if not fname.lower().endswith('.md'):
                    continue
                path = os.path.join(root, fname)
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        text = f.read()
                except Exception:
                    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                        text = f.read()

                # 按标题切分，包含标题在块内
                lines = text.splitlines()
                current = []
                current_header = None
                for line in lines:
                    if line.strip().startswith('#'):
                        # 新章节
                        if current:
                            chunk = '\n'.join(current).strip()
                            if chunk:
                                docs.append({"content": chunk, "source_file": path})
                        current = [line]
                        current_header = line
                    else:
                        current.append(line)

                if current:
                    chunk = '\n'.join(current).strip()
                    if chunk:
                        docs.append({"content": chunk, "source_file": path})

        logger.info("已加载文档块：%d 条", len(docs))
        return docs

    # ---- 分词 / tokenize ----
    try:
        import jieba

        def tokenize(text: str):
            return [t for t in jieba.lcut(text) if t.strip()]
    except Exception:
        logger.info("未找到 jieba，使用简单分词（字/词边界）")

        def tokenize(text: str):
            return re.findall(r"\w+|[\u4e00-\u9fff]", text)

    # ---- 第2步：BM25 检索器（纯 Python 实现） ----
    class BM25:
        def __init__(self, docs_tokens, k1=1.5, b=0.75):
            self.k1 = k1
            self.b = b
            self.N = len(docs_tokens)
            self.doc_len = [len(d) for d in docs_tokens]
            self.avgdl = sum(self.doc_len) / self.N if self.N > 0 else 0.0

            # 计算词频和文档频率
            self.f = []  # 每文档的词频字典
            df = {}
            for tokens in docs_tokens:
                freqs = {}
                for word in tokens:
                    freqs[word] = freqs.get(word, 0) + 1
                self.f.append(freqs)
                for word in freqs.keys():
                    df[word] = df.get(word, 0) + 1

            # idf
            self.idf = {}
            for word, freq in df.items():
                # 标准 idf 平滑
                self.idf[word] = max(0.0, math.log((self.N - freq + 0.5) / (freq + 0.5) + 1))

        def score(self, query_tokens, index):
            score = 0.0
            freqs = self.f[index]
            dl = self.doc_len[index]
            for q in query_tokens:
                if q not in freqs:
                    continue
                idf = self.idf.get(q, 0.0)
                f = freqs[q]
                denom = f + self.k1 * (1 - self.b + self.b * dl / self.avgdl)
                score += idf * f * (self.k1 + 1) / denom
            return score

        def search(self, query, top_k=5):
            q_tokens = tokenize(query)
            scores = []
            for i in range(self.N):
                s = self.score(q_tokens, i)
                scores.append((i, s))
            scores.sort(key=lambda x: x[1], reverse=True)
            return scores[:top_k]

    # ---- 第3步：可选 TF-IDF 向量检索（纯 numpy 实现） ----
    try:
        import numpy as np

        class TFIDFRetriever:
            def __init__(self, docs_tokens):
                # 建立词表
                vocab = {}
                for tokens in docs_tokens:
                    for t in tokens:
                        if t not in vocab:
                            vocab[t] = len(vocab)
                self.vocab = vocab
                self.N = len(docs_tokens)
                V = len(vocab)
                # 构建 TF 矩阵
                tf = np.zeros((self.N, V), dtype=float)
                df = np.zeros(V, dtype=float)
                for i, tokens in enumerate(docs_tokens):
                    for t in tokens:
                        idx = vocab[t]
                        tf[i, idx] += 1.0
                    # 文档频率
                    present = set(tokens)
                    for t in present:
                        df[vocab[t]] += 1.0

                # TF 归一化
                row_sums = tf.sum(axis=1, keepdims=True)
                row_sums[row_sums == 0] = 1.0
                self.tf = tf / row_sums

                # idf
                self.idf = np.log((self.N + 1.0) / (df + 1.0)) + 1.0

                # 文档向量
                self.doc_vecs = self.tf * self.idf
                # L2 归一化
                norms = np.linalg.norm(self.doc_vecs, axis=1, keepdims=True)
                norms[norms == 0] = 1.0
                self.doc_vecs = self.doc_vecs / norms

            def query_vector(self, query_tokens):
                vec = np.zeros(len(self.vocab), dtype=float)
                for t in query_tokens:
                    idx = self.vocab.get(t)
                    if idx is not None:
                        vec[idx] += 1.0
                if vec.sum() == 0:
                    return vec
                # TF
                vec = vec / vec.sum()
                vec = vec * self.idf
                norm = np.linalg.norm(vec)
                if norm == 0:
                    return vec
                return vec / norm

            def search(self, query, top_k=5):
                q_tokens = tokenize(query)
                qv = self.query_vector(q_tokens)
                if qv.sum() == 0:
                    return []
                sims = np.dot(self.doc_vecs, qv)
                idxs = np.argsort(-sims)[:top_k]
                return list(zip(idxs.tolist(), sims[idxs].tolist()))

    except Exception:
        np = None
        TFIDFRetriever = None

    # ---- 构建索引 ----
    docs = load_documents(input_dir)
    texts = [d['content'] for d in docs]
    docs_tokens = [tokenize(t) for t in texts]

    # BM25 索引
    import math
    bm25 = BM25(docs_tokens)

    # TF-IDF 索引（如果可用）
    tfidf = None
    if 'TFIDFRetriever' in locals() and TFIDFRetriever is not None:
        try:
            tfidf = TFIDFRetriever(docs_tokens)
        except Exception:
            tfidf = None

    logger.info("索引构建完成：BM25 文档数=%d TFIDF=%s", len(docs_tokens), 'ok' if tfidf else 'no')

    # ---- 混合检索接口 ----
    def hybrid_search(query: str, top_k=5, alpha=0.6, full_result: bool = True):
        """混合 BM25 + TF-IDF 的检索，alpha 权重给 BM25。
        full_result=True 返回 [{content, source_file, score}], False 只返回 content 字符串列表。
        """
        bm25_res = bm25.search(query, top_k=top_k*3)
        bm25_scores = {i: s for i, s in bm25_res}

        tf_res = []
        if tfidf is not None:
            tf_res = tfidf.search(query, top_k=top_k*3)
        tf_scores = {i: s for i, s in tf_res}

        # 归一化 BM25 分数
        bm_vals = list(bm25_scores.values()) if bm25_scores else [0.0]
        bm_min, bm_max = min(bm_vals), max(bm_vals)
        def norm_bm(v):
            if bm_max - bm_min <= 1e-9:
                return 0.0 if v == 0 else 1.0
            return (v - bm_min) / (bm_max - bm_min)

        combined = {}
        for idx, v in bm25_scores.items():
            combined[idx] = combined.get(idx, 0.0) + alpha * norm_bm(v)
        for idx, v in tf_scores.items():
            combined[idx] = combined.get(idx, 0.0) + (1 - alpha) * v

        ranked = sorted(combined.items(), key=lambda x: x[1], reverse=True)[:top_k]
        if full_result:
            out = []
            for idx, score in ranked:
                out.append({
                    "content": docs[idx]['content'],
                    "source_file": docs[idx]['source_file'],
                    "score": float(score)
                })
            return out
        else:
            return [docs[idx]['content'] for idx, _ in ranked]

    # 如果需要交互则进入查询循环，否则仅返回检索接口
    if interactive:
        try:
            if os.environ.get('SKIP_INTERACTIVE') or not (hasattr(sys.stdin, 'isatty') and sys.stdin.isatty()):
                print("索引已准备好，共 %d 个文档块。非交互环境，跳过查询。" % len(docs))
            else:
                print("索引已准备好，共 %d 个文档块。输入查询，空输入退出。" % len(docs))
                while True:
                    q = input('query> ').strip()
                    if not q:
                        break
                    hits = hybrid_search(q, top_k=5, full_result=True)
                    for i, h in enumerate(hits, 1):
                        print(f"[{i}] score={h['score']:.4f} file={h['source_file']}")
                        snippet = h['content'][:400].replace('\n', ' ')
                        print('    ', snippet)
        except Exception:
            logger.info('交互查询退出或不支持交互环境')

    # 返回检索接口以便外部调用
    return {
        'hybrid_search': hybrid_search,
        'bm25': bm25,
        'tfidf': tfidf,
        'docs': docs,
        'tokenize': tokenize,
    }


def basequery(top_k: int, topic: str, full_result: bool = True):
        """简单接口：内部构建索引并返回混合检索结果。可直接被同文件夹其他模块调用。

        参数：
            - top_k: 返回结果数量
            - topic: 查询文本
            - full_result: True 返回完整结构，False 只返回 content
        返回：检索结果列表（与 hybrid_search 输出格式相同，或 content 列表）
        """
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        input_dir = os.path.join(repo_root, 'input')
        output_dir = os.path.join(repo_root, 'output')
        work_dir = repo_root

        # 构建索引（非交互）
        iface = search(input_dir=input_dir, output_dir=output_dir, work_dir=work_dir, interactive=False, full_result=full_result)
        hybrid = iface.get('hybrid_search')
        if hybrid is None:
                return []
        return hybrid(topic, top_k=top_k, full_result=full_result)


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

    # 运行默认的交互式搜索
    search(input_dir=input_dir, output_dir=output_dir, work_dir=work_dir, interactive=True, full_result = False)

