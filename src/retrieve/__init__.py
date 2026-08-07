"""Hybrid retrieval (Phase 3): Chroma dense + BM25, rerank, confidence gate."""

from .config import RetrievalConfig, load_config
from .pipeline import RetrievalResult, retrieve

__all__ = [
    "RetrievalConfig",
    "RetrievalResult",
    "load_config",
    "retrieve",
]
