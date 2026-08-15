"""使用 RRF 融合 Dense 与 BM25 候选结果。"""

from __future__ import annotations


def rrf_fuse(rankings: list[list[dict]], rank_constant: int = 60) -> list[dict]:
    scores: dict[str, float] = {}
    cache: dict[str, dict] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            key = str(item["chunk_id"])
            scores[key] = scores.get(key, 0.0) + 1.0 / (rank_constant + rank)
            if key not in cache:
                cache[key] = dict(item)
            else:
                cache[key].update(
                    {name: value for name, value in item.items() if name not in cache[key]}
                )
    ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    fused = []
    for key, score in ordered:
        item = cache[key]
        item["rrf_score"] = score
        fused.append(item)
    return fused
