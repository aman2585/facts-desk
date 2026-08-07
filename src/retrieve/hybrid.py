"""Hybrid retrieval: dense (Chroma) ∪ BM25 with optional metadata pre-filter."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.ingest.embedder import embed_texts
from src.ingest.indexes import _tokenize

from .config import RetrievalConfig
from .store import PublishedIndex, get_bm25, get_chroma_collection


@dataclass
class Candidate:
    chunk_id: str
    source_id: str
    scheme_code: str
    plan: str
    source_url: str
    text: str
    heading_path: list[str] = field(default_factory=list)
    dense_score: float | None = None
    bm25_score: float | None = None
    rerank_score: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def _chroma_where(scheme_code: str | None, plan: str | None) -> dict[str, Any] | None:
    clauses: list[dict[str, Any]] = []
    if scheme_code:
        clauses.append({"scheme_code": scheme_code})
    if plan:
        clauses.append({"plan": plan})
    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}


def dense_search(
    query: str,
    index: PublishedIndex,
    cfg: RetrievalConfig,
    scheme_code: str | None = None,
    plan: str | None = None,
) -> list[Candidate]:
    collection = get_chroma_collection(index.chroma_collection)
    qvec = embed_texts([query], model_name=cfg.embedding_model)[0].tolist()
    n = min(cfg.dense_top_k, max(1, len(index.chunk_ids)))
    where = _chroma_where(scheme_code, plan)
    kwargs: dict[str, Any] = {
        "query_embeddings": [qvec],
        "n_results": n,
        "include": ["documents", "metadatas", "distances"],
    }
    if where is not None:
        kwargs["where"] = where
    result = collection.query(**kwargs)

    hits: list[Candidate] = []
    ids = (result.get("ids") or [[]])[0]
    docs = (result.get("documents") or [[]])[0]
    metas = (result.get("metadatas") or [[]])[0]
    dists = (result.get("distances") or [[]])[0]
    for i, cid in enumerate(ids):
        meta = metas[i] or {}
        dist = float(dists[i]) if dists else 0.0
        # Chroma cosine distance: similarity ≈ 1 - distance (for normalised vectors)
        sim = 1.0 - dist
        ch = index.chunks_by_id.get(cid, {})
        hits.append(
            Candidate(
                chunk_id=cid,
                source_id=str(meta.get("source_id") or ch.get("source_id") or ""),
                scheme_code=str(meta.get("scheme_code") or ch.get("scheme_code") or ""),
                plan=str(meta.get("plan") or ch.get("plan") or ""),
                source_url=str(meta.get("source_url") or ch.get("source_url") or ""),
                text=docs[i] if docs else (ch.get("text") or ""),
                heading_path=list(ch.get("heading_path") or []),
                dense_score=sim,
                metadata=dict(meta),
            )
        )
    return hits


def bm25_search(
    query: str,
    index: PublishedIndex,
    cfg: RetrievalConfig,
    scheme_code: str | None = None,
    plan: str | None = None,
) -> list[Candidate]:
    bm25, chunk_ids = get_bm25(index.version_dir)
    scores = bm25.get_scores(_tokenize(query))
    ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)

    hits: list[Candidate] = []
    for idx, score in ranked:
        if len(hits) >= cfg.bm25_top_k:
            break
        cid = chunk_ids[idx]
        ch = index.chunks_by_id.get(cid)
        if not ch:
            continue
        if scheme_code and ch.get("scheme_code") != scheme_code:
            continue
        if plan and ch.get("plan") != plan:
            continue
        hits.append(
            Candidate(
                chunk_id=cid,
                source_id=str(ch.get("source_id") or ""),
                scheme_code=str(ch.get("scheme_code") or ""),
                plan=str(ch.get("plan") or ""),
                source_url=str(ch.get("source_url") or ""),
                text=str(ch.get("text") or ""),
                heading_path=list(ch.get("heading_path") or []),
                bm25_score=float(score),
                metadata={
                    "heading_path_str": ch.get("heading_path_str", ""),
                    "corpus_version": ch.get("corpus_version", ""),
                },
            )
        )
    return hits


def hybrid_retrieve(
    query: str,
    index: PublishedIndex,
    cfg: RetrievalConfig,
    scheme_code: str | None = None,
    plan: str | None = None,
) -> list[Candidate]:
    """Union dense ∪ BM25 candidates; merge scores by chunk_id."""
    dense_hits = dense_search(query, index, cfg, scheme_code=scheme_code, plan=plan)
    lexical_hits = bm25_search(query, index, cfg, scheme_code=scheme_code, plan=plan)

    merged: dict[str, Candidate] = {}
    for hit in dense_hits + lexical_hits:
        existing = merged.get(hit.chunk_id)
        if existing is None:
            merged[hit.chunk_id] = hit
            continue
        if hit.dense_score is not None:
            existing.dense_score = hit.dense_score
        if hit.bm25_score is not None:
            existing.bm25_score = hit.bm25_score
        if not existing.text and hit.text:
            existing.text = hit.text

    # Stable order: prefer higher dense, then bm25
    def sort_key(c: Candidate) -> tuple[float, float]:
        return (c.dense_score if c.dense_score is not None else -1.0, c.bm25_score or 0.0)

    return sorted(merged.values(), key=sort_key, reverse=True)
