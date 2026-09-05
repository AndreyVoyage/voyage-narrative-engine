#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Workspace / Domain Foundation v0 -- ProjectManifest plain-data model.

Deeply immutable, stdlib-only. Mirrors the established VNE immutability
pattern: frozen dataclasses holding only detached plain data, deterministic
``to_dict`` and validated ``from_dict``.

A ``ProjectManifest`` is a small membership boundary: for one project, it
lists which already-existing, already-canonical entities (accepted scenes,
characters, locations, media assets) are in scope, keyed by their own
stable identifiers. It never copies, re-derives, or supersedes those
entities' own payload -- ASS, Location Canon, Character Canon, and the
Visual Asset Registry each remain the sole source of truth for their own
content. This module performs NO filesystem I/O.

Entity kinds (v0, closed set):

    SCENE        -- a known accepted-scene reference (``scene_id``/``ass_id``).
                    No canonical multi-scene store exists yet, so a SCENE
                    entry additionally carries an explicit ``source_ref``
                    locator; this package never scans for ASS files and
                    never reads the referenced source.
    CHARACTER    -- a ``character_id`` resolved through the existing
                    Character Canon Read Bridge.
    LOCATION     -- a ``location_id`` resolved through the existing Location
                    Canon loader.
    MEDIA_ASSET  -- an ``asset_id`` resolved through the existing Visual
                    Asset Registry.

For CHARACTER/LOCATION/MEDIA_ASSET, ``source_ref`` is deliberately forbidden
on the manifest entry: a path is a locator, never logical identity, and
each of these three kinds already has a canonical loader that derives the
real, current locator from the stable id alone.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional, Tuple

from .errors import ProjectManifestValidationError

SCENE = "SCENE"
CHARACTER = "CHARACTER"
LOCATION = "LOCATION"
MEDIA_ASSET = "MEDIA_ASSET"

ENTITY_KINDS: Tuple[str, ...] = (SCENE, CHARACTER, LOCATION, MEDIA_ASSET)

# Kinds whose current locator is always derived fresh from an existing
# canonical loader; a manifest ``source_ref`` would be redundant at best and
# a stale/conflicting hint at worst, so it is rejected outright.
_KINDS_WITHOUT_SOURCE_REF: Tuple[str, ...] = (CHARACTER, LOCATION, MEDIA_ASSET)

# Mirrors the existing lowercase-id convention (location_id / asset_id).
PROJECT_ID_RE = re.compile(r"^[a-z][a-z0-9_]{2,63}$")


def _is_safe_relative_path(value: Any) -> bool:
    """True if ``value`` is a repo-relative, forward-slash, traversal-free path."""
    if not isinstance(value, str) or not value:
        return False
    if value.startswith(("/", "\\")):
        return False
    if re.match(r"^[A-Za-z]:", value):
        return False
    if "\\" in value:
        return False
    parts = value.split("/")
    return all(part not in ("", ".", "..") for part in parts)


def _require_non_empty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or value == "":
        raise ProjectManifestValidationError(f"{field}: required non-empty string")
    if value.strip() != value:
        raise ProjectManifestValidationError(
            f"{field}: must not have leading/trailing whitespace"
        )
    return value


@dataclass(frozen=True)
class ProjectEntityRef:
    """One project-scoped membership entry: an existing entity, by stable id.

    This is a pointer, never a copy: it never carries the referenced
    entity's own payload, and (except for SCENE) never carries a path -- the
    existing canonical loader for that kind is the sole source of the
    actual current locator.
    """

    entity_kind: str
    stable_id: str
    source_ref: Optional[str] = None

    def __post_init__(self) -> None:
        if self.entity_kind not in ENTITY_KINDS:
            raise ProjectManifestValidationError(
                f"entity_kind: expected one of {ENTITY_KINDS}, got {self.entity_kind!r}"
            )
        _require_non_empty_string(self.stable_id, "stable_id")

        if self.entity_kind == SCENE:
            if not isinstance(self.source_ref, str) or self.source_ref == "":
                raise ProjectManifestValidationError(
                    "source_ref: required non-empty string for entity_kind SCENE "
                    "(no canonical multi-scene store exists to derive it from)"
                )
            if not _is_safe_relative_path(self.source_ref):
                raise ProjectManifestValidationError(
                    f"source_ref: unsafe or non-relative path: {self.source_ref!r}"
                )
        elif self.entity_kind in _KINDS_WITHOUT_SOURCE_REF:
            if self.source_ref is not None:
                raise ProjectManifestValidationError(
                    f"source_ref: must be omitted for entity_kind {self.entity_kind} "
                    "(its stable id alone resolves through the existing canonical loader)"
                )

    def key(self) -> Tuple[str, str]:
        """The membership identity: ``(entity_kind, stable_id)``."""
        return (self.entity_kind, self.stable_id)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "entity_kind": self.entity_kind,
            "stable_id": self.stable_id,
        }
        if self.source_ref is not None:
            result["source_ref"] = self.source_ref
        return result

    @classmethod
    def from_dict(cls, data: Any) -> "ProjectEntityRef":
        if not isinstance(data, dict):
            raise ProjectManifestValidationError("entity: must be an object")
        for field in ("entity_kind", "stable_id"):
            if field not in data:
                raise ProjectManifestValidationError(f"entity.{field}: required field missing")
        return cls(
            entity_kind=data["entity_kind"],
            stable_id=data["stable_id"],
            source_ref=data.get("source_ref"),
        )


@dataclass(frozen=True)
class ProjectManifest:
    """The immutable, deterministic project membership boundary.

    ``entities`` must not contain two entries with the same
    ``(entity_kind, stable_id)`` pair -- membership identity is exactly that
    pair, never a list position or a path.
    """

    schema_version: str
    project_id: str
    entities: Tuple[ProjectEntityRef, ...]

    def __post_init__(self) -> None:
        _require_non_empty_string(self.schema_version, "schema_version")
        project_id = _require_non_empty_string(self.project_id, "project_id")
        if not PROJECT_ID_RE.match(project_id):
            raise ProjectManifestValidationError(
                "project_id: expected lowercase slug [a-z][a-z0-9_]{2,63}"
            )

        entities = tuple(self.entities)
        object.__setattr__(self, "entities", entities)

        seen: dict[Tuple[str, str], int] = {}
        for index, entity in enumerate(entities):
            if not isinstance(entity, ProjectEntityRef):
                raise ProjectManifestValidationError(
                    f"entities[{index}]: expected ProjectEntityRef"
                )
            key = entity.key()
            if key in seen:
                raise ProjectManifestValidationError(
                    f"duplicate entity {key!r} (also at entities[{seen[key]}])"
                )
            seen[key] = index

    def to_dict(self) -> dict[str, Any]:
        """Return the full manifest envelope (fresh plain data).

        Entities are sorted by ``(entity_kind, stable_id)`` for deterministic
        serialization, independent of construction/insertion order.
        """
        ordered = sorted(self.entities, key=lambda e: (e.entity_kind, e.stable_id))
        return {
            "schema_version": self.schema_version,
            "project_id": self.project_id,
            "entities": [e.to_dict() for e in ordered],
        }

    @classmethod
    def from_dict(cls, data: Any) -> "ProjectManifest":
        if not isinstance(data, dict):
            raise ProjectManifestValidationError("manifest root must be an object")
        for field in ("schema_version", "project_id", "entities"):
            if field not in data:
                raise ProjectManifestValidationError(f"{field}: required field missing")
        raw_entities = data["entities"]
        if not isinstance(raw_entities, list):
            raise ProjectManifestValidationError("entities: expected an array")
        entities = tuple(ProjectEntityRef.from_dict(item) for item in raw_entities)
        return cls(
            schema_version=data["schema_version"],
            project_id=data["project_id"],
            entities=entities,
        )
