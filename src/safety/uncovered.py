"""Uncovered-scheme detection — closes Phase 3 silent wrong-scheme gap.

Any foreign / unrecognised AMC or scheme-shaped name that is not one of the
five corpus aliases must resolve as uncovered (never retrieve as ok).
"""

from __future__ import annotations

import re

# Known non-corpus AMCs / brand tokens (expand over time).
FOREIGN_AMC_TOKENS: tuple[str, ...] = (
    "SBI",
    "ICICI",
    "Axis",
    "Kotak",
    "Nippon",
    "UTI",
    "Parag Parikh",
    "Mirae",
    "Quant",
    "Franklin",
    "DSP",
    "Motilal",
    "Tata",
    "Aditya Birla",
    "Birla Sun Life",
    "Canara Robeco",
    "Canara",
    "PGIM",
    "WhiteOak",
    "White Oak",
    "Invesco",
    "Edelweiss",
    "Bandhan",
    "HSBC",
    "Baroda",
    "Mahindra Manulife",
    "Sundaram",
    "LIC",
    "Navi",
    "Zerodha",
)

# Legacy short patterns kept for parity with Phase 3 normaliser.
UNCOVERED_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(rf"\b{re.escape(tok)}\b", re.I) for tok in FOREIGN_AMC_TOKENS
) + (
    re.compile(r"\bBluechip\b", re.I),
)

# Scheme-shaped phrase: <Name> + category word, where Name is not HDFC.
_SCHEME_SHAPE = re.compile(
    r"\b(?P<amc>(?!HDFC\b)[A-Za-z][A-Za-z0-9&]*(?:\s+[A-Za-z][A-Za-z0-9&]*){0,4})\s+"
    r"(?:"
    r"Mid\s*-?\s*Cap|Small\s*-?\s*Cap|Flexi\s*-?\s*Cap|Large\s*-?\s*Cap|"
    r"Multi\s*-?\s*Cap|Focused|Bluechip|Index|Advantage|"
    r"(?:Mutual\s+)?Fund|Scheme|Equity|Hybrid"
    r")\b",
    re.I,
)

# Attribute + foreign-looking fund name without requiring full AMC list.
_ATTR_CUES = re.compile(
    r"\b(?:exit\s*load|expense\s*ratio|\bTER\b|minimum\s*SIP|min\s*SIP|"
    r"riskometer|benchmark|AUM|NAV|lock[\s-]?in)\b",
    re.I,
)


def foreign_amc_match(text: str) -> str | None:
    for pat in UNCOVERED_PATTERNS:
        m = pat.search(text or "")
        if m:
            return m.group(0)
    return None


def scheme_shape_foreign(text: str) -> str | None:
    """Return matched foreign scheme-shaped phrase if present and not HDFC."""
    m = _SCHEME_SHAPE.search(text or "")
    if not m:
        return None
    amc = (m.group("amc") or "").strip()
    if not amc:
        return None
    # Determiners / question words / auxiliaries are not AMCs
    # (e.g. "What index does …" must not become uncovered).
    _NON_AMC = {
        "the",
        "this",
        "that",
        "a",
        "an",
        "my",
        "our",
        "your",
        "what",
        "which",
        "who",
        "whose",
        "how",
        "when",
        "where",
        "why",
        "does",
        "do",
        "did",
        "is",
        "are",
        "was",
        "were",
        "its",
        "their",
    }
    if amc.lower() in _NON_AMC:
        return None
    # Reject any phrase that still mentions HDFC (e.g. "the HDFC fund")
    if "hdfc" in amc.lower() or amc.upper().startswith("HDFC"):
        return None
    return m.group(0)


def looks_like_uncovered_scheme(text: str) -> tuple[bool, str | None]:
    """
    True when query clearly targets a non-corpus scheme/AMC.

    Used by normaliser + intent classifier so unrecognised names never
    fall through to unresolved → hybrid retrieve → wrong scheme ok.
    """
    if not (text or "").strip():
        return False, None
    hit = foreign_amc_match(text)
    if hit:
        return True, hit
    shape = scheme_shape_foreign(text)
    if shape:
        return True, shape
    return False, None
