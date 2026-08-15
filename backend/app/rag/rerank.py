"""必选交叉编码器精排阶段，默认使用 ``BAAI/bge-reranker-base``。"""
from __future__ import annotations

import os
from typing import Any

DEFAULT_RERANK_MODEL = "BAAI/bge-reranker-base"


class Reranker:
    def __init__(self, model_name: str | None = None, use_fp16: bool = False):
        from FlagEmbedding import FlagReranker  # 延迟导入，只有启用精排时才加载 Torch

        self.model_name = (
            model_name
            or os.environ.get("SERVICELOOP_RAG_RERANK_MODEL")
            or os.environ.get("REDEVOPS_RAG_RERANK_MODEL", DEFAULT_RERANK_MODEL)
        )
        self.model = FlagReranker(self.model_name, use_fp16=use_fp16)

    def rerank(self, query: str, candidates: list[dict]) -> list[dict]:
        if not candidates:
            return candidates
        pairs: list[tuple[str, str]] = [(query, str(c.get("text") or "")) for c in candidates]
        raw_scores: Any = self.model.compute_score(pairs, normalize=True)
        if raw_scores is None:
            return candidates
        if hasattr(raw_scores, "tolist"):
            raw_scores = raw_scores.tolist()
        scores = raw_scores if isinstance(raw_scores, list) else [raw_scores]
        for c, s in zip(candidates, scores):
            c["rerank_score"] = float(s)
        candidates.sort(key=lambda r: r.get("rerank_score", 0.0), reverse=True)
        return candidates
