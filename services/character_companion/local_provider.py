#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Local LLM provider for Character Companion (V1).

A thin ``ProviderFactory`` -- ``Callable[[recorder|None], Callable[[list], str]]``
matching :data:`services.character_lab.runtime_service.ProviderFactory` exactly
-- that sends the ALREADY-ASSEMBLED provider request (the exact ``messages``
list built by ``RuntimeService`` / the Grounded policy) to a locally running
LLM server and returns the plain assistant text.

Scope of this adapter (everything host-specific is isolated HERE):
- talks the Ollama-native ``POST /api/chat`` shape (``{model, messages,
  stream:false}`` -> ``message.content``), the same shape the repo's existing
  ``tools/llm_provider._complete_local`` already uses;
- rejects any non-loopback base URL by default (127.0.0.1 / localhost / ::1);
- requires NO API key and reads NO cloud credential env vars;
- never retries, never falls back to a cloud provider, never rebuilds any
  prompt / grounding / memory / epistemic / scene / history layer;
- fails closed: connection refused / timeout / non-2xx / malformed JSON /
  missing content / blank content all raise :class:`LocalLLMProviderError`.

Provider selection is explicit via ``COMPANION_PROVIDER`` (``fake`` | ``local``).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Optional
from urllib.parse import urlsplit

__all__ = [
    "LocalLLMProviderError",
    "LocalLLMConfig",
    "assert_loopback_url",
    "build_local_llm_provider_factory",
    "resolve_companion_provider_factory",
    "PROVIDER_FAKE",
    "PROVIDER_LOCAL",
]

PROVIDER_FAKE = "fake"
PROVIDER_LOCAL = "local"

# Hosts accepted by default. This slice is LOCAL LLM only -- arbitrary remote
# endpoints are refused until a future explicit configuration feature adds them.
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})

DEFAULT_LOCAL_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_LOCAL_MODEL = "llama3"
DEFAULT_LOCAL_TIMEOUT_S = 120.0
#: Ollama `options.num_ctx` bounds -- modest; no giant default. Unset => the
#: request shape is unchanged (server default context).
NUM_CTX_MIN = 512
NUM_CTX_MAX = 131072


class LocalLLMProviderError(RuntimeError):
    """Fail-closed local-provider error. ``code`` is a small fixed vocabulary:
    ``provider_unavailable`` (server down / unreachable / timed out) or
    ``provider_failed`` (reached the server, but the response was unusable)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def assert_loopback_url(base_url: str) -> str:
    """Return ``base_url`` unchanged if it targets a loopback host, else raise.

    Accepts ``127.0.0.1``, ``localhost`` and ``::1`` (bracketed or not) over
    http/https. Any other host -- a public name or a routable IP -- is refused.
    """
    if not isinstance(base_url, str) or not base_url.strip():
        raise LocalLLMProviderError("provider_failed", "LOCAL_LLM_BASE_URL must be a non-empty string")
    parts = urlsplit(base_url.strip())
    if parts.scheme not in ("http", "https"):
        raise LocalLLMProviderError("provider_failed", f"unsupported URL scheme {parts.scheme!r}")
    host = (parts.hostname or "").lower()
    if host not in _LOOPBACK_HOSTS:
        raise LocalLLMProviderError(
            "provider_failed",
            f"local LLM base URL must be loopback ({sorted(_LOOPBACK_HOSTS)}); "
            f"refusing host {host!r}",
        )
    return base_url.strip()


@dataclass(frozen=True)
class LocalLLMConfig:
    base_url: str = DEFAULT_LOCAL_BASE_URL
    model: str = DEFAULT_LOCAL_MODEL
    timeout_s: float = DEFAULT_LOCAL_TIMEOUT_S
    num_ctx: Optional[int] = None   # when set -> Ollama options.num_ctx

    def __post_init__(self) -> None:
        assert_loopback_url(self.base_url)
        if not isinstance(self.model, str) or not self.model.strip():
            raise LocalLLMProviderError("provider_failed", "LOCAL_LLM_MODEL must be a non-empty string")
        if isinstance(self.timeout_s, bool) or not isinstance(self.timeout_s, (int, float)):
            raise LocalLLMProviderError("provider_failed", "LOCAL_LLM_TIMEOUT must be a number")
        if self.timeout_s <= 0:
            raise LocalLLMProviderError("provider_failed", "LOCAL_LLM_TIMEOUT must be greater than zero")
        if self.num_ctx is not None:
            if isinstance(self.num_ctx, bool) or not isinstance(self.num_ctx, int) or self.num_ctx <= 0:
                raise LocalLLMProviderError("provider_failed", "LOCAL_LLM_NUM_CTX must be a positive integer")
            if not (NUM_CTX_MIN <= self.num_ctx <= NUM_CTX_MAX):
                raise LocalLLMProviderError(
                    "provider_failed", f"LOCAL_LLM_NUM_CTX must be within [{NUM_CTX_MIN}, {NUM_CTX_MAX}]"
                )

    @classmethod
    def from_env(cls, env: Optional[dict] = None) -> "LocalLLMConfig":
        env = env if env is not None else os.environ
        raw_timeout = env.get("LOCAL_LLM_TIMEOUT")
        try:
            timeout_s = float(raw_timeout) if raw_timeout not in (None, "") else DEFAULT_LOCAL_TIMEOUT_S
        except (TypeError, ValueError):
            raise LocalLLMProviderError("provider_failed", f"LOCAL_LLM_TIMEOUT is not a number: {raw_timeout!r}")
        raw_ctx = env.get("LOCAL_LLM_NUM_CTX")
        num_ctx: Optional[int] = None
        if raw_ctx not in (None, ""):
            try:
                num_ctx = int(raw_ctx)
            except (TypeError, ValueError):
                raise LocalLLMProviderError("provider_failed", f"LOCAL_LLM_NUM_CTX is not an integer: {raw_ctx!r}")
        return cls(
            base_url=(env.get("LOCAL_LLM_BASE_URL") or DEFAULT_LOCAL_BASE_URL).strip(),
            model=(env.get("LOCAL_LLM_MODEL") or DEFAULT_LOCAL_MODEL).strip(),
            timeout_s=timeout_s,
            num_ctx=num_ctx,
        )


# Injectable transport: (url, payload, timeout_s) -> parsed JSON dict.
HttpPost = Callable[[str, dict, float], Any]


def _default_http_post(url: str, payload: dict, timeout_s: float) -> Any:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:  # noqa: S310 -- loopback only
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:200]
        raise LocalLLMProviderError("provider_failed", f"local LLM HTTP {exc.code}: {detail}") from None
    except urllib.error.URLError as exc:
        raise LocalLLMProviderError("provider_unavailable", f"local LLM unreachable: {exc.reason}") from None
    except TimeoutError:
        raise LocalLLMProviderError("provider_unavailable", "local LLM timed out") from None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LocalLLMProviderError("provider_failed", f"local LLM returned invalid JSON: {exc}") from None
    if not isinstance(data, dict):
        raise LocalLLMProviderError("provider_failed", "local LLM response must be a JSON object")
    return data


def _extract_content(data: dict) -> str:
    message = data.get("message")
    content: Any = None
    if isinstance(message, dict):
        content = message.get("content")
    if content is None and isinstance(data.get("response"), str):
        content = data["response"]
    if not isinstance(content, str):
        raise LocalLLMProviderError("provider_failed", "local LLM returned no message content")
    if not content.strip():
        raise LocalLLMProviderError("provider_failed", "local LLM returned blank message content")
    return content


def build_local_llm_provider_factory(
    config: LocalLLMConfig,
    *,
    http_post: Optional[HttpPost] = None,
):
    """Return a ``ProviderFactory`` bound to ``config``.

    The returned ``factory(recorder)`` yields a one-shot ``callable(messages) ->
    str``. ``messages`` is passed through verbatim (already assembled upstream).
    """
    if not isinstance(config, LocalLLMConfig):
        raise TypeError("config must be a LocalLLMConfig")
    assert_loopback_url(config.base_url)
    post = http_post or _default_http_post
    url = config.base_url.rstrip("/") + "/api/chat"

    def factory(recorder: Optional[Callable[[dict], None]] = None):
        def provider(messages: list) -> str:
            if not isinstance(messages, list) or not messages:
                raise LocalLLMProviderError("provider_failed", "provider request must be a non-empty message list")
            payload = {"model": config.model, "messages": messages, "stream": False}
            if config.num_ctx is not None:
                # unset -> request shape unchanged; set -> Ollama options.num_ctx
                payload["options"] = {"num_ctx": config.num_ctx}
            if recorder is not None:
                recorder({"event": "request", "payload": {"model": config.model, "messages": messages}, "body": payload})
            data = post(url, payload, config.timeout_s)
            content = _extract_content(data)
            if recorder is not None:
                recorder({"event": "response", "data": data})
            return content

        return provider

    return factory


def resolve_companion_provider_factory(
    env: Optional[dict] = None,
    *,
    fake_factory,
    http_post: Optional[HttpPost] = None,
):
    """Select the Companion provider factory from ``COMPANION_PROVIDER``.

    ``fake`` (default) -> the supplied deterministic ``fake_factory``.
    ``local``          -> :func:`build_local_llm_provider_factory` from env.

    There is NO cloud mode here and NO automatic fallback: an unknown value is
    a hard error, and ``local`` never silently degrades to ``fake`` or a remote
    provider.
    """
    env = env if env is not None else os.environ
    mode = (env.get("COMPANION_PROVIDER") or PROVIDER_FAKE).strip().lower()
    if mode == PROVIDER_FAKE:
        return fake_factory
    if mode == PROVIDER_LOCAL:
        return build_local_llm_provider_factory(LocalLLMConfig.from_env(env), http_post=http_post)
    raise LocalLLMProviderError(
        "provider_failed",
        f"COMPANION_PROVIDER must be {PROVIDER_FAKE!r} or {PROVIDER_LOCAL!r}, got {mode!r}",
    )
