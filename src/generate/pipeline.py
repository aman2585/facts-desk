"""Ask pipeline: redact → classify → (refuse | retrieve → generate → validate → assemble)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.generate.assembler import (
    COVERAGE_GATE_FAIL,
    AssembledResponse,
    assemble_answer,
    assemble_api_error,
    assemble_coverage,
    assemble_safety,
)
from src.generate.config import GenerateConfig, load_config
from src.generate.generator import GenerationResult, generate_answer
from src.generate.llm import LLMAPIError, LLMClient
from src.retrieve.hybrid import Candidate
from src.retrieve.normaliser import normalise_query
from src.retrieve.pipeline import RetrievalResult, retrieve
from src.retrieve.store import PublishedIndex, get_published_index
from src.safety.intent import IntentResult, classify_intent
from src.safety.refusals import handle_refusal, should_short_circuit


@dataclass
class AskResult:
    query: str
    intent: IntentResult
    response: AssembledResponse
    retrieval: RetrievalResult | None = None
    generation: GenerationResult | None = None
    corpus_version: str | None = None
    model_version: str | None = None
    audit: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "intent": self.intent.as_dict(),
            "response": self.response.as_dict(),
            "retrieval": self.retrieval.as_dict() if self.retrieval else None,
            "generation": self.generation.as_dict() if self.generation else None,
            "corpus_version": self.corpus_version,
            "model_version": self.model_version,
            "audit": self.audit,
        }


def _candidates_to_chunk_dicts(
    candidates: list[Candidate],
    index: PublishedIndex,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for c in candidates:
        full = dict(index.chunks_by_id.get(c.chunk_id) or {})
        if not full:
            full = {
                "chunk_id": c.chunk_id,
                "source_id": c.source_id,
                "source_url": c.source_url,
                "scheme_code": c.scheme_code,
                "plan": c.plan,
                "text": c.text,
                "heading_path": c.heading_path,
                "tables": [],
                "fetched_at": (c.metadata or {}).get("fetched_at"),
            }
        # Prefer live candidate text if store missing
        if c.text and not full.get("text"):
            full["text"] = c.text
        if c.source_url and not full.get("source_url"):
            full["source_url"] = c.source_url
        out.append(full)
    return out


def ask(
    query: str,
    *,
    gen_cfg: GenerateConfig | None = None,
    client: LLMClient | None = None,
    index: PublishedIndex | None = None,
    tau: float | None = None,
) -> AskResult:
    """
    Full offline ask path (no UI):
      redact → classify → (refuse | retrieve → generate → validate → assemble)
    """
    config = gen_cfg or load_config()
    intent = classify_intent(query)  # redacts PII internally
    published = index or get_published_index()

    base_audit: dict[str, Any] = {
        "redacted_query": intent.redacted_query,
        "intent": intent.intent,
        "scheme_code": intent.scheme_code,
        "resolution": intent.resolution,
        "corpus_version": published.corpus_version,
        "model_version": config.model_version,
    }

    # --- refusal / non-factual short-circuit ---
    if should_short_circuit(intent.intent):
        handler = handle_refusal(intent.intent, scheme_code=intent.scheme_code)
        assembled = assemble_safety(handler, meta=base_audit)
        audit = {
            **base_audit,
            "path": "safety",
            "handler_kind": handler.kind,
            "model_version": config.model_version,
        }
        return AskResult(
            query=query,
            intent=intent,
            response=assembled,
            corpus_version=published.corpus_version,
            model_version=config.model_version,
            audit=audit,
        )

    # --- retrieve ---
    retrieval = retrieve(
        intent.redacted_query,
        index=published,
        tau=tau,
        apply_scheme_filter=True,
    )

    if retrieval.status != "ok" or not retrieval.chunks:
        msg = COVERAGE_GATE_FAIL
        if retrieval.status == "ambiguous":
            handler = handle_refusal("ambiguous", scheme_code=intent.scheme_code)
            assembled = assemble_safety(
                handler,
                meta={**base_audit, "retrieval_status": retrieval.status},
            )
        elif retrieval.status == "uncovered":
            handler = handle_refusal("uncovered_scheme", scheme_code=None)
            assembled = assemble_safety(
                handler,
                meta={**base_audit, "retrieval_status": retrieval.status},
            )
        else:
            assembled = assemble_coverage(
                msg,
                scheme_code=intent.scheme_code,
                meta={**base_audit, "retrieval_status": retrieval.status},
            )
        audit = {
            **base_audit,
            "path": "retrieval_short_circuit",
            "retrieval_status": retrieval.status,
            "model_version": config.model_version,
        }
        return AskResult(
            query=query,
            intent=intent,
            response=assembled,
            retrieval=retrieval,
            corpus_version=published.corpus_version,
            model_version=config.model_version,
            audit=audit,
        )

    chunk_dicts = _candidates_to_chunk_dicts(retrieval.chunks, published)
    # Generation must see the same abbreviation expansion retrieval uses.
    gen_query = normalise_query(intent.redacted_query).normalised
    try:
        generation = generate_answer(
            gen_query,
            chunk_dicts,
            scheme_code=intent.scheme_code,
            cfg=config,
            client=client,
        )
    except LLMAPIError as exc:
        assembled = assemble_api_error(
            str(exc),
            status_code=exc.status_code,
            meta={**base_audit, "path": "api_error"},
        )
        audit = {
            **base_audit,
            "path": "api_error",
            "api_error": str(exc),
            "status_code": exc.status_code,
            "is_rate_limit": exc.is_rate_limit,
            "model_version": config.model_version,
            "retrieval_status": retrieval.status,
            "chunk_ids": [c.chunk_id for c in retrieval.chunks],
        }
        return AskResult(
            query=query,
            intent=intent,
            response=assembled,
            retrieval=retrieval,
            corpus_version=published.corpus_version,
            model_version=config.model_version,
            audit=audit,
        )

    # Freshness from cited chunk
    fetched_at = None
    scheme_name = None
    if generation.cited_chunk_id and generation.cited_chunk_id in published.chunks_by_id:
        ch = published.chunks_by_id[generation.cited_chunk_id]
        fetched_at = ch.get("fetched_at")
        scheme_name = ch.get("scheme_name")
    elif chunk_dicts:
        fetched_at = chunk_dicts[0].get("fetched_at")
        scheme_name = chunk_dicts[0].get("scheme_name")

    # Distinguish groundedness/validator safe-fallback coverage from a real answer
    assembled = assemble_answer(
        generation.raw_output,
        citation_url=generation.cited_url,
        fetched_at=fetched_at,
        scheme_name=scheme_name,
        used_fallback=generation.used_fallback,
        meta={
            **base_audit,
            **generation.audit,
        },
    )

    audit = {
        **base_audit,
        "path": "generate",
        "model_version": generation.model_version,
        "chunk_ids": [c.chunk_id for c in retrieval.chunks],
        "retrieval_status": retrieval.status,
        "validator_verdicts": generation.audit.get("validator_verdicts"),
        "groundedness": generation.audit.get("groundedness"),
        "groundedness_first": generation.audit.get("groundedness_first"),
        "used_fallback": generation.used_fallback,
        "eval_bucket_hint": (
            "grounded-fail" if generation.used_fallback else "answered"
        ),
    }

    return AskResult(
        query=query,
        intent=intent,
        response=assembled,
        retrieval=retrieval,
        generation=generation,
        corpus_version=published.corpus_version,
        model_version=generation.model_version,
        audit=audit,
    )
