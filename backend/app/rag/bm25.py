"""预构建、适合中文检索的 BM25 倒排索引。"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from collections.abc import Sequence

from .types import Chunk

_TOKEN_PATTERN = re.compile(
    r"[a-z0-9]+(?:[._:/-][a-z0-9]+)*|[\u4e00-\u9fff]+", re.IGNORECASE
)


def tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    for part in _TOKEN_PATTERN.findall(str(text).lower()):
        if all("\u4e00" <= char <= "\u9fff" for char in part):
            tokens.extend(
                [part]
                if len(part) == 1
                else [part[index : index + 2] for index in range(len(part) - 1)]
            )
        else:
            tokens.append(part)
    return tokens


class BM25Index:
    """知识变化时构建语料统计信息，检索时只读取命中的倒排表。"""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = float(k1)
        self.b = float(b)
        self._chunks: dict[str, Chunk] = {}
        self._lengths: dict[str, int] = {}
        self._postings: dict[str, tuple[tuple[str, int], ...]] = {}
        self._average_length = 1.0

    def rebuild(self, chunks: Sequence[Chunk]) -> None:
        chunk_map: dict[str, Chunk] = {}
        lengths: dict[str, int] = {}
        postings: dict[str, list[tuple[str, int]]] = defaultdict(list)

        for chunk in chunks:
            terms = tokenize(chunk.text)
            frequencies = Counter(terms)
            chunk_map[chunk.id] = chunk
            lengths[chunk.id] = len(terms)
            for term, frequency in frequencies.items():
                postings[term].append((chunk.id, frequency))

        self._chunks = chunk_map
        self._lengths = lengths
        self._postings = {
            term: tuple(rows) for term, rows in postings.items()
        }
        self._average_length = (
            sum(lengths.values()) / len(lengths) if lengths else 1.0
        )

    def search(self, query: str, limit: int = 50) -> list[dict]:
        query_terms = set(tokenize(query))
        document_count = len(self._chunks)
        if not query_terms or not document_count:
            return []

        scores: dict[str, float] = defaultdict(float)
        for term in query_terms:
            rows = self._postings.get(term, ())
            document_frequency = len(rows)
            if not document_frequency:
                continue
            inverse_frequency = math.log(
                1
                + (document_count - document_frequency + 0.5)
                / (document_frequency + 0.5)
            )
            for chunk_id, frequency in rows:
                length = self._lengths[chunk_id]
                denominator = frequency + self.k1 * (
                    1 - self.b + self.b * length / self._average_length
                )
                scores[chunk_id] += (
                    inverse_frequency
                    * frequency
                    * (self.k1 + 1)
                    / denominator
                )

        ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        hits = []
        for chunk_id, score in ordered[: max(int(limit), 0)]:
            item = self._chunks[chunk_id].result()
            item.update(bm25_score=score, source_type="bm25")
            hits.append(item)
        return hits

    @property
    def size(self) -> int:
        return len(self._chunks)
