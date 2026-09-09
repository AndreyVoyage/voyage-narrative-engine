#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OpenAI-compatible cloud provider factory for Character Companion.

Covers the ``openai_compat`` transport family (DeepSeek / OpenAI / Qwen) with a
single adapter: ``POST <base_url>/v1/chat/completions`` ->
``choices[0].message.content``. The API key is passed in the ``Authorization``
header and is NEVER put into the recorder payload, an error message, or a log
line. Fail-closed on every non-happy path. No retry, no fallback.

Automated tests point ``base_url`` at a temporary localhost fake server; no live
cloud call is ever made from tests.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Optional

__all__ = [
    "CloudProviderError",
    "CloudProviderConfig",
    "build_openai_compat_provider_factory",
]

_DEFAULT_TIMEOUT_S = 60.0


class CloudProviderError(RuntimeError):
    """Deterministic, secret-free cloud-provider error. ``code`` is one of
    ``missing_credential`` / ``provider_unavailable`` / ``provider_failed``."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class CloudProviderConfig:
    provider_id: str
    model: str
    base_url: str
    timeout_s: float = _DEFAULT_TIMEOUT_S

    def __post_init__(self) -> None:
        for name, val in (("provider_id", self.provider_id), ("model", self.model), ("base_url", self.base_url)):
            if not isinstance(val, str) or not val.strip():
                raise CloudProviderError("provider_failed", f"{name} must be a non-empty string")
        if isinstance(self.timeout_s, bool) or not isinstance(self.timeout_s, (int, float)) or self.timeout_s <= 0:
            raise CloudProviderError("provider_failed", "timeout must be a positive number")


# Injectable transport: (url, payload, headers, timeout_s) -> parsed JSON dict.
HttpPost = Callable[[str, dict, dict, float], Any]


def _default_http_post(url: str, payload: dict, headers: dict, timeout_s: float) -> Any:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json", **headers},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:  # noqa: S310
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        # the detail body may echo request data; keep it short and never include
        # our own headers in it
        detail = exc.read().decode("utf-8", errors="replace")[:180]
        raise CloudProviderError("provider_failed", f"cloud provider HTTP {exc.code}: {detail}") from None
    except urllib.error.URLError as exc:
        raise CloudProviderError("provider_unavailable", f"cloud provider unreachable: {exc.reason}") from None
    except TimeoutError:
        raise CloudProviderError("provider_unavailable", "cloud provider timed out") from None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CloudProviderError("provider_failed", f"cloud provider returned invalid JSON: {exc}") from None
    if not isinstance(data, dict):
        raise CloudProviderError("provider_failed", "cloud provider response must be a JSON object")
    return data


def _extract_content(data: dict) -> str:
    choices = data.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        message = choices[0].get("message")
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                return content
            if isinstance(content, str):
                raise CloudProviderError("provider_failed", "cloud provider returned blank message content")
    raise CloudProviderError("provider_failed", "cloud provider returned no message content")


def build_openai_compat_provider_factory(
    config: CloudProviderConfig,
    *,
    api_key: str,
    http_post: Optional[HttpPost] = None,
):
    """Return a ``ProviderFactory`` bound to ``config`` + ``api_key``.

    The key is captured in the closure and used ONLY as an ``Authorization``
    header value. It is never recorded, logged, or surfaced in an error.
    """
    if not isinstance(config, CloudProviderConfig):
        raise TypeError("config must be a CloudProviderConfig")
    if not isinstance(api_key, str) or not api_key.strip():
        raise CloudProviderError("missing_credential", f"no credential for provider {config.provider_id!r}")
    key = api_key.strip()
    post = http_post or _default_http_post
    url = config.base_url.rstrip("/") + "/v1/chat/completions"

    def factory(recorder: Optional[Callable[[dict], None]] = None):
        def provider(messages: list) -> str:
            if not isinstance(messages, list) or not messages:
                raise CloudProviderError("provider_failed", "provider request must be a non-empty message list")
            payload = {"model": config.model, "messages": messages}
            if recorder is not None:
                # NOTE: no headers, no api_key -- request payload only
                recorder({"event": "request", "payload": {"model": config.model, "messages": messages}})
            data = post(url, payload, {"Authorization": f"Bearer {key}"}, config.timeout_s)
            content = _extract_content(data)
            if recorder is not None:
                recorder({"event": "response", "data": data})
            return content

        return provider

    return factory
