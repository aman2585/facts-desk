# Implementation Plan — Facts Desk (Mutual Fund FAQ Assistant)

| Field | Value |
|---|---|
| Document | Phase-by-phase implementation plan |
| Status | Ready to execute |
| Sources of truth | [`problemStatement.md`](problemStatement.md), [`PRD.md`](PRD.md), [`docs/RAG_Architecture.md`](docs/RAG_Architecture.md) |
| Scope lock | Exactly **5** Groww HTML scheme pages · **no PDFs** · Scheduler **09:15 AM IST daily** |
| Last updated | 05 August 2026 |

---

## How to use this plan

Implement **one phase at a time**. Do not start the next phase until the current phase’s **exit criteria** are met.

| Rule | Why |
|---|---|
| Eval before polish | Accuracy gates beat UI polish |
| Refusal before clever answers | Safety is a feature, not a patch |
| HTML-only forever in v1 | No SID/KIM/factsheet PDF code path |
| Allow-list only | Never fetch or cite outside the five URLs |

```
Phase 1  Foundation & corpus
   ↓
Phase 2  Ingestion + scheduler
   ↓
Phase 3  Hybrid retrieval
   ↓
Phase 4  Generation + validation + safety
   ↓
Phase 5  API + UI + audit
   ↓
Phase 6  Ops hardening + launch gates
```

---

## Scope reminder (all phases)

### Locked stack decisions (v1)

| Layer | Choice |
|---|---|
| Embedding model | **`BAAI/bge-large-en-v1.5`** (local) |
| Vector store | **Chroma DB — local persistent store** |

### Corpus (exhaustive)

| ID | Scheme | URL |
|---|---|---|
| `src_001` | HDFC Mid Cap Fund Direct Growth | https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth |
| `src_002` | HDFC Equity Fund Direct Growth | https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth |
| `src_003` | HDFC Small Cap Fund Direct Growth | https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth |
| `src_004` | HDFC Nifty 50 Index Fund Direct Growth | https://groww.in/mutual-funds/hdfc-nifty-50-index-fund-direct-growth |
| `src_005` | HDFC Balanced Advantage Fund Direct Growth | https://groww.in/mutual-funds/hdfc-balanced-advantage-fund-direct-growth |

### Explicit non-goals for this plan (v1)

- PDF ingestion · open-web crawl · multi-AMC · performance answers · advice/comparison · account/PII features · multilingual UI

---

## Phase 1 — Foundation & corpus freeze

**Goal:** Lock scope, scaffold the repo, and commit eval stubs so every later phase can be measured.

**Maps to:** Architecture M0 · PRD Phase 0 (foundation)

### Work items

1. **Repo scaffold** (per architecture §15)
   - `corpus/`, `src/{ingest,retrieve,generate,safety,api,admin}/`, `eval/{golden,adversarial}/`, `ui/`, `docs/`, `README.md`
2. **Freeze `corpus/corpus.yaml`**
   - Exactly the five URLs above
   - `format: html_only`
   - `refresh: "daily@09:15 Asia/Kolkata"`
3. **Intent taxonomy freeze**
   - Answerable vs refusable intents from PRD §9 (scoped to attributes on Groww pages only)
   - Document in `docs/` or README; treat as contractual for Compliance review
4. **Golden set stubs** (`eval/golden/`)
   - Schema: `query`, `verified_answer`, `expected_source_id`, `intent`, `verified_by`, `verified_on`
   - Seed ≥30 items across the five schemes (expand toward ≥150 by Phase 6)
   - **No** items that require PDF-only facts
5. **Adversarial refusal stubs** (`eval/adversarial/`)
   - Seed ≥20 prompts (advisory, comparative, predictive, calculation, jailbreak, PII)
   - Expand toward ≥100 by Phase 6
6. **Scheme alias map (draft)**
   - Mid Cap / Equity / Small Cap / Nifty 50 / Balanced Advantage aliases
7. **README skeleton**
   - What this is, five URLs, facts-only disclaimer, known limitations, how to run (TBD per phase)

### Deliverables

| Artefact | Location |
|---|---|
| Allow-listed corpus registry | `corpus/corpus.yaml` |
| Eval stubs | `eval/golden/`, `eval/adversarial/` |
| Taxonomy + disclaimer | README / docs |
| Empty package layout | `src/…` |

### Exit criteria

- [x] `corpus.yaml` contains **only** the five Groww URLs; no PDF sources
- [x] Taxonomy (answerable / refusable) written and ready for Compliance sign-off
- [x] Golden ≥30 and adversarial ≥20 committed with schema validated
- [x] Disclaimer text present: **“Facts-only. No investment advice.”**
- [x] No application code required yet beyond stubs / config

**Phase 1 status:** Complete (05 August 2026). Validate anytime with `python scripts/validate_phase1.py`.

### Out of scope this phase

Fetcher, indexes, LLM calls, UI.

---

## Phase 2 — Ingestion pipeline & scheduler

**Goal:** Reliably turn the five HTML pages into a versioned searchable index — on a schedule.

**Maps to:** Architecture M1 · PRD F1 (ingestion), F1.6 (scheduler)

### Work items

1. **Fetcher (HTML only)**
   - GET allow-listed URLs only; reject non-HTML / PDF
   - Store raw HTML, `fetched_at`, HTTP status, `content_hash`
   - Redirects only within `groww.in` to an allow-listed final URL
2. **HTML parser + sanitiser**
   - Isolate scheme content; preserve tables as `{label, value}`
   - Strip scripts / injection-like instruction patterns
3. **Section chunker**
   - ~300–600 tokens; heading breadcrumbs; parent `source_url` on every chunk
4. **Metadata enricher**
   - `amc`, `scheme_name`, `scheme_code`, `plan=Direct`, `option=Growth`, `document_type=groww_scheme_page`, `authority=Groww`
5. **Attribute extractor (structured)**
   - TER, exit load, min SIP (and other labelled fields) for later numeric diffs
6. **Embedder + index build**
   - Embed chunks with **`BAAI/bge-large-en-v1.5`** (local; pin model revision in config)
   - Persist dense vectors in **Chroma DB local** store (e.g. `data/chroma/`), with metadata: `chunk_id`, `source_id`, `scheme_code`, `plan`, `source_url`, `corpus_version`
   - Also build chunk store + BM25 index
   - Atomic publish → `corpus_version` (e.g. `YYYY-MM-DD.N`)
7. **Scheduler**
   - Cron: `15 9 * * *` timezone `Asia/Kolkata`
   - Job: run full ingestion over all five URLs
   - Manual/admin trigger supported
   - On failure: keep last published index; alert; never publish partial index
8. **CLI / script**
   - `ingest run` (once) and `ingest schedule` (register cron)

### Deliverables

| Artefact | Notes |
|---|---|
| `src/ingest/*` | fetch → parse → chunk → embed (`bge-large-en-v1.5`) → publish |
| Scheduler config | 09:15 AM IST daily |
| Chroma local + BM25 indexes | All five sources present |
| Ingest run logs | Per-URL status + hash |

### Exit criteria

- [x] One successful end-to-end ingest of all **five** pages
- [x] Chunks embedded with **`BAAI/bge-large-en-v1.5`** and stored in **Chroma DB local**
- [x] Indexes queryable offline (smoke: Chroma metadata filter by `scheme_code` + BM25)
- [x] Re-ingest with unchanged hash skips rebuild for that source
- [x] Scheduler configured for **09:15 AM IST**; documented how to run manually
- [x] **Zero** PDF libraries or PDF code paths in the repo
- [x] Failed fetch leaves previous `corpus_version` intact
- [x] No cloud vector DB dependency (Chroma local only for v1)

**Phase 2 status:** Complete (07 August 2026).

```bash
python -m src.ingest.cli run          # manual ingest
python -m src.ingest.cli smoke        # BM25 + Chroma smoke
python -m src.ingest.cli schedule     # daily 09:15 Asia/Kolkata
```

Published pointer: `data/published/current.json`.

### Out of scope this phase

Query API, LLM generation, UI, numeric approval queue UI (extraction + hash diff logging is enough; human gate UI lands in Phase 6).

---

## Phase 3 — Hybrid retrieval

**Goal:** Given a factual query, return the right chunks for the right scheme — or confidently say “not in my sources.”

**Maps to:** Architecture M2 · PRD F2

### Work items

1. **Query normaliser**
   - Abbreviation expansion (TER, SIP, IDCW, AUM, NAV, …)
   - Scheme alias → `scheme_code`
2. **Metadata pre-filter**
   - Filter by `scheme_code` + `plan=Direct` when resolved
3. **Hybrid retriever**
   - Dense top-k from **Chroma DB local** (query embedded with **`BAAI/bge-large-en-v1.5`**) ∪ BM25 top-k (e.g. k=20 each)
   - Apply Chroma metadata filters when `scheme_code` is resolved
4. **Cross-encoder reranker**
   - Keep top 3–5 chunks
5. **Confidence gate**
   - If top score < `τ` → do **not** proceed to generation; return coverage-gap signal
6. **Scheme disambiguation signal**
   - If top hits span multiple schemes → return `ambiguous` (clarify later in UI)
7. **Offline retrieval eval**
   - Measure recall@k / MRR on golden set subset (retrieval-only, no LLM)

### Deliverables

| Artefact | Notes |
|---|---|
| `src/retrieve/*` | filter, hybrid, rerank, gate |
| Tunable `τ` | Config file; documented |
| Retrieval eval report | Against golden subset |

### Exit criteria

- [x] For golden factual queries with a known `expected_source_id`, top-5 chunks include the correct source ≥ target (tune; aim high before Phase 4) — **recall@5 = 32/32 (1.000) on corpus `2026-08-07.7`; also reported per intent**
- [x] Mid Cap vs Small Cap and Equity vs Balanced Advantage confusion is measured and acceptable — **0 cross-confusions on top-1 in both 2×2 matrices** (`scripts/validate_phase3.py`)
- [x] Low-confidence queries return gate-fail (no silent empty context) — **τ sweep + out-of-corpus negatives; weather → `ambiguous`/`gate_fail`; uncovered AMCs → `uncovered`**
- [x] Uncovered schemes / unresolved entities produce an explicit signal (not a wrong scheme guess)

**Phase 3 status:** Complete (07 August 2026). Validate with `python scripts/validate_phase3.py`.  
Published: `corpus_version=2026-08-07.7` · Chroma `facts_desk_2026_08_07_7`.  
Config: `src/retrieve/config.yaml` (`tau` default `0.0` — not eval-tuned).

```bash
python -m src.retrieve.cli "What is the expense ratio of HDFC Mid Cap Fund Direct Growth?"
python scripts/validate_phase3.py
```

### Out of scope this phase

LLM answer wording, refusal templates, chat UI.

---

## Phase 4 — Generation, validation & safety

**Goal:** Produce ≤3-sentence, single-citation answers — or refuse cleanly — with hard guards against advice and invented numbers.

**Maps to:** Architecture M3 + M4 · PRD F3, F4, F5, F6.1

### Work items

1. **Extractive generator**
   - System prompt: answer only from provided chunks; temp ≈ 0
   - Output contract: ≤3 sentences · exactly 1 allow-listed citation · freshness footer from `fetched_at`
2. **Deterministic output validator**
   - Sentence count, citation count, allow-list URL, numeric-verbatim check, advisory lexicon blocklist
   - Fail → regenerate once → else safe fallback (“not in my sources”)
3. **Groundedness verifier**
   - Claims must be supported by the **cited** chunk
4. **Response assembler**
   - Answer / coverage / performance-redirect formats per PRD §12
5. **Intent classifier**
   - Classes: `factual_in_scope`, `advisory`, `comparative`, `predictive`, `performance`, `personal_account`, `pii_bearing`, `out_of_domain`, `uncovered_scheme`, `ambiguous`
6. **Refusal & performance handlers**
   - Templated refusals + educational link (SEBI/AMFI — **not** ingested)
   - Performance: never state returns; link to relevant Groww scheme page only
7. **PII redactor (edge)**
   - PAN / Aadhaar / folio / OTP / email / phone → type tokens before model/log
8. **Wire offline “ask” CLI**
   - Full path: redact → classify → (refuse \| retrieve → generate → validate → assemble)
9. **Eval runners**
   - Golden accuracy + citation presence
   - Adversarial refusal recall

### Deliverables

| Artefact | Notes |
|---|---|
| `src/generate/*` | prompt, validator, groundedness, assembler |
| `src/safety/*` | PII, intent, refusal, lexicon |
| CLI `ask` | End-to-end without UI |
| Eval scripts | CI-ready commands |

### Exit criteria

- [ ] Golden-set factual accuracy ≥ **90%** (PRD Phase 1 gate)
- [ ] Citation present and allow-listed on **100%** of answered golden items
- [ ] Adversarial refusal recall ≥ **95%**
- [ ] Advisory lexicon / numeric-verbatim validator catches known bad fixtures
- [ ] PII in a test query is redacted before any persistence or model payload dump
- [ ] Performance queries never return inline return figures

### Out of scope this phase

Production HTTP API, chat UI, admin console.

---

## Phase 5 — API, minimal UI & audit

**Goal:** Ship the product surface users and support can use — with auditability and caching.

**Maps to:** Architecture M5 · PRD F7, F6.5–F6.6, F3.5 (cache), F8.1

### Work items

1. **Query API**
   - `POST /ask` (or equivalent): streaming response preferred
   - Rate limit per session/IP
   - Session id only (no login / account link)
2. **Response cache**
   - Key: `hash(normalised_redacted_query + corpus_version)`
   - Invalidate on corpus publish
3. **Audit log**
   - Persist: redacted query, intent, chunk ids, corpus_version, response, citation, validator verdicts, model_version, timestamp
   - Sufficient to replay why an answer was produced
4. **Minimal chat UI** (problem statement + PRD F7)
   - Welcome message
   - Three example question chips
   - Persistent disclaimer: **“Facts-only. No investment advice.”**
   - Answer card (text + source chip + freshness footer + thumbs)
   - Refusal card (distinct, educational link)
   - Loading / streamed output
   - Mobile-first layout
5. **Feedback**
   - Thumbs up/down + reason chips (`wrong number` / `outdated` / `not what I asked` / `no source` / `other`)
6. **Clarifying question UI**
   - Up to 3 scheme chips when retrieval signals `ambiguous`
7. **Copy answer + citation** (support-friendly)

### Deliverables

| Artefact | Notes |
|---|---|
| `src/api/*` | Query endpoint, streaming, rate limit |
| `ui/*` | Minimal chat + disclaimer |
| Audit store | Queryable by timestamp / session |
| Cache layer | Version-aware |

### Exit criteria

- [ ] User can ask a factual question in the UI and get a sourced ≤3-sentence answer
- [ ] Refusal path renders correctly for an advisory chip/example
- [ ] Disclaimer visible without scrolling
- [ ] Every response written to audit log (redacted)
- [ ] Cache hit returns identical card for identical query + corpus_version
- [ ] No PII persisted in raw form (spot-check with test strings)

### Out of scope this phase

Full compliance console, multi-AMC, embeddable production widget traffic split (basic embed optional).

---

## Phase 6 — Ops hardening & launch gates

**Goal:** Make the system operable and meet launch-quality gates before broader use.

**Maps to:** Architecture M6 · PRD F1.7, F4.5, F8.2–F8.3, F9, Phase 1–2 exit gates

### Work items

1. **Numeric-diff human gate**
   - Diff TER / exit load / min SIP vs last published
   - Hold publish for that source until approve/reject
   - Minimal admin approval queue (F9.2)
2. **Dead-link monitor**
   - HEAD all five URLs on the daily schedule (with or right after ingest)
   - Quarantine answers if 4xx/5xx
3. **Admin / compliance console (v1)**
   - Corpus browser: source, last fetch, hash, version
   - Kill switch: global / scheme / intent
   - Answer replay from audit + retrieval trace
4. **Expand eval sets to PRD targets**
   - Golden ≥ **150** · Adversarial ≥ **100**
5. **CI gates**
   - Run golden + adversarial on every corpus/prompt/model change
   - Block promote of `corpus_version` if gates fail
6. **Consistency canary**
   - Replay a small golden slice periodically; alert on drift
7. **Staleness behaviour**
   - Withhold volatile fields (e.g. TER) if refresh SLA breached; caution otherwise
8. **README completion**
   - Setup, architecture summary, five URLs, limitations, how to run ingest/ask/eval, incident/kill-switch notes
9. **Internal pilot readiness**
   - Scripted walkthrough for support/content; sample conversations for Compliance audit

### Deliverables

| Artefact | Notes |
|---|---|
| Approval queue | Numeric diffs |
| Dead-link job | Daily with scheduler |
| Admin v1 | Browser + kill switch + replay |
| CI pipeline | Golden + adversarial gates |
| Complete README | Launch-ready |

### Exit criteria

- [ ] Golden factual accuracy ≥ **95%** (launch gate)
- [ ] Refusal recall ≥ **99%** on adversarial set
- [ ] Citation validity ≥ **99%**
- [ ] Advisory leakage = **0** on audit sample
- [ ] Numeric change cannot go live without human approval
- [ ] Kill switch disables the assistant without a redeploy
- [ ] Scheduler + dead-link + ingest documented and observed successful in a dry run
- [ ] README lists the five URLs, HTML-only constraint, and known limitations

### Out of scope this phase (defer)

- Multi-AMC expansion (PRD F11.1)
- Hindi / regional languages (F11.2)
- Structured attribute API for scheme pages (F11.3)
- Broad external traffic ramp / paid GTM

---

## Cross-phase checklist

Track these continuously; they apply from Phase 2 onward.

| Check | Phases |
|---|---|
| Only five allow-listed URLs fetched/cited | 2–6 |
| No PDF dependency introduced | 2–6 |
| Scheduler remains 09:15 AM IST | 2, 6 |
| Embeddings = `BAAI/bge-large-en-v1.5`; vectors in Chroma DB local | 2–6 |
| Answers ≤3 sentences + exactly one citation + freshness footer | 4–6 |
| Advice / comparison / returns never answered inline | 4–6 |
| PII never stored raw | 4–6 |
| Partial index never published | 2, 6 |

---

## Suggested timeline (indicative)

| Phase | Focus | Indicative duration |
|---|---|---|
| 1 | Foundation & corpus | ~3–5 days |
| 2 | Ingestion + scheduler | ~1–1.5 weeks |
| 3 | Hybrid retrieval | ~1 week |
| 4 | Generation + safety | ~1.5–2 weeks |
| 5 | API + UI + audit | ~1–1.5 weeks |
| 6 | Ops + launch gates | ~1.5–2 weeks |

Durations are guides. **Exit criteria override calendar.**

---

## Traceability

| Phase | Problem statement | PRD | Architecture |
|---|---|---|---|
| 1 | Corpus definition, disclaimer | Phase 0, Appendix A/B/C | M0, §2, §15 |
| 2 | HTML-only ingest, scheduler 09:15 IST | F1, F1.6 | M1, §5.2, §6 |
| 3 | Accurate retrieval | F2 | M2, §7.4–7.5 |
| 4 | Facts-only answers, refusal, privacy | F3–F6 | M3–M4, §7.6–7.9 |
| 5 | Minimal UI, citations, transparency | F7, F6.5, F8.1 | M5, §10 |
| 6 | Success criteria / launch quality | §7.2, F1.7, F4.5, F8–F9 | M6, §12–14 |

---

## Definition of done (whole plan)

The implementation plan is complete when Phases 1–6 exit criteria are all met and the system can:

1. Ingest the five Groww pages daily at **09:15 AM IST** (HTML only).
2. Answer in-scope factual questions in ≤3 sentences with exactly one allow-listed citation and a freshness footer.
3. Refuse advisory / comparative / predictive queries politely with an educational link.
4. Never invent numbers, never answer from PDFs or non-allow-listed URLs, never persist raw PII.
5. Pass golden ≥95%, refusal recall ≥99%, and zero advisory leakage on the audit sample.

---

*End of implementation plan.*
