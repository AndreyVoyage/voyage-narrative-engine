#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CRP S2C-A -- multi-provider adapter foundation tests (zero network).

Tests ProviderConfig validation, DeepSeek/Qwen config representability,
credential-env configurability (name-only, no secret value stored), reserved
extra-param collision, plain-text extraction via a monkeypatched transport,
transport-control separation, fail-closed credential/malformed-response, and
no retry/fallback. No real HTTP request, no real credential read.
"""

from __future__ import annotations

import os
import sys

import pytest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TOOLS_DIR = os.path.join(_PROJECT_ROOT, "tools")
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

import crp_provider_adapter  # noqa: E402
import llm_provider  # noqa: E402

from crp_provider_adapter import (  # noqa: E402
    ProviderConfig,
    ProviderConfigError,
    build_provider_callable,
)


def _valid_config(**overrides) -> ProviderConfig:
    kwargs = dict(
        provider_id="deepseek",
        model="deepseek-v4-pro",
        base_url="https://api.deepseek.com",
        credential_env="DEEPSEEK_API_KEY",
        timeout_s=60.0,
        max_tokens=1200,
    )
    kwargs.update(overrides)
    return ProviderConfig(**kwargs)


class TestProviderConfigValidation:
    def test_valid_config_accepted(self):
        cfg = _valid_config()
        assert cfg.provider_id == "deepseek"
        assert cfg.timeout_s == 60.0

    @pytest.mark.parametrize("field", ["provider_id", "model", "base_url", "credential_env"])
    def test_empty_required_string_rejected(self, field):
        with pytest.raises(ProviderConfigError):
            _valid_config(**{field: ""})

    def test_non_positive_timeout_rejected(self):
        for bad in (0, -1, 0.0, -5.5):
            with pytest.raises(ProviderConfigError):
                _valid_config(timeout_s=bad)

    def test_non_positive_max_tokens_rejected(self):
        for bad in (0, -1):
            with pytest.raises(ProviderConfigError):
                _valid_config(max_tokens=bad)

    def test_non_numeric_timeout_rejected(self):
        with pytest.raises(ProviderConfigError):
            _valid_config(timeout_s="fast")  # type: ignore[arg-type]

    def test_bool_timeout_rejected(self):
        with pytest.raises(ProviderConfigError):
            _valid_config(timeout_s=True)  # type: ignore[arg-type]


class TestMultiProviderRepresentability:
    def test_deepseek_config_representable(self):
        cfg = _valid_config(
            provider_id="deepseek",
            model="deepseek-v4-pro",
            base_url="https://api.deepseek.com",
            credential_env="DEEPSEEK_API_KEY",
        )
        assert cfg.provider_id == "deepseek"
        assert cfg.model == "deepseek-v4-pro"
        assert cfg.credential_env == "DEEPSEEK_API_KEY"

    def test_qwen_config_representable_different_env_name(self):
        cfg = _valid_config(
            provider_id="qwen",
            model="qwen-test-model",
            base_url="https://dashscope.example.invalid/compatible-mode/v1",
            credential_env="DASHSCOPE_API_KEY",
        )
        assert cfg.provider_id == "qwen"
        assert cfg.model == "qwen-test-model"
        assert cfg.credential_env == "DASHSCOPE_API_KEY"

    def test_no_role_domain_coupling_in_config(self):
        # ProviderConfig is a plain data value; it has no CRP role logic.
        cfg = _valid_config()
        assert not any(hasattr(cfg, a) for a in ("role_id", "task_id", "subject_id"))
        with pytest.raises(TypeError):
            build_provider_callable("not-a-config")  # type: ignore[arg-type]


class TestCredentialBoundary:
    def test_no_secret_value_field_present(self):
        cfg = _valid_config()
        for forbidden_attr in ("api_key", "secret", "token", "credential"):
            assert not hasattr(cfg, forbidden_attr), (
                f"ProviderConfig must not expose {forbidden_attr!r}"
            )

    def test_credential_env_is_name_only(self):
        cfg = _valid_config(credential_env="SOME_VARIABLE_NAME")
        assert cfg.credential_env == "SOME_VARIABLE_NAME"


class TestExtraParamsSafety:
    @pytest.mark.parametrize("key", [
        "base_url", "credential_env", "timeout_s", "api_key", "messages", "model",
    ])
    def test_reserved_key_collision_rejected(self, key):
        with pytest.raises(ProviderConfigError):
            _valid_config(extra_params={key: "hijack"})

    def test_extra_params_frozen_read_only(self):
        cfg = _valid_config(extra_params={"temperature": 0.1})
        with pytest.raises(Exception):
            cfg.extra_params["temperature"] = 0.9  # type: ignore[index]


class TestBuildProviderCallable:
    def test_returns_plain_text(self, monkeypatch):
        calls = {}

        def fake_complete(messages, *, provider, model=None, system=None, params=None):
            calls["provider"] = provider
            calls["model"] = model
            calls["params"] = params
            calls["messages"] = messages
            return "plain assistant text"

        monkeypatch.setattr(crp_provider_adapter, "complete", fake_complete)
        cfg = _valid_config()
        provider_callable = build_provider_callable(cfg)
        result = provider_callable([{"role": "system", "content": "sys"},
                                    {"role": "user", "content": "u"}])

        assert result == "plain assistant text"
        assert calls["provider"] == "cloud"
        assert calls["model"] == "deepseek-v4-pro"
        assert calls["params"]["base_url"] == "https://api.deepseek.com"
        assert calls["params"]["credential_env"] == "DEEPSEEK_API_KEY"
        assert calls["params"]["timeout_s"] == 60.0
        assert calls["params"]["max_tokens"] == 1200
        assert "api_key" not in calls["params"]

    def test_json_mode_adds_response_format(self, monkeypatch):
        captured = {}

        def fake_complete(messages, *, provider, model=None, system=None, params=None):
            captured["params"] = params
            return "{}"

        monkeypatch.setattr(crp_provider_adapter, "complete", fake_complete)
        cfg = _valid_config(json_mode=True)
        build_provider_callable(cfg)([{"role": "user", "content": "hi"}])
        assert captured["params"]["response_format"] == {"type": "json_object"}

    def test_json_mode_false_omits_response_format(self, monkeypatch):
        captured = {}

        def fake_complete(messages, *, provider, model=None, system=None, params=None):
            captured["params"] = params
            return "{}"

        monkeypatch.setattr(crp_provider_adapter, "complete", fake_complete)
        cfg = _valid_config(json_mode=False)
        build_provider_callable(cfg)([{"role": "user", "content": "hi"}])
        assert "response_format" not in captured["params"]

    def test_no_retry_no_fallback(self, monkeypatch):
        n_calls = {"count": 0}

        def fake_complete(messages, *, provider, model=None, system=None, params=None):
            n_calls["count"] += 1
            raise llm_provider.LLMProviderError("boom")

        monkeypatch.setattr(crp_provider_adapter, "complete", fake_complete)
        provider_callable = build_provider_callable(_valid_config())
        with pytest.raises(llm_provider.LLMProviderError):
            provider_callable([{"role": "user", "content": "hi"}])
        assert n_calls["count"] == 1  # no retry


class TestTransportControlSeparation:
    def _capture(self, monkeypatch):
        captured = {}

        def fake_post_json(url, payload, *, headers, timeout_s):
            captured["url"] = url
            captured["payload"] = payload
            captured["timeout_s"] = timeout_s
            captured["headers"] = headers
            return {"choices": [{"message": {"content": "resp-text"}}]}

        monkeypatch.setattr(llm_provider, "_post_json", fake_post_json)
        return captured

    def test_timeout_s_controls_transport_not_json(self, monkeypatch):
        captured = self._capture(monkeypatch)
        out = llm_provider._complete_cloud(
            [{"role": "user", "content": "hi"}],
            model="m",
            params={"api_key": "synthetic-test-value",
                    "base_url": "https://fake.invalid",
                    "timeout_s": 42.0,
                    "credential_env": "SYNTHETIC_TEST_ENV_NAME",
                    "temperature": 0.1},
        )
        assert out == "resp-text"
        assert captured["timeout_s"] == 42.0
        assert "timeout_s" not in captured["payload"]
        assert "credential_env" not in captured["payload"]
        assert "base_url" not in captured["payload"]
        assert "api_key" not in captured["payload"]
        assert captured["payload"]["temperature"] == 0.1

    def test_malformed_response_fails_closed(self, monkeypatch):
        monkeypatch.setattr(llm_provider, "_post_json",
                            lambda *a, **k: {"no": "choices"})
        with pytest.raises(llm_provider.LLMProviderError):
            llm_provider._complete_cloud(
                [{"role": "user", "content": "hi"}],
                model="m",
                params={"api_key": "synthetic-test-value", "base_url": "https://fake.invalid"},
            )

    def test_missing_credential_fails_closed(self, monkeypatch):
        # No api_key and a synthetic credential_env name that is deliberately
        # unset in the real process environment -> fail closed before any HTTP.
        monkeypatch.setattr(
            llm_provider, "_post_json",
            lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not reach transport")),
        )
        with pytest.raises(llm_provider.LLMProviderError):
            llm_provider._complete_cloud(
                [{"role": "user", "content": "hi"}],
                model="m",
                params={"credential_env": "CRP_SYNTHETIC_UNSET_VAR_123456789"},
            )