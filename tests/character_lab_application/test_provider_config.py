"""Character Lab DeepSeek provider configuration (offline, fail-closed)."""

from __future__ import annotations

import pytest

from services.character_draft import CharacterDraftError
from services.character_lab_application.provider import (
    DEEPSEEK_CONFIG_INVALID_MESSAGE,
    DEEPSEEK_DEFAULT_BASE_URL,
    DEEPSEEK_DEFAULT_MODEL,
    CharacterLabProviderConfigError,
    build_character_lab_provider,
    resolve_character_lab_provider_config,
)


def test_defaults_when_only_key_present():
    config = resolve_character_lab_provider_config({"DEEPSEEK_API_KEY": "k"})
    assert config.api_key_env == "DEEPSEEK_API_KEY"
    assert config.base_url == DEEPSEEK_DEFAULT_BASE_URL
    assert config.model == DEEPSEEK_DEFAULT_MODEL


def test_explicit_deepseek_config_accepted():
    config = resolve_character_lab_provider_config(
        {
            "DEEPSEEK_API_KEY": "k",
            "DEEPSEEK_BASE_URL": "https://api.deepseek.com/v1",
            "DEEPSEEK_MODEL": "deepseek-chat",
        }
    )
    assert config.base_url == "https://api.deepseek.com/v1"
    assert config.model == "deepseek-chat"


def test_openai_only_env_is_never_selected():
    config = resolve_character_lab_provider_config({"OPENAI_API_KEY": "k"})
    assert config.api_key_env == "DEEPSEEK_API_KEY"


def test_both_keys_prefer_deepseek():
    config = resolve_character_lab_provider_config(
        {"DEEPSEEK_API_KEY": "d", "OPENAI_API_KEY": "o"}
    )
    assert config.api_key_env == "DEEPSEEK_API_KEY"


def test_openai_default_endpoint_rejected():
    with pytest.raises(CharacterLabProviderConfigError):
        resolve_character_lab_provider_config(
            {"DEEPSEEK_BASE_URL": "https://api.openai.com"}
        )


def test_malformed_base_url_rejected():
    with pytest.raises(CharacterLabProviderConfigError):
        resolve_character_lab_provider_config({"DEEPSEEK_BASE_URL": "not a url"})


def test_empty_model_uses_default():
    config = resolve_character_lab_provider_config({"DEEPSEEK_MODEL": ""})
    assert config.model == DEEPSEEK_DEFAULT_MODEL


def test_missing_key_fails_closed_before_network(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    provider = build_character_lab_provider({})
    with pytest.raises(CharacterDraftError) as caught:
        provider([{"role": "user", "content": "hi"}], None)
    assert "DEEPSEEK_API_KEY" in str(caught.value)


def test_malformed_config_builds_failing_provider_no_network():
    provider = build_character_lab_provider(
        {"DEEPSEEK_BASE_URL": "https://api.openai.com"}
    )
    with pytest.raises(CharacterDraftError) as caught:
        provider([{"role": "user", "content": "hi"}], None)
    assert str(caught.value) == DEEPSEEK_CONFIG_INVALID_MESSAGE
