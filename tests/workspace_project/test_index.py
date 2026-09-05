#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WorkspaceIndex v0 tests -- resolution per entity kind, fail-closed lookup,
duplicate rejection, and the path-never-defines-identity invariant."""

from __future__ import annotations

import pytest

from services.location_canon import load_location
from services.workspace_project import (
    CHARACTER,
    LOCATION,
    MEDIA_ASSET,
    SCENE,
    BrokenRegistrationError,
    DuplicateEntityError,
    EntityNotFoundError,
    ProjectEntityRef,
    ProjectManifest,
    UnknownEntityKindError,
    WorkspaceIndex,
    WorkspaceIndexConfigurationError,
)

from .conftest import write_asset_registry, write_character_preset


def _manifest(entities):
    return ProjectManifest(
        schema_version="vne_workspace_project_manifest/0.1",
        project_id="demo_project",
        entities=tuple(entities),
    )


# ---------------------------------------------------------------------------
# SCENE -- pure manifest pass-through, no file I/O
# ---------------------------------------------------------------------------


def test_resolve_registered_scene_reference(repo_root):
    manifest = _manifest(
        [ProjectEntityRef(entity_kind=SCENE, stable_id="sc_004", source_ref="authoring/scenes/sc_004.json")]
    )
    index = WorkspaceIndex(manifest, repo_root=repo_root)

    resolved = index.resolve(SCENE, "sc_004")
    assert resolved.entity_kind == SCENE
    assert resolved.stable_id == "sc_004"
    assert resolved.source_ref == "authoring/scenes/sc_004.json"
    assert resolved.content_hash is None


# ---------------------------------------------------------------------------
# LOCATION -- resolved through services.location_canon.load_location
# ---------------------------------------------------------------------------


def test_resolve_registered_location_reference(repo_root):
    manifest = _manifest([ProjectEntityRef(entity_kind=LOCATION, stable_id="gym")])
    index = WorkspaceIndex(manifest, repo_root=repo_root)

    resolved = index.resolve(LOCATION, "gym")
    assert resolved.entity_kind == LOCATION
    assert resolved.stable_id == "gym"
    assert resolved.source_ref == "scenarios/locations/gym.json"

    direct = load_location(repo_root, "gym")
    assert resolved.content_hash == direct.content_hash


def test_location_resolution_never_depends_on_a_manifest_path(repo_root):
    """LOCATION entries carry no path at all (forbidden by ProjectEntityRef);
    the resolved locator comes entirely from the existing canonical loader,
    driven only by the stable id."""
    manifest = _manifest([ProjectEntityRef(entity_kind=LOCATION, stable_id="yoga_hall")])
    index = WorkspaceIndex(manifest, repo_root=repo_root)

    resolved = index.resolve(LOCATION, "yoga_hall")
    direct = load_location(repo_root, "yoga_hall")
    assert resolved.source_ref == "scenarios/locations/yoga_hall.json"
    assert resolved.content_hash == direct.content_hash


def test_registered_location_that_no_longer_resolves_fails_closed(repo_root):
    manifest = _manifest([ProjectEntityRef(entity_kind=LOCATION, stable_id="no_such_location")])
    index = WorkspaceIndex(manifest, repo_root=repo_root)

    with pytest.raises(BrokenRegistrationError):
        index.resolve(LOCATION, "no_such_location")


# ---------------------------------------------------------------------------
# CHARACTER -- resolved through services.character_canon_bridge.read_character_canon
# ---------------------------------------------------------------------------


def test_resolve_registered_character_reference(tmp_path):
    canon_root = tmp_path / "character-canon"
    write_character_preset(canon_root, "KIRA", "APPROVED_AS_CANON")

    manifest = _manifest([ProjectEntityRef(entity_kind=CHARACTER, stable_id="KIRA")])
    index = WorkspaceIndex(manifest, repo_root=tmp_path, character_canon_root=canon_root)

    resolved = index.resolve(CHARACTER, "KIRA")
    assert resolved.entity_kind == CHARACTER
    assert resolved.stable_id == "KIRA"
    assert resolved.source_ref == "AI_CHARACTERS/KIRA/10_notes/KIRA_REFERENCE_PRESETS.json"
    assert resolved.content_hash


def test_character_resolution_without_canon_root_is_a_configuration_error(tmp_path):
    manifest = _manifest([ProjectEntityRef(entity_kind=CHARACTER, stable_id="KIRA")])
    index = WorkspaceIndex(manifest, repo_root=tmp_path)

    with pytest.raises(WorkspaceIndexConfigurationError):
        index.resolve(CHARACTER, "KIRA")


def test_registered_character_that_no_longer_resolves_fails_closed(tmp_path):
    canon_root = tmp_path / "character-canon"  # never populated
    manifest = _manifest([ProjectEntityRef(entity_kind=CHARACTER, stable_id="GHOST")])
    index = WorkspaceIndex(manifest, repo_root=tmp_path, character_canon_root=canon_root)

    with pytest.raises(BrokenRegistrationError):
        index.resolve(CHARACTER, "GHOST")


# ---------------------------------------------------------------------------
# MEDIA_ASSET -- resolved through tools.visual_asset_registry
# ---------------------------------------------------------------------------


def test_resolve_registered_media_asset_reference(tmp_path):
    registry_path = tmp_path / "scenarios" / "visual_assets" / "ASSET_REGISTRY.json"
    write_asset_registry(
        registry_path,
        [
            {
                "asset_id": "gym_wide_shot",
                "type": "background",
                "relative_path": "novel/game/images/story/gym_wide_shot.png",
                "source_kind": "manual",
            }
        ],
    )

    manifest = _manifest([ProjectEntityRef(entity_kind=MEDIA_ASSET, stable_id="gym_wide_shot")])
    index = WorkspaceIndex(manifest, repo_root=tmp_path, asset_registry_path=registry_path)

    resolved = index.resolve(MEDIA_ASSET, "gym_wide_shot")
    assert resolved.entity_kind == MEDIA_ASSET
    assert resolved.stable_id == "gym_wide_shot"
    assert resolved.source_ref == "novel/game/images/story/gym_wide_shot.png"


def test_media_asset_resolution_uses_default_registry_path_under_repo_root(tmp_path):
    registry_path = tmp_path / "scenarios" / "visual_assets" / "ASSET_REGISTRY.json"
    write_asset_registry(
        registry_path,
        [{"asset_id": "gym_wide_shot", "type": "background", "relative_path": "x/y.png"}],
    )

    manifest = _manifest([ProjectEntityRef(entity_kind=MEDIA_ASSET, stable_id="gym_wide_shot")])
    # No explicit asset_registry_path: must fall back to repo_root's default location.
    index = WorkspaceIndex(manifest, repo_root=tmp_path)

    resolved = index.resolve(MEDIA_ASSET, "gym_wide_shot")
    assert resolved.source_ref == "x/y.png"


def test_registered_media_asset_that_no_longer_resolves_fails_closed(tmp_path):
    registry_path = tmp_path / "scenarios" / "visual_assets" / "ASSET_REGISTRY.json"
    write_asset_registry(registry_path, [])  # empty registry

    manifest = _manifest([ProjectEntityRef(entity_kind=MEDIA_ASSET, stable_id="missing_asset")])
    index = WorkspaceIndex(manifest, repo_root=tmp_path, asset_registry_path=registry_path)

    with pytest.raises(BrokenRegistrationError):
        index.resolve(MEDIA_ASSET, "missing_asset")


# ---------------------------------------------------------------------------
# Fail-closed lookup semantics
# ---------------------------------------------------------------------------


def test_unknown_id_raises_typed_not_found(repo_root):
    manifest = _manifest([ProjectEntityRef(entity_kind=LOCATION, stable_id="gym")])
    index = WorkspaceIndex(manifest, repo_root=repo_root)

    with pytest.raises(EntityNotFoundError):
        index.resolve(LOCATION, "not_registered")


def test_wrong_entity_kind_for_a_registered_id_is_not_found(repo_root):
    """"gym" is registered as LOCATION only; asking for it as CHARACTER must
    fail closed rather than resolving across kinds."""
    manifest = _manifest([ProjectEntityRef(entity_kind=LOCATION, stable_id="gym")])
    index = WorkspaceIndex(manifest, repo_root=repo_root)

    with pytest.raises(EntityNotFoundError):
        index.resolve(CHARACTER, "gym")


def test_unsupported_entity_kind_string_raises_unknown_kind(repo_root):
    manifest = _manifest([ProjectEntityRef(entity_kind=LOCATION, stable_id="gym")])
    index = WorkspaceIndex(manifest, repo_root=repo_root)

    with pytest.raises(UnknownEntityKindError):
        index.resolve("NOT_A_KIND", "gym")


def test_duplicate_entities_rejected_defensively_by_the_index(repo_root):
    """ProjectManifest already rejects duplicate (kind, id) pairs at
    construction; the index re-checks its own input independently, so this
    exercises that defense-in-depth path directly (bypassing ProjectManifest's
    own constructor validation via a minimal duck-typed stand-in)."""

    class _RawEntities:
        def __init__(self, entities):
            self.entities = entities

    duplicated = _RawEntities(
        (
            ProjectEntityRef(entity_kind=LOCATION, stable_id="gym"),
            ProjectEntityRef(entity_kind=LOCATION, stable_id="gym"),
        )
    )

    with pytest.raises(DuplicateEntityError):
        WorkspaceIndex(duplicated, repo_root=repo_root)
