"""基于 LangChain + DashScope 的中英文／多语言向量模型适配层。

底层存储只依赖一个很小的接口：``encode(texts)``、``encode_queries(queries)``
以及向量维度 ``dim``。这个适配层把 LangChain 的 ``DashScopeEmbeddings`` 转成
该接口，供文档入库和 DenseRetriever 查询编码使用。
"""
from __future__ import annotations

import os
from collections.abc import Iterable

from .config import read_api_key

DEFAULT_MODEL = "qwen3.7-text-embedding"
DEFAULT_DIM = 1024


class Embedder:
    """使用 DashScope 中文/多语言 Embedding 的 LangChain 适配器。"""

    backend = "dashscope"
    # 不把相关性阈值设得过高，避免尚未完成业务数据校准时误删候选。
    sim_floor = 0.0

    def __init__(
        self,
        model_name: str | None = None,
        dim: int | None = None,
        batch_size: int = 20,
    ):
        from dotenv import load_dotenv
        from langchain_community.embeddings import DashScopeEmbeddings

        load_dotenv()
        self.model_name = model_name or os.environ.get(
            "REDEVOPS_RAG_EMBED_MODEL", DEFAULT_MODEL
        )
        self.dim = int(
            dim
            or os.environ.get("SERVICELOOP_RAG_EMBED_DIM")
            or os.environ.get("REDEVOPS_RAG_EMBED_DIM", DEFAULT_DIM)
        )
        self.batch_size = max(int(batch_size), 1)

        api_key = read_api_key("DASHSCOPE_API_KEY")
        if not api_key:
            raise ValueError("尚未配置 DASHSCOPE_API_KEY。")
        options: dict = {
            "model": self.model_name,
            "dashscope_api_key": api_key,
        }
        self.model = DashScopeEmbeddings(**options)

    def _validate(self, vectors: list[list[float]]) -> list[list[float]]:
        normalized = [[float(value) for value in vector] for vector in vectors]
        for vector in normalized:
            if len(vector) != self.dim:
                raise ValueError(
                    f"Embedding 维度不匹配：模型返回 {len(vector)} 维，"
                    f"配置为 {self.dim} 维。请设置 REDEVOPS_RAG_EMBED_DIM，"
                    "并重新构建当前知识索引。"
                )
        return normalized

    def encode(self, texts: Iterable[str]) -> list[list[float]]:
        """批量编码文档；LangChain 内部会以 document 类型请求 DashScope。"""
        items = [str(text) for text in texts]
        vectors: list[list[float]] = []
        for start in range(0, len(items), self.batch_size):
            vectors.extend(self.model.embed_documents(items[start : start + self.batch_size]))
        return self._validate(vectors)

    def encode_queries(self, queries: Iterable[str]) -> list[list[float]]:
        """编码查询；保留 DashScope 对 query/document 的非对称优化。"""
        vectors = [self.model.embed_query(str(query)) for query in queries]
        return self._validate(vectors)
