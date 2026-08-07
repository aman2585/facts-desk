"""Edge PII redaction — before any model call, log, or cache key."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Ordered: longer / more specific patterns first where they overlap.
_PII_RULES: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "pan",
        re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", re.I),
        "<PAN_REDACTED>",
    ),
    (
        "aadhaar",
        re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"),
        "<AADHAAR_REDACTED>",
    ),
    (
        "email",
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
        "<EMAIL_REDACTED>",
    ),
    (
        "phone",
        re.compile(
            r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{9}(?!\d)"
        ),
        "<PHONE_REDACTED>",
    ),
    (
        "folio",
        re.compile(
            r"\b(?:folio(?:\s*(?:number|no\.?|#|is))?)\s*[:=]?\s*\d{6,}\b",
            re.I,
        ),
        "<FOLIO_REDACTED>",
    ),
    (
        "otp",
        re.compile(
            r"\b(?:otp|one[-\s]?time\s+password)\s*[:=]?\s*\d{4,8}\b",
            re.I,
        ),
        "<OTP_REDACTED>",
    ),
)


@dataclass(frozen=True)
class RedactionResult:
    original: str
    redacted: str
    types_found: list[str] = field(default_factory=list)

    @property
    def has_pii(self) -> bool:
        return bool(self.types_found)


def redact_pii(text: str) -> RedactionResult:
    """Replace PAN / Aadhaar / folio / OTP / email / phone with type tokens."""
    if not text:
        return RedactionResult(original=text or "", redacted=text or "", types_found=[])
    out = text
    found: list[str] = []
    for name, pat, token in _PII_RULES:
        if pat.search(out):
            found.append(name)
            out = pat.sub(token, out)
    # Dedupe preserving order
    seen: set[str] = set()
    types: list[str] = []
    for t in found:
        if t not in seen:
            seen.add(t)
            types.append(t)
    return RedactionResult(original=text, redacted=out, types_found=types)
