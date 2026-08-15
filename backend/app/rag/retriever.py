"""Dense + 预构建 BM25 + RRF + 必选 Cross-Encoder 精排。"""

from __future__ import annotations

from collections.abc import Callable

from .index_manager import IndexManager
from .rrf import rrf_fuse
from .types import EmbedderProtocol, RerankerProtocol


class HybridRetriever:
    def __init__(
        self,
        index_manager: IndexManager,
        embedder: EmbedderProtocol,
        reranker_factory: Callable[[], RerankerProtocol],
    ):
        self.index_manager = index_manager
        self.embedder = embedder
        self._reranker_factory = reranker_factory
        self._reranker: RerankerProtocol | None = None

    def _rerank(self, query: str, candidates: list[dict]) -> list[dict]:
        if self._reranker is None:
            self._reranker = self._reranker_factory()
        return self._reranker.rerank(query, candidates)

    def search(
        self,
        query: str,
        limit: int = 8,
        pool: int = 50,
        vector_threshold: float = 0.0,
    ) -> list[dict]:
        if not query or not query.strip() or not self.index_manager.chunk_count:
            return []
        query_vector = self.embedder.encode_queries([query])[0]
        dense_hits = self.index_manager.dense_search(
            query_vector, limit=pool, threshold=vector_threshold
        )
        bm25_hits = self.index_manager.bm25_search(query, limit=pool)
        candidates = rrf_fuse([dense_hits, bm25_hits])[:pool]
        if candidates:
            candidates = self._rerank(query, candidates)
        return candidates[: max(int(limit), 0)]
