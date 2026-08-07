"""Deterministic post-generation output validator (no LLM).

Fail closed: any failed check → ValidationResult.passed=False.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

import yaml

from src.ingest.paths import CORPUS_PATH, ROOT
from src.safety.lexicon import find_lexicon_hits, find_meta_language_hits

# URL-ish tokens in answer body (http/https).
_URL_RE = re.compile(r"https?://[^\s\]\)>\"']+", re.I)

# Numbers: integers, decimals, percentages, Indian ₹ amounts (optional commas).
_NUMBER_RE = re.compile(
    r"(?<![A-Za-z])"  # not mid-token like ABCDE1234F
    r"(?:"
    r"₹\s*[\d,]+(?:\.\d+)?|"
    r"[\d,]+(?:\.\d+)?%?|"
    r"\d+(?:\.\d+)+|"
    r"\d+"
    r")"
    r"(?![A-Za-z])",
)


@dataclass(frozen=True)
class ValidationResult:
    passed: bool
    failed_checks: list[str] = field(default_factory=list)
    details: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "passed": self.passed,
            "failed_checks": list(self.failed_checks),
            "details": dict(self.details),
        }


@lru_cache(maxsize=1)
def load_allowlisted_urls() -> frozenset[str]:
    data = yaml.safe_load(CORPUS_PATH.read_text(encoding="utf-8")) or {}
    urls: set[str] = set()
    for src in data.get("sources") or []:
        url = (src.get("url") or "").strip().rstrip("/")
        if url:
            urls.add(url)
    return frozenset(urls)


def extract_urls(text: str) -> list[str]:
    found = _URL_RE.findall(text or "")
    # Strip trailing punctuation commonly stuck to markdown links
    cleaned: list[str] = []
    for u in found:
        cleaned.append(u.rstrip(".,;:!?)\"'"))
    return cleaned


def count_sentences(text: str) -> int:
    """Count sentences in answer body, ignoring bare URL-only lines."""
    if not text or not text.strip():
        return 0
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        # Drop lines that are only a URL / markdown source chip
        if _URL_RE.fullmatch(stripped):
            continue
        if stripped.startswith("[Source:") or stripped.startswith("Last updated"):
            continue
        # Strip inline URLs for sentence splitting
        lines.append(_URL_RE.sub(" ", stripped))
    body = " ".join(lines)
    body = re.sub(r"\s+", " ", body).strip()
    if not body:
        return 0
    # Split on . ! ? followed by space or end; keep abbreviations soft (v1 simple)
    parts = re.split(r"(?<=[.!?])\s+", body)
    sentences = [p.strip() for p in parts if p.strip()]
    return len(sentences)


def _normalise_number_token(tok: str) -> str:
    t = tok.strip().replace(",", "").replace(" ", "")
    t = t.replace("₹", "")
    return t.lower()


def extract_numbers(text: str) -> list[str]:
    raw = _NUMBER_RE.findall(text or "")
    out: list[str] = []
    for tok in raw:
        norm = _normalise_number_token(tok)
        if not norm or norm in {"%"}:
            continue
        # Skip lone years that look like dates only if desired — keep all for strictness
        out.append(norm)
    return out


def _url_canonical(url: str) -> str:
    return (url or "").strip().rstrip("/")


def validate_answer(
    answer: str,
    *,
    cited_chunk_text: str = "",
    allowlisted_urls: Iterable[str] | None = None,
) -> ValidationResult:
    """
    Deterministic checks (architecture §7.7 / PRD F3.3):
      sentence_count ≤ 3
      citation_count == 1
      allow_list: URL ∈ five Groww URLs
      numeric_verbatim: every number in answer ⊆ cited chunk text
      advisory_lexicon: zero blocklist hits
    """
    failed: list[str] = []
    details: dict = {}

    allow = (
        frozenset(_url_canonical(u) for u in allowlisted_urls)
        if allowlisted_urls is not None
        else load_allowlisted_urls()
    )

    # --- sentence count ---
    n_sent = count_sentences(answer)
    details["sentence_count"] = n_sent
    if n_sent > 3 or n_sent < 1:
        failed.append("sentence_count")

    # --- citations ---
    urls = [_url_canonical(u) for u in extract_urls(answer)]
    details["urls"] = urls
    details["citation_count"] = len(urls)
    if len(urls) != 1:
        failed.append("citation_count")

    # --- allow-list (only when exactly one URL, still flag bad URL if any present) ---
    if urls:
        bad = [u for u in urls if u not in allow]
        details["non_allowlisted"] = bad
        if bad:
            failed.append("allow_list")
        # Host sanity: must be groww.in path under mutual-funds when single URL
        for u in urls:
            parsed = urlparse(u)
            if parsed.netloc.lower() not in {"groww.in", "www.groww.in"}:
                if "allow_list" not in failed:
                    failed.append("allow_list")

    # --- numeric verbatim ---
    answer_nums = extract_numbers(answer)
    # Exclude numbers that appear only inside URLs already stripped — extract from body
    body_for_nums = _URL_RE.sub(" ", answer or "")
    answer_nums = extract_numbers(body_for_nums)
    chunk_nums = set(extract_numbers(cited_chunk_text))
    details["answer_numbers"] = answer_nums
    details["chunk_numbers"] = sorted(chunk_nums)
    missing = [n for n in answer_nums if n not in chunk_nums]
    # Also require substring presence for percentage forms like 0.71% in chunk
    missing_strict: list[str] = []
    chunk_flat = (cited_chunk_text or "").replace(",", "").replace(" ", "").lower()
    for n in answer_nums:
        if n in chunk_nums:
            continue
        # Accept if raw token appears in chunk (e.g. 0.71% vs 0.71)
        bare = n.rstrip("%")
        if bare and bare in chunk_flat:
            continue
        if n in chunk_flat:
            continue
        missing_strict.append(n)
    details["missing_numbers"] = missing_strict
    if missing_strict:
        failed.append("numeric_verbatim")

    # --- advisory lexicon ---
    hits = find_lexicon_hits(body_for_nums)
    details["lexicon_hits"] = hits
    if hits:
        failed.append("advisory_lexicon")

    # --- meta-language (internal machinery leak) ---
    meta_hits = find_meta_language_hits(body_for_nums)
    details["meta_language_hits"] = meta_hits
    if meta_hits:
        failed.append("meta_language")

    # Deduplicate while preserving order
    seen: set[str] = set()
    ordered: list[str] = []
    for c in failed:
        if c not in seen:
            seen.add(c)
            ordered.append(c)

    return ValidationResult(passed=not ordered, failed_checks=ordered, details=details)


def fixtures_path() -> Path:
    return ROOT / "eval" / "fixtures" / "validator" / "fail_closed.json"
