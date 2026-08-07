"""Rule-based intent classifier — 10 contractual classes (Phase 4).

Classes:
  factual_in_scope, advisory, comparative, predictive, performance,
  personal_account, pii_bearing, out_of_domain, uncovered_scheme, ambiguous
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from src.retrieve.normaliser import NormalisedQuery, normalise_query
from src.safety.pii import redact_pii
from src.safety.uncovered import looks_like_uncovered_scheme

IntentClass = Literal[
    "factual_in_scope",
    "advisory",
    "comparative",
    "predictive",
    "performance",
    "personal_account",
    "pii_bearing",
    "out_of_domain",
    "uncovered_scheme",
    "ambiguous",
]

INTENT_CLASSES: tuple[IntentClass, ...] = (
    "factual_in_scope",
    "advisory",
    "comparative",
    "predictive",
    "performance",
    "personal_account",
    "pii_bearing",
    "out_of_domain",
    "uncovered_scheme",
    "ambiguous",
)


@dataclass(frozen=True)
class IntentResult:
    intent: IntentClass
    redacted_query: str
    scheme_code: str | None
    resolution: str
    reason: str
    pii_types: tuple[str, ...] = ()

    def as_dict(self) -> dict:
        return {
            "intent": self.intent,
            "redacted_query": self.redacted_query,
            "scheme_code": self.scheme_code,
            "resolution": self.resolution,
            "reason": self.reason,
            "pii_types": list(self.pii_types),
        }


_JAILBREAK = re.compile(
    r"(ignore\s+(all\s+)?(previous|prior)\s+instructions|"
    r"pretend\s+you\s+are|"
    r"act\s+as\s+(my\s+)?(sebi|ria|adviser|advisor)|"
    r"just\s+between\s+us|"
    r"as\s+a\s+friend|"
    r"you\s+can\s+tell\s+me\s+which|"
    r"i'?m\s+a\s+sebi[- ]registered)",
    re.I,
)

_COMPARATIVE = re.compile(
    r"\b(which\s+is\s+better|vs\.?|versus|compared\s+to|compare|"
    r"safer\s+than|better\s+than|outperform|"
    r"which\s+(?:fund|scheme)\s+(?:is\s+)?(?:safer|better))\b",
    re.I,
)

_PREDICTIVE = re.compile(
    r"\b(will\s+\w+\s+give|forecast|predict|projected\s+return|"
    r"next\s+year|expected\s+return|likely\s+to\s+return)\b",
    re.I,
)

_PERFORMANCE = re.compile(
    r"\b(\d+\s*-?\s*year\s+returns?|returns?\s+last\s+year|"
    r"how\s+much\s+return|cagr|trailing\s+return|"
    r"gave\s+last\s+year|performance\s+(?:of|for|figures)|"
    r"absolute\s+returns?)\b",
    re.I,
)

_ADVISORY = re.compile(
    r"\b(should\s+i|shall\s+i|is\s+it\s+a\s+good|"
    r"good\s+buy|good\s+fund\s+for\s+me|"
    r"recommend|advise|advice|"
    r"invest\s+more|put\s+my\s+(?:emergency\s+)?fund|"
    r"suitable\s+for|risk\s+appetite|portfolio\s+should|"
    r"what\s+portfolio|allocate|"
    r"redeem\s+now|or\s+wait|"
    r"increase\s+(?:my\s+)?sip|"
    r"for\s+a\s+\d+-year-old|"
    r"for\s+tax|"
    r"switch\s+to)\b",
    re.I,
)

_CALC = re.compile(
    r"\b(how\s+much\s+will\s+i\s+get|future\s+value|calculate|"
    r"if\s+i\s+invest\s+₹|at\s+\d+%\s+for)\b",
    re.I,
)

_PERSONAL = re.compile(
    r"\b(my\s+(?:current\s+)?balance|my\s+folio|my\s+holdings|"
    r"my\s+units|my\s+capital\s+gains|my\s+account)\b",
    re.I,
)

_OOD = re.compile(
    r"\b(weather|cricket|recipe|movie|bitcoin\s+price|who\s+won)\b",
    re.I,
)

_FACTUAL_CUE = re.compile(
    r"\b(expense\s*ratio|\bTER\b|exit\s*load|minimum\s*SIP|min\s*SIP|"
    r"riskometer|benchmark|category|fund\s*manager|AUM|lock[\s-]?in|"
    r"minimum\s+additional|plan|option|IDCW)\b",
    re.I,
)


def classify_intent(raw_query: str) -> IntentResult:
    """
    Classify into one of 10 intents. PII is redacted first.

    Priority (fail closed toward refusal/coverage):
      pii → jailbreak/advisory → uncovered → ambiguous → comparative →
      predictive → performance → personal → calc/advisory → ood → factual
    """
    pii = redact_pii(raw_query or "")
    text = pii.redacted
    nq: NormalisedQuery = normalise_query(text)

    if pii.has_pii:
        return IntentResult(
            intent="pii_bearing",
            redacted_query=text,
            scheme_code=nq.scheme_code,
            resolution=nq.resolution,
            reason="pii_detected",
            pii_types=tuple(pii.types_found),
        )

    # Compound / advisory / jailbreak before factual — even if scheme resolves
    if _JAILBREAK.search(text):
        return IntentResult(
            intent="advisory",
            redacted_query=text,
            scheme_code=nq.scheme_code,
            resolution=nq.resolution,
            reason="jailbreak_or_roleplay",
        )

    if _COMPARATIVE.search(text):
        return IntentResult(
            intent="comparative",
            redacted_query=text,
            scheme_code=nq.scheme_code,
            resolution=nq.resolution,
            reason="comparative_language",
        )

    if _ADVISORY.search(text) or _CALC.search(text):
        return IntentResult(
            intent="advisory",
            redacted_query=text,
            scheme_code=nq.scheme_code,
            resolution=nq.resolution,
            reason="advisory_or_calculation",
        )

    if _PREDICTIVE.search(text):
        return IntentResult(
            intent="predictive",
            redacted_query=text,
            scheme_code=nq.scheme_code,
            resolution=nq.resolution,
            reason="predictive_language",
        )

    if _PERFORMANCE.search(text):
        return IntentResult(
            intent="performance",
            redacted_query=text,
            scheme_code=nq.scheme_code,
            resolution=nq.resolution,
            reason="performance_or_returns",
        )

    if _PERSONAL.search(text):
        return IntentResult(
            intent="personal_account",
            redacted_query=text,
            scheme_code=nq.scheme_code,
            resolution=nq.resolution,
            reason="personal_account",
        )

    # Uncovered / ambiguous from normaliser (alias map + foreign AMC)
    if nq.resolution == "ambiguous":
        return IntentResult(
            intent="ambiguous",
            redacted_query=text,
            scheme_code=None,
            resolution="ambiguous",
            reason="ambiguous_scheme",
        )

    if nq.resolution == "uncovered":
        return IntentResult(
            intent="uncovered_scheme",
            redacted_query=text,
            scheme_code=None,
            resolution="uncovered",
            reason="foreign_or_unrecognised_scheme",
        )

    # Trust normaliser when a corpus alias already resolved. A second
    # scheme-shape pass on raw text false-positived on in-corpus phrasing
    # ("Nifty 50 Index Fund", "Balanced Advantage Fund", "What index …").
    if nq.resolution != "resolved":
        uncovered, hit = looks_like_uncovered_scheme(nq.normalised)
        if uncovered:
            return IntentResult(
                intent="uncovered_scheme",
                redacted_query=text,
                scheme_code=None,
                resolution="uncovered",
                reason=f"uncovered_heuristic:{hit}",
            )

    # Scheme-shaped / attribute query that did not resolve to one of five
    if nq.resolution == "unresolved" and _FACTUAL_CUE.search(text):
        return IntentResult(
            intent="uncovered_scheme",
            redacted_query=text,
            scheme_code=None,
            resolution="uncovered",
            reason="unresolved_attribute_query",
        )

    if _OOD.search(text):
        return IntentResult(
            intent="out_of_domain",
            redacted_query=text,
            scheme_code=nq.scheme_code,
            resolution=nq.resolution,
            reason="out_of_domain",
        )

    if nq.resolution == "resolved" and _FACTUAL_CUE.search(text):
        return IntentResult(
            intent="factual_in_scope",
            redacted_query=text,
            scheme_code=nq.scheme_code,
            resolution=nq.resolution,
            reason="resolved_factual",
        )

    if nq.resolution == "resolved":
        if len(text.split()) <= 12:
            return IntentResult(
                intent="factual_in_scope",
                redacted_query=text,
                scheme_code=nq.scheme_code,
                resolution=nq.resolution,
                reason="resolved_short_query",
            )

    if nq.resolution == "unresolved":
        return IntentResult(
            intent="out_of_domain",
            redacted_query=text,
            scheme_code=None,
            resolution=nq.resolution,
            reason="unresolved_non_scheme",
        )

    return IntentResult(
        intent="out_of_domain",
        redacted_query=text,
        scheme_code=nq.scheme_code,
        resolution=nq.resolution,
        reason="default_out_of_domain",
    )
