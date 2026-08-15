from app.rag.dense import ExactDenseIndex
from app.rag.types import Chunk


def test_dense_scans_every_chunk_and_ranks_by_cosine():
    index = ExactDenseIndex(2)
    index.rebuild(
        [
            Chunk("a", "doc", 1, "A", "test", 0, "相似", (1.0, 0.0)),
            Chunk("b", "doc", 1, "B", "test", 1, "不相似", (0.0, 1.0)),
        ]
    )

    hits = index.search([1.0, 0.0], limit=1)

    assert hits[0]["chunk_id"] == "a"
    assert hits[0]["similarity"] == 1.0
