"""Load and validate the allow-listed corpus registry."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

from .paths import ALLOWED_HOST, CORPUS_PATH


@dataclass(frozen=True)
class Source:
    id: str
    url: str
    authority: str
    doc_type: str
    scheme_code: str
    display_name: str
    plan: str
    option: str
    numeric_fields: tuple[str, ...]
    owner: str


@dataclass(frozen=True)
class CorpusConfig:
    corpus_version_seed: str
    amc: str
    format: str
    embedding_model: str
    vector_store: str
    scheduler_cron: str
    scheduler_timezone: str
    sources: tuple[Source, ...]

    @property
    def allowlisted_urls(self) -> set[str]:
        return {s.url for s in self.sources}

    def source_by_id(self, source_id: str) -> Source:
        for s in self.sources:
            if s.id == source_id:
                return s
        raise KeyError(source_id)


def _require_html_only(data: dict[str, Any]) -> None:
    if data.get("format") != "html_only":
        raise ValueError("corpus.format must be html_only (no PDFs)")
    blob = yaml.safe_dump(data).lower()
    if ".pdf" in blob:
        raise ValueError("PDF references are not allowed in corpus.yaml")


def load_corpus(path: Path | None = None) -> CorpusConfig:
    path = path or CORPUS_PATH
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    _require_html_only(data)

    sources: list[Source] = []
    for raw in data["sources"]:
        url = raw["url"].strip()
        host = urlparse(url).netloc.lower()
        if host != ALLOWED_HOST and not host.endswith("." + ALLOWED_HOST):
            raise ValueError(f"URL host not allow-listed: {url}")
        schemes = raw.get("schemes") or []
        if not schemes:
            raise ValueError(f"Source {raw['id']} missing schemes")
        sources.append(
            Source(
                id=raw["id"],
                url=url,
                authority=raw.get("authority", "Groww"),
                doc_type=raw.get("doc_type", "groww_scheme_page"),
                scheme_code=schemes[0],
                display_name=raw.get("display_name") or schemes[0],
                plan=raw.get("plan", "Direct"),
                option=raw.get("option", "Growth"),
                numeric_fields=tuple(raw.get("numeric_fields") or []),
                owner=raw.get("owner", "content-ops"),
            )
        )

    if len(sources) != 5:
        raise ValueError(f"Expected exactly 5 sources, found {len(sources)}")

    sched = data.get("scheduler") or {}
    return CorpusConfig(
        corpus_version_seed=str(data.get("corpus_version", "")),
        amc=data.get("amc", "HDFC Mutual Fund"),
        format=data["format"],
        embedding_model=data.get("embedding_model", "BAAI/bge-large-en-v1.5"),
        vector_store=data.get("vector_store", "chroma_local"),
        scheduler_cron=sched.get("cron", "15 9 * * *"),
        scheduler_timezone=sched.get("timezone", "Asia/Kolkata"),
        sources=tuple(sources),
    )
