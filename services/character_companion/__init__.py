#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Character Companion -- the end-user chat client's backend surface.

Separate from Character Lab (the developer/operator/debug client). Composes the
same Character Runtime / Core lower layers through a minimal five-operation
service and a JSON transport; adds a durable COMPANION session registry and
reuses the existing Runtime Memory event log as conversation history.
"""

from .catalog import (
    CompanionCatalog,
    CompanionCharacterEntry,
    build_default_catalog,
)
from .image_jobs import (
    KIND_CONTEXT,
    KIND_CUSTOM,
    STATE_FAILED,
    STATE_GENERATING,
    STATE_QUEUED,
    STATE_READY,
    CompanionImageError,
    FakeImageGenerator,
    ImageJob,
    ImageJobService,
    UnavailableImageGenerator,
)
from .attachments import (
    AUTHORITY_USER_ATTACHMENT_DATA,
    AcceptedAttachment,
    AttachmentError,
    AttachmentSecurityGateway,
)
from .cloud_provider import (
    CloudProviderConfig,
    CloudProviderError,
    build_openai_compat_provider_factory,
)
from .credentials import (
    CredentialError,
    CredentialMetadata,
    CredentialVault,
    InMemoryCredentialVault,
    WindowsDpapiCredentialVault,
    build_default_credential_vault,
)
from .provider_registry import (
    ALL_ROLES,
    ROLE_DIALOGUE,
    RUNTIME_WIRED_ROLES,
    ProviderEntry,
    ProviderRegistryError,
    all_providers,
    get_provider,
)
from .provider_resolution import (
    CompanionConfigError,
    resolve_dialogue_provider_factory,
    test_provider_connection,
)
from .release import (
    COMPANION_MODES,
    KIRA_GROUNDED_OBSERVED_PROMPT_TOKENS,
    MODE_DEV,
    MODE_RELEASE,
    RELEASE_NAME,
    RELEASE_VERSION,
    ReleaseManifestError,
    build_release_manifest,
    normalize_mode,
)
from .scenarios import SCENE_FIELDS, random_field, random_scenario
from .settings import (
    NUM_CTX_KIRA_SAFE_HINT,
    NUM_CTX_MAX,
    NUM_CTX_MIN,
    CompanionSettings,
    RoleAssignment,
    SettingsError,
    SettingsStore,
)
from .service import (
    PURPOSE_COMPANION,
    CompanionError,
    CompanionMessage,
    CompanionProviderError,
    CompanionScene,
    CompanionService,
    CompanionSession,
    CompanionTurn,
)
from .local_provider import (
    PROVIDER_FAKE,
    PROVIDER_LOCAL,
    LocalLLMConfig,
    LocalLLMProviderError,
    assert_loopback_url,
    build_local_llm_provider_factory,
    resolve_companion_provider_factory,
)
from .transport import CompanionTransport, CompanionTransportError

__all__ = [
    "PROVIDER_FAKE",
    "PROVIDER_LOCAL",
    "LocalLLMConfig",
    "LocalLLMProviderError",
    "assert_loopback_url",
    "build_local_llm_provider_factory",
    "resolve_companion_provider_factory",
    "CompanionCatalog",
    "CompanionCharacterEntry",
    "build_default_catalog",
    "PURPOSE_COMPANION",
    "CompanionError",
    "CompanionProviderError",
    "CompanionMessage",
    "CompanionScene",
    "CompanionService",
    "CompanionSession",
    "CompanionTurn",
    "CompanionTransport",
    "CompanionTransportError",
    "CompanionImageError",
    "ImageJob",
    "ImageJobService",
    "FakeImageGenerator",
    "UnavailableImageGenerator",
    "KIND_CUSTOM",
    "KIND_CONTEXT",
    "STATE_QUEUED",
    "STATE_GENERATING",
    "STATE_READY",
    "STATE_FAILED",
    "SCENE_FIELDS",
    "random_scenario",
    "random_field",
    "CredentialError",
    "CredentialMetadata",
    "CredentialVault",
    "InMemoryCredentialVault",
    "WindowsDpapiCredentialVault",
    "build_default_credential_vault",
    "CompanionSettings",
    "RoleAssignment",
    "SettingsError",
    "SettingsStore",
    "NUM_CTX_MIN",
    "NUM_CTX_MAX",
    "NUM_CTX_KIRA_SAFE_HINT",
    "ProviderEntry",
    "ProviderRegistryError",
    "all_providers",
    "get_provider",
    "ALL_ROLES",
    "ROLE_DIALOGUE",
    "RUNTIME_WIRED_ROLES",
    "CompanionConfigError",
    "resolve_dialogue_provider_factory",
    "test_provider_connection",
    "CloudProviderConfig",
    "CloudProviderError",
    "build_openai_compat_provider_factory",
    "AttachmentSecurityGateway",
    "AttachmentError",
    "AcceptedAttachment",
    "AUTHORITY_USER_ATTACHMENT_DATA",
    "RELEASE_NAME",
    "RELEASE_VERSION",
    "MODE_DEV",
    "MODE_RELEASE",
    "COMPANION_MODES",
    "KIRA_GROUNDED_OBSERVED_PROMPT_TOKENS",
    "ReleaseManifestError",
    "build_release_manifest",
    "normalize_mode",
]
