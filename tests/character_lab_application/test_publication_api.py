"""Application-facade tests for explicit Character Publication V1."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from services.character_authoring import CharacterAuthoringStore, LifecycleState
from services.character_lab_application import (
    AUTHORING_NOT_FOUND,
    PUBLICATION_NOT_APPROVED,
    PUBLICATION_STALE_REVISION,
    PUBLICATION_STALE_SNAPSHOT,
    PUBLICATION_VALIDATION_FAILED,
    CharacterLabApplicationConfig,
    CharacterLabApplicationError,
    CharacterLabApplicationService,
    CharacterPublicationResult,
)


def semantic(*, visual_identity=None):
    return {
        "identity": {"display_name": "Atlas"},
        "biography": "Biography.",
        "psychology": {
            "personality": ["curious"],
            "behavioral_traits": ["observant"],
            "emotional_tendencies": ["reflective"],
            "goals_motivations": ["understand"],
        },
        "speech": {"speech_style": "measured", "register": None},
        "character_relations": {
            "relational_tendencies": ["builds trust"],
            "attachment_traits": ["consistent"],
        },
        "appearance": {"descriptors": ["dark hair"]},
        "boundaries": {"principles": ["respects refusal"]},
        "visual_identity": {} if visual_identity is None else visual_identity,
    }


def build_service(tmp_path, *, visual_identity=None):
    root = tmp_path / "character_authoring"
    service = CharacterLabApplicationService(
        CharacterLabApplicationConfig(character_authoring_root=root)
    )
    created = service.create_character(
        character_id="atlas",
        version_id="version-v1",
        revision_id="revision-r1",
        version_label="Version 1",
        semantic=semantic(visual_identity=visual_identity),
    )
    return service, CharacterAuthoringStore(root), created


def approve(service, created):
    service.submit_for_approval(
        character_id=created.character_id,
        version_id=created.version_id,
        revision_id=created.revision_id,
        snapshot_hash=created.snapshot_hash,
    )
    service.approve_as_canon(
        character_id=created.character_id,
        version_id=created.version_id,
        revision_id=created.revision_id,
        snapshot_hash=created.snapshot_hash,
    )


def call_publish(service, created, **overrides):
    return service.publish_character_version(
        character_id=overrides.get("character_id", created.character_id),
        version_id=overrides.get("version_id", created.version_id),
        revision_id=overrides.get("revision_id", created.revision_id),
        snapshot_hash=overrides.get("snapshot_hash", created.snapshot_hash),
    )


def test_facade_publishes_path_free_result_under_sibling_root(tmp_path):
    service, _store, created = build_service(tmp_path)
    approve(service, created)

    result = call_publish(service, created)

    assert isinstance(result, CharacterPublicationResult)
    path = tmp_path / "character_authoring_publication" / "atlas" / result.package_hash
    assert path.is_file()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["provenance"]["source_snapshot_hash"] == created.snapshot_hash


def test_facade_maps_not_approved(tmp_path):
    service, _store, created = build_service(tmp_path)

    with pytest.raises(CharacterLabApplicationError) as excinfo:
        call_publish(service, created)

    assert excinfo.value.code == PUBLICATION_NOT_APPROVED


def test_facade_maps_stale_revision_and_snapshot(tmp_path):
    service, _store, created = build_service(tmp_path)
    approve(service, created)

    with pytest.raises(CharacterLabApplicationError) as revision_error:
        call_publish(service, created, revision_id="revision-r2")
    with pytest.raises(CharacterLabApplicationError) as snapshot_error:
        call_publish(service, created, snapshot_hash="f" * 64)

    assert revision_error.value.code == PUBLICATION_STALE_REVISION
    assert snapshot_error.value.code == PUBLICATION_STALE_SNAPSHOT


def test_facade_maps_missing_source_to_existing_authoring_not_found(tmp_path):
    service, _store, created = build_service(tmp_path)

    with pytest.raises(CharacterLabApplicationError) as excinfo:
        call_publish(service, created, character_id="missing")

    assert excinfo.value.code == AUTHORING_NOT_FOUND


def test_facade_maps_non_empty_visual_identity_to_validation_failed(tmp_path):
    service, _store, created = build_service(
        tmp_path, visual_identity={"reference_asset_id": "portrait-1"}
    )
    approve(service, created)

    with pytest.raises(CharacterLabApplicationError) as excinfo:
        call_publish(service, created)

    assert excinfo.value.code == PUBLICATION_VALIDATION_FAILED
