# RAG Architecture — Facts Desk (Mutual Fund FAQ Assistant)

| Field | Value |
|---|---|
| Document | Detailed RAG architecture |
| Status | Design baseline for implementation |
| Sources of truth | [`problemStatement.md`](../problemStatement.md), [`PRD.md`](../PRD.md) |
| Product | Facts Desk — facts-only Q&A over five Groww scheme pages |
| Last updated | 05 August 2026 |

---

## 1. Purpose

This document specifies the **Retrieval-Augmented Generation (RAG)** system for Facts Desk: a facts-only mutual fund FAQ assistant that answers objective questions about **five fixed HDFC Direct Growth schemes** using **only five allow-listed Groww HTML pages**.

Design goals (from the PRD):

1. **Accuracy over intelligence** — extract and phrase facts; never invent or advise.
2. **One claim, one source** — every answer cites exactly one allow-listed Groww URL.
3. **Corpus is the product** — nothing outside `corpus.yaml` is fetched or retrieved.
4. **HTML only** — no PDF ingestion (no SID, KIM, or factsheet PDFs).
5. **Refusal is a first-class path** — advisory / comparative / predictive queries never reach generation as answers.
6. **Auditability** — every answer reconstructable from `(redacted_query, chunk_ids, corpus_version, model_version, validator_verdicts)`.

---

## 2. Scope lock (non-negotiable)

### 2.1 Allow-listed corpus (exhaustive)

| ID | Scheme | URL |
|---|---|---|
| `src_001` | HDFC Mid Cap Fund Direct Growth | https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth |
| `src_002` | HDFC Equity Fund Direct Growth | https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth |
| `src_003` | HDFC Small Cap Fund Direct Growth | https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth |
| `src_004` | HDFC Nifty 50 Index Fund Direct Growth | https://groww.in/mutual-funds/hdfc-nifty-50-index-fund-direct-growth |
| `src_005` | HDFC Balanced Advantage Fund Direct Growth | https://groww.in/mutual-funds/hdfc-balanced-advantage-fund-direct-growth |

### 2.2 Explicit exclusions

| Excluded | Handling |
|---|---|
| PDFs (SID, KIM, factsheets, circulars) | Never fetch, parse, or index |
| Open-web / other aggregators / AMC sites | Never retrieve |
| Schemes outside the five | Coverage-limit message; no answer |
| Performance / returns / projections | Refuse inline; link to scheme page only |
| Advice / comparison / suitability | Templated refusal + educational link (not ingested) |

Educational links (SEBI / AMFI) used in refusal templates are **not** part of the RAG corpus.

---

## 3. Architecture overview

The system splits into two planes:

1. **Offline ingestion** — **Scheduler** (09:15 IST daily) → fetch → parse → chunk → embed → index → human gate on numeric diffs → publish versioned index.
2. **Online query path** — redact → classify → (refuse \| retrieve → rerank → generate → validate → assemble) → audit.

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         OFFLINE — INGESTION PLANE                        │
│                                                                          │
│  ┌──────────────── Scheduler ────────────────┐                           │
│  │  Run ingestion service @ 09:15 AM IST daily│                          │
│  │  (+ optional manual / admin trigger)       │                          │
│  └────────────────────┬───────────────────────┘                          │
│                       ▼                                                  │
│  corpus.yaml (5 URLs)                                                    │
│       │                                                                  │
│       ▼                                                                  │
│  ┌─────────┐   ┌──────────┐   ┌──────────┐   ┌────────────┐             │
│  │ Fetcher │──►│ HTML     │──►│ Section  │──►│ Metadata   │             │
│  │ (HTML)  │   │ Parser   │   │ Chunker  │   │ Enricher   │             │
│  └─────────┘   └──────────┘   └──────────┘   └─────┬──────┘             │
│       │              │                              │                    │
│       │         content_hash                   chunks + attrs            │
│       ▼              ▼                              ▼                    │
│  ┌────────────────────────────────┐      ┌─────────────────────┐         │
│  │ Change detector + numeric-diff │      │ Embedding encoder   │         │
│  │ review queue (human approve)   │      │ + BM25 index build  │         │
│  └───────────────┬────────────────┘      └──────────┬──────────┘         │
│                  │ approve                          │                    │
│                  ▼                                  ▼                    │
│           ┌──────────────────────────────────────────────┐               │
│           │     Published index (corpus_version)         │               │
│           │  Chroma (local) · BM25 · chunk store · meta  │               │
│           └──────────────────────┬───────────────────────┘               │
└──────────────────────────────────┼───────────────────────────────────────┘
                                   │ read-only at query time
┌──────────────────────────────────┼───────────────────────────────────────┐
│                         ONLINE — QUERY PLANE                             │
│                                  ▼                                       │
│  Client (chat UI / embed)                                                │
│       │                                                                  │
│       ▼                                                                  │
│  ┌────────────┐  ┌──────────────┐  ┌─────────────────┐                   │
│  │ Edge: PII  │─►│ Normaliser   │─►│ Intent          │                   │
│  │ redaction  │  │ + abbrev     │  │ classifier      │                   │
│  └────────────┘  └──────────────┘  └────────┬────────┘                   │
│                                             │                            │
│                    advisory / comparative / predictive / PII / OOD       │
│                                             │                            │
│                                             ▼                            │
│                                    ┌────────────────┐                    │
│                                    │ Refusal handler│──► response        │
│                                    │ (templated)    │                    │
│                                    └────────────────┘                    │
│                                             │ factual_in_scope           │
│                                             ▼                            │
│  ┌──────────────┐  ┌─────────────┐  ┌────────────┐  ┌─────────────────┐ │
│  │ Scheme /     │─►│ Hybrid      │─►│ Cross-enc. │─►│ Confidence gate │ │
│  │ plan filter  │  │ retrieve    │  │ rerank     │  └────────┬────────┘ │
│  └──────────────┘  │ dense+BM25  │  │ top 3–5    │           │          │
│                    └─────────────┘  └────────────┘           │          │
│                         below threshold ─────────────────────┤          │
│                                                              ▼          │
│                                                   "not in my sources"   │
│                                                              │ pass     │
│                                                              ▼          │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────────────────┐ │
│  │ Extractive     │─►│ Deterministic  │─►│ Groundedness verifier      │ │
│  │ generator      │  │ output         │  │ (claim ⊆ cited chunk)      │ │
│  │ (temp ≈ 0)     │  │ validator      │  └─────────────┬──────────────┘ │
│  └────────────────┘  └────────────────┘                │                │
│                                                        ▼                │
│                                    Response assembly + citation footer  │
│                                                        │                │
│                                                        ▼                │
│                                              Audit log + cache write    │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Design principles → architecture mapping

| Principle | Architectural enforcement |
|---|---|
| Accuracy over intelligence | Extractive prompt; numeric-verbatim guardrail; no parametric fallback |
| One claim, one citation | Validator rejects ≠1 link or non-allow-listed URL |
| Freshness visible | `fetched_at` on every chunk; footer uses cited page’s fetch date |
| Refusal as a feature | Pre-retrieval classifier + templated handlers; layered blocklist |
| Corpus is the product | Hard allow-list in fetcher + retriever + citation validator |
| Never touch PII | Edge redaction before log, cache key, or model call |
| Boring on purpose | Response contract: ≤3 sentences, no hedging lexicon |

---

## 5. Component catalogue

### 5.1 Offline components

| Component | Responsibility | Inputs | Outputs |
|---|---|---|---|
| **Scheduler** | Triggers the ingestion service on a fixed cadence; supports manual/admin re-run | Cron config / job definitions | Ingestion job start events |
| **Corpus registry** | Version-controlled allow-list | `corpus.yaml` | Source descriptors |
| **Fetcher** | HTTP GET of HTML only; robots/headers; retries | URL list | Raw HTML + headers + `fetched_at` |
| **Content hasher** | Detect page changes | Raw HTML (normalised) | `content_hash` |
| **HTML parser** | Extract main content, tables, sections; strip nav/chrome | Raw HTML | Structured document AST |
| **Sanitiser** | Strip scripts, event handlers, injection-like instruction patterns | AST / text | Clean text + tables |
| **Section chunker** | Split by headings; 300–600 tokens; keep breadcrumbs | Clean doc | Chunks |
| **Metadata enricher** | Attach scheme/plan/url/dates | Chunks + registry | Enriched chunks |
| **Attribute extractor** | Optional structured pull of TER, exit load, min SIP, etc. | Tables / labelled fields | Attribute records (for diffs) |
| **Diff engine** | Compare previous vs new numeric attributes | Attribute records | Diff events |
| **Approval queue** | Human gate for numeric changes | Diff events | Approve / reject |
| **Embedder** | Dense vectors for chunks via **`BAAI/bge-large-en-v1.5`** | Chunk text | Embeddings (1024-d) |
| **Index builder** | Build / swap **Chroma DB (local)** vector collection + BM25 + chunk store | Embeddings + text | Published `corpus_version` |
| **Dead-link monitor** | HEAD of 5 URLs (same daily schedule as ingestion, or immediately after fetch) | Registry | Quarantine alerts |

### 5.2 Scheduler (first-class)

The **Scheduler** is a required offline component. It does not fetch or parse content itself; it only **starts the ingestion service**.

| Property | Value |
|---|---|
| **Primary job** | Run ingestion service over the five allow-listed Groww URLs |
| **Cadence** | **Daily at 09:15 AM IST** (`Asia/Kolkata`) |
| **Cron (IST)** | `15 9 * * *` in timezone `Asia/Kolkata` (or equivalent UTC offset-aware schedule) |
| **Scope** | All five corpus URLs every run (no subset unless a source is quarantined) |
| **Manual override** | Admin / ops may trigger the same ingestion pipeline out-of-band (e.g. after an urgent page change) |
| **On success** | Proceed through fetch → parse → chunk → (numeric approval if needed) → publish `corpus_version` |
| **On failure** | Keep last published index; alert corpus owner; do not flip `current_corpus_version` to a partial build |
| **Idempotency** | Re-running the same day is safe: unchanged `content_hash` skips rebuild for that source |
| **Related jobs** | Dead-link HEAD checks may run in the same job (post-fetch) or as a sibling daily job |

```
┌─────────────┐         ┌──────────────────────┐
│  Scheduler  │────────►│  Ingestion service   │
│  09:15 IST  │  daily  │  fetch 5 HTML pages  │
└─────────────┘         └──────────────────────┘
```

### 5.3 Online components

| Component | Responsibility |
|---|---|
| **API gateway** | Rate limit, session id, TLS termination |
| **PII redactor** | Detect & replace PAN / Aadhaar / folio / OTP / email / phone |
| **Query normaliser** | Lowercase lightly, expand TER/IDCW/SIP/…, scheme alias map |
| **Intent classifier** | Route to factual / refuse classes / ambiguous |
| **Refusal handler** | Templates + educational outbound links (not from corpus) |
| **Scheme resolver** | Map query entities → one of five schemes (or ask to clarify) |
| **Hybrid retriever** | Dense + BM25 with metadata pre-filter |
| **Reranker** | Cross-encoder; keep top 3–5 |
| **Confidence gate** | Score threshold → generate or "not in my sources" |
| **Generator** | Small LLM, temp≈0, extractive system prompt |
| **Output validator** | Deterministic checks (length, link, allow-list, numerics, lexicon) |
| **Groundedness verifier** | Claim entailment vs cited chunk |
| **Response assembler** | Answer card + source chip + freshness footer |
| **Response cache** | Key: `(normalised_query, corpus_version)` |
| **Audit logger** | Full reconstructable trace (redacted) |

---

## 6. Offline ingestion pipeline (detailed)

### 6.1 Sequence

```
Scheduler @ 09:15 AM IST daily  (or manual/admin trigger)
    → load corpus.yaml
    → for each of 5 URLs:
         fetch HTML
         compute content_hash
         if hash unchanged → bump last_verified_at; skip rebuild for that source
         else:
              parse HTML → sections + tables
              sanitise (strip scripts / injection patterns)
              extract structured attributes (TER, exit_load, min_sip, …)
              emit numeric diffs vs previous published attributes
              if numeric fields changed → enqueue ApprovalQueue; HOLD publish for that source
              else → chunk → embed → stage index shard
    → after all sources ready (and approvals complete):
         build new index atomically
         assign corpus_version = "YYYY-MM-DD.N"
         swap published pointer
         invalidate response cache for affected schemes (or entire version)
```

### 6.2 Fetch rules

- **Method:** GET HTML only. Follow redirects only within `groww.in` and only to an allow-listed final URL.
- **Reject:** any `Content-Type` that is not HTML; any `.pdf` link discovery; any outbound crawl.
- **Timeouts / retries:** bounded (e.g. 10s timeout, 2 retries with backoff).
- **Stamps:** store `fetched_at`, HTTP status, final URL, `content_hash`.
- **Failure policy:** keep last published chunks for that source; mark `stale` / raise alert; do not serve a partial new index (E14).

### 6.3 HTML parsing strategy

Groww scheme pages are sectioned UIs. Parser responsibilities:

1. Isolate primary scheme content (exclude global nav, footer, related funds carousel if it injects other schemes’ numbers).
2. Preserve **tables and key-value blocks** as structured rows (`label`, `value`), not flattened prose.
3. Capture headings as hierarchy for chunk breadcrumbs, e.g.  
   `HDFC Mid Cap Fund Direct Growth > Returns & Risk > Riskometer`.
4. Drop client-only charts/images where no text alt exists (E9 → out of scope / manual override).

### 6.4 Chunking strategy

| Parameter | Value |
|---|---|
| Target size | ~300–600 tokens |
| Split unit | Section / subsection first; fall back to sliding window with overlap (~50 tokens) only within a section |
| Breadcrumbs | Always prefix chunk text with heading path |
| Parent ref | Every chunk stores `source_id`, `source_url` (citation target is the page URL, never a chunk id) |
| Tables | Prefer one chunk per logical table or attribute group so TER/exit-load stay atomic |

**Chunk record (logical schema):**

```json
{
  "chunk_id": "src_001::c_014",
  "source_id": "src_001",
  "source_url": "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth",
  "amc": "HDFC",
  "scheme_name": "HDFC Mid Cap Fund",
  "scheme_code": "hdfc_mid_cap_direct_growth",
  "plan": "Direct",
  "option": "Growth",
  "document_type": "groww_scheme_page",
  "authority": "Groww",
  "heading_path": ["Overview", "Investment Details"],
  "text": "...",
  "tables": [{"label": "Expense ratio", "value": "0.7%"}],
  "content_hash": "sha256:...",
  "fetched_at": "2026-08-05T06:00:00Z",
  "corpus_version": "2026-08-05.1"
}
```

### 6.5 Numeric-diff human gate

Silent TER/exit-load/min-SIP drift is a critical failure mode.

1. Extract canonical attributes after parse.
2. Diff against last **published** attribute set.
3. If any `numeric_fields` change → **do not auto-publish** that source’s new chunks.
4. Content/ops reviews diff in admin console; approve or reject.
5. On approve → include in next index build; on reject → keep prior chunks, alert owner.

### 6.6 Index artefacts

For each published `corpus_version`:

| Store | Contents |
|---|---|
| **Chunk store** | Full chunk JSON (source of truth for generation & audit) |
| **Vector index** | **Chroma DB local** collection of dense embeddings from `BAAI/bge-large-en-v1.5` (cosine), keyed by `chunk_id` with scheme metadata |
| **BM25 index** | Lexical index over chunk text + scheme aliases |
| **Attribute store** | Optional structured facts for eval / admin diffs |
| **Manifest** | Source list, hashes, `fetched_at`, approver ids, version id |

**Atomic publish:** build under a staging version → health check (5 HEAD + sample retrieval) → flip `current_corpus_version` pointer. Queries never read a mid-build index.

---

## 7. Online query path (detailed)

### 7.1 End-to-end sequence

```
User message
  → PII redaction (edge)
  → Cache lookup (normalised_query, corpus_version)? hit → return cached card
  → Query normalisation + abbreviation expansion + alias map
  → Intent classification
       ├─ advisory | comparative | predictive | suitability | calculation
       │     → Refusal template + educational link → audit → return
       ├─ performance
       │     → Performance handler (no figures; link scheme page) → audit → return
       ├─ personal_account | pii_bearing
       │     → Warn + redirect; never ask for identifiers → audit → return
       ├─ out_of_domain | uncovered_scheme
       │     → Scope / coverage message → audit → return
       ├─ ambiguous scheme
       │     → One clarifying question (≤3 chips) → return (no generation)
       └─ factual_in_scope
             → Metadata filter (scheme_code, plan=Direct)
             → Hybrid retrieve (dense top-k ∪ BM25 top-k)
             → Rerank → top 3–5
             → Confidence gate
                   ├─ fail → "not in my sources" + scheme page link
                   └─ pass → Generate (extractive, temp≈0)
                               → Output validator
                                     ├─ fail → regenerate once
                                     │         ├─ pass → continue
                                     │         └─ fail → safe fallback
                                     └─ pass → Groundedness check
                                                 ├─ fail → safe fallback + eval queue
                                                 └─ pass → Assemble response
                                                           → Cache write
                                                           → Audit log
                                                           → Stream to client
```

### 7.2 Intent classes

| Class | Next hop |
|---|---|
| `factual_in_scope` | Retrieval path |
| `advisory` | Refusal |
| `comparative` | Refusal |
| `predictive` | Refusal |
| `performance` | Dedicated redirect (no inline returns) |
| `personal_account` | Refuse + app/support |
| `pii_bearing` | Redact, warn, refuse account-specific part |
| `out_of_domain` | Scope reminder |
| `uncovered_scheme` | Coverage limit (five schemes) |
| `ambiguous` | Clarifying question |

Classifier is a **gate**, not the only defence. Downstream: retrieval scope, system prompt, validator, advisory lexicon blocklist.

### 7.3 Query preprocessing

1. **PII strip** → type tokens (`<PAN_REDACTED>`, …).
2. **Abbreviation expansion:** TER, IDCW, SIP, STP, SWP, NFO, KIM, SID, AUM, NAV, BAF, …
3. **Scheme alias map** (examples):
   - “hdfc midcap” / “hdfc mid cap direct” → `hdfc_mid_cap_direct_growth`
   - “hdfc flexi” / “hdfc equity fund” → `hdfc_equity_direct_growth`
   - “hdfc nifty 50” / “hdfc index” → `hdfc_nifty_50_index_direct_growth`
4. **Plan/option defaults:** corpus is Direct Growth only; if user says Regular/IDCW → clarify or state coverage.

### 7.4 Hybrid retrieval

**Why hybrid:** scheme names are long and near-identical; pure vector search confuses Mid Cap vs Small Cap and Equity vs Balanced Advantage.

```
candidates = union(
  chroma_dense_search(query_embedding_bge_large, filter=scheme_meta, k=20),
  bm25_search(query_text, filter=scheme_meta, k=20)
)
reranked = cross_encoder(query, candidates)[:5]
```

Query and document embeddings both use **`BAAI/bge-large-en-v1.5`**; dense hits come from the **Chroma DB local** collection.

**Metadata pre-filter** (when scheme resolved):

```
amc = HDFC AND plan = Direct AND scheme_code IN {resolved}
```

If scheme unresolved but intent factual → retrieve across all five with lower confidence threshold, then force disambiguation if top hits span multiple schemes (E2).

### 7.5 Confidence gate

| Condition | Action |
|---|---|
| Top rerank score < `τ` | Do **not** call generator; return F5.4 "not in my sources" |
| Top chunks disagree on a numeric | Withhold; corpus alert (E5) |
| Cited source past refresh SLA for volatile field | Withhold TER; caution for softer fields (F4.4) |

`τ` is tuned on the golden set; ship with a configurable threshold, not a hard-coded magic number in prompts.

### 7.6 Generation contract

**System policy (extractive-first):**

- Answer **only** using provided chunks.
- ≤ 3 sentences; declarative; no hedging (“typically”, “generally”, “you may want”).
- Exactly **one** citation URL from the allow-list, matching the chunk’s `source_url`.
- Numbers must appear **verbatim** in a provided chunk — no arithmetic, rounding, unit conversion, or aggregation.
- Temperature ≈ 0; no tools; no web browse.

**User/context payload to model:**

```
chunks: [{chunk_id, heading_path, text, tables, source_url, fetched_at}]
query: <redacted normalised query>
scheme: <resolved scheme_code or null>
```

### 7.7 Deterministic output validator

Reject (then one regenerate, then safe fallback) if any fail:

| Check | Rule |
|---|---|
| Sentence count | ≤ 3 |
| Citation count | Exactly 1 URL |
| Allow-list | URL ∈ {five Groww URLs} |
| Numeric verbatim | Every number in answer ⊆ retrieved chunk text/tables |
| Advisory lexicon | Zero hits on blocklist (recommend, better, should, outperform, …) |
| Empty / speculative | No “I think”, “might”, “probably” |

### 7.8 Groundedness verifier

Second pass (LLM-as-judge **or** entailment model + spot checks):

- Each factual claim in the answer must be supported by the **cited** chunk (not merely any retrieved chunk).
- Failures → safe fallback + log to eval queue (F3.4).

### 7.9 Response assembly

```
<answer text ≤3 sentences>

[Source: Groww — <Scheme Display Name>](<allow-listed url>)
Last updated from sources: <DD Mon YYYY>   # from cited chunk.fetched_at
```

UI also shows persistent disclaimer: **Facts-only. No investment advice.**

---

## 8. Data model summary

### 8.1 `corpus.yaml` (authoritative allow-list)

See PRD Appendix A. Runtime must load this file (or its compiled equivalent) and **refuse** any fetch/citation outside it.

### 8.2 Runtime objects

| Object | Key fields |
|---|---|
| `Source` | `source_id`, `url`, `scheme_code`, `refresh`, `owner`, `numeric_fields[]` |
| `Chunk` | see §6.4 |
| `AttributeSnapshot` | `source_id`, `field`, `value`, `corpus_version`, `approved_by` |
| `QueryEvent` | `session_id`, `redacted_query`, `intent`, `scheme_code`, `corpus_version` |
| `RetrievalTrace` | `chunk_ids[]`, `scores[]`, `rerank_scores[]`, `gate_passed` |
| `GenerationTrace` | `model_version`, `raw_output`, `validator_verdicts[]`, `groundedness` |
| `ResponseRecord` | `answer`, `citation_url`, `freshness_date`, `response_type` (`answer`\|`refusal`\|`coverage`\|`clarify`) |
| `AuditLogEntry` | join of above + timestamp; retention per Legal policy |

### 8.3 Cache key

```
cache_key = hash(normalised_redacted_query + "|" + current_corpus_version)
```

Invalidate on corpus publish (global or per-scheme). Determinism: identical key → identical card (E30, E37).

---

## 9. Suggested reference stack (implementation guidance)

Locked decisions for v1 embeddings and vector storage; other layers remain flexible:

| Layer | Choice |
|---|---|
| API | FastAPI / Node (Express) |
| Fetch / parse | `httpx` + BeautifulSoup / Readability |
| **Embeddings** | **`BAAI/bge-large-en-v1.5`** (local via Sentence-Transformers / Hugging Face) |
| **Vector store** | **Chroma DB — local persistent store** (on-disk; no cloud vector DB in v1) |
| BM25 | `rank_bm25` / OpenSearch |
| Reranker | `bge-reranker-base` (or equivalent local cross-encoder) |
| Generator | Small chat model (GPT-4.1-mini / Claude Haiku / local 7–8B) |
| Intent | Lightweight classifier or constrained LLM JSON |
| UI | Next.js / simple React chat · Embeddable iframe widget |
| **Scheduler** | Cron / APScheduler — **`15 9 * * *` Asia/Kolkata** · or Cloud Scheduler with IST |
| Observability | Structured JSON logs + OpenTelemetry |

**Embedding notes (`BAAI/bge-large-en-v1.5`):**

- Dimension: **1024**
- Use cosine similarity in Chroma (normalize embeddings if required by the client)
- For retrieval queries, follow BGE query formatting conventions where applicable (e.g. retrieval instruction prefix if used consistently at ingest and query time)
- Run locally; pin model revision in config for reproducibility across `corpus_version` builds

**Chroma DB (local) notes:**

- Persist under a project data directory (e.g. `data/chroma/`); one collection per published `corpus_version` or a single collection with `corpus_version` metadata + atomic swap
- Store `chunk_id`, `source_id`, `scheme_code`, `plan`, `source_url` as metadata for pre-filtering
- v1 does **not** use Pinecone, Qdrant Cloud, or other managed vector services

**Spend budget on retrieval quality + eval harness, not on a large generative model.**

---

## 10. Deployment topology

```
                    ┌──────────────┐
   Browser / Embed  │  Static UI   │
                    └──────┬───────┘
                           │ HTTPS
                    ┌──────▼───────┐
                    │  API Gateway │  rate limit, TLS, session
                    └──────┬───────┘
                           │
              ┌────────────▼────────────┐
              │     Query service       │
              │  redact · classify ·    │
              │  retrieve · generate ·  │
              │  validate · audit       │
              └─────┬──────────┬────────┘
                    │          │
         ┌──────────▼──┐   ┌───▼────────────┐
         │ Index (RO)  │   │ Model provider │
         │ Chroma local│   │ (gen / class)  │
         │ + BM25+chunks│  └────────────────┘
         └─────────────┘
                    ▲
         ┌──────────┴──────────┐
         │     Scheduler       │  09:15 AM IST daily
         │          │          │
         │          ▼          │
         │  Ingestion worker   │  fetch, parse, approve, publish
         │  + Admin console    │  (+ manual re-run)
         └─────────────────────┘
```

- Query service scales horizontally; index is read-only replicas.
- **Scheduler** fires the ingestion service once per day at **09:15 AM IST**; ingestion is a single-writer publisher to avoid split-brain versions.
- Kill switch (F9.4): feature flags for `global`, `scheme_code`, `intent` without redeploy.

---

## 11. Security, privacy, and compliance controls

| Control | Implementation |
|---|---|
| PII | Edge regex + detector before any persistence or model I/O |
| No account link | Anonymous session id only in v1 |
| Prompt injection | Treat chunk text as data; sanitise at ingest; CI poisoned-HTML fixture |
| Citation allow-list | Validated post-generation; model cannot invent URLs that pass |
| Audit | Reconstruct any answer from logs + corpus version |
| Data residency | India-region storage per NFR |
| Advisory leakage | Zero-tolerance metric; auto-disable intent on confirmed leak |

---

## 12. Evaluation architecture

Tied to CI (PRD F8):

| Suite | Size | Gate |
|---|---|---|
| Golden factual Q&A | ≥ 150 | Launch accuracy ≥ 95% |
| Adversarial refusal | ≥ 100 | Refusal recall ≥ 99% |
| Citation validity | on golden | ≥ 99% |
| Consistency canary | 20 queries / hour | Identical answers for identical inputs |

**Eval loop on corpus change:**

```
corpus publish → run golden + adversarial →
  pass → promote to production pointer
  fail → keep previous corpus_version; alert
```

Do **not** include golden items that require PDF-only facts.

---

## 13. Latency & SLOs (architecture implications)

| Metric | Target | Implication |
|---|---|---|
| TTFT | < 1.2s p50 / < 2.5s p95 | Stream tokens; parallelise retrieve+embed query |
| Full answer | < 3s p50 / < 6s p95 | Keep top-k small; small generator |
| Hard timeout | 8s | Fallback extract / "not in my sources" (E33) |
| Availability | 99.5% | Degrade to retrieval-only snippet mode on LLM outage (E31) |

---

## 14. Failure modes & safe defaults

| Failure | Safe default |
|---|---|
| Retrieval empty / low confidence | "Not in my sources" — never parametric memory |
| Validator fails twice | Safe fallback — never unvalidated text |
| LLM outage | Retrieval-only labelled extract + citation |
| Fetch failure | Keep last good chunks; mark stale |
| Numeric conflict | Withhold answer; alert corpus owner |
| Advisory leak detected | Kill intent / global flag |

**Fail closed** on advice, jailbreaks, and unresolved numerics. **Fail soft** on coverage gaps.

---

## 15. Repository layout (suggested)

```
/
├── problemStatement.md
├── PRD.md
├── docs/
│   └── RAG_Architecture.md          ← this file
├── corpus/
│   └── corpus.yaml                  ← exactly 5 URLs
├── src/
│   ├── ingest/                      # fetch, parse, chunk, embed, publish
│   ├── retrieve/                    # hybrid, rerank, filters
│   ├── generate/                    # prompt, validator, groundedness
│   ├── safety/                      # PII, intent, refusal, lexicon
│   ├── api/                         # query endpoint, streaming
│   └── admin/                       # diffs, kill switch, replay
├── eval/
│   ├── golden/
│   └── adversarial/
├── ui/                              # chat + disclaimer + chips
└── README.md
```

---

## 16. Implementation sequence (architecture milestones)

Aligned with PRD phases, architecture-first:

| Milestone | Deliverable |
|---|---|
| M0 | Freeze `corpus.yaml` (5 URLs); golden + adversarial stubs |
| M1 | Scheduler (09:15 IST daily) + ingestion: HTML fetch → parse → chunk → embed with **`BAAI/bge-large-en-v1.5`** → **Chroma DB local** + BM25; no PDF code path |
| M2 | Hybrid retrieve + rerank + confidence gate with offline eval |
| M3 | Generator + deterministic validator + groundedness |
| M4 | Intent classifier + refusal templates + PII redaction |
| M5 | API + minimal UI + audit log + cache |
| M6 | Numeric approval queue + dead-link monitor + CI gates |

---

## 17. Known architectural limitations (v1)

1. **Five schemes only** — no multi-AMC retrieval.
2. **HTML-only** — attributes present solely in PDFs/images/widgets are unanswered.
3. **Groww as surface** — numbers reflect Groww page content, not a multi-document AMC reconciliation.
4. **English-first** — regional language support is Phase 4.
5. **No personalisation** — no holdings, folio, or account context.
6. **Educational refusal links** are outbound only and not verified by the RAG index.

---

## 18. Traceability to product docs

| Architecture section | Problem statement | PRD |
|---|---|---|
| Allow-list of 5 URLs | Corpus Definition | F1.1, §9.1, Appendix A |
| HTML-only / no PDFs | Constraints | N9, F1.2 |
| Hybrid retrieve + rerank | — | F2, §11 |
| ≤3 sentences, 1 citation, freshness | FAQ requirements | F3, F4, §12 |
| Refusal + edu links | Refusal Handling | F5 |
| PII | Privacy | F6 |
| Eval harness | Success Criteria | F8, Appendix B |
| Minimal UI | UI | F7 |

---

## 19. Open engineering decisions (does not change scope)

| Decision | Recommendation |
|---|---|
| Exact embedding / rerank models | **Resolved for embeddings:** `BAAI/bge-large-en-v1.5` + **Chroma DB local**. Still tune reranker and Mid/Small-cap discrimination on a held-out slice |
| Confidence threshold `τ` | Sweep on golden set; freeze before external launch |
| Intent classifier: rules+LLM vs fine-tuned | Start rules + small LLM JSON; add fine-tune if over-refusal > 5% |
| Structured attribute store | Yes for numeric diffs even if generation stays chunk-based |
| Headless JS rendering for Groww | Prefer static HTML if complete; only add headless if critical fields are client-only — still no PDFs |

---

*End of RAG architecture document.*
