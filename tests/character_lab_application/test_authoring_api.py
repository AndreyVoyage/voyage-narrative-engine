"""S2 CREATE / IMPORT / SAVE / NEW VERSION application API tests."""

from __future__ import annotations

import copy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from services.character_authoring import (
    CharacterAuthoringStorageError,
    CharacterAuthoringStore,
    LifecycleState,
    compute_snapshot_hash,
)
from services.character_canon_bridge import CanonReference, Provenance
from services.character_lab_application import (
    AUTHORING_ALREADY_EXISTS,
    AUTHORING_NOT_EDITABLE,
    AUTHORING_NOT_FOUND,
    AUTHORING_PERSISTENCE_FAILED,
    AUTHORING_UNAVAILABLE,
    AUTHORING_VALIDATION_FAILED,
    IMMUTABLE_PERSISTENCE_FAILED,
    IMPORT_REQUIRES_AUTHORING_COMPLETION,
    IMPORT_SOURCE_UNAVAILABLE,
    CharacterLabApplicationConfig,
    CharacterLabApplicationError,
    CharacterLabApplicationService,
)
from tests.character_canon_bridge.conftest import make_status


def semantic(name: str = "Atlas") -> dict:
    return {
        "identity": {"display_name": name},
        "biography": f"Biography for {name}.",
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
        "visual_identity": {"reference_asset_id": "portrait-1"},
    }


def build_service(
    tmp_path,
    *,
    with_canon: bool = True,
    canon_import_reader=None,
    canon_semantic_mapper=None,
):
    authoring_root = tmp_path / "authoring"
    canon_root = tmp_path / "canon" if with_canon else None
    config = CharacterLabApplicationConfig(
        character_canon_root=canon_root,
        character_authoring_root=authoring_root,
    )
    kwargs = {}
    if canon_import_reader is not None:
        kwargs["canon_import_reader"] = canon_import_reader
    if canon_semantic_mapper is not None:
        kwargs["canon_semantic_mapper"] = canon_semantic_mapper
    return (
        CharacterLabApplicationService(config, **kwargs),
        CharacterAuthoringStore(authoring_root),
        canon_root,
    )


def create_initial(service, *, name="Atlas", character_id="atlas"):
    return service.create_character(
        character_id=character_id,
        version_id="version-v1",
        revision_id="revision-r1",
        version_label="Version 1",
        semantic=semantic(name),
    )


def revision_path(store, character_id, version_id, revision_id):
    return (
        store.root
        / character_id
        / "versions"
        / version_id
        / "revisions"
        / f"{revision_id}.json"
    )


def test_create_character_persists_one_draft_version_and_revision(tmp_path):
    service, store, _ = build_service(tmp_path)

    result = create_initial(service)

    assert result.operation == "CREATE"
    assert result.lifecycle_state == LifecycleState.DRAFT.value
    assert store.list_character_ids() == ["atlas"]
    assert store.list_versions("atlas") == ["version-v1"]
    assert store.list_revisions("atlas", "version-v1") == ["revision-r1"]
    record = store.load_revision("atlas", "version-v1", "revision-r1")
    assert result.character_id == record.character_id
    assert result.version_id == record.version_id
    assert result.revision_id == record.revision_id
    assert result.snapshot_hash == record.snapshot_hash
    assert result.snapshot_hash == compute_snapshot_hash(record.semantic)
    assert record.lifecycle_state is LifecycleState.DRAFT
    assert store.read_character_pointer("atlas").selected_version_id == "version-v1"
    assert (
        store.read_version_pointer("atlas", "version-v1").selected_revision_id
        == "revision-r1"
    )


def test_duplicate_character_creation_fails_without_overwrite(tmp_path):
    service, store, _ = build_service(tmp_path)
    create_initial(service)
    path = revision_path(store, "atlas", "version-v1", "revision-r1")
    original = path.read_bytes()

    with pytest.raises(CharacterLabApplicationError) as excinfo:
        create_initial(service, name="Replacement")

    assert excinfo.value.code == AUTHORING_ALREADY_EXISTS
    assert path.read_bytes() == original
    assert store.list_versions("atlas") == ["version-v1"]
    assert store.list_revisions("atlas", "version-v1") == ["revision-r1"]


@pytest.mark.parametrize(
    "character_id,payload",
    [
        ("Atlas", semantic()),
        ("atlas", {"identity": {"display_name": "Incomplete"}}),
    ],
)
def test_invalid_create_input_leaves_no_partial_character(
    tmp_path, character_id, payload
):
    service, store, _ = build_service(tmp_path)

    with pytest.raises(CharacterLabApplicationError) as excinfo:
        service.create_character(
            character_id=character_id,
            version_id="version-v1",
            revision_id="revision-r1",
            version_label="Version 1",
            semantic=payload,
        )

    assert excinfo.value.code == AUTHORING_VALIDATION_FAILED
    assert store.list_character_ids() == []


def test_save_adds_revision_in_same_version_and_preserves_old_bytes(tmp_path):
    service, store, _ = build_service(tmp_path)
    first = create_initial(service)
    old_path = revision_path(store, "atlas", "version-v1", "revision-r1")
    old_bytes = old_path.read_bytes()
    updated = semantic("Atlas Updated")

    second = service.save_character(
        character_id="atlas",
        version_id="version-v1",
        revision_id="revision-r2",
        semantic=updated,
    )

    assert second.operation == "SAVE"
    assert second.character_id == first.character_id
    assert second.version_id == first.version_id
    assert second.revision_id != first.revision_id
    assert store.list_versions("atlas") == ["version-v1"]
    assert store.list_revisions("atlas", "version-v1") == [
        "revision-r1",
        "revision-r2",
    ]
    assert old_path.read_bytes() == old_bytes
    assert store.load_revision("atlas", "version-v1", "revision-r1").snapshot_hash == first.snapshot_hash
    assert (
        store.load_revision("atlas", "version-v1", "revision-r2")
        .semantic.to_dict()["identity"]["display_name"]
        == "Atlas Updated"
    )
    assert (
        store.read_version_pointer("atlas", "version-v1").selected_revision_id
        == "revision-r2"
    )


@pytest.mark.parametrize(
    "state", [LifecycleState.DRAFT, LifecycleState.CHANGES_REQUESTED]
)
def test_save_is_allowed_in_editable_lifecycle_states(tmp_path, state):
    service, store, _ = build_service(tmp_path)
    create_initial(service)
    pointer = store.read_version_pointer("atlas", "version-v1")
    store.update_version_pointer(replace(pointer, lifecycle_state=state))

    result = service.save_character(
        character_id="atlas",
        version_id="version-v1",
        revision_id="revision-r2",
        semantic=semantic("Edited"),
    )

    assert result.lifecycle_state == state.value
    assert (
        store.load_revision("atlas", "version-v1", "revision-r2").lifecycle_state
        is state
    )


@pytest.mark.parametrize(
    "state",
    [
        LifecycleState.PENDING_APPROVAL,
        LifecycleState.APPROVED_AS_CANON,
        LifecycleState.WITHDRAWN,
    ],
)
def test_save_rejects_non_editable_lifecycle_states(tmp_path, state):
    service, store, _ = build_service(tmp_path)
    create_initial(service)
    pointer = store.read_version_pointer("atlas", "version-v1")
    store.update_version_pointer(replace(pointer, lifecycle_state=state))

    with pytest.raises(CharacterLabApplicationError) as excinfo:
        service.save_character(
            character_id="atlas",
            version_id="version-v1",
            revision_id="revision-r2",
            semantic=semantic("Rejected edit"),
        )

    assert excinfo.value.code == AUTHORING_NOT_EDITABLE
    assert store.list_revisions("atlas", "version-v1") == ["revision-r1"]
    assert store.read_version_pointer("atlas", "version-v1").selected_revision_id == "revision-r1"


def test_unknown_version_save_is_normalized(tmp_path):
    service, store, _ = build_service(tmp_path)
    store.create_character("atlas")

    with pytest.raises(CharacterLabApplicationError) as excinfo:
        service.save_character(
            character_id="atlas",
            version_id="missing-v1",
            revision_id="revision-r1",
            semantic=semantic(),
        )

    assert excinfo.value.code == AUTHORING_NOT_FOUND


def test_duplicate_revision_save_is_immutable_failure(tmp_path):
    service, store, _ = build_service(tmp_path)
    create_initial(service)
    path = revision_path(store, "atlas", "version-v1", "revision-r1")
    original = path.read_bytes()

    with pytest.raises(CharacterLabApplicationError) as excinfo:
        service.save_character(
            character_id="atlas",
            version_id="version-v1",
            revision_id="revision-r1",
            semantic=semantic("Different"),
        )

    assert excinfo.value.code == IMMUTABLE_PERSISTENCE_FAILED
    assert path.read_bytes() == original


def test_pointer_failure_leaves_new_immutable_revision_recoverable(
    tmp_path, monkeypatch
):
    service, store, _ = build_service(tmp_path)
    create_initial(service)
    application_store = service._authoring._store

    def fail_pointer_update(pointer):
        raise CharacterAuthoringStorageError("simulated pointer failure")

    monkeypatch.setattr(application_store, "update_version_pointer", fail_pointer_update)

    with pytest.raises(CharacterLabApplicationError) as excinfo:
        service.save_character(
            character_id="atlas",
            version_id="version-v1",
            revision_id="revision-r2",
            semantic=semantic("Recoverable"),
        )

    assert excinfo.value.code == AUTHORING_PERSISTENCE_FAILED
    assert excinfo.value.details["revision_persisted"] is True
    assert store.load_revision("atlas", "version-v1", "revision-r2").revision_id == "revision-r2"
    assert store.read_version_pointer("atlas", "version-v1").selected_revision_id == "revision-r1"


def test_new_version_is_explicit_draft_and_does_not_change_v1(tmp_path):
    service, store, _ = build_service(tmp_path)
    first = create_initial(service)
    v1_pointer = store.read_version_pointer("atlas", "version-v1")
    v1_path = revision_path(store, "atlas", "version-v1", "revision-r1")
    v1_bytes = v1_path.read_bytes()

    second = service.create_new_version(
        character_id="atlas",
        version_id="version-v2",
        revision_id="revision-v2-r1",
        version_label="Version 2",
        semantic=semantic("Atlas V2"),
    )

    assert second.operation == "NEW_VERSION"
    assert second.character_id == first.character_id
    assert second.version_id == "version-v2"
    assert second.lifecycle_state == LifecycleState.DRAFT.value
    assert store.list_versions("atlas") == ["version-v1", "version-v2"]
    assert store.read_version_pointer("atlas", "version-v1") == v1_pointer
    assert v1_path.read_bytes() == v1_bytes
    assert store.read_character_pointer("atlas").selected_version_id == "version-v2"

    service.save_character(
        character_id="atlas",
        version_id="version-v2",
        revision_id="revision-v2-r2",
        semantic=semantic("Atlas V2 saved"),
    )
    assert store.list_revisions("atlas", "version-v1") == ["revision-r1"]
    assert store.list_revisions("atlas", "version-v2") == [
        "revision-v2-r1",
        "revision-v2-r2",
    ]


def test_new_version_collision_fails_without_changing_existing_version(tmp_path):
    service, store, _ = build_service(tmp_path)
    create_initial(service)
    original_pointer = store.read_version_pointer("atlas", "version-v1")
    path = revision_path(store, "atlas", "version-v1", "revision-r1")
    original_bytes = path.read_bytes()

    with pytest.raises(CharacterLabApplicationError) as excinfo:
        service.create_new_version(
            character_id="atlas",
            version_id="version-v1",
            revision_id="revision-r2",
            version_label="Colliding version",
            semantic=semantic("Collision"),
        )

    assert excinfo.value.code == AUTHORING_ALREADY_EXISTS
    assert store.list_versions("atlas") == ["version-v1"]
    assert store.read_version_pointer("atlas", "version-v1") == original_pointer
    assert path.read_bytes() == original_bytes


class FakeDirectCanonReader:
    def __init__(self, source_semantic):
        self.source_semantic = source_semantic
        self.calls = []
        self.writes = 0

    def __call__(self, root, character_id, usage_context):
        self.calls.append((root, character_id, usage_context))
        return SimpleNamespace(
            character_id=character_id,
            status="APPROVED_AS_CANON",
            active_version="canon-v7",
            references=(
                CanonReference(key="portrait", path="refs/synthetic-alpha.png"),
            ),
            content_hash="c" * 64,
            provenance=Provenance(
                source_kind="synthetic_character_canon",
                source_ref="AI_CHARACTERS/SYNTHETIC_ALPHA/source.json",
                source_hash="d" * 64,
            ),
            authoring_semantic=self.source_semantic,
        )


def test_import_success_creates_local_draft_and_retains_provenance(tmp_path):
    source_semantic = semantic("Synthetic Alpha")
    source_before = copy.deepcopy(source_semantic)
    reader = FakeDirectCanonReader(source_semantic)
    service, store, canon_root = build_service(
        tmp_path,
        canon_import_reader=reader,
        canon_semantic_mapper=lambda snapshot: snapshot.authoring_semantic,
    )

    result = service.import_character(
        source_character_id="SYNTHETIC_ALPHA",
        character_id="synthetic-alpha",
        version_id="version-v1",
        revision_id="revision-r1",
        version_label="Imported draft",
    )

    assert reader.calls == [(canon_root, "SYNTHETIC_ALPHA", "authoring")]
    assert reader.writes == 0
    assert source_semantic == source_before
    assert result.operation == "IMPORT"
    assert result.lifecycle_state == LifecycleState.DRAFT.value
    assert result.source_character_id == "SYNTHETIC_ALPHA"
    assert result.source_revision_id is None
    assert result.source_snapshot_hash == "c" * 64
    assert result.source_ref == "AI_CHARACTERS/SYNTHETIC_ALPHA/source.json"
    record = store.load_revision(
        "synthetic-alpha", "version-v1", "revision-r1"
    )
    assert record.lifecycle_state is LifecycleState.DRAFT
    assert record.snapshot_hash == compute_snapshot_hash(record.semantic)
    provenance = record.workflow_metadata["import_provenance"]
    assert provenance["source_character_id"] == "SYNTHETIC_ALPHA"
    assert provenance["source_content_hash"] == "c" * 64
    assert provenance["source_hash"] == "d" * 64
    assert "publication" not in record.workflow_metadata
    assert "activation" not in record.workflow_metadata


def test_actual_bridge_incomplete_import_fails_without_partial_persistence(tmp_path):
    service, store, canon_root = build_service(tmp_path)
    make_status(canon_root, "SYNTHETIC_BETA", "APPROVED_AS_CANON")
    source_path = (
        canon_root
        / "AI_CHARACTERS"
        / "SYNTHETIC_BETA"
        / "10_notes"
        / "SYNTHETIC_BETA_REFERENCE_PRESETS.json"
    )
    source_before = source_path.read_bytes()

    with pytest.raises(CharacterLabApplicationError) as excinfo:
        service.import_character(
            source_character_id="SYNTHETIC_BETA",
            character_id="synthetic-beta",
            version_id="version-v1",
            revision_id="revision-r1",
            version_label="Incomplete import",
        )

    assert excinfo.value.code == IMPORT_REQUIRES_AUTHORING_COMPLETION
    assert "biography" in excinfo.value.details["missing_fields"]
    assert "psychology" in excinfo.value.details["missing_fields"]
    assert source_path.read_bytes() == source_before
    assert store.list_character_ids() == []


def test_direct_mapping_missing_required_field_reports_field_and_persists_nothing(
    tmp_path,
):
    incomplete = semantic("Synthetic Gamma")
    del incomplete["biography"]
    reader = FakeDirectCanonReader(incomplete)
    service, store, _ = build_service(
        tmp_path,
        canon_import_reader=reader,
        canon_semantic_mapper=lambda snapshot: snapshot.authoring_semantic,
    )

    with pytest.raises(CharacterLabApplicationError) as excinfo:
        service.import_character(
            source_character_id="SYNTHETIC_GAMMA",
            character_id="synthetic-gamma",
            version_id="version-v1",
            revision_id="revision-r1",
            version_label="Incomplete import",
        )

    assert excinfo.value.code == IMPORT_REQUIRES_AUTHORING_COMPLETION
    assert excinfo.value.details["missing_fields"] == ("biography",)
    assert store.list_character_ids() == []


def test_import_unavailable_is_normalized_and_persists_nothing(tmp_path):
    service, store, _ = build_service(tmp_path, with_canon=False)

    with pytest.raises(CharacterLabApplicationError) as excinfo:
        service.import_character(
            source_character_id="UNAVAILABLE_SOURCE",
            character_id="local-draft",
            version_id="version-v1",
            revision_id="revision-r1",
            version_label="Unavailable",
        )

    assert excinfo.value.code == IMPORT_SOURCE_UNAVAILABLE
    assert store.list_character_ids() == []


def test_import_rejects_invalid_local_id_before_reading_canon(tmp_path):
    reader = FakeDirectCanonReader(semantic("Synthetic Delta"))
    service, store, _ = build_service(
        tmp_path,
        canon_import_reader=reader,
        canon_semantic_mapper=lambda snapshot: snapshot.authoring_semantic,
    )

    with pytest.raises(CharacterLabApplicationError) as excinfo:
        service.import_character(
            source_character_id="SYNTHETIC_DELTA",
            character_id="Synthetic-Delta",
            version_id="version-v1",
            revision_id="revision-r1",
            version_label="Invalid local id",
        )

    assert excinfo.value.code == AUTHORING_VALIDATION_FAILED
    assert reader.calls == []
    assert store.list_character_ids() == []


def test_authoring_mutation_without_store_configuration_is_normalized(tmp_path):
    service = CharacterLabApplicationService(
        CharacterLabApplicationConfig(character_canon_root=tmp_path / "canon")
    )

    with pytest.raises(CharacterLabApplicationError) as excinfo:
        create_initial(service)

    assert excinfo.value.code == AUTHORING_UNAVAILABLE


def test_authoring_api_contains_no_kira_specific_production_logic():
    source = Path("services/character_lab_application/authoring.py").read_text(
        encoding="utf-8"
    ).upper()
    assert "KIRA" not in source
    assert "PUBLISH" not in source
    assert "ACTIVATE" not in source
