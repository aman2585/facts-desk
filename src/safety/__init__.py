"""Safety layer: PII, intent, refusals, uncovered-scheme gate, lexicon.

Import submodules directly (e.g. ``from src.safety.intent import classify_intent``)
to avoid circular imports with ``src.retrieve.normaliser``.
"""

__all__ = [
    "INTENT_CLASSES",
    "IntentResult",
    "RedactionResult",
    "SafetyHandlerResult",
    "classify_intent",
    "handle_performance",
    "handle_refusal",
    "looks_like_uncovered_scheme",
    "redact_pii",
]


def __getattr__(name: str):
    if name in {"INTENT_CLASSES", "IntentResult", "classify_intent"}:
        from src.safety import intent as m

        return getattr(m, name)
    if name in {"RedactionResult", "redact_pii"}:
        from src.safety import pii as m

        return getattr(m, name)
    if name in {"SafetyHandlerResult", "handle_performance", "handle_refusal"}:
        from src.safety import refusals as m

        return getattr(m, name)
    if name == "looks_like_uncovered_scheme":
        from src.safety.uncovered import looks_like_uncovered_scheme

        return looks_like_uncovered_scheme
    raise AttributeError(name)
