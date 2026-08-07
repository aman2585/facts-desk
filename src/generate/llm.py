"""LLM provider clients — OpenAI-compatible HTTP (Groq default).

Swap provider via config.yaml without changing prompt or validator code.
"""

from __future__ import annotations

import os
import time
from typing import Any, Protocol

import httpx

from src.generate.config import GenerateConfig, load_config


class LLMAPIError(Exception):
    """Raised when the model HTTP API fails after retries — must not become safe fallback."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        body: str | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.body = body

    @property
    def is_rate_limit(self) -> bool:
        return self.status_code == 429


class LLMClient(Protocol):
    @property
    def model_version(self) -> str: ...

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
    ) -> str: ...


class OpenAICompatibleClient:
    """Chat Completions client for Groq (and other OpenAI-compatible APIs)."""

    def __init__(self, cfg: GenerateConfig):
        self.cfg = cfg
        key = os.environ.get(cfg.api_key_env, "").strip()
        if not key:
            raise RuntimeError(
                f"Missing API key: set environment variable {cfg.api_key_env}"
            )
        self._api_key = key

    @property
    def model_version(self) -> str:
        return self.cfg.model_version

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
    ) -> str:
        temp = self.cfg.temperature if temperature is None else temperature
        payload: dict[str, Any] = {
            "model": self.cfg.model_id,
            "messages": messages,
            "temperature": temp,
            "max_tokens": self.cfg.max_tokens,
        }
        url = f"{self.cfg.api_base}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        max_retries = max(0, self.cfg.http_max_retries)
        last_exc: Exception | None = None

        for attempt in range(max_retries + 1):
            try:
                with httpx.Client(timeout=self.cfg.timeout_s) as client:
                    resp = client.post(url, headers=headers, json=payload)
            except httpx.HTTPError as exc:
                last_exc = exc
                if attempt >= max_retries:
                    raise LLMAPIError(
                        f"LLM HTTP transport error after {attempt + 1} attempt(s): {exc}"
                    ) from exc
                self._sleep_backoff(attempt)
                continue

            if resp.status_code == 429:
                retry_after = _retry_after_seconds(resp)
                if attempt >= max_retries:
                    raise LLMAPIError(
                        f"LLM rate limited (429) after {attempt + 1} attempt(s)",
                        status_code=429,
                        body=resp.text[:500],
                    )
                self._sleep_backoff(attempt, retry_after=retry_after)
                continue

            if resp.status_code >= 500:
                if attempt >= max_retries:
                    raise LLMAPIError(
                        f"LLM server error ({resp.status_code}) after {attempt + 1} attempt(s)",
                        status_code=resp.status_code,
                        body=resp.text[:500],
                    )
                self._sleep_backoff(attempt)
                continue

            if resp.status_code >= 400:
                raise LLMAPIError(
                    f"LLM API error ({resp.status_code})",
                    status_code=resp.status_code,
                    body=resp.text[:500],
                )

            data = resp.json()
            try:
                return str(data["choices"][0]["message"]["content"] or "").strip()
            except (KeyError, IndexError, TypeError) as exc:
                raise LLMAPIError(
                    f"Unexpected LLM response shape: {data!r}",
                    status_code=resp.status_code,
                ) from exc

        raise LLMAPIError(f"LLM call failed: {last_exc}")

    def _sleep_backoff(self, attempt: int, *, retry_after: float | None = None) -> None:
        base = self.cfg.http_retry_backoff_s
        cap = self.cfg.http_retry_backoff_max_s
        delay = min(cap, base * (2**attempt))
        if retry_after is not None and retry_after > 0:
            delay = max(delay, min(cap, retry_after))
        time.sleep(delay)


def _retry_after_seconds(resp: httpx.Response) -> float | None:
    raw = resp.headers.get("retry-after")
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def get_llm_client(cfg: GenerateConfig | None = None) -> LLMClient:
    """Factory — currently Groq via OpenAI-compatible endpoint; extend by provider."""
    config = cfg or load_config()
    if config.provider in {"groq", "openai_compatible", "openai"}:
        return OpenAICompatibleClient(config)
    raise ValueError(
        f"Unsupported LLM provider {config.provider!r}. "
        "Set provider in src/generate/config.yaml (supported: groq)."
    )
