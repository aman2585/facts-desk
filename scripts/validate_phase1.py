#!/usr/bin/env python3
"""Validate Phase 1 eval stubs and corpus allow-list (stdlib only)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ALLOWED_SOURCES = {"src_001", "src_002", "src_003", "src_004", "src_005"}
ALLOWED_GOLDEN_INTENTS = {
    "expense_ratio",
    "exit_load",
    "min_sip",
    "min_additional",
    "lock_in",
    "riskometer",
    "benchmark",
    "category",
    "fund_manager",
    "plan_option",
    "aum",
    "definition_on_page",
}
ALLOWED_ADVERSARIAL_INTENTS = {
    "advisory",
    "comparative",
    "predictive",
    "suitability",
    "performance",
    "calculation",
    "timing",
    "personal_account",
    "out_of_domain",
    "pii_bearing",
    "uncovered_scheme",
    "ambiguous",
    "jailbreak",
}
ALLOWED_BEHAVIOURS = {
    "refuse",
    "refuse_with_edu_link",
    "performance_redirect",
    "coverage_limit",
    "clarify",
    "redact_and_warn",
}

GOLDEN_REQUIRED = {
    "id",
    "query",
    "verified_answer",
    "expected_source_id",
    "intent",
    "verified_by",
    "verified_on",
}
ADVERSARIAL_REQUIRED = {
    "id",
    "query",
    "expected_intent",
    "expected_behaviour",
    "verified_by",
    "verified_on",
}


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    raise SystemExit(1)


def validate_golden(path: Path) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data.get("items")
    if not isinstance(items, list):
        fail(f"{path}: missing items list")
    ids: set[str] = set()
    for i, item in enumerate(items):
        missing = GOLDEN_REQUIRED - set(item)
        if missing:
            fail(f"{path}[{i}]: missing fields {sorted(missing)}")
        if item["id"] in ids:
            fail(f"{path}: duplicate id {item['id']}")
        ids.add(item["id"])
        if item["expected_source_id"] not in ALLOWED_SOURCES:
            fail(f"{path}[{item['id']}]: bad expected_source_id")
        if item["intent"] not in ALLOWED_GOLDEN_INTENTS:
            fail(f"{path}[{item['id']}]: bad intent")
        if len(item["query"].strip()) < 3:
            fail(f"{path}[{item['id']}]: query too short")
    if len(items) < 30:
        fail(f"{path}: need ≥30 golden items, found {len(items)}")
    print(f"OK: golden suite — {len(items)} items")
    return len(items)


def validate_adversarial(path: Path) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data.get("items")
    if not isinstance(items, list):
        fail(f"{path}: missing items list")
    ids: set[str] = set()
    for i, item in enumerate(items):
        missing = ADVERSARIAL_REQUIRED - set(item)
        if missing:
            fail(f"{path}[{i}]: missing fields {sorted(missing)}")
        if item["id"] in ids:
            fail(f"{path}: duplicate id {item['id']}")
        ids.add(item["id"])
        if item["expected_intent"] not in ALLOWED_ADVERSARIAL_INTENTS:
            fail(f"{path}[{item['id']}]: bad expected_intent")
        if item["expected_behaviour"] not in ALLOWED_BEHAVIOURS:
            fail(f"{path}[{item['id']}]: bad expected_behaviour")
    if len(items) < 40:
        fail(f"{path}: need ≥40 adversarial items, found {len(items)}")
    print(f"OK: adversarial suite — {len(items)} items")
    return len(items)


def validate_corpus(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "html_only" not in text:
        fail(f"{path}: format must be html_only")
    if ".pdf" in text.lower():
        fail(f"{path}: PDF references are not allowed in corpus")
    urls = [
        "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth",
        "https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth",
        "https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth",
        "https://groww.in/mutual-funds/hdfc-nifty-50-index-fund-direct-growth",
        "https://groww.in/mutual-funds/hdfc-balanced-advantage-fund-direct-growth",
    ]
    for url in urls:
        if url not in text:
            fail(f"{path}: missing required URL {url}")
    # Exactly five source ids
    for sid in ALLOWED_SOURCES:
        if f"id: {sid}" not in text and f"id: {sid}" not in text.replace('"', ""):
            # YAML may quote or not; check plain id line
            if sid not in text:
                fail(f"{path}: missing source id {sid}")
    print(f"OK: corpus allow-list — 5 Groww HTML URLs, html_only")


def main() -> None:
    validate_corpus(ROOT / "corpus" / "corpus.yaml")
    validate_golden(ROOT / "eval" / "golden" / "items.json")
    validate_adversarial(ROOT / "eval" / "adversarial" / "items.json")
    print("Phase 1 foundation validation passed.")


if __name__ == "__main__":
    main()
