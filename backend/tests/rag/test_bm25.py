from app.rag.bm25 import BM25Index
from app.rag.types import Chunk


def chunk(chunk_id: str, text: str) -> Chunk:
    return Chunk(chunk_id, "doc", 1, "title", "test", 0, text, (1.0, 0.0))


def test_bm25_builds_postings_once_and_queries_relevant_terms():
    index = BM25Index()
    index.rebuild(
        [
            chunk("refund", "退款申请将在三个工作日内处理"),
            chunk("shipping", "物流信息每天更新"),
        ]
    )
    postings_identity = id(index._postings)

    hits = index.search("退款多久处理")

    assert hits[0]["chunk_id"] == "refund"
    assert hits[0]["bm25_score"] > 0
    assert id(index._postings) == postings_identity
