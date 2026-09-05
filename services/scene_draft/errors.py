#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exception hierarchy for the Scene Editor domain lifecycle slice
(``services/scene_draft``).

Small, transport-independent, named exceptions, mirroring the house style of
``services/workspace_project/errors.py`` and ``services/persona_gateway/errors.py``.
Messages never carry raw scene content or absolute machine paths -- only stable
logical identifiers (scene_id, version, field names) may appear.
"""

from __future__ import annotations


class SceneDraftError(Exception):
    """Root of the scene_draft exception hierarchy."""


class SceneValidationError(SceneDraftError):
    """Raised when a scene ``body`` is not a dict, or fails the existing
    unmodified ``tools.narrative_schema_v2.validate_scene`` semantic check."""


class SceneIdMismatchError(SceneDraftError):
    """Raised when ``body["id"]`` does not exactly equal the requested ``scene_id``."""


class SceneInvariantError(SceneDraftError):
    """Raised on a model invariant violation: invalid ``version``, unknown
    ``lifecycle``, DRAFT carrying an acceptance, or ACCEPTED without one."""


class SceneVersionNotFoundError(SceneDraftError):
    """Raised when no persisted record exists for ``(scene_id, version)``."""


class SceneHistoryExistsError(SceneDraftError):
    """Raised when ``create_initial_draft`` is called for a scene that already
    has an initialized version history (a latest-version pointer exists)."""


class AcceptedVersionImmutableError(SceneDraftError):
    """Raised when a mutation (``save_draft``) targets an ACCEPTED version.

    Accepted versions are immutable. Editing them requires
    ``fork_draft_from_version``, never an in-place save.
    """


class AlreadyAcceptedError(SceneDraftError):
    """Raised when ``accept_draft`` targets a version that is not DRAFT (that
    is, the one-time DRAFT -> ACCEPTED transition has already occurred)."""


class PersistenceError(SceneDraftError):
    """Raised when a persisted record or pointer is missing, malformed, or
    mismatches the requested ``scene_id``/``version``, or when a scene_id
    cannot be safely mapped to a locator."""


class AcceptanceError(SceneDraftError):
    """Raised when the ASS importer succeeds but the returned ASS is
    inconsistent with the SceneVersion being accepted (scene_id or version
    mismatch)."""
