"""Groundedness verifier — claims must be supported by the cited chunk."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.generate.validator import extract_numbers, extract_urls

_STOP = frozenset(
    """
    a an the and or of to in on for is are was were be been being
    this that these those it its with from by as at if then so not
    no yes can could would should may might must do does did have has had
    i you we they he she them their our your my
    fund scheme page groww hdfc direct growth
    """.split()
)

_WORD_RE = re.compile(r"[A-Za-z0-9%]+")


@dataclass(frozen=True)
class GroundednessResult:
    passed: bool
    reason: str = ""
    details: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "passed": self.passed,
            "reason": self.reason,
            "details": dict(self.details),
        }


def _content_tokens(text: str) -> list[str]:
    toks = []
    for w in _WORD_RE.findall(text or ""):
        low = w.lower()
        if low in _STOP or len(low) < 3:
            continue
        toks.append(low)
    return toks


def verify_groundedness(answer: str, cited_chunk_text: str) -> GroundednessResult:
    """
    Fail closed if the answer is not supported by the cited chunk.

    Checks:
      1. Answer has a body (not empty after stripping URLs).
      2. Every number in the answer body appears in the cited chunk.
      3. A majority of content tokens from the answer appear in the cited chunk.
    """
    urls = extract_urls(answer)
    body = answer or ""
    for u in urls:
        body = body.replace(u, " ")
    body = re.sub(r"\s+", " ", body).strip()
    if not body:
        return GroundednessResult(False, "empty_answer_body")

    chunk = cited_chunk_text or ""
    chunk_flat = chunk.replace(",", "").replace(" ", "").lower()
    chunk_lower = chunk.lower()

    missing_nums: list[str] = []
    for n in extract_numbers(body):
        bare = n.rstrip("%")
        if n in chunk_flat or (bare and bare in chunk_flat):
            continue
        # also allow spaced forms in original chunk
        if n in chunk_lower or bare in chunk_lower:
            continue
        missing_nums.append(n)
    if missing_nums:
        return GroundednessResult(
            False,
            "numbers_not_in_cited_chunk",
            {"missing_numbers": missing_nums},
        )

    tokens = _content_tokens(body)
    if not tokens:
        # Number-only short answer already checked numbers
        return GroundednessResult(True, "numbers_only_ok")

    present = [t for t in tokens if t in chunk_lower]
    ratio = len(present) / max(1, len(tokens))
    details = {
        "token_count": len(tokens),
        "present_count": len(present),
        "overlap_ratio": round(ratio, 3),
    }
    if ratio < 0.5:
        return GroundednessResult(
            False,
            "low_lexical_overlap_with_cited_chunk",
            details,
        )
    return GroundednessResult(True, "ok", details)
