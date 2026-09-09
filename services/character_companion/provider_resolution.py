#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Resolve the DIALOGUE-role provider factory from settings + vault + registry.

There is exactly ONE factory per turn, chosen deterministically here. If it is a
cloud provider and its credential is missing, or if the provider call later
fails, the error propagates -- this module NEVER builds a second factory for a
different provider. Silent cloud/fake fallback is impossible by construction;
enabling any fallback is a future explicit policy.
"""

from __future__ import annotations

from typing import Callable, Optional

from .cloud_provider import (
    CloudProviderConfig,
    CloudProviderError,
    build_openai_compat_provider_factory,
)
from .credentials import CredentialError
from .local_provider import LocalLLMConfig, build_local_llm_provider_factory
from .provider_registry import (
    ROLE_DIALOGUE,
    TRANSPORT_FAKE,
    TRANSPORT_OLLAMA_NATIVE,
    TRANSPORT_OPENAI_COMPAT,
    ProviderRegistryError,
    get_provider,
    require_role_supported,
)
from .settings import CompanionSettings

__all__ = [
    "CompanionConfigError",
    "resolve_dialogue_provider_factory",
    "test_provider_connection",
]

_PROBE_MESSAGES = [{"role": "user", "content": "ping"}]


class CompanionConfigError(RuntimeError):
    """A configuration problem that must surface as a bounded error (never a
    silent switch to another provider)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _base_url_for(settings: CompanionSettings, provider_id: str) -> str:
    return settings.base_urls.get(provider_id) or get_provider(provider_id).default_base_url


def _factory_for(
    settings: CompanionSettings,
    vault,
    provider_id: str,
    model_id: str,
    *,
    role: str = ROLE_DIALOGUE,
    fake_factory,
    http_post_local: Optional[Callable] = None,
    http_post_cloud: Optional[Callable] = None,
):
    try:
        entry = require_role_supported(provider_id, role)
    except ProviderRegistryError as exc:
        raise CompanionConfigError(exc.code, exc.message) from exc

    base_url = _base_url_for(settings, entry.provider_id)
    model = (model_id or entry.default_model).strip()

    if entry.transport == TRANSPORT_FAKE:
        return fake_factory
    if entry.transport == TRANSPORT_OLLAMA_NATIVE:
        cfg = LocalLLMConfig(base_url=base_url, model=model, num_ctx=settings.local_num_ctx)
        return build_local_llm_provider_factory(cfg, http_post=http_post_local)
    if entry.transport == TRANSPORT_OPENAI_COMPAT:
        try:
            if not vault.has(entry.provider_id):
                raise CompanionConfigError(
                    "missing_credential",
                    f"Не задан ключ API для провайдера «{entry.display_name}».",
                )
            api_key = vault.resolve(entry.provider_id)
        except CredentialError as exc:
            raise CompanionConfigError(exc.code, exc.message) from exc
        cfg = CloudProviderConfig(provider_id=entry.provider_id, model=model, base_url=base_url)
        return build_openai_compat_provider_factory(cfg, api_key=api_key, http_post=http_post_cloud)

    raise CompanionConfigError("unknown_transport", f"unknown transport {entry.transport!r}")


def resolve_dialogue_provider_factory(
    settings: CompanionSettings,
    vault,
    *,
    fake_factory,
    http_post_local: Optional[Callable] = None,
    http_post_cloud: Optional[Callable] = None,
):
    """The single provider factory used by ``CompanionService.send_message``."""
    a = settings.dialogue()
    return _factory_for(
        settings, vault, a.provider_id, a.model_id,
        fake_factory=fake_factory, http_post_local=http_post_local, http_post_cloud=http_post_cloud,
    )


def test_provider_connection(
    provider_id: str,
    model_id: str,
    settings: CompanionSettings,
    vault,
    *,
    fake_factory,
    http_post_local: Optional[Callable] = None,
    http_post_cloud: Optional[Callable] = None,
) -> dict:
    """Send a tiny probe through the selected provider adapter. Never deletes a
    credential on failure; never logs headers/secrets."""
    try:
        factory = _factory_for(
            settings, vault, provider_id, model_id,
            fake_factory=fake_factory, http_post_local=http_post_local, http_post_cloud=http_post_cloud,
        )
        text = factory(None)(_PROBE_MESSAGES)
        return {"ok": bool(isinstance(text, str) and text.strip()), "status": "ok"}
    except CompanionConfigError as exc:
        return {"ok": False, "status": exc.code, "message": exc.message}
    except (CloudProviderError,) as exc:
        return {"ok": False, "status": exc.code, "message": exc.message}
    except Exception as exc:  # noqa: BLE001 -- bounded; never leak internals/secrets
        code = getattr(exc, "code", "provider_failed")
        return {"ok": False, "status": str(code), "message": "проверка соединения не удалась"}
