"""支持动态知识更新和原子索引切换的进程内 RAG 门面。"""

from __future__ import annotations

import os
from collections.abc import Callable
from threading import RLock
from uuid import uuid4

from .embed import DEFAULT_DIM, Embedder
from .index_manager import IndexManager
from .ingest import chunk_text
from .rerank import Reranker
from .retriever import HybridRetriever
from .types import Chunk, EmbedderProtocol, KnowledgeDocument, RerankerProtocol


class RAGEngine:
    def __init__(
        self,
        *,
        embedder: EmbedderProtocol | None = None,
        embedder_factory: Callable[[], EmbedderProtocol] = Embedder,
        reranker: RerankerProtocol | None = None,
        reranker_factory: Callable[[], RerankerProtocol] = Reranker,
        dimension: int | None = None,
        chunk_size: int = 1000,
        chunk_overlap: int = 150,
    ):
        configured_dimension = int(
            dimension
            or getattr(embedder, "dim", 0)
            or os.getenv("SERVICELOOP_RAG_EMBED_DIM", DEFAULT_DIM)
        )
        self.index_manager = IndexManager(configured_dimension)
        self._embedder = embedder
        self._embedder_factory = embedder_factory
        self._reranker = reranker
        self._reranker_factory = reranker_factory
        self._retriever: HybridRetriever | None = None
        self._documents: dict[str, KnowledgeDocument] = {}
        self._history: dict[str, list[KnowledgeDocument]] = {}
        self._write_lock = RLock()
        self.chunk_size = int(chunk_size)
        self.chunk_overlap = int(chunk_overlap)

    def _get_embedder(self) -> EmbedderProtocol:
        if self._embedder is None:
            self._embedder = self._embedder_factory()
        if self._embedder.dim != self.index_manager.dimension:
            raise ValueError(
                f"配置的向量维度 {self.index_manager.dimension} 与向量模型维度 "
                f"{self._embedder.dim} 不一致。"
            )
        return self._embedder

    def _get_reranker(self) -> RerankerProtocol:
        """按需创建精排模型，并保证调用方得到确定的非空实例。"""

        if self._reranker is None:
            self._reranker = self._reranker_factory()
        return self._reranker

    def _get_retriever(self) -> HybridRetriever:
        if self._retriever is None:
            self._retriever = HybridRetriever(
                self.index_manager,
                self._get_embedder(),
                self._get_reranker,
            )
        return self._retriever

    def upsert_document(
        self,
        *,
        title: str,
        content: str,
        document_id: str | None = None,
        source: str = "operations",
    ) -> dict:
        with self._write_lock:
            return self._upsert_document(
                title=title,
                content=content,
                document_id=document_id,
                source=source,
            )

    def replace_documents(self, documents: list[dict]) -> dict:
        """用持久化知识重建完整快照，并在成功后一次性切换。"""

        with self._write_lock:
            prepared: list[tuple[dict, list[str]]] = []
            texts: list[str] = []
            for item in documents:
                title = str(item["title"]).strip()
                content = str(item["content"]).strip()
                if not title or not content:
                    raise ValueError("持久化知识的标题和正文不能为空。")
                pieces = chunk_text(content, self.chunk_size, self.chunk_overlap)
                prepared.append((item, pieces))
                texts.extend(pieces)

            embeddings = self._get_embedder().encode(texts) if texts else []
            offset = 0
            restored: dict[str, KnowledgeDocument] = {}
            for item, pieces in prepared:
                document_id = str(item["id"])
                version = int(item["version"])
                vectors = embeddings[offset : offset + len(pieces)]
                offset += len(pieces)
                chunks = tuple(
                    Chunk(
                        id=f"{document_id}:v{version}:{index}",
                        document_id=document_id,
                        document_version=version,
                        title=str(item["title"]).strip(),
                        source=str(item.get("source") or "operations"),
                        chunk_index=index,
                        text=text,
                        embedding=tuple(float(value) for value in vector),
                    )
                    for index, (text, vector) in enumerate(
                        zip(pieces, vectors, strict=True)
                    )
                )
                restored[document_id] = KnowledgeDocument(
                    id=document_id,
                    title=str(item["title"]).strip(),
                    content=str(item["content"]).strip(),
                    version=version,
                    source=str(item.get("source") or "operations"),
                    chunks=chunks,
                )

            index_version = self.index_manager.rebuild(
                [chunk for document in restored.values() for chunk in document.chunks]
            )
            self._documents = restored
            self._history = {
                document_id: [document] for document_id, document in restored.items()
            }
            return {
                "document_count": len(restored),
                "chunk_count": self.index_manager.chunk_count,
                "index_version": index_version,
            }

    def _upsert_document(
        self,
        *,
        title: str,
        content: str,
        document_id: str | None,
        source: str,
    ) -> dict:
        clean_title = title.strip()
        clean_content = content.strip()
        if not clean_title:
            raise ValueError("知识标题不能为空。")
        if not clean_content:
            raise ValueError("知识正文不能为空。")

        resolved_id = document_id.strip() if document_id else str(uuid4())
        current = self._documents.get(resolved_id)
        version = current.version + 1 if current else 1
        pieces = chunk_text(clean_content, self.chunk_size, self.chunk_overlap)
        embeddings = self._get_embedder().encode(pieces)
        chunks = tuple(
            Chunk(
                id=f"{resolved_id}:v{version}:{index}",
                document_id=resolved_id,
                document_version=version,
                title=clean_title,
                source=source,
                chunk_index=index,
                text=text,
                embedding=tuple(float(value) for value in embedding),
            )
            for index, (text, embedding) in enumerate(
                zip(pieces, embeddings, strict=True)
            )
        )
        candidate = KnowledgeDocument(
            id=resolved_id,
            title=clean_title,
            content=clean_content,
            version=version,
            source=source,
            chunks=chunks,
        )
        proposed_documents = {**self._documents, resolved_id: candidate}
        proposed_chunks = [
            chunk
            for document in proposed_documents.values()
            for chunk in document.chunks
        ]

        # 只有 Dense 和 BM25 索引全部构建成功后，才修改当前知识状态。
        index_version = self.index_manager.rebuild(proposed_chunks)
        self._documents = proposed_documents
        self._history.setdefault(resolved_id, []).append(candidate)
        result = candidate.summary()
        result["index_version"] = index_version
        return result

    def archive_document(self, document_id: str) -> dict:
        with self._write_lock:
            return self._archive_document(document_id)

    def _archive_document(self, document_id: str) -> dict:
        if document_id not in self._documents:
            raise KeyError(f"找不到知识文档：{document_id}")
        proposed_documents = dict(self._documents)
        removed = proposed_documents.pop(document_id)
        proposed_chunks = [
            chunk
            for document in proposed_documents.values()
            for chunk in document.chunks
        ]
        index_version = self.index_manager.rebuild(proposed_chunks)
        self._documents = proposed_documents
        return {
            "id": removed.id,
            "status": "archived",
            "index_version": index_version,
        }

    def search(self, query: str, limit: int = 8, pool: int = 50) -> list[dict]:
        clean_query = query.strip()
        if not clean_query:
            raise ValueError("检索问题不能为空。")
        if not self.index_manager.chunk_count:
            return []
        return self._get_retriever().search(clean_query, limit=limit, pool=pool)

    def list_documents(self) -> list[dict]:
        return [
            document.summary()
            for document in sorted(
                self._documents.values(), key=lambda item: item.updated_at, reverse=True
            )
        ]

    def list_versions(self, document_id: str) -> list[dict]:
        history = self._history.get(document_id)
        if not history:
            raise KeyError(f"找不到知识文档：{document_id}")
        return [
            {**document.summary(), "content": document.content}
            for document in reversed(history)
        ]

    def status(self) -> dict:
        return {
            **self.index_manager.status(),
            "document_count": len(self._documents),
            "ready": bool(self.index_manager.chunk_count),
            "storage": "temporary_in_memory",
        }
