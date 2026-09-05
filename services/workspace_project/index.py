#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Workspace / Domain Foundation v0 -- read-only WorkspaceIndex.

Resolves one project's registered ``ProjectEntityRef`` entries to their
current locator, using ONLY existing canonical loaders:

    SCENE        -- pure pass-through of the manifest's own ``source_ref``.
                    No canonical multi-scene store exists yet to verify
                    against, so this package never reads, parses, or hashes
                    an ASS file; SCENE resolution is intentionally the
                    narrowest case here.
    CHARACTER    -- ``services.character_canon_bridge.read_character_canon``,
                    given an explicit, caller-supplied Character Canon root.
                    Never scans the root; reads exactly the one requested id.
    LOCATION     -- ``services.location_canon.load_location``, given an
                    explicit, caller-supplied repo root.
    MEDIA_ASSET  -- ``tools.visual_asset_registry.load_registry`` /
                    ``lookup_asset``, given an explicit, caller-supplied
                    registry path.

The index is in-memory only: it is built fresh from a ``ProjectManifest``
plus explicit roots, and nothing here is written to disk. Membership (is
this id even in the project) and existence (does the canonical loader still
find it) are checked separately -- a registered id whose canonical loader
now fails raises ``BrokenRegistrationError`` rather than silently returning
stale manifest data.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

from services.character_canon_bridge import (
    CharacterCanonBridgeError,
    read_character_canon,
)
from services.location_canon import LocationCanonError, load_location
from tools.visual_asset_registry import load_registry, lookup_asset

from .errors import (
    BrokenRegistrationError,
    DuplicateEntityError,
    EntityNotFoundError,
    UnknownEntityKindError,
    WorkspaceIndexConfigurationError,
)
from .model import CHARACTER, ENTITY_KINDS, LOCATION, MEDIA_ASSET, SCENE, ProjectEntityRef, ProjectManifest

_DEFAULT_ASSET_REGISTRY_RELATIVE_PATH = ("scenarios", "visual_assets", "ASSET_REGISTRY.json")
_CHARACTER_USAGE_CONTEXT = "authoring"


@dataclass(frozen=True)
class ResolvedEntity:
    """The result of resolving one registered entity: its current locator.

    ``source_ref`` is a locator only, never identity -- ``entity_kind`` +
    ``stable_id`` remain the entity's identity regardless of this value.
    ``content_hash`` is populated only when the underlying canonical loader
    computes one; SCENE resolution never reads a file, so it is always
    ``None`` there.
    """

    entity_kind: str
    stable_id: str
    source_ref: str
    content_hash: Optional[str] = None


class WorkspaceIndex:
    """Read-only resolver over one project's registered entities.

    Construction never touches Character Canon, Location Canon, or the
    Visual Asset Registry -- it only indexes the manifest's own entries in
    memory. Every canonical loader call happens lazily, inside ``resolve``.
    """

    def __init__(
        self,
        manifest: ProjectManifest,
        *,
        repo_root: Path,
        character_canon_root: Optional[Path] = None,
        asset_registry_path: Optional[Path] = None,
    ) -> None:
        self._repo_root = Path(repo_root)
        self._character_canon_root = (
            Path(character_canon_root) if character_canon_root is not None else None
        )
        self._asset_registry_path = (
            Path(asset_registry_path)
            if asset_registry_path is not None
            else self._repo_root.joinpath(*_DEFAULT_ASSET_REGISTRY_RELATIVE_PATH)
        )

        entries: Dict[Tuple[str, str], ProjectEntityRef] = {}
        for entity in manifest.entities:
            key = entity.key()
            if key in entries:
                # ProjectManifest already rejects this at construction; this
                # is a defense-in-depth check of the index's own input.
                raise DuplicateEntityError(f"duplicate entity {key!r} in manifest")
            entries[key] = entity
        self._entries = entries

    def resolve(self, entity_kind: str, stable_id: str) -> ResolvedEntity:
        """Resolve one registered ``(entity_kind, stable_id)`` to its current locator.

        Raises ``UnknownEntityKindError`` for an unsupported ``entity_kind``,
        ``EntityNotFoundError`` when the pair is not registered in this
        project, ``WorkspaceIndexConfigurationError`` when resolving this
        kind requires a root the index was not given, and
        ``BrokenRegistrationError`` when the registered id no longer
        resolves through its existing canonical loader.
        """
        if entity_kind not in ENTITY_KINDS:
            raise UnknownEntityKindError(
                f"entity_kind: expected one of {ENTITY_KINDS}, got {entity_kind!r}"
            )

        entry = self._entries.get((entity_kind, stable_id))
        if entry is None:
            raise EntityNotFoundError(
                f"{entity_kind}:{stable_id} is not registered in this project"
            )

        if entity_kind == SCENE:
            return ResolvedEntity(
                entity_kind=SCENE, stable_id=stable_id, source_ref=entry.source_ref
            )
        if entity_kind == LOCATION:
            return self._resolve_location(stable_id)
        if entity_kind == CHARACTER:
            return self._resolve_character(stable_id)
        return self._resolve_media_asset(stable_id)

    def _resolve_location(self, location_id: str) -> ResolvedEntity:
        try:
            canon = load_location(self._repo_root, location_id)
        except LocationCanonError as exc:
            raise BrokenRegistrationError(
                f"registered location {location_id!r} did not resolve: {exc}"
            ) from exc
        return ResolvedEntity(
            entity_kind=LOCATION,
            stable_id=location_id,
            source_ref=f"scenarios/locations/{location_id}.json",
            content_hash=canon.content_hash,
        )

    def _resolve_character(self, character_id: str) -> ResolvedEntity:
        if self._character_canon_root is None:
            raise WorkspaceIndexConfigurationError(
                "resolving a CHARACTER entity requires character_canon_root"
            )
        try:
            snapshot = read_character_canon(
                self._character_canon_root, character_id, _CHARACTER_USAGE_CONTEXT
            )
        except CharacterCanonBridgeError as exc:
            raise BrokenRegistrationError(
                f"registered character {character_id!r} did not resolve: {exc}"
            ) from exc
        return ResolvedEntity(
            entity_kind=CHARACTER,
            stable_id=character_id,
            source_ref=snapshot.provenance.source_ref,
            content_hash=snapshot.content_hash,
        )

    def _resolve_media_asset(self, asset_id: str) -> ResolvedEntity:
        try:
            records = load_registry(self._asset_registry_path)
            record = lookup_asset(records, asset_id)
        except ValueError as exc:
            raise BrokenRegistrationError(
                f"registered media asset {asset_id!r} did not resolve: {exc}"
            ) from exc
        return ResolvedEntity(
            entity_kind=MEDIA_ASSET,
            stable_id=asset_id,
            source_ref=record.get("relative_path", ""),
            content_hash=record.get("imported_hash") or record.get("source_hash"),
        )
