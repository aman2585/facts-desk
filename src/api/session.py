"""Anonymous session id only — no login / account link (F6.3)."""

from __future__ import annotations

import re
import uuid

_SESSION_RE = re.compile(r"^[A-Za-z0-9_-]{8,128}$")


def mint_session_id() -> str:
    return str(uuid.uuid4())


def normalise_session_id(raw: str | None) -> str:
    """Accept client session id or mint a new one. Never ties to accounts."""
    if raw is None:
        return mint_session_id()
    value = raw.strip()
    if not value or not _SESSION_RE.fullmatch(value):
        return mint_session_id()
    return value
