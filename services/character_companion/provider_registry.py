#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Data-driven Companion provider registry.

Each entry describes a provider FAMILY (deepseek / openai / qwen / local) as
data -- transport shape, whether a credential is required, default base URL,
supported model roles, and a small starter model catalog. The UI and the
dialogue-role resolver read this table; nothing hardcodes "these four forever".

Only the ``DIALOGUE`` role is wired to the runtime in this release; the other
roles are configuration metadata (foundation) and are never presented as
implemented.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

# ---- roles ---------------------------------------------------------------
ROLE_DIALOGUE = "DIALOGUE"
ROLE_VISION = "VISION"
ROLE_IMAGE_GENERATION = "IMAGE_GENERATION"
ROLE_STT = "STT"
ROLE_TTS = "TTS"
ROLE_REALTIME = "REALTIME"
ROLE_LOCAL_ALTERNATIVE = "LOCAL_ALTERNATIVE"

ALL_ROLES: Tuple[str, ...] = (
    ROLE_DIALOGUE, ROLE_VISION, ROLE_IMAGE_GENERATION,
    ROLE_STT, ROLE_TTS, ROLE_REALTIME, ROLE_LOCAL_ALTERNATIVE,
)
#: Roles this release actually routes at runtime.
RUNTIME_WIRED_ROLES: Tuple[str, ...] = (ROLE_DIALOGUE,)

# ---- transports -------------------------------------------------------
TRANSPORT_OPENAI_COMPAT = "openai_compat"   # POST <base>/v1/chat/completions
TRANSPORT_OLLAMA_NATIVE = "ollama_native"   # POST <base>/api/chat
TRANSPORT_FAKE = "fake"

KIND_CLOUD = "cloud"
KIND_LOCAL = "local"


class ProviderRegistryError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ProviderEntry:
    provider_id: str
    display_name: str
    kind: str
    transport: str
    credential_required: bool
    default_base_url: str
    supported_roles: Tuple[str, ...]
    model_catalog: Tuple[str, ...]
    default_model: str
    notes: str = ""

    def to_json(self, *, connected: bool = False, configured_model: Optional[str] = None,
                masked_tail: Optional[str] = None, last_test_status: Optional[str] = None) -> dict:
        return {
            "providerId": self.provider_id,
            "displayName": self.display_name,
            "kind": self.kind,
            "transport": self.transport,
            "credentialRequired": self.credential_required,
            "defaultBaseUrl": self.default_base_url,
            "supportedRoles": list(self.supported_roles),
            "runtimeWiredRoles": [r for r in self.supported_roles if r in RUNTIME_WIRED_ROLES],
            "modelCatalog": list(self.model_catalog),
            "defaultModel": self.default_model,
            "notes": self.notes,
            "connected": connected,
            "configuredModel": configured_model or self.default_model,
            "maskedTail": masked_tail,
            "lastTestStatus": last_test_status,
        }


_ENTRIES: Tuple[ProviderEntry, ...] = (
    ProviderEntry(
        provider_id="deepseek",
        display_name="DeepSeek",
        kind=KIND_CLOUD,
        transport=TRANSPORT_OPENAI_COMPAT,
        credential_required=True,
        default_base_url="https://api.deepseek.com",
        supported_roles=(ROLE_DIALOGUE,),
        model_catalog=("deepseek-chat", "deepseek-reasoner"),
        default_model="deepseek-chat",
        notes="Сильная работа с характером и диалогом.",
    ),
    ProviderEntry(
        provider_id="openai",
        display_name="OpenAI",
        kind=KIND_CLOUD,
        transport=TRANSPORT_OPENAI_COMPAT,
        credential_required=True,
        default_base_url="https://api.openai.com",
        supported_roles=(ROLE_DIALOGUE, ROLE_VISION, ROLE_IMAGE_GENERATION, ROLE_STT, ROLE_TTS, ROLE_REALTIME),
        model_catalog=("gpt-4o-mini", "gpt-4o"),
        default_model="gpt-4o-mini",
        notes="Широкий мультимодальный набор возможностей (метаданные; в этом релизе используется только диалог).",
    ),
    ProviderEntry(
        provider_id="qwen",
        display_name="Qwen",
        kind=KIND_CLOUD,
        transport=TRANSPORT_OPENAI_COMPAT,
        credential_required=True,
        default_base_url="https://dashscope.aliyuncs.com/compatible-mode",
        supported_roles=(ROLE_DIALOGUE, ROLE_VISION),
        model_catalog=("qwen-plus", "qwen-max"),
        default_model="qwen-plus",
        notes="Совместимый OpenAI-протокол; альтернативное облачное семейство.",
    ),
    ProviderEntry(
        provider_id="local",
        display_name="Local (Ollama)",
        kind=KIND_LOCAL,
        transport=TRANSPORT_OLLAMA_NATIVE,
        credential_required=False,
        default_base_url="http://127.0.0.1:11434",
        supported_roles=(ROLE_DIALOGUE, ROLE_LOCAL_ALTERNATIVE),
        model_catalog=("llama3", "llama3.1", "qwen2.5"),
        default_model="llama3",
        notes="Приватность / без оплаты за токены; нужен подходящий локальный сервер и модель.",
    ),
    ProviderEntry(
        provider_id="fake",
        display_name="Fake (dev)",
        kind=KIND_LOCAL,
        transport=TRANSPORT_FAKE,
        credential_required=False,
        default_base_url="",
        supported_roles=(ROLE_DIALOGUE,),
        model_catalog=("fake",),
        default_model="fake",
        notes="Детерминированная заглушка для разработки и тестов. Никогда не автоматический fallback.",
    ),
)

_BY_ID: Dict[str, ProviderEntry] = {e.provider_id: e for e in _ENTRIES}


def all_providers(*, include_fake: bool = True) -> Tuple[ProviderEntry, ...]:
    return tuple(e for e in _ENTRIES if include_fake or e.provider_id != "fake")


def get_provider(provider_id: str) -> ProviderEntry:
    entry = _BY_ID.get((provider_id or "").strip().lower())
    if entry is None:
        raise ProviderRegistryError("unknown_provider", f"unknown provider {provider_id!r}")
    return entry


def is_known_provider(provider_id: str) -> bool:
    return (provider_id or "").strip().lower() in _BY_ID


def is_known_role(role: str) -> bool:
    return role in ALL_ROLES


def require_role_supported(provider_id: str, role: str) -> ProviderEntry:
    if not is_known_role(role):
        raise ProviderRegistryError("unknown_role", f"unknown model role {role!r}")
    entry = get_provider(provider_id)
    if role not in entry.supported_roles:
        raise ProviderRegistryError(
            "unsupported_role", f"provider {entry.provider_id!r} does not support role {role!r}"
        )
    return entry
