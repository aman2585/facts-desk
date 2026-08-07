# Phase 4 Handoff — Facts Desk Generation, Validation & Safety

| Field | Value |
|---|---|
| Phase | 4 — Generation, validation & safety |
| Status | **Complete** — Phase 4 exit criteria **met** (golden **31/32 = 0.969**; adversarial **42/42**; `api-error = 0`) |
| Current published pointer | `corpus_version=2026-08-07.7` · `facts_desk_2026_08_07_7` · **10 chunks** (unchanged from Phase 3) |
| Generator | Groq OpenAI-compatible · `llama-3.1-8b-instant` · `temperature=0.0` ([`src/generate/config.yaml`](../src/generate/config.yaml)) |
| Handoff date | 07 August 2026 |
| Sources | [`implementationplan.md`](../implementationplan.md) · [`docs/RAG_Architecture.md`](RAG_Architecture.md) · [`PRD.md`](../PRD.md) · [`docs/PHASE3_HANDOFF.md`](PHASE3_HANDOFF.md) · [`docs/PHASE2_HANDOFF.md`](PHASE2_HANDOFF.md) |

---

## 1. What was built

### Part 1 — Safety + deterministic validator (no generator)

```
fixtures (fail-closed) → validate_answer
query → redact_pii → classify_intent (10 classes)
      → templated refusal | performance redirect | coverage_limit | clarify
```

| Area | Location | Notes |
|---|---|---|
| Deterministic validator | [`src/generate/validator.py`](../src/generate/validator.py) | Sentence ≤3, exactly 1 allow-listed URL, numeric-verbatim, advisory lexicon |
| Fail-closed fixtures | [`eval/fixtures/validator/fail_closed.json`](../eval/fixtures/validator/fail_closed.json) | 4 sentences, 0/2 citations, non-allow-listed URL, non-verbatim number, advisory phrase |
| Lexicon | [`src/safety/lexicon.py`](../src/safety/lexicon.py) | Shared blocklist for validator |
| PII redactor | [`src/safety/pii.py`](../src/safety/pii.py) | PAN / Aadhaar / folio / OTP / email / phone → type tokens |
| Uncovered detection | [`src/safety/uncovered.py`](../src/safety/uncovered.py) | Foreign AMC list + scheme-shape heuristic; wired into [`src/retrieve/normaliser.py`](../src/retrieve/normaliser.py) |
| Intent classifier | [`src/safety/intent.py`](../src/safety/intent.py) | 10 classes per implementation plan |
| Refusals / performance | [`src/safety/refusals.py`](../src/safety/refusals.py) | Templated handlers; SEBI/AMFI links **not** in corpus |
| Adversarial expansion | [`eval/adversarial/items.json`](../eval/adversarial/items.json) | **n=42** (≥40): compound factual+advisory + unrecognised AMCs; includes Axis Midcap / Kotak Flexicap |
| Uncovered fixtures | [`eval/fixtures/safety/uncovered.json`](../eval/fixtures/safety/uncovered.json) | Axis / Kotak must never resolve to a corpus scheme |
| Part 1 gate | [`scripts/validate_phase4_part1.py`](../scripts/validate_phase4_part1.py) | Validator fixtures + uncovered gap + in-corpus aliases + PII + performance + intent spot-checks |
| Scheme alias tests | [`tests/test_scheme_aliases.py`](../tests/test_scheme_aliases.py) | All five schemes resolve from common phrasings; Axis/Kotak/SBI/ICICI stay uncovered |

### Part 2 — Generator, groundedness, assembler, ask CLI, eval

```
redact → classify → (refuse | retrieve → generate → labelled_attrs complete
                                      → validate → [regen once]
                                      → groundedness → assemble)
```

| Area | Location | Notes |
|---|---|---|
| Config / LLM client | [`src/generate/config.yaml`](../src/generate/config.yaml) · [`llm.py`](../src/generate/llm.py) | Provider/model/temp swappable; Groq HTTP; **429 exponential backoff**; exhausted 429 → `LLMAPIError` (not safe fallback) |
| Extractive prompt | [`src/generate/prompt.py`](../src/generate/prompt.py) | Chunk-wording only; prefer one sentence; no definitions / padding; dual labelled-pair rule for Category/Sub-category |
| **Labelled-attr completer** | [`src/generate/labelled_attrs.py`](../src/generate/labelled_attrs.py) | Deterministic post-LLM completer for **category** queries — see §1.1 |
| Generator | [`src/generate/generator.py`](../src/generate/generator.py) | Validate → regen once → safe fallback; calls `complete_labelled_attributes` after each LLM attempt; audit keeps `groundedness_first` + `groundedness_fallback` |
| Groundedness | [`src/generate/groundedness.py`](../src/generate/groundedness.py) | Numbers + lexical overlap vs **cited** chunk (threshold unchanged) |
| Assembler | [`src/generate/assembler.py`](../src/generate/assembler.py) | Answer / coverage / refusal / performance / **`api_error`** cards; freshness from `fetched_at` |
| Ask pipeline + CLI | [`src/generate/pipeline.py`](../src/generate/pipeline.py) · [`cli.py`](../src/generate/cli.py) | Full offline ask path |
| Golden eval | [`scripts/eval_golden.py`](../scripts/eval_golden.py) | Buckets: **answered / refused / grounded-fail / api-error**; `eval_query_delay_s` between items |
| Adversarial eval | [`scripts/eval_adversarial.py`](../scripts/eval_adversarial.py) | Refusal recall; api-error excluded from recall denom; delay supported |
| Labelled-attr tests | [`tests/test_labelled_attrs.py`](../tests/test_labelled_attrs.py) | g026–g028 under-specify fixtures; non-category unchanged |

**Out of scope (still):** HTTP API, chat UI, admin console, numeric approval UI (Phase 5–6).

### 1.1 `labelled_attrs.py` (deterministic completer)

Post-generation completer for **category / scheme-type** queries (e.g. g026–g028):

| Property | Behaviour |
|---|---|
| **When it runs** | After each LLM attempt in `generate_answer`, before validate |
| **Gate** | Category-shaped query **and** cited chunk has **both** `Category` + `Sub-category` labelled pairs **and** the LLM answer is under-specified (missing a value or missing both labels) |
| **Rewrite** | Replaces answer body with `Category: {v}; Sub-category: {v}`; keeps citation URL |
| **Value source** | **Only** from the cited chunk (`tables`, else `Label: value` in chunk text) — no invented values |
| **Labels** | Canonical forms `Category` / `Sub-category` (casing normalised) |
| **Non-trigger** | TER / exit-load / other intents; single missing label; already-complete answers |

Fixes under-specified paraphrases such as “is a Mid Cap scheme” / “category is Equity” that omitted the paired Sub-category (or Category) present in the chunk.

---

## 2. Commands

```bash
# Part 1 gate (no Groq)
python scripts/validate_phase4_part1.py

# Alias / labelled-attr unit tests
python -m unittest tests.test_scheme_aliases tests.test_labelled_attrs -v

# Offline ask (requires GROQ_API_KEY)
python -m src.generate.cli "What is the expense ratio of HDFC Mid Cap Fund Direct Growth?"
python -m src.generate.cli --json "..."

# Golden / adversarial (requires GROQ_API_KEY; delay from config, default 2s)
python scripts/eval_golden.py --json-out data/logs/golden_eval.json
python scripts/eval_adversarial.py --json-out data/logs/adversarial_eval.json
```

Config: [`src/generate/config.yaml`](../src/generate/config.yaml)  
Published index: `data/published/current.json` (still Phase 3 corpus `.7`)

---

## 3. Exit criteria status

| # | Criterion | Result | Evidence / note |
|---|---|---|---|
| 1 | Golden factual accuracy ≥ **90%** | **PASS** | **31/32 = 0.969** on clean run with `api-error = 0` |
| 2 | Citation allow-listed on **100%** of answered golden items | **PASS** | **citation_on_answered = 31/31** |
| 3 | Adversarial refusal recall ≥ **95%** | **PASS** | **42/42**; no advisory / scope leaks |
| 4 | Advisory lexicon / numeric-verbatim catch known bad fixtures | **PASS** | `validate_phase4_part1.py` — all six fail-closed fixtures |
| 5 | PII redacted before model/persistence path | **PASS** | Part 1 gate; classifier sees redacted query |
| 6 | Performance queries never return inline return figures | **PASS** | Part 1 performance handler check |

**Honest summary:** Phase 4 exit gates are met. One golden item remains a generate-path failure: **g002** (`grounded-fail`) — does not block the ≥90% accuracy gate.

---

## 4. Eval results (clean exit run)

### 4.1 Bucket model

| Bucket | Meaning |
|---|---|
| `answered` | `response_type=answer` |
| `refused` | Safety / retrieval short-circuit (refusal, clarify, performance, pii_warn, uncovered coverage) |
| `grounded-fail` | Generate path used safe fallback (validator or groundedness) |
| `api-error` | Model HTTP failure after retries (e.g. 429) — **not** a coverage gap |

Accuracy excludes `api-error` from the denominator. Exit code **2** if any `api-error` remains.

### 4.2 Golden (exit run)

| Metric | Value |
|---|---|
| Factual accuracy | **31/32 (0.969)** |
| Citation on answered | **31/31 (1.000)** |
| `answered` | **31** |
| `refused` | **0** |
| `grounded-fail` | **1** (**g002**) |
| `api-error` | **0** |

### 4.3 Remaining miss — g002

| Field | Value |
|---|---|
| ID | **g002** |
| Eval bucket | `grounded-fail` |
| Notes | Sole non-answer on the exit run; generate path fell back (validator/groundedness). Inspect `groundedness_first` in a follow-up if tightening Equity / Flexi Cap TER phrasing. Does **not** reopen Phase 4 exit. |

### 4.4 Adversarial (exit run)

| Metric | Value |
|---|---|
| Suite size | **42** |
| Refusal recall | **42/42 (1.000)** |
| Leaks | **None** (no advisory / scope leakage on the suite) |
| Axis / Kotak / foreign AMCs | Classify `uncovered_scheme`; coverage_limit |

### 4.5 Part 1 fixture gate

`python scripts/validate_phase4_part1.py` — **passed** (validator fail-closed ×6, uncovered Axis/Kotak, in-corpus Nifty/BAF aliases, PII, performance, 10 intent classes).

### 4.6 Historical note (superseded)

An earlier contaminated run reported ~6/32 with 429s absorbed as coverage and 7 Nifty/BAF items false-positive `uncovered_scheme`. Those defects are fixed (resolver order + `labelled_attrs`); the §4.2 exit run supersedes that headline.

---

## 5. Known Issues

### Phase 4 residual (non-blocking)

1. **g002 grounded-fail** — only remaining golden miss; see §4.3.
2. **Groq free-tier rate limits** — retries + backoff + `eval_query_delay_s` + `api_error` bucket keep eval honest; suites remain slow.
3. **`tau=0.0` still ungated (carried from Phase 3)** — confidence gate does not reject low-score candidates; out-of-corpus safety depends on resolver/classifier short-circuits.
4. **Mega-KV chunk / thin corpus (carried)** — ~2 chunks/scheme; fact accuracy still generation+validation over Investment-details blobs.

### Fixed during Phase 4 exit push

| Issue | Resolution |
|---|---|
| Nifty 50 / BAF → false `uncovered_scheme` (7 golden refused) | Alias before scheme-shape; intent skips uncovered heuristic when resolved; aliases expanded (`nifty 50`, `BAF`, …); tests in `tests/test_scheme_aliases.py` |
| g026–g028 under-specified Category answers | [`labelled_attrs.py`](../src/generate/labelled_attrs.py) deterministic completer |

### Carried forward from Phase 3 ([`PHASE3_HANDOFF.md`](PHASE3_HANDOFF.md))

| Issue | Status entering Phase 5 |
|---|---|
| Negatives score high if forced past uncovered short-circuit | Unchanged — Axis/Kotak/SBI/ICICI caught at ask/normaliser; unrecognised names still a residual risk |
| τ untuned | Unchanged (`tau=0.0`) |
| Equity / Flexi Cap naming footgun | Unchanged — relevant to **g002** investigation |
| Filter-off recall@1 = 0.844; recall@5 not discriminative | Unchanged — corpus still 10 chunks |

### Carried forward from Phase 2 ([`PHASE2_HANDOFF.md`](PHASE2_HANDOFF.md))

| Issue | Status |
|---|---|
| `src_002` Flexi Cap display vs Equity URL/`scheme_code` | Owner decision stands; still a UX/retrieval footgun |
| Atomic publish incomplete | Staging/old Chroma accumulate; crash consistency untested |
| Embedding model revision unpinned | Unchanged |
| Scheduler not observed at real 09:15 IST | Unchanged |
| Fail-soft fetch not chaos-tested | Unchanged |
| Numeric approval = log only | Phase 6 |
| Thin page coverage after exclusions | Unchanged (~2 chunks/scheme) |

---

## 6. Recommended owner actions for Phase 5

1. Ship API + minimal UI + audit/cache per implementation plan Phase 5.
2. Optionally inspect **g002** `groundedness_first` (Equity TER) — polish only; not a Phase 4 reopen.
3. Keep τ at 0.0 until corpus growth; do not treat Phase 3 recall@5 as product accuracy.
4. Continue Phase 2 publish hardening and scheduler observation.

---

## 7. Traceability

| Phase 4 work item | Location |
|---|---|
| Output validator | `src/generate/validator.py` |
| Labelled-attr completer | `src/generate/labelled_attrs.py` |
| Groundedness | `src/generate/groundedness.py` |
| Generator + audit dual groundedness | `src/generate/generator.py` |
| Prompt (extractive contract) | `src/generate/prompt.py` |
| Assembler (+ `api_error`) | `src/generate/assembler.py` |
| Groq client + 429 retry | `src/generate/llm.py` |
| Ask path | `src/generate/pipeline.py` · `cli.py` |
| PII / intent / refusals / uncovered | `src/safety/*` |
| Alias resolve order | `src/retrieve/normaliser.py` |
| Golden / adversarial eval | `scripts/eval_golden.py` · `eval_adversarial.py` |
| Part 1 gate | `scripts/validate_phase4_part1.py` |
| Alias / labelled-attr tests | `tests/test_scheme_aliases.py` · `tests/test_labelled_attrs.py` |

---

## 8. Definition of done (Phase 4) — **met**

| # | Requirement | Status |
|---|---|---|
| 1 | Golden factual accuracy ≥ **90%** on a run with **api-error = 0** | **Met** — 31/32 (0.969), api-error = 0 |
| 2 | Citation allow-listed on **100%** of answered golden items | **Met** — 31/31 |
| 3 | Adversarial refusal recall ≥ **95%** (api-error excluded or zero) | **Met** — 42/42, no leaks |
| 4 | In-corpus schemes are **not** classified `uncovered_scheme` by mistake | **Met** — Nifty/BAF alias fix + tests |
| 5 | 429s never appear as silent coverage fallbacks | **Met** — distinct `api_error` path; exit run had zero |

Phase 4 ask path is exit-complete for handoff to Phase 5 (API + UI + audit). Residual: **g002** grounded-fail only.

---

*End of Phase 4 handoff.*
