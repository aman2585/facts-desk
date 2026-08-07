"""Content hashing for change detection."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any

from .paths import HASHES_DIR, PARSER_CHUNKER_VERSION


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


_STABLE_KEYS = (
    "scheme_name",
    "fund_house",
    "scheme_code",
    "category",
    "sub_category",
    "expense_ratio",
    "exit_load",
    "min_sip_investment",
    "min_investment_amount",
    "mini_additional_investment",
    "fund_manager",
    "benchmark",
    "benchmark_name",
    "aum",
    "sip_allowed",
    "lock_in",
    "nfo_risk",
)


def _extract_next_data_json(html: str) -> dict[str, Any] | None:
    m = re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


def stable_payload_for_hash(html: str) -> str:
    """
    Hash stable fund facts from Groww __NEXT_DATA__, not the full HTML.

    Full HTML includes volatile Cloudflare/build noise that would defeat skip-rebuild.
    Includes PARSER_CHUNKER_VERSION so parser/chunker logic changes force rebuild.
    """
    next_data = _extract_next_data_json(html)
    if not next_data:
        text = re.sub(r'nonce="[^"]*"', "", html)
        text = re.sub(r"\s+", " ", text).strip()
        envelope = {
            "parser_chunker_version": PARSER_CHUNKER_VERSION,
            "fallback_html": text,
        }
        return json.dumps(envelope, sort_keys=True, default=str)

    page = (next_data.get("props") or {}).get("pageProps") or {}
    mf = page.get("mfServerSideData") or {}
    stable: dict[str, Any] = {k: mf.get(k) for k in _STABLE_KEYS}
    stats = mf.get("return_stats") or []
    if stats and isinstance(stats[0], dict):
        stable["risk"] = stats[0].get("risk")
        stable["risk_rating"] = stats[0].get("risk_rating")
    envelope = {
        "parser_chunker_version": PARSER_CHUNKER_VERSION,
        "fund_fields": stable,
    }
    return json.dumps(envelope, sort_keys=True, default=str)


def content_hash(html: str) -> str:
    digest = hashlib.sha256(stable_payload_for_hash(html).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def load_hash_record(source_id: str) -> dict[str, Any] | None:
    path = HASHES_DIR / f"{source_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_hash_record(source_id: str, record: dict[str, Any]) -> None:
    HASHES_DIR.mkdir(parents=True, exist_ok=True)
    path = HASHES_DIR / f"{source_id}.json"
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
