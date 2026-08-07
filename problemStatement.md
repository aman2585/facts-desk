**Build a RAG Chatbot \- Problem statement**

### Problem Statement

Problem Statement: Mutual Fund FAQ Assistant (Facts-Only Q\&A)  
Overview

The objective of this project is to build a **facts-only FAQ assistant** for mutual fund schemes, using **Groww** as the reference product context. The assistant will answer **objective, verifiable queries** related to mutual funds by retrieving information exclusively from a **fixed, allow-listed corpus of five Groww scheme pages** (HTML only).

The system must strictly **avoid providing investment advice, opinions, or recommendations**. Every response must include a **single, clear source link** and adhere to defined constraints around clarity, accuracy, and compliance.

---

Objective

Design and implement a lightweight **Retrieval-Augmented Generation (RAG)-based assistant** that:

* Answers **factual queries** about five specified HDFC mutual fund schemes  
* Uses a **curated corpus of exactly five Groww scheme-page URLs** (no PDFs, no open-web crawl)  
* Provides **concise, source-backed responses**

---

Target Users

* Retail investors comparing mutual fund schemes  
* Customer support and content teams handling repetitive mutual fund queries

---

Scope of Work

1\. Corpus Definition

* **AMC:** HDFC Mutual Fund (via Groww scheme pages)  
* **Exactly five allow-listed URLs** — these are the *only* sources ingested:

  1. https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth  
  2. https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth  
  3. https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth  
  4. https://groww.in/mutual-funds/hdfc-nifty-50-index-fund-direct-growth  
  5. https://groww.in/mutual-funds/hdfc-balanced-advantage-fund-direct-growth  

* **HTML only.** Do **not** ingest PDFs (no SID, KIM, or factsheet PDFs).  
* Nothing outside this allow-list is ever fetched or retrieved.  
* **Scheduler:** run the ingestion service for these five URLs **daily at 09:15 AM IST** (with optional manual re-run).

---

2\. FAQ Assistant Requirements

The assistant must:

* Answer **facts-only queries** about the five schemes above, such as:  
  * Expense ratio of a scheme  
  * Exit load details  
  * Minimum SIP amount  
  * Lock-in period (where applicable)  
  * Riskometer classification  
  * Benchmark index  
  * Other objective attributes published on the scheme page  
* Ensure:  
  * Each response is **limited to a maximum of 3 sentences**  
  * Each response includes **exactly one citation link** (one of the five allow-listed URLs)  
  * Each response includes a footer:  
     **“Last updated from sources: \<date\>”**

---

3\. Refusal Handling

The assistant must **refuse non-factual or advisory queries**, such as:

* “Should I invest in this fund?”  
* “Which fund is better?”

Refusal responses should:

* Be **polite and clearly worded**  
* Reinforce the **facts-only limitation**  
* Provide a **relevant educational link** (e.g., AMFI or SEBI investor-education resource). Educational links used in refusals are **not** part of the ingestion corpus.

---

4\. User Interface (Minimal)

The solution should include a simple interface with:

* A welcome message  
* Three example questions  
* A visible disclaimer:  
   **“Facts-only. No investment advice.”**

---

Constraints

Data and Sources

* Ingest **only** the five Groww scheme-page URLs listed above  
* **No PDFs** — no SID, KIM, factsheet, or other document downloads  
* Do **not** crawl or retrieve from third-party blogs, other aggregators, or any URL outside the allow-list  
* Coverage is limited to these five Direct Growth schemes; queries about other schemes or AMCs are out of coverage

Privacy and Security

* Do **not** collect, store, or process:  
  * PAN or Aadhaar numbers  
  * Account numbers  
  * OTPs  
  * Email addresses or phone numbers

Content Restrictions

* No investment advice or recommendations  
* No performance comparisons or return calculations  
* For performance-related queries, refuse to state figures inline and **link to the relevant Groww scheme page** (one of the five allow-listed URLs) only

Transparency

* Responses must be **short, factual, and verifiable**  
* Every answer must include a **source link and last updated date**

---

Expected Deliverables

1. **README Document**  
   * Setup instructions  
   * Selected AMC and schemes (the five Groww URLs)  
   * Architecture overview (RAG approach)  
   * Known limitations  
2. **Disclaimer Snippet**  
   * “Facts-only. No investment advice.”

---

Success Criteria

* Accurate retrieval of factual mutual fund information from the five-page corpus  
* Strict adherence to **facts-only responses**  
* Consistent inclusion of **valid source citations** (allow-listed URLs only)  
* Proper refusal of advisory queries  
* Clean, minimal, and user-friendly interface

---

Summary

The goal is to build a **trustworthy, transparent, and compliant mutual fund FAQ assistant** that prioritizes **accuracy over intelligence**. The system should ensure that users receive only **verified, source-backed financial information** from five fixed Groww scheme pages, without PDFs, advisory bias, or speculative content.
