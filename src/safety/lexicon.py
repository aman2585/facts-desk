"""Advisory / hedging lexicon blocklist for deterministic validation."""

from __future__ import annotations

import re

# Phrases and tokens that must never appear in a facts-only answer.
ADVISORY_PHRASES: tuple[str, ...] = (
    "i recommend",
    "i'd recommend",
    "we recommend",
    "you should",
    "you shouldn't",
    "you may want",
    "you might want",
    "consider investing",
    "good idea",
    "better than",
    "best fund",
    "best option",
    "outperform",
    "outperforms",
    "outperformed",
    "suitable for you",
    "right for you",
    "as your adviser",
    "as your advisor",
    "i advise",
    "my advice",
    "go ahead and",
    "must buy",
    "should buy",
    "should invest",
    "should redeem",
    "should switch",
    "prefer this",
    "safer choice",
    "less risky for you",
)

HEDGING_PHRASES: tuple[str, ...] = (
    "i think",
    "might",
    "probably",
    "typically",
    "generally",
    "most investors",
    "you may want to consider",
)

# Internal RAG / prompt machinery — must never leak into user-facing answers.
META_LANGUAGE_PHRASES: tuple[str, ...] = (
    "chunk",
    "chunks",
    "provided context",
    "the sources given",
    "the provided",
    "the passage",
    "provided chunks",
    "source chunks",
    "retrieved context",
    "context provided",
    "in the context",
    "given context",
    "according to the context",
)

_BLOCKLIST_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(rf"(?<![a-z0-9]){re.escape(p)}(?![a-z0-9])", re.I)
    for p in (*ADVISORY_PHRASES, *HEDGING_PHRASES)
)

_META_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(rf"(?<![a-z0-9]){re.escape(p)}(?![a-z0-9])", re.I)
    for p in META_LANGUAGE_PHRASES
)


def find_lexicon_hits(text: str) -> list[str]:
    """Return matched advisory/hedging blocklist phrases found in text."""
    hits: list[str] = []
    lowered = text or ""
    for pat, phrase in zip(_BLOCKLIST_PATTERNS, (*ADVISORY_PHRASES, *HEDGING_PHRASES)):
        if pat.search(lowered):
            hits.append(phrase)
    return hits


def find_meta_language_hits(text: str) -> list[str]:
    """Return matched internal-machinery phrases that must not appear in answers."""
    hits: list[str] = []
    lowered = text or ""
    for pat, phrase in zip(_META_PATTERNS, META_LANGUAGE_PHRASES):
        if pat.search(lowered):
            hits.append(phrase)
    return hits


def has_advisory_lexicon(text: str) -> bool:
    return bool(find_lexicon_hits(text))
