#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Plain-data models for the N7 Persona Data Gateway (P1a-S1 partial runtime).

All models are ``@dataclass(frozen=True)`` and contain only detached plain
data: ``dict``/``list``/``tuple``/``str``/``int``/``float``/``bool``/``None``
(or nested frozen dataclasses composed exclusively of the same). None of
these models ever hold Ren'Py objects, live mutable references, open file
handles, or provider objects.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class CharacterRef:
    """A minimal character identity: id + display name."""

    id: str
    name: str


@dataclass(frozen=True)
class ModuleMetadata:
    """One manifest entry describing an allowlisted persona module."""

    module_id: str
    version: Optional[str]
    required: Optional[bool]
    description: Optional[str]


@dataclass(frozen=True)
class CharacterManifest:
    """The parsed, validated INDEX.json manifest for one character."""

    id: str
    name: str
    version: Optional[str]
    schema_version: Optional[str]
    default_level: Optional[str]
    default_ag_level: Optional[int]
    compatible_scenarios: Tuple[str, ...]
    modules: Tuple[ModuleMetadata, ...]


@dataclass(frozen=True)
class Provenance:
    """Provenance attached to every module read response.

    For modular Kira files, ``schema`` is always ``None`` (no valid
    per-module schema is declared -- see docs on JSON_PARSE_ONLY policy).
    ``read_only`` is always ``True``. ``source`` is a stable logical
    identifier (``"personas/<character_id>/<module_id>"``), never an
    absolute local filesystem path.
    """

    source: str
    schema: Optional[str]
    content_hash: str
    version: Optional[str]
    read_only: bool


@dataclass(frozen=True)
class ModuleResult:
    """One successfully read persona module, with provenance."""

    module_id: str
    data: dict
    provenance: Provenance


@dataclass(frozen=True)
class MessageEntry:
    """One (role, content) transcript message, detached from source."""

    role: str
    content: str


@dataclass(frozen=True)
class SessionMeta:
    """Metadata for one saved aside/session record (no raw file path)."""

    session_id: Optional[str]
    scene_id: str
    beat_id: str
    progress_index: int


@dataclass(frozen=True)
class StateSnapshot:
    """A detached snapshot of saved aside/session memory for one character.

    Sourced exclusively from saved session data (see
    ``state_snapshot_service.py``) -- never from live Ren'Py ``v2_*``
    canon and never fabricated from a state template.
    """

    character_id: str
    summary: str
    recent: Tuple[MessageEntry, ...]
    session_count: int
    max_progress_index: Optional[int]
    sessions: Tuple[SessionMeta, ...]


@dataclass(frozen=True)
class HistoryRecord:
    """One matched history record from a read-only history search."""

    session_id: Optional[str]
    scene_id: Optional[str]
    beat_id: Optional[str]
    progress_index: Optional[int]
    match_type: str
    snippet: str


@dataclass(frozen=True)
class HistorySearchResult:
    """The full result of one read-only history search."""

    character_id: str
    query: str
    limit: int
    records: Tuple[HistoryRecord, ...]
