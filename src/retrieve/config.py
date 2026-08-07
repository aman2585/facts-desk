"""Load Phase 3 retrieval config."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

CONFIG_PATH = Path(__file__).resolve().parent / "config.yaml"


@dataclass(frozen=True)
class RetrievalConfig:
    embedding_model: str
    reranker_model: str
    dense_top_k: int
    bm25_top_k: int
    rerank_top_k: int
    tau: float
    ambiguity_min_schemes: int
    plan_default: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RetrievalConfig":
        return cls(
            embedding_model=str(data.get("embedding_model", "BAAI/bge-large-en-v1.5")),
            reranker_model=str(data.get("reranker_model", "BAAI/bge-reranker-base")),
            dense_top_k=int(data.get("dense_top_k", 20)),
            bm25_top_k=int(data.get("bm25_top_k", 20)),
            rerank_top_k=int(data.get("rerank_top_k", 5)),
            tau=float(data.get("tau", 0.0)),
            ambiguity_min_schemes=int(data.get("ambiguity_min_schemes", 2)),
            plan_default=str(data.get("plan_default", "Direct")),
        )


def load_config(path: Path | None = None) -> RetrievalConfig:
    cfg_path = path or CONFIG_PATH
    data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    return RetrievalConfig.from_dict(data)
