"""Deterministic labelled-attribute completion for extractive answers.

When the cited chunk holds labelled pairs for the attribute the user asked
about (e.g. Category + Sub-category), the answer must include those labels
and values as written — not a partial paraphrase.
"""

from __future__ import annotations

import re
from typing import Any, Sequence

from src.generate.validator import extract_urls

# Category / scheme-type questions (g026–g028 and similar).
# Do NOT match bare scheme names like "HDFC Mid Cap Fund" in TER/exit-load queries.
_CATEGORY_QUERY = re.compile(
    r"\b(categor(?:y|ies)|sub[- ]?categor(?:y|ies))\b|"
    r"\ba\s+(?:mid|small|large|flexi)[- ]?cap\s+(?:scheme|fund)\b",
    re.I,
)

_CATEGORY_LABELS = ("Category", "Sub-category")


def is_category_query(query: str) -> bool:
    return bool(_CATEGORY_QUERY.search(query or ""))


def _table_map(chunk: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for row in chunk.get("tables") or []:
        label = str(row.get("label") or "").strip()
        value = str(row.get("value") or "").strip()
        if label and value:
            out[label] = value
    # Fallback: pipe-separated KV in chunk text
    text = chunk.get("text") or ""
    for m in re.finditer(
        r"(Category|Sub-category)\s*:\s*([^|\n]+)",
        text,
        flags=re.I,
    ):
        label = m.group(1)
        # Normalise casing to canonical labels
        canon = "Sub-category" if label.lower().startswith("sub") else "Category"
        if canon not in out:
            out[canon] = m.group(2).strip()
    return out


def extract_category_pairs(chunk: dict[str, Any]) -> list[tuple[str, str]]:
    """Return ordered (label, value) for Category then Sub-category when present."""
    m = _table_map(chunk)
    pairs: list[tuple[str, str]] = []
    for label in _CATEGORY_LABELS:
        if label in m and m[label]:
            pairs.append((label, m[label]))
    return pairs


def format_category_answer(pairs: Sequence[tuple[str, str]]) -> str:
    """Match golden verified_answer style: 'Category: X; Sub-category: Y'."""
    return "; ".join(f"{lab}: {val}" for lab, val in pairs)


def _answer_has_all_pairs(answer: str, pairs: Sequence[tuple[str, str]]) -> bool:
    hay = (answer or "").lower()
    for _lab, val in pairs:
        if val.lower() not in hay:
            return False
    # Prefer both labels present when we have both pairs
    if len(pairs) >= 2:
        has_category = "category" in hay
        has_sub = "sub-category" in hay or "sub category" in hay
        if not (has_category and has_sub):
            return False
    return True


def _split_body_and_citation(raw: str) -> tuple[str, str | None]:
    urls = extract_urls(raw or "")
    cite = urls[0].rstrip("/") if urls else None
    lines: list[str] = []
    for line in (raw or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if cite and cite in stripped.replace(")", ""):
            continue
        lines.append(stripped)
    body = "\n".join(lines).strip()
    return body, cite


def _resolve_chunk(
    raw: str,
    chunks: Sequence[dict[str, Any]],
) -> dict[str, Any] | None:
    urls = extract_urls(raw or "")
    if urls:
        cite = urls[0].rstrip("/")
        for ch in chunks:
            if str(ch.get("source_url") or "").rstrip("/") == cite:
                return ch
    return chunks[0] if chunks else None


def complete_labelled_attributes(
    query: str,
    raw_answer: str,
    chunks: Sequence[dict[str, Any]],
) -> str:
    """
    If the query asks for category and the cited chunk has Category /
    Sub-category labelled pairs, ensure the answer states both as written.

    Leaves non-category answers and missing labels unchanged.
    """
    if not is_category_query(query) or not chunks:
        return raw_answer

    chunk = _resolve_chunk(raw_answer, chunks)
    if not chunk:
        return raw_answer

    pairs = extract_category_pairs(chunk)
    if len(pairs) < 2:
        # Need both labelled pairs to enforce the dual-attribute contract
        return raw_answer

    if _answer_has_all_pairs(raw_answer, pairs):
        return raw_answer

    _body, cite = _split_body_and_citation(raw_answer)
    url = cite or str(chunk.get("source_url") or "").rstrip("/") or None
    body = format_category_answer(pairs)
    if url:
        return f"{body}\n\n{url}"
    return body
