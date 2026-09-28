"""Character Lab provider configuration: explicit DeepSeek, fail-closed.

This is the single Character Lab transport-configuration boundary. It resolves
and validates ONE DeepSeek configuration, then builds ONE shared provider
callable used by BOTH the AI-first creation flow and Test Dialogue. Prompts and
state remain separate; only transport/config is shared here.

Character Lab Test App V1 explicitly uses DeepSeek and never falls back to
OpenAI. ``OPENAI_API_KEY`` / ``OPENAI_BASE_URL`` / OpenAI model defaults have no
effect on the resolved Character Lab configuration.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

from services.character_draft import (
    CharacterDraftError,
    DraftProviderConfig,
    ProviderCallable,
    make_llm_provider,
)

DEEPSEEK_API_KEY_ENV = "DEEPSEEK_API_KEY"
DEEPSEEK_DEFAULT_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_DEFAULT_MODEL = "deepseek-chat"

# The OpenAI endpoint is explicitly rejected so a DeepSeek key can never be
# sent to it by accident.
_OPENAI_DEFAULT_BASE_URL = "https://api.openai.com"

# Safe, secret-free guidance surfaced when Character Lab cannot build a usable
# DeepSeek provider (e.g. a malformed non-secret configuration).
DEEPSEEK_CONFIG_INVALID_MESSAGE = (
    "DeepSeek configuration is invalid. Check DEEPSEEK_BASE_URL and DEEPSEEK_MODEL."
)
# Safe guidance when no provider transport has been wired into the service.
DEEPSEEK_NOT_CONFIGURED_MESSAGE = (
    "DeepSeek provider is not configured. Set DEEPSEEK_API_KEY and retry."
)


class CharacterLabProviderConfigError(RuntimeError):
    """The resolved Character Lab DeepSeek configuration is incoherent."""


@dataclass(frozen=True)
class CharacterLabProviderConfig:
    """Resolved, validated Character Lab DeepSeek transport configuration.

    Key presence is intentionally NOT part of this value: the app must still
    open for local authoring/inspection without a live credential. The key is
    checked at operation time, before any HTTP request, by the shared transport.
    """

    api_key_env: str = DEEPSEEK_API_KEY_ENV
    base_url: str = DEEPSEEK_DEFAULT_BASE_URL
    model: str = DEEPSEEK_DEFAULT_MODEL

    def validate(self) -> None:
        base_url = (self.base_url or "").strip()
        model = (self.model or "").strip()
        if not base_url:
            raise CharacterLabProviderConfigError("DeepSeek base URL must be non-empty")
        if not model:
            raise CharacterLabProviderConfigError("DeepSeek model must be non-empty")
        if base_url.rstrip("/") == _OPENAI_DEFAULT_BASE_URL.rstrip("/"):
            raise CharacterLabProviderConfigError(
                "DeepSeek base URL must not be the OpenAI endpoint"
            )
        scheme, _, remainder = base_url.partition("://")
        if scheme.lower() not in ("http", "https") or not remainder.split("/", 1)[0]:
            raise CharacterLabProviderConfigError("DeepSeek base URL is malformed")


def resolve_character_lab_provider_config(
    env: Mapping[str, str] | None = None,
) -> CharacterLabProviderConfig:
    """Resolve and validate the Character Lab DeepSeek configuration.

    Explicit ``DEEPSEEK_BASE_URL`` / ``DEEPSEEK_MODEL`` override the trusted
    defaults; empty values fall back to those defaults. Validation is performed
    before any network call. Key presence is deferred to operation time.
    """
    environment = os.environ if env is None else env
    base_url = (
        (environment.get("DEEPSEEK_BASE_URL") or "").strip()
        or DEEPSEEK_DEFAULT_BASE_URL
    )
    model = (environment.get("DEEPSEEK_MODEL") or "").strip() or DEEPSEEK_DEFAULT_MODEL
    config = CharacterLabProviderConfig(
        api_key_env=DEEPSEEK_API_KEY_ENV,
        base_url=base_url,
        model=model,
    )
    config.validate()
    return config


def build_character_lab_provider(
    env: Mapping[str, str] | None = None,
) -> ProviderCallable:
    """Build the shared Character Lab DeepSeek provider transport.

    Returns a provider callable. On a malformed non-secret configuration the
    returned callable fails with a safe, secret-free error at call time (never
    a network call, never an OpenAI fallback).
    """
    try:
        config = resolve_character_lab_provider_config(env)
    except CharacterLabProviderConfigError:
        return _failing_provider()

    return make_llm_provider(
        DraftProviderConfig(
            provider="cloud",
            model=config.model,
            base_url=config.base_url,
            api_key_env=config.api_key_env,
        )
    )


def _failing_provider() -> ProviderCallable:
    def _call(messages: list[dict[str, str]], system: str | None) -> str:
        raise CharacterDraftError(DEEPSEEK_CONFIG_INVALID_MESSAGE)

    return _call


# -- AI-Create provider failure sanitization ---------------------------------

# Canonical, secret-free user-facing AI-Create provider failure messages. The
# user-visible text ALWAYS originates from these trusted constants, never from a
# provider exception. Arbitrary provider exception text (HTTP bodies, headers,
# URLs, request/response bodies, tracebacks) is discarded at this boundary.
AI_CREATE_GENERIC_FAILURE_MESSAGE = "Не удалось получить ответ от AI-провайдера."
AI_CREATE_SAFE_MISSING_KEY_MESSAGE = "API key is not configured. Set DEEPSEEK_API_KEY and retry."

# The EXACT, full-string messages the shared provider layer emits for the known
# missing-credential condition (plus the local invalid-config guidance, which is
# already a safe constant). Only an exact full-string match (never a
# prefix/substring/regex) identifies a case; every other message -- including
# any prefix-spoofed variant -- collapses to the generic failure message.
_AI_CREATE_SAFE_MESSAGES = {
    "API key is not configured. Set DEEPSEEK_API_KEY and retry.": AI_CREATE_SAFE_MISSING_KEY_MESSAGE,
    DEEPSEEK_CONFIG_INVALID_MESSAGE: DEEPSEEK_CONFIG_INVALID_MESSAGE,
}


def safe_ai_create_provider_message(exc: BaseException) -> str:
    """Return a sanitized user-facing message for an AI-Create provider failure.

    Fails closed: only an exact, contract-guaranteed known message (identified
    by exception type + exact full-string match) is returned -- and even then
    the text is a local canonical constant, never ``str(exc)``. No regex, no
    prefix, no substring, no passthrough of the original exception string.
    """
    if isinstance(exc, CharacterDraftError):
        return _AI_CREATE_SAFE_MESSAGES.get(str(exc), AI_CREATE_GENERIC_FAILURE_MESSAGE)
    return AI_CREATE_GENERIC_FAILURE_MESSAGE


__all__ = [
    "AI_CREATE_GENERIC_FAILURE_MESSAGE",
    "AI_CREATE_SAFE_MISSING_KEY_MESSAGE",
    "DEEPSEEK_API_KEY_ENV",
    "DEEPSEEK_CONFIG_INVALID_MESSAGE",
    "DEEPSEEK_DEFAULT_BASE_URL",
    "DEEPSEEK_DEFAULT_MODEL",
    "DEEPSEEK_NOT_CONFIGURED_MESSAGE",
    "CharacterLabProviderConfig",
    "CharacterLabProviderConfigError",
    "build_character_lab_provider",
    "resolve_character_lab_provider_config",
    "safe_ai_create_provider_message",
]
