"""End-to-end hybrid retrieval pipeline (Phase 3)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .config import RetrievalConfig, load_config
from .gate import GateDecision, GateStatus, apply_gate
from .hybrid import Candidate, hybrid_retrieve
from .normaliser import NormalisedQuery, normalise_query
from .rerank import rerank
from .store import PublishedIndex, get_published_index


@dataclass
class RetrievalResult:
    status: GateStatus
    query: NormalisedQuery
    chunks: list[Candidate]
    gate: GateDecision
    corpus_version: str
    chroma_collection: str
    config: RetrievalConfig
    candidates_pre_rerank: int = 0

    def top_source_ids(self, k: int = 5) -> list[str]:
        out: list[str] = []
        for c in self.chunks[:k]:
            if c.source_id and c.source_id not in out:
                out.append(c.source_id)
        return out

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "corpus_version": self.corpus_version,
            "chroma_collection": self.chroma_collection,
            "tau": self.gate.tau,
            "top_score": self.gate.top_score,
            "reason": self.gate.reason,
            "query": {
                "raw": self.query.raw,
                "normalised": self.query.normalised,
                "scheme_code": self.query.scheme_code,
                "resolution": self.query.resolution,
                "matched_alias": self.query.matched_alias,
            },
            "chunks": [
                {
                    "chunk_id": c.chunk_id,
                    "source_id": c.source_id,
                    "scheme_code": c.scheme_code,
                    "rerank_score": c.rerank_score,
                    "dense_score": c.dense_score,
                    "bm25_score": c.bm25_score,
                    "heading_path": c.heading_path,
                }
                for c in self.chunks
            ],
        }


def retrieve(
    query: str,
    *,
    cfg: RetrievalConfig | None = None,
    index: PublishedIndex | None = None,
    tau: float | None = None,
    apply_scheme_filter: bool = True,
) -> RetrievalResult:
    """
    Normalise → (optional metadata filter) → hybrid → rerank → gate.

    Does not call an LLM. Status signals:
      ok | gate_fail | ambiguous | uncovered | unresolved
    """
    config = cfg or load_config()
    published = index or get_published_index()
    nq = normalise_query(query, plan_default=config.plan_default)

    # Early exit for uncovered / pre-retrieval ambiguous — no wrong-scheme search
    if nq.resolution in {"uncovered", "ambiguous"}:
        gate = apply_gate(nq, [], config, tau=tau)
        return RetrievalResult(
            status=gate.status,
            query=nq,
            chunks=[],
            gate=gate,
            corpus_version=published.corpus_version,
            chroma_collection=published.chroma_collection,
            config=config,
        )

    scheme_code = nq.scheme_code if apply_scheme_filter else None
    plan = nq.plan if (apply_scheme_filter and nq.scheme_code) else None

    candidates = hybrid_retrieve(
        nq.normalised,
        published,
        config,
        scheme_code=scheme_code,
        plan=plan,
    )
    ranked = rerank(nq.normalised, candidates, config)
    gate = apply_gate(nq, ranked, config, tau=tau)

    # On gate_fail / ambiguous-from-hits, still return ranked chunks for eval/debug
    # but status tells callers not to generate.
    return RetrievalResult(
        status=gate.status,
        query=nq,
        chunks=ranked,
        gate=gate,
        corpus_version=published.corpus_version,
        chroma_collection=published.chroma_collection,
        config=config,
        candidates_pre_rerank=len(candidates),
    )
