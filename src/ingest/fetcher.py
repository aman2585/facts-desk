"""HTML-only fetcher for allow-listed Groww scheme pages."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from .corpus_loader import CorpusConfig
from .hasher import content_hash, utc_now_iso
from .paths import ALLOWED_HOST, FETCH_RETRIES, FETCH_TIMEOUT_S, RAW_DIR, USER_AGENT


@dataclass
class FetchResult:
    source_id: str
    requested_url: str
    final_url: str
    status_code: int
    content_type: str
    html: str
    content_hash: str
    fetched_at: str
    ok: bool
    error: str | None = None
    charset: str | None = None


class AllowListError(ValueError):
    pass


def _assert_allowlisted(url: str, allowlisted: set[str]) -> None:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if host != ALLOWED_HOST and not host.endswith("." + ALLOWED_HOST):
        raise AllowListError(f"Host not allowed: {host}")
    normalised = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
    allowed_norm = {u.rstrip("/") for u in allowlisted}
    if normalised not in allowed_norm:
        raise AllowListError(f"Final URL not in allow-list: {url}")


def _is_html(content_type: str, url: str) -> bool:
    ct = (content_type or "").lower()
    if "pdf" in ct or url.lower().endswith(".pdf"):
        return False
    return "html" in ct or ct.startswith("text/") or ct == ""


def _charset_from_content_type(content_type: str) -> str | None:
    m = re.search(r"charset\s*=\s*([^\s;]+)", content_type or "", re.I)
    if not m:
        return None
    return m.group(1).strip().strip("\"'").lower()


def decode_response_html(resp: httpx.Response) -> tuple[str, str]:
    """
    Decode response bytes using the HTTP Content-Type charset when present.
    Falls back to httpx charset detection, then UTF-8.
    """
    ctype = resp.headers.get("content-type", "")
    charset = _charset_from_content_type(ctype) or (resp.charset_encoding or None) or "utf-8"
    try:
        html = resp.content.decode(charset)
    except LookupError:
        charset = "utf-8"
        html = resp.content.decode("utf-8")
    except UnicodeDecodeError:
        # Last resort: utf-8 with replacement (should be rare for Groww)
        charset = "utf-8"
        html = resp.content.decode("utf-8", errors="replace")
    return html, charset


def fetch_source(source_id: str, url: str, corpus: CorpusConfig) -> FetchResult:
    """GET one allow-listed HTML page with retries. Never follows off-allow-list redirects."""
    fetched_at = utc_now_iso()
    last_error: str | None = None

    for attempt in range(FETCH_RETRIES + 1):
        try:
            with httpx.Client(
                follow_redirects=True,
                timeout=FETCH_TIMEOUT_S,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Charset": "utf-8",
                },
            ) as client:
                resp = client.get(url)
                final_url = str(resp.url)
                _assert_allowlisted(final_url, corpus.allowlisted_urls)
                ctype = resp.headers.get("content-type", "")
                if not _is_html(ctype, final_url):
                    raise AllowListError(f"Non-HTML content-type rejected: {ctype}")
                html, charset = decode_response_html(resp)
                if not html or len(html) < 500:
                    raise RuntimeError("HTML payload too small / empty")

                result = FetchResult(
                    source_id=source_id,
                    requested_url=url,
                    final_url=final_url,
                    status_code=resp.status_code,
                    content_type=ctype,
                    html=html,
                    content_hash=content_hash(html),
                    fetched_at=fetched_at,
                    ok=resp.status_code == 200,
                    error=None if resp.status_code == 200 else f"HTTP {resp.status_code}",
                    charset=charset,
                )
                _persist_raw(result)
                return result
        except Exception as exc:  # noqa: BLE001 — surfaced in FetchResult
            last_error = str(exc)
            if attempt < FETCH_RETRIES:
                time.sleep(1.5 * (attempt + 1))

    return FetchResult(
        source_id=source_id,
        requested_url=url,
        final_url=url,
        status_code=0,
        content_type="",
        html="",
        content_hash="",
        fetched_at=fetched_at,
        ok=False,
        error=last_error or "fetch failed",
        charset=None,
    )


def _persist_raw(result: FetchResult) -> None:
    if not result.html:
        return
    out_dir = RAW_DIR / result.source_id
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = result.fetched_at.replace(":", "").replace("-", "")
    (out_dir / f"{stamp}.html").write_text(result.html, encoding="utf-8")
    (out_dir / "latest.html").write_text(result.html, encoding="utf-8")
    meta = {
        "source_id": result.source_id,
        "requested_url": result.requested_url,
        "final_url": result.final_url,
        "status_code": result.status_code,
        "content_type": result.content_type,
        "charset": result.charset,
        "content_hash": result.content_hash,
        "fetched_at": result.fetched_at,
    }
    (out_dir / "latest_meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
