#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Data-driven Companion provider + model catalog.

Each :class:`ProviderEntry` describes a provider FAMILY as data -- transport
shape, whether a credential is required, default base URL, and a small starter
catalog of :class:`ModelEntry` records. Each model carries *capability* flags
(DIALOGUE / VISION / IMAGE_GENERATION / VIDEO_GENERATION / STT / TTS / REALTIME
/ IMAGE_TO_IMAGE / CHARACTER_REFERENCE / LOCAL / CLOUD) plus optional, strictly
*known-fact* media metadata. The UI and the role resolver read this table;
nothing hardcodes "these four forever" and nothing hardcodes model ids in React.

Only ``DIALOGUE`` is wired to the runtime in this release
(:data:`RUNTIME_WIRED_ROLES`). Every media role is configuration metadata
(foundation) and is never presented as an implemented feature. Capabilities that
are not safely known from repository configuration are marked ``unverified`` /
``UNKNOWN`` rather than guessed, and this module makes **no** provider-policy
claims about adult content.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

# ---- roles ---------------------------------------------------------------
ROLE_DIALOGUE = "DIALOGUE"
ROLE_VISION = "VISION"
ROLE_IMAGE_GENERATION = "IMAGE_GENERATION"
ROLE_VIDEO_GENERATION = "VIDEO_GENERATION"
ROLE_STT = "STT"
ROLE_TTS = "TTS"
ROLE_REALTIME = "REALTIME"
ROLE_LOCAL_ALTERNATIVE = "LOCAL_ALTERNATIVE"

ALL_ROLES: Tuple[str, ...] = (
    ROLE_DIALOGUE, ROLE_VISION, ROLE_IMAGE_GENERATION, ROLE_VIDEO_GENERATION,
    ROLE_STT, ROLE_TTS, ROLE_REALTIME, ROLE_LOCAL_ALTERNATIVE,
)
#: Roles this release actually routes at runtime. Everything else is foundation.
RUNTIME_WIRED_ROLES: Tuple[str, ...] = (ROLE_DIALOGUE,)

#: Canonical presentation order for the "models by task" settings section.
ROLE_DISPLAY_ORDER: Tuple[str, ...] = (
    ROLE_DIALOGUE, ROLE_VISION, ROLE_IMAGE_GENERATION, ROLE_VIDEO_GENERATION,
    ROLE_STT, ROLE_TTS, ROLE_REALTIME, ROLE_LOCAL_ALTERNATIVE,
)

# ---- capabilities -----------------------------------------------------
CAP_DIALOGUE = "DIALOGUE"
CAP_VISION = "VISION"
CAP_IMAGE_GENERATION = "IMAGE_GENERATION"
CAP_VIDEO_GENERATION = "VIDEO_GENERATION"
CAP_STT = "STT"
CAP_TTS = "TTS"
CAP_REALTIME = "REALTIME"
CAP_IMAGE_TO_IMAGE = "IMAGE_TO_IMAGE"
CAP_CHARACTER_REFERENCE = "CHARACTER_REFERENCE"
CAP_LOCAL = "LOCAL"
CAP_CLOUD = "CLOUD"

ALL_CAPABILITIES: Tuple[str, ...] = (
    CAP_DIALOGUE, CAP_VISION, CAP_IMAGE_GENERATION, CAP_VIDEO_GENERATION,
    CAP_STT, CAP_TTS, CAP_REALTIME, CAP_IMAGE_TO_IMAGE, CAP_CHARACTER_REFERENCE,
    CAP_LOCAL, CAP_CLOUD,
)

#: capability -> the model-role it satisfies
_CAP_TO_ROLE: Dict[str, str] = {
    CAP_DIALOGUE: ROLE_DIALOGUE,
    CAP_VISION: ROLE_VISION,
    CAP_IMAGE_GENERATION: ROLE_IMAGE_GENERATION,
    CAP_VIDEO_GENERATION: ROLE_VIDEO_GENERATION,
    CAP_STT: ROLE_STT,
    CAP_TTS: ROLE_TTS,
    CAP_REALTIME: ROLE_REALTIME,
}

# ---- model status ---------------------------------------------------
MODEL_AVAILABLE = "available"        # advertised by the provider today
MODEL_UNVERIFIED = "unverified"      # plausible but not checked against current provider docs
MODEL_DEPRECATED = "deprecated"

# ---- content-policy profile (neutral; never asserts "provider X allows NSFW")
POLICY_STANDARD_ONLY = "STANDARD_ONLY"
POLICY_PROVIDER_POLICY_DEPENDENT = "PROVIDER_POLICY_DEPENDENT"
POLICY_LOCAL_MODEL_POLICY = "LOCAL_MODEL_POLICY"
POLICY_UNKNOWN = "UNKNOWN"

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
class ModelEntry:
    model_id: str
    display_name: str
    capabilities: Tuple[str, ...]
    status: str = MODEL_AVAILABLE
    notes: str = ""
    content_policy_profile: str = POLICY_UNKNOWN
    # Optional media facts -- ``None`` means UNKNOWN (never guessed).
    supports_reference_image: Optional[bool] = None
    supports_image_to_image: Optional[bool] = None
    supports_character_reference: Optional[bool] = None
    supports_video: Optional[bool] = None
    max_duration_seconds: Optional[int] = None

    def roles(self) -> Tuple[str, ...]:
        seen = []
        for cap in self.capabilities:
            role = _CAP_TO_ROLE.get(cap)
            if role and role not in seen:
                seen.append(role)
        return tuple(seen)

    def supports_role(self, role: str) -> bool:
        if role == ROLE_LOCAL_ALTERNATIVE:
            return CAP_DIALOGUE in self.capabilities and CAP_LOCAL in self.capabilities
        return role in self.roles()

    def to_json(self) -> dict:
        return {
            "modelId": self.model_id,
            "displayName": self.display_name,
            "capabilities": list(self.capabilities),
            "roles": list(self.roles()),
            "status": self.status,
            "notes": self.notes,
            "contentPolicyProfile": self.content_policy_profile,
            "supportsReferenceImage": self.supports_reference_image,
            "supportsImageToImage": self.supports_image_to_image,
            "supportsCharacterReference": self.supports_character_reference,
            "supportsVideo": self.supports_video,
            "maxDurationSeconds": self.max_duration_seconds,
        }


@dataclass(frozen=True)
class ProviderEntry:
    provider_id: str
    display_name: str
    kind: str
    transport: str
    credential_required: bool
    default_base_url: str
    models: Tuple[ModelEntry, ...]
    default_model: str
    notes: str = ""
    #: extra roles beyond what the model capabilities already imply
    extra_roles: Tuple[str, ...] = ()

    # -- backward-compatible derivations --------------------------------
    @property
    def model_catalog(self) -> Tuple[str, ...]:
        return tuple(m.model_id for m in self.models)

    @property
    def supported_roles(self) -> Tuple[str, ...]:
        seen = list(self.extra_roles)
        for m in self.models:
            for role in m.roles():
                if role not in seen:
                    seen.append(role)
        # a local provider that can do DIALOGUE can also serve LOCAL_ALTERNATIVE
        if self.kind == KIND_LOCAL and ROLE_DIALOGUE in seen and ROLE_LOCAL_ALTERNATIVE not in seen:
            seen.append(ROLE_LOCAL_ALTERNATIVE)
        return tuple(r for r in ROLE_DISPLAY_ORDER if r in seen)

    @property
    def capabilities(self) -> Tuple[str, ...]:
        seen = [CAP_LOCAL if self.kind == KIND_LOCAL else CAP_CLOUD]
        for m in self.models:
            for cap in m.capabilities:
                if cap not in seen:
                    seen.append(cap)
        return tuple(c for c in ALL_CAPABILITIES if c in seen)

    def get_model(self, model_id: str) -> Optional[ModelEntry]:
        mid = (model_id or "").strip()
        for m in self.models:
            if m.model_id == mid:
                return m
        return None

    def models_for_role(self, role: str) -> Tuple[ModelEntry, ...]:
        return tuple(m for m in self.models if m.supports_role(role))

    def default_model_for_role(self, role: str) -> str:
        for m in self.models:
            if m.supports_role(role):
                return m.model_id
        return self.default_model

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
            "capabilities": list(self.capabilities),
            "modelCatalog": list(self.model_catalog),      # backward-compatible id list
            "models": [m.to_json() for m in self.models],
            "defaultModel": self.default_model,
            "notes": self.notes,
            "connected": connected,
            "configuredModel": configured_model or self.default_model,
            "maskedTail": masked_tail,
            "lastTestStatus": last_test_status,
        }


# ======================================================================
# Repository-backed catalog.
#
# Media capabilities are advertised ONLY where there is a justified model entry.
# Anything uncertain is ``MODEL_UNVERIFIED`` with UNKNOWN media facts, so the UI
# never pretends a configured model already performs a feature.
# ======================================================================
_ENTRIES: Tuple[ProviderEntry, ...] = (
    ProviderEntry(
        provider_id="deepseek",
        display_name="DeepSeek",
        kind=KIND_CLOUD,
        transport=TRANSPORT_OPENAI_COMPAT,
        credential_required=True,
        default_base_url="https://api.deepseek.com",
        models=(
            ModelEntry("deepseek-chat", "DeepSeek Chat", (CAP_DIALOGUE, CAP_CLOUD),
                       content_policy_profile=POLICY_PROVIDER_POLICY_DEPENDENT),
            ModelEntry("deepseek-reasoner", "DeepSeek Reasoner", (CAP_DIALOGUE, CAP_CLOUD),
                       content_policy_profile=POLICY_PROVIDER_POLICY_DEPENDENT),
        ),
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
        models=(
            ModelEntry("gpt-4o-mini", "GPT-4o mini", (CAP_DIALOGUE, CAP_VISION, CAP_CLOUD),
                       content_policy_profile=POLICY_PROVIDER_POLICY_DEPENDENT),
            ModelEntry("gpt-4o", "GPT-4o", (CAP_DIALOGUE, CAP_VISION, CAP_CLOUD),
                       content_policy_profile=POLICY_PROVIDER_POLICY_DEPENDENT),
            ModelEntry("gpt-image-1", "GPT Image 1",
                       (CAP_IMAGE_GENERATION, CAP_IMAGE_TO_IMAGE, CAP_CLOUD),
                       status=MODEL_UNVERIFIED,
                       notes="Возможности изображения — метаданные каталога; не подключено в этой сборке.",
                       content_policy_profile=POLICY_PROVIDER_POLICY_DEPENDENT,
                       supports_image_to_image=True, supports_reference_image=True),
            ModelEntry("sora-2", "Sora 2", (CAP_VIDEO_GENERATION, CAP_CLOUD),
                       status=MODEL_UNVERIFIED,
                       notes="Генерация видео — только основа конфигурации; адаптер не реализован.",
                       content_policy_profile=POLICY_PROVIDER_POLICY_DEPENDENT,
                       supports_video=True),
            ModelEntry("whisper-1", "Whisper", (CAP_STT, CAP_CLOUD),
                       status=MODEL_UNVERIFIED,
                       content_policy_profile=POLICY_PROVIDER_POLICY_DEPENDENT),
            ModelEntry("gpt-4o-mini-tts", "GPT-4o mini TTS", (CAP_TTS, CAP_CLOUD),
                       status=MODEL_UNVERIFIED,
                       content_policy_profile=POLICY_PROVIDER_POLICY_DEPENDENT),
            ModelEntry("gpt-4o-realtime-preview", "GPT-4o Realtime", (CAP_REALTIME, CAP_CLOUD),
                       status=MODEL_UNVERIFIED,
                       content_policy_profile=POLICY_PROVIDER_POLICY_DEPENDENT),
        ),
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
        models=(
            ModelEntry("qwen-plus", "Qwen Plus", (CAP_DIALOGUE, CAP_CLOUD),
                       content_policy_profile=POLICY_PROVIDER_POLICY_DEPENDENT),
            ModelEntry("qwen-max", "Qwen Max", (CAP_DIALOGUE, CAP_CLOUD),
                       content_policy_profile=POLICY_PROVIDER_POLICY_DEPENDENT),
            ModelEntry("qwen-vl-plus", "Qwen-VL Plus", (CAP_VISION, CAP_CLOUD),
                       status=MODEL_UNVERIFIED,
                       content_policy_profile=POLICY_PROVIDER_POLICY_DEPENDENT),
        ),
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
        models=(
            ModelEntry("llama3", "Llama 3", (CAP_DIALOGUE, CAP_LOCAL),
                       content_policy_profile=POLICY_LOCAL_MODEL_POLICY),
            ModelEntry("llama3.1", "Llama 3.1", (CAP_DIALOGUE, CAP_LOCAL),
                       content_policy_profile=POLICY_LOCAL_MODEL_POLICY),
            ModelEntry("qwen2.5", "Qwen 2.5", (CAP_DIALOGUE, CAP_LOCAL),
                       content_policy_profile=POLICY_LOCAL_MODEL_POLICY),
            ModelEntry("llava", "LLaVA", (CAP_VISION, CAP_LOCAL),
                       status=MODEL_UNVERIFIED,
                       notes="Локальный анализ изображений — не проверено в этой сборке.",
                       content_policy_profile=POLICY_LOCAL_MODEL_POLICY),
        ),
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
        models=(
            ModelEntry("fake", "Fake", (CAP_DIALOGUE, CAP_LOCAL),
                       content_policy_profile=POLICY_STANDARD_ONLY),
        ),
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


def is_known_capability(cap: str) -> bool:
    return cap in ALL_CAPABILITIES


def require_role_supported(provider_id: str, role: str) -> ProviderEntry:
    if not is_known_role(role):
        raise ProviderRegistryError("unknown_role", f"unknown model role {role!r}")
    entry = get_provider(provider_id)
    if role not in entry.supported_roles:
        raise ProviderRegistryError(
            "unsupported_role", f"provider {entry.provider_id!r} does not support role {role!r}"
        )
    return entry


def require_model_supported(provider_id: str, model_id: str, role: str) -> Tuple[ProviderEntry, ModelEntry]:
    """Validate provider exists, model exists in that provider's catalog, and the
    model's capabilities satisfy the requested role. The catalog is
    authoritative. Raises :class:`ProviderRegistryError` with a bounded code."""
    entry = require_role_supported(provider_id, role)
    model = entry.get_model(model_id)
    if model is None:
        raise ProviderRegistryError(
            "unknown_model", f"provider {entry.provider_id!r} has no model {model_id!r}"
        )
    if not model.supports_role(role):
        raise ProviderRegistryError(
            "unsupported_model_role",
            f"model {model.model_id!r} does not support role {role!r}",
        )
    return entry, model


def providers_supporting_role(role: str) -> Tuple[str, ...]:
    if not is_known_role(role):
        return ()
    return tuple(e.provider_id for e in _ENTRIES if role in e.supported_roles)
