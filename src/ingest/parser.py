"""Parse Groww HTML: prefer __NEXT_DATA__ mfServerSideData; sanitise HTML text."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from bs4 import BeautifulSoup

INJECTION_PATTERNS = [
    re.compile(r"ignore (all )?previous instructions", re.I),
    re.compile(r"system prompt", re.I),
    re.compile(r"you are now", re.I),
]

# Holdings / comparisons / performance are not answerable (PRD §9) —
# exclude from sections/chunks. Performance must be an explicit rule
# (not accidental word-count drop): returns are refusable (PRD §9.2).
HOLDINGS_HEADING_RE = re.compile(r"\bholdings?\b", re.I)
COMPARE_HEADING_RE = re.compile(
    r"\bcompare\b|\bsimilar funds?\b|\bother funds?\b",
    re.I,
)
PERFORMANCE_HEADING_RE = re.compile(
    r"\breturn calculator\b"
    r"|\breturns?\s+and\s+rankings?\b"
    r"|\b(?:trailing|rolling|historic)\s+returns?\b"
    r"|\bperformance\b"
    r"|\bcagr\b"
    r"|\b(?:1y|3y|5y|10y)\s+returns?\b",
    re.I,
)

# Rupee sign via codepoint escape — never depend on source-file encoding of '₹'
INR = "\u20b9"


@dataclass
class ParsedDocument:
    source_id: str
    source_url: str
    scheme_name: str
    fund_house: str
    structured: dict[str, Any]
    sections: list[dict[str, Any]] = field(default_factory=list)
    kv_rows: list[dict[str, str]] = field(default_factory=list)
    raw_text: str = ""


def extract_next_data(html: str) -> dict[str, Any] | None:
    m = re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


def _sanitize_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    for pat in INJECTION_PATTERNS:
        text = pat.sub("[filtered]", text)
    return text


def _mf_payload(next_data: dict[str, Any]) -> dict[str, Any]:
    page = (next_data.get("props") or {}).get("pageProps") or {}
    mf = page.get("mfServerSideData")
    return mf if isinstance(mf, dict) else {}


def _risk_label(mf: dict[str, Any]) -> str | None:
    stats = mf.get("return_stats") or []
    if stats and isinstance(stats[0], dict):
        return stats[0].get("risk") or None
    return mf.get("nfo_risk")


def _format_lock_in(raw: Any) -> str | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, dict):
        years, months, days = raw.get("years"), raw.get("months"), raw.get("days")
        if not any([years, months, days]):
            return "None"
        parts = []
        if years:
            parts.append(f"{years} year(s)")
        if months:
            parts.append(f"{months} month(s)")
        if days:
            parts.append(f"{days} day(s)")
        return ", ".join(parts) if parts else "None"
    return str(raw)


def _format_percent(raw: Any) -> str | None:
    if raw is None or raw == "":
        return None
    s = str(raw).strip()
    if s.endswith("%"):
        return s
    return f"{s}%"


def _format_inr_amount(raw: Any) -> str | None:
    """Format rupee amounts as published on Groww UI (₹ prefix)."""
    if raw is None or raw == "":
        return None
    s = str(raw).strip()
    if s.startswith(INR) or s.startswith("Rs") or s.startswith("INR"):
        return s
    return f"{INR}{s}"


def _format_aum_cr(raw: Any) -> str | None:
    if raw is None or raw == "":
        return None
    s = str(raw).strip()
    if "Cr" in s or "cr" in s:
        if not s.startswith(INR):
            return f"{INR}{s}"
        return s
    try:
        num = float(s)
        formatted = f"{num:.4f}".rstrip("0").rstrip(".")
    except ValueError:
        formatted = s
    return f"{INR}{formatted} Cr"


def structured_facts(mf: dict[str, Any]) -> dict[str, Any]:
    """Canonical attributes used for chunks + numeric diffs (display-ready units)."""
    return {
        "scheme_name": mf.get("scheme_name"),
        "fund_house": mf.get("fund_house"),
        "scheme_code_groww": mf.get("scheme_code"),
        "category": mf.get("category"),
        "sub_category": mf.get("sub_category"),
        "expense_ratio": _format_percent(mf.get("expense_ratio")),
        "exit_load": mf.get("exit_load"),
        "min_sip_investment": _format_inr_amount(mf.get("min_sip_investment")),
        "min_investment_amount": _format_inr_amount(mf.get("min_investment_amount")),
        "mini_additional_investment": _format_inr_amount(mf.get("mini_additional_investment")),
        "fund_manager": mf.get("fund_manager"),
        "benchmark": mf.get("benchmark") or mf.get("benchmark_name"),
        "benchmark_name": mf.get("benchmark_name"),
        "aum": _format_aum_cr(mf.get("aum")),
        "riskometer": _risk_label(mf),
        "sip_allowed": mf.get("sip_allowed"),
        "lock_in": _format_lock_in(mf.get("lock_in") or mf.get("lockin") or mf.get("lock_in_period")),
        # Raw numerics retained for Phase 6 diffing if needed
        "_raw_expense_ratio": mf.get("expense_ratio"),
        "_raw_min_sip_investment": mf.get("min_sip_investment"),
        "_raw_min_investment_amount": mf.get("min_investment_amount"),
        "_raw_aum": mf.get("aum"),
    }


def _kv_from_facts(facts: dict[str, Any]) -> list[dict[str, str]]:
    labels = {
        "expense_ratio": "Expense ratio",
        "exit_load": "Exit load",
        "min_sip_investment": "Minimum SIP",
        "min_investment_amount": "Minimum investment",
        "mini_additional_investment": "Minimum additional purchase",
        "fund_manager": "Fund manager",
        "benchmark": "Benchmark",
        "benchmark_name": "Benchmark name",
        "aum": "AUM",
        "riskometer": "Riskometer",
        "category": "Category",
        "sub_category": "Sub-category",
        "lock_in": "Lock-in",
        "sip_allowed": "SIP allowed",
    }
    rows: list[dict[str, str]] = []
    for key, label in labels.items():
        val = facts.get(key)
        if val is None or val == "":
            continue
        rows.append({"label": label, "value": str(val)})
    return rows


def _is_excluded_heading(heading_path: list[str]) -> bool:
    """Drop holdings, compare/similar-funds, and performance/returns sections."""
    return any(
        HOLDINGS_HEADING_RE.search(h or "")
        or COMPARE_HEADING_RE.search(h or "")
        or PERFORMANCE_HEADING_RE.search(h or "")
        for h in heading_path
    )


def _html_text_sections(html: str, scheme_name: str) -> tuple[list[dict[str, Any]], str]:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript", "svg", "iframe"]):
        tag.decompose()
    for sel in ["nav", "footer", "header"]:
        for tag in soup.select(sel):
            tag.decompose()

    sections: list[dict[str, Any]] = []
    current_heading = ["Overview"]
    buf: list[str] = []
    skip_section = False

    def flush() -> None:
        nonlocal buf
        if skip_section:
            buf = []
            return
        text = _sanitize_text(" ".join(buf))
        if text:
            sections.append({"heading_path": list(current_heading), "text": text})
        buf = []

    root = soup.find("main") or soup.find("article") or soup.body or soup
    for el in root.find_all(["h1", "h2", "h3", "p", "li", "td", "th"], recursive=True):
        name = el.name.lower()
        text = _sanitize_text(el.get_text(" ", strip=True))
        if not text or len(text) < 2:
            continue
        if name in {"h1", "h2", "h3"}:
            flush()
            current_heading = [scheme_name, text] if scheme_name else [text]
            skip_section = _is_excluded_heading(current_heading)
            continue
        if skip_section:
            continue
        buf.append(text)
        if sum(len(x.split()) for x in buf) > 800:
            flush()

    flush()
    raw = _sanitize_text(root.get_text(" ", strip=True))[:50000]
    return sections, raw


def parse_html(source_id: str, source_url: str, html: str, display_name: str) -> ParsedDocument:
    next_data = extract_next_data(html)
    mf = _mf_payload(next_data) if next_data else {}
    facts = structured_facts(mf) if mf else {}
    scheme_name = str(facts.get("scheme_name") or display_name)
    fund_house = str(facts.get("fund_house") or "HDFC Mutual Fund")
    kv_rows = _kv_from_facts(facts)

    sections: list[dict[str, Any]] = []
    if kv_rows:
        lines = [f"{r['label']}: {r['value']}" for r in kv_rows]
        sections.append(
            {
                "heading_path": [scheme_name, "Investment details"],
                "text": _sanitize_text(f"{scheme_name}. " + " | ".join(lines)),
                "tables": kv_rows,
            }
        )

    html_sections, raw_text = _html_text_sections(html, scheme_name)
    for sec in html_sections[:12]:
        if _is_excluded_heading(sec.get("heading_path") or []):
            continue
        if len(sec["text"].split()) < 25:
            continue
        sections.append(sec)

    return ParsedDocument(
        source_id=source_id,
        source_url=source_url,
        scheme_name=scheme_name,
        fund_house=fund_house,
        structured=facts,
        sections=sections,
        kv_rows=kv_rows,
        raw_text=raw_text,
    )
