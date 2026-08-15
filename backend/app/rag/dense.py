"""对全部生效知识块执行 Dense 精确召回。"""

from __future__ import annotations

import math
from collections.abc import Sequence

from .types import Chunk


def _normalize(vector: Sequence[float]) -> tuple[float, ...]:
    values = tuple(float(value) for value in vector)
    norm = math.sqrt(sum(value * value for value in values))
    if norm == 0.0:
        return tuple(0.0 for _ in values)
    return tuple(value / norm for value in values)


class ExactDenseIndex:
    """在内存保存归一化向量，并扫描全部 ``N x 向量维度`` 数值。"""

    def __init__(self, dimension: int):
        self.dimension = int(dimension)
        self._rows: tuple[tuple[Chunk, tuple[float, ...]], ...] = ()

    def rebuild(self, chunks: Sequence[Chunk]) -> None:
        rows = []
        for chunk in chunks:
            if len(chunk.embedding) != self.dimension:
                raise ValueError(
                    f"知识块 {chunk.id} 的向量维度不匹配："
                    f"{len(chunk.embedding)} != {self.dimension}"
                )
            rows.append((chunk, _normalize(chunk.embedding)))
        self._rows = tuple(rows)

    def search(
        self,
        query_vector: Sequence[float],
        limit: int = 50,
        threshold: float = 0.0,
    ) -> list[dict]:
        if len(query_vector) != self.dimension:
            raise ValueError(
                f"问题向量维度不匹配："
                f"{len(query_vector)} != {self.dimension}"
            )
        normalized_query = _normalize(query_vector)
        hits: list[dict] = []
        for chunk, normalized_embedding in self._rows:
            score = sum(
                query_value * document_value
                for query_value, document_value in zip(
                    normalized_query, normalized_embedding, strict=True
                )
            )
            if score < threshold:
                continue
            item = chunk.result()
            item.update(similarity=score, source_type="vector")
            hits.append(item)
        hits.sort(key=lambda item: item["similarity"], reverse=True)
        return hits[: max(int(limit), 0)]

    @property
    def size(self) -> int:
        return len(self._rows)
