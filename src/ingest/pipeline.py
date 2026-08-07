"""End-to-end ingestion orchestration with atomic publish."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .chunker import chunk_document
from .corpus_loader import CorpusConfig, Source, load_corpus
from .diffing import diff_numeric, extract_attributes, load_previous_attributes, log_diffs
from .fetcher import fetch_source
from .hasher import load_hash_record, save_hash_record, utc_now_iso
from .indexes import build_bm25, publish_chroma, write_chunk_store
from .parser import parse_html
from .paths import EMBEDDING_MODEL, LOGS_DIR, PUBLISHED_POINTER, STAGING_DIR

logger = logging.getLogger("facts_desk.ingest")


@dataclass
class SourceRunResult:
    source_id: str
    url: str
    status: str  # fetched|unchanged|failed|reused_previous
    content_hash: str | None = None
    chunk_count: int = 0
    error: str | None = None
    numeric_diffs: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class IngestRunResult:
    corpus_version: str
    published: bool
    embedding_model: str
    chroma_collection: str | None
    sources: list[SourceRunResult]
    chunk_total: int
    message: str


def _next_corpus_version() -> str:
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    # Increment .N if same day versions exist
    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    existing = sorted(STAGING_DIR.glob(f"{day}.*"))
    n = 1
    if existing:
        try:
            n = max(int(p.name.split(".")[-1]) for p in existing) + 1
        except ValueError:
            n = len(existing) + 1
    return f"{day}.{n}"


def _load_previous_chunks_for_source(source_id: str) -> list[dict[str, Any]]:
    if not PUBLISHED_POINTER.exists():
        return []
    pointer = json.loads(PUBLISHED_POINTER.read_text(encoding="utf-8"))
    version = pointer.get("corpus_version")
    if not version:
        return []
    path = STAGING_DIR / version / "chunks.jsonl"
    if not path.exists():
        return []
    out = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            ch = json.loads(line)
            if ch.get("source_id") == source_id:
                out.append(ch)
    return out


def _process_source(
    source: Source,
    corpus: CorpusConfig,
    corpus_version: str,
    force: bool,
) -> tuple[SourceRunResult, list[dict[str, Any]], dict[str, Any] | None]:
    fetch = fetch_source(source.id, source.url, corpus)
    if not fetch.ok:
        # Keep previous chunks if any
        prev_chunks = _load_previous_chunks_for_source(source.id)
        if prev_chunks:
            logger.warning("Fetch failed for %s (%s); reusing previous chunks", source.id, fetch.error)
            return (
                SourceRunResult(
                    source_id=source.id,
                    url=source.url,
                    status="reused_previous",
                    content_hash=prev_chunks[0].get("content_hash"),
                    chunk_count=len(prev_chunks),
                    error=fetch.error,
                ),
                prev_chunks,
                None,
            )
        return (
            SourceRunResult(
                source_id=source.id,
                url=source.url,
                status="failed",
                error=fetch.error or "fetch failed",
            ),
            [],
            None,
        )

    prev_hash = load_hash_record(source.id)
    if not force and prev_hash and prev_hash.get("content_hash") == fetch.content_hash:
        prev_chunks = _load_previous_chunks_for_source(source.id)
        save_hash_record(
            source.id,
            {
                **prev_hash,
                "last_verified_at": fetch.fetched_at,
                "unchanged": True,
            },
        )
        if prev_chunks:
            # Refresh corpus_version stamp on reused chunks for this publish
            refreshed = []
            for ch in prev_chunks:
                c = dict(ch)
                c["corpus_version"] = corpus_version
                c["fetched_at"] = fetch.fetched_at
                refreshed.append(c)
            return (
                SourceRunResult(
                    source_id=source.id,
                    url=source.url,
                    status="unchanged",
                    content_hash=fetch.content_hash,
                    chunk_count=len(refreshed),
                ),
                refreshed,
                load_previous_attributes(source.id),
            )

    doc = parse_html(source.id, source.url, fetch.html, source.display_name)
    chunks = chunk_document(doc, source, fetch.content_hash, fetch.fetched_at, corpus_version)
    attrs = extract_attributes(source.id, source.scheme_code, doc.structured)
    prev_attrs = load_previous_attributes(source.id)
    diffs = diff_numeric(prev_attrs, attrs)
    if diffs:
        log_diffs(source.id, diffs, corpus_version)

    save_hash_record(
        source.id,
        {
            "source_id": source.id,
            "url": source.url,
            "content_hash": fetch.content_hash,
            "fetched_at": fetch.fetched_at,
            "last_verified_at": fetch.fetched_at,
            "status_code": fetch.status_code,
            "unchanged": False,
        },
    )

    return (
        SourceRunResult(
            source_id=source.id,
            url=source.url,
            status="fetched",
            content_hash=fetch.content_hash,
            chunk_count=len(chunks),
            numeric_diffs=diffs,
        ),
        chunks,
        attrs,
    )


def run_ingestion(
    force: bool = False,
    skip_embed: bool = False,
    corpus_path: Path | None = None,
) -> IngestRunResult:
    """
    Run full ingestion for all five allow-listed sources.

    On partial fetch failure: reuse previous chunks for that source.
    Never flips the published pointer if zero sources produced chunks.
    """
    corpus = load_corpus(corpus_path)
    corpus_version = _next_corpus_version()
    version_dir = STAGING_DIR / corpus_version
    version_dir.mkdir(parents=True, exist_ok=True)
    (version_dir / "attributes").mkdir(exist_ok=True)

    all_chunks: list[dict[str, Any]] = []
    source_results: list[SourceRunResult] = []
    attrs_by_source: dict[str, dict[str, Any]] = {}

    for source in corpus.sources:
        logger.info("Ingesting %s", source.id)
        result, chunks, attrs = _process_source(source, corpus, corpus_version, force=force)
        source_results.append(result)
        all_chunks.extend(chunks)
        if attrs:
            attrs_by_source[source.id] = attrs
            (version_dir / "attributes" / f"{source.id}.json").write_text(
                json.dumps(attrs, indent=2, ensure_ascii=True), encoding="utf-8"
            )

    if not all_chunks:
        msg = "No chunks produced; published pointer left unchanged."
        logger.error(msg)
        _write_run_log(corpus_version, source_results, published=False, message=msg)
        return IngestRunResult(
            corpus_version=corpus_version,
            published=False,
            embedding_model=corpus.embedding_model or EMBEDDING_MODEL,
            chroma_collection=None,
            sources=source_results,
            chunk_total=0,
            message=msg,
        )

    # Require all five scheme_codes represented when possible; if a source failed with no history, still publish others but warn
    present_sources = {c["source_id"] for c in all_chunks}
    missing = [s.id for s in corpus.sources if s.id not in present_sources]
    if missing:
        logger.warning("Missing sources in this build (no reusable history): %s", missing)

    write_chunk_store(version_dir, all_chunks)
    build_bm25(version_dir, all_chunks)

    chroma_collection = None
    model_name = corpus.embedding_model or EMBEDDING_MODEL
    if skip_embed:
        logger.warning("skip_embed=True — Chroma not updated")
    else:
        chroma_collection = publish_chroma(corpus_version, all_chunks, model_name=model_name)

    manifest = {
        "corpus_version": corpus_version,
        "published_at": utc_now_iso(),
        "embedding_model": model_name,
        "vector_store": "chroma_local",
        "chroma_collection": chroma_collection,
        "chunk_count": len(all_chunks),
        "sources": [asdict(r) for r in source_results],
        "format": "html_only",
        "amc": corpus.amc,
    }
    (version_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Atomic-ish publish: write pointer last
    PUBLISHED_POINTER.parent.mkdir(parents=True, exist_ok=True)
    pointer = {
        "corpus_version": corpus_version,
        "version_dir": str(version_dir),
        "chroma_collection": chroma_collection,
        "embedding_model": model_name,
        "published_at": utc_now_iso(),
        "chunk_count": len(all_chunks),
    }
    tmp = PUBLISHED_POINTER.with_suffix(".tmp")
    tmp.write_text(json.dumps(pointer, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(PUBLISHED_POINTER)

    msg = f"Published corpus_version={corpus_version} chunks={len(all_chunks)}"
    logger.info(msg)
    _write_run_log(corpus_version, source_results, published=True, message=msg, manifest=manifest)

    return IngestRunResult(
        corpus_version=corpus_version,
        published=True,
        embedding_model=model_name,
        chroma_collection=chroma_collection,
        sources=source_results,
        chunk_total=len(all_chunks),
        message=msg,
    )


def _write_run_log(
    corpus_version: str,
    sources: list[SourceRunResult],
    published: bool,
    message: str,
    manifest: dict[str, Any] | None = None,
) -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    path = LOGS_DIR / f"ingest_{corpus_version.replace('.', '_')}.json"
    payload = {
        "corpus_version": corpus_version,
        "published": published,
        "message": message,
        "sources": [asdict(s) for s in sources],
        "manifest": manifest,
        "logged_at": utc_now_iso(),
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
