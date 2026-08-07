"""Templated refusals + performance redirect handler (no answer assembler)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from src.safety.intent import IntentClass

# Educational outbound links — NOT part of the RAG corpus.
SEBI_INVESTOR_EDU = "https://investor.sebi.gov.in/"
AMFI_INVESTOR_EDU = "https://www.amfiindia.com/investor-corner"

ResponseKind = Literal[
    "refusal",
    "refusal_with_edu",
    "performance_redirect",
    "coverage_limit",
    "clarify",
    "pii_warn",
]


@dataclass(frozen=True)
class SafetyHandlerResult:
    kind: ResponseKind
    intent: IntentClass
    text: str
    educational_url: str | None = None
    scheme_url: str | None = None
    # Never include return figures / invented facts
    must_not_contain_returns: bool = False

    def as_dict(self) -> dict:
        return {
            "kind": self.kind,
            "intent": self.intent,
            "text": self.text,
            "educational_url": self.educational_url,
            "scheme_url": self.scheme_url,
            "must_not_contain_returns": self.must_not_contain_returns,
        }


_REFUSAL_GENERIC = (
    "I can only share verified facts from official sources, so I can't give "
    "investment advice or recommendations. SEBI's investor education pages "
    "explain how to evaluate schemes yourself."
)

_REFUSAL_COMPARATIVE = (
    "I can only share verified facts from official sources, so I can't say "
    "whether one scheme is better than another. AMFI's investor education pages "
    "explain how to evaluate schemes on your own."
)

_REFUSAL_PREDICTIVE = (
    "I can't forecast returns or predict future performance. I only share "
    "verified facts from five allow-listed Groww scheme pages."
)

_COVERAGE = (
    "I only cover five HDFC Direct Growth schemes on Groww, so I can't answer "
    "about that scheme. Ask about one of those five, or check the scheme page "
    "on Groww yourself."
)

_CLARIFY = (
    "I cover five HDFC Direct Growth schemes on Groww. Which one do you mean — "
    "Mid Cap, Equity (Flexi Cap), Small Cap, Nifty 50 Index, or Balanced Advantage?"
)

_PERSONAL = (
    "I can't look up personal account balances, folios, or holdings. I only "
    "answer objective facts from five Groww scheme pages."
)

_OOD = (
    "I'm a facts-only mutual fund assistant for five HDFC Direct Growth schemes "
    "on Groww, so I can't help with that topic."
)

_PII_WARN = (
    "Please don't share PAN, Aadhaar, folio numbers, OTPs, email, or phone in "
    "chat. I've redacted what you sent. I can't answer account-specific questions."
)

_PERFORMANCE = (
    "I don't share performance figures or returns. The scheme page on Groww "
    "publishes current performance data, including standard disclosures."
)

# scheme_code → allow-listed Groww URL
SCHEME_URLS: dict[str, str] = {
    "hdfc_mid_cap_direct_growth": (
        "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth"
    ),
    "hdfc_equity_direct_growth": (
        "https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth"
    ),
    "hdfc_small_cap_direct_growth": (
        "https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth"
    ),
    "hdfc_nifty_50_index_direct_growth": (
        "https://groww.in/mutual-funds/hdfc-nifty-50-index-fund-direct-growth"
    ),
    "hdfc_balanced_advantage_direct_growth": (
        "https://groww.in/mutual-funds/hdfc-balanced-advantage-fund-direct-growth"
    ),
}


def handle_refusal(
    intent: IntentClass,
    *,
    scheme_code: str | None = None,
) -> SafetyHandlerResult:
    """Map non-factual intents to templated safe responses."""
    if intent == "performance":
        return handle_performance(scheme_code=scheme_code)

    if intent == "uncovered_scheme":
        return SafetyHandlerResult(
            kind="coverage_limit",
            intent=intent,
            text=_COVERAGE,
            educational_url=None,
            scheme_url=None,
        )

    if intent == "ambiguous":
        return SafetyHandlerResult(
            kind="clarify",
            intent=intent,
            text=_CLARIFY,
        )

    if intent == "pii_bearing":
        return SafetyHandlerResult(
            kind="pii_warn",
            intent=intent,
            text=_PII_WARN,
        )

    if intent == "personal_account":
        return SafetyHandlerResult(
            kind="refusal",
            intent=intent,
            text=_PERSONAL,
        )

    if intent == "out_of_domain":
        return SafetyHandlerResult(
            kind="refusal",
            intent=intent,
            text=_OOD,
        )

    if intent == "comparative":
        return SafetyHandlerResult(
            kind="refusal_with_edu",
            intent=intent,
            text=_REFUSAL_COMPARATIVE,
            educational_url=AMFI_INVESTOR_EDU,
        )

    if intent == "predictive":
        return SafetyHandlerResult(
            kind="refusal",
            intent=intent,
            text=_REFUSAL_PREDICTIVE,
        )

    # advisory (default refuse path)
    return SafetyHandlerResult(
        kind="refusal_with_edu",
        intent=intent if intent != "factual_in_scope" else "advisory",
        text=_REFUSAL_GENERIC,
        educational_url=SEBI_INVESTOR_EDU,
    )


def handle_performance(*, scheme_code: str | None = None) -> SafetyHandlerResult:
    """Never state returns inline; optionally link the allow-listed Groww page."""
    url = SCHEME_URLS.get(scheme_code or "") if scheme_code else None
    text = _PERFORMANCE
    if url:
        text = f"{_PERFORMANCE} See: {url}"
    return SafetyHandlerResult(
        kind="performance_redirect",
        intent="performance",
        text=text,
        scheme_url=url,
        must_not_contain_returns=True,
    )


def should_short_circuit(intent: IntentClass) -> bool:
    """True when retrieval/generation must not run."""
    return intent != "factual_in_scope"
