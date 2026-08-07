"""Generation config — provider / model / temperature (swappable)."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

_CONFIG_PATH = Path(__file__).resolve().parent / "config.yaml"


@dataclass(frozen=True)
class GenerateConfig:
    provider: str
    model_id: str
    temperature: float
    max_tokens: int
    api_base: str
    api_key_env: str
    timeout_s: float
    http_max_retries: int
    http_retry_backoff_s: float
    http_retry_backoff_max_s: float
    eval_query_delay_s: float

    @property
    def model_version(self) -> str:
        """Audit metadata string: provider:model_id."""
        return f"{self.provider}:{self.model_id}"


@lru_cache(maxsize=1)
def load_config(path: Path | None = None) -> GenerateConfig:
    cfg_path = path or _CONFIG_PATH
    data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    return GenerateConfig(
        provider=str(data.get("provider") or "groq").strip().lower(),
        model_id=str(data.get("model_id") or "llama-3.1-8b-instant").strip(),
        temperature=float(data.get("temperature", 0.0)),
        max_tokens=int(data.get("max_tokens") or 256),
        api_base=str(
            data.get("api_base") or "https://api.groq.com/openai/v1"
        ).rstrip("/"),
        api_key_env=str(data.get("api_key_env") or "GROQ_API_KEY").strip(),
        timeout_s=float(data.get("timeout_s") or 60),
        http_max_retries=int(data.get("http_max_retries") or 5),
        http_retry_backoff_s=float(data.get("http_retry_backoff_s") or 1.0),
        http_retry_backoff_max_s=float(data.get("http_retry_backoff_max_s") or 60.0),
        eval_query_delay_s=float(data.get("eval_query_delay_s") or 2.0),
    )


def clear_config_cache() -> None:
    load_config.cache_clear()
