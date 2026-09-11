#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Editor Application Service v1 -- immutable application-layer DTOs.

Small, stable result/view objects for UI. Stable IDs are explicit; display
metadata is separated from storage internals; no base32 paths and no raw
filesystem ``Path`` are required by normal UI operations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Tuple


@dataclass(frozen=True)
class EditorDiagnostic:
    """One structured validation/application diagnostic.

    ``code`` is a stable machine-readable category; ``message`` retains the
    original human-readable validator text; ``severity`` is one of
    ``error``/``warning``/``info``. ``entry_id``/``field`` are populated only
    when reliably identifiable from the underlying domain message.
    """

    code: str
    message: str
    severity: str = "error"
    entry_id: Optional[str] = None
    field: Optional[str] = None


@dataclass(frozen=True)
class EditorOperationResult:
    """Structured result of a mutation (create/save/fork/validate/accept)."""

    ok: bool
    code: str
    message: str
    scene_id: Optional[str] = None
    version: Optional[int] = None
    lifecycle: Optional[str] = None
    diagnostics: Tuple[EditorDiagnostic, ...] = ()
    partial_state: bool = False
    recovery_required: bool = False


@dataclass(frozen=True)
class EditorSceneSummary:
    """One scene's editor-facing summary (no storage internals)."""

    scene_id: str
    title: Optional[str]
    latest_version: Optional[int]
    lifecycle: Optional[str]
    accepted_version: Optional[int]
    ass_id: Optional[str]


@dataclass(frozen=True)
class EditorCharacterSummary:
    """One character's editor-facing summary."""

    character_id: str
    label: str
    status: Optional[str]


@dataclass(frozen=True)
class EditorLocationSummary:
    """One location's editor-facing summary."""

    location_id: str
    label: str
    tier: Optional[str]


@dataclass(frozen=True)
class EditorSceneWorkspace:
    """Aggregate editor-facing view of one scene (no storage internals)."""

    scene_id: str
    latest_version: int
    lifecycle: str
    body: dict[str, Any]
    acceptance: Optional[dict[str, str]]
    can_fork_next_version: bool
    manifest_included: bool


@dataclass(frozen=True)
class EditorAcceptanceState:
    """Read-only acceptance/inclusion state for one scene version."""

    scene_id: str
    version: int
    lifecycle: str
    accepted: bool
    ass_id: Optional[str]
    ass_content_hash: Optional[str]
    manifest_included: bool
    batch_included: bool
    batch_resolvable: bool
