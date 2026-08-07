#!/usr/bin/env python3
"""Validate Phase 4 part 1: deterministic validator fixtures + safety layer."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.generate.validator import validate_answer
from src.retrieve.normaliser import normalise_query
from src.safety.intent import INTENT_CLASSES, classify_intent
from src.safety.pii import redact_pii
from src.safety.refusals import handle_performance, handle_refusal


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    raise SystemExit(1)


def ok(msg: str) -> None:
    print(f"OK: {msg}".encode("ascii", errors="replace").decode("ascii"))


def validate_adversarial_count() -> None:
    path = ROOT / "eval" / "adversarial" / "items.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data["items"]
    if len(items) < 40:
        fail(f"adversarial need >=40 items, found {len(items)}")
    # Required Phase 3 gap queries present
    queries = {i["query"] for i in items}
    for q in ("Axis Midcap exit load", "Kotak Flexicap TER"):
        if q not in queries:
            fail(f"adversarial missing required fixture query: {q}")
    compound = [
        i
        for i in items
        if "and should" in i["query"].lower()
        or "and is it" in i["query"].lower()
        or "and whether" in i["query"].lower()
        or "then advise" in i["query"].lower()
        or "and would you" in i["query"].lower()
        or ("and" in i["query"].lower() and i["expected_intent"] in {"advisory", "comparative"})
    ]
    if len(compound) < 5:
        fail(f"need >=5 compound factual+advisory/comparative items, found {len(compound)}")
    uncovered = [i for i in items if i["expected_intent"] == "uncovered_scheme"]
    if len(uncovered) < 8:
        fail(f"need >=8 uncovered_scheme items, found {len(uncovered)}")
    ok(f"adversarial suite - {len(items)} items (>=40)")


def validate_validator_fixtures() -> None:
    path = ROOT / "eval" / "fixtures" / "validator" / "fail_closed.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    chunk = data["cited_chunk_text"]
    allow = data["allowlisted_urls"]
    required_ids = {
        "fail_four_sentences",
        "fail_zero_citations",
        "fail_two_citations",
        "fail_non_allowlisted_url",
        "fail_number_not_verbatim",
        "fail_advisory_phrase",
    }
    found_ids = {f["id"] for f in data["fixtures"]}
    missing = required_ids - found_ids
    if missing:
        fail(f"validator fixtures missing ids: {sorted(missing)}")

    for fix in data["fixtures"]:
        result = validate_answer(
            fix["answer"],
            cited_chunk_text=chunk,
            allowlisted_urls=allow,
        )
        if result.passed:
            fail(f"fixture {fix['id']} unexpectedly PASSED (must fail closed)")
        expected = set(fix["expect_failed_checks"])
        actual = set(result.failed_checks)
        if not expected.issubset(actual):
            fail(
                f"fixture {fix['id']}: expected failed checks {sorted(expected)} "
                f"subset actual {sorted(actual)}; details={result.details}"
            )
        ok(f"validator fail-closed - {fix['id']} -> {result.failed_checks}")


def validate_uncovered_gap() -> None:
    path = ROOT / "eval" / "fixtures" / "safety" / "uncovered.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for fix in data["fixtures"]:
        q = fix["query"]
        nq = normalise_query(q)
        ir = classify_intent(q)
        if nq.resolution != "uncovered":
            fail(f"{fix['id']}: normaliser resolution={nq.resolution}, want uncovered")
        if nq.scheme_code is not None:
            fail(f"{fix['id']}: scheme_code={nq.scheme_code}, must be None")
        if ir.intent != "uncovered_scheme":
            fail(f"{fix['id']}: intent={ir.intent}, want uncovered_scheme")
        # Must not retrieve-as-ok: refusal short-circuit
        resp = handle_refusal(ir.intent)
        if resp.kind != "coverage_limit":
            fail(f"{fix['id']}: handler kind={resp.kind}, want coverage_limit")
        ok(f"uncovered gap - {fix['id']} -> uncovered_scheme / coverage_limit")


def validate_intent_classes() -> None:
    if len(INTENT_CLASSES) != 10:
        fail(f"INTENT_CLASSES must be 10, got {len(INTENT_CLASSES)}")
    expected = {
        "factual_in_scope",
        "advisory",
        "comparative",
        "predictive",
        "performance",
        "personal_account",
        "pii_bearing",
        "out_of_domain",
        "uncovered_scheme",
        "ambiguous",
    }
    if set(INTENT_CLASSES) != expected:
        fail(f"INTENT_CLASSES mismatch: {set(INTENT_CLASSES)}")
    ok("intent classifier - 10 classes")


def validate_pii() -> None:
    sample = "My PAN is ABCDE1234F and folio is 1234567890 — tell me my capital gains."
    r = redact_pii(sample)
    if "ABCDE1234F" in r.redacted or "1234567890" in r.redacted:
        fail(f"PII not redacted: {r.redacted}")
    if "pan" not in r.types_found or "folio" not in r.types_found:
        fail(f"PII types incomplete: {r.types_found}")
    ir = classify_intent(sample)
    if ir.intent != "pii_bearing":
        fail(f"PII query intent={ir.intent}, want pii_bearing")
    if "ABCDE1234F" in ir.redacted_query:
        fail("classifier leaked raw PAN")
    ok("PII redactor - PAN/folio redacted before classify")


def validate_performance_handler() -> None:
    resp = handle_performance(scheme_code="hdfc_small_cap_direct_growth")
    if resp.kind != "performance_redirect":
        fail(f"performance kind={resp.kind}")
    if "%" in resp.text or "CAGR" in resp.text.upper():
        fail(f"performance text must not contain return figures: {resp.text}")
    if not resp.scheme_url or "groww.in" not in resp.scheme_url:
        fail(f"performance must link Groww scheme page, got {resp.scheme_url}")
    ok("performance handler - no inline returns, Groww link only")


def validate_sample_adversarial_intents() -> None:
    path = ROOT / "eval" / "adversarial" / "items.json"
    items = json.loads(path.read_text(encoding="utf-8"))["items"]
    # Spot-check key behaviours (not full golden accuracy gate)
    checks = [
        ("a023", "uncovered_scheme"),
        ("a024", "uncovered_scheme"),
        ("a021", "advisory"),
        ("a025", "advisory"),
        ("a014", "out_of_domain"),
        ("a017", "ambiguous"),
        ("a008", "performance"),
        ("a003", "comparative"),
        ("a039", "uncovered_scheme"),
    ]
    by_id = {i["id"]: i for i in items}
    for iid, want in checks:
        q = by_id[iid]["query"]
        got = classify_intent(q).intent
        if got != want:
            fail(f"{iid}: classify={got}, want {want} (query={q!r})")
        ok(f"intent spot-check - {iid} -> {got}")


def validate_in_corpus_scheme_aliases() -> None:
    """Nifty 50 / BAF (and all five schemes) must resolve — not uncovered FP."""
    cases = [
        ("Nifty 50", "hdfc_nifty_50_index_direct_growth"),
        ("NIFTY 50 Index Fund", "hdfc_nifty_50_index_direct_growth"),
        ("Balanced Advantage", "hdfc_balanced_advantage_direct_growth"),
        ("BAF", "hdfc_balanced_advantage_direct_growth"),
        ("What index does HDFC Nifty 50 Index Fund track?", "hdfc_nifty_50_index_direct_growth"),
        ("HDFC Balanced Advantage Fund Direct Growth expense ratio?", "hdfc_balanced_advantage_direct_growth"),
        ("HDFC Mid Cap Fund", "hdfc_mid_cap_direct_growth"),
        ("HDFC Flexi Cap", "hdfc_equity_direct_growth"),
        ("HDFC Small Cap", "hdfc_small_cap_direct_growth"),
    ]
    for phrase, want in cases:
        nq = normalise_query(phrase)
        ir = classify_intent(phrase)
        if nq.resolution != "resolved" or nq.scheme_code != want:
            fail(
                f"alias resolve {phrase!r}: resolution={nq.resolution} "
                f"scheme={nq.scheme_code}, want resolved/{want}"
            )
        if ir.intent == "uncovered_scheme":
            fail(f"alias resolve {phrase!r}: intent incorrectly uncovered_scheme")
        ok(f"in-corpus alias - {phrase!r} -> {want}")


def main() -> None:
    validate_adversarial_count()
    validate_validator_fixtures()
    validate_intent_classes()
    validate_uncovered_gap()
    validate_in_corpus_scheme_aliases()
    validate_pii()
    validate_performance_handler()
    validate_sample_adversarial_intents()
    print("Phase 4 part 1 validation passed.")


if __name__ == "__main__":
    main()
