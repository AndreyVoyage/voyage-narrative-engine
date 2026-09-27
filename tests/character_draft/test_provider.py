"""Provider boundary: configuration and fail-closed credential handling."""

from __future__ import annotations

import pytest

from services.character_draft import (
    CharacterDraftError,
    DraftProviderConfig,
    make_llm_provider,
)


def test_missing_credential_is_user_readable(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    provider = make_llm_provider(
        DraftProviderConfig(provider="cloud", api_key_env="DEEPSEEK_API_KEY")
    )
    with pytest.raises(CharacterDraftError) as caught:
        provider([{"role": "user", "content": "hi"}], None)
    assert "DEEPSEEK_API_KEY" in str(caught.value)


def test_config_from_env(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-chat")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    config = DraftProviderConfig.from_env()
    assert config.model == "deepseek-chat"
    assert config.base_url == "https://api.deepseek.com"
    assert config.api_key_env == "DEEPSEEK_API_KEY"


def test_config_falls_back_to_openai_key(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    config = DraftProviderConfig.from_env()
    assert config.api_key_env == "OPENAI_API_KEY"
