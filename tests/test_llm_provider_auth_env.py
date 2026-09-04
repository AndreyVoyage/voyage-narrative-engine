#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Focused tests for the cloud provider ``api_key_env`` correction.

Mocked network only (``_post_json`` is patched). No real API key, no network.
Secrets are test-local dummy strings; real environment values are never read
or printed.
"""

from __future__ import annotations

import json
import os
import sys

import pytest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TOOLS_DIR = os.path.join(_PROJECT_ROOT, "tools")
for _p in (_PROJECT_ROOT, _TOOLS_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import llm_provider  # noqa: E402

_CANNED_OK = {"choices": [{"message": {"content": "OK"}}]}


@pytest.fixture
def captured(monkeypatch):
    """Patch _post_json; capture (url, payload, headers); return canned OK."""
    box: dict[str, object] = {}

    def fake_post_json(url, payload, *, headers, timeout_s=30.0):
        box["url"] = url
        box["payload"] = json.loads(json.dumps(payload))  # deep copy
        box["headers"] = dict(headers)
        box["timeout_s"] = timeout_s
        return _CANNED_OK

    monkeypatch.setattr(llm_provider, "_post_json", fake_post_json)
    return box


def _complete(**params):
    return llm_provider.complete(
        [{"role": "user", "content": "hi"}],
        provider="cloud",
        model="m1",
        params=params or None,
    )


def test_default_uses_openai_api_key(captured, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "dummy-openai-A")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    assert _complete() == "OK"
    assert captured["headers"]["Authorization"] == "Bearer dummy-openai-A"


def test_explicit_openai_api_key_matches_default(captured, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "dummy-openai-B")
    assert _complete(api_key_env="OPENAI_API_KEY") == "OK"
    assert captured["headers"]["Authorization"] == "Bearer dummy-openai-B"


def test_explicit_deepseek_api_key(captured, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "dummy-deepseek-C")
    assert _complete(
        api_key_env="DEEPSEEK_API_KEY", base_url="https://api.deepseek.com"
    ) == "OK"
    assert captured["headers"]["Authorization"] == "Bearer dummy-deepseek-C"


def test_unknown_env_name_rejected_before_network(monkeypatch):
    called = {"n": 0}
    monkeypatch.setattr(
        llm_provider,
        "_post_json",
        lambda *a, **k: called.__setitem__("n", called["n"] + 1),
    )
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    with pytest.raises(llm_provider.LLMProviderError):
        _complete(api_key_env="SOME_OTHER_KEY")
    assert called["n"] == 0


def test_selected_env_absent_fails_before_network(monkeypatch):
    called = {"n": 0}
    monkeypatch.setattr(
        llm_provider,
        "_post_json",
        lambda *a, **k: called.__setitem__("n", called["n"] + 1),
    )
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with pytest.raises(llm_provider.LLMProviderError) as excinfo:
        _complete(api_key_env="DEEPSEEK_API_KEY")
    assert called["n"] == 0
    assert "DEEPSEEK_API_KEY" in str(excinfo.value)  # name only, no value exists


def test_api_key_env_absent_from_request_body(captured, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "dummy-deepseek-D")
    _complete(api_key_env="DEEPSEEK_API_KEY", base_url="https://api.deepseek.com")
    payload = captured["payload"]
    assert "api_key_env" not in payload
    assert "base_url" not in payload
    assert "dummy-deepseek-D" not in json.dumps(payload)
    assert "dummy-deepseek-D" not in captured["url"]


def test_secret_never_in_error_representation(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "SECRET-should-not-leak-123")

    def boom(url, payload, *, headers, timeout_s=30.0):
        raise llm_provider.LLMProviderError("HTTP 401: Unauthorized")

    monkeypatch.setattr(llm_provider, "_post_json", boom)
    with pytest.raises(llm_provider.LLMProviderError) as excinfo:
        _complete(api_key_env="DEEPSEEK_API_KEY", base_url="https://api.deepseek.com")
    assert "SECRET-should-not-leak-123" not in str(excinfo.value)
    assert "SECRET-should-not-leak-123" not in repr(excinfo.value)


def test_authorization_header_receives_selected_secret(captured, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "dummy-openai-should-not-be-used")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "dummy-deepseek-selected")
    _complete(api_key_env="DEEPSEEK_API_KEY", base_url="https://api.deepseek.com")
    assert captured["headers"]["Authorization"] == "Bearer dummy-deepseek-selected"


def test_existing_cloud_request_shape_unchanged(captured, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "dummy-openai-E")
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    _complete()
    assert captured["url"] == "https://api.openai.com/v1/chat/completions"
    payload = captured["payload"]
    assert payload["model"] == "m1"
    assert payload["messages"] == [{"role": "user", "content": "hi"}]

    # ...and with an explicit DeepSeek base_url + extra params, only base_url and
    # api_key_env are stripped; other params still pass through to the body.
    monkeypatch.setenv("DEEPSEEK_API_KEY", "dummy-deepseek-F")
    _complete(
        api_key_env="DEEPSEEK_API_KEY",
        base_url="https://api.deepseek.com",
        thinking={"type": "disabled"},
        temperature=0,
    )
    assert captured["url"] == "https://api.deepseek.com/v1/chat/completions"
    payload = captured["payload"]
    assert payload["thinking"] == {"type": "disabled"}
    assert payload["temperature"] == 0
    assert "api_key_env" not in payload and "base_url" not in payload


def test_caller_params_dict_not_mutated(captured, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "dummy-deepseek-G")
    params = {"api_key_env": "DEEPSEEK_API_KEY", "base_url": "https://api.deepseek.com"}
    llm_provider.complete(
        [{"role": "user", "content": "hi"}],
        provider="cloud",
        model="m1",
        params=params,
    )
    assert params == {
        "api_key_env": "DEEPSEEK_API_KEY",
        "base_url": "https://api.deepseek.com",
    }
