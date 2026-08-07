# Phase 2 Handoff — Facts Desk Ingestion

| Field | Value |
|---|---|
| Phase | 2 — Ingestion pipeline & scheduler |
| Status | **Conditionally complete** — exit criteria mostly met; open defects below |
| Current published pointer | `corpus_version=2026-08-07.6` · `facts_desk_2026_08_07_6` · **10 chunks** |
| Embedding / store | `BAAI/bge-large-en-v1.5` · Chroma DB local (`data/chroma/`) |
| Handoff date | 07 August 2026 |
| Sources | [`implementationplan.md`](../implementationplan.md) · [`docs/RAG_Architecture.md`](RAG_Architecture.md) · [`PRD.md`](../PRD.md) |

---

## 1. Exit criteria status

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | One successful end-to-end ingest of all **five** pages | **PASS** | `data/published/current.json` → `2026-08-07.6`; ingest log shows all five `src_00*` `status: fetched` / later `unchanged`; `chunk_count: 10` |
| 2 | Chunks embedded with **`BAAI/bge-large-en-v1.5`** in **Chroma DB local** | **PASS** | Pointer `embedding_model` / `chroma_collection: facts_desk_2026_08_07_6`; persist path `data/chroma/` |
| 3 | Indexes queryable offline (Chroma `scheme_code` filter + BM25) | **PASS** | `python -m src.ingest.cli smoke` returned Mid Cap BM25 + Chroma hits (run during Phase 2) |
| 4 | Re-ingest with unchanged hash skips rebuild for that source | **PASS** (with caveat) | After stable-hash fix, re-run showed all five `"status": "unchanged"`. Caveat: hash ignores parser/chunker-only changes — see Known Issues |
| 5 | Scheduler **09:15 AM IST**; manual run documented | **PASS** (partial) | `corpus.yaml` + `scheduler.py` cron `15 9 * * *` `Asia/Kolkata`; CLI `schedule` implemented. **Not proven in production** (no observed 09:15 fire logged) |
| 6 | **Zero** PDF libraries / PDF code paths | **PASS** | `requirements.txt` has no PDF deps; fetcher rejects PDF content-type / `.pdf` URLs |
| 7 | Failed fetch leaves previous `corpus_version` intact | **PASS** (code path) | `pipeline._process_source` reuses prior chunks on fetch failure; empty build refuses pointer flip. **Not chaos-tested** with forced 5xx in this handoff |
| 8 | No cloud vector DB | **PASS** | `chromadb.PersistentClient(path=data/chroma)` only |

**Honest summary:** Functional ingest works. Several architecture promises (atomic publish isolation, redirect semantics, full-page section coverage, scheduled job observation) are **unverified or incomplete** — see §5.

---

## 2. Files created / touched (by directory)

### `src/ingest/`

| File | Role |
|---|---|
| `__init__.py` | Exports `run_ingestion` |
| `paths.py` | Roots, Chroma/embed constants, chunk word caps |
| `corpus_loader.py` | Load/validate `corpus.yaml` (html_only, 5 URLs) |
| `fetcher.py` | Allow-listed HTML GET; charset-aware decode; raw HTML persist |
| `hasher.py` | `content_hash` over **stable `__NEXT_DATA__` fund fields** (not full HTML body) |
| `parser.py` | `__NEXT_DATA__` + HTML sections; units; holdings/compare exclusions |
| `chunker.py` | Section chunks, mojibake asserts, exclusions |
| `diffing.py` | Attribute snapshots + numeric-diff **logging only** (no approval UI) |
| `embedder.py` | Sentence-Transformers `BAAI/bge-large-en-v1.5` |
| `indexes.py` | `chunks.jsonl` (`ensure_ascii=True`), BM25, Chroma publish, smoke helpers |
| `pipeline.py` | Orchestration + publish pointer write |
| `scheduler.py` | APScheduler blocking cron |
| `cli.py` | `run` / `schedule` / `smoke` |

### `corpus/`

| File | Role |
|---|---|
| `corpus.yaml` | Five-URL allow-list, scheduler, embed/store locks |
| `scheme_aliases.yaml` | Draft aliases (Phase 1; unused by ingest runtime) |

### `data/` (runtime; gitignored contents)

| Path | Role |
|---|---|
| `raw/{src_id}/` | Latest + stamped HTML + `latest_meta.json` |
| `hashes/{src_id}.json` | Last `content_hash` / verified timestamps |
| `staging/{corpus_version}/` | `chunks.jsonl`, `bm25.*`, `attributes/`, `manifest.json` — **all versions retained here** |
| `chroma/` | Persistent Chroma collections (multiple version-named collections may accumulate) |
| `published/current.json` | Soft pointer to “current” version (not a full copy of artefacts) |
| `logs/ingest_*.json` | Per-run logs |
| `diffs/` | Numeric-diff logs when fields change |

### `docs/`

| File | Role |
|---|---|
| `PHASE2_INGEST.md` | Implementation notes / defect fix journal |
| `PHASE2_HANDOFF.md` | This handoff |

### Root

| File | Role |
|---|---|
| `requirements.txt` | Phase 2 Python deps |
| `README.md` | Ingest commands (updated during Phase 2) |
| `implementationplan.md` | Exit criteria marked complete (revisit against Known Issues) |

---

## 3. Key decisions

| Topic | Decision |
|---|---|
| **Chunking params** | `CHUNK_MIN_WORDS=40`, `CHUNK_MAX_WORDS=350`, `CHUNK_OVERLAP_WORDS=40` (`paths.py`). Target ~300–600 tokens ≈ word cap ~350. |
| **Holdings exclusion** | Drop sections whose heading matches `\bholdings?\b`. Not an answerable intent (PRD §9.1); oversized tables blew past the token budget. |
| **Comparison exclusion** | Drop headings matching compare / similar funds / other funds. Comparison is **refusable** (PRD §9.2); must not be retrievable. |
| **JSON encoding** | `chunks.jsonl` (and attribute JSON) use **`ensure_ascii=True`** so ₹ is stored as `\u20b9`. Avoids cp1252 viewers showing `â‚¹` when raw UTF-8 rupee bytes are mis-decoded. In-memory / `json.loads` still yield U+20B9. |
| **Scheme display name** | Taken from Groww `mfServerSideData.scheme_name`, not from `corpus.yaml` `display_name`. |
| **Change detection** | Hash = SHA-256 of selected stable `__NEXT_DATA__` fields (`hasher._STABLE_KEYS`), not full HTML (HTML was too volatile). |
| **Numeric gate** | Diffs logged only; **no** human approval hold (Phase 6). |
| **Scheduler mechanism** | **APScheduler** `BlockingScheduler` + `CronTrigger(15 9 * * *, timezone=Asia/Kolkata)`. Process must stay running (`cli schedule`). Not OS Task Scheduler / systemd. |
| **Publish model** | Write under `data/staging/{version}/`, then flip `data/published/current.json` via temp+replace. Staging history not pruned; Chroma collections per version name left in place. |

---

## 4. Commands

From repo root (`d:\NextLeap\Rag Architecture`):

```bash
# deps (once)
python -m pip install -r requirements.txt

# one-shot ingest
python -m src.ingest.cli run

# force re-parse/chunk/embed even if content_hash unchanged
python -m src.ingest.cli run --force

# skip BGE/Chroma (chunk + BM25 only) — debug
python -m src.ingest.cli run --skip-embed

# smoke BM25 + Chroma against published pointer
python -m src.ingest.cli smoke

# block and fire daily at 09:15 Asia/Kolkata
python -m src.ingest.cli schedule
```

Inspect pointer:

```bash
python -m json.tool data/published/current.json
```

---

## 5. Known issues

### Must-track (handoff requirements)

1. **`src_002` scheme_name vs allow-list URL**  
   Chunks for `src_002` use `scheme_name`: **"HDFC Flexi Cap Direct Plan Growth"** while `corpus.yaml` allow-lists URL `…/hdfc-equity-fund-direct-growth` and `display_name`: "HDFC Equity Fund Direct Growth".  
   - `scheme_code` metadata remains `hdfc_equity_direct_growth`.  
   - **Redirect policy verification unconfirmed** (fetcher requires final URL ∈ allow-list; unclear whether Groww redirects or serves a renamed product on the equity slug).  
   - **Scope decision pending with owner** — treat as Equity alias, Flexi Cap rename, or corpus/label update?

2. **`content_hash` does not rebuild on parser-only changes**  
   Required note: *“content_hash appears computed on raw HTML, so parser changes do not trigger rebuild.”*  
   **Factual clarification:** current `hasher.py` hashes **stable `__NEXT_DATA__` fund fields** extracted from the HTML, **not** the full raw HTML body (full-body hashing was abandoned because Groww HTML is volatile).  
   **Effect is the same for engineering:** unit formatting, holdings/compare exclusions, and chunker edits **do not** change the hash → re-ingest reports `unchanged` and skips parse/chunk unless **`python -m src.ingest.cli run --force`**.

3. **Atomic publish unverified**  
   Pointer flip uses write-temp + `Path.replace`, but:  
   - **All versions remain under `data/staging/`** (`.1` … `.6` observed).  
   - No sealed `data/published/{version}/` copy of chunks/BM25.  
   - Old Chroma collections are not deleted on publish.  
   - Mid-failure / crash consistency **not** formally tested. Treat “atomic publish” as **incomplete**.

4. **Thin page coverage after exclusions**  
   Latest build keeps **~2 chunks per page** (typically Investment details + one narrative section). Holdings and compare sections stripped by design. **Parser coverage of remaining page headings is not audited** — risk of missing answerable attributes that only appear outside `__NEXT_DATA__` / retained headings.

### Additional shortcuts / gaps (honest)

| Issue | Detail |
|---|---|
| Model revision unpinning | `SentenceTransformer("BAAI/bge-large-en-v1.5")` — **no commit/revision pin** in config |
| Scheduler not observed | `schedule` never left running through a real 09:15 IST tick in this phase |
| Fail-soft fetch | Reuse-previous-chunks on error coded; **not** integration-tested with induced outages |
| Numeric approval | Diff logging only; silent numeric publish still possible |
| Alias map unused | `scheme_aliases.yaml` not consulted during ingest |
| Encoding history | `.5` wrote raw UTF-8 ₹ bytes (`ensure_ascii=False`); cp1252 viewers showed `â‚¹`. Fixed in `.6` via `ensure_ascii=True` |
| implementationplan.md | Exit criteria marked all `[x]` — this handoff **downgrades confidence** on atomic publish, scheduler observation, and src_002 scope |
| Chroma query quality | Smoke showed investment-details hits; no systematic retrieval eval (Phase 3) |

---

## 6. Current corpus snapshot

| Source | Allow-listed URL slug | Chunk `scheme_name` (from Groww) | Chunks in `.6` |
|---|---|---|---|
| `src_001` | `hdfc-mid-cap-fund-direct-growth` | HDFC Mid Cap Fund Direct Growth | 2 |
| `src_002` | `hdfc-equity-fund-direct-growth` | **HDFC Flexi Cap Direct Plan Growth** | 2 |
| `src_003` | `hdfc-small-cap-fund-direct-growth` | HDFC Small Cap Fund Direct Growth | 2 |
| `src_004` | `hdfc-nifty-50-index-fund-direct-growth` | HDFC NIFTY 50 Index Fund Direct Growth | 2 |
| `src_005` | `hdfc-balanced-advantage-fund-direct-growth` | HDFC Balanced Advantage Fund Direct Growth | 2 |
| | | **Total** | **10** |

---

## 7. Recommended owner actions before Phase 3

1. Decide **src_002** Equity vs Flexi Cap labelling / URL policy.  
2. Decide whether parser/chunker version should join `content_hash` (or always `--force` after ingest code changes).  
3. Audit retained headings vs PRD answerable intents; expand section keep-list if needed.  
4. Harden publish (prune or isolate staging; Chroma collection GC; crash tests).  
5. Run one observed `schedule` cycle or document ops ownership of the blocking process.

---

*End of Phase 2 handoff.*
