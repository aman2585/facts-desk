"""Cross-encoder reranker (BAAI/bge-reranker-base)."""

from __future__ import annotations

from functools import lru_cache

from .config import RetrievalConfig
from .hybrid import Candidate


@lru_cache(maxsize=2)
def _get_reranker(model_name: str):
    from sentence_transformers import CrossEncoder

    return CrossEncoder(model_name)


def rerank(
    query: str,
    candidates: list[Candidate],
    cfg: RetrievalConfig,
) -> list[Candidate]:
    if not candidates:
        return []
    model = _get_reranker(cfg.reranker_model)
    pairs = [[query, c.text] for c in candidates]
    scores = model.predict(pairs)
    scored: list[Candidate] = []
    for c, score in zip(candidates, scores):
        c.rerank_score = float(score)
        scored.append(c)
    scored.sort(key=lambda x: x.rerank_score if x.rerank_score is not None else float("-inf"), reverse=True)
    return scored[: cfg.rerank_top_k]
