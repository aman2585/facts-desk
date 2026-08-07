# Intent Taxonomy (v1) — Facts Desk

| Field | Value |
|---|---|
| Status | Frozen for Compliance review (Phase 1) |
| Corpus | Five Groww HDFC Direct Growth scheme pages (HTML only) |
| Sources | [`PRD.md`](../PRD.md) §9 · [`problemStatement.md`](../problemStatement.md) |
| Last updated | 05 August 2026 |

> **Facts-only. No investment advice.**  
> This taxonomy is contractual for v1. Changes require Compliance re-approval.

---

## 1. Coverage boundary

Answers may only be grounded in content published on these pages:

| Source ID | Scheme | URL |
|---|---|---|
| `src_001` | HDFC Mid Cap Fund Direct Growth | https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth |
| `src_002` | HDFC Equity Fund Direct Growth | https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth |
| `src_003` | HDFC Small Cap Fund Direct Growth | https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth |
| `src_004` | HDFC Nifty 50 Index Fund Direct Growth | https://groww.in/mutual-funds/hdfc-nifty-50-index-fund-direct-growth |
| `src_005` | HDFC Balanced Advantage Fund Direct Growth | https://groww.in/mutual-funds/hdfc-balanced-advantage-fund-direct-growth |

If an attribute is not present on the page → **"not in my sources"** (coverage gap), not a guessed answer.  
No PDF / SID / KIM / factsheet / open-web retrieval.

---

## 2. Answerable intents

| Intent ID | Intent | Example query | Notes |
|---|---|---|---|
| `expense_ratio` | Expense ratio (TER) | What's the expense ratio of HDFC Mid Cap Direct? | Direct plan only in corpus |
| `exit_load` | Exit load | Is there an exit load if I redeem after 8 months? | |
| `min_sip` | Minimum SIP / investment | What's the minimum SIP amount? | |
| `min_additional` | Minimum additional purchase | Can I add ₹300 to my folio? | Only if published on page |
| `lock_in` | Lock-in period | Does this scheme have a lock-in? | Only if published on page |
| `riskometer` | Riskometer | What's the riskometer for this scheme? | |
| `benchmark` | Benchmark index | What is this fund benchmarked against? | |
| `category` | Scheme category | Is this a mid-cap or a small-cap? | |
| `fund_manager` | Fund manager | Who manages this scheme? | Only if published on page |
| `plan_option` | Plan / option availability | Does it have an IDCW option? | Only if published on page |
| `aum` | AUM / other page attributes | What is the AUM of this fund? | Only if published on page |
| `definition_on_page` | Definition as applied to scheme | What is the exit load for this scheme? | Must still cite scheme page |

Classifier label for these when in scope: `factual_in_scope`.

---

## 3. Refusable / non-answer intents

| Intent ID | Class | Example | Handling |
|---|---|---|---|
| `advisory` | Advisory | Should I invest in this fund? | Refuse + SEBI/AMFI education link |
| `comparative` | Comparative | Which is better, Mid Cap or Small Cap? | Refuse + education link |
| `predictive` | Predictive | Will this give 15% next year? | Refuse |
| `suitability` | Suitability / personal | I'm 30, what's a good portfolio? | Refuse + RIA pointer |
| `performance` | Performance & returns | What were 3-year returns? | No figures inline; link Groww scheme page only |
| `calculation` | Calculation / projection | How much will ₹5,000/month become? | Refuse |
| `timing` | Timing advice | Should I redeem now or wait? | Refuse |
| `personal_account` | Account-specific | What's my current balance? | Refuse; never request identifiers |
| `out_of_domain` | Out of domain | What's the weather? | Scope reminder |
| `pii_bearing` | PII-bearing | My PAN is ABCDE1234F, check my folio | Redact, warn, refuse account part |
| `uncovered_scheme` | Outside corpus | What's the TER of SBI Bluechip? | Coverage limit (five schemes only) |
| `ambiguous` | Ambiguous scheme | What's the exit load of the HDFC fund? | One clarifying question (≤3 chips) |

Educational links used in refusals are **not** part of the ingestion corpus.

---

## 4. Response contract (all answerable intents)

- ≤ 3 sentences  
- Exactly **one** citation URL from the five allow-listed sources  
- Footer: `Last updated from sources: <DD Mon YYYY>`  
- No hedging, advice, comparisons, or invented numbers  

---

## 5. Compliance sign-off

| Role | Sign-off | Date |
|---|---|---|
| Product | Pending | |
| Compliance | Pending | |
| Legal | Pending | |

---

*End of intent taxonomy v1.*
