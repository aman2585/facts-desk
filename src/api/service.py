"""Ask service — cache → pipeline → audit. Emits typed cards only."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator

from pydantic import BaseModel

from src.api.audit import write_audit_entry
from src.api.cache import get_cached_card, put_cached_card
from src.api.cards import assemble_to_card, card_to_dict, parse_card
from src.api.config import ApiConfig, load_config
from src.generate.pipeline import AskResult, ask
from src.safety.pii import redact_pii


@dataclass
class AskServiceResult:
    session_id: str
    card: BaseModel
    cache_hit: bool
    cache_key: str
    audit_id: str
    corpus_version: str | None


def _citation_from_card(card: BaseModel) -> str | None:
    data = card_to_dict(card)
    return data.get("citation_url") or data.get("scheme_url")


def _audit_from_ask(
    *,
    session_id: str,
    result: AskResult,
    card: BaseModel,
    cache_hit: bool,
    cache_key: str,
    cfg: ApiConfig,
) -> str:
    chunk_ids: list[str] = []
    if result.retrieval and result.retrieval.chunks:
        chunk_ids = [c.chunk_id for c in result.retrieval.chunks]
    elif isinstance(result.audit.get("chunk_ids"), list):
        chunk_ids = [str(x) for x in result.audit["chunk_ids"]]

    return write_audit_entry(
        session_id=session_id,
        redacted_query=result.intent.redacted_query,
        intent=result.intent.intent,
        chunk_ids=chunk_ids,
        corpus_version=result.corpus_version,
        card=card,
        citation_url=_citation_from_card(card),
        validator_verdicts=result.audit.get("validator_verdicts"),
        model_version=result.model_version,
        cache_hit=cache_hit,
        cache_key=cache_key,
        path=str(result.audit.get("path") or ""),
        extra={
            "groundedness": result.audit.get("groundedness"),
            "retrieval_status": result.audit.get("retrieval_status"),
            "used_fallback": result.audit.get("used_fallback"),
        },
        cfg=cfg,
    )


def run_ask(
    query: str,
    *,
    session_id: str,
    cfg: ApiConfig | None = None,
) -> AskServiceResult:
    """Synchronous ask with cache + audit. Card is always a discriminated union."""
    config = cfg or load_config()
    cached, key, version = get_cached_card(query, cfg=config)
    if cached is not None:
        card = parse_card(cached)
        redacted = redact_pii(query).redacted
        audit_id = write_audit_entry(
            session_id=session_id,
            redacted_query=redacted,
            intent=None,
            chunk_ids=[],
            corpus_version=version,
            card=card,
            citation_url=_citation_from_card(card),
            validator_verdicts=None,
            model_version=None,
            cache_hit=True,
            cache_key=key,
            path="cache",
            cfg=config,
        )
        return AskServiceResult(
            session_id=session_id,
            card=card,
            cache_hit=True,
            cache_key=key,
            audit_id=audit_id,
            corpus_version=version,
        )

    result = ask(query)
    card = assemble_to_card(result.response, corpus_version=result.corpus_version)
    key = put_cached_card(query, card, cfg=config)
    audit_id = _audit_from_ask(
        session_id=session_id,
        result=result,
        card=card,
        cache_hit=False,
        cache_key=key,
        cfg=config,
    )
    return AskServiceResult(
        session_id=session_id,
        card=card,
        cache_hit=False,
        cache_key=key,
        audit_id=audit_id,
        corpus_version=result.corpus_version,
    )


def iter_ask_events(
    query: str,
    *,
    session_id: str,
    cfg: ApiConfig | None = None,
) -> Iterator[dict[str, Any]]:
    """
    Streaming event sequence for SSE:
      status → card → done
    UI consumes `card` by `type`; never parses prose from status events.
    """
    config = cfg or load_config()
    yield {"event": "status", "data": {"stage": "accepted", "session_id": session_id}}

    cached, key, version = get_cached_card(query, cfg=config)
    if cached is not None:
        yield {"event": "status", "data": {"stage": "cache_hit"}}
        card = parse_card(cached)
        redacted = redact_pii(query).redacted
        audit_id = write_audit_entry(
            session_id=session_id,
            redacted_query=redacted,
            intent=None,
            chunk_ids=[],
            corpus_version=version,
            card=card,
            citation_url=_citation_from_card(card),
            validator_verdicts=None,
            model_version=None,
            cache_hit=True,
            cache_key=key,
            path="cache",
            cfg=config,
        )
        yield {"event": "card", "data": card_to_dict(card)}
        yield {
            "event": "done",
            "data": {
                "session_id": session_id,
                "cache_hit": True,
                "cache_key": key,
                "audit_id": audit_id,
                "corpus_version": version,
            },
        }
        return

    yield {"event": "status", "data": {"stage": "generating"}}
    result = ask(query)
    card = assemble_to_card(result.response, corpus_version=result.corpus_version)
    key = put_cached_card(query, card, cfg=config)
    audit_id = _audit_from_ask(
        session_id=session_id,
        result=result,
        card=card,
        cache_hit=False,
        cache_key=key,
        cfg=config,
    )
    yield {"event": "card", "data": card_to_dict(card)}
    yield {
        "event": "done",
        "data": {
            "session_id": session_id,
            "cache_hit": False,
            "cache_key": key,
            "audit_id": audit_id,
            "corpus_version": result.corpus_version,
        },
    }
