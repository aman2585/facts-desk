"""Query normalisation: abbreviation expansion + scheme alias resolution."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml

from src.ingest.paths import ROOT
from src.safety.uncovered import foreign_amc_match, scheme_shape_foreign

ALIASES_PATH = ROOT / "corpus" / "scheme_aliases.yaml"

SchemeResolution = Literal["resolved", "ambiguous", "unresolved", "uncovered"]

# Expand common mutual-fund abbreviations (case-insensitive whole tokens).
ABBREVIATIONS: dict[str, str] = {
    "ter": "expense ratio total expense ratio TER",
    "sip": "SIP systematic investment plan",
    "idcw": "IDCW income distribution cum capital withdrawal dividend",
    "aum": "AUM assets under management",
    "nav": "NAV net asset value",
    "stp": "STP systematic transfer plan",
    "swp": "SWP systematic withdrawal plan",
    "nfo": "NFO new fund offer",
    "kim": "KIM key information memorandum",
    "sid": "SID scheme information document",
    "baf": "balanced advantage fund BAF",
}

@dataclass(frozen=True)
class NormalisedQuery:
    raw: str
    normalised: str
    scheme_code: str | None
    resolution: SchemeResolution
    matched_alias: str | None = None
    plan: str | None = None


@lru_cache(maxsize=1)
def _load_alias_maps() -> tuple[list[tuple[str, str]], list[str]]:
    """Return (sorted alias→scheme_code pairs longest-first, ambiguous aliases)."""
    data = yaml.safe_load(ALIASES_PATH.read_text(encoding="utf-8")) or {}
    pairs: list[tuple[str, str]] = []
    for scheme_code, aliases in (data.get("aliases") or {}).items():
        for alias in aliases or []:
            pairs.append((alias.strip().lower(), str(scheme_code)))
    pairs.sort(key=lambda x: len(x[0]), reverse=True)
    ambiguous = [a.strip().lower() for a in (data.get("ambiguous_aliases") or [])]
    ambiguous.sort(key=len, reverse=True)
    return pairs, ambiguous


def expand_abbreviations(text: str) -> str:
    tokens = re.findall(r"[A-Za-z0-9]+|[^\w\s]", text, flags=re.UNICODE)
    out: list[str] = []
    for tok in tokens:
        key = tok.lower()
        if key in ABBREVIATIONS:
            out.append(ABBREVIATIONS[key])
        else:
            out.append(tok)
    # Rebuild with spaces; collapse whitespace
    joined = " ".join(out)
    return re.sub(r"\s+", " ", joined).strip()


def _contains_phrase(haystack: str, needle: str) -> bool:
    if not needle:
        return False
    # Word-boundary-ish: allow spaces/hyphens inside alias
    pattern = re.compile(
        r"(?<![a-z0-9])" + re.escape(needle).replace(r"\ ", r"[\s\-]+") + r"(?![a-z0-9])",
        re.I,
    )
    return bool(pattern.search(haystack))


def resolve_scheme(text: str) -> tuple[str | None, SchemeResolution, str | None]:
    """Map query text → scheme_code using longest alias match.

    Order (critical):
      1. ambiguous short forms
      2. known foreign AMC tokens (Axis/Kotak/…) — before aliases so
         "Axis Midcap" cannot steal the mid-cap corpus alias
      3. corpus aliases — before scheme-shape so in-corpus phrases like
         "Nifty 50 Index Fund" / "Balanced Advantage Fund" resolve
      4. scheme-shape heuristic for unrecognised fund-like names
    """
    lowered = text.lower()
    pairs, ambiguous = _load_alias_maps()

    # Ambiguous short forms before foreign-AMC heuristics (e.g. "the HDFC fund").
    for amb in ambiguous:
        if _contains_phrase(lowered, amb):
            specific = False
            for alias, _code in pairs:
                if len(alias) > len(amb) and _contains_phrase(lowered, alias):
                    specific = True
                    break
            if not specific:
                return None, "ambiguous", amb

    # Known foreign AMCs only — never let "midcap" alias steal Axis Midcap etc.
    foreign = foreign_amc_match(text)
    if foreign:
        return None, "uncovered", foreign

    for alias, scheme_code in pairs:
        if _contains_phrase(lowered, alias):
            return scheme_code, "resolved", alias

    # Unrecognised scheme-shaped names (after aliases so Nifty/BAF are not FP).
    shape = scheme_shape_foreign(text)
    if shape:
        return None, "uncovered", shape

    return None, "unresolved", None


def normalise_query(raw: str, plan_default: str = "Direct") -> NormalisedQuery:
    expanded = expand_abbreviations(raw or "")
    scheme_code, resolution, matched = resolve_scheme(expanded)
    plan = plan_default if resolution == "resolved" else None
    return NormalisedQuery(
        raw=raw or "",
        normalised=expanded,
        scheme_code=scheme_code,
        resolution=resolution,
        matched_alias=matched,
        plan=plan,
    )
