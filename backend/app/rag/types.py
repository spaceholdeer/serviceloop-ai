"""各检索阶段共用的轻量无依赖数据类型。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Protocol


@dataclass(frozen=True)
class Chunk:
    id: str
    document_id: str
    document_version: int
    title: str
    source: str
    chunk_index: int
    text: str
    embedding: tuple[float, ...]

    def result(self) -> dict:
        data = asdict(self)
        data.pop("embedding", None)
        data["chunk_id"] = data.pop("id")
        return data


@dataclass(frozen=True)
class KnowledgeDocument:
    id: str
    title: str
    content: str
    version: int = 1
    source: str = "operations"
    status: str = "published"
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    chunks: tuple[Chunk, ...] = ()

    def summary(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "version": self.version,
            "source": self.source,
            "status": self.status,
            "updated_at": self.updated_at.isoformat(),
            "chunk_count": len(self.chunks),
        }


class EmbedderProtocol(Protocol):
    dim: int

    def encode(self, texts) -> list[list[float]]: ...

    def encode_queries(self, queries) -> list[list[float]]: ...


class RerankerProtocol(Protocol):
    def rerank(self, query: str, candidates: list[dict]) -> list[dict]: ...
