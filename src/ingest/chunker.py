"""Section-aware chunking with breadcrumbs and metadata enrichment."""

from __future__ import annotations

import re
from typing import Any

from .corpus_loader import Source
from .hasher import utc_now_iso
from .parser import (
    COMPARE_HEADING_RE,
    HOLDINGS_HEADING_RE,
    INR,
    PERFORMANCE_HEADING_RE,
    ParsedDocument,
)
from .paths import CHUNK_MAX_WORDS, CHUNK_MIN_WORDS, CHUNK_OVERLAP_WORDS

# Mojibake of UTF-8 ₹ (U+20B9 → bytes E2 82 B9) when decoded as cp1252/latin-1:
#   U+00E2 â, U+201A ‚, U+00B9 ¹  → visible as "â‚¹"
MOJIBAKE_MARKERS = ("\u00e2", "\u00c3", "\u00b9", "\u201a")  # â Ã ¹ ‚
MOJIBAKE_RUPEE = "\u00e2\u201a\u00b9"  # â‚¹

# Fail closed if return figures leak past heading exclusion (expense-ratio
# bare "0.75%" is allowed; signed/horizon/CAGR return patterns are not).
RETURN_FIGURE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bCAGR\b", re.I),
    re.compile(r"\b(?:trailing|rolling|historic)\s+returns?\b", re.I),
    re.compile(r"\bfund returns\b", re.I),
    re.compile(r"\breturn calculator\b", re.I),
    re.compile(r"\bcategory average\b", re.I),
    re.compile(r"\b(?:1Y|3Y|5Y|10Y)\b.{0,60}\d+(?:\.\d+)?\s*%", re.I | re.S),
    re.compile(r"\d+(?:\.\d+)?\s*%.{0,60}\b(?:1Y|3Y|5Y|10Y)\b", re.I | re.S),
    re.compile(
        r"\b(?:1|3|5|10)\s*Y(?:ear)?s?\b.{0,60}\+\s*\d+(?:\.\d+)?\s*%",
        re.I | re.S,
    ),
    re.compile(r"\+\s*\d+(?:\.\d+)?\s*%"),  # e.g. +20.5% / + 7.14 %
)


def assert_clean_utf8_text(text: str, chunk_id: str = "") -> None:
    """
    Fail if text contains cp1252-mojibake stand-ins for ₹ / other UTF-8 sequences.

    Note: a *correct* Unicode rupee (U+20B9) does NOT match these markers. If a
    UTF-8 file is later opened as cp1252, viewers show â‚¹ even though the
    in-memory/on-disk Unicode was fine — that display bug is why we also write
    chunks.jsonl with ensure_ascii=True (\\u20b9 escapes).
    """
    if MOJIBAKE_RUPEE in text:
        raise ValueError(
            f"Encoding corruption in chunk {chunk_id!r}: found mojibake rupee {MOJIBAKE_RUPEE!r}. "
            "UTF-8 bytes were decoded as cp1252 somewhere in the pipeline."
        )
    for marker in MOJIBAKE_MARKERS:
        if marker in text:
            raise ValueError(
                f"Encoding corruption in chunk {chunk_id!r}: "
                f"found mojibake marker {marker!r} (U+{ord(marker):04X}). "
                "Ensure UTF-8 read/write and correct HTTP charset decoding."
            )


def assert_no_return_figures(text: str, chunk_id: str = "") -> None:
    """
    Assert published chunk text has no performance/return-figure patterns.

    Complements PERFORMANCE_HEADING_RE: heading exclusion is primary;
    this catches leakage into Investment details / other sections.
    """
    for pat in RETURN_FIGURE_PATTERNS:
        m = pat.search(text or "")
        if m:
            raise ValueError(
                f"Return-figure leak in chunk {chunk_id!r}: "
                f"matched {pat.pattern!r} at {m.group(0)!r}. "
                "Performance/returns must not be published (PRD §9.2)."
            )


def _word_chunks(text: str, max_words: int = CHUNK_MAX_WORDS, overlap: int = CHUNK_OVERLAP_WORDS) -> list[str]:
    words = text.split()
    if not words:
        return []
    if len(words) <= max_words:
        return [" ".join(words)]
    out: list[str] = []
    start = 0
    while start < len(words):
        end = min(len(words), start + max_words)
        out.append(" ".join(words[start:end]))
        if end >= len(words):
            break
        start = max(0, end - overlap)
    return out


def _is_excluded_section(heading_path: list[str]) -> bool:
    return any(
        HOLDINGS_HEADING_RE.search(h or "")
        or COMPARE_HEADING_RE.search(h or "")
        or PERFORMANCE_HEADING_RE.search(h or "")
        for h in heading_path
    )


def chunk_document(
    doc: ParsedDocument,
    source: Source,
    content_hash: str,
    fetched_at: str,
    corpus_version: str,
) -> list[dict[str, Any]]:
    """
    Build chunks for one source.

    Holdings, compare/similar-funds, and performance/returns sections are
    excluded (not answerable; comparison and returns are refusable per PRD §9.2).
    """
    chunks: list[dict[str, Any]] = []
    counter = 0

    for section in doc.sections:
        heading_path = section.get("heading_path") or [doc.scheme_name]
        if _is_excluded_section(heading_path):
            continue

        breadcrumb = " > ".join(heading_path)
        base_text = section.get("text") or ""
        tables = section.get("tables") or []
        parts = _word_chunks(base_text)
        for part in parts:
            word_count = len(part.split())
            if word_count < CHUNK_MIN_WORDS and not tables:
                continue
            if word_count > CHUNK_MAX_WORDS:
                for sub in _word_chunks(part, max_words=CHUNK_MAX_WORDS, overlap=0):
                    counter += 1
                    chunk_id = f"{source.id}::c_{counter:03d}"
                    prefixed = f"{breadcrumb}\n{sub}".strip()
                    assert_clean_utf8_text(prefixed, chunk_id)
                    assert_no_return_figures(prefixed, chunk_id)
                    chunks.append(
                        _chunk_record(
                            chunk_id,
                            source,
                            doc,
                            heading_path,
                            breadcrumb,
                            prefixed,
                            [],
                            content_hash,
                            fetched_at,
                            corpus_version,
                        )
                    )
                continue

            counter += 1
            chunk_id = f"{source.id}::c_{counter:03d}"
            prefixed = f"{breadcrumb}\n{part}".strip()
            assert_clean_utf8_text(prefixed, chunk_id)
            assert_no_return_figures(prefixed, chunk_id)
            chunk_tables = tables if (tables and word_count <= CHUNK_MAX_WORDS) else []
            chunks.append(
                _chunk_record(
                    chunk_id,
                    source,
                    doc,
                    heading_path,
                    breadcrumb,
                    prefixed,
                    chunk_tables,
                    content_hash,
                    fetched_at,
                    corpus_version,
                )
            )

    if not chunks and doc.kv_rows:
        counter = 1
        lines = [f"{r['label']}: {r['value']}" for r in doc.kv_rows]
        text = f"{doc.scheme_name} > Investment details\n" + " | ".join(lines)
        assert_clean_utf8_text(text, f"{source.id}::c_001")
        assert_no_return_figures(text, f"{source.id}::c_001")
        chunks.append(
            _chunk_record(
                f"{source.id}::c_{counter:03d}",
                source,
                doc,
                [doc.scheme_name, "Investment details"],
                f"{doc.scheme_name} > Investment details",
                text,
                doc.kv_rows,
                content_hash,
                fetched_at or utc_now_iso(),
                corpus_version,
            )
        )

    for ch in chunks:
        assert_clean_utf8_text(ch["text"], ch["chunk_id"])
        assert_no_return_figures(ch["text"], ch["chunk_id"])
        # Rupee amounts must use real U+20B9, never mojibake
        if "Minimum SIP" in ch["text"] or "AUM" in ch["text"]:
            if INR not in ch["text"] and "Rs" not in ch["text"]:
                raise ValueError(f"Chunk {ch['chunk_id']} missing INR/rupee marker for money fields")
        for row in ch.get("tables") or []:
            cell = f"{row.get('label', '')}{row.get('value', '')}"
            assert_clean_utf8_text(cell, ch["chunk_id"])
            assert_no_return_figures(cell, ch["chunk_id"])

    return chunks


def _chunk_record(
    chunk_id: str,
    source: Source,
    doc: ParsedDocument,
    heading_path: list[str],
    breadcrumb: str,
    text: str,
    tables: list[dict[str, str]],
    content_hash: str,
    fetched_at: str,
    corpus_version: str,
) -> dict[str, Any]:
    return {
        "chunk_id": chunk_id,
        "source_id": source.id,
        "source_url": source.url,
        "amc": "HDFC",
        "scheme_name": doc.scheme_name,
        "scheme_code": source.scheme_code,
        "plan": source.plan,
        "option": source.option,
        "document_type": "groww_scheme_page",
        "authority": source.authority,
        "heading_path": heading_path,
        "heading_path_str": breadcrumb,
        "text": text,
        "tables": tables,
        "content_hash": content_hash,
        "fetched_at": fetched_at,
        "corpus_version": corpus_version,
    }
