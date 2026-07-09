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
import sys
import urllib.error
import urllib.request
from typing import Any


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
    payload: dict[str, Any] = {
        "model": model or DEFAULT_LOCAL_MODEL,
        "messages": messages,
        "stream": False,
    }
    for key, value in options.items():
        if key != "base_url":
            payload[key] = value

    data = _post_json(f"{base_url}/api/chat", payload, headers={})
    message = data.get("message")
    if isinstance(message, dict) and isinstance(message.get("content"), str):
        return message["content"]
    if isinstance(data.get("response"), str):
        return data["response"]
    raise LLMProviderError("local provider returned no message content")


def _complete_cloud(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    params: dict[str, Any] | None = None,
) -> str:
    options = params or {}
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise LLMProviderError("OPENAI_API_KEY is required for cloud provider")

    base_url = str(options.get("base_url") or os.environ.get("OPENAI_BASE_URL") or DEFAULT_CLOUD_BASE_URL).rstrip("/")
    payload: dict[str, Any] = {
        "model": model or DEFAULT_CLOUD_MODEL,
        "messages": messages,
    }
    for key, value in options.items():
        if key != "base_url":
            payload[key] = value

    headers = {"Authorization": f"Bearer {api_key}"}
    data = _post_json(f"{base_url}/v1/chat/completions", payload, headers=headers)
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            return message["content"]
    raise LLMProviderError("cloud provider returned no message content")


def _post_json(url: str, payload: dict[str, Any], *, headers: dict[str, str]) -> dict[str, Any]:
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
        with urllib.request.urlopen(request, timeout=30) as response:
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
