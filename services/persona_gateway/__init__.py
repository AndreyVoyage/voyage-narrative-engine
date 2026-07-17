#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
N7 Persona Data Gateway -- P1a-S1 partial runtime public API.

Exposes only the P1a-S1 slice: static Kira module retrieval, saved
aside/session state snapshot, and read-only history search. This slice
deliberately does not export AD policy, MCP/HTTP adapter symbols, Ren'Py
adapter symbols, LLM integration, or any write/proposal-capable N6 API.

``services/__init__.py`` is intentionally NOT created: ``services`` is
resolved as an implicit PEP 420 namespace package.
"""

from __future__ import annotations

from .errors import (
    CharacterNotFoundError,
    HistoryNotFoundError,
    HistoryRecordError,
    ManifestIntegrityError,
    ManifestNotFoundError,
    ManifestParseError,
    ModuleEncodingError,
    ModuleParseError,
    ModuleSizeLimitError,
    PathSecurityError,
    PersonaGatewayError,
    PersonaModuleNotFoundError,
    SnapshotUnavailableError,
    UnsupportedExtensionError,
)
from .history_query_service import HistoryQueryService
from .models import (
    CharacterManifest,
    CharacterRef,
    HistoryRecord,
    HistorySearchResult,
    MessageEntry,
    ModuleMetadata,
    ModuleResult,
    Provenance,
    SessionMeta,
    StateSnapshot,
)
from .persona_repository import PersonaRepository
from .state_snapshot_service import StateSnapshotService

__all__ = [
    # Services
    "PersonaRepository",
    "StateSnapshotService",
    "HistoryQueryService",
    # Models
    "CharacterRef",
    "ModuleMetadata",
    "CharacterManifest",
    "Provenance",
    "ModuleResult",
    "MessageEntry",
    "SessionMeta",
    "StateSnapshot",
    "HistoryRecord",
    "HistorySearchResult",
    # Errors
    "PersonaGatewayError",
    "ManifestNotFoundError",
    "ManifestParseError",
    "ManifestIntegrityError",
    "CharacterNotFoundError",
    "PersonaModuleNotFoundError",
    "ModuleEncodingError",
    "ModuleParseError",
    "PathSecurityError",
    "UnsupportedExtensionError",
    "ModuleSizeLimitError",
    "SnapshotUnavailableError",
    "HistoryNotFoundError",
    "HistoryRecordError",
]
