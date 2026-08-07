"""API config — rate limits, cache/audit paths."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from src.ingest.paths import DATA_DIR

_CONFIG_PATH = Path(__file__).resolve().parent / "config.yaml"


@dataclass(frozen=True)
class ApiConfig:
    session_max_requests: int
    session_window_s: float
    ip_max_requests: int
    ip_window_s: float
    cache_enabled: bool
    cache_dir: Path
    audit_dir: Path
    stream_default: bool


@lru_cache(maxsize=1)
def load_config(path: Path | None = None) -> ApiConfig:
    cfg_path = path or _CONFIG_PATH
    data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    rl = data.get("rate_limit") or {}
    cache = data.get("cache") or {}
    audit = data.get("audit") or {}
    cache_rel = str(cache.get("dir") or "cache/responses")
    audit_rel = str(audit.get("dir") or "logs/audit")
    return ApiConfig(
        session_max_requests=int(rl.get("session_max_requests") or 30),
        session_window_s=float(rl.get("session_window_s") or 60),
        ip_max_requests=int(rl.get("ip_max_requests") or 60),
        ip_window_s=float(rl.get("ip_window_s") or 60),
        cache_enabled=bool(cache.get("enabled", True)),
        cache_dir=DATA_DIR / cache_rel,
        audit_dir=DATA_DIR / audit_rel,
        stream_default=bool(data.get("stream_default", True)),
    )


def clear_config_cache() -> None:
    load_config.cache_clear()
