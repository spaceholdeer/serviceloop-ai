from app.rag.rrf import rrf_fuse


def test_rrf_rewards_chunks_found_by_both_retrievers():
    dense = [{"chunk_id": "both"}, {"chunk_id": "dense"}]
    bm25 = [{"chunk_id": "both"}, {"chunk_id": "keyword"}]

    fused = rrf_fuse([dense, bm25])

    assert fused[0]["chunk_id"] == "both"
    assert fused[0]["rrf_score"] > fused[1]["rrf_score"]
