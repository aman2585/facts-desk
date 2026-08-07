"""Response assembler — answer / coverage / refusal / performance formats."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache
from typing import Any, Literal

import yaml

from src.generate.validator import extract_urls
from src.ingest.paths import CORPUS_PATH
from src.safety.refusals import SCHEME_URLS, SafetyHandlerResult

_URL_RE_INLINE = re.compile(r"https?://[^\s\]\)>\"']+", re.I)

ResponseType = Literal[
    "answer",
    "refusal",
    "coverage",
    "clarify",
    "performance",
    "pii_warn",
    "api_error",
]


@dataclass
class AssembledResponse:
    response_type: ResponseType
    text: str
    citation_url: str | None = None
    source_label: str | None = None
    freshness_date: str | None = None
    educational_url: str | None = None
    display: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "response_type": self.response_type,
            "text": self.text,
            "citation_url": self.citation_url,
            "source_label": self.source_label,
            "freshness_date": self.freshness_date,
            "educational_url": self.educational_url,
            "display": self.display,
            "meta": self.meta,
        }


@lru_cache(maxsize=1)
def _source_meta() -> dict[str, dict[str, str]]:
    """source_url / scheme_code → display fields from corpus.yaml."""
    data = yaml.safe_load(CORPUS_PATH.read_text(encoding="utf-8")) or {}
    by_url: dict[str, dict[str, str]] = {}
    for src in data.get("sources") or []:
        url = str(src.get("url") or "").rstrip("/")
        entry = {
            "display_name": str(src.get("display_name") or ""),
            "authority": str(src.get("authority") or "Groww"),
            "source_id": str(src.get("id") or ""),
            "url": url,
        }
        if url:
            by_url[url] = entry
        for code in src.get("schemes") or []:
            by_url[f"scheme:{code}"] = entry
    return by_url


def format_freshness(fetched_at: str | None) -> str | None:
    """Format fetched_at ISO timestamp as 'DD Mon YYYY'."""
    if not fetched_at:
        return None
    raw = fetched_at.strip()
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        dt = datetime.fromisoformat(raw)
        return dt.strftime("%d %b %Y")
    except ValueError:
        return fetched_at[:10] if len(fetched_at) >= 10 else fetched_at


def strip_urls_from_text(text: str) -> str:
    """Remove http(s) URLs when a structured citation/scheme link already exists."""
    if not text:
        return ""
    cleaned = _URL_RE_INLINE.sub(" ", text)
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r" +", " ", cleaned)
    return cleaned.strip(" \t\n:;,-")


def _answer_body(raw: str) -> str:
    """Strip trailing bare URL lines from model output for display body."""
    lines = (raw or "").splitlines()
    kept: list[str] = []
    for line in lines:
        stripped = line.strip()
        if extract_urls(stripped) and re.fullmatch(r"https?://\S+", stripped):
            continue
        if stripped.startswith("[Source:") or stripped.startswith("[Education]"):
            continue
        kept.append(line)
    return "\n".join(kept).strip()


def assemble_answer(
    raw_output: str,
    *,
    citation_url: str | None,
    fetched_at: str | None,
    scheme_name: str | None = None,
    used_fallback: bool = False,
    meta: dict[str, Any] | None = None,
) -> AssembledResponse:
    url = (citation_url or "").rstrip("/") or None
    if not url:
        urls = extract_urls(raw_output)
        url = urls[0].rstrip("/") if urls else None

    info = _source_meta().get(url or "", {})
    display_name = scheme_name or info.get("display_name") or "Groww scheme page"
    authority = info.get("authority") or "Groww"
    freshness = format_freshness(fetched_at)
    body = _answer_body(raw_output)
    # Citation chip carries the link — keep raw URL out of card text.
    if url:
        body = strip_urls_from_text(body)

    source_label = f"{authority} — {display_name}"
    parts = [body] if body else []
    if url:
        parts.append(f"[Source: {source_label}]({url})")
    if freshness:
        parts.append(f"Last updated from sources: {freshness}")
    display = "\n\n".join(parts)

    rtype: ResponseType = "coverage" if used_fallback else "answer"
    return AssembledResponse(
        response_type=rtype,
        text=body,
        citation_url=url,
        source_label=source_label if url else None,
        freshness_date=freshness,
        display=display,
        meta=dict(meta or {}),
    )


def assemble_safety(
    handler: SafetyHandlerResult,
    *,
    meta: dict[str, Any] | None = None,
) -> AssembledResponse:
    kind_map: dict[str, ResponseType] = {
        "refusal": "refusal",
        "refusal_with_edu": "refusal",
        "performance_redirect": "performance",
        "coverage_limit": "coverage",
        "clarify": "clarify",
        "pii_warn": "pii_warn",
    }
    rtype = kind_map.get(handler.kind, "refusal")
    text = handler.text or ""
    # Scheme / edu buttons carry links — strip any inlined URLs from card text.
    if handler.scheme_url or handler.educational_url:
        text = strip_urls_from_text(text)
    parts = [text]
    if handler.educational_url:
        parts.append(f"[Education]({handler.educational_url})")
    if handler.scheme_url:
        url = handler.scheme_url.rstrip("/")
        info = _source_meta().get(url, {})
        label = info.get("display_name") or "Groww scheme page"
        parts.append(f"[Source: Groww — {label}]({url})")
    return AssembledResponse(
        response_type=rtype,
        text=text,
        citation_url=handler.scheme_url,
        educational_url=handler.educational_url,
        source_label=None,
        freshness_date=None,
        display="\n\n".join(parts),
        meta={
            **(meta or {}),
            "intent": handler.intent,
            "handler_kind": handler.kind,
        },
    )


def assemble_coverage(
    message: str,
    *,
    scheme_code: str | None = None,
    fetched_at: str | None = None,
    meta: dict[str, Any] | None = None,
) -> AssembledResponse:
    url = SCHEME_URLS.get(scheme_code or "") if scheme_code else None
    info = _source_meta().get((url or "").rstrip("/"), {}) if url else {}
    freshness = format_freshness(fetched_at)
    parts = [message]
    if url:
        label = info.get("display_name") or "Groww scheme page"
        parts.append(f"[Source: Groww — {label}]({url})")
    if freshness:
        parts.append(f"Last updated from sources: {freshness}")
    return AssembledResponse(
        response_type="coverage",
        text=message,
        citation_url=url,
        source_label=f"Groww — {info.get('display_name')}" if url else None,
        freshness_date=freshness,
        display="\n\n".join(parts),
        meta=dict(meta or {}),
    )


COVERAGE_GATE_FAIL = (
    "I couldn't find that in my official sources, so I'd rather not guess. "
    "You can check the scheme page on Groww, or reach out to support."
)


def assemble_api_error(
    message: str,
    *,
    status_code: int | None = None,
    meta: dict[str, Any] | None = None,
) -> AssembledResponse:
    """Distinct card when the model API fails (e.g. 429) — not a coverage gap."""
    detail = f" (HTTP {status_code})" if status_code is not None else ""
    text = (
        f"The answer could not be generated because the model API failed{detail}. "
        "This is a temporary service error, not a missing fact in the corpus."
    )
    if message:
        text = f"{text}\n\nDetails: {message}"
    return AssembledResponse(
        response_type="api_error",
        text=text,
        display=text,
        meta={
            **(meta or {}),
            "api_error": True,
            "status_code": status_code,
        },
    )

