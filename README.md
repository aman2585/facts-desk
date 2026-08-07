# Facts Desk

A facts-only FAQ assistant for mutual fund schemes, built as a Retrieval-Augmented Generation (RAG) system over a fixed, allow-listed corpus of five Groww scheme pages.

**Facts-only. No investment advice.**

The assistant answers objective, verifiable questions about five HDFC Direct Growth schemes — expense ratio, exit load, minimum SIP, riskometer, benchmark, category, lock-in — and refuses everything else. Every answer carries exactly one citation to an allow-listed source URL and a freshness footer showing when that source was last fetched.

Refusal is treated as a first-class product feature, not a failure mode. Advisory, comparative, predictive, performance and account-specific queries are declined with a pointer to SEBI/AMFI investor education material.

---

## Corpus

Exactly five URLs are ingested. Nothing outside this allow-list is ever fetched or cited.

| ID | Scheme | URL |
|---|---|---|
| `src_001` | HDFC Mid Cap Fund Direct Growth | https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth |
| `src_002` | HDFC Equity Fund Direct Growth | https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth |
| `src_003` | HDFC Small Cap Fund Direct Growth | https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth |
| `src_004` | HDFC Nifty 50 Index Fund Direct Growth | https://groww.in/mutual-funds/hdfc-nifty-50-index-fund-direct-growth |
| `src_005` | HDFC Balanced Advantage Fund Direct Growth | https://groww.in/mutual-funds/hdfc-balanced-advantage-fund-direct-growth |

**HTML only.** No SID, KIM, or factsheet PDFs are ingested; there is no PDF code path in the repository. No open-web crawl, no third-party aggregators.

Note on `src_002`: Groww displays this scheme as "HDFC Flexi Cap Direct Plan Growth" following an AMC rename. The allow-listed URL and internal `scheme_code` are unchanged; only the display name differs.

---

## Architecture

```
INGEST      fetch (allow-list only) → parse __NEXT_DATA__ + HTML sections
            → chunk (350 word cap) → embed → stage → atomic pointer flip

RETRIEVE    normalise (abbreviations + scheme aliases)
            → uncovered / ambiguous short-circuit
            → metadata pre-filter (scheme_code + plan=Direct)
            → hybrid: Chroma dense ∪ BM25
            → cross-encoder rerank → confidence gate

GENERATE    redact PII → classify intent (10 classes)
            → refuse | retrieve → generate → validate → verify groundedness
            → assemble card

SERVE       POST /ask (SSE) → cache → audit → typed card → UI
```

| Layer | Choice |
|---|---|
| Embeddings | `BAAI/bge-large-en-v1.5` (local) |
| Vector store | Chroma DB, local persistent |
| Lexical | BM25 |
| Reranker | `BAAI/bge-reranker-base` |
| Generator | Groq `llama-3.1-8b-instant`, temperature 0 |
| API | FastAPI, SSE streaming |

### Scheduler and change detection

Ingestion runs on a daily cron at **09:15 IST** (`15 9 * * *`, timezone `Asia/Kolkata`) via an APScheduler blocking process, with a manual trigger available at any time.

Change detection hashes a stable subset of each page's structured fund fields rather than the raw HTML, which is too volatile to compare directly. Sources whose hash is unchanged skip re-parsing and re-embedding. The hash envelope includes a parser/chunker version string, so changes to ingest logic invalidate the skip and force a rebuild.

On fetch failure the previous chunks for that source are reused and the published pointer is not flipped — a partial index is never published.

Numeric changes to attributes such as TER, exit load and minimum SIP are diffed against the last published values and logged. A human approval gate on those diffs is specified for Phase 6 and is not yet built.

### Safety layers

Answers pass three independent checks before reaching a user:

1. **Deterministic validator** — at most 3 sentences, exactly one allow-listed citation, every number in the answer present verbatim in the cited chunk, no advisory-lexicon phrases. Failure triggers one regeneration, then a safe fallback.
2. **Groundedness verifier** — claims must be supported by the *cited* chunk, checked on numbers and lexical overlap.
3. **Intent classifier** — ten classes routed before retrieval, so advisory and out-of-scope queries never reach the model.

Sections that would enable refusable behaviour are excluded at ingest time rather than filtered later: holdings tables, "compare similar funds", and all performance/returns sections. Return figures cannot leak because they are never indexed.

### Response cards

The API returns a discriminated union; the UI switches on `type` and never parses prose.

| `type` | Fields |
|---|---|
| `answer` | `text`, `citation_url`, `source_label`, `freshness_date` |
| `refusal` | `text`, `educational_url` (may be null) |
| `coverage` | `text`, optional citation |
| `performance_redirect` | `text`, `scheme_url` |
| `clarify` | `text`, `options[]` |
| `api_error` | `text`, `status_code` |

---

## Setup

Requires Python 3.11+ and a [Groq](https://console.groq.com) API key.

```bash
python -m pip install -r requirements.txt
export GROQ_API_KEY="your-key"        # PowerShell: $env:GROQ_API_KEY="your-key"
```

First run downloads the embedding and reranker models (~2.3 GB).

### Ingest

```bash
python -m src.ingest.cli run              # one-shot ingest
python -m src.ingest.cli run --force      # re-parse even if content unchanged
python -m src.ingest.cli smoke            # BM25 + Chroma smoke test
python -m src.ingest.cli schedule         # blocking daily cron at 09:15 IST
```

Published pointer: `data/published/current.json`

### Ask (CLI)

```bash
python -m src.generate.cli "What is the expense ratio of HDFC Mid Cap Fund?"
python -m src.generate.cli --json "..."   # full audit trace
```

### Run the app

```bash
python -m src.api.cli --host 127.0.0.1 --port 8000   # API
python ui/serve.py                                    # UI on :5173
```

### Evaluate

```bash
python scripts/validate_phase1.py                    # corpus + eval set integrity
python scripts/validate_phase3.py                    # retrieval eval, no LLM
python scripts/validate_phase4_part1.py              # safety fixtures, no LLM
python scripts/eval_golden.py --json-out data/logs/golden_eval.json
python scripts/eval_adversarial.py
python -m unittest tests.test_scheme_aliases tests.test_labelled_attrs -v
```

---

## Evaluation

Golden set: 32 factual queries, human-verified against live Groww pages on 2026-08-07.
Adversarial set: 42 prompts spanning advisory, comparative, predictive, calculation, PII, out-of-domain, and compound factual+advisory phrasings.

| Metric | Result | Gate |
|---|---|---|
| Golden factual accuracy | **31/32 (0.969)** | ≥ 0.90 |
| Citation allow-listed on answered items | **31/31 (1.000)** | 1.000 |
| Adversarial refusal recall | **42/42 (1.000)** | ≥ 0.95 |
| Advisory / scope leaks | **0** | 0 |
| API errors on exit run | **0** | 0 |

Eval buckets separate `answered`, `refused`, `grounded-fail` and `api-error`, so an upstream HTTP failure can never be silently counted as a coverage gap. Accuracy excludes `api-error` from the denominator.

### On the retrieval numbers

`recall@5` on this corpus reads 1.000, and that figure should not be trusted as evidence of retrieval quality. The published index holds 10 chunks; top-5 returns half the corpus, and once the scheme pre-filter resolves, the candidate pool is 2 chunks. The more honest measure is **recall@1 with the metadata filter disabled: 0.844**, with all five misses concentrated on `src_002`.

Because most answerable attributes live in a single Investment-details chunk per scheme, retrieval cannot isolate "the exit-load fact" from "the expense-ratio fact". Fact-level accuracy is therefore measured at generation time on the golden set, not inferred from retrieval recall.

---

## Known limitations

**Corpus and coverage**

- Five HDFC Direct Growth schemes only. Any other scheme, plan, or AMC returns a coverage refusal.
- ~2 chunks per scheme after holdings, comparison and performance exclusions. Parser coverage of remaining page headings has not been fully audited.
- Performance figures, returns and NAV history are deliberately never indexed.

**Retrieval**

- The confidence threshold `tau` is set to `0.0` and does not gate. Out-of-corpus safety currently depends on the alias/uncovered resolver rather than the score gate. Forced past that resolver, out-of-corpus queries can score ~0.72–0.78 — high enough to pass any usable threshold. An *unrecognised* scheme name (not in the uncovered pattern list) remains a residual silent-failure path.
- `tau` is deliberately left untuned until the corpus grows; tuning it against a 32-item eval would overfit.

**Generation**

- `g002` (Equity TER) is the one remaining golden miss, failing on groundedness.
- Groundedness overlap is a weak signal on very short answers — a one-sentence reply can pass on a five-token overlap.
- Abbreviation expansion reaches retrieval but not the generation prompt, so a query using "TER" can produce a hedged answer that mentions internal machinery. Fix identified, not yet applied.
- Icon glyphs in the UI can render as literal text if the icon font fails to load.

**Operations**

- Atomic publish is incomplete: staging versions and old Chroma collections accumulate, and crash consistency is untested.
- The embedding model revision is not pinned to a commit.
- The scheduler cron is configured and the CLI works, but it has never been observed firing at a real 09:15 IST tick.
- Fail-soft fetch behaviour is coded but not chaos-tested.
- Numeric diffs are logged without a human approval gate, so a changed figure can publish silently.
- Groq free-tier rate limits constrain evaluation throughput; retries, backoff and an inter-query delay keep runs honest.

Kill switch, admin console, numeric approval queue, dead-link monitoring and CI gates are specified in the implementation plan as Phase 6 and are not built.

---

## Privacy

PAN, Aadhaar, folio numbers, OTPs, email addresses and phone numbers are redacted at the edge before any model call or persistence. Queries carrying PII are refused rather than answered. Verified: no raw PII appears anywhere under `data/`.

Sessions are anonymous — a session id only, with no login or account linkage.

Every response is written to an append-only audit log containing the redacted query, intent, retrieved chunk ids, corpus version, response card, citation, validator verdicts, groundedness result, model version and timestamp — enough to reconstruct why any given answer was produced.

---

## Project documentation

| Document | Contents |
|---|---|
| `problemStatement.md` | Original brief and constraints |
| `PRD.md` | Product requirements |
| `docs/RAG_Architecture.md` | System architecture |
| `implementationplan.md` | Six-phase plan with exit criteria |
| `docs/PHASE2_HANDOFF.md` | Ingestion — what passed, what didn't |
| `docs/PHASE3_HANDOFF.md` | Retrieval — with an honest reading of the metrics |
| `docs/PHASE4_HANDOFF.md` | Generation, validation and safety |
| `docs/PHASE5_HANDOFF.md` | API, cache and audit |
| `docs/INTENT_TAXONOMY.md` | Answerable vs refusable intent contract |

Each handoff records exit criteria as pass/fail with evidence, plus carried-forward defects. Where a number looked good for the wrong reason, that is stated rather than smoothed over.

---

## Disclaimer

> **Facts-only. No investment advice.**

This assistant reports published scheme attributes from five Groww pages. It does not provide investment advice, recommendations, comparisons, or performance figures, and it is not a substitute for a SEBI-registered investment adviser. Always verify figures against the linked source page before acting on them.
