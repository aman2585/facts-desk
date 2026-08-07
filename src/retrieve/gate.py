"""Confidence gate and scheme-disambiguation signals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .config import RetrievalConfig
from .hybrid import Candidate
from .normaliser import NormalisedQuery

GateStatus = Literal["ok", "gate_fail", "ambiguous", "uncovered", "unresolved"]


@dataclass
class GateDecision:
    status: GateStatus
    top_score: float | None
    tau: float
    scheme_codes_in_hits: list[str]
    reason: str


def apply_gate(
    nq: NormalisedQuery,
    ranked: list[Candidate],
    cfg: RetrievalConfig,
    tau: float | None = None,
) -> GateDecision:
    threshold = cfg.tau if tau is None else float(tau)

    if nq.resolution == "uncovered":
        return GateDecision(
            status="uncovered",
            top_score=None,
            tau=threshold,
            scheme_codes_in_hits=[],
            reason="Query names a scheme/AMC outside the five-URL corpus",
        )

    if nq.resolution == "ambiguous":
        return GateDecision(
            status="ambiguous",
            top_score=None,
            tau=threshold,
            scheme_codes_in_hits=[],
            reason="Scheme reference is ambiguous; clarify before answering",
        )

    if not ranked:
        return GateDecision(
            status="gate_fail",
            top_score=None,
            tau=threshold,
            scheme_codes_in_hits=[],
            reason="No retrieval candidates",
        )

    top_score = ranked[0].rerank_score
    if top_score is None:
        top_score = ranked[0].dense_score if ranked[0].dense_score is not None else float("-inf")

    schemes = []
    for c in ranked:
        if c.scheme_code and c.scheme_code not in schemes:
            schemes.append(c.scheme_code)

    if top_score < threshold:
        return GateDecision(
            status="gate_fail",
            top_score=float(top_score),
            tau=threshold,
            scheme_codes_in_hits=schemes,
            reason=f"Top rerank score {top_score:.4f} < tau {threshold:.4f}",
        )

    # Unresolved scheme + multi-scheme top hits → ask to clarify (no wrong guess)
    if nq.resolution == "unresolved" and len(schemes) >= cfg.ambiguity_min_schemes:
        return GateDecision(
            status="ambiguous",
            top_score=float(top_score),
            tau=threshold,
            scheme_codes_in_hits=schemes,
            reason="Top hits span multiple schemes; clarify which scheme",
        )

    if nq.resolution == "unresolved" and not schemes:
        return GateDecision(
            status="unresolved",
            top_score=float(top_score),
            tau=threshold,
            scheme_codes_in_hits=[],
            reason="Scheme entity unresolved and no scheme metadata on hits",
        )

    return GateDecision(
        status="ok",
        top_score=float(top_score),
        tau=threshold,
        scheme_codes_in_hits=schemes,
        reason="Passed confidence gate",
    )
