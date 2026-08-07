"""In-memory sliding-window rate limit per session and IP (F6.6)."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass

from src.api.config import ApiConfig, load_config


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    retry_after_s: float | None = None
    scope: str | None = None  # "session" | "ip"


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._session: dict[str, deque[float]] = defaultdict(deque)
        self._ip: dict[str, deque[float]] = defaultdict(deque)

    def _prune(self, q: deque[float], now: float, window_s: float) -> None:
        cutoff = now - window_s
        while q and q[0] < cutoff:
            q.popleft()

    def check(
        self,
        *,
        session_id: str,
        ip: str,
        cfg: ApiConfig | None = None,
    ) -> RateLimitDecision:
        config = cfg or load_config()
        now = time.monotonic()
        with self._lock:
            sq = self._session[session_id]
            self._prune(sq, now, config.session_window_s)
            if len(sq) >= config.session_max_requests:
                oldest = sq[0]
                retry = max(0.0, config.session_window_s - (now - oldest))
                return RateLimitDecision(
                    allowed=False, retry_after_s=retry, scope="session"
                )

            iq = self._ip[ip or "unknown"]
            self._prune(iq, now, config.ip_window_s)
            if len(iq) >= config.ip_max_requests:
                oldest = iq[0]
                retry = max(0.0, config.ip_window_s - (now - oldest))
                return RateLimitDecision(
                    allowed=False, retry_after_s=retry, scope="ip"
                )

            sq.append(now)
            iq.append(now)
            return RateLimitDecision(allowed=True)


# Process-wide limiter (API single-process v1).
limiter = SlidingWindowLimiter()
