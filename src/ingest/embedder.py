"""Local embedder: BAAI/bge-large-en-v1.5 via sentence-transformers."""

from __future__ import annotations

from functools import lru_cache
from typing import Sequence

import numpy as np

from .paths import EMBEDDING_MODEL


@lru_cache(maxsize=1)
def get_model(model_name: str = EMBEDDING_MODEL):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)


def embed_texts(texts: Sequence[str], model_name: str = EMBEDDING_MODEL, batch_size: int = 16) -> np.ndarray:
    """Return L2-normalised embeddings (cosine-friendly) as float32 array [n, 1024]."""
    if not texts:
        return np.zeros((0, 1024), dtype=np.float32)
    model = get_model(model_name)
    vectors = model.encode(
        list(texts),
        batch_size=batch_size,
        show_progress_bar=len(texts) > 8,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )
    return np.asarray(vectors, dtype=np.float32)
