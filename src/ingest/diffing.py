"""Structured attribute snapshots and numeric-diff logging (Phase 2: log-only)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .hasher import utc_now_iso
from .paths import DIFFS_DIR, STAGING_DIR


NUMERIC_KEYS = ("expense_ratio", "exit_load", "min_sip_investment", "min_investment_amount", "aum")


def extract_attributes(source_id: str, scheme_code: str, structured: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "scheme_code": scheme_code,
        "captured_at": utc_now_iso(),
        "fields": {
            # Prefer raw numerics for diffs; fall back to display strings
            "expense_ratio": structured.get("_raw_expense_ratio", structured.get("expense_ratio")),
            "exit_load": structured.get("exit_load"),
            "min_sip": structured.get("_raw_min_sip_investment", structured.get("min_sip_investment")),
            "min_investment": structured.get(
                "_raw_min_investment_amount", structured.get("min_investment_amount")
            ),
            "min_additional": structured.get("mini_additional_investment"),
            "aum": structured.get("_raw_aum", structured.get("aum")),
            "riskometer": structured.get("riskometer"),
            "benchmark": structured.get("benchmark"),
            "category": structured.get("category"),
            "sub_category": structured.get("sub_category"),
            "fund_manager": structured.get("fund_manager"),
            "lock_in": structured.get("lock_in"),
        },
        "display_fields": {
            "expense_ratio": structured.get("expense_ratio"),
            "min_sip": structured.get("min_sip_investment"),
            "min_investment": structured.get("min_investment_amount"),
            "aum": structured.get("aum"),
        },
    }


def load_previous_attributes(source_id: str) -> dict[str, Any] | None:
    # Prefer last published staging attrs if pointer exists
    from .paths import PUBLISHED_POINTER

    if not PUBLISHED_POINTER.exists():
        return None
    pointer = json.loads(PUBLISHED_POINTER.read_text(encoding="utf-8"))
    version = pointer.get("corpus_version")
    if not version:
        return None
    path = STAGING_DIR / version / "attributes" / f"{source_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def diff_numeric(previous: dict[str, Any] | None, current: dict[str, Any]) -> list[dict[str, Any]]:
    if not previous:
        return []
    prev_fields = previous.get("fields") or {}
    curr_fields = current.get("fields") or {}
    diffs: list[dict[str, Any]] = []
    for key in ("expense_ratio", "exit_load", "min_sip", "min_investment", "aum"):
        old, new = prev_fields.get(key), curr_fields.get(key)
        if old is None and new is None:
            continue
        if str(old) != str(new):
            diffs.append({"field": key, "old": old, "new": new})
    return diffs


def log_diffs(source_id: str, diffs: list[dict[str, Any]], corpus_version: str) -> Path | None:
    if not diffs:
        return None
    DIFFS_DIR.mkdir(parents=True, exist_ok=True)
    path = DIFFS_DIR / f"{source_id}_{corpus_version.replace(':', '')}.json"
    payload = {
        "source_id": source_id,
        "corpus_version": corpus_version,
        "logged_at": utc_now_iso(),
        "phase": 2,
        "note": "Numeric diffs logged only; human approval queue ships in Phase 6.",
        "diffs": diffs,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
