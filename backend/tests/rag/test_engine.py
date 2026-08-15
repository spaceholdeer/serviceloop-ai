from __future__ import annotations

import pytest

from app.rag.engine import RAGEngine


class FakeEmbedder:
    dim = 2

    @staticmethod
    def _vector(text: str) -> list[float]:
        return [1.0, 0.0] if "退款" in text else [0.0, 1.0]

    def encode(self, texts):
        return [self._vector(text) for text in texts]

    def encode_queries(self, queries):
        return [self._vector(query) for query in queries]


class FakeReranker:
    def rerank(self, query, candidates):
        for rank, candidate in enumerate(candidates):
            candidate["rerank_score"] = 1.0 - rank / 100
        return candidates


def engine() -> RAGEngine:
    return RAGEngine(embedder=FakeEmbedder(), reranker=FakeReranker(), dimension=2)


def test_dynamic_upsert_creates_a_new_version_and_replaces_old_chunks():
    rag = engine()
    first = rag.upsert_document(
        document_id="refund-policy", title="退款", content="退款需要三个工作日"
    )
    second = rag.upsert_document(
        document_id="refund-policy", title="退款", content="退款需要五个工作日"
    )

    assert first["version"] == 1
    assert second["version"] == 2
    assert rag.status()["document_count"] == 1
    assert rag.status()["chunk_count"] == 1
    assert [item["version"] for item in rag.list_versions("refund-policy")] == [2, 1]
    assert rag.search("退款")[0]["document_version"] == 2
    assert "五个工作日" in rag.search("退款")[0]["text"]


def test_failed_rebuild_keeps_the_previous_document_version(monkeypatch):
    rag = engine()
    rag.upsert_document(document_id="refund", title="退款", content="旧规则可以退款")

    def fail(_chunks):
        raise RuntimeError("索引构建失败")

    monkeypatch.setattr(rag.index_manager, "rebuild", fail)
    with pytest.raises(RuntimeError, match="索引构建失败"):
        rag.upsert_document(document_id="refund", title="退款", content="新规则不能退款")

    assert rag.list_documents()[0]["version"] == 1


def test_archive_removes_document_from_both_indexes():
    rag = engine()
    rag.upsert_document(document_id="refund", title="退款", content="可以申请退款")

    result = rag.archive_document("refund")

    assert result["status"] == "archived"
    assert rag.status()["chunk_count"] == 0
    assert rag.search("退款") == []


def test_accepts_both_chinese_and_english_knowledge_and_queries():
    rag = engine()

    chinese_result = rag.upsert_document(
        title="X3 Pro 兼容说明",
        content="X3 Pro 支持 iPhone 16，但部分功能要求 iOS 18。",
    )
    english_result = rag.upsert_document(
        title="Refund Policy",
        content="Refund requests are processed within three business days.",
    )

    assert chinese_result["version"] == 1
    assert english_result["version"] == 1
    assert rag.search("X3 Pro 支持 iPhone 16 吗？")
    assert rag.search("refund policy")
