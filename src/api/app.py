"""FastAPI app — POST /ask (streaming SSE or JSON), session id only."""

from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator

from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from src.api.cards import card_to_dict
from src.api.config import load_config
from src.api.rate_limit import limiter
from src.api.service import AskServiceResult, run_ask
from src.api.session import normalise_session_id

app = FastAPI(
    title="Facts Desk API",
    description="Facts-only. No investment advice. Session id only — no login.",
    version="0.5.0",
)


class AskRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    session_id: str | None = Field(
        default=None,
        description="Anonymous session id. Server mints one if omitted/invalid.",
    )
    stream: bool | None = Field(
        default=None,
        description="SSE stream when true; JSON envelope when false. Default from config.",
    )


class AskJsonResponse(BaseModel):
    session_id: str
    cache_hit: bool
    cache_key: str
    audit_id: str
    corpus_version: str | None
    card: dict[str, Any]


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip() or "unknown"
    if request.client:
        return request.client.host or "unknown"
    return "unknown"


def _enforce_rate_limit(session_id: str, ip: str) -> None:
    decision = limiter.check(session_id=session_id, ip=ip)
    if decision.allowed:
        return
    retry = int(decision.retry_after_s or 1) + 1
    raise HTTPException(
        status_code=429,
        detail={
            "type": "api_error",
            "text": "Rate limit exceeded. Please wait and try again.",
            "scope": decision.scope,
            "retry_after_s": retry,
        },
        headers={"Retry-After": str(retry)},
    )


def _sse_pack(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/ask")
async def post_ask(
    body: AskRequest,
    request: Request,
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
) -> Response:
    """
    Ask a facts-only question.

    Response card is a discriminated union on `type`:
      answer | refusal | coverage | performance_redirect | clarify | api_error

    Streaming (default): text/event-stream with events status → card → done.
    Non-streaming: application/json with `{session_id, cache_hit, card, ...}`.
    """
    cfg = load_config()
    session_id = normalise_session_id(body.session_id or x_session_id)
    _enforce_rate_limit(session_id, _client_ip(request))

    stream = cfg.stream_default if body.stream is None else bool(body.stream)
    query = body.query.strip()
    if not query:
        raise HTTPException(
            status_code=422,
            detail={"type": "api_error", "text": "query must not be empty"},
        )

    if stream:
        async def event_source() -> AsyncIterator[str]:
            yield _sse_pack(
                "status",
                {"stage": "accepted", "session_id": session_id},
            )

            def _run() -> AskServiceResult:
                return run_ask(query, session_id=session_id, cfg=cfg)

            yield _sse_pack("status", {"stage": "generating"})
            result = await asyncio.to_thread(_run)
            stage = "cache_hit" if result.cache_hit else "generated"
            yield _sse_pack("status", {"stage": stage})
            yield _sse_pack("card", card_to_dict(result.card))
            yield _sse_pack(
                "done",
                {
                    "session_id": result.session_id,
                    "cache_hit": result.cache_hit,
                    "cache_key": result.cache_key,
                    "audit_id": result.audit_id,
                    "corpus_version": result.corpus_version,
                },
            )

        return StreamingResponse(
            event_source(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Session-Id": session_id,
                "X-Accel-Buffering": "no",
            },
        )

    result = await asyncio.to_thread(
        run_ask, query, session_id=session_id, cfg=cfg
    )
    payload = AskJsonResponse(
        session_id=result.session_id,
        cache_hit=result.cache_hit,
        cache_key=result.cache_key,
        audit_id=result.audit_id,
        corpus_version=result.corpus_version,
        card=card_to_dict(result.card),
    )
    return JSONResponse(
        content=payload.model_dump(mode="json"),
        headers={"X-Session-Id": session_id},
    )


def create_app() -> FastAPI:
    return app
