#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Anthropic-native (Claude Messages API) provider factory for Character Companion.

Covers the ``anthropic_native`` transport: ``POST <base_url>/v1/messages`` ->
``content[0].text``. The API key is sent ONLY as an ``Authorization: Bearer``
header value and is NEVER put into the recorder payload, an error message, or a
log line. Fail-closed on every non-happy path. No retry, no fallback, exactly
one HTTP attempt per provider invocation.

Canonical application input is a ``messages`` list of ``{role, content}`` with
roles ``system`` / ``user`` / ``assistant`` (assembled upstream by the Grounded
runtime policy -- it may carry MULTIPLE ``system`` blocks: core instruction,
grounding, state/memory/consolidated/epistemic/scene). The Anthropic Messages
API does NOT accept ``system`` inside ``messages[]``, so this adapter translates
it:

  * every ``system`` message -> the top-level ``system`` string, joined in order
    with a blank line to preserve the block boundaries the runtime intended by
    emitting them as separate messages; omitted when there are no system
    messages;
  * every ``user`` / ``assistant`` message -> ``messages`` in preserved order;
  * any other role -> fail closed (bounded ``provider_failed``).

Request is minimal (``model``, ``max_tokens``, ``system`` when present,
``messages``) -- no tools / thinking / streaming / vision / temperature /
top_p, none of which the V1 dialogue contract requires.

``max_tokens`` is required by Anthropic. There is no established project-wide
dialogue output-token limit, so this adapter defines :data:`DEFAULT_MAX_TOKENS`
(1024) as its local V1 default.

Response normalization returns the plain text exactly (``str``). If the response
carries a non-text content block (tool_use / image / thinking / ...) the result
would be semantically ambiguous and the adapter fails closed rather than
fabricating text.

The provider is UNTRUSTED: its raw response body, HTTP error body, and echo
fields are NEVER persisted, logged, or reported. The recorder receives only
allowlist-only metadata (the resolved ``model`` id when it exactly matches the
trusted configured model) -- never the full provider response.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Optional

__all__ = [
    "ANTHROPIC_VERSION",
    "DEFAULT_MAX_TOKENS",
    "AnthropicProviderError",
    "AnthropicProviderConfig",
    "build_anthropic_provider_factory",
]

_DEFAULT_TIMEOUT_S = 60.0
#: Official Anthropic Messages API version header value.
ANTHROPIC_VERSION = "2023-06-01"
#: Local V1 adapter default for the required ``max_tokens`` field. There is no
#: established project-wide dialogue output-token limit to reuse, so this is the
#: Anthropic-adapter default (and is NOT a new settings schema).
DEFAULT_MAX_TOKENS = 1024
#: Separator used to join multiple canonical ``system`` blocks into the single
#: top-level Anthropic ``system`` string. A blank line preserves the block
#: boundaries the runtime intended by emitting separate system messages.
_SYSTEM_JOIN = "\n\n"
#: Upper bound on a provider-returned model id we are willing to retain.
_MODEL_ID_MAX_LEN = 128


class AnthropicProviderError(RuntimeError):
    """Deterministic, secret-free Anthropic-provider error. ``code`` mirrors the
    existing cloud-provider vocabulary: ``missing_credential`` /
    ``provider_unavailable`` / ``provider_failed``."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class AnthropicProviderConfig:
    provider_id: str
    model: str
    base_url: str
    timeout_s: float = _DEFAULT_TIMEOUT_S
    max_tokens: int = DEFAULT_MAX_TOKENS

    def __post_init__(self) -> None:
        for name, val in (
            ("provider_id", self.provider_id),
            ("model", self.model),
            ("base_url", self.base_url),
        ):
            if not isinstance(val, str) or not val.strip():
                raise AnthropicProviderError("provider_failed", f"{name} must be a non-empty string")
        if isinstance(self.timeout_s, bool) or not isinstance(self.timeout_s, (int, float)) or self.timeout_s <= 0:
            raise AnthropicProviderError("provider_failed", "timeout must be a positive number")
        if isinstance(self.max_tokens, bool) or not isinstance(self.max_tokens, int) or self.max_tokens <= 0:
            raise AnthropicProviderError("provider_failed", "max_tokens must be a positive integer")


# Injectable transport: (url, payload, headers, timeout_s) -> parsed JSON dict.
# Matches the cloud_provider seam so provider_resolution can share http_post_cloud.
HttpPost = Callable[[str, dict, dict, float], Any]


def _http_error_message(code: int) -> str:
    """Bounded, secret-free meaning from a trusted HTTP status code only. Never
    reads the untrusted provider error body."""
    if code in (401, 403):
        return "Anthropic authentication failed"
    if code == 429:
        return "Anthropic rate limit or service unavailable"
    if 400 <= code < 500:
        return f"Anthropic request failed with HTTP {code}"
    return "Anthropic service unavailable"


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
        # NEVER read/echo the provider error body: it is untrusted and may reflect
        # the credential. Derive bounded meaning from the HTTP status code only.
        raise AnthropicProviderError("provider_failed", _http_error_message(exc.code)) from None
    except urllib.error.URLError as exc:
        raise AnthropicProviderError("provider_unavailable", f"anthropic provider unreachable: {exc.reason}") from None
    except TimeoutError:
        raise AnthropicProviderError("provider_unavailable", "anthropic provider timed out") from None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise AnthropicProviderError("provider_failed", "anthropic provider returned invalid JSON") from None
    if not isinstance(data, dict):
        raise AnthropicProviderError("provider_failed", "anthropic provider response must be a JSON object")
    return data


def _translate_messages(messages: list):
    """Split canonical messages into ``(system_text | None, anthropic_messages)``.

    Fail-closed on a non-list, an empty list, a non-object message, a non-string
    ``content``, or any role outside ``system``/``user``/``assistant``. Never
    silently drops or rewrites a message.
    """
    if not isinstance(messages, list) or not messages:
        raise AnthropicProviderError("provider_failed", "provider request must be a non-empty message list")
    system_parts = []
    body = []
    for message in messages:
        if not isinstance(message, dict):
            raise AnthropicProviderError("provider_failed", "provider request messages must be objects")
        role = message.get("role")
        content = message.get("content")
        if role == "system":
            if not isinstance(content, str):
                raise AnthropicProviderError("provider_failed", "system message content must be a string")
            system_parts.append(content)
        elif role in ("user", "assistant"):
            if not isinstance(content, str):
                raise AnthropicProviderError("provider_failed", f"{role} message content must be a string")
            body.append({"role": role, "content": content})
        else:
            raise AnthropicProviderError("provider_failed", f"unsupported message role {role!r}")
    if not body:
        raise AnthropicProviderError(
            "provider_failed", "provider request must contain at least one user/assistant message"
        )
    system = _SYSTEM_JOIN.join(system_parts) if system_parts else None
    return system, body


def _extract_text(data: dict) -> str:
    content = data.get("content")
    if not isinstance(content, list) or not content:
        raise AnthropicProviderError("provider_failed", "anthropic provider returned no content")
    texts = []
    for block in content:
        if not isinstance(block, dict):
            raise AnthropicProviderError("provider_failed", "anthropic provider content block must be an object")
        btype = block.get("type")
        if btype == "text":
            text = block.get("text")
            if not isinstance(text, str):
                raise AnthropicProviderError("provider_failed", "anthropic provider text block has no string text")
            texts.append(text)
        else:
            raise AnthropicProviderError("provider_failed", "anthropic provider returned unsupported content block type")
    if not texts:
        raise AnthropicProviderError("provider_failed", "anthropic provider returned no text content")
    result = "\n".join(texts)
    if not result.strip():
        raise AnthropicProviderError("provider_failed", "anthropic provider returned blank text content")
    return result


def _safe_response_metadata(data: dict, configured_model: str, credential: str) -> dict:
    """Allowlist-only recorder metadata (never persists untrusted provider data).

    Retains ONLY the resolved ``model`` id when it is a bounded string that
    exactly matches the trusted configured model and does not carry the
    credential. Content blocks, echo fields, arbitrary keys, and
    credential-bearing data are never persisted.
    """
    model = data.get("model")
    if not isinstance(model, str):
        return {}
    model = model.strip()
    if not model or len(model) > _MODEL_ID_MAX_LEN:
        return {}
    if credential and credential in model:
        return {}
    if model != configured_model:
        return {}
    return {"model": model}


def build_anthropic_provider_factory(
    config: AnthropicProviderConfig,
    *,
    api_key: str,
    http_post: Optional[HttpPost] = None,
):
    """Return a ``ProviderFactory`` bound to ``config`` + ``api_key``.

    The key is captured in the closure and used ONLY as an ``Authorization:
    Bearer`` header value. It is never recorded, logged, or surfaced in an error.
    """
    if not isinstance(config, AnthropicProviderConfig):
        raise TypeError("config must be an AnthropicProviderConfig")
    if not isinstance(api_key, str) or not api_key.strip():
        raise AnthropicProviderError("missing_credential", f"no credential for provider {config.provider_id!r}")
    key = api_key.strip()
    post = http_post or _default_http_post
    url = config.base_url.rstrip("/") + "/v1/messages"

    def factory(recorder: Optional[Callable[[dict], None]] = None):
        def provider(messages: list) -> str:
            system, body_messages = _translate_messages(messages)
            payload = {"model": config.model, "max_tokens": config.max_tokens}
            if system is not None:
                payload["system"] = system
            payload["messages"] = body_messages
            if recorder is not None:
                # NOTE: no headers, no api_key -- request payload only
                recorder({
                    "event": "request",
                    "payload": {"model": config.model, "max_tokens": config.max_tokens,
                                "system": system, "messages": body_messages},
                })
            headers = {"Authorization": f"Bearer {key}", "anthropic-version": ANTHROPIC_VERSION}
            data = post(url, payload, headers, config.timeout_s)
            if not isinstance(data, dict):
                raise AnthropicProviderError(
                    "provider_failed", "anthropic provider response must be a JSON object"
                )
            content = _extract_text(data)
            if recorder is not None:
                # allowlist-only metadata; never the full provider response
                recorder({"event": "response", "data": _safe_response_metadata(data, config.model, key)})
            return content

        return provider

    return factory
