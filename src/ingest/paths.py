"""Shared paths and constants for ingestion."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORPUS_PATH = ROOT / "corpus" / "corpus.yaml"
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
STAGING_DIR = DATA_DIR / "staging"
CHROMA_DIR = DATA_DIR / "chroma"
HASHES_DIR = DATA_DIR / "hashes"
LOGS_DIR = DATA_DIR / "logs"
DIFFS_DIR = DATA_DIR / "diffs"
PUBLISHED_POINTER = DATA_DIR / "published" / "current.json"

EMBEDDING_MODEL = "BAAI/bge-large-en-v1.5"
EMBEDDING_DIM = 1024
CHROMA_COLLECTION_PREFIX = "facts_desk_"

ALLOWED_HOST = "groww.in"
USER_AGENT = "FactsDeskIngest/0.2 (+https://localhost; facts-only research)"
FETCH_TIMEOUT_S = 30
FETCH_RETRIES = 2

# Approx tokens ≈ words * 1.3; target 300–600 tokens → keep ≤ ~350 words hard cap
CHUNK_MIN_WORDS = 40
CHUNK_MAX_WORDS = 350
CHUNK_OVERLAP_WORDS = 40

# Bump when parser/chunker exclusion or formatting logic changes so
# content_hash invalidates and re-ingest rebuilds (not only fund-field diffs).
PARSER_CHUNKER_VERSION = "2026-08-07.perf1"
