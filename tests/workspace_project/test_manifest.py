#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ProjectManifest v0 tests -- construction validation, duplicate rejection,
deterministic serialization, save/load round-trip, and fail-closed parsing."""

from __future__ import annotations

import json

import pytest

from services.workspace_project import (
    CHARACTER,
    LOCATION,
    MEDIA_ASSET,
    PROJECT_MANIFEST_SCHEMA_VERSION,
    SCENE,
    ProjectEntityRef,
    ProjectManifest,
    ProjectManifestError,
    ProjectManifestNotFoundError,
    ProjectManifestValidationError,
    load_manifest,
    parse_manifest,
    save_manifest,
    serialize_manifest,
    validate_manifest,
)


def _manifest(**overrides):
    base = dict(
        schema_version=PROJECT_MANIFEST_SCHEMA_VERSION,
        project_id="demo_project",
        entities=(
            ProjectEntityRef(entity_kind=LOCATION, stable_id="gym"),
            ProjectEntityRef(entity_kind=CHARACTER, stable_id="KIRA"),
            ProjectEntityRef(entity_kind=MEDIA_ASSET, stable_id="gym_wide_shot"),
            ProjectEntityRef(
                entity_kind=SCENE,
                stable_id="sc_004",
                source_ref="authoring/scenes/sc_004.json",
            ),
        ),
    )
    base.update(overrides)
    return ProjectManifest(**base)


# ---------------------------------------------------------------------------
# ProjectEntityRef construction validation
# ---------------------------------------------------------------------------


def test_valid_entity_construction_for_each_kind():
    ProjectEntityRef(entity_kind=LOCATION, stable_id="gym")
    ProjectEntityRef(entity_kind=CHARACTER, stable_id="KIRA")
    ProjectEntityRef(entity_kind=MEDIA_ASSET, stable_id="gym_wide_shot")
    ProjectEntityRef(entity_kind=SCENE, stable_id="sc_004", source_ref="authoring/scenes/sc_004.json")


def test_invalid_entity_kind_rejected():
    with pytest.raises(ProjectManifestValidationError):
        ProjectEntityRef(entity_kind="FOO", stable_id="x")


def test_empty_stable_id_rejected():
    with pytest.raises(ProjectManifestValidationError):
        ProjectEntityRef(entity_kind=LOCATION, stable_id="")


def test_whitespace_padded_stable_id_rejected():
    with pytest.raises(ProjectManifestValidationError):
        ProjectEntityRef(entity_kind=LOCATION, stable_id=" gym ")


def test_scene_without_source_ref_rejected():
    with pytest.raises(ProjectManifestValidationError):
        ProjectEntityRef(entity_kind=SCENE, stable_id="sc_004")


def test_scene_with_unsafe_source_ref_rejected():
    with pytest.raises(ProjectManifestValidationError):
        ProjectEntityRef(
            entity_kind=SCENE, stable_id="sc_004", source_ref="../outside.json"
        )
    with pytest.raises(ProjectManifestValidationError):
        ProjectEntityRef(
            entity_kind=SCENE, stable_id="sc_004", source_ref="C:/abs/path.json"
        )


@pytest.mark.parametrize("kind", [LOCATION, CHARACTER, MEDIA_ASSET])
def test_source_ref_forbidden_for_derived_kinds(kind):
    """A path never defines identity for kinds with an existing canonical
    loader: supplying one is rejected rather than silently ignored."""
    with pytest.raises(ProjectManifestValidationError):
        ProjectEntityRef(entity_kind=kind, stable_id="x", source_ref="some/path.json")


# ---------------------------------------------------------------------------
# ProjectManifest construction validation
# ---------------------------------------------------------------------------


def test_valid_manifest_construction():
    manifest = _manifest()
    assert manifest.project_id == "demo_project"
    assert len(manifest.entities) == 4


def test_invalid_project_id_rejected():
    with pytest.raises(ProjectManifestValidationError):
        _manifest(project_id="Not-A-Slug")


def test_empty_project_id_rejected():
    with pytest.raises(ProjectManifestValidationError):
        _manifest(project_id="")


def test_duplicate_stable_ids_rejected():
    with pytest.raises(ProjectManifestValidationError):
        _manifest(
            entities=(
                ProjectEntityRef(entity_kind=LOCATION, stable_id="gym"),
                ProjectEntityRef(entity_kind=LOCATION, stable_id="gym"),
            )
        )


def test_same_stable_id_different_kind_is_not_a_duplicate():
    """Identity is (entity_kind, stable_id); the same string under two kinds
    is not ambiguous."""
    manifest = _manifest(
        entities=(
            ProjectEntityRef(entity_kind=LOCATION, stable_id="shared_id"),
            ProjectEntityRef(entity_kind=MEDIA_ASSET, stable_id="shared_id"),
        )
    )
    assert len(manifest.entities) == 2


# ---------------------------------------------------------------------------
# Deterministic serialization
# ---------------------------------------------------------------------------


def test_serialization_is_deterministic_regardless_of_insertion_order():
    manifest_a = _manifest()
    manifest_b = _manifest(entities=tuple(reversed(_manifest().entities)))
    assert serialize_manifest(manifest_a) == serialize_manifest(manifest_b)


def test_serialize_manifest_ends_with_newline_and_is_valid_json():
    text = serialize_manifest(_manifest())
    assert text.endswith("\n")
    json.loads(text)


def test_parse_manifest_round_trip_preserves_content():
    manifest = _manifest()
    text = serialize_manifest(manifest)
    parsed = parse_manifest(text)
    assert parsed.to_dict() == manifest.to_dict()


# ---------------------------------------------------------------------------
# Fail-closed parsing
# ---------------------------------------------------------------------------


def test_parse_manifest_rejects_malformed_json():
    with pytest.raises(ProjectManifestError):
        parse_manifest("{ not json")


def test_parse_manifest_rejects_non_object_root():
    with pytest.raises(ProjectManifestValidationError):
        parse_manifest("[]")


def test_parse_manifest_rejects_wrong_schema_version():
    with pytest.raises(ProjectManifestValidationError):
        parse_manifest(json.dumps({"schema_version": "wrong/0.0", "project_id": "x", "entities": []}))


def test_parse_manifest_rejects_missing_required_field():
    with pytest.raises(ProjectManifestValidationError):
        parse_manifest(json.dumps({"schema_version": PROJECT_MANIFEST_SCHEMA_VERSION, "entities": []}))


def test_parse_manifest_rejects_non_list_entities():
    with pytest.raises(ProjectManifestValidationError):
        parse_manifest(
            json.dumps(
                {
                    "schema_version": PROJECT_MANIFEST_SCHEMA_VERSION,
                    "project_id": "demo_project",
                    "entities": "not-a-list",
                }
            )
        )


# ---------------------------------------------------------------------------
# Save/load round-trip (atomic write)
# ---------------------------------------------------------------------------


def test_load_missing_manifest_raises_not_found(tmp_path):
    with pytest.raises(ProjectManifestNotFoundError):
        load_manifest(tmp_path / "missing.project.json")


def test_save_then_load_round_trip(tmp_path):
    manifest = _manifest()
    path = tmp_path / "demo_project.project.json"
    save_manifest(path, manifest)

    assert path.is_file()
    loaded = load_manifest(path)
    assert loaded.to_dict() == manifest.to_dict()
    assert validate_manifest(path) == []


def test_save_manifest_leaves_no_temp_file_behind(tmp_path):
    manifest = _manifest()
    path = tmp_path / "demo_project.project.json"
    save_manifest(path, manifest)

    leftovers = [p for p in tmp_path.iterdir() if p.name.startswith(".workspace_project_")]
    assert leftovers == []


def test_save_manifest_overwrites_atomically(tmp_path):
    path = tmp_path / "demo_project.project.json"
    save_manifest(path, _manifest())
    replacement = _manifest(
        entities=(ProjectEntityRef(entity_kind=LOCATION, stable_id="yoga_hall"),)
    )
    save_manifest(path, replacement)

    loaded = load_manifest(path)
    assert loaded.to_dict() == replacement.to_dict()


def test_validate_manifest_reports_missing_file(tmp_path):
    errors = validate_manifest(tmp_path / "missing.project.json")
    assert errors == ["manifest does not exist"]


def test_validate_manifest_reports_malformed_file(tmp_path):
    path = tmp_path / "bad.project.json"
    path.write_text("{ not json", encoding="utf-8")
    errors = validate_manifest(path)
    assert len(errors) == 1
