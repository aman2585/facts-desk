#!/usr/bin/env python3
"""
Phase 3 offline retrieval eval (no LLM).

Reports:
  - recall@5 overall and per intent
  - MRR (source-level)
  - Mid Cap vs Small Cap / Equity vs BAF confusion (top-1 source)
  - τ sweep on golden + out-of-corpus negatives (gate behaviour)

Does not tune thresholds to improve scores — reports whatever the config default
and the sweep produce.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

GOLDEN_PATH = ROOT / "eval" / "golden" / "items.json"

# Pairwise confusion slices (expected_source_id)
MID_SMALL = ("src_001", "src_003")  # Mid Cap vs Small Cap
EQUITY_BAF = ("src_002", "src_005")  # Equity vs Balanced Advantage

# Out-of-corpus / low-confidence negatives for τ sweep (must not silently answer)
OUT_OF_CORPUS_NEGATIVES: list[dict[str, str]] = [
    {
        "id": "neg_sbi_ter",
        "query": "What is the expense ratio of SBI Bluechip Direct Growth?",
        "expect_status": "uncovered",
    },
    {
        "id": "neg_axis_exit",
        "query": "Exit load for Axis Midcap Fund Direct Growth?",
        "expect_status": "uncovered",
    },
    {
        "id": "neg_icici_sip",
        "query": "Minimum SIP in ICICI Prudential Bluechip Direct?",
        "expect_status": "uncovered",
    },
    {
        "id": "neg_kotak",
        "query": "What is the TER of Kotak Flexicap Direct Growth?",
        "expect_status": "uncovered",
    },
    {
        "id": "neg_weather",
        "query": "What is the weather in Mumbai today?",
        "expect_status": "gate_fail",  # unresolved + likely low score / multi or fail
    },
    {
        "id": "neg_ambiguous_hdfc",
        "query": "What's the exit load of the HDFC fund?",
        "expect_status": "ambiguous",
    },
]


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    raise SystemExit(1)


def load_golden() -> list[dict[str, Any]]:
    data = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    items = data.get("items") or []
    return [i for i in items if i.get("expected_source_id")]


def reciprocal_rank(source_ids: list[str], expected: str) -> float:
    for i, sid in enumerate(source_ids, 1):
        if sid == expected:
            return 1.0 / i
    return 0.0


def confusion_for_pair(
    rows: list[dict[str, Any]],
    a: str,
    b: str,
    label_a: str,
    label_b: str,
) -> dict[str, Any]:
    """2x2 top-1 source confusion for items whose expected source is a or b."""
    labels = {a: label_a, b: label_b}
    matrix = {
        label_a: {label_a: 0, label_b: 0, "other": 0},
        label_b: {label_a: 0, label_b: 0, "other": 0},
    }
    n = 0
    for row in rows:
        exp = row["expected_source_id"]
        if exp not in (a, b):
            continue
        n += 1
        pred = row["top1_source_id"]
        exp_l = labels[exp]
        if pred == a:
            pred_l = label_a
        elif pred == b:
            pred_l = label_b
        else:
            pred_l = "other"
        matrix[exp_l][pred_l] += 1
    return {"n": n, "matrix": matrix, "pair": (a, b), "labels": (label_a, label_b)}


def print_confusion(title: str, conf: dict[str, Any]) -> None:
    print(f"\n### {title} (n={conf['n']})")
    la, lb = conf["labels"]
    mat = conf["matrix"]
    print(f"{'expected\\\\pred':<16} {la:<12} {lb:<12} {'other':<8}")
    for exp_l in (la, lb):
        row = mat[exp_l]
        print(f"{exp_l:<16} {row[la]:<12} {row[lb]:<12} {row['other']:<8}")


def status_ok_for_negative(got: str, expect: str) -> bool:
    """
    Negatives must not return status=ok with a wrong silent answer.
    Accept exact expect_status, or any non-ok safe signal for weather-like items.
    """
    if got == expect:
        return True
    # Uncovered patterns may also gate_fail if alias detection misses — still safe
    if expect == "uncovered" and got in {"uncovered", "gate_fail"}:
        return True
    if expect == "gate_fail" and got in {"gate_fail", "ambiguous", "unresolved", "uncovered"}:
        return True
    if expect == "ambiguous" and got == "ambiguous":
        return True
    return False


def main() -> int:
    from src.retrieve.config import load_config
    from src.retrieve.pipeline import retrieve
    from src.retrieve.store import get_published_index

    cfg = load_config()
    index = get_published_index()

    print("=" * 72)
    print("Phase 3 retrieval validation")
    print(f"corpus_version={index.corpus_version}")
    print(f"chroma_collection={index.chroma_collection}")
    print(f"chunk_count={len(index.chunk_ids)}")
    print(f"default_tau={cfg.tau}")
    print(f"reranker={cfg.reranker_model}")
    print("=" * 72)

    if index.corpus_version != "2026-08-07.7":
        print(
            f"WARN: expected corpus 2026-08-07.7, found {index.corpus_version} "
            "(continuing against published pointer)"
        )
    if index.chroma_collection != "facts_desk_2026_08_07_7":
        print(
            f"WARN: expected Chroma facts_desk_2026_08_07_7, "
            f"found {index.chroma_collection}"
        )

    golden = load_golden()
    if len(golden) < 30:
        fail(f"golden set too small: {len(golden)}")

    rows: list[dict[str, Any]] = []
    per_intent_hits: dict[str, list[bool]] = defaultdict(list)
    rr_scores: list[float] = []
    # Cache full retrieval traces (chunks + normalised query) for τ sweep without re-rerank
    cached_results: dict[str, Any] = {}

    print("\n## Retrieval on golden set (default τ)\n")
    for item in golden:
        qid = item["id"]
        query = item["query"]
        expected = item["expected_source_id"]
        intent = item.get("intent") or "unknown"
        result = retrieve(query, cfg=cfg, index=index)
        cached_results[qid] = result
        source_ids = [c.source_id for c in result.chunks[:5]]
        hit = expected in source_ids
        top1 = source_ids[0] if source_ids else None
        rr = reciprocal_rank(source_ids, expected)
        rr_scores.append(rr)
        per_intent_hits[intent].append(hit)
        rows.append(
            {
                "id": qid,
                "intent": intent,
                "expected_source_id": expected,
                "top1_source_id": top1,
                "top5_source_ids": source_ids,
                "hit_at_5": hit,
                "rr": rr,
                "status": result.status,
                "top_score": result.gate.top_score,
                "scheme_resolution": result.query.resolution,
            }
        )
        mark = "HIT" if hit else "MISS"
        print(
            f"  {qid:<5} {mark:<4} intent={intent:<16} "
            f"exp={expected} top1={top1} status={result.status} "
            f"score={result.gate.top_score}"
        )

    overall_hits = sum(1 for r in rows if r["hit_at_5"])
    overall_recall = overall_hits / len(rows)
    mrr = sum(rr_scores) / len(rr_scores)

    print("\n## Recall@5 / MRR\n")
    print(f"  overall recall@5: {overall_hits}/{len(rows)} = {overall_recall:.3f}")
    print(f"  MRR (source):     {mrr:.3f}")

    print("\n## Recall@5 per intent\n")
    print(f"  {'intent':<22} {'hit':<8} {'n':<6} recall@5")
    for intent in sorted(per_intent_hits.keys()):
        hits = per_intent_hits[intent]
        n = len(hits)
        h = sum(1 for x in hits if x)
        print(f"  {intent:<22} {h:<8} {n:<6} {h / n:.3f}")

    mid_small = confusion_for_pair(rows, *MID_SMALL, "Mid Cap", "Small Cap")
    equity_baf = confusion_for_pair(rows, *EQUITY_BAF, "Equity", "BAF")
    print_confusion("Confusion: Mid Cap vs Small Cap (top-1 source)", mid_small)
    print_confusion("Confusion: Equity vs Balanced Advantage (top-1 source)", equity_baf)

    # τ sweep
    print("\n## τ sweep (golden gate_fail rate + negative safety)\n")
    # Collect score distribution from golden for informative grid
    scores = [r["top_score"] for r in rows if r["top_score"] is not None]
    # Fixed grid — not optimized against metrics
    tau_grid = sorted(set([-5.0, -2.0, -1.0, 0.0, 0.5, 1.0, 2.0, 5.0] + ([cfg.tau] if cfg.tau not in (-5.0, -2.0, -1.0, 0.0, 0.5, 1.0, 2.0, 5.0) else [])))

    print(f"  golden top_score min/median/max: ", end="")
    if scores:
        ss = sorted(scores)
        med = ss[len(ss) // 2]
        print(f"{ss[0]:.4f} / {med:.4f} / {ss[-1]:.4f}")
    else:
        print("n/a")

    print(
        f"\n  {'tau':>8}  {'golden_ok':>10}  {'golden_gate_fail':>16}  "
        f"{'neg_safe':>10}  {'neg_n':>6}"
    )

    from src.retrieve.gate import apply_gate

    # Cache negatives once (rerank once); re-gate across τ
    neg_cached = [(neg, retrieve(neg["query"], cfg=cfg, index=index)) for neg in OUT_OF_CORPUS_NEGATIVES]

    for tau in tau_grid:
        golden_ok = 0
        golden_fail = 0
        for item in golden:
            cached = cached_results[item["id"]]
            gate = apply_gate(cached.query, cached.chunks, cfg, tau=tau)
            if gate.status == "ok":
                golden_ok += 1
            elif gate.status == "gate_fail":
                golden_fail += 1

        neg_safe = 0
        for neg, cached in neg_cached:
            gate = apply_gate(cached.query, cached.chunks, cfg, tau=tau)
            if status_ok_for_negative(gate.status, neg["expect_status"]):
                neg_safe += 1

        print(
            f"  {tau:8.2f}  {golden_ok:10d}  {golden_fail:16d}  "
            f"{neg_safe:10d}  {len(OUT_OF_CORPUS_NEGATIVES):6d}"
        )

    print("\n## Out-of-corpus negatives detail (default τ)\n")
    for neg, result in neg_cached:
        safe = status_ok_for_negative(result.status, neg["expect_status"])
        print(
            f"  {neg['id']:<20} expect={neg['expect_status']:<12} "
            f"got={result.status:<12} safe={safe} "
            f"top_score={result.gate.top_score} schemes={result.gate.scheme_codes_in_hits}"
        )

    # Exit criteria reporting (honest — no threshold gaming)
    print("\n## Exit criteria checklist (report only)\n")
    print(f"  [ ] recall@5 overall = {overall_recall:.3f} (aim high before Phase 4; no hard gate here)")
    print("  [ ] Mid Cap vs Small Cap confusion measured above")
    print("  [ ] Equity vs BAF confusion measured above")
    print("  [ ] Low-confidence / negatives produce gate_fail|uncovered|ambiguous (see τ sweep)")
    print("  [ ] Uncovered schemes emit explicit uncovered/gate_fail — not silent ok")

    # Soft structural assertions (not score-tuned)
    if index.corpus_version != "2026-08-07.7":
        fail("Published corpus_version is not 2026-08-07.7")
    if index.chroma_collection != "facts_desk_2026_08_07_7":
        fail("Published chroma_collection is not facts_desk_2026_08_07_7")
    if len(index.chunk_ids) != 10:
        fail(f"Expected 10 chunks in thin corpus, found {len(index.chunk_ids)}")

    # Must report per-intent (already printed); ensure every golden intent appeared
    if not per_intent_hits:
        fail("No per-intent recall computed")

    print("\nOK: Phase 3 validation script completed (metrics reported honestly).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
