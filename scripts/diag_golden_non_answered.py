#!/usr/bin/env python3
"""Report golden non-answers: card type + groundedness_first overlap/missing tokens."""
from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Optional local .env (KEY=VALUE lines) — does not modify repo defaults
_env = ROOT / ".env"
if _env.exists():
    for line in _env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

import src.generate.generator as gen_mod
from src.generate.groundedness import _content_tokens, verify_groundedness
from src.generate.pipeline import ask
from src.generate.validator import extract_urls
from src.safety.refusals import should_short_circuit

_real_verify = verify_groundedness
_capture: list[tuple[str, str, dict]] = []


def _capturing_verify(answer: str, cited_chunk_text: str):
    result = _real_verify(answer, cited_chunk_text)
    _capture.append((answer, cited_chunk_text or "", result.as_dict()))
    return result


gen_mod.verify_groundedness = _capturing_verify  # type: ignore[attr-defined]


def _missing_tokens(answer: str, cited: str) -> list[str]:
    urls = extract_urls(answer)
    body = answer or ""
    for u in urls:
        body = body.replace(u, " ")
    body = re.sub(r"\s+", " ", body).strip()
    tokens = _content_tokens(body)
    cl = (cited or "").lower()
    return [t for t in tokens if t not in cl]


def main() -> None:
    data = json.loads((ROOT / "eval" / "golden" / "items.json").read_text(encoding="utf-8"))
    rows = []
    for item in data["items"]:
        _capture.clear()
        try:
            result = ask(item["query"])
        except Exception as exc:  # noqa: BLE001
            rows.append(
                {
                    "id": item["id"],
                    "golden_intent": item["intent"],
                    "response_type": "error",
                    "error": str(exc),
                    "overlap_ratio": None,
                    "missing_tokens": None,
                    "path": "error",
                }
            )
            print(f"{item['id']} ERROR {exc}", flush=True)
            continue

        rtype = result.response.response_type
        if rtype == "answer":
            print(f"{item['id']} ANSWER skip", flush=True)
            continue

        short = should_short_circuit(result.intent.intent)
        g1 = (result.audit or {}).get("groundedness_first") or {}
        details = g1.get("details") or {}
        missing = None
        if _capture:
            first_raw, cited, _ = _capture[0]
            missing = _missing_tokens(first_raw, cited)
        elif short:
            missing = []  # never scored

        row = {
            "id": item["id"],
            "golden_intent": item["intent"],
            "classifier_intent": result.intent.intent,
            "response_type": rtype,
            "path": "safety_short_circuit" if short else "generate",
            "overlap_ratio": details.get("overlap_ratio") if not short else None,
            "token_count": details.get("token_count") if not short else None,
            "present_count": details.get("present_count") if not short else None,
            "groundedness_first_passed": g1.get("passed") if not short else None,
            "groundedness_first_reason": g1.get("reason") if not short else "n/a_pre_generation",
            "missing_tokens": missing if not short else None,
            "classifier_reason": result.intent.reason,
        }
        rows.append(row)
        print(
            f"{item['id']} {rtype} path={row['path']} overlap={row['overlap_ratio']} "
            f"missing={row['missing_tokens']}",
            flush=True,
        )

    by_intent: dict[str, list] = defaultdict(list)
    for r in rows:
        by_intent[r["golden_intent"]].append(r)

    out = {"n_non_answered": len(rows), "by_intent": dict(sorted(by_intent.items())), "rows": rows}
    path = ROOT / "data" / "logs" / "golden_non_answered_report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    # Human-readable
    md = [f"# Golden non-answered ({len(rows)})", ""]
    for intent, group in sorted(by_intent.items()):
        md.append(f"## {intent} (n={len(group)})")
        md.append("")
        for r in group:
            md.append(
                f"- **{r['id']}** · card=`{r['response_type']}` · path=`{r['path']}` · "
                f"overlap_ratio=`{r['overlap_ratio']}` · missing_tokens=`{r['missing_tokens']}`"
            )
            if r.get("classifier_reason"):
                md.append(f"  - classifier={r['classifier_intent']} ({r['classifier_reason']})")
        md.append("")
    md_path = ROOT / "data" / "logs" / "golden_non_answered_report.md"
    md_path.write_text("\n".join(md), encoding="utf-8")
    print("WROTE", path, md_path, flush=True)


if __name__ == "__main__":
    main()
