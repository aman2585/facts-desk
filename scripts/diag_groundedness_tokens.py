#!/usr/bin/env python3
"""Diag: groundedness tokens vs cited chunk (report only)."""
from __future__ import annotations

import json
import re
from pathlib import Path

from src.generate.groundedness import _STOP, _WORD_RE, _content_tokens, verify_groundedness
from src.generate.validator import extract_numbers, extract_urls
from src.retrieve.store import get_published_index

ROOT = Path(__file__).resolve().parents[1]


def joined(ch: dict) -> str:
    parts = [ch.get("text") or ""]
    for row in ch.get("tables") or []:
        parts.append(f"{row.get('label', '')}: {row.get('value', '')}")
    return "\n".join(parts)


def analyze(answer: str, cited_text: str, label: str) -> dict:
    urls = extract_urls(answer)
    body = answer
    for u in urls:
        body = body.replace(u, " ")
    body = re.sub(r"\s+", " ", body).strip()
    raw_word_tokens = _WORD_RE.findall(body)
    content = _content_tokens(body)
    chunk_lower = (cited_text or "").lower()
    chunk_flat = (cited_text or "").replace(",", "").replace(" ", "").lower()
    membership = [{"token": t, "in_chunk_lower": t in chunk_lower} for t in content]
    g = verify_groundedness(answer, cited_text)
    return {
        "label": label,
        "body_after_url_strip": body,
        "raw_word_re_findall": raw_word_tokens,
        "content_tokens": content,
        "token_count": len(content),
        "membership": membership,
        "present_tokens": [t for t in content if t in chunk_lower],
        "present_count": sum(1 for t in content if t in chunk_lower),
        "answer_numbers": extract_numbers(body),
        "chunk_flat_has_0.75%": "0.75%" in chunk_flat,
        "chunk_lower_has_0.75%": "0.75%" in chunk_lower,
        "chunk_lower_has_75%": "75%" in chunk_lower,
        "chunk_flat_has_bare_0.75": "0.75" in chunk_flat,
        "groundedness": g.as_dict(),
        "cited_len": len(cited_text or ""),
    }


def main() -> None:
    idx = get_published_index()
    c1 = joined(idx.chunks_by_id["src_001::c_001"])
    c2 = joined(idx.chunks_by_id["src_001::c_002"])

    url = "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth"
    answers = [
        f"The expense ratio is 0.75%.\n\n{url}",
        f"The expense ratio of HDFC Mid Cap Fund Direct Growth is 0.75%.\n\n{url}",
        f"The expense ratio for the Mid Cap option is 0.75%.\n\n{url}",
        f"Expense ratio: 0.75%.\n\n{url}",
    ]

    rows = [analyze(a, c1, "vs_c001_joined") for a in answers]
    # cases that can yield present_count 0 while numbers may still pass
    rows.append(analyze(answers[1], "0.75", "vs_bare_0.75_only"))
    rows.append(analyze(answers[1], "0.75%", "vs_0.75pct_only"))
    rows.append(analyze(answers[1], "", "vs_empty"))
    rows.append(analyze(answers[1], c2, "vs_c002_only"))

    # Find any answer+cited combo with token_count==6 and present_count==0 using c1 variants
    six_zero = []
    candidates = [
        f"The expense ratio for the Mid Cap option is 0.75%.\n\n{url}",
        f"The Mid Cap plan expense ratio equals 0.75% today.\n\n{url}",
        f"Current Mid Cap TER expense ratio sits at 0.75%.\n\n{url}",
    ]
    for a in candidates:
        for cited, lab in [(c1, "c1"), ("0.75", "bare"), ("0.75%", "pct")]:
            r = analyze(a, cited, lab)
            if r["token_count"] == 6 and r["present_count"] == 0:
                six_zero.append(r)

    report = {
        "word_re_on_0.75%": _WORD_RE.findall("0.75%"),
        "word_re_pattern": _WORD_RE.pattern,
        "stop_scheme_words": sorted(
            x for x in _STOP if x in {"hdfc", "fund", "direct", "growth", "scheme", "page", "groww"}
        ),
        "normalisation": {
            "answer": [
                "1. extract_urls(answer)",
                "2. body = answer; replace each url with a space",
                "3. collapse whitespace: re.sub(r'\\s+', ' ', body).strip()",
                "4. numbers: extract_numbers(body) — separate regex, keeps decimals like 0.75%",
                "5. lexical tokens: findall([A-Za-z0-9%]+) then .lower(); drop len<3 and _STOP",
                "6. CRITICAL: '.' is outside the token charset, so '0.75%' tokenises as ['0','75%'] not ['0.75%']",
            ],
            "cited_chunk": [
                "1. cited_chunk_text as passed in (joined chunk text + 'label: value' table lines)",
                "2. numeric side: chunk_flat = chunk.replace(',','').replace(' ','').lower()",
                "3. numeric/lexical side: chunk_lower = chunk.lower() (spaces/punct kept)",
                "4. lexical test: (token in chunk_lower) substring check — chunk is NOT tokenised",
            ],
        },
        "cited_c001_exact": c1,
        "analyses": rows,
        "token_count_6_present_0": six_zero,
    }
    out = ROOT / "data" / "logs" / "diag_groundedness_tokens.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print("wrote", out)
    print("WORD_RE 0.75% =>", _WORD_RE.findall("0.75%"))
    for r in rows:
        print(
            f"{r['label']}: tokens={r['content_tokens']} present={r['present_count']} "
            f"reason={r['groundedness']['reason']}"
        )


if __name__ == "__main__":
    main()
