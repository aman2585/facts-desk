# PRD — Mutual Fund FAQ Assistant ("Facts Desk")

**A facts-only, citation-backed Q&A assistant for mutual fund schemes**

| Field | Value |
|---|---|
| Document version | v1.1 (Draft for review) |
| Status | Proposed — pending Compliance + Legal sign-off |
| Product surface | Web app (embeddable widget + standalone page) |
| Reference product context | Groww (investment platform) |
| Core technology | Retrieval-Augmented Generation (RAG) over a fixed corpus of 5 Groww scheme pages (HTML only; no PDFs) |
| Author | Product |
| Reviewers | Engineering, Design, Compliance, Legal, Customer Support Ops, Content |
| Last updated | 05 August 2026 |

---

## 1. TL;DR

Retail mutual fund investors ask the same ~200 objective questions over and over — *what is the exit load, what is the minimum SIP, what is the benchmark for this scheme.* Today those answers are scattered across 60-page Scheme Information Documents, PDF factsheets that change monthly, AMC help centres, AMFI circulars and SEBI master circulars. Users instead ask Google, Reddit, YouTube, WhatsApp uncles and general-purpose chatbots — and get answers that are stale, wrong, or quietly advisory.

**Facts Desk** is a narrow, deliberately unambitious assistant. It answers only objective, verifiable questions about **five fixed HDFC Direct Growth schemes**, exclusively from a curated allow-list of **five Groww scheme-page URLs (HTML only; no PDFs)**. Every answer is ≤3 sentences, carries exactly one source link (one of those five URLs), and shows the date the source was last fetched. Anything advisory — *"should I invest", "which fund is better", "will this give 15% returns"* — is politely refused and redirected to an educational resource.

The bet: **in regulated finance, a product that answers 40% of questions with near-100% verifiability beats a product that answers 100% of questions with 85% verifiability.** Accuracy over intelligence. Scope discipline is the feature, not the compromise.

---

## 2. Context and problem

### 2.1 Market context

Indian mutual funds have gone from a niche urban product to a mass-market savings habit in under a decade. As of June 2026, industry AUM stood at roughly ₹82.2 lakh crore, spread across ~27.9 crore folios, with SIP assets alone around ₹17.7 lakh crore — about a fifth of the industry. Growth is increasingly coming from B30 cities and from first-time investors who onboarded through app-first platforms.

Three consequences follow:

1. **The median investor is less financially literate than ever.** The marginal new folio in 2026 belongs to someone who found SIPs through an app or a reel, not through a distributor who explained exit loads over chai.
2. **Support volume scales with folios, not with AUM.** A ₹500/month SIP investor generates roughly the same number of support tickets as a ₹50,000/month investor, but a fraction of the revenue.
3. **Regulatory scrutiny of AI-generated output has hardened.** SEBI's Intermediaries (Amendment) Regulations, 2025 inserted Regulation 16C, making SEBI-regulated entities *solely* responsible for the output of AI/ML tools they use — whether built in-house or procured from a vendor — along with data privacy, security and integrity. A June 2025 consultation paper on responsible AI/ML usage in Indian securities markets extended the direction of travel. Translation: any platform shipping a general-purpose LLM chat surface next to a Buy button owns every hallucination it produces.

### 2.2 The specific problem

Objective mutual fund facts are **public, authoritative and machine-readable — and still practically inaccessible to the person who needs them.**

The information exists. The exit load for a scheme is stated precisely in the SID and the KIM. The expense ratio is disclosed on the AMC website and updated when it changes. The ELSS lock-in is in SEBI regulation. But:

- The SID is a 60–120 page PDF written for regulators, not readers.
- The factsheet is a monthly PDF with a different layout per AMC and per month.
- Expense ratios change; PDFs on the internet don't.
- Search engines rank SEO-optimised aggregator blogs above the AMC's own disclosure page.
- General chatbots answer confidently from training data that is months or years stale, with no citation and no freshness signal — and will happily slide from "the exit load is 1%" into "so it's better to hold for a year", which is advice.

The user's actual job is small and boring: *get one correct number, from a source I can check, in under 20 seconds.* Nothing in the current landscape does that job well.

### 2.3 Why "facts-only" is a product decision, not a limitation

Every adjacent product that has tried to be helpful about mutual funds has drifted into advice, because advice is what users ask for and what engagement metrics reward. Advice in this domain is regulated (SEBI Investment Advisers Regulations), carries liability, and requires suitability assessment.

By hard-scoping to facts, Facts Desk:

- can be shipped by a non-RIA entity without registering as an investment adviser,
- can be evaluated against ground truth (a number is right or wrong — no rubric needed),
- can be defended in a regulatory conversation line by line,
- and is *cheap*, because it needs neither a giant model nor a giant corpus.

The refusal behaviour is therefore a **primary feature with its own success metrics**, not an error state.

---

## 3. Why this product will work

### 3.1 The problem is bounded and the ground truth is stable

Unlike open-ended financial questions, factual scheme attributes have exactly one correct answer at a point in time, published on a named page. This means:

- Retrieval is tractable: **exactly five Groww HTML scheme pages** cover the v1 corpus — Mid Cap, Equity (Flexi Cap), Small Cap, Nifty 50 Index, and Balanced Advantage (all Direct Growth).
- Evaluation is objective: build a golden set of ~150 Q&A pairs with verified answers and measure exact-match accuracy.
- Regression is detectable: when a scheme page updates, a nightly eval run tells you which answers moved.

Most RAG products fail because "was that a good answer?" is unanswerable at scale. Here it is answerable by a script.

### 3.2 Citation is the product, not a garnish

Trust in financial information is not built by fluency; it is built by the ability to verify. A one-line answer with a link to the AMC's own page is *more* trustworthy than a beautifully written three-paragraph explanation without one. The single-citation constraint is also a forcing function on retrieval quality — if the system can't attribute the claim to one document, it shouldn't make the claim.

### 3.3 The refusal is a differentiator, not a drawback

Users have been trained by general chatbots to expect confident answers to everything. A system that says *"I can't tell you which fund is better — here's SEBI's investor education page on how to evaluate schemes"* reads as honest rather than broken, **provided the refusal is fast, warm, and gives the user somewhere to go.** Early qualitative testing should validate this; it is the single biggest UX risk in the product.

### 3.4 The economics are trivially favourable

A support ticket handled by a human costs on the order of ₹40–₹120 fully loaded, depending on channel. A retrieved-and-answered query costs a fraction of a rupee. Deflecting even 20% of factual mutual fund queries pays for the system many times over — and unlike a support macro, it works at 2 a.m. and improves with corpus curation rather than headcount.

### 3.5 Timing

- Retrieval + reranking + small-model extraction is now commodity infrastructure; this was a research project in 2022 and is a two-sprint build in 2026.
- Regulatory pressure has made *constrained* AI more attractive than *capable* AI inside financial firms. A system whose blast radius is provably bounded is easier to get approved than a general assistant.
- Competitors are shipping broad AI assistants. There is an opening for the one that is credible.

---

## 4. Users, jobs, and pain points

### 4.1 Primary personas

#### Persona A — "Rohit, the second-year SIP investor"
27, product designer in Pune. Started a ₹5,000 SIP in 2024 because a colleague did. Owns four schemes, understands roughly one of them. Checks the app twice a week out of anxiety.

> **Anecdote.** In March, Rohit wanted to redeem ₹40,000 from a flexi-cap fund to pay a deposit. He wanted to know whether he'd be charged an exit load. He searched "exit load [scheme name]" and got: a 2023 blog saying 1% before 1 year, a YouTube short about exit loads in general, and an aggregator page with a number that didn't match his app. He gave up, redeemed anyway, and got ₹380 less than he expected. He didn't complain — he just told two friends the platform "cuts money without telling you."
>
> The exit load was correctly disclosed in the SID and on the AMC's scheme page. He never found either.

**Job to be done:** *When I'm about to do something with my money, tell me the rule that applies, from a source I can trust, before I do it.*

#### Persona B — "Meera, the tax-season scrambler"
34, dentist in Kochi. Files her own ITR. Once a year she needs a capital gains statement and cannot remember where it lives.

> **Anecdote.** On 28 July, Meera needed her FY capital gains report. She searched the app, found a "Reports" section, downloaded something labelled "Portfolio Statement", and sent it to nobody because it wasn't what her CA asked for. She then messaged support and waited 14 hours for a reply that was three sentences long and entirely correct.
>
> Those three sentences existed as a help-centre article. It was the fourth result for her query.

**Job to be done:** *Tell me the exact steps to get the exact document, and link me to the official instructions.*

#### Persona C — "Sandeep, the ELSS lock-in checker"
41, ops manager in Ghaziabad. Invests in ELSS every March for Section 80C.

> **Anecdote.** Sandeep asked a general-purpose chatbot when his March 2023 ELSS SIP instalments would unlock. It told him "3 years from investment", which is correct, and then added that ELSS "typically outperforms other 80C options over the long term", which is a comparative performance claim he had no way to verify and which shaped his next investment. He did not ask for advice. He got it anyway.

**Job to be done:** *Answer exactly what I asked. Don't sell me anything.*

#### Persona D — "Priya, Tier-1 support agent"
24, contact centre in Hyderabad. Handles 60–90 mutual fund chats a shift. Has 11 browser tabs open permanently.

> **Anecdote.** Priya's most-used tab is a shared Google Sheet the team maintains with scheme attributes, last updated by someone who left in November. She knows two of the columns are stale but not which two, so she opens the AMC PDF to double-check "important" ones — which costs her ~90 seconds per query and which she skips when the queue is long.

**Job to be done:** *Give me a copy-pasteable, sourced answer I can trust without opening a PDF.*

#### Persona E — "Anand, content/compliance reviewer"
38, content lead. Owns the help centre and signs off on anything customer-facing.

> **Anecdote.** Anand blocked a previous AI assistant pilot after a QA sample of 50 conversations found four answers that were factually stale and one that recommended a fund category. He wasn't opposed to AI; he was opposed to not being able to prove what it would say.

**Job to be done:** *Let me see, test and constrain what this thing says before it says it.*

### 4.2 Consolidated pain points

| # | Pain point | Who feels it | Current workaround | Cost of the workaround |
|---|---|---|---|---|
| P1 | Correct answer exists but is buried in a 60–120pp PDF | A, C | Skim / give up | Wrong financial decisions, avoidable charges |
| P2 | Search returns stale third-party content ranked above official sources | A, B, C | Trust the top result | Confidently wrong beliefs |
| P3 | No way to tell whether a number is current | A, D | Assume | Silent staleness; erodes trust when discovered |
| P4 | General chatbots answer without citation and drift into advice | C | Believe it | Unregulated de-facto advice; platform liability |
| P5 | Repetitive factual tickets crowd out genuinely complex ones | D | Internal cheat sheets | Stale internal sources; agent time; slow SLAs |
| P6 | Process questions ("where do I download X") are answered inconsistently | B, D | Ad-hoc macros | Inconsistent CX, repeat contacts |
| P7 | No auditable record of what an assistant told a user | E | Don't ship the assistant | Innovation blocked entirely |

---

## 5. Alternatives in the market

### 5.1 Landscape

| Category | Examples | What they do well | Where they fail for this job |
|---|---|---|---|
| **Platform search & help centres** | Groww Help, Zerodha Coin support, Kuvera help | Authoritative for platform-level process questions; owned content | Keyword search, not question answering; weak on scheme-level attributes; no citations to primary regulatory sources; content ages silently |
| **AMC websites & fund pages** | HDFC MF, SBI MF, ICICI Pru MF scheme pages | The primary source of truth; accurate and current | Navigation is hostile; data trapped in PDFs; no cross-AMC or cross-scheme lookup; no natural language entry point |
| **AMFI / SEBI portals** | amfiindia.com, sebi.gov.in, SEBI Investor Website | Definitive on regulation, categorisation, NAV history | Written for industry, not investors; circular-and-annexure format; near-zero discoverability for retail users |
| **Data aggregators & research portals** | Value Research, Moneycontrol, Morningstar India, ET Money | Comparison tables, ratings, screeners, rich data | Editorialised and rating-driven; blend fact with opinion; not the source of record; frequently the origin of stale numbers |
| **General-purpose AI assistants** | ChatGPT, Gemini, Perplexity, Copilot | Excellent language understanding; will attempt anything | Training-data staleness on numeric attributes; inconsistent citation; no corpus guarantees; drift into advisory framing; no audit trail; no accountability under Reg 16C |
| **Existing fintech AI assistants** | In-app AI helpers shipped by brokers/platforms | Contextual to the user's own portfolio; convenient | Broad scope makes them hard to certify; usually optimise for engagement/conversion; opaque provenance |
| **Human customer support** | Platform + AMC + RTA (CAMS/KFintech) support | Definitive, empathetic, can handle exceptions | Slow, expensive, business hours, inconsistent between agents |
| **Distributors, RIAs, and "finfluencers"** | MFDs, registered advisers, YouTube/Instagram creators | Personalised guidance (RIAs are the legitimate channel for advice) | Advice, not facts; variable quality; incentive conflicts; creators are unregulated on factual accuracy |
| **Community forums** | r/IndiaInvestments, Twitter/X, WhatsApp groups | Fast, real-world, high-context | Anecdotal, unverifiable, confidently wrong, occasionally malicious |

### 5.2 Positioning

Two axes matter: **breadth of scope** (facts → advice) and **verifiability** (unsourced → primary-source cited).

```
                       High verifiability
                              ▲
        AMC / AMFI / SEBI     │     ★ FACTS DESK
        primary documents     │     (facts + one primary citation
        (accurate, unusable)  │      + freshness date + refusal)
                              │
  ◀───────────────────────────┼───────────────────────────▶
  Narrow scope (facts only)   │        Broad scope (advice)
                              │
        Help-centre search    │     General AI assistants,
        Aggregator data pages │     finfluencers, forums,
                              │     rating-driven portals
                              ▼
                       Low verifiability
```

**The gap we occupy:** nobody today combines *narrow factual scope* with *primary-source citation* and *explicit freshness*. Aggregators are broad and unsourced. Primary sources are accurate and unusable. General AI is broad and unverifiable.

### 5.3 Why incumbents won't trivially close the gap

- **Aggregators** monetise engagement, comparison and lead-gen; a system that refuses to compare funds is directly opposed to their revenue model.
- **General assistants** cannot make corpus guarantees — their value proposition is answering everything, which is exactly the thing we are giving up.
- **AMCs** individually lack the incentive and product muscle to build a conversational layer over their own PDFs, and their output would be single-AMC anyway.
- **Platforms** could build this, but their instinct is to build the *broad* assistant, which is far harder to certify. Being narrow is a strategy competitors find unattractive — which is what makes it durable.

---

## 6. Goals and non-goals

### 6.1 Product goals

| ID | Goal |
|---|---|
| G1 | Answer factual mutual fund scheme queries correctly, from the five allow-listed Groww pages only |
| G2 | Make every answer verifiable in one click, with an explicit freshness date |
| G3 | Refuse advisory, predictive and comparative queries reliably and gracefully |
| G4 | Deflect repetitive factual support contacts without degrading user experience |
| G5 | Give Compliance a system they can inspect, test and constrain before launch |
| G6 | Keep the surface minimal enough that a first-time user understands the contract in 5 seconds |

### 6.2 Explicit non-goals (v1)

| ID | Non-goal | Rationale |
|---|---|---|
| N1 | Investment advice, recommendations or suitability assessment | Regulated activity; out of scope permanently |
| N2 | Performance comparison, return calculation, or forecasting | Explicitly excluded by the brief; link to the Groww scheme page instead |
| N3 | Personalised answers about a user's own holdings, units or transactions | Requires PII and account access; excluded by privacy constraints |
| N4 | Multi-AMC coverage at launch | Corpus is fixed to five HDFC schemes on Groww; expand only after accuracy holds |
| N5 | Transactional actions (place SIP, redeem, switch) | Different risk class; separate product |
| N6 | Open-web retrieval | Corpus must remain the five allow-listed Groww URLs only |
| N7 | Long-form explanations, tutorials, or "learn" content | ≤3 sentences is the contract; link out for depth |
| N8 | Voice, WhatsApp, or multilingual support | Phase 4 candidates, not v1 |
| N9 | PDF ingestion (SID, KIM, factsheets, circulars) | v1 corpus is **HTML-only**; no PDF fetch, parse, or index |
| N10 | Schemes or URLs beyond the five Groww pages | Out of coverage; answer with coverage limit / "not in my sources" |

---

## 7. Success metrics

### 7.1 North Star

**Verified Factual Resolutions (VFR): the number of sessions per week where a user asked an in-scope factual question, received an answer, and did not re-ask, rephrase, or escalate to support within 24 hours.**

It captures the entire value chain — in-scope, answered, correct enough to stop looking.

### 7.2 Quality metrics (primary; gate for launch)

| Metric | Definition | Launch gate | 6-month target |
|---|---|---|---|
| **Factual accuracy** | % of golden-set (n≥150) answers exactly matching verified ground truth | ≥ 95% | ≥ 98% |
| **Citation validity** | % of answers whose citation is (a) present, (b) exactly one, (c) resolves 200, (d) actually contains the claim | ≥ 99% | 99.9% |
| **Citation groundedness** | % of answers where every factual token is supported by the cited chunk (LLM-as-judge + human audit of 50/week) | ≥ 97% | ≥ 99% |
| **Refusal precision** | % of refusals that were genuinely out of scope (i.e. not over-refusal) | ≥ 90% | ≥ 95% |
| **Refusal recall** | % of out-of-scope queries (advisory/comparative/predictive) correctly refused, on an adversarial set of ≥100 prompts | ≥ 99% | 100% |
| **Advisory leakage** | Answers containing recommendation, comparison, prediction or suitability language | **0** occurrences in any audit | **0** |
| **PII capture rate** | Sessions where PAN/Aadhaar/account/OTP/contact data was persisted | **0** | **0** |
| **Staleness** | % of served answers whose source was re-verified within SLA (30 days; 7 days for expense ratio/NAV-adjacent fields) | ≥ 95% | ≥ 99% |

> Advisory leakage and PII capture are **zero-tolerance**. A single confirmed instance triggers rollback, not a backlog ticket.

### 7.3 Experience metrics (secondary)

| Metric | Launch target |
|---|---|
| Answer rate (in-scope queries that produce an answer rather than "I don't know") | ≥ 70% |
| Time to first token | < 1.2s p50, < 2.5s p95 |
| Full answer latency | < 3s p50, < 6s p95 |
| Citation click-through | ≥ 15% (a health signal for trust, not a maximisation target) |
| Thumbs-up rate on answered queries | ≥ 80% |
| Session-level re-ask rate | ≤ 20% |
| Post-refusal educational-link click-through | ≥ 25% |
| Post-refusal session abandonment | ≤ 40% (i.e. most users continue after a refusal) |

### 7.4 Business metrics

| Metric | Target (6 months post-launch) |
|---|---|
| Support-contact deflection on tagged factual intents | 20–30% reduction |
| Agent handle time on factual MF tickets (internal console) | −30% |
| Cost per resolved query | < ₹1.50 fully loaded |
| Help-centre article coverage gaps identified via unanswered-query log | ≥ 25 new/updated articles per quarter |

### 7.5 Counter-metrics (watch for damage)

- **Over-refusal rate** on in-scope factual queries — target < 5%. A safe-but-useless assistant is a failed assistant.
- **Escalation-after-refusal rate** — if refusals simply push volume to support, we've moved cost, not removed it.
- **Trust erosion signal** — % of users who click a citation and then re-ask the same question (suggests the citation didn't support the claim).
- **Answer-shopping** — repeated rephrasings of an advisory query in one session (suggests users are trying to jailbreak the scope; also a UX signal that the refusal copy isn't landing).

---

## 8. Product principles

1. **Accuracy over intelligence.** "I don't have that in my sources" is a good answer. A plausible guess is a defect.
2. **One claim, one source.** If we can't point to a single document that says it, we don't say it.
3. **Freshness is visible.** Every answer wears its age.
4. **Refusal is a feature.** It gets copywriting, design and metrics like any other feature.
5. **The corpus is the product.** Model choice is replaceable; curation is the moat.
6. **Never touch PII.** The safest way to protect user data is to never receive it.
7. **Boring on purpose.** No personality, no hedging, no encouragement, no emoji, no engagement bait.

---

## 9. Scope definition

### 9.1 Answerable intent taxonomy (v1)

All answers must be grounded in content present on one of the **five Groww scheme pages**. Intents that require SID/KIM/PDF factsheets, AMC help centres, or AMFI/SEBI pages are out of coverage for v1 and should return "not in my sources" (F5.4) rather than inventing an answer.

| Intent | Example query | Primary source |
|---|---|---|
| Expense ratio (TER) | "What's the expense ratio of the direct plan?" | Groww scheme page |
| Exit load | "Is there an exit load if I redeem after 8 months?" | Groww scheme page |
| Minimum investment / minimum SIP | "What's the minimum SIP amount?" | Groww scheme page |
| Minimum additional purchase, multiples | "Can I add ₹300 to my existing folio?" | Groww scheme page (if published) |
| Lock-in period | "Does this scheme have a lock-in?" | Groww scheme page (if published) |
| Riskometer classification | "What's the riskometer for this scheme?" | Groww scheme page |
| Benchmark index | "What is this fund benchmarked against?" | Groww scheme page |
| Scheme category (SEBI classification) | "Is this a mid-cap or a small-cap?" | Groww scheme page |
| Fund manager name & tenure | "Who manages this scheme?" | Groww scheme page (if published) |
| Plan/option availability | "Does it have an IDCW option?" | Groww scheme page (if published) |
| AUM / other published scheme attributes | "What is the AUM of this fund?" | Groww scheme page (if published) |
| Definitions (only if stated on page) | "What is exit load?" (as applied to this scheme) | Groww scheme page |

**Covered schemes (exhaustive for v1):**

1. HDFC Mid Cap Fund — Direct Growth — https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth  
2. HDFC Equity Fund — Direct Growth — https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth  
3. HDFC Small Cap Fund — Direct Growth — https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth  
4. HDFC Nifty 50 Index Fund — Direct Growth — https://groww.in/mutual-funds/hdfc-nifty-50-index-fund-direct-growth  
5. HDFC Balanced Advantage Fund — Direct Growth — https://groww.in/mutual-funds/hdfc-balanced-advantage-fund-direct-growth  

Queries about statement downloads, KYC process, tax reckoners, other AMCs, or other schemes are **coverage gaps**, not answerable intents.

### 9.2 Refusable intent taxonomy

| Class | Example | Handling |
|---|---|---|
| Advisory | "Should I invest in this fund?" | Refuse + link to SEBI/AMFI investor education |
| Comparative | "Which is better, A or B?" | Refuse + link to AMFI scheme comparison guidance |
| Predictive | "Will this give 15% next year?" | Refuse + note past performance is not indicative |
| Suitability / personal | "I'm 30, what's a good portfolio?" | Refuse + point to registered investment advisers |
| Performance & returns | "What were 3-year returns?" | Refuse-to-answer-inline + **link to the relevant Groww scheme page only** |
| Calculation | "How much will ₹5,000/month become?" | Refuse (no return calculations per constraints) |
| Timing | "Should I redeem now or wait?" | Refuse |
| Account-specific | "What's my current balance?" | Refuse + direct to logged-in app/support; never request identifiers |
| Out-of-domain | "What's the weather?" | Polite scope reminder |
| PII-bearing | Message containing PAN/Aadhaar/account/OTP/email/phone | Redact-on-ingest, do not persist, refuse and warn |

---

## 10. Features and requirements

Priority key: **P0** = required for launch, **P1** = fast-follow, **P2** = later phase.

### F1 — Corpus ingestion & curation (P0)

- **F1.1** Allow-listed source registry. A version-controlled config file (`corpus.yaml`) listing **exactly these five Groww scheme-page URLs** with: URL, scheme mapping, refresh cadence, and owner. **Nothing outside the registry is ever fetched or retrieved.**

  | Scheme | URL |
  |---|---|
  | HDFC Mid Cap Fund Direct Growth | https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth |
  | HDFC Equity Fund Direct Growth | https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth |
  | HDFC Small Cap Fund Direct Growth | https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth |
  | HDFC Nifty 50 Index Fund Direct Growth | https://groww.in/mutual-funds/hdfc-nifty-50-index-fund-direct-growth |
  | HDFC Balanced Advantage Fund Direct Growth | https://groww.in/mutual-funds/hdfc-balanced-advantage-fund-direct-growth |

- **F1.2** Fetcher supporting **HTML only**, with content hashing to detect changes and `fetched_at` / `document_effective_date` stamps. **No PDF fetch, download, or parse.**
- **F1.3** HTML parsing that preserves structured sections and tables on the scheme page (expense ratio, exit load, minimums, riskometer, benchmark, etc.). Tables extracted as structured rows, not flattened text.
- **F1.4** Chunking strategy: semantic/section-aware chunks of ~300–600 tokens with heading breadcrumbs preserved, plus a parent-document reference so the citation resolves to the human-navigable Groww scheme page rather than a chunk.
- **F1.5** Metadata enrichment: `amc` (HDFC), `scheme_name`, `scheme_code`, `plan` (Direct), `option` (Growth), `document_type` (`groww_scheme_page`), `effective_date`, `source_url`, `authority` (Groww), `content_hash`.
- **F1.6** **Scheduler:** run the ingestion service **daily at 09:15 AM IST** for all five scheme pages (plus optional manual/admin re-run). Change detection emits a diff for review.
- **F1.7** Manual review gate: any diff touching a numeric attribute (TER, load, minimums) requires a human approval before it goes live. Silent auto-updates of numbers are prohibited.

### F2 — Retrieval (P0)

- **F2.1** Hybrid retrieval: dense embeddings + BM25/keyword. Pure vector search underperforms badly on exact entity queries — scheme names are long, near-identical, and differ by one word ("Regular" vs "Direct", "Growth" vs "IDCW").
- **F2.2** Metadata pre-filtering on scheme and plan before semantic search.
- **F2.3** Cross-encoder reranking of top-k candidates; keep top 3–5 for generation.
- **F2.4** Confidence thresholding: if the top reranked score is below threshold, do **not** generate — return the "not in my sources" response (F5.4).
- **F2.5** Scheme disambiguation: if the query matches multiple schemes/plans above threshold, ask exactly one clarifying question rather than guessing (see E2).
- **F2.6** Query preprocessing: expand abbreviations (TER, IDCW, STP, SWP, NFO, KIM, SID), normalise scheme aliases, strip PII (see F6.1).

### F3 — Answer generation (P0)

- **F3.1** **Extractive-first policy.** The generator's job is to phrase a retrieved fact, not to reason. System prompt constrains output to statements directly supported by the provided chunks.
- **F3.2** Hard output contract:
  - ≤ 3 sentences
  - exactly 1 citation link
  - footer: `Last updated from sources: <DD Mon YYYY>`
  - no hedging, no encouragement, no follow-up sales prompt
- **F3.3** **Post-generation validator (deterministic, non-LLM where possible):** rejects the response if it contains >3 sentences, ≠1 link, a link outside the allow-list, a numeric value not present in the retrieved chunks, or any term on the advisory lexicon blocklist. Failed validation → regenerate once → else fall back to safe response.
- **F3.4** Groundedness check: a second-pass verifier confirms each claim is entailed by the cited chunk. Failures are logged and routed to the eval queue.
- **F3.5** Determinism: temperature ≈ 0; identical query + identical corpus state should yield a stable answer. Response caching keyed on `(normalised_query, corpus_version)`.
- **F3.6** Numeric guardrail: numbers may only be surfaced if they appear verbatim in a retrieved chunk. No arithmetic, no unit conversion, no rounding, no aggregation, ever.

### F4 — Citation & freshness (P0)

- **F4.1** Exactly one link per answer, resolving to the most specific allow-listed Groww scheme-page URL available.
- **F4.2** Link display shows the source (e.g. "Groww — HDFC Mid Cap Fund Direct Growth").
- **F4.3** `Last updated from sources: <date>` = the date the cited page was last successfully fetched and verified, not the date of the conversation.
- **F4.4** Staleness banner: if the cited source exceeds its refresh SLA, the answer is served with a visible caution or withheld, per field type (configurable; withhold for TER, caution for category/definitions).
- **F4.5** Dead-link monitor: automated HEAD checks on the same daily schedule as ingestion (**09:15 AM IST**, or immediately after each fetch); any 4xx/5xx quarantines the affected answers.

### F5 — Refusal & scope enforcement (P0)

- **F5.1** Pre-retrieval intent classifier routing to: `factual_in_scope`, `advisory`, `comparative`, `predictive`, `performance`, `personal_account`, `pii_bearing`, `out_of_domain`, `ambiguous`.
- **F5.2** Layered defence: classifier → retrieval scope → system prompt → output validator → lexicon blocklist. No single point of failure.
- **F5.3** Refusal response template — polite, one line of reason, one educational link, no lecture:
  > I can only share verified facts from official sources, so I can't tell you whether a scheme suits you. SEBI's investor education pages explain how to evaluate schemes yourself. → [SEBI Investor Website]
- **F5.4** "Not in my sources" response, distinct from refusal (this is a coverage gap, not a scope violation), with an escalation affordance:
  > I couldn't find that in my official sources, so I'd rather not guess. You can check the scheme page on Groww, or reach out to support. → [Scheme page]
- **F5.5** Performance queries get a dedicated handler: never state returns inline; always link to the relevant allow-listed Groww scheme page.
- **F5.6** Jailbreak resistance: role-play, hypothetical, "as a friend", "just between us", "pretend you're my adviser", translated-language and encoded prompts must all fail closed. Adversarial suite runs in CI.
- **F5.7** Prompt-injection defence: content retrieved from pages is data, never instruction. Injected text inside HTML must not alter behaviour.

### F6 — Privacy & security (P0)

- **F6.1** PII detection and redaction **at the edge, before logging or model call**: PAN, Aadhaar, folio/account numbers, OTPs, email, phone. Redacted to type tokens (`<PAN_REDACTED>`).
- **F6.2** No persistence of raw user messages containing PII; analytics store intent labels and redacted text only.
- **F6.3** No login, no account linking, no cookies beyond a session identifier in v1. Anonymous by construction.
- **F6.4** If a user volunteers an identifier, respond with a warning and a reminder never to share such details in chat.
- **F6.5** Full audit log of `(redacted_query, retrieved_chunk_ids, corpus_version, response, citation, validator_verdicts, model_version, timestamp)` retained per the data-retention policy — sufficient to reconstruct exactly why any answer was produced.
- **F6.6** Rate limiting and abuse protection per session/IP.

### F7 — User interface (P0)

- **F7.1** Single-screen chat with: welcome message, three example questions as tappable chips, persistent disclaimer **"Facts-only. No investment advice."** visible without scrolling.
- **F7.2** Answer card: answer text, source chip (authority + document type), `Last updated from sources: <date>` footer, thumbs up/down.
- **F7.3** Refusal card: visually distinct (neutral, not alarming), refusal copy, educational link.
- **F7.4** Loading state under 1.2s to first token; streamed output.
- **F7.5** Accessibility: WCAG 2.1 AA — keyboard navigable, screen-reader labels on source chips, 4.5:1 contrast, no colour-only status encoding.
- **F7.6** Mobile-first responsive layout; ≥60% of traffic will be mobile.
- **F7.7** Embeddable widget mode (iframe/script) for placement in the help centre and scheme pages.
- **F7.8** Copy-answer-with-citation button (critical for support agents).

### F8 — Feedback & evaluation (P0/P1)

- **F8.1 (P0)** Thumbs up/down with optional reason chips: *wrong number / outdated / not what I asked / no source / other*.
- **F8.2 (P0)** Golden evaluation set (≥150 Q&A pairs) with human-verified answers, run in CI on every corpus or prompt change.
- **F8.3 (P0)** Adversarial refusal suite (≥100 prompts) run in CI.
- **F8.4 (P1)** Unanswered-query dashboard driving corpus expansion and help-centre content gaps.
- **F8.5 (P1)** Weekly human audit sample (n=50) reviewed by Compliance.

### F9 — Admin & compliance console (P1)

- **F9.1** Corpus browser: every source, last fetch, hash, diff history, owner.
- **F9.2** Approval queue for numeric diffs (F1.7).
- **F9.3** Answer replay: reconstruct any past answer with its retrieval trace.
- **F9.4** Kill switch: disable a scheme, a document, an intent, or the whole assistant without a deploy.
- **F9.5** Prompt/policy version history with diffs and approver.

### F10 — Support agent mode (P1)

- **F10.1** Internal build with agent-specific affordances: multi-answer view, copy-with-citation, "flag as wrong" that routes straight to the corpus owner.
- **F10.2** Ticket-context prefill from the support tool.

### F11 — Coverage expansion (P2)

- **F11.1** Multi-AMC corpus with per-AMC accuracy gating (an AMC ships only after its own golden set clears 95%).
- **F11.2** Hindi + 2 regional languages, with the constraint that **citations stay in the source language** and the accuracy gate is re-run per language.
- **F11.3** Structured attribute API so scheme pages can render sourced facts natively (same corpus, non-chat surface).

---

## 11. System architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                        INGESTION (offline)                         │
│  corpus.yaml (exactly 5 Groww scheme-page URLs; HTML only)         │
│      → Fetcher (HTML only — no PDFs, content-hash, effective-date) │
│      → HTML parser (tables / sections preserved)                   │
│      → Section-aware chunker (+ heading breadcrumbs)               │
│      → Metadata enrichment (amc, scheme, plan, dates)              │
│      → Embedding + BM25 index build                                │
│      → Numeric-diff review queue ──► human approval ──► publish    │
└────────────────────────────────────────────────────────────────────┘
                                  │  versioned index (corpus_version)
                                  ▼
┌────────────────────────────────────────────────────────────────────┐
│                          QUERY PATH (online)                       │
│  User query                                                        │
│   → PII redaction (edge, pre-log)                                  │
│   → Query normalisation / abbreviation expansion                   │
│   → Intent classifier ──► advisory/comparative/predictive/PII ──►  │
│                            REFUSAL HANDLER (templated + edu link)  │
│   → Metadata filter (scheme, plan) + hybrid retrieval (dense+BM25) │
│   → Cross-encoder rerank → top-k chunks                            │
│   → Confidence gate ──► below threshold ──► "not in my sources"    │
│   → Constrained generation (extractive, temp≈0, ≤3 sentences)      │
│   → Deterministic validator (length, 1 link, allow-list, numerics, │
│                              advisory lexicon)                     │
│   → Groundedness verifier (claim ⊆ cited chunk)                    │
│   → Response assembly (answer + 1 citation + freshness footer)     │
│   → Audit log (redacted query, chunk ids, versions, verdicts)      │
└────────────────────────────────────────────────────────────────────┘
```

**Key architectural decisions and their rationale:**

| Decision | Rationale |
|---|---|
| Hybrid retrieval, not pure vector | Scheme names are long and near-identical; lexical matching is essential for exact entity resolution |
| Reranking before generation | Cheap accuracy win; the difference between "top-20 contains the answer" and "top-3 is the answer" |
| Extractive-first generation | Minimises hallucination surface; the model phrases, it does not reason |
| Deterministic validator after the model | Never rely on a probabilistic system to enforce a hard constraint |
| Versioned corpus + response cache | Reproducibility and auditability; the same question yesterday and today has a traceable answer |
| Human gate on numeric diffs | Silent numeric drift is the highest-severity failure mode in this product |
| Small model is sufficient | Task is extraction + formatting; spend the budget on retrieval and evaluation, not model size |

---

## 12. Response contract

### 12.1 Answer format

```
<Fact statement, ≤3 sentences, no hedging, no advice>

[Source: <Authority> — <Document type>](<url>)
Last updated from sources: <DD Mon YYYY>
```

**Example (in scope):**
> The exit load for this scheme is 1% of the applicable NAV if units are redeemed within 365 days of allotment. No exit load applies after 365 days.
>
> [Source: Groww — HDFC Mid Cap Fund Direct Growth](https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth)
> *Last updated from sources: 28 Jul 2026*

**Example (attribute not on page — coverage gap):**
> I couldn't find that in my sources for this scheme, so I'd rather not guess. You can check the scheme page on Groww, or reach out to support.
>
> [Source: Groww — HDFC Equity Fund Direct Growth](https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth)
> *Last updated from sources: 21 Jul 2026*

**Example (performance query — redirect, not answer):**
> I don't share performance figures or returns. The scheme page publishes current performance data, including standard disclosures.
>
> [Source: Groww — HDFC Small Cap Fund Direct Growth](https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth)
> *Last updated from sources: 31 Jul 2026*

**Example (refusal):**
> I can only share verified facts from official sources, so I can't say whether one scheme is better than another. AMFI's investor education pages explain how to evaluate schemes on your own.
>
> [Source: AMFI — Investor education](…)

### 12.2 Tone rules

- Declarative, present tense, no adjectives of quality.
- Never say "great question", "I'd recommend", "you may want to consider", "typically", "generally", "most investors".
- Never end with a question unless disambiguating (E2).
- Never use emoji.

### 12.3 Disclaimer snippet (required, always visible)

> **Facts-only. No investment advice.**
> Answers are retrieved from five allow-listed Groww scheme pages for selected HDFC Direct Growth funds. This assistant does not provide investment advice, recommendations or performance comparisons. Mutual fund investments are subject to market risks; read all scheme related documents carefully.

---

## 13. Edge cases

### 13.1 Retrieval & data

| ID | Edge case | Handling |
|---|---|---|
| E1 | Query matches no chunk above threshold | "Not in my sources" (F5.4). Never generate from parametric memory. Log to coverage gap dashboard. |
| E2 | Ambiguous scheme reference ("the flexi cap fund") when multiple match | One clarifying question with up to 3 named options as chips. Never pick the most popular. |
| E3 | Direct vs Regular plan not specified (expense ratios differ materially) | Ask which plan, or state both if both are in one retrieved chunk — but that counts as one answer with one citation. |
| E4 | Growth vs IDCW option confusion | Same as E3. |
| E5 | Two sections on the same page conflict, or a page value looks inconsistent with another allow-listed page | Prefer the more recently fetched page content; if the gap exceeds tolerance, **withhold the answer**, serve "not in my sources", and raise a corpus alert. Never average, never pick silently. |
| E6 | Source page updated mid-session | Answer reflects corpus version at query time; footer date makes this explicit. |
| E7 | Source URL 404s or Groww restructures the scheme page | Quarantine affected answers; page the corpus owner. Do not fall back to non-allow-listed URLs or PDFs. |
| E8 | HTML parse produces a garbled table or missing section | Ingestion validator rejects chunks failing a structural sanity check; page flagged for manual review. |
| E9 | Fact exists only in an image, chart, or client-rendered widget not available as HTML text | Out of scope for v1; flag for manual transcription into a reviewed override entry if Compliance approves. |
| E10 | Scheme merged, renamed, or wound up | Corpus records lifecycle state; answers for retired schemes state the status and link to the Groww scheme page if still allow-listed. |
| E11 | Attribute not published on the Groww scheme page | "Not in my sources" (F5.4). Do not fetch SIDs, KIMs, factsheet PDFs, or other sites to fill the gap. |
| E12 | Regulatory change invalidates a stored fact (e.g. taxation change) | Out of corpus for v1 if not reflected on the Groww page; withhold or "not in my sources" until the page updates and passes numeric review. |
| E13 | Prompt injection inside fetched HTML ("ignore previous instructions") | Retrieved content is treated strictly as data; injection patterns stripped at ingestion; CI test with a poisoned fixture. |
| E14 | Corpus is mid-rebuild | Serve from the last published index; never serve from a partial index. |

### 13.2 Query & scope

| ID | Edge case | Handling |
|---|---|---|
| E15 | Mixed query: "What's the exit load and should I redeem?" | Answer the factual half, refuse the advisory half, in one response, still ≤3 sentences with one citation. |
| E16 | Advisory query disguised as factual: "What's the best expense ratio available?" | Superlative + selection framing → refuse. "What is the expense ratio of scheme X" → answer. |
| E17 | Comparison framed factually: "Is A's expense ratio higher than B's?" | Refuse the comparison; offer to state each scheme's ratio separately in follow-up turns. |
| E18 | Return calculation: "If I invest ₹5,000/month for 10 years…" | Refuse — no calculations, no projections. Link to SEBI investor education on SIPs. |
| E19 | Repeated rephrasing to extract advice | Refusal remains consistent across turns; the system does not soften. Log as answer-shopping. |
| E20 | Role-play / hypothetical jailbreak | Fail closed. Refusal copy does not acknowledge the framing. |
| E21 | User asks in Hinglish or a regional language (v1 is English) | Answer if the intent classifier is confident and retrieval succeeds; otherwise say the assistant currently works in English. Never guess a number from a misparsed query. |
| E22 | User asks about a non-mutual-fund product (stocks, insurance, FDs) | Out-of-domain scope reminder. |
| E23 | User asks about a scheme or AMC not in the five-URL corpus | State the coverage limit plainly (five HDFC Direct Growth schemes on Groww) and do not link outside the allow-list. |
| E24 | Query contains PAN/Aadhaar/account number | Redact pre-log, do not answer the account-specific part, warn the user not to share identifiers, direct to authenticated support. |
| E25 | User asks "are you a financial adviser / are you SEBI registered?" | Direct, honest answer: no, this is an automated facts-only tool; link to disclaimer. |
| E26 | User asks about the assistant's own limitations or sources | Answer transparently; list source authorities and the corpus scope. Transparency is in scope. |
| E27 | Distress signal ("I've lost my life savings, what do I do") | Do not attempt to counsel or advise. Respond with brief acknowledgement, direct to human support and to SEBI's investor grievance channel (SCORES). Never a templated cheerful refusal. |
| E28 | User reports a scam or unauthorised transaction | Do not troubleshoot. Route immediately to human support and the official grievance channel; state it clearly and once. |
| E29 | Complaint about the platform itself | Route to support; do not defend, do not explain. |
| E30 | User asks the same factual question repeatedly | Serve the cached deterministic answer; identical wording (an inconsistent answer would be worse than a repetitive one). |

### 13.3 System & operational

| ID | Edge case | Handling |
|---|---|---|
| E31 | Model provider outage | Degrade to retrieval-only mode: return the top-matching source snippet with its citation, clearly labelled as an extract rather than an answer. |
| E32 | Validator rejects generation twice | Serve the safe fallback ("not in my sources"). Never serve an unvalidated response. |
| E33 | Latency budget exceeded | Show source card first, stream answer after; hard timeout with fallback at 8s. |
| E34 | Traffic spike / abuse | Rate limit per session; queue with an honest wait message. |
| E35 | Confirmed advisory leakage in production | Automatic feature-flag disable of the affected intent; incident review within 24h; postmortem to Compliance. |
| E36 | Screenshot of an answer shared out of context | Answers include the source and date inline in the rendered card so a screenshot stays self-documenting; disclaimer is part of the card in shared/embed mode. |
| E37 | Two users get different answers to the same question | Prevented by determinism + caching; monitored via a consistency canary that replays 20 golden queries hourly. |

---

## 14. Non-functional requirements

| Area | Requirement |
|---|---|
| **Latency** | TTFT < 1.2s p50 / < 2.5s p95; complete response < 3s p50 / < 6s p95; hard timeout 8s |
| **Availability** | 99.5% for v1; graceful degradation (E31) rather than hard failure |
| **Throughput** | Design for 50 QPS peak; horizontal scale on the retrieval tier |
| **Cost** | < ₹1.50 per resolved query fully loaded, including infra and model |
| **Reproducibility** | Any answer reconstructable from the audit log + corpus version |
| **Security** | TLS everywhere; secrets in a managed store; no PII at rest; least-privilege access to the audit log; annual pen test |
| **Data residency & retention** | India-region storage; retention per policy; redaction before persistence |
| **Regulatory alignment** | Built assuming the operating entity is solely responsible for AI output under SEBI's Reg 16C — hence the mandatory audit trail, human numeric gate, kill switch and versioned policy history |
| **Accessibility** | WCAG 2.1 AA |
| **Browser support** | Last 2 versions of Chrome, Safari, Firefox, Edge; Android Chrome, iOS Safari |
| **Observability** | Structured logs, retrieval traces, per-intent dashboards, alerting on accuracy/staleness/leakage |

> **Note:** regulatory characterisation is a matter for Legal and Compliance. This PRD is written to be conservative, but nothing here is legal advice and the scope boundary must be signed off before launch.

---

## 15. Risks and mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Hallucinated numeric fact reaches a user | Medium | **Critical** | Extractive-first generation; numeric-verbatim guardrail (F3.6); deterministic validator; groundedness verifier; golden-set CI |
| Silent staleness (TER changed, corpus didn't) | High | High | Refresh SLAs; change detection; staleness banner; withhold on SLA breach for volatile fields |
| Advisory drift in edge phrasing | Medium | **Critical** | Layered defence; adversarial CI suite; zero-tolerance metric with rollback |
| Over-refusal makes the product useless | Medium | High | Over-refusal counter-metric < 5%; refusal precision gate; regular review of refused-but-in-scope queries |
| Users perceive refusals as evasive | Medium | Medium | Refusal copy testing; always give a link and a next step; measure post-refusal continuation |
| Corpus maintenance decays after launch | High | High | Named corpus owner; approval queue in the workflow; staleness on the team dashboard, not buried |
| Prompt injection via source HTML | Low | High | Data/instruction separation; ingestion sanitisation; poisoned-fixture CI test |
| Scope creep toward "just add comparisons" | **High** | High | Non-goals are contractual; any scope change requires Compliance re-approval, not just PM approval |
| Support teams don't adopt the agent console | Medium | Medium | Co-design with agents in Phase 2; measure handle time, not logins |
| Legal/compliance blocks launch late | Medium | High | Compliance in the room from Phase 0; demo the *refusal* behaviour first, not the answer behaviour |

---

## 16. Implementation phases

### Phase 0 — Foundation & alignment (Weeks 1–2)

- Freeze the v1 corpus to the **five Groww HDFC Direct Growth scheme pages** listed in §9.1 / F1.1. No additional URLs; **no PDFs**.
- Assemble and freeze `corpus.yaml` with those five URLs only; lock ingestion schedule to **09:15 AM IST daily** (F1.6).
- Write the answerable/refusable intent taxonomy (§9) and get **Compliance sign-off on the taxonomy before any code**.
- Build the golden evaluation set (150 Q&A) and the adversarial refusal set (100 prompts), both human-verified, scoped to attributes published on the five pages.
- **Exit criteria:** signed-off taxonomy; frozen five-URL corpus list; eval sets committed to the repo.

### Phase 1 — Core RAG pipeline (Weeks 3–6)

- Ingestion: HTML fetcher (no PDF path), table/section-aware extraction, chunking, metadata, index build for the five pages.
- Retrieval: hybrid search, metadata filtering, reranking, confidence gate.
- Generation: constrained prompt, deterministic validator, groundedness verifier, response contract.
- Refusal: intent classifier + templated handlers + lexicon blocklist.
- CI: golden set + adversarial set run on every commit.
- **Exit criteria:** ≥90% accuracy on golden set, ≥95% refusal recall, 100% citation presence. No UI yet.

### Phase 2 — Product surface & internal pilot (Weeks 7–10)

- Build the minimal UI (F7): welcome, three example chips, persistent disclaimer, answer/refusal cards, feedback.
- Build the compliance console v1 (F9.1–F9.4) and the agent mode (F10).
- **Internal pilot with 15–25 support agents** — highest-value, lowest-risk audience: they can spot wrong answers instantly and their feedback is expert feedback.
- Weekly Compliance audit of 50 conversations.
- **Exit criteria:** launch gates in §7.2 met on live traffic; zero advisory-leakage incidents over 2 consecutive weeks; agent NPS positive.

### Phase 3 — Limited external launch (Weeks 11–14)

- Ship the embeddable widget on 3–5 high-traffic help-centre articles and scheme pages, at 5–10% traffic allocation.
- Instrument the full metric suite; daily accuracy monitoring; kill switch tested in production.
- Coverage expansion driven by the unanswered-query log (F8.4).
- **Exit criteria:** accuracy holds on organic traffic; deflection signal visible on tagged intents; over-refusal < 5%.

### Phase 4 — Scale (Months 4–6)

- Ramp to 100% on the reference AMC.
- Add AMCs sequentially with per-AMC accuracy gating (F11.1).
- Language expansion (F11.2) and structured attribute API (F11.3).
- Establish steady-state ops: named corpus owner, monthly Compliance review, quarterly adversarial red-team.

### Sequencing rationale

Ship the *evaluation harness before the product*, the *refusal before the answers*, and the *internal audience before the external one*. Every phase gate is an accuracy gate, not a date.

---

## 17. Go-to-market plan

### 17.1 Positioning

**Category:** not "AI assistant" — that promise is broad and instantly distrusted in finance. Position as **a verification tool**.

**Positioning statement:**
> For retail mutual fund investors and support teams who need objective scheme facts they can trust, Facts Desk answers factual questions using only five allow-listed Groww scheme pages for selected HDFC Direct Growth funds, with a source link and freshness date on every answer. Unlike general AI assistants and aggregator sites, it never gives advice, never compares funds, and never answers without a citation.

**Message hierarchy:**
1. *Every answer has a source.* (trust)
2. *Facts only — no advice, ever.* (scope clarity, and it pre-empts the trust objection)
3. *Answers in seconds from the scheme page — no PDF hunting.* (utility)

**Explicitly avoided messaging:** "smart", "personalised", "your investing companion", anything implying guidance. The brand promise is restraint.

### 17.2 Launch sequence

| Stage | Audience | Channel | Objective |
|---|---|---|---|
| **S0 — Internal alpha** (Wk 7) | Support agents, content, compliance | Internal tool | Find wrong answers cheaply; build internal advocates |
| **S1 — Support enablement** (Wk 9) | Full support org | Agent console + training | Reduce handle time; agents become the strongest external testimonial |
| **S2 — Help-centre embed** (Wk 11) | Organic help-seekers | Widget on top articles + scheme pages | Capture users at highest intent, lowest expectation |
| **S3 — In-product entry point** (Wk 14) | Existing investors | Contextual "Ask about this scheme" on scheme detail pages | Scale usage where the question is actually formed |
| **S4 — Standalone + public** (Mo 4) | Broad retail | Public URL, SEO, content marketing | Acquisition and category positioning |
| **S5 — Partnerships** (Mo 5–6) | AMCs, distributors, RTAs | B2B/embed conversations | Distribution and corpus co-ownership |

The critical insight: **launch where expectations are lowest and intent is highest.** A user who has already opened a help article and is reading a wall of text is delighted by a two-sentence sourced answer. A user who lands on a shiny "AI Assistant" homepage expects it to do everything and is disappointed by a refusal.

### 17.3 Channel plan

**Owned**
- Help centre widget (primary volume driver)
- Scheme detail page entry points, scoped to that scheme so ambiguity drops to near zero
- Email to existing investors — one send, framed as *"a faster way to check scheme facts"*, not as an AI launch
- In-app announcement card, dismissible, no interstitial

**Earned**
- A short, candid engineering/product blog post on *building an assistant that refuses things* — this is genuinely interesting to a fintech and AI audience and does double duty as a trust artifact
- Publish the accuracy methodology and the golden-set approach. Transparency about evaluation is unusual and therefore differentiating
- Financial-media pitch angle: **"the AI that won't tell you what to buy"** — a contrarian story in a market saturated with AI-advice claims

**Paid** — deliberately minimal at launch. Paid acquisition on an unproven-accuracy product buys the wrong kind of scale. Revisit at Phase 4 with search intent targeting on high-volume factual queries ("exit load [scheme]", "ELSS lock-in period", "how to download capital gains statement").

**SEO** — the structured attribute API (F11.3) lets scheme pages render sourced facts as indexable content. This is the compounding long-term channel: own the factual query, then offer the conversational surface.

**Community & influencer** — engage carefully. The natural allies are the credibility-focused corners (personal-finance subreddits, CA/tax communities, MFD forums) who value verifiability. Avoid returns-focused creators entirely; their audience wants exactly what we refuse to give.

### 17.4 Adoption strategy for support teams

Support is both a user segment and a distribution channel, and it is the fastest path to demonstrable ROI.

1. Ship agent mode before the consumer surface.
2. Train on the *refusal* behaviour first — agents need to know what it won't do so they don't over-rely on it.
3. Make "flag as wrong" one click, and close the loop visibly (tell the flagging agent when their flag fixed the corpus). This is the single highest-leverage adoption mechanic.
4. Measure handle time on tagged intents, not tool logins.

### 17.5 Trust-building programme

Trust is the entire GTM, so it gets a workstream:

- **Visible methodology page**: how the corpus is built, what's in it, refresh cadence, known limitations.
- **Public source list**: every URL in the corpus, published. Nobody does this. It costs nothing and is disproportionately convincing.
- **Known-limitations section in the README** and in the product: state plainly what it can't answer.
- **Incident transparency**: if a wrong answer ships, say so and say what changed.
- **Compliance co-sign**: the disclaimer and refusal copy are reviewed by Compliance and dated.

### 17.6 Business model

v1 is a **cost-reduction and trust product**, not a revenue product. Value accrues as:
- reduced support cost per folio,
- improved conversion/retention through reduced pre-transaction uncertainty (a user who understands exit load before redeeming is a less angry user afterwards),
- a defensible compliance posture that makes subsequent AI shipping easier.

Longer-term monetisable directions (Phase 4+, out of scope here): white-label embed for AMCs and distributors; a structured, licensed fund-facts API for partners.

### 17.7 GTM success metrics

| Horizon | Metric | Target |
|---|---|---|
| Launch (Wk 14) | Weekly sessions | 5,000 |
| Launch | Support agent weekly active usage | ≥ 60% of agents |
| Month 3 | Weekly Verified Factual Resolutions | 15,000 |
| Month 3 | Deflection on tagged factual intents | 20% |
| Month 6 | Weekly sessions | 50,000 |
| Month 6 | Deflection on tagged factual intents | 30% |
| Month 6 | AMCs covered | 3–5 |
| Month 6 | Trust proxy: citation CTR | ≥ 15% sustained |
| Ongoing | Advisory leakage incidents | 0 |

### 17.8 Launch readiness checklist

- [ ] Compliance sign-off on taxonomy, refusal copy, disclaimer
- [ ] Legal review of the scope boundary and disclaimer placement
- [ ] Golden-set accuracy ≥ 95%, refusal recall ≥ 99%
- [ ] Zero advisory leakage over 2 consecutive audit weeks
- [ ] PII redaction verified by security review
- [ ] Kill switch tested in production
- [ ] Audit log verified reconstructable end-to-end
- [ ] Support team trained; escalation path defined
- [ ] Methodology page and public source list published
- [ ] Incident response runbook signed off
- [ ] Rollback plan tested

---

## 18. Open questions

| # | Question | Owner | Needed by |
|---|---|---|---|
| Q1 | ~~Which AMC for v1?~~ **Resolved:** HDFC via five Groww Direct Growth scheme pages (see §9.1). Revisit only if expanding corpus. | Product + Eng | Phase 0 (done) |
| Q2 | Does the operating entity's regulatory status change the disclaimer or the permitted intent set? | Legal | Phase 0 |
| Q3 | Do we withhold or caution on stale TER? (Proposal: withhold.) | Compliance | Phase 1 |
| Q4 | Should the assistant ever state *both* Direct and Regular TER in one answer, given the one-citation rule? (v1 corpus is Direct Growth only.) | Product | Phase 1 |
| Q5 | Retention period for audit logs, and who can query them? | Legal + Security | Phase 2 |
| Q6 | Do we publish the full five-URL corpus list publicly? (Recommendation: yes.) | Product + Compliance | Phase 3 |
| Q7 | Should refusals offer a one-tap handoff to a human, or does that undermine deflection? | Product + Support | Phase 2 |
| Q8 | Language expansion: translate answers, or restrict to English until per-language accuracy gates pass? | Product | Phase 4 |
| Q9 | If a needed attribute is only in a SID/factsheet PDF and not on the Groww page, do we expand the corpus later or stay "not in my sources"? (v1 default: stay out — no PDFs.) | Product + Compliance | Phase 0 |

---

## Appendix A — Corpus registry (v1 — exhaustive)

```yaml
corpus_version: "2026-08-05.1"
amc: "HDFC Mutual Fund"
source_surface: "Groww scheme pages"
format: html_only  # no PDFs
sources:
  - id: src_001
    url: "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth"
    authority: Groww
    doc_type: groww_scheme_page
    schemes: [hdfc_mid_cap_direct_growth]
    plan: Direct
    option: Growth
    refresh: "daily@09:15 Asia/Kolkata"
    numeric_fields: [expense_ratio, exit_load, min_sip]
    owner: content-ops
  - id: src_002
    url: "https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth"
    authority: Groww
    doc_type: groww_scheme_page
    schemes: [hdfc_equity_direct_growth]
    plan: Direct
    option: Growth
    refresh: "daily@09:15 Asia/Kolkata"
    numeric_fields: [expense_ratio, exit_load, min_sip]
    owner: content-ops
  - id: src_003
    url: "https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth"
    authority: Groww
    doc_type: groww_scheme_page
    schemes: [hdfc_small_cap_direct_growth]
    plan: Direct
    option: Growth
    refresh: "daily@09:15 Asia/Kolkata"
    numeric_fields: [expense_ratio, exit_load, min_sip]
    owner: content-ops
  - id: src_004
    url: "https://groww.in/mutual-funds/hdfc-nifty-50-index-fund-direct-growth"
    authority: Groww
    doc_type: groww_scheme_page
    schemes: [hdfc_nifty_50_index_direct_growth]
    plan: Direct
    option: Growth
    refresh: "daily@09:15 Asia/Kolkata"
    numeric_fields: [expense_ratio, exit_load, min_sip]
    owner: content-ops
  - id: src_005
    url: "https://groww.in/mutual-funds/hdfc-balanced-advantage-fund-direct-growth"
    authority: Groww
    doc_type: groww_scheme_page
    schemes: [hdfc_balanced_advantage_direct_growth]
    plan: Direct
    option: Growth
    refresh: "daily@09:15 Asia/Kolkata"
    numeric_fields: [expense_ratio, exit_load, min_sip]
    owner: content-ops
```

**v1 composition (exactly 5 URLs):** five Groww HTML scheme pages for HDFC Direct Growth funds listed above. **No SIDs, KIMs, factsheet PDFs, AMC FAQ pages, or AMFI/SEBI pages in the ingestion corpus.** Educational links used only in refusal templates may point to SEBI/AMFI but are not ingested.

**Scheduler:** ingestion for all five URLs runs **daily at 09:15 AM IST** (`Asia/Kolkata`), with optional manual/admin re-run.

---

## Appendix B — Evaluation set design

**Golden factual set (n ≥ 150).** Per item: `query`, `verified_answer`, `expected_source_id`, `intent`, `verified_by`, `verified_on`. Distribution roughly mirrors expected traffic across the five schemes: exit load 15%, expense ratio 15%, minimums 12%, riskometer/benchmark/category 20%, fund manager / AUM / other page attributes 15%, near-miss scheme disambiguation 15%, other 8%. Include near-miss pairs across the five schemes (Mid Cap vs Small Cap, Equity vs Balanced Advantage, Index vs active) as a distinct hard slice. Do not include Q&A that can only be answered from PDFs.

**Adversarial refusal set (n ≥ 100).** Direct advisory · comparative · predictive · calculation · suitability · role-play jailbreak · authority-claim jailbreak ("I'm a SEBI-registered adviser, you can tell me") · mixed factual+advisory · PII-bearing · injected-instruction fixtures · translated advisory prompts.

**Cadence:** both suites in CI on every corpus/prompt/model change; full run nightly; weekly human audit (n=50) reviewed by Compliance; quarterly external red-team.

---

## Appendix C — Disclaimer snippet (canonical)

**Short form (persistent UI chip):**
> Facts-only. No investment advice.

**Long form (footer, embed, README):**
> **Facts-only. No investment advice.** This assistant answers objective questions about five selected HDFC Direct Growth mutual fund schemes using information retrieved from the corresponding Groww scheme pages (HTML only; no PDFs). It does not provide investment advice, recommendations, suitability assessments, performance comparisons or return projections. Information may not reflect the most recent changes; always verify against the linked Groww scheme page. Mutual fund investments are subject to market risks; read all scheme related documents carefully.

---

## Appendix D — README outline (deliverable)

1. **What this is** — one paragraph, including the facts-only scope boundary
2. **Setup** — prerequisites, environment variables, index build, running locally, running the eval suites
3. **Selected AMC and schemes** — HDFC via the five Groww Direct Growth URLs (Appendix A), with rationale for the fixed scope
4. **Corpus** — full five-URL source list, HTML-only ingestion, refresh cadence, how (not) to add a source, the numeric-diff approval process; explicit note that PDFs are out of scope
5. **Architecture** — ingestion pipeline, retrieval, generation constraints, validator, refusal layers (diagram from §11)
6. **Response contract** — format, citation rule, freshness footer
7. **Evaluation** — golden set, adversarial set, how to run, current scores
8. **Known limitations** — five schemes only, English only, HTML-only (no SID/KIM/factsheet PDFs), no images/client-only widgets, no performance data, no personalisation, staleness window, no coverage of schemes outside the registry
9. **Disclaimer snippet**
10. **Incident response** — kill switch, rollback, escalation contacts
