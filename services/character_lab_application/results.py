#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Character Lab Application Service v1 -- immutable application-layer DTOs.

Small, stable result/view objects for UI. No raw ``CharacterCanonSnapshot``,
no filesystem ``Path``, no Character Canon internals are ever exposed past
this boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class CharacterSummary:
    """One character's Character Lab-facing summary."""

    character_id: str
    label: str
    status: Optional[str]


@dataclass(frozen=True)
class CharacterVersionSummary:
    """One character version, as actually represented by current canon data.

    Current-main Character Canon carries a single ``active_version`` string
    tag per character (no version history). ``list_versions`` therefore
    returns zero entries when no tag is present, or exactly one entry when it
    is -- never a synthesized/demo list.
    """

    version_id: str
    is_active: bool


@dataclass(frozen=True)
class CharacterInspectorDetail:
    """Read-only foundation metadata for the selected character/version."""

    character_id: str
    label: str
    status: Optional[str]
    canon_approved: bool
    active_version_id: Optional[str]
    source_ref: Optional[str]


@dataclass(frozen=True)
class Message:
    """One transcript entry. Offline-only: never populated by a provider."""

    role: str
    content: str


@dataclass(frozen=True)
class LabSession:
    """A local, offline application-level test-dialogue session.

    Immutable: ``character_id``/``version_id`` are the session's binding and
    never change for the lifetime of this session id. Appending a message
    produces a new ``LabSession`` value (via
    ``CharacterLabApplicationService.append_message``); it never mutates an
    existing instance in place, and a later change to the *currently
    selected* character/version elsewhere in the UI never reaches back into
    an already-created session's binding.
    """

    session_id: str
    character_id: str
    version_id: Optional[str]
    transcript: Tuple[Message, ...] = ()


@dataclass(frozen=True)
class CharacterAuthoringResult:
    """Successful local Character Authoring mutation result.

    The four stable content identities are returned for callers, but this DTO
    is not a runtime/test-session pin and carries no publication or activation
    authority.
    """

    operation: str
    character_id: str
    version_id: str
    revision_id: str
    snapshot_hash: str
    lifecycle_state: str
    source_character_id: Optional[str] = None
    source_revision_id: Optional[str] = None
    source_snapshot_hash: Optional[str] = None
    source_ref: Optional[str] = None


@dataclass(frozen=True)
class CharacterSessionPin:
    """Exact immutable identity of one persisted authoring revision.

    A pin is detached from mutable character/version pointers and carries no
    publication, activation, or runtime-memory authority.
    """

    character_id: str
    version_id: str
    revision_id: str
    snapshot_hash: str


@dataclass(frozen=True)
class CharacterPublicationResult:
    """Path-free identity of one immutable published runtime package."""

    runtime_package_schema_version: str
    character_id: str
    package_hash: str
    source_version_id: str
    source_revision_id: str
    source_snapshot_hash: str
