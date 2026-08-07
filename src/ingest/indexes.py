"""Chunk store, BM25, and Chroma DB local vector index."""

from __future__ import annotations

import json
import pickle
import re
from pathlib import Path
from typing import Any

from rank_bm25 import BM25Okapi

from .embedder import embed_texts
from .paths import CHROMA_COLLECTION_PREFIX, CHROMA_DIR, EMBEDDING_MODEL


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def write_chunk_store(version_dir: Path, chunks: list[dict[str, Any]]) -> Path:
    """
    Persist chunks as UTF-8 JSONL.

    Uses ensure_ascii=True so non-ASCII (e.g. U+20B9 ₹) is stored as \\u20b9
    escapes. That keeps the file ASCII-safe under accidental cp1252 viewers
    (which otherwise render UTF-8 ₹ bytes as the mojibake â‚¹) while
    json.loads(...) still yields the correct Unicode rupee.
    """
    path = version_dir / "chunks.jsonl"
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for ch in chunks:
            f.write(json.dumps(ch, ensure_ascii=True) + "\n")

    # Round-trip verify: reload and confirm no mojibake, rupee intact where expected
    with path.open("r", encoding="utf-8") as f:
        first = f.readline()
    loaded = json.loads(first)
    text = loaded.get("text", "")
    if "\u00e2\u201a\u00b9" in text or "\u00e2" in text and "Minimum SIP" in text:
        raise ValueError("chunks.jsonl round-trip still contains mojibake rupee")
    if "Minimum SIP" in text and "\u20b9" not in text and "Rs" not in text:
        raise ValueError("chunks.jsonl round-trip lost rupee sign on Minimum SIP")
    # On-disk must not contain raw UTF-8 rupee bytes (force escapes)
    raw = path.read_bytes()
    if b"\xe2\x82\xb9" in raw:
        raise ValueError(
            "chunks.jsonl contains raw UTF-8 rupee bytes; expected \\u20b9 escapes "
            "(ensure_ascii=True)"
        )
    return path


def build_bm25(version_dir: Path, chunks: list[dict[str, Any]]) -> Path:
    corpus_tokens = [_tokenize(ch["text"]) for ch in chunks]
    bm25 = BM25Okapi(corpus_tokens)
    payload = {
        "chunk_ids": [ch["chunk_id"] for ch in chunks],
        "tokens": corpus_tokens,
    }
    # Persist tokens + ids; rebuild BM25 object on load for simplicity/portability
    path = version_dir / "bm25.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    # Also pickle a ready BM25 for smoke tests
    with (version_dir / "bm25.pkl").open("wb") as f:
        pickle.dump({"bm25": bm25, "chunk_ids": payload["chunk_ids"]}, f)
    return path


def load_bm25(version_dir: Path) -> tuple[BM25Okapi, list[str]]:
    with (version_dir / "bm25.pkl").open("rb") as f:
        data = pickle.load(f)
    return data["bm25"], data["chunk_ids"]


def _chroma_meta(ch: dict[str, Any]) -> dict[str, Any]:
    # Chroma metadata must be scalar
    return {
        "chunk_id": ch["chunk_id"],
        "source_id": ch["source_id"],
        "scheme_code": ch["scheme_code"],
        "plan": ch["plan"],
        "source_url": ch["source_url"],
        "corpus_version": ch["corpus_version"],
        "heading_path_str": ch.get("heading_path_str", ""),
        "fetched_at": ch.get("fetched_at", ""),
    }


def publish_chroma(corpus_version: str, chunks: list[dict[str, Any]], model_name: str = EMBEDDING_MODEL) -> str:
    import chromadb
    from chromadb.config import Settings

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(
        path=str(CHROMA_DIR),
        settings=Settings(anonymized_telemetry=False),
    )
    collection_name = f"{CHROMA_COLLECTION_PREFIX}{corpus_version.replace('.', '_').replace('-', '_')}"

    # Drop if re-publishing same version name
    existing = {c.name for c in client.list_collections()}
    if collection_name in existing:
        client.delete_collection(collection_name)

    collection = client.create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine", "embedding_model": model_name, "corpus_version": corpus_version},
    )

    texts = [ch["text"] for ch in chunks]
    vectors = embed_texts(texts, model_name=model_name)
    ids = [ch["chunk_id"] for ch in chunks]
    metas = [_chroma_meta(ch) for ch in chunks]

    # Upsert in batches
    batch = 32
    for i in range(0, len(ids), batch):
        collection.add(
            ids=ids[i : i + batch],
            embeddings=vectors[i : i + batch].tolist(),
            documents=texts[i : i + batch],
            metadatas=metas[i : i + batch],
        )

    return collection_name


def smoke_chroma_query(collection_name: str, scheme_code: str, query: str, model_name: str = EMBEDDING_MODEL) -> list[dict[str, Any]]:
    import chromadb
    from chromadb.config import Settings

    client = chromadb.PersistentClient(path=str(CHROMA_DIR), settings=Settings(anonymized_telemetry=False))
    collection = client.get_collection(collection_name)
    qvec = embed_texts([query], model_name=model_name)[0].tolist()
    result = collection.query(
        query_embeddings=[qvec],
        n_results=3,
        where={"scheme_code": scheme_code},
        include=["documents", "metadatas", "distances"],
    )
    hits = []
    for i, doc_id in enumerate(result["ids"][0]):
        hits.append(
            {
                "id": doc_id,
                "document": result["documents"][0][i],
                "metadata": result["metadatas"][0][i],
                "distance": result["distances"][0][i],
            }
        )
    return hits


def smoke_bm25_query(version_dir: Path, query: str, top_k: int = 3) -> list[dict[str, Any]]:
    bm25, chunk_ids = load_bm25(version_dir)
    scores = bm25.get_scores(_tokenize(query))
    ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:top_k]
    # Load chunk texts
    texts = {}
    with (version_dir / "chunks.jsonl").open(encoding="utf-8") as f:
        for line in f:
            ch = json.loads(line)
            texts[ch["chunk_id"]] = ch
    out = []
    for idx, score in ranked:
        cid = chunk_ids[idx]
        ch = texts.get(cid, {})
        out.append({"chunk_id": cid, "score": float(score), "scheme_code": ch.get("scheme_code"), "text": (ch.get("text") or "")[:200]})
    return out
