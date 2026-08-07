# Phase 2 — Ingestion notes

## What was built

| Module | Role |
|---|---|
| `src/ingest/fetcher.py` | Allow-listed HTML GET only; rejects PDF / non-HTML |
| `src/ingest/parser.py` | Parses Groww `__NEXT_DATA__.mfServerSideData` + HTML sections |
| `src/ingest/chunker.py` | Section chunks with breadcrumbs + metadata |
| `src/ingest/diffing.py` | Attribute snapshots + numeric-diff **logging** (approval UI = Phase 6) |
| `src/ingest/embedder.py` | `BAAI/bge-large-en-v1.5` (local) |
| `src/ingest/indexes.py` | Chroma DB local + BM25 + chunk store |
| `src/ingest/pipeline.py` | Orchestration + atomic publish pointer |
| `src/ingest/scheduler.py` | APScheduler cron `15 9 * * *` `Asia/Kolkata` |
| `src/ingest/cli.py` | `run` / `schedule` / `smoke` |

## Change detection

`content_hash` is computed from **stable fund fields** inside `__NEXT_DATA__` (expense ratio, exit load, SIP mins, AUM, etc.), not the full HTML body — Groww pages include volatile Cloudflare/build noise.

## Defect fixes (2026-08-07.6)

### Why the â/Ã/¹ assertion did not fire on `.5`

The in-memory / correctly UTF-8-decoded chunk text contained **U+20B9 (₹)**, not the Latin-1 mojibake characters â/Ã/¹.  
UTF-8 bytes of ₹ are `E2 82 B9`. Opening that file as **cp1252** *displays* `â‚¹`, but the Unicode string never contained those codepoints — so the assertion had nothing to match.

### Root-cause fix

- Rupee built via `"\u20b9"` (not a source-file literal).
- `chunks.jsonl` written with **`ensure_ascii=True`** so on disk you see `\u20b9`, never raw multi-byte UTF-8 that cp1252 viewers garble.
- Round-trip check rejects raw `\xe2\x82\xb9` bytes and mojibake sequences.
- Mojibake guard expanded to include `‚` (U+201A) and the full `â‚¹` sequence.

### Exclusions

Holdings **and** “Compare similar funds” / similar-funds headings are dropped at parse + chunk (comparison is refusable).
