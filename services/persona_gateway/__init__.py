#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
N7 Persona Data Gateway -- P1a-S1 partial runtime + P1b Option A public API.

Exposes the P1a-S1 slice (static single-character module retrieval, saved
aside/session state snapshot, and read-only history search) plus the P1b
Option A ``PersonaCatalog`` (caller-injected multi-character catalog, no
registry file, no runtime directory scan). This slice deliberately does
not export AD policy, MCP/HTTP adapter symbols, Ren'Py adapter symbols,
LLM integration, or any write/proposal-capable N6 API.

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
from .persona_catalog import PersonaCatalog
from .persona_repository import PersonaRepository
from .state_snapshot_service import StateSnapshotService

__all__ = [
    # Services
    "PersonaRepository",
    "PersonaCatalog",
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
