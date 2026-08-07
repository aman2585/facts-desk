"""Load published chunk store, BM25, and Chroma collection from current pointer."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from src.ingest.indexes import load_bm25
from src.ingest.paths import CHROMA_DIR, PUBLISHED_POINTER


@dataclass
class PublishedIndex:
    corpus_version: str
    version_dir: Path
    chroma_collection: str
    embedding_model: str
    chunks_by_id: dict[str, dict[str, Any]]
    chunk_ids: list[str]


def load_published_pointer(path: Path | None = None) -> dict[str, Any]:
    pointer_path = path or PUBLISHED_POINTER
    if not pointer_path.exists():
        raise FileNotFoundError(f"Published pointer missing: {pointer_path}")
    return json.loads(pointer_path.read_text(encoding="utf-8"))


def load_chunks(version_dir: Path) -> dict[str, dict[str, Any]]:
    path = version_dir / "chunks.jsonl"
    out: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            ch = json.loads(line)
            out[ch["chunk_id"]] = ch
    return out


@lru_cache(maxsize=1)
def get_published_index() -> PublishedIndex:
    pointer = load_published_pointer()
    version_dir = Path(pointer["version_dir"])
    chunks = load_chunks(version_dir)
    return PublishedIndex(
        corpus_version=str(pointer["corpus_version"]),
        version_dir=version_dir,
        chroma_collection=str(pointer["chroma_collection"]),
        embedding_model=str(pointer.get("embedding_model") or "BAAI/bge-large-en-v1.5"),
        chunks_by_id=chunks,
        chunk_ids=list(chunks.keys()),
    )


def clear_index_cache() -> None:
    get_published_index.cache_clear()


def get_bm25(version_dir: Path | None = None):
    idx = get_published_index()
    return load_bm25(version_dir or idx.version_dir)


def get_chroma_collection(collection_name: str | None = None):
    import chromadb
    from chromadb.config import Settings

    idx = get_published_index()
    name = collection_name or idx.chroma_collection
    client = chromadb.PersistentClient(
        path=str(CHROMA_DIR),
        settings=Settings(anonymized_telemetry=False),
    )
    return client.get_collection(name)
