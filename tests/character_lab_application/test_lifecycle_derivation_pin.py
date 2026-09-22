"""S3 lifecycle, approved derivation, and exact session-pin tests."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from services.character_authoring import (
    CharacterAuthoringStorageError,
    CharacterAuthoringStore,
    LifecycleState,
)
from services.character_lab_application import (
    AUTHORING_ALREADY_EXISTS,
    AUTHORING_INVALID_LIFECYCLE_TRANSITION,
    AUTHORING_NOT_EDITABLE,
    AUTHORING_NOT_FOUND,
    AUTHORING_PERSISTENCE_FAILED,
    AUTHORING_STALE_REVISION,
    AUTHORING_STALE_SNAPSHOT,
    AUTHORING_VALIDATION_FAILED,
    DERIVATION_SOURCE_NOT_APPROVED,
    CharacterLabApplicationConfig,
    CharacterLabApplicationError,
    CharacterLabApplicationService,
    CharacterSessionPin,
)


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


def build_service(tmp_path):
    authoring_root = tmp_path / "authoring"
    service = CharacterLabApplicationService(
        CharacterLabApplicationConfig(character_authoring_root=authoring_root)
    )
    return service, CharacterAuthoringStore(authoring_root)


def create_initial(service, *, character_id="atlas", name="Atlas"):
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


def submit(service, result):
    return service.submit_for_approval(
        character_id=result.character_id,
        version_id=result.version_id,
        revision_id=result.revision_id,
        snapshot_hash=result.snapshot_hash,
    )


def approve(service, result):
    submit(service, result)
    return service.approve_as_canon(
        character_id=result.character_id,
        version_id=result.version_id,
        revision_id=result.revision_id,
        snapshot_hash=result.snapshot_hash,
    )


def test_submit_draft_freezes_exact_selected_revision(tmp_path):
    service, store = build_service(tmp_path)
    created = create_initial(service)
    path = revision_path(store, "atlas", "version-v1", "revision-r1")
    before = path.read_bytes()
    semantic_before = store.load_revision(
        "atlas", "version-v1", "revision-r1"
    ).semantic.to_dict()

    result = submit(service, created)

    pointer = store.read_version_pointer("atlas", "version-v1")
    record = store.load_revision("atlas", "version-v1", "revision-r1")
    assert result.operation == "SUBMIT_FOR_APPROVAL"
    assert result.lifecycle_state == LifecycleState.PENDING_APPROVAL.value
    assert (result.character_id, result.version_id, result.revision_id) == (
        "atlas",
        "version-v1",
        "revision-r1",
    )
    assert result.snapshot_hash == created.snapshot_hash
    assert pointer.lifecycle_state is LifecycleState.PENDING_APPROVAL
    assert pointer.selected_revision_id == "revision-r1"
    assert path.read_bytes() == before
    assert record.semantic.to_dict() == semantic_before
    assert record.snapshot_hash == created.snapshot_hash


def test_submit_changes_requested_is_allowed_and_preserves_revision(tmp_path):
    service, store = build_service(tmp_path)
    created = create_initial(service)
    submit(service, created)
    service.request_changes(
        character_id="atlas",
        version_id="version-v1",
        revision_id=created.revision_id,
        snapshot_hash=created.snapshot_hash,
    )
    path = revision_path(store, "atlas", "version-v1", "revision-r1")
    before = path.read_bytes()

    result = submit(service, created)

    assert result.lifecycle_state == LifecycleState.PENDING_APPROVAL.value
    assert path.read_bytes() == before


@pytest.mark.parametrize(
    "revision_id,snapshot_hash,error_code",
    [
        ("revision-other", None, AUTHORING_STALE_REVISION),
        (None, "f" * 64, AUTHORING_STALE_SNAPSHOT),
    ],
)
def test_submit_rejects_wrong_exact_identity(
    tmp_path, revision_id, snapshot_hash, error_code
):
    service, store = build_service(tmp_path)
    created = create_initial(service)

    with pytest.raises(CharacterLabApplicationError) as excinfo:
        service.submit_for_approval(
            character_id="atlas",
            version_id="version-v1",
            revision_id=revision_id or created.revision_id,
            snapshot_hash=snapshot_hash or created.snapshot_hash,
        )

    assert excinfo.value.code == error_code
    assert store.read_version_pointer(
        "atlas", "version-v1"
    ).lifecycle_state is LifecycleState.DRAFT


def test_submit_rejects_stale_revision_after_newer_save(tmp_path):
    service, store = build_service(tmp_path)
    first = create_initial(service)
    service.save_character(
        character_id="atlas",
        version_id="version-v1",
        revision_id="revision-r2",
        semantic=semantic("Atlas revised"),
    )

    with pytest.raises(CharacterLabApplicationError) as excinfo:
        submit(service, first)

    assert excinfo.value.code == AUTHORING_STALE_REVISION
    assert store.read_version_pointer(
        "atlas", "version-v1"
    ).lifecycle_state is LifecycleState.DRAFT


def test_lifecycle_transition_unknown_target_is_normalized(tmp_path):
    service, _ = build_service(tmp_path)

    with pytest.raises(CharacterLabApplicationError) as excinfo:
        service.submit_for_approval(
            character_id="missing",
            version_id="version-v1",
            revision_id="revision-r1",
            snapshot_hash="a" * 64,
        )

    assert excinfo.value.code == AUTHORING_NOT_FOUND


@pytest.mark.parametrize(
    "state",
    [
        LifecycleState.PENDING_APPROVAL,
        LifecycleState.APPROVED_AS_CANON,
        LifecycleState.WITHDRAWN,
    ],
)
def test_submit_rejects_illegal_source_lifecycle(tmp_path, state):
    service, store = build_service(tmp_path)
    created = create_initial(service)
    pointer = store.read_version_pointer("atlas", "version-v1")
    store.update_version_pointer(replace(pointer, lifecycle_state=state))

    with pytest.raises(CharacterLabApplicationError) as excinfo:
        submit(service, created)

    assert excinfo.value.code == AUTHORING_INVALID_LIFECYCLE_TRANSITION
    assert store.read_version_pointer("atlas", "version-v1").lifecycle_state is state


def test_request_changes_allows_save_and_resubmit_of_new_selection(tmp_path):
    service, store = build_service(tmp_path)
    first = create_initial(service)
    submit(service, first)
    old_path = revision_path(store, "atlas", "version-v1", "revision-r1")
    old_bytes = old_path.read_bytes()

    changed = service.request_changes(
        character_id="atlas",
        version_id="version-v1",
        revision_id=first.revision_id,
        snapshot_hash=first.snapshot_hash,
    )
    second = service.save_character(
        character_id="atlas",
        version_id="version-v1",
        revision_id="revision-r2",
        semantic=semantic("Atlas corrected"),
    )
    resubmitted = submit(service, second)

    assert changed.lifecycle_state == LifecycleState.CHANGES_REQUESTED.value
    assert resubmitted.revision_id == "revision-r2"
    assert resubmitted.snapshot_hash == second.snapshot_hash
    assert resubmitted.lifecycle_state == LifecycleState.PENDING_APPROVAL.value
    assert old_path.read_bytes() == old_bytes
    assert store.list_revisions("atlas", "version-v1") == [
        "revision-r1",
        "revision-r2",
    ]


def test_approve_pending_records_local_approval_without_external_write(tmp_path):
    service, store = build_service(tmp_path)
    created = create_initial(service)
    submit(service, created)
    path = revision_path(store, "atlas", "version-v1", "revision-r1")
    before = path.read_bytes()
    external_sentinel = tmp_path / "external-canon-sentinel.json"
    external_sentinel.write_bytes(b'{"unchanged":true}\n')
    external_before = external_sentinel.read_bytes()

    result = service.approve_as_canon(
        character_id="atlas",
        version_id="version-v1",
        revision_id=created.revision_id,
        snapshot_hash=created.snapshot_hash,
    )

    pointer = store.read_version_pointer("atlas", "version-v1")
    assert result.operation == "APPROVE_AS_CANON"
    assert result.lifecycle_state == LifecycleState.APPROVED_AS_CANON.value
    assert pointer.lifecycle_state is LifecycleState.APPROVED_AS_CANON
    assert pointer.selected_revision_id == "revision-r1"
    assert path.read_bytes() == before
    assert external_sentinel.read_bytes() == external_before


@pytest.mark.parametrize(
    "state",
    [
        LifecycleState.DRAFT,
        LifecycleState.CHANGES_REQUESTED,
        LifecycleState.WITHDRAWN,
    ],
)
def test_approve_rejects_non_pending_state(tmp_path, state):
    service, store = build_service(tmp_path)
    created = create_initial(service)
    if state is LifecycleState.CHANGES_REQUESTED:
        pointer = store.read_version_pointer("atlas", "version-v1")
        store.update_version_pointer(replace(pointer, lifecycle_state=state))

    with pytest.raises(CharacterLabApplicationError) as excinfo:
        service.approve_as_canon(
            character_id="atlas",
            version_id="version-v1",
            revision_id=created.revision_id,
            snapshot_hash=created.snapshot_hash,
        )

    assert excinfo.value.code == AUTHORING_INVALID_LIFECYCLE_TRANSITION


@pytest.mark.parametrize(
    "revision_id,snapshot_hash,error_code",
    [
        ("revision-other", None, AUTHORING_STALE_REVISION),
        (None, "e" * 64, AUTHORING_STALE_SNAPSHOT),
    ],
)
def test_approve_rejects_stale_revision_or_hash(
    tmp_path, revision_id, snapshot_hash, error_code
):
    service, store = build_service(tmp_path)
    created = create_initial(service)
    submit(service, created)

    with pytest.raises(CharacterLabApplicationError) as excinfo:
        service.approve_as_canon(
            character_id="atlas",
            version_id="version-v1",
            revision_id=revision_id or created.revision_id,
            snapshot_hash=snapshot_hash or created.snapshot_hash,
        )

    assert excinfo.value.code == error_code
    assert store.read_version_pointer(
        "atlas", "version-v1"
    ).lifecycle_state is LifecycleState.PENDING_APPROVAL


def test_double_approval_is_rejected(tmp_path):
    service, store = build_service(tmp_path)
    created = create_initial(service)
    approve(service, created)

    with pytest.raises(CharacterLabApplicationError) as excinfo:
        service.approve_as_canon(
            character_id="atlas",
            version_id="version-v1",
            revision_id=created.revision_id,
            snapshot_hash=created.snapshot_hash,
        )

    assert excinfo.value.code == AUTHORING_INVALID_LIFECYCLE_TRANSITION
    assert store.read_version_pointer(
        "atlas", "version-v1"
    ).lifecycle_state is LifecycleState.APPROVED_AS_CANON


@pytest.mark.parametrize(
    "failure",
    [
        CharacterAuthoringStorageError("simulated pointer failure"),
        OSError("simulated raw filesystem failure"),
    ],
)
def test_transition_pointer_failure_preserves_previous_workflow_state(
    tmp_path, monkeypatch, failure
):
    service, store = build_service(tmp_path)
    created = create_initial(service)
    path = revision_path(store, "atlas", "version-v1", "revision-r1")
    before = path.read_bytes()

    def fail_pointer_update(pointer):
        raise failure

    monkeypatch.setattr(
        service._authoring._store, "update_version_pointer", fail_pointer_update
    )

    with pytest.raises(CharacterLabApplicationError) as excinfo:
        submit(service, created)

    assert excinfo.value.code == AUTHORING_PERSISTENCE_FAILED
    assert store.read_version_pointer(
        "atlas", "version-v1"
    ).lifecycle_state is LifecycleState.DRAFT
    assert path.read_bytes() == before


@pytest.mark.parametrize("operation", ["request_changes", "withdraw_submission"])
@pytest.mark.parametrize(
    "state",
    [
        LifecycleState.DRAFT,
        LifecycleState.CHANGES_REQUESTED,
        LifecycleState.APPROVED_AS_CANON,
        LifecycleState.WITHDRAWN,
    ],
)
def test_pending_only_transitions_reject_every_other_source(
    tmp_path, operation, state
):
    service, store = build_service(tmp_path)
    created = create_initial(service)
    pointer = store.read_version_pointer("atlas", "version-v1")
    store.update_version_pointer(replace(pointer, lifecycle_state=state))

    with pytest.raises(CharacterLabApplicationError) as excinfo:
        getattr(service, operation)(
            character_id="atlas",
            version_id="version-v1",
            revision_id=created.revision_id,
            snapshot_hash=created.snapshot_hash,
        )

    assert excinfo.value.code == AUTHORING_INVALID_LIFECYCLE_TRANSITION
    assert store.read_version_pointer("atlas", "version-v1").lifecycle_state is state


def test_withdraw_is_terminal_and_preserves_revision(tmp_path):
    service, store = build_service(tmp_path)
    created = create_initial(service)
    submit(service, created)
    path = revision_path(store, "atlas", "version-v1", "revision-r1")
    before = path.read_bytes()

    result = service.withdraw_submission(
        character_id="atlas",
        version_id="version-v1",
        revision_id=created.revision_id,
        snapshot_hash=created.snapshot_hash,
    )

    assert result.lifecycle_state == LifecycleState.WITHDRAWN.value
    assert path.read_bytes() == before
    with pytest.raises(CharacterLabApplicationError) as save_error:
        service.save_character(
            character_id="atlas",
            version_id="version-v1",
            revision_id="revision-r2",
            semantic=semantic("Blocked"),
        )
    assert save_error.value.code == AUTHORING_NOT_EDITABLE
    with pytest.raises(CharacterLabApplicationError) as submit_error:
        submit(service, created)
    assert submit_error.value.code == AUTHORING_INVALID_LIFECYCLE_TRANSITION


def test_derive_approved_version_copies_exact_semantics_and_provenance(tmp_path):
    service, store = build_service(tmp_path)
    source = create_initial(service)
    approve(service, source)
    source_pointer = store.read_version_pointer("atlas", "version-v1")
    source_path = revision_path(store, "atlas", "version-v1", "revision-r1")
    source_bytes = source_path.read_bytes()
    source_record = store.load_revision("atlas", "version-v1", "revision-r1")

    derived = service.derive_version_from_approved(
        character_id="atlas",
        source_version_id="version-v1",
        source_revision_id="revision-r1",
        source_snapshot_hash=source.snapshot_hash,
        new_version_id="version-v2",
        new_revision_id="revision-v2-r1",
        new_version_label="Version 2",
    )

    derived_pointer = store.read_version_pointer("atlas", "version-v2")
    derived_record = store.load_revision("atlas", "version-v2", "revision-v2-r1")
    assert derived.operation == "DERIVE_VERSION"
    assert derived.lifecycle_state == LifecycleState.DRAFT.value
    assert derived.snapshot_hash == source.snapshot_hash
    assert derived_record.semantic.to_dict() == source_record.semantic.to_dict()
    assert (
        derived_pointer.derived_from_version_id,
        derived_pointer.derived_from_revision_id,
        derived_pointer.derived_from_snapshot_hash,
    ) == ("version-v1", "revision-r1", source.snapshot_hash)
    assert (
        derived_record.derived_from_version_id,
        derived_record.derived_from_revision_id,
        derived_record.derived_from_snapshot_hash,
    ) == ("version-v1", "revision-r1", source.snapshot_hash)
    assert derived_pointer.selected_revision_id == "revision-v2-r1"
    assert store.read_character_pointer("atlas").selected_version_id == "version-v2"
    assert store.read_version_pointer("atlas", "version-v1") == source_pointer
    assert source_path.read_bytes() == source_bytes

    edited = service.save_character(
        character_id="atlas",
        version_id="version-v2",
        revision_id="revision-v2-r2",
        semantic=semantic("Atlas V2 edited"),
    )
    assert edited.version_id == "version-v2"
    assert store.list_revisions("atlas", "version-v2") == [
        "revision-v2-r1",
        "revision-v2-r2",
    ]
    assert store.read_version_pointer("atlas", "version-v1") == source_pointer
    assert source_path.read_bytes() == source_bytes


@pytest.mark.parametrize(
    "state",
    [
        LifecycleState.DRAFT,
        LifecycleState.PENDING_APPROVAL,
        LifecycleState.CHANGES_REQUESTED,
        LifecycleState.WITHDRAWN,
    ],
)
def test_derive_rejects_non_approved_source_without_target_state(tmp_path, state):
    service, store = build_service(tmp_path)
    source = create_initial(service)
    pointer = store.read_version_pointer("atlas", "version-v1")
    store.update_version_pointer(replace(pointer, lifecycle_state=state))

    with pytest.raises(CharacterLabApplicationError) as excinfo:
        service.derive_version_from_approved(
            character_id="atlas",
            source_version_id="version-v1",
            source_revision_id="revision-r1",
            source_snapshot_hash=source.snapshot_hash,
            new_version_id="version-v2",
            new_revision_id="revision-v2-r1",
            new_version_label="Version 2",
        )

    assert excinfo.value.code == DERIVATION_SOURCE_NOT_APPROVED
    assert store.list_versions("atlas") == ["version-v1"]


@pytest.mark.parametrize(
    "revision_id,snapshot_hash,error_code",
    [
        ("revision-other", None, AUTHORING_STALE_REVISION),
        (None, "d" * 64, AUTHORING_STALE_SNAPSHOT),
    ],
)
def test_derive_rejects_stale_source_without_target_state(
    tmp_path, revision_id, snapshot_hash, error_code
):
    service, store = build_service(tmp_path)
    source = create_initial(service)
    approve(service, source)

    with pytest.raises(CharacterLabApplicationError) as excinfo:
        service.derive_version_from_approved(
            character_id="atlas",
            source_version_id="version-v1",
            source_revision_id=revision_id or source.revision_id,
            source_snapshot_hash=snapshot_hash or source.snapshot_hash,
            new_version_id="version-v2",
            new_revision_id="revision-v2-r1",
            new_version_label="Version 2",
        )

    assert excinfo.value.code == error_code
    assert store.list_versions("atlas") == ["version-v1"]


def test_derive_rejects_target_collision_without_mutating_existing_version(tmp_path):
    service, store = build_service(tmp_path)
    source = create_initial(service)
    approve(service, source)
    existing = service.create_new_version(
        character_id="atlas",
        version_id="version-v2",
        revision_id="revision-v2-existing",
        version_label="Existing Version 2",
        semantic=semantic("Existing V2"),
    )
    existing_path = revision_path(
        store, "atlas", "version-v2", "revision-v2-existing"
    )
    existing_bytes = existing_path.read_bytes()

    with pytest.raises(CharacterLabApplicationError) as excinfo:
        service.derive_version_from_approved(
            character_id="atlas",
            source_version_id="version-v1",
            source_revision_id="revision-r1",
            source_snapshot_hash=source.snapshot_hash,
            new_version_id="version-v2",
            new_revision_id="revision-v2-r1",
            new_version_label="Collision",
        )

    assert excinfo.value.code == AUTHORING_ALREADY_EXISTS
    assert store.read_version_pointer(
        "atlas", "version-v2"
    ).selected_revision_id == existing.revision_id
    assert existing_path.read_bytes() == existing_bytes


@pytest.mark.parametrize(
    "new_version_id,new_revision_id",
    [
        ("Version-V2", "revision-v2-r1"),
        ("version-v2", "Revision-V2-R1"),
    ],
)
def test_derive_invalid_target_identity_creates_no_target(
    tmp_path, new_version_id, new_revision_id
):
    service, store = build_service(tmp_path)
    source = create_initial(service)
    approve(service, source)

    with pytest.raises(CharacterLabApplicationError) as excinfo:
        service.derive_version_from_approved(
            character_id="atlas",
            source_version_id="version-v1",
            source_revision_id="revision-r1",
            source_snapshot_hash=source.snapshot_hash,
            new_version_id=new_version_id,
            new_revision_id=new_revision_id,
            new_version_label="Invalid target",
        )

    assert excinfo.value.code == AUTHORING_VALIDATION_FAILED
    assert store.list_versions("atlas") == ["version-v1"]


def test_session_pin_is_exact_and_does_not_mutate_state(tmp_path):
    service, store = build_service(tmp_path)
    created = create_initial(service)
    character_pointer = store.read_character_pointer("atlas")
    version_pointer = store.read_version_pointer("atlas", "version-v1")
    path = revision_path(store, "atlas", "version-v1", "revision-r1")
    before = path.read_bytes()

    pin = service.create_session_pin(
        character_id="atlas",
        version_id="version-v1",
        revision_id="revision-r1",
    )

    assert isinstance(pin, CharacterSessionPin)
    assert (pin.character_id, pin.version_id, pin.revision_id, pin.snapshot_hash) == (
        "atlas",
        "version-v1",
        "revision-r1",
        created.snapshot_hash,
    )
    assert store.read_character_pointer("atlas") == character_pointer
    assert store.read_version_pointer("atlas", "version-v1") == version_pointer
    assert path.read_bytes() == before


def test_session_pin_does_not_drift_after_new_save(tmp_path):
    service, _ = build_service(tmp_path)
    created = create_initial(service)
    pin = service.create_session_pin(
        character_id="atlas",
        version_id="version-v1",
        revision_id="revision-r1",
    )

    service.save_character(
        character_id="atlas",
        version_id="version-v1",
        revision_id="revision-r2",
        semantic=semantic("Atlas newer"),
    )

    assert pin == CharacterSessionPin(
        character_id="atlas",
        version_id="version-v1",
        revision_id="revision-r1",
        snapshot_hash=created.snapshot_hash,
    )


def test_session_pin_does_not_drift_after_derived_version(tmp_path):
    service, _ = build_service(tmp_path)
    source = create_initial(service)
    pin = service.create_session_pin(
        character_id="atlas",
        version_id="version-v1",
        revision_id="revision-r1",
    )
    approve(service, source)

    service.derive_version_from_approved(
        character_id="atlas",
        source_version_id="version-v1",
        source_revision_id="revision-r1",
        source_snapshot_hash=source.snapshot_hash,
        new_version_id="version-v2",
        new_revision_id="revision-v2-r1",
        new_version_label="Version 2",
    )

    assert pin.version_id == "version-v1"
    assert pin.revision_id == "revision-r1"
    assert pin.snapshot_hash == source.snapshot_hash


@pytest.mark.parametrize("missing", ["character", "version", "revision"])
def test_session_pin_rejects_unknown_identity(tmp_path, missing):
    service, store = build_service(tmp_path)
    if missing == "version":
        store.create_character("atlas")
    elif missing == "revision":
        create_initial(service)

    with pytest.raises(CharacterLabApplicationError) as excinfo:
        service.create_session_pin(
            character_id="missing" if missing == "character" else "atlas",
            version_id="missing-v1" if missing == "version" else "version-v1",
            revision_id=(
                "missing-r1" if missing == "revision" else "revision-r1"
            ),
        )

    assert excinfo.value.code == AUTHORING_NOT_FOUND


def test_lifecycle_and_pin_are_generic_for_unrelated_character(tmp_path):
    service, store = build_service(tmp_path)
    created = create_initial(service, character_id="zephyr", name="Zephyr")

    pending = submit(service, created)
    pin = service.create_session_pin(
        character_id="zephyr",
        version_id="version-v1",
        revision_id="revision-r1",
    )

    assert pending.character_id == "zephyr"
    assert pin.character_id == "zephyr"
    assert store.read_version_pointer(
        "zephyr", "version-v1"
    ).lifecycle_state is LifecycleState.PENDING_APPROVAL


def test_s3_production_module_has_no_character_specific_or_publish_logic():
    source = Path("services/character_lab_application/authoring.py").read_text(
        encoding="utf-8"
    ).upper()
    assert "KIRA" not in source
    assert "PUBLISH" not in source
    assert "ACTIVATE" not in source
