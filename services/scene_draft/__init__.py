#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scene Editor domain lifecycle -- public API.

Additive, domain/backend only. ASS remains the canonical accepted-scene
contract; SceneVersion is an authoring/history artifact. No UI, no Story Graph,
no Variant, no ChoiceBlock, no provider calls.
"""

from __future__ import annotations

from .compiler import accept_draft
from .errors import (
    AcceptanceError,
    AcceptanceIncompleteError,
    AcceptedVersionImmutableError,
    AlreadyAcceptedError,
    PersistenceError,
    SceneDraftError,
    SceneHistoryExistsError,
    SceneIdMismatchError,
    SceneInvariantError,
    SceneValidationError,
    SceneVersionNotFoundError,
)
from .hashing import compute_authored_body_hash
from .model import (
    LIFECYCLE_ACCEPTED,
    LIFECYCLE_DRAFT,
    LIFECYCLES,
    AcceptanceLink,
    SceneVersion,
)
from .store import SceneDraftStore, serialize_pointer, serialize_version_record

__all__ = [
    # Model
    "SceneVersion",
    "AcceptanceLink",
    "LIFECYCLE_DRAFT",
    "LIFECYCLE_ACCEPTED",
    "LIFECYCLES",
    # Store / compiler
    "SceneDraftStore",
    "accept_draft",
    "serialize_version_record",
    "serialize_pointer",
    # Hashing
    "compute_authored_body_hash",
    # Errors
    "SceneDraftError",
    "SceneValidationError",
    "SceneIdMismatchError",
    "SceneInvariantError",
    "SceneVersionNotFoundError",
    "SceneHistoryExistsError",
    "AcceptedVersionImmutableError",
    "AlreadyAcceptedError",
    "PersistenceError",
    "AcceptanceError",
    "AcceptanceIncompleteError",
]
