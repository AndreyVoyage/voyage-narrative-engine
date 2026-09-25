"""LAB-L1 approve_as_canon: explicit approver, Lab-captured time, write-once evidence."""

from __future__ import annotations

import json
import os
import re
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from services.character_authoring import (
    CharacterAuthoringStorageError,
    CharacterAuthoringStore,
    LifecycleState,
)
from services.character_lab_application import (
    APPROVAL_EVIDENCE_CONFLICT,
    AUTHORING_INVALID_LIFECYCLE_TRANSITION,
    AUTHORING_PERSISTENCE_FAILED,
    AUTHORING_STALE_REVISION,
    AUTHORING_STALE_SNAPSHOT,
    AUTHORING_VALIDATION_FAILED,
    CharacterLabApplicationConfig,
    CharacterLabApplicationError,
    CharacterLabApplicationService,
)

FIXED_MOMENT = datetime(2026, 3, 4, 5, 6, 7, 891011, tzinfo=timezone.utc)
FIXED_TEXT = "2026-03-04T05:06:07Z"


def semantic() -> dict:
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
        "visual_identity": {},
    }


class Clock:
    def __init__(self, *moments):
        self._moments = list(moments) or [FIXED_MOMENT]
        self.calls = 0

    def __call__(self):
        self.calls += 1
        index = min(self.calls, len(self._moments)) - 1
        return self._moments[index]


def build(tmp_path, clock=None):
    root = tmp_path / "authoring"
    service = CharacterLabApplicationService(
        CharacterLabApplicationConfig(character_authoring_root=root),
        approval_clock=clock or Clock(),
    )
    created = service.create_character(
        character_id="atlas",
        version_id="version-v1",
        revision_id="revision-r1",
        version_label="Version 1",
        semantic=semantic(),
    )
    return service, CharacterAuthoringStore(root), created


def submit(service, created):
    return service.submit_for_approval(
        character_id=created.character_id,
        version_id=created.version_id,
        revision_id=created.revision_id,
        snapshot_hash=created.snapshot_hash,
    )


def approve(service, created, **overrides):
    values = dict(
        character_id=created.character_id,
        version_id=created.version_id,
        revision_id=created.revision_id,
        snapshot_hash=created.snapshot_hash,
        decided_by="Ada Approver",
    )
    values.update(overrides)
    return service.approve_as_canon(**values)


def approvals_dir(store):
    return store.root / "atlas" / "versions" / "version-v1" / "approvals"


def evidence_path(store):
    return approvals_dir(store) / "revision-r1.json"


def state(store):
    return store.read_version_pointer("atlas", "version-v1").lifecycle_state


# -- happy path -------------------------------------------------------------


def test_approval_persists_exact_evidence_then_transitions(tmp_path):
    clock = Clock()
    service, store, created = build(tmp_path, clock)
    submit(service, created)

    result = approve(service, created)

    assert result.operation == "APPROVE_AS_CANON"
    assert result.lifecycle_state == LifecycleState.APPROVED_AS_CANON.value
    assert state(store) is LifecycleState.APPROVED_AS_CANON
    assert json.loads(evidence_path(store).read_text(encoding="utf-8")) == {
        "schema_version": "character_approval_evidence/1.0",
        "character_id": "atlas",
        "version_id": "version-v1",
        "revision_id": "revision-r1",
        "snapshot_hash": created.snapshot_hash,
        "decision": "HUMAN_APPROVED",
        "decided_by": "Ada Approver",
        "decided_at": FIXED_TEXT,
    }
    assert clock.calls == 1


def test_evidence_is_readable_through_store_api(tmp_path):
    service, store, created = build(tmp_path)
    submit(service, created)
    approve(service, created)

    evidence = store.load_approval_evidence("atlas", "version-v1", "revision-r1")

    assert evidence.decided_by == "Ada Approver"
    assert evidence.decided_at == FIXED_TEXT
    assert evidence.snapshot_hash == created.snapshot_hash


def test_decided_by_is_preserved_exactly(tmp_path):
    service, store, created = build(tmp_path)
    submit(service, created)

    approve(service, created, decided_by="  Андрей  Воевода ")

    assert store.load_approval_evidence(
        "atlas", "version-v1", "revision-r1"
    ).decided_by == "  Андрей  Воевода "


def test_default_clock_captures_real_utc_at_approval(tmp_path):
    root = tmp_path / "authoring"
    service = CharacterLabApplicationService(
        CharacterLabApplicationConfig(character_authoring_root=root)
    )
    created = service.create_character(
        character_id="atlas",
        version_id="version-v1",
        revision_id="revision-r1",
        version_label="Version 1",
        semantic=semantic(),
    )
    submit(service, created)
    store = CharacterAuthoringStore(root)

    before = datetime.now(timezone.utc).replace(microsecond=0)
    approve(service, created)
    after = datetime.now(timezone.utc)

    decided_at = store.load_approval_evidence(
        "atlas", "version-v1", "revision-r1"
    ).decided_at
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", decided_at)
    parsed = datetime.strptime(decided_at, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )
    assert before <= parsed <= after


def test_decided_at_is_not_derived_from_other_times(tmp_path):
    clock = Clock(datetime(2031, 1, 2, 3, 4, 5, tzinfo=timezone.utc))
    service, store, created = build(tmp_path, clock)
    submit(service, created)
    os.utime(store.root / "atlas" / "versions" / "version-v1" / "revisions"
             / "revision-r1.json", (1_000_000_000, 1_000_000_000))

    approve(service, created)

    assert store.load_approval_evidence(
        "atlas", "version-v1", "revision-r1"
    ).decided_at == "2031-01-02T03:04:05Z"


def test_approval_does_not_touch_revision_or_pointer_metadata(tmp_path):
    service, store, created = build(tmp_path)
    submit(service, created)
    revision_file = (
        store.root / "atlas" / "versions" / "version-v1" / "revisions"
        / "revision-r1.json"
    )
    revision_before = revision_file.read_bytes()
    metadata_before = dict(
        store.read_version_pointer("atlas", "version-v1").workflow_metadata
    )

    approve(service, created)

    assert revision_file.read_bytes() == revision_before
    pointer = store.read_version_pointer("atlas", "version-v1")
    assert dict(pointer.workflow_metadata) == metadata_before == {}
    assert sorted(p.name for p in approvals_dir(store).iterdir()) == [
        "revision-r1.json"
    ]


def test_approval_creates_no_release_vocabulary_or_publication_artifact(tmp_path):
    service, store, created = build(tmp_path)
    submit(service, created)

    approve(service, created)

    text = evidence_path(store).read_text(encoding="utf-8").lower()
    for forbidden in (
        "releaseid", "release_id", "aggregate", "packagehash", "package_hash",
        "domainhashes", "acceptancerecord", "canonical_current",
    ):
        assert forbidden not in text
    assert not (tmp_path / "character_authoring_publication").exists()
    assert not list(tmp_path.rglob("*.vchar"))


# -- decided_by validation --------------------------------------------------


def test_decided_by_is_a_required_argument(tmp_path):
    service, store, created = build(tmp_path)
    submit(service, created)

    with pytest.raises(TypeError):
        service.approve_as_canon(
            character_id="atlas",
            version_id="version-v1",
            revision_id=created.revision_id,
            snapshot_hash=created.snapshot_hash,
        )

    assert state(store) is LifecycleState.PENDING_APPROVAL
    assert not approvals_dir(store).exists()


@pytest.mark.parametrize(
    "value", [None, 0, b"Ada", ["Ada"], "", "   ", "\t\r\n", "Jose\u0301"]
)
def test_invalid_decided_by_fails_before_any_capture_or_write(tmp_path, value):
    clock = Clock()
    service, store, created = build(tmp_path, clock)
    submit(service, created)

    with pytest.raises(CharacterLabApplicationError) as excinfo:
        approve(service, created, decided_by=value)

    assert excinfo.value.code == AUTHORING_VALIDATION_FAILED
    assert clock.calls == 0
    assert state(store) is LifecycleState.PENDING_APPROVAL
    assert not approvals_dir(store).exists()


def test_decided_by_is_never_inferred_from_environment(tmp_path, monkeypatch):
    for name in ("USERNAME", "USER", "LOGNAME", "GIT_AUTHOR_NAME", "GIT_COMMITTER_NAME"):
        monkeypatch.setenv(name, "ENV_IDENTITY_SENTINEL")
    service, store, created = build(tmp_path)
    submit(service, created)

    approve(service, created, decided_by="Explicit Human")

    text = evidence_path(store).read_text(encoding="utf-8")
    assert "Explicit Human" in text
    assert "ENV_IDENTITY_SENTINEL" not in text


# -- ordering and failure boundaries ---------------------------------------


def test_failed_precondition_writes_no_evidence_and_never_reads_clock(tmp_path):
    clock = Clock()
    service, store, created = build(tmp_path, clock)

    # DRAFT is not approvable.
    with pytest.raises(CharacterLabApplicationError) as draft:
        approve(service, created)
    assert draft.value.code == AUTHORING_INVALID_LIFECYCLE_TRANSITION

    submit(service, created)
    with pytest.raises(CharacterLabApplicationError) as stale_revision:
        approve(service, created, revision_id="revision-other")
    with pytest.raises(CharacterLabApplicationError) as stale_snapshot:
        approve(service, created, snapshot_hash="e" * 64)

    assert stale_revision.value.code == AUTHORING_STALE_REVISION
    assert stale_snapshot.value.code == AUTHORING_STALE_SNAPSHOT
    assert clock.calls == 0
    assert state(store) is LifecycleState.PENDING_APPROVAL
    assert not approvals_dir(store).exists()


def test_evidence_persistence_failure_leaves_pointer_unchanged(tmp_path, monkeypatch):
    service, store, created = build(tmp_path)
    submit(service, created)

    def fail(_evidence):
        raise CharacterAuthoringStorageError("simulated evidence failure")

    monkeypatch.setattr(service._authoring._store, "persist_approval_evidence", fail)

    with pytest.raises(CharacterLabApplicationError) as excinfo:
        approve(service, created)

    assert excinfo.value.code == AUTHORING_PERSISTENCE_FAILED
    assert state(store) is LifecycleState.PENDING_APPROVAL
    assert not evidence_path(store).exists()


def test_evidence_is_persisted_before_the_pointer_transition(tmp_path, monkeypatch):
    service, store, created = build(tmp_path)
    submit(service, created)
    observed = {}
    original = service._authoring._store.update_version_pointer

    def spy(pointer):
        observed["evidence_existed"] = evidence_path(store).is_file()
        observed["target"] = pointer.lifecycle_state
        return original(pointer)

    monkeypatch.setattr(service._authoring._store, "update_version_pointer", spy)

    approve(service, created)

    assert observed == {
        "evidence_existed": True,
        "target": LifecycleState.APPROVED_AS_CANON,
    }


def test_pointer_failure_after_evidence_allows_exact_retry(tmp_path, monkeypatch):
    clock = Clock(
        datetime(2026, 3, 4, 5, 6, 7, tzinfo=timezone.utc),
        datetime(2027, 9, 9, 9, 9, 9, tzinfo=timezone.utc),
    )
    service, store, created = build(tmp_path, clock)
    submit(service, created)
    real_update = service._authoring._store.update_version_pointer

    def fail_once(pointer):
        raise CharacterAuthoringStorageError("simulated pointer failure")

    monkeypatch.setattr(service._authoring._store, "update_version_pointer", fail_once)

    with pytest.raises(CharacterLabApplicationError) as excinfo:
        approve(service, created)

    assert excinfo.value.code == AUTHORING_PERSISTENCE_FAILED
    assert excinfo.value.details["approval_evidence_persisted"] is True
    assert state(store) is LifecycleState.PENDING_APPROVAL
    first_bytes = evidence_path(store).read_bytes()

    monkeypatch.setattr(service._authoring._store, "update_version_pointer", real_update)
    retry = approve(service, created)

    assert retry.lifecycle_state == LifecycleState.APPROVED_AS_CANON.value
    assert state(store) is LifecycleState.APPROVED_AS_CANON
    assert evidence_path(store).read_bytes() == first_bytes
    assert store.load_approval_evidence(
        "atlas", "version-v1", "revision-r1"
    ).decided_at == "2026-03-04T05:06:07Z"
    assert clock.calls == 1


def test_retry_by_a_different_approver_fails_closed(tmp_path, monkeypatch):
    service, store, created = build(tmp_path)
    submit(service, created)
    real_update = service._authoring._store.update_version_pointer

    def fail(pointer):
        raise CharacterAuthoringStorageError("simulated pointer failure")

    monkeypatch.setattr(service._authoring._store, "update_version_pointer", fail)
    with pytest.raises(CharacterLabApplicationError):
        approve(service, created)
    original_bytes = evidence_path(store).read_bytes()
    monkeypatch.setattr(service._authoring._store, "update_version_pointer", real_update)

    with pytest.raises(CharacterLabApplicationError) as excinfo:
        approve(service, created, decided_by="Someone Else")

    assert excinfo.value.code == APPROVAL_EVIDENCE_CONFLICT
    assert state(store) is LifecycleState.PENDING_APPROVAL
    assert evidence_path(store).read_bytes() == original_bytes


def test_concurrent_writer_conflict_fails_closed(tmp_path, monkeypatch):
    service, store, created = build(tmp_path)
    submit(service, created)
    inner = service._authoring._store
    real_persist = inner.persist_approval_evidence

    def racing(evidence):
        # Another approver wins the write-once slot between our read and write.
        real_persist(replace(evidence, decided_by="Racing Approver"))
        return real_persist(evidence)

    monkeypatch.setattr(inner, "persist_approval_evidence", racing)

    with pytest.raises(CharacterLabApplicationError) as excinfo:
        approve(service, created)

    assert excinfo.value.code == APPROVAL_EVIDENCE_CONFLICT
    assert state(store) is LifecycleState.PENDING_APPROVAL
    assert store.load_approval_evidence(
        "atlas", "version-v1", "revision-r1"
    ).decided_by == "Racing Approver"


@pytest.mark.parametrize(
    "raw", ["not json", "{}", '{"schema_version": "character_approval_evidence/1.0"}']
)
def test_corrupt_existing_evidence_fails_closed_without_overwrite(tmp_path, raw):
    service, store, created = build(tmp_path)
    submit(service, created)
    approvals_dir(store).mkdir(parents=True)
    evidence_path(store).write_text(raw, encoding="utf-8")
    before = evidence_path(store).read_bytes()

    with pytest.raises(CharacterLabApplicationError) as excinfo:
        approve(service, created)

    assert excinfo.value.code == AUTHORING_PERSISTENCE_FAILED
    assert state(store) is LifecycleState.PENDING_APPROVAL
    assert evidence_path(store).read_bytes() == before


@pytest.mark.parametrize(
    "clock_value", [datetime(2026, 3, 4, 5, 6, 7), "2026-03-04T05:06:07Z", None]
)
def test_broken_clock_fails_closed_before_any_write(tmp_path, clock_value):
    service, store, created = build(tmp_path, lambda: clock_value)
    submit(service, created)

    with pytest.raises(CharacterLabApplicationError) as excinfo:
        approve(service, created)

    assert excinfo.value.code == AUTHORING_VALIDATION_FAILED
    assert state(store) is LifecycleState.PENDING_APPROVAL
    assert not evidence_path(store).exists()


def test_non_utc_clock_is_converted_to_utc(tmp_path):
    from datetime import timedelta

    moment = datetime(2026, 3, 4, 8, 6, 7, tzinfo=timezone(timedelta(hours=3)))
    service, store, created = build(tmp_path, Clock(moment))
    submit(service, created)

    approve(service, created)

    assert store.load_approval_evidence(
        "atlas", "version-v1", "revision-r1"
    ).decided_at == FIXED_TEXT


def test_double_approval_is_still_rejected_and_evidence_unchanged(tmp_path):
    clock = Clock()
    service, store, created = build(tmp_path, clock)
    submit(service, created)
    approve(service, created)
    before = evidence_path(store).read_bytes()

    with pytest.raises(CharacterLabApplicationError) as excinfo:
        approve(service, created, decided_by="Another Approver")

    assert excinfo.value.code == AUTHORING_INVALID_LIFECYCLE_TRANSITION
    assert evidence_path(store).read_bytes() == before
    assert clock.calls == 1


# -- historical approvals ---------------------------------------------------


def test_historical_approved_version_is_not_given_fabricated_evidence(tmp_path):
    service, store, created = build(tmp_path)
    pointer = store.read_version_pointer("atlas", "version-v1")
    store.update_version_pointer(
        replace(pointer, lifecycle_state=LifecycleState.APPROVED_AS_CANON)
    )

    with pytest.raises(CharacterLabApplicationError) as excinfo:
        approve(service, created)
    derived = service.derive_version_from_approved(
        character_id="atlas",
        source_version_id="version-v1",
        source_revision_id=created.revision_id,
        source_snapshot_hash=created.snapshot_hash,
        new_version_id="version-v2",
        new_revision_id="revision-r2",
        new_version_label="Version 2",
    )

    assert excinfo.value.code == AUTHORING_INVALID_LIFECYCLE_TRANSITION
    assert derived.lifecycle_state == LifecycleState.DRAFT.value
    assert state(store) is LifecycleState.APPROVED_AS_CANON
    assert not approvals_dir(store).exists()
    assert not list(store.root.rglob("approvals"))


def test_reapproval_path_via_derived_version_records_fresh_evidence(tmp_path):
    clock = Clock(datetime(2028, 5, 6, 7, 8, 9, tzinfo=timezone.utc))
    service, store, created = build(tmp_path, clock)
    pointer = store.read_version_pointer("atlas", "version-v1")
    store.update_version_pointer(
        replace(pointer, lifecycle_state=LifecycleState.APPROVED_AS_CANON)
    )
    derived = service.derive_version_from_approved(
        character_id="atlas",
        source_version_id="version-v1",
        source_revision_id=created.revision_id,
        source_snapshot_hash=created.snapshot_hash,
        new_version_id="version-v2",
        new_revision_id="revision-r2",
        new_version_label="Version 2",
    )
    submit(service, derived)

    approve(service, derived)

    evidence = store.load_approval_evidence("atlas", "version-v2", "revision-r2")
    assert evidence.decided_at == "2028-05-06T07:08:09Z"
    assert evidence.decided_by == "Ada Approver"
    assert not (
        store.root / "atlas" / "versions" / "version-v1" / "approvals"
    ).exists()
