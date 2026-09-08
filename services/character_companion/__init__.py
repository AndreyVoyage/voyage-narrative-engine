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
from .scenarios import SCENE_FIELDS, random_field, random_scenario
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
]
