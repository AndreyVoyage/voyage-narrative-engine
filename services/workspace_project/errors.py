#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exception hierarchy for Workspace / Domain Foundation v0.

Small, transport-independent, named exceptions. Messages never carry
absolute machine paths or Character Canon content.
"""

from __future__ import annotations


class WorkspaceProjectError(Exception):
    """Root of the Workspace / Domain Foundation exception hierarchy."""


class ProjectManifestError(WorkspaceProjectError):
    """Root of the ProjectManifest exception hierarchy."""


class ProjectManifestValidationError(ProjectManifestError):
    """Raised when a ProjectManifest or one of its entities is structurally
    unsound: bad ``project_id``/``entity_kind``/``stable_id``, a disallowed
    or missing ``source_ref``, or a duplicate ``(entity_kind, stable_id)``
    pair."""


class ProjectManifestNotFoundError(ProjectManifestError):
    """Raised when the manifest file does not exist at the requested path."""


class WorkspaceIndexError(WorkspaceProjectError):
    """Root of the WorkspaceIndex exception hierarchy."""


class WorkspaceIndexConfigurationError(WorkspaceIndexError):
    """Raised when resolving an entity needs a root the index was not given
    (for example resolving a CHARACTER entity without a
    ``character_canon_root``)."""


class UnknownEntityKindError(WorkspaceIndexError):
    """Raised when ``entity_kind`` is not one of the supported entity kinds."""


class EntityNotFoundError(WorkspaceIndexError):
    """Raised when ``(entity_kind, stable_id)`` is not registered in the
    project."""


class DuplicateEntityError(WorkspaceIndexError):
    """Raised when the same ``(entity_kind, stable_id)`` pair appears more
    than once in the entities handed to the index.

    Defense in depth: ``ProjectManifest`` already rejects this at
    construction, but the index re-checks its own input independently.
    """


class BrokenRegistrationError(WorkspaceIndexError):
    """Raised when a registered entity no longer resolves through its own
    existing canonical loader (for example a registered ``location_id`` with
    no ``scenarios/locations/<id>.json``, or a registered ``asset_id``
    missing from the Visual Asset Registry).

    Membership in the manifest is not proof of current existence -- this
    package fails closed rather than returning stale manifest data.
    """
