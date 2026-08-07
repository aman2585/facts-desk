"""Extractive generator: LLM → validate → regen once → safe fallback."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

from src.generate.config import GenerateConfig, load_config
from src.generate.groundedness import GroundednessResult, verify_groundedness
from src.generate.labelled_attrs import complete_labelled_attributes
from src.generate.llm import LLMClient, get_llm_client
from src.generate.prompt import build_messages
from src.generate.validator import ValidationResult, extract_urls, validate_answer

SAFE_FALLBACK_BODY = (
    "I couldn't find that in my official sources, so I'd rather not guess."
)


@dataclass
class GenerationResult:
    raw_output: str
    used_fallback: bool
    attempts: int
    validator: ValidationResult
    groundedness: GroundednessResult
    model_version: str
    cited_url: str | None = None
    cited_chunk_id: str | None = None
    cited_chunk_text: str = ""
    retrieved_text: str = ""
    audit: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "raw_output": self.raw_output,
            "used_fallback": self.used_fallback,
            "attempts": self.attempts,
            "validator": self.validator.as_dict(),
            "groundedness": self.groundedness.as_dict(),
            "model_version": self.model_version,
            "cited_url": self.cited_url,
            "cited_chunk_id": self.cited_chunk_id,
            "audit": self.audit,
        }


def _chunk_payloads(chunks: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for ch in chunks:
        out.append(
            {
                "chunk_id": ch.get("chunk_id"),
                "source_id": ch.get("source_id"),
                "source_url": ch.get("source_url"),
                "scheme_code": ch.get("scheme_code"),
                "scheme_name": ch.get("scheme_name"),
                "heading_path": ch.get("heading_path") or [],
                "heading_path_str": ch.get("heading_path_str"),
                "text": ch.get("text") or "",
                "tables": ch.get("tables") or [],
                "fetched_at": ch.get("fetched_at"),
            }
        )
    return out


def _joined_retrieved_text(chunks: Sequence[dict[str, Any]]) -> str:
    parts: list[str] = []
    for ch in chunks:
        parts.append(ch.get("text") or "")
        for row in ch.get("tables") or []:
            parts.append(f"{row.get('label', '')}: {row.get('value', '')}")
    return "\n".join(parts)


def _resolve_cited_chunk(
    answer: str,
    chunks: Sequence[dict[str, Any]],
) -> tuple[str | None, str | None, str]:
    urls = extract_urls(answer)
    if not urls:
        if chunks:
            ch = chunks[0]
            return (
                str(ch.get("source_url") or "") or None,
                str(ch.get("chunk_id") or "") or None,
                _joined_retrieved_text([ch]),
            )
        return None, None, ""
    cite = urls[0].rstrip("/")
    for ch in chunks:
        url = str(ch.get("source_url") or "").rstrip("/")
        if url == cite:
            return cite, str(ch.get("chunk_id") or "") or None, _joined_retrieved_text([ch])
    return cite, None, _joined_retrieved_text(chunks)


def _safe_fallback_output(chunks: Sequence[dict[str, Any]]) -> str:
    url = ""
    for ch in chunks:
        if ch.get("source_url"):
            url = str(ch["source_url"])
            break
    if url:
        return f"{SAFE_FALLBACK_BODY}\n\n{url}"
    return SAFE_FALLBACK_BODY


def generate_answer(
    query: str,
    chunks: Sequence[dict[str, Any]],
    *,
    scheme_code: str | None = None,
    cfg: GenerateConfig | None = None,
    client: LLMClient | None = None,
) -> GenerationResult:
    """
    Extractive generation with deterministic validation.

    Fail closed: validate → regenerate once → else safe fallback.
    Groundedness must pass on the cited chunk; else safe fallback.
    """
    config = cfg or load_config()
    llm = client or get_llm_client(config)
    model_version = llm.model_version
    payloads = _chunk_payloads(chunks)
    retrieved_text = _joined_retrieved_text(payloads)

    if not payloads:
        fb = SAFE_FALLBACK_BODY
        validator = validate_answer(fb, cited_chunk_text="")
        grounded = GroundednessResult(False, "no_chunks")
        return GenerationResult(
            raw_output=fb,
            used_fallback=True,
            attempts=0,
            validator=validator,
            groundedness=grounded,
            model_version=model_version,
            retrieved_text="",
            audit={
                "model_version": model_version,
                "validator_verdicts": [validator.as_dict()],
                "groundedness": grounded.as_dict(),
                "fallback_reason": "no_chunks",
            },
        )

    prior_failures: list[str] = []
    verdicts: list[dict] = []
    raw = ""
    validator = ValidationResult(passed=False, failed_checks=["not_run"])
    attempts = 0

    for attempt in range(1, 3):
        attempts = attempt
        messages = build_messages(
            query,
            payloads,
            scheme_code=scheme_code,
            prior_failures=prior_failures or None,
        )
        raw = llm.complete(messages, temperature=config.temperature)
        # Complete Category + Sub-category when chunk has both labelled pairs
        # (fixes under-specified paraphrases like "is a Mid Cap scheme").
        raw = complete_labelled_attributes(query, raw, payloads)
        validator = validate_answer(raw, cited_chunk_text=retrieved_text)
        verdicts.append({"attempt": attempt, **validator.as_dict()})
        if validator.passed:
            break
        prior_failures = list(validator.failed_checks)

    used_fallback = False
    if not validator.passed:
        raw = _safe_fallback_output(payloads)
        used_fallback = True
        validator = validate_answer(raw, cited_chunk_text=retrieved_text)
        verdicts.append({"attempt": "fallback", **validator.as_dict()})

    cited_url, cited_chunk_id, cited_text = _resolve_cited_chunk(raw, payloads)
    grounded_first = verify_groundedness(raw, cited_text)
    grounded = grounded_first
    grounded_fallback_result: GroundednessResult | None = None

    if not used_fallback and not grounded_first.passed:
        raw = _safe_fallback_output(payloads)
        used_fallback = True
        validator = validate_answer(raw, cited_chunk_text=retrieved_text)
        cited_url, cited_chunk_id, cited_text = _resolve_cited_chunk(raw, payloads)
        grounded_fallback_result = verify_groundedness(raw, cited_text)
        grounded = grounded_fallback_result
        verdicts.append(
            {
                "attempt": "groundedness_fallback",
                **validator.as_dict(),
                "groundedness": grounded_fallback_result.as_dict(),
            }
        )

    audit = {
        "model_version": model_version,
        "provider": config.provider,
        "model_id": config.model_id,
        "temperature": config.temperature,
        "validator_verdicts": verdicts,
        "groundedness_first": grounded_first.as_dict(),
        "groundedness_fallback": (
            grounded_fallback_result.as_dict() if grounded_fallback_result else None
        ),
        "groundedness": grounded.as_dict(),
        "used_fallback": used_fallback,
        "attempts": attempts,
        "cited_url": cited_url,
        "cited_chunk_id": cited_chunk_id,
        "chunk_ids": [c.get("chunk_id") for c in payloads],
    }

    return GenerationResult(
        raw_output=raw,
        used_fallback=used_fallback,
        attempts=attempts,
        validator=validator,
        groundedness=grounded,
        model_version=model_version,
        cited_url=cited_url,
        cited_chunk_id=cited_chunk_id,
        cited_chunk_text=cited_text,
        retrieved_text=retrieved_text,
        audit=audit,
    )
