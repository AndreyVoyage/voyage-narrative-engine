#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Workspace / Domain Foundation v0 -- public API.

A minimal project-scoped membership manifest (``ProjectManifest``) plus a
read-only, stable-ID-keyed resolver (``WorkspaceIndex``) over already-
existing canonical VNE domain objects: ASS-anchored scene references,
Character Canon, Location Canon, and the Visual Asset Registry.

This package does not implement a Project Character Library, Character
Package version pinning, an editable Scene aggregate, a Story Graph, a
migration framework, a filesystem watcher, move/rename tracking, or
multi-workspace orchestration. It never writes to Character Canon, ASS,
Location Canon, or the Visual Asset Registry, and it never scans a
directory to discover entities -- membership is exactly what a
``ProjectManifest`` explicitly lists.
"""

from __future__ import annotations

from .errors import (
    BrokenRegistrationError,
    DuplicateEntityError,
    EntityNotFoundError,
    ProjectManifestError,
    ProjectManifestNotFoundError,
    ProjectManifestValidationError,
    UnknownEntityKindError,
    WorkspaceIndexConfigurationError,
    WorkspaceIndexError,
    WorkspaceProjectError,
)
from .index import ResolvedEntity, WorkspaceIndex
from .manifest import (
    PROJECT_MANIFEST_SCHEMA_VERSION,
    load_manifest,
    parse_manifest,
    save_manifest,
    serialize_manifest,
    validate_manifest,
)
from .model import (
    CHARACTER,
    ENTITY_KINDS,
    LOCATION,
    MEDIA_ASSET,
    SCENE,
    ProjectEntityRef,
    ProjectManifest,
)
from .accepted_batch import (
    ACCEPTED_BATCH_SCHEMA_VERSION,
    AcceptedBatchError,
    AcceptedBatchNotFoundError,
    AcceptedBatchResolutionError,
    AcceptedBatchValidationError,
    AcceptedOrderedASSBatch,
    AcceptedOrderedASSRef,
    load_accepted_batch,
    parse_accepted_batch,
    resolve_accepted_ordered_ass_batch,
    save_accepted_batch,
    serialize_accepted_batch,
    validate_accepted_batch,
)

__all__ = [
    "SCENE",
    "CHARACTER",
    "LOCATION",
    "MEDIA_ASSET",
    "ENTITY_KINDS",
    "ProjectEntityRef",
    "ProjectManifest",
    "PROJECT_MANIFEST_SCHEMA_VERSION",
    "serialize_manifest",
    "parse_manifest",
    "load_manifest",
    "save_manifest",
    "validate_manifest",
    "WorkspaceIndex",
    "ResolvedEntity",
    "WorkspaceProjectError",
    "ProjectManifestError",
    "ProjectManifestValidationError",
    "ProjectManifestNotFoundError",
    "WorkspaceIndexError",
    "WorkspaceIndexConfigurationError",
    "UnknownEntityKindError",
    "EntityNotFoundError",
    "DuplicateEntityError",
    "BrokenRegistrationError",
    # Accepted OrderedASS batch (references-only production selection)
    "ACCEPTED_BATCH_SCHEMA_VERSION",
    "AcceptedOrderedASSRef",
    "AcceptedOrderedASSBatch",
    "serialize_accepted_batch",
    "parse_accepted_batch",
    "load_accepted_batch",
    "save_accepted_batch",
    "validate_accepted_batch",
    "resolve_accepted_ordered_ass_batch",
    "AcceptedBatchError",
    "AcceptedBatchValidationError",
    "AcceptedBatchNotFoundError",
    "AcceptedBatchResolutionError",
]
