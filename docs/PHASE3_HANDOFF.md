# Phase 3 Handoff — Facts Desk Hybrid Retrieval

| Field | Value |
|---|---|
| Phase | 3 — Hybrid retrieval |
| Status | **Conditionally complete** — exit criteria met on thin corpus; metrics need honest reading (below) |
| Current published pointer | `corpus_version=2026-08-07.7` · `facts_desk_2026_08_07_7` · **10 chunks** (2 per scheme) |
| Embedding / store / rerank | `BAAI/bge-large-en-v1.5` · Chroma local · `BAAI/bge-reranker-base` |
| Default τ | `0.0` in [`src/retrieve/config.yaml`](../src/retrieve/config.yaml) — **untuned** |
| Handoff date | 07 August 2026 |
| Sources | [`implementationplan.md`](../implementationplan.md) · [`docs/RAG_Architecture.md`](RAG_Architecture.md) · [`PRD.md`](../PRD.md) · [`docs/PHASE2_HANDOFF.md`](PHASE2_HANDOFF.md) |

---

## 1. What was built

End-to-end **retrieval-only** path (no LLM generation, no refusals UI):

```
query → normalise (abbrev + aliases)
      → uncovered / ambiguous short-circuit
      → metadata pre-filter (scheme_code + plan=Direct when resolved)
      → hybrid (Chroma dense top-k ∪ BM25 top-k)
      → cross-encoder rerank (top 3–5)
      → confidence gate (τ)
      → status: ok | gate_fail | ambiguous | uncovered | unresolved
```

### `src/retrieve/`

| File | Role |
|---|---|
| `config.yaml` / `config.py` | Tunable `tau`, top-k, model names |
| `normaliser.py` | Abbreviation expansion; scheme alias map; out-of-corpus AMC patterns (**before** alias match) |
| `store.py` | Load published pointer, chunks, BM25, Chroma collection |
| `hybrid.py` | Dense + BM25 union with optional metadata filter |
| `rerank.py` | `CrossEncoder("BAAI/bge-reranker-base")` |
| `gate.py` | τ gate + multi-scheme → `ambiguous` |
| `pipeline.py` | `retrieve()` orchestration |
| `cli.py` | Smoke CLI |

### `scripts/`

| File | Role |
|---|---|
| `validate_phase3.py` | Offline eval: recall@5 overall + **per intent**, Mid Cap↔Small Cap / Equity↔BAF confusion, τ sweep + out-of-corpus negatives |

### Related (owner decisions during Phase 3)

| Change | Notes |
|---|---|
| `src/ingest/hasher.py` + `paths.PARSER_CHUNKER_VERSION` | `content_hash` now includes parser/chunker version so logic changes invalidate skip-rebuild |
| `parser` / `chunker` | Explicit **performance/returns** heading exclusion + return-figure assert (pre–Phase 3 fix) |
| `README.md` | `src_002` Flexi Cap = Groww display rename; URL / `scheme_code` unchanged |

---

## 2. Commands

```bash
# Smoke one query against published index
python -m src.retrieve.cli "What is the expense ratio of HDFC Mid Cap Fund Direct Growth?"

# Offline retrieval eval (honest metrics + τ sweep)
python scripts/validate_phase3.py
```

Published pointer: `data/published/current.json`  
Config: `src/retrieve/config.yaml`

---

## 3. Exit criteria status

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | Golden factual queries: correct source in top-5 | **PASS*** | recall@5 = **32/32 (1.000)** with default filter ON; also per-intent all 1.000 |
| 2 | Mid Cap vs Small Cap / Equity vs BAF confusion measured | **PASS** | Top-1 2×2 matrices: **0** cross-confusions (filter ON) |
| 3 | Low-confidence → gate-fail / explicit signal | **PARTIAL** | Negatives safe via **alias/uncovered resolver**, not τ — see Known Issues |
| 4 | Uncovered / unresolved → explicit signal, not wrong guess | **PARTIAL** | Known AMCs (`SBI`, `Axis`, …) → `uncovered`. **Unrecognised** names can still retrieve silently |

\*See §4 caveats — recall@5 on this corpus is **not** a strong discriminator.

---

## 4. Eval results (honest reading)

### 4.1 Headline numbers (`scripts/validate_phase3.py`, filter ON, τ=0.0)

| Metric | Value |
|---|---|
| recall@5 overall | **32/32 = 1.000** |
| recall@5 per intent | All intents **1.000** (expense_ratio, exit_load, min_sip, …) |
| MRR (source) | **1.000** |
| Mid Cap ↔ Small Cap (top-1) | 0 confusions (n=14) |
| Equity ↔ BAF (top-1) | 0 confusions (n=12) |
| Negatives safe @ τ=0 | 6/6 (via resolver short-circuit) |

### 4.2 Caveat — recall@5 = 1.000 is corpus-size-limited

Published index has **10 chunks**. With `rerank_top_k=5`, top-5 returns **half the entire corpus**. When the scheme pre-filter resolves, the candidate pool is only **2 chunks** for that scheme — so “correct source in top-5” is nearly automatic once the alias resolves.

**Do not treat recall@5=1.000 as evidence of strong retrieval quality.** Prefer:

| Stronger check | Result (filter **OFF**) |
|---|---|
| **recall@1 overall** | **27/32 = 0.844** |
| recall@1 misses | All **5** misses are `src_002` (Equity) — often ranked under Nifty 50 / Mid Cap without the filter |

Per-intent recall@1 (filter OFF): expense_ratio 1.000; exit_load 0.833; min_sip / riskometer / benchmark 0.800; category 0.667.

### 4.3 Intent not discriminated within a scheme

For Mid Cap / Small Cap / Nifty 50 / BAF, an **expense-ratio** query and an **exit-load** query return the **same top-1 chunk** (`{src}::c_001` — Investment details). That chunk holds nearly all structured KV facts.

| Scheme | expense top-1 | exit-load top-1 | Same chunk? |
|---|---|---|---|
| Mid Cap | `src_001::c_001` | `src_001::c_001` | Yes |
| Equity | `src_002::c_001` | `src_004::c_001` | No (scheme miss, not intent split) |
| Small Cap | `src_003::c_001` | `src_003::c_001` | Yes |
| Nifty 50 | `src_004::c_001` | `src_004::c_001` | Yes |
| BAF | `src_005::c_001` | `src_005::c_001` | Yes |

**Implication for Phase 4:** retrieval cannot be assumed to isolate “the exit-load sentence” vs “the TER sentence”. **Fact-level / numeric accuracy must be measured on the golden set at generation+validation time**, not inferred from retrieval recall.

### 4.4 τ sweep (summary)

Rerank scores on golden are mostly ~0.7–1.0 (one Equity category ~0.21). At `tau=0.0`, golden_ok=32 and gate_fail=0. Raising τ toward 0.5–1.0 starts rejecting in-scope Equity items before it reliably rejects dangerous negatives (see Known Issues).

---

## 5. Known Issues

### Must-track (Phase 3)

1. **`tau=0.0` does not gate**  
   Default config never fails the confidence gate on scored candidates. Coverage gaps / low-confidence paths are not enforced by τ today.

2. **Negatives can score high; alias resolver is the real safety net**  
   Forced hybrid+rerank (bypassing uncovered short-circuit) on out-of-corpus queries:
   - Axis Midcap exit load → top score **~0.781** (hits Mid Cap Investment details)
   - Kotak Flexicap TER → top score **~0.725** (hits Equity Investment details)
   - Ambiguous “the HDFC fund” → **~0.960** if forced  
   These would **pass any τ ≤ ~0.78**. They are caught only because `normaliser` maps known foreign AMCs / ambiguous phrases to `uncovered` / `ambiguous` **before** search.  
   **Silent failure path:** an **unrecognised** scheme/AMC name (not in the uncovered pattern list) can resolve as `unresolved`, retrieve across the corpus, and return `ok` with a wrong scheme’s Investment-details chunk.

3. **τ untuned pending a larger corpus**  
   Do not bake an eval-optimized τ into CI until chunk count / section coverage grows and filter-off recall@1 (and Phase 4 fact accuracy) are the targets. Sweep lives in `validate_phase3.py` for observation only.

4. **Thin corpus / mega-KV chunk**  
   ~2 chunks per scheme; most answerable intents live in one Investment-details blob. Hybrid+rerank cannot separate intents inside that blob.

5. **Equity (`src_002`) is the hard scheme without the filter**  
   Groww display name “Flexi Cap” vs corpus “Equity”; filter-off recall misses concentrate here. Alias + filter mask the issue in the headline recall@5.

### Carried forward from Phase 2 ([`PHASE2_HANDOFF.md`](PHASE2_HANDOFF.md))

| Issue | Status entering Phase 4 |
|---|---|
| **`src_002` scheme_name vs URL** | **Owner decision recorded:** keep `scheme_code` / URL; Flexi Cap is Groww display rename (README note). Still a retrieval/UX footgun. |
| **`content_hash` ignored parser-only changes** | **Mitigated in code:** hash envelope now includes `PARSER_CHUNKER_VERSION`. Still need `--force` (or version bump) after ingest logic changes; `.7` may predate some hash bumps. |
| **Atomic publish incomplete** | Staging versions + old Chroma collections accumulate; no sealed `published/{version}/` copy; crash consistency untested. |
| **Thin page coverage after exclusions** | Still ~2 chunks/page; holdings/compare/performance dropped by rule; many HTML headings flush empty (widget/div-only). |
| Embedding model revision unpinned | Still `SentenceTransformer("BAAI/bge-large-en-v1.5")` without commit pin. |
| Scheduler not observed at real 09:15 IST | Unchanged. |
| Fail-soft fetch not chaos-tested | Unchanged. |
| Numeric approval = log only | Unchanged (Phase 6). |

---

## 6. Recommended owner actions before / during Phase 4

1. Measure **fact-level golden accuracy** in generation (Phase 4) — do not rely on Phase 3 recall@5.
2. Expand uncovered-scheme patterns or add a stricter “must resolve to one of five” gate before `ok`.
3. Tune τ only after corpus growth or attribute-level chunking; keep reporting filter-off recall@1.
4. Continue Phase 2 publish hardening and scheduler observation.
5. Consider splitting Investment-details KV into per-attribute chunks if intent-level retrieval becomes a product requirement.

---

## 7. Traceability

| Phase 3 work item | Location |
|---|---|
| Query normaliser | `src/retrieve/normaliser.py` |
| Metadata pre-filter + hybrid | `src/retrieve/hybrid.py` |
| Rerank | `src/retrieve/rerank.py` |
| Confidence gate + ambiguity | `src/retrieve/gate.py` |
| Offline eval | `scripts/validate_phase3.py` |
| Tunable τ | `src/retrieve/config.yaml` |

---

## 8. Golden set verification (2026-08-07)

The golden factual set (`eval/golden/items.json`, n=32) is now **human-verified**.

| Field | Value |
|---|---|
| `verified_by` | `AMAN` |
| `verified_on` | `2026-08-07` |
| `verification_status` | `verified` |
| Corpus reference | `2026-08-07.7` Investment-details chunk KVs (aligned to live Groww pages as of that date) |
| Suite version | `2026-08-07.verified` |

Placeholder `[STUB — verify on Groww]` answers were replaced with the published attribute values (TER, exit load, min SIP, riskometer, benchmark, category, fund manager, AUM, lock-in). Phase 4 fact-level accuracy eval should use these as ground truth.

---

*End of Phase 3 handoff.*
