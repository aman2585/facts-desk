"""Response cache keyed on hash(normalised_redacted_query + corpus_version).

Invalidated when the published corpus_version changes (on publish).
"""

from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path
from typing import Any

from src.api.cards import card_to_dict, parse_card
from src.api.config import ApiConfig, load_config
from src.ingest.paths import PUBLISHED_POINTER
from src.retrieve.normaliser import normalise_query
from src.safety.pii import redact_pii

_META_NAME = "_cache_meta.json"
_lock = threading.Lock()
_last_seen_version: str | None = None


def _read_published_version() -> str:
    if not PUBLISHED_POINTER.exists():
        return "unpublished"
    try:
        data = json.loads(PUBLISHED_POINTER.read_text(encoding="utf-8"))
        return str(data.get("corpus_version") or "unpublished")
    except (OSError, json.JSONDecodeError):
        return "unpublished"


def cache_key(normalised_redacted_query: str, corpus_version: str) -> str:
    material = f"{normalised_redacted_query}|{corpus_version}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def normalised_redacted_query(query: str) -> str:
    """Redact PII then normalise — never use raw query in the cache key."""
    redacted = redact_pii(query).redacted
    return normalise_query(redacted).normalised


def invalidate_cache(cfg: ApiConfig | None = None) -> None:
    """Wipe all cached cards. Call on corpus publish (or auto via version watch)."""
    global _last_seen_version
    config = cfg or load_config()
    with _lock:
        if config.cache_dir.exists():
            for path in config.cache_dir.glob("*.json"):
                try:
                    path.unlink()
                except OSError:
                    pass
        config.cache_dir.mkdir(parents=True, exist_ok=True)
        version = _read_published_version()
        _write_meta(config.cache_dir, version)
        _last_seen_version = version


def _write_meta(cache_dir: Path, corpus_version: str) -> None:
    meta_path = cache_dir / _META_NAME
    meta_path.write_text(
        json.dumps({"corpus_version": corpus_version}, indent=2),
        encoding="utf-8",
    )


def _ensure_version(cfg: ApiConfig) -> str:
    """If published corpus_version changed, invalidate the whole cache."""
    global _last_seen_version
    current = _read_published_version()
    cfg.cache_dir.mkdir(parents=True, exist_ok=True)
    meta_path = cfg.cache_dir / _META_NAME
    stored: str | None = None
    if meta_path.exists():
        try:
            stored = str(
                json.loads(meta_path.read_text(encoding="utf-8")).get(
                    "corpus_version"
                )
            )
        except (OSError, json.JSONDecodeError, TypeError):
            stored = None
    if _last_seen_version is None:
        _last_seen_version = stored
    if stored != current or _last_seen_version != current:
        # Drop entries from prior corpus_version (publish invalidation).
        for path in cfg.cache_dir.glob("*.json"):
            if path.name == _META_NAME:
                continue
            try:
                path.unlink()
            except OSError:
                pass
        _write_meta(cfg.cache_dir, current)
        _last_seen_version = current
    return current


def get_cached_card(
    query: str,
    *,
    cfg: ApiConfig | None = None,
) -> tuple[dict[str, Any] | None, str, str]:
    """
    Returns (card_dict_or_None, cache_key, corpus_version).
    """
    config = cfg or load_config()
    with _lock:
        version = _ensure_version(config)
        if not config.cache_enabled:
            nrq = normalised_redacted_query(query)
            return None, cache_key(nrq, version), version
        nrq = normalised_redacted_query(query)
        key = cache_key(nrq, version)
        path = config.cache_dir / f"{key}.json"
        if not path.exists():
            return None, key, version
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("corpus_version") != version:
                path.unlink(missing_ok=True)
                return None, key, version
            card = payload.get("card")
            if not isinstance(card, dict):
                return None, key, version
            # Validate shape
            parse_card(card)
            return card, key, version
        except (OSError, json.JSONDecodeError, ValueError):
            return None, key, version


def put_cached_card(
    query: str,
    card: Any,
    *,
    cfg: ApiConfig | None = None,
) -> str:
    """Store card for key. Skips api_error cards. Returns cache key."""
    config = cfg or load_config()
    card_dict = card_to_dict(card) if hasattr(card, "model_dump") else dict(card)
    if card_dict.get("type") == "api_error":
        nrq = normalised_redacted_query(query)
        version = _read_published_version()
        return cache_key(nrq, version)

    with _lock:
        version = _ensure_version(config)
        if not config.cache_enabled:
            nrq = normalised_redacted_query(query)
            return cache_key(nrq, version)
        nrq = normalised_redacted_query(query)
        key = cache_key(nrq, version)
        path = config.cache_dir / f"{key}.json"
        path.write_text(
            json.dumps(
                {
                    "cache_key": key,
                    "corpus_version": version,
                    "normalised_redacted_query": nrq,
                    "card": card_dict,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return key
