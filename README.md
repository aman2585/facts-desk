# Facts Desk — Mutual Fund FAQ Assistant

**Facts-only. No investment advice.**

A facts-only RAG assistant that answers objective questions about **five fixed HDFC Direct Growth schemes** using **only five allow-listed Groww HTML scheme pages**. No PDFs. No advice. No performance figures inline.

| | |
|---|---|
| Product docs | [`problemStatement.md`](problemStatement.md) · [`PRD.md`](PRD.md) |
| Architecture | [`docs/RAG_Architecture.md`](docs/RAG_Architecture.md) |
| Implementation plan | [`implementationplan.md`](implementationplan.md) |
| Intent taxonomy | [`docs/INTENT_TAXONOMY.md`](docs/INTENT_TAXONOMY.md) |
| Current phase | **Phase 3** — hybrid retrieval (Chroma + BM25) |
| Published corpus | `2026-08-07.7` · Chroma `facts_desk_2026_08_07_7` |

---

## Disclaimer

> **Facts-only. No investment advice.** This assistant answers objective questions about five selected HDFC Direct Growth mutual fund schemes using information retrieved from the corresponding Groww scheme pages (HTML only; no PDFs). It does not provide investment advice, recommendations, suitability assessments, performance comparisons or return projections. Information may not reflect the most recent changes; always verify against the linked Groww scheme page. Mutual fund investments are subject to market risks; read all scheme related documents carefully.

---

## Covered schemes (exhaustive)

| ID | Scheme | URL |
|---|---|---|
| `src_001` | HDFC Mid Cap Fund Direct Growth | https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth |
| `src_002` | HDFC Equity Fund Direct Growth | https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth |

> **Note (`src_002`):** Groww currently displays this page as **“HDFC Flexi Cap Direct Plan Growth”** (product rename). Facts Desk keeps allow-listed URL slug `hdfc-equity-fund-direct-growth`, `scheme_code` `hdfc_equity_direct_growth`, and corpus `display_name` “HDFC Equity Fund Direct Growth”. Treat “Flexi Cap” as a display alias for Equity — do not change the URL or `scheme_code`.
| `src_003` | HDFC Small Cap Fund Direct Growth | https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth |
| `src_004` | HDFC Nifty 50 Index Fund Direct Growth | https://groww.in/mutual-funds/hdfc-nifty-50-index-fund-direct-growth |
| `src_005` | HDFC Balanced Advantage Fund Direct Growth | https://groww.in/mutual-funds/hdfc-balanced-advantage-fund-direct-growth |

Registry: [`corpus/corpus.yaml`](corpus/corpus.yaml)  
Aliases: [`corpus/scheme_aliases.yaml`](corpus/scheme_aliases.yaml)

---

## Locked stack (v1)

| Layer | Choice |
|---|---|
| Embeddings | `BAAI/bge-large-en-v1.5` |
| Vector store | Chroma DB (local) |
| Ingestion schedule | Daily **09:15 AM IST** (`Asia/Kolkata`) |
| Sources | HTML only — **no PDFs** |

---

## Repository layout

```
corpus/           # allow-list + scheme aliases
docs/             # architecture, taxonomy
eval/
  golden/         # factual Q&A stubs (≥30; target ≥150)
  adversarial/    # refusal stubs (≥20; target ≥100)
src/
  ingest/         # Phase 2+
  retrieve/       # Phase 3+
  generate/       # Phase 4+
  safety/         # Phase 4+
  api/            # Phase 5+
  admin/          # Phase 6+
ui/               # Phase 5+
scripts/          # validation helpers
data/             # local Chroma / caches (gitignored)
```

---

## Setup

```bash
python -m pip install -r requirements.txt
python scripts/validate_phase1.py
```

### Phase 2 — Ingestion

```bash
# One-shot ingest (fetch 5 Groww pages → chunk → BGE embed → Chroma + BM25)
python -m src.ingest.cli run

# Force re-parse even if content hash unchanged
python -m src.ingest.cli run --force

# Smoke-test BM25 + Chroma against published index
python -m src.ingest.cli smoke

# Block and run daily at 09:15 Asia/Kolkata
python -m src.ingest.cli schedule
```

### Phase 3 — Hybrid retrieval

```bash
# Smoke a single query against published index (2026-08-07.7)
python -m src.retrieve.cli "What is the expense ratio of HDFC Mid Cap Fund Direct Growth?"

# Offline eval: recall@5 (overall + per intent), confusion matrices, τ sweep
python scripts/validate_phase3.py
```

Config (including confidence gate `tau`): [`src/retrieve/config.yaml`](src/retrieve/config.yaml)

Published pointer: `data/published/current.json`  
Chroma path: `data/chroma/`  
Chunk/BM25 staging: `data/staging/<corpus_version>/`  
Ingest logs: `data/logs/`

---

## Evaluation stubs

| Suite | Path | Phase 1 count | Final target |
|---|---|---|---|
| Golden factual | `eval/golden/items.json` | 32 | ≥150 |
| Adversarial refusal | `eval/adversarial/items.json` | 22 | ≥100 |

Golden `verified_answer` values are **stubs** (`verification_status: stub_pending_page_verify`) until human verification against live Groww pages (attributes are now available in `data/staging/*/attributes/`).

---

## Response contract (preview)

```
<Fact statement, ≤3 sentences, no hedging, no advice>

[Source: Groww — <Scheme Name>](<allow-listed url>)
Last updated from sources: <DD Mon YYYY>
```

---

## Known limitations (v1)

- Five schemes only; English only
- HTML-only corpus — no SID / KIM / factsheet PDFs
- No performance figures inline; no personalisation; no account data
- Attributes missing from the Groww page → “not in my sources”
- Educational refusal links (SEBI/AMFI) are not ingested
- Change detection hashes stable `__NEXT_DATA__` fund fields **plus** `PARSER_CHUNKER_VERSION` (not volatile full HTML); bump the version constant after parser/chunker logic changes and re-ingest with `--force`
- `src_002` Groww display name may say Flexi Cap; corpus identity remains Equity (`scheme_code` / URL unchanged)

---

## How to run (phases)

| Phase | Capability | Status |
|---|---|---|
| 1 | Foundation & corpus freeze | **Done** |
| 2 | Ingestion + scheduler 09:15 IST | **Done** |
| 3 | Hybrid retrieval (Chroma + BM25) | **Done** (eval via `scripts/validate_phase3.py`) |
| 4 | Generation + refusal + PII | TBD |
| 5 | API + minimal UI + audit | TBD |
| 6 | Ops hardening + launch gates | TBD |

See [`implementationplan.md`](implementationplan.md) for exit criteria per phase.

---

## Incident response (placeholder)

Kill switch, rollback, and escalation contacts will be wired in Phase 6. Until then, do not deploy externally.
