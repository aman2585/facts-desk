# Phase 5 Handoff — Facts Desk API, Cache & Audit (Part 1)

| Field | Value |
|---|---|
| Phase | 5 — API, minimal UI & audit |
| Status | **Part 1 complete** — `src/api/` query surface shipped; **Part 2 (UI) not started** |
| Current published pointer | `corpus_version=2026-08-07.7` · `facts_desk_2026_08_07_7` · **10 chunks** (unchanged) |
| API | FastAPI · `POST /ask` (SSE default / JSON via `stream=false`) · session id only |
| Handoff date | 07 August 2026 |
| Sources | [`implementationplan.md`](../implementationplan.md) · [`docs/RAG_Architecture.md`](RAG_Architecture.md) · [`PRD.md`](../PRD.md) · [`docs/PHASE4_HANDOFF.md`](PHASE4_HANDOFF.md) · [`docs/PHASE3_HANDOFF.md`](PHASE3_HANDOFF.md) · [`docs/PHASE2_HANDOFF.md`](PHASE2_HANDOFF.md) |

---

## 1. What Part 1 built

Query API only — **no UI**. UI switches on card `type`; never parses prose.

```
Client
  → POST /ask (X-Session-Id or body.session_id; mint if missing)
  → rate limit (session + IP)
  → cache lookup hash(normalised_redacted_query + "|" + corpus_version)
       ├─ hit  → status cache_hit → identical card → audit (path=cache)
       └─ miss → ask pipeline → card → cache write → audit
  → SSE: status → card → done   |   JSON: {session_id, cache_hit, card, …}
```

### `src/api/`

| File | Role |
|---|---|
| [`app.py`](../src/api/app.py) | FastAPI `POST /ask`, `/health`; SSE streaming; `X-Session-Id` header |
| [`service.py`](../src/api/service.py) | Orchestrates cache → `ask()` → card assemble → audit |
| [`cards.py`](../src/api/cards.py) | Discriminated union: `answer` · `refusal` · `coverage` · `performance_redirect` · `clarify` · `api_error` |
| [`cache.py`](../src/api/cache.py) | SHA-256 key; wipe when published `corpus_version` changes; `invalidate_cache()` for publish hook |
| [`audit.py`](../src/api/audit.py) | JSONL audit store; `iter_audit()` by session / since |
| [`rate_limit.py`](../src/api/rate_limit.py) | Sliding window per session + IP (F6.6) |
| [`session.py`](../src/api/session.py) | Anonymous session id only — no login / account link (F6.3) |
| [`config.yaml`](../src/api/config.yaml) · [`config.py`](../src/api/config.py) | Rate limits, cache/audit dirs, `stream_default` |
| [`cli.py`](../src/api/cli.py) | `python -m src.api.cli` → uvicorn |

### Runtime paths

| Artefact | Location |
|---|---|
| Response cache | `data/cache/responses/{sha256}.json` |
| Audit log | `data/logs/audit/audit_YYYY-MM-DD.jsonl` |
| Published pointer (cache invalidation watch) | `data/published/current.json` |

### Commands

```bash
python -m pip install -r requirements.txt
python -m src.api.cli --host 127.0.0.1 --port 8000

# JSON (non-stream)
curl -s -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d "{\"query\":\"What is the expense ratio of HDFC Mid Cap Fund?\",\"stream\":false}"

# SSE (default)
curl -N -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d "{\"query\":\"Should I invest in HDFC Mid Cap Fund?\"}"
```

---

## 2. Verified behaviour (Part 1)

| Check | Result | Evidence |
|---|---|---|
| **Answer card** with citation + freshness footer | **PASS** | Audit `87dcd6a1-…`: `type=answer`, TER `0.75%`, allow-listed Groww URL, `freshness_date=07 Aug 2026`, `source_label` present |
| **Refusal card** with educational link | **PASS** | Audit `78b18ed8-…` (advisory): `type=refusal`, `educational_url=https://investor.sebi.gov.in/` |
| **PII refusal** — `educational_url` null; raw PII never on disk | **PASS** | Audit `a3418530-…`: `intent=pii_bearing`, `educational_url=null`, `redacted_query` contains `<PAN_REDACTED>` only (no raw PAN in audit/cache) |
| **Cache hit** returns identical card via distinct `cache_hit` stage | **PASS** | Repeat Mid Cap TER → SSE `status.stage=cache_hit`; audit `f5d5f4c7-…` has `cache_hit=true`, `path=cache`, same answer text/citation as miss |
| **Audit row** sufficient to replay a decision | **PASS** | e.g. `87dcd6a1-…`: redacted query, intent, chunk ids, corpus_version, response card, citation, validator_verdicts, model_version, groundedness, timestamp, session_id |

Card contract (UI must switch on `type` only):

| `type` | Key fields |
|---|---|
| `answer` | `text`, `citation_url`, `source_label`, `freshness_date` |
| `refusal` | `text`, `educational_url` (**may be null**) |
| `coverage` | `text`, optional citation |
| `performance_redirect` | `text`, `scheme_url` |
| `clarify` | `text`, `options[]` (`scheme_code`, `label`, `url`) |
| `api_error` | `text`, `status_code` |

---

## 3. What Part 2 needs

Maps to implementation plan Phase 5 work items 4–7 · PRD F7, F8.1.

1. **Minimal chat UI** (`ui/`) — welcome, three example chips, mobile-first, loading / streamed SSE consumption.
2. **Six card types** — render by `card.type` only; never scrape answer prose for links or dates.
3. **Persistent disclaimer** — **“Facts-only. No investment advice.”** visible without scrolling.
4. **Feedback thumbs** (F8.1) — up/down + reason chips (`wrong number` / `outdated` / `not what I asked` / `no source` / `other`); link to `audit_id` / `session_id`.
5. **Clarify chips** — up to 3 (API currently returns all five scheme `options` on `clarify`); chip tap re-asks with chosen scheme.
6. **Copy answer + citation** — support-friendly clipboard of text + source URL / freshness.

**Still out of scope for Phase 5:** admin console, numeric approval UI, kill switch (Phase 6).

---

## 4. Known Issues

### Phase 5 Part 1 (new)

1. **Groundedness overlap is a weak signal on terse answers**  
   One-sentence replies can pass with very small token sets (e.g. audit `87dcd6a1-…`: `token_count=5`, `overlap_ratio=1.0`). Do not treat high overlap alone as strong claim coverage when the answer is short.

2. **Refusal cards may have `educational_url: null`**  
   PII / personal-account / some predictive paths return refusal **without** an edu link. UI must not assume the link exists — render text-only when null (verified: `a3418530-…`).

### Carried forward from Phase 4 ([`PHASE4_HANDOFF.md`](PHASE4_HANDOFF.md))

| Issue | Status entering Part 2 / Phase 6 |
|---|---|
| **g002** grounded-fail (Equity TER) | Unchanged — optional polish; not a Phase 4 reopen |
| Groq free-tier rate limits | Unchanged — `api_error` path + backoff |
| `tau=0.0` ungated | Unchanged |
| Mega-KV / thin corpus (~2 chunks/scheme) | Unchanged |

### Carried forward from Phase 3 ([`PHASE3_HANDOFF.md`](PHASE3_HANDOFF.md))

| Issue | Status |
|---|---|
| Negatives score high if forced past uncovered short-circuit | Unchanged — resolver is the safety net; unrecognised names still residual risk |
| τ untuned | Unchanged |
| Equity / Flexi Cap naming footgun | Unchanged |
| Filter-off recall@1 = 0.844; recall@5 not discriminative | Unchanged — corpus still 10 chunks |

### Carried forward from Phase 2 ([`PHASE2_HANDOFF.md`](PHASE2_HANDOFF.md))

| Issue | Status |
|---|---|
| `src_002` Flexi Cap display vs Equity URL / `scheme_code` | Owner decision stands; UX footgun for Part 2 copy/chips |
| Atomic publish incomplete | Staging/old Chroma accumulate; crash consistency untested |
| Embedding model revision unpinned | Unchanged |
| Scheduler not observed at real 09:15 IST | Unchanged |
| Fail-soft fetch not chaos-tested | Unchanged |
| Numeric approval = log only | Phase 6 |
| Thin page coverage after exclusions | Unchanged (~2 chunks/scheme) |

---

## 5. Recommended owner actions for Part 2

1. Build `ui/` against the six card types; gate edu-link / citation / freshness on field presence.
2. Wire thumbs → audit (`audit_id` from SSE `done` / JSON body).
3. Optionally call `invalidate_cache()` from ingest publish (API already wipes on next request when `corpus_version` flips).
4. Keep Phase 2–4 residuals visible; do not block Part 2 UI on g002 / τ / publish hardening.

---

## 6. Traceability

| Phase 5 Part 1 work item | Location |
|---|---|
| `POST /ask` + streaming | `src/api/app.py` |
| Session id only | `src/api/session.py` |
| Rate limit | `src/api/rate_limit.py` |
| Response cache (F3.5) | `src/api/cache.py` |
| Audit log (F6.5; F8.1 linkage ready) | `src/api/audit.py` · `data/logs/audit/` |
| Discriminated cards | `src/api/cards.py` |
| Ask orchestration | `src/api/service.py` |

---

## 7. Definition of done

| # | Requirement | Status |
|---|---|---|
| 1 | Part 1: API + cache + audit + typed cards | **Met** |
| 2 | Part 2: minimal UI + disclaimer + feedback + clarify + copy | **Not started** |
| 3 | Phase 5 exit criteria in implementation plan (UI-facing) | **Blocked on Part 2** |

---

*End of Phase 5 handoff (Part 1).*
