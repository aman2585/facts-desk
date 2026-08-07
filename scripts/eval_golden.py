#!/usr/bin/env python3
"""Golden-set eval: factual accuracy + citation presence (Phase 4)."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.generate.config import load_config
from src.generate.pipeline import AskResult, ask
from src.generate.validator import extract_urls, load_allowlisted_urls

SOURCE_URL_TO_ID = {
    "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth": "src_001",
    "https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth": "src_002",
    "https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth": "src_003",
    "https://groww.in/mutual-funds/hdfc-nifty-50-index-fund-direct-growth": "src_004",
    "https://groww.in/mutual-funds/hdfc-balanced-advantage-fund-direct-growth": "src_005",
}


def _norm(s: str) -> str:
    t = (s or "").lower().replace("\r", " ").replace("\n", " ")
    t = t.replace("₹", "").replace(",", "")
    t = re.sub(r"\s+", " ", t).strip()
    return t


def answer_matches(verified: str, response_text: str, display: str) -> bool:
    """True if verified_answer appears in the assembled response (substring, normalised)."""
    needle = _norm(verified)
    hay = _norm(response_text + " " + display)
    if not needle:
        return False
    if needle in hay:
        return True
    needle2 = needle.strip(" .")
    return bool(needle2) and needle2 in hay


def eval_bucket(result: AskResult) -> str:
    """answered | refused | grounded-fail | api-error"""
    rtype = result.response.response_type
    path = (result.audit or {}).get("path")
    if rtype == "api_error" or path == "api_error":
        return "api-error"
    if rtype == "answer":
        return "answered"
    if rtype in {"refusal", "clarify", "performance", "pii_warn"}:
        return "refused"
    # coverage / other
    if path == "generate" and result.generation and result.generation.used_fallback:
        return "grounded-fail"
    if path == "generate":
        # unexpected non-answer without fallback flag
        return "grounded-fail"
    # safety uncovered / retrieval short-circuit
    return "refused"


def evaluate_item(item: dict) -> dict:
    result = ask(item["query"])
    display = result.response.display
    text = result.response.text
    urls = extract_urls(display) or (
        [result.response.citation_url] if result.response.citation_url else []
    )
    urls = [u.rstrip("/") for u in urls if u]
    allow = load_allowlisted_urls()
    citation_ok = len(urls) >= 1 and all(u in allow for u in urls)
    source_id = SOURCE_URL_TO_ID.get(urls[0], None) if urls else None
    source_ok = source_id == item.get("expected_source_id")
    bucket = eval_bucket(result)
    is_answer = bucket == "answered"
    accuracy_ok = bool(is_answer and answer_matches(item["verified_answer"], text, display))

    return {
        "id": item["id"],
        "intent_class": result.intent.intent,
        "response_type": result.response.response_type,
        "eval_bucket": bucket,
        "accuracy_ok": accuracy_ok,
        "citation_ok": citation_ok and is_answer,
        "source_ok": source_ok and is_answer,
        "expected_source_id": item.get("expected_source_id"),
        "got_source_id": source_id,
        "used_fallback": bool(result.generation and result.generation.used_fallback),
        "model_version": result.model_version,
        "status_code": (result.audit or {}).get("status_code"),
        "display_preview": display[:240],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Eval golden factual accuracy + citations")
    parser.add_argument(
        "--path",
        type=Path,
        default=ROOT / "eval" / "golden" / "items.json",
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--json-out", type=Path, default=None)
    parser.add_argument(
        "--delay",
        type=float,
        default=None,
        help="Seconds between queries (default: config eval_query_delay_s)",
    )
    parser.add_argument("-q", "--quiet", action="store_true")
    args = parser.parse_args(argv)

    cfg = load_config()
    delay = cfg.eval_query_delay_s if args.delay is None else float(args.delay)

    data = json.loads(args.path.read_text(encoding="utf-8"))
    items = data["items"]
    if args.limit is not None:
        items = items[: args.limit]

    rows: list[dict] = []
    for i, item in enumerate(items):
        if i > 0 and delay > 0:
            time.sleep(delay)
        try:
            row = evaluate_item(item)
        except Exception as exc:  # noqa: BLE001 — unexpected only; API errors are cards
            row = {
                "id": item["id"],
                "error": str(exc),
                "eval_bucket": "api-error",
                "response_type": "error",
                "accuracy_ok": False,
                "citation_ok": False,
                "source_ok": False,
            }
        rows.append(row)
        if not args.quiet:
            bucket = row.get("eval_bucket")
            if row.get("error"):
                print(f"{row['id']}: api-error ERR={row['error']}")
            else:
                flags = [
                    "ACC" if row["accuracy_ok"] else "acc_fail",
                    "CIT" if row["citation_ok"] else "cit_fail",
                ]
                print(
                    f"{row['id']}: bucket={bucket} {', '.join(flags)} "
                    f"type={row.get('response_type')}"
                )

    n = len(rows)
    buckets = {
        "answered": sum(1 for r in rows if r.get("eval_bucket") == "answered"),
        "refused": sum(1 for r in rows if r.get("eval_bucket") == "refused"),
        "grounded-fail": sum(1 for r in rows if r.get("eval_bucket") == "grounded-fail"),
        "api-error": sum(1 for r in rows if r.get("eval_bucket") == "api-error"),
    }
    answered = [r for r in rows if r.get("eval_bucket") == "answered"]
    scorable = [r for r in rows if r.get("eval_bucket") != "api-error"]
    n_acc = sum(1 for r in rows if r.get("accuracy_ok"))
    n_cit = sum(1 for r in answered if r.get("citation_ok"))
    cit_denom = max(1, len(answered))
    score_denom = max(1, len(scorable))

    summary = {
        "n": n,
        "buckets": buckets,
        "answered": buckets["answered"],
        "refused": buckets["refused"],
        "grounded_fail": buckets["grounded-fail"],
        "api_error": buckets["api-error"],
        "accuracy_excluding_api_error": n_acc / score_denom,
        "accuracy_count": f"{n_acc}/{len(scorable)}",
        "citation_on_answered": n_cit / cit_denom,
        "citation_count": f"{n_cit}/{len(answered)}",
        "eval_query_delay_s": delay,
        "model_version": next(
            (r.get("model_version") for r in rows if r.get("model_version")), None
        ),
    }
    print(
        f"SUMMARY buckets answered={buckets['answered']} refused={buckets['refused']} "
        f"grounded-fail={buckets['grounded-fail']} api-error={buckets['api-error']}"
    )
    print(
        f"SUMMARY accuracy(excl api-error)={summary['accuracy_count']} "
        f"({summary['accuracy_excluding_api_error']:.3f}) "
        f"citation_on_answered={summary['citation_count']} "
        f"({summary['citation_on_answered']:.3f})"
    )

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps({"summary": summary, "rows": rows}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    if buckets["api-error"] > 0:
        print(
            f"WARN: {buckets['api-error']} api-error item(s) — do not treat as coverage gaps."
        )
        return 2
    if args.limit is None and summary["accuracy_excluding_api_error"] < 0.90:
        return 1
    if answered and summary["citation_on_answered"] < 1.0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
