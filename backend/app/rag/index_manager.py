"""构建完整的不可变检索快照，并进行原子切换。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from threading import RLock

from .bm25 import BM25Index
from .dense import ExactDenseIndex
from .types import Chunk


@dataclass(frozen=True)
class IndexSnapshot:
    version: int
    chunks: tuple[Chunk, ...]
    dense: ExactDenseIndex
    bm25: BM25Index
    built_at: datetime


class IndexManager:
    def __init__(self, dimension: int):
        self.dimension = int(dimension)
        dense = ExactDenseIndex(self.dimension)
        bm25 = BM25Index()
        self._snapshot = IndexSnapshot(0, (), dense, bm25, datetime.now(UTC))
        self._lock = RLock()

    def rebuild(self, chunks: list[Chunk] | tuple[Chunk, ...]) -> int:
        """在当前检索快照之外完成构建，成功后一次性替换生效快照。"""

        frozen_chunks = tuple(chunks)
        dense = ExactDenseIndex(self.dimension)
        bm25 = BM25Index()
        dense.rebuild(frozen_chunks)
        bm25.rebuild(frozen_chunks)

        with self._lock:
            version = self._snapshot.version + 1
            self._snapshot = IndexSnapshot(
                version=version,
                chunks=frozen_chunks,
                dense=dense,
                bm25=bm25,
                built_at=datetime.now(UTC),
            )
        return version

    def dense_search(self, query_vector, limit: int, threshold: float) -> list[dict]:
        snapshot = self._snapshot
        return snapshot.dense.search(query_vector, limit=limit, threshold=threshold)

    def bm25_search(self, query: str, limit: int) -> list[dict]:
        snapshot = self._snapshot
        return snapshot.bm25.search(query, limit=limit)

    def status(self) -> dict:
        snapshot = self._snapshot
        return {
            "index_version": snapshot.version,
            "chunk_count": len(snapshot.chunks),
            "embedding_dimension": self.dimension,
            "built_at": snapshot.built_at.isoformat(),
        }

    @property
    def chunk_count(self) -> int:
        return len(self._snapshot.chunks)
