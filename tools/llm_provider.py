#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Minimal LLM provider abstraction for N6 Character Aside.

Providers:
- mock: deterministic, offline, no network calls. Intended for tests and the
  first playable Aside slice.
- local: Ollama-compatible local chat endpoint.
- cloud: OpenAI-compatible chat completions endpoint. Cloud providers can have
  content policies; for adult content, local providers are preferred.

This module intentionally uses stdlib only and does not read .env files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import ssl
import sys
import urllib.error
import urllib.request
from typing import Any

try:
    import certifi
except ImportError:
    certifi = None


DEFAULT_LOCAL_BASE_URL = "http://localhost:11434"
DEFAULT_LOCAL_MODEL = "llama3"
DEFAULT_CLOUD_BASE_URL = "https://api.openai.com"
DEFAULT_CLOUD_MODEL = "gpt-4o-mini"


class LLMProviderError(RuntimeError):
    """Clean, user-facing provider error."""


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


def complete(
    messages: list[dict[str, str]],
    *,
    provider: str,
    model: str | None = None,
    system: str | None = None,
    params: dict[str, Any] | None = None,
) -> str:
    """Return a completion string from mock, local, or cloud provider."""
    normalized = _normalize_messages(messages, system=system)
    selected = provider.strip().lower()
    options = params or {}

    if selected == "mock":
        return _complete_mock(normalized, model=model, params=options)
    if selected == "local":
        return _complete_local(normalized, model=model, params=options)
    if selected == "cloud":
        return _complete_cloud(normalized, model=model, params=options)

    raise LLMProviderError(f"Unknown provider: {provider}")


def _normalize_messages(
    messages: list[dict[str, str]],
    *,
    system: str | None = None,
) -> list[dict[str, str]]:
    if not isinstance(messages, list):
        raise LLMProviderError("messages must be a list")

    result: list[dict[str, str]] = []
    if system:
        result.append({"role": "system", "content": system})

    for message in messages:
        if not isinstance(message, dict):
            raise LLMProviderError("each message must be an object")
        role = str(message.get("role", "")).strip()
        content = message.get("content")
        if role not in {"system", "user", "assistant"}:
            raise LLMProviderError(f"invalid message role: {role}")
        if not isinstance(content, str):
            raise LLMProviderError("message content must be a string")
        result.append({"role": role, "content": content})

    if not result:
        raise LLMProviderError("at least one message is required")
    return result


def _complete_mock(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    params: dict[str, Any] | None = None,
) -> str:
    del params
    last_user = _last_message(messages, "user") or messages[-1]
    text = " ".join(last_user["content"].split())
    snippet = _truncate(text, 160)
    digest = hashlib.sha256(_canonical_payload(messages, model=model).encode("utf-8")).hexdigest()[:10]
    return f"[MOCK] ({last_user['role']}) {snippet} :: {digest}"


def _complete_local(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    params: dict[str, Any] | None = None,
) -> str:
    options = params or {}
    base_url = str(options.get("base_url") or DEFAULT_LOCAL_BASE_URL).rstrip("/")
    timeout_s = options.get("timeout_s", 30.0)
    payload: dict[str, Any] = {
        "model": model or DEFAULT_LOCAL_MODEL,
        "messages": messages,
        "stream": False,
    }
    for key, value in options.items():
        if key not in ("base_url", "timeout_s"):
            payload[key] = value

    data = _post_json(
        f"{base_url}/api/chat",
        payload,
        headers={},
        timeout_s=timeout_s,
    )
    message = data.get("message")
    if isinstance(message, dict) and isinstance(message.get("content"), str):
        return message["content"]
    if isinstance(data.get("response"), str):
        return data["response"]
    raise LLMProviderError("local provider returned no message content")


# Transport/control fields the cloud transport consumes itself and must never
# be forwarded into the outbound generation JSON payload. ``api_key`` may be an
# already-read credential value; ``credential_env`` may be the NAME of an
# environment variable holding one (read here, once, fail-closed if unusable).
_CLOUD_CONTROL_FIELDS = frozenset({"base_url", "credential_env", "timeout_s", "api_key"})


def _complete_cloud(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    params: dict[str, Any] | None = None,
) -> str:
    options = params or {}

    # Credential resolution -- never hardcodes a provider env-var name. The
    # caller supplies either an already-read ``api_key`` value or the NAME of
    # the environment variable holding the credential.
    api_key = options.get("api_key")
    if not api_key:
        credential_env = options.get("credential_env")
        if not credential_env:
            raise LLMProviderError(
                "cloud provider requires an explicit credential (api_key) or "
                "a configured credential_env variable name"
            )
        api_key = os.environ.get(str(credential_env))
    if not api_key:
        raise LLMProviderError("cloud provider credential is not set or is empty")

    base_url = str(options.get("base_url") or os.environ.get("OPENAI_BASE_URL") or DEFAULT_CLOUD_BASE_URL).rstrip("/")
    timeout_s = options.get("timeout_s", 30.0)

    payload: dict[str, Any] = {
        "model": model or DEFAULT_CLOUD_MODEL,
        "messages": messages,
    }
    for key, value in options.items():
        if key not in _CLOUD_CONTROL_FIELDS:
            payload[key] = value

    headers = {"Authorization": f"Bearer {api_key}"}
    data = _post_json(f"{base_url}/v1/chat/completions", payload, headers=headers, timeout_s=timeout_s)
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        choice = choices[0] if isinstance(choices[0], dict) else None
        if isinstance(choice, dict):
            finish_reason = choice.get("finish_reason")
            if finish_reason != "stop":
                # Fail closed: only an explicit "stop" is accepted as a complete,
                # successful non-streaming answer. Missing or non-success values
                # (length, content_filter, tool_calls, etc.) must never be treated
                # as a finished answer. The human-readable message still surfaces
                # only terminal metadata and no credential material.
                #
                # The COMPLETE parsed provider response is preserved on the
                # exception (out-of-band diagnostic attribute only) so an outer
                # boundary can record it before the fail-closed error propagates.
                # ``data`` is never mutated; this truncated response is never
                # returned as success, never repaired, never retried.
                error = LLMProviderError(
                    f"cloud provider did not finish successfully (finish_reason={finish_reason!r})"
                )
                error.provider_diagnostic = data
                raise error
            message = choice.get("message")
            if isinstance(message, dict) and isinstance(message.get("content"), str):
                content = message["content"]
                if not content.strip():
                    # Never propagate an empty/whitespace assistant answer; this
                    # would otherwise flow into the R8 parser and be reported as a
                    # parse-stage empty output rather than a transport failure.
                    raise LLMProviderError("cloud provider returned empty message content")
                return content
    raise LLMProviderError("cloud provider returned no message content")


def _post_json(
    url: str,
    payload: dict[str, Any],
    *,
    headers: dict[str, str],
    timeout_s: float = 30.0,
) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            **headers,
        },
    )
    try:
        timeout_value = float(timeout_s)
    except (TypeError, ValueError):
        raise LLMProviderError(
            f"Invalid HTTP timeout value: {timeout_s!r}"
        )

    if timeout_value <= 0:
        raise LLMProviderError(
            f"HTTP timeout must be greater than zero: {timeout_value!r}"
        )

    try:
        _ssl_context = _get_ssl_context()
        with urllib.request.urlopen(
            request,
            timeout=timeout_value,
            context=_ssl_context,
        ) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise LLMProviderError(f"HTTP {exc.code}: {_truncate(detail, 200)}") from None
    except urllib.error.URLError as exc:
        raise LLMProviderError(f"connection failed: {exc.reason}") from None
    except TimeoutError:
        raise LLMProviderError("connection timed out") from None

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LLMProviderError(f"invalid JSON response: {exc}") from None
    if not isinstance(data, dict):
        raise LLMProviderError("provider response must be a JSON object")
    return data


def _get_ssl_context() -> ssl.SSLContext | None:
    """Return a verified SSL context using certifi CA bundle.

    On Ren'Py Windows the embedded Python may not load the Windows trust
    store, resulting in a zero-CA default context.  certifi provides a
    portable Mozilla-curated CA bundle that avoids this problem while
    keeping full certificate verification enabled.

    Returns None when certifi is unavailable so that callers that need
    TLS can fail clearly rather than silently downgrading to an
    insecure context.  (At this point certifi is always bundled with
    Ren'Py, so None is effectively unreachable in production.)
    """
    if certifi is None:
        return None
    return ssl.create_default_context(cafile=certifi.where())


def _last_message(messages: list[dict[str, str]], role: str) -> dict[str, str] | None:
    for message in reversed(messages):
        if message["role"] == role:
            return message
    return None


def _canonical_payload(messages: list[dict[str, str]], *, model: str | None) -> str:
    return json.dumps({"model": model or "mock", "messages": messages}, ensure_ascii=False, sort_keys=True)


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _parse_params(raw_params: list[str], *, base_url: str | None, character: str | None) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if base_url:
        params["base_url"] = base_url
    if character:
        params["character"] = character

    for item in raw_params:
        if "=" not in item:
            raise LLMProviderError(f"invalid param, expected key=value: {item}")
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise LLMProviderError("param key cannot be empty")
        params[key] = _coerce_param_value(value.strip())
    return params


def _coerce_param_value(value: str) -> Any:
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if value.lower() == "null":
        return None
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="N6 LLM provider helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    complete_parser = subparsers.add_parser("complete", help="run a chat completion")
    complete_parser.add_argument("--provider", default="mock", help="provider name: mock, local, or cloud")
    complete_parser.add_argument("--message", required=True, help="user message")
    complete_parser.add_argument("--system", default=None, help="optional system message")
    complete_parser.add_argument("--model", default=None, help="optional model name")
    complete_parser.add_argument("--base-url", default=None, help="provider base URL")
    complete_parser.add_argument("--character", default=None, help="optional character id/name for caller context")
    complete_parser.add_argument("--param", action="append", default=[], help="extra provider parameter as key=value")
    return parser


def main(argv: list[str] | None = None) -> int:
    _configure_stdio()
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "complete":
            params = _parse_params(args.param, base_url=args.base_url, character=args.character)
            response = complete(
                [{"role": "user", "content": args.message}],
                provider=args.provider,
                model=args.model,
                system=args.system,
                params=params,
            )
            print(response)
            return 0
        raise LLMProviderError(f"Unknown command: {args.command}")
    except LLMProviderError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
