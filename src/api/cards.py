"""Discriminated response cards — UI switches on `type`, never parses prose."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Any, Literal

import yaml
from pydantic import BaseModel, Field

from src.generate.assembler import AssembledResponse
from src.ingest.paths import CORPUS_PATH

CardType = Literal[
    "answer",
    "refusal",
    "coverage",
    "performance_redirect",
    "clarify",
    "api_error",
]


class SchemeOption(BaseModel):
    scheme_code: str
    label: str
    url: str


class AnswerCard(BaseModel):
    type: Literal["answer"] = "answer"
    text: str
    citation_url: str
    source_label: str | None = None
    freshness_date: str | None = None
    corpus_version: str | None = None


class RefusalCard(BaseModel):
    type: Literal["refusal"] = "refusal"
    text: str
    educational_url: str | None = None
    corpus_version: str | None = None


class CoverageCard(BaseModel):
    type: Literal["coverage"] = "coverage"
    text: str
    citation_url: str | None = None
    source_label: str | None = None
    freshness_date: str | None = None
    corpus_version: str | None = None


class PerformanceRedirectCard(BaseModel):
    type: Literal["performance_redirect"] = "performance_redirect"
    text: str
    scheme_url: str | None = None
    corpus_version: str | None = None


class ClarifyCard(BaseModel):
    type: Literal["clarify"] = "clarify"
    text: str
    options: list[SchemeOption] = Field(default_factory=list)
    corpus_version: str | None = None


class ApiErrorCard(BaseModel):
    type: Literal["api_error"] = "api_error"
    text: str
    status_code: int | None = None
    corpus_version: str | None = None


ResponseCard = Annotated[
    AnswerCard
    | RefusalCard
    | CoverageCard
    | PerformanceRedirectCard
    | ClarifyCard
    | ApiErrorCard,
    Field(discriminator="type"),
]


@lru_cache(maxsize=1)
def scheme_options() -> tuple[SchemeOption, ...]:
    """Allow-listed scheme chips for clarify cards (corpus.yaml order)."""
    data = yaml.safe_load(CORPUS_PATH.read_text(encoding="utf-8")) or {}
    out: list[SchemeOption] = []
    for src in data.get("sources") or []:
        schemes = src.get("schemes") or []
        if not schemes:
            continue
        out.append(
            SchemeOption(
                scheme_code=str(schemes[0]),
                label=str(src.get("display_name") or schemes[0]),
                url=str(src.get("url") or "").rstrip("/"),
            )
        )
    return tuple(out)


def card_to_dict(card: BaseModel) -> dict[str, Any]:
    return card.model_dump(mode="json")


def assemble_to_card(
    assembled: AssembledResponse,
    *,
    corpus_version: str | None,
) -> AnswerCard | RefusalCard | CoverageCard | PerformanceRedirectCard | ClarifyCard | ApiErrorCard:
    """Map assembler response_type → API card discriminated union."""
    rtype = assembled.response_type
    cv = corpus_version

    if rtype == "answer":
        url = (assembled.citation_url or "").rstrip("/")
        if not url:
            # Contract requires citation on answers; degrade to coverage if missing.
            return CoverageCard(
                text=assembled.text,
                citation_url=None,
                source_label=assembled.source_label,
                freshness_date=assembled.freshness_date,
                corpus_version=cv,
            )
        return AnswerCard(
            text=assembled.text,
            citation_url=url,
            source_label=assembled.source_label,
            freshness_date=assembled.freshness_date,
            corpus_version=cv,
        )

    if rtype == "performance":
        return PerformanceRedirectCard(
            text=assembled.text,
            scheme_url=(assembled.citation_url or None),
            corpus_version=cv,
        )

    if rtype == "clarify":
        return ClarifyCard(
            text=assembled.text,
            options=list(scheme_options()),
            corpus_version=cv,
        )

    if rtype == "api_error":
        status = None
        if isinstance(assembled.meta, dict):
            raw = assembled.meta.get("status_code")
            status = int(raw) if raw is not None else None
        return ApiErrorCard(
            text=assembled.text,
            status_code=status,
            corpus_version=cv,
        )

    if rtype == "coverage":
        return CoverageCard(
            text=assembled.text,
            citation_url=assembled.citation_url,
            source_label=assembled.source_label,
            freshness_date=assembled.freshness_date,
            corpus_version=cv,
        )

    # refusal + pii_warn → refusal card (UI switches on type only)
    return RefusalCard(
        text=assembled.text,
        educational_url=assembled.educational_url,
        corpus_version=cv,
    )


def parse_card(data: dict[str, Any]) -> BaseModel:
    """Rehydrate a cached card dict into a typed model."""
    t = data.get("type")
    mapping: dict[str, type[BaseModel]] = {
        "answer": AnswerCard,
        "refusal": RefusalCard,
        "coverage": CoverageCard,
        "performance_redirect": PerformanceRedirectCard,
        "clarify": ClarifyCard,
        "api_error": ApiErrorCard,
    }
    cls = mapping.get(str(t))
    if cls is None:
        raise ValueError(f"Unknown card type: {t!r}")
    return cls.model_validate(data)
