"""Audit log — reconstructable answer trace (F6.5; supports F8.1 feedback).

Persists redacted query, intent, chunk ids, corpus_version, response card,
citation, validator verdicts, model_version, timestamp, session_id.
Never stores raw PII.
"""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from src.api.cards import card_to_dict
from src.api.config import ApiConfig, load_config

_lock = threading.Lock()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _day_path(audit_dir: Path, when: datetime | None = None) -> Path:
    dt = when or datetime.now(timezone.utc)
    return audit_dir / f"audit_{dt.strftime('%Y-%m-%d')}.jsonl"


def write_audit_entry(
    *,
    session_id: str,
    redacted_query: str,
    intent: str | None,
    chunk_ids: list[str] | None,
    corpus_version: str | None,
    card: Any,
    citation_url: str | None,
    validator_verdicts: Any,
    model_version: str | None,
    cache_hit: bool,
    cache_key: str | None = None,
    path: str | None = None,
    extra: dict[str, Any] | None = None,
    cfg: ApiConfig | None = None,
) -> str:
    """Append one audit record. Returns audit_id."""
    config = cfg or load_config()
    config.audit_dir.mkdir(parents=True, exist_ok=True)
    audit_id = str(uuid.uuid4())
    card_dict = card_to_dict(card) if hasattr(card, "model_dump") else dict(card)
    entry: dict[str, Any] = {
        "audit_id": audit_id,
        "timestamp": _utc_now_iso(),
        "session_id": session_id,
        "redacted_query": redacted_query,
        "intent": intent,
        "chunk_ids": list(chunk_ids or []),
        "corpus_version": corpus_version,
        "response": card_dict,
        "citation": citation_url or card_dict.get("citation_url") or card_dict.get(
            "scheme_url"
        ),
        "validator_verdicts": validator_verdicts,
        "model_version": model_version,
        "cache_hit": cache_hit,
        "cache_key": cache_key,
        "path": path,
    }
    if extra:
        entry["extra"] = extra

    target = _day_path(config.audit_dir)
    line = json.dumps(entry, ensure_ascii=False) + "\n"
    with _lock:
        with target.open("a", encoding="utf-8") as fh:
            fh.write(line)
    return audit_id


def iter_audit(
    *,
    session_id: str | None = None,
    since: str | None = None,
    cfg: ApiConfig | None = None,
    limit: int = 1000,
) -> Iterator[dict[str, Any]]:
    """Yield audit entries newest-file-first, optionally filtered."""
    config = cfg or load_config()
    if not config.audit_dir.exists():
        return
    files = sorted(config.audit_dir.glob("audit_*.jsonl"), reverse=True)
    n = 0
    for path in files:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in reversed(lines):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if session_id and row.get("session_id") != session_id:
                continue
            if since and str(row.get("timestamp") or "") < since:
                continue
            yield row
            n += 1
            if n >= limit:
                return
