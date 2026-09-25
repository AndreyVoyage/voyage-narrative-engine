"""LAB-L1 approval evidence: immutable model, timestamps, and write-once store."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from services.character_authoring import (
    APPROVAL_DECISION_HUMAN_APPROVED,
    APPROVAL_EVIDENCE_SCHEMA_VERSION,
    ApprovalEvidence,
    ApprovalEvidenceConflictError,
    CharacterAuthoringCorruptionError,
    CharacterAuthoringInvariantError,
    CharacterAuthoringNotFoundError,
    CharacterAuthoringStore,
    CharacterAuthoringValidationError,
    IdentifierValidationError,
    format_decided_at,
    validate_decided_at,
    validate_decided_by,
)

DECIDED_AT = "2026-03-04T05:06:07Z"


def semantic(name: str = "Atlas") -> dict:
    return {
        "identity": {"display_name": name},
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


def build_store(tmp_path):
    store = CharacterAuthoringStore(tmp_path / "authoring")
    store.create_character("atlas")
    store.create_version("atlas", "version-v1", version_label="Version 1")
    record = store.persist_revision("atlas", "version-v1", "revision-r1", semantic())
    return store, record


def evidence_for(record, **overrides) -> ApprovalEvidence:
    values = dict(
        character_id=record.character_id,
        version_id=record.version_id,
        revision_id=record.revision_id,
        snapshot_hash=record.snapshot_hash,
        decided_by="Ada Approver",
        decided_at=DECIDED_AT,
    )
    values.update(overrides)
    return ApprovalEvidence(**values)


def approval_file(store, *, revision_id="revision-r1"):
    return (
        store.root / "atlas" / "versions" / "version-v1" / "approvals"
        / f"{revision_id}.json"
    )


# -- constants and shape ------------------------------------------------


def test_schema_and_decision_constants_are_exact():
    assert APPROVAL_EVIDENCE_SCHEMA_VERSION == "character_approval_evidence/1.0"
    assert APPROVAL_DECISION_HUMAN_APPROVED == "HUMAN_APPROVED"


def test_evidence_has_exactly_the_ratified_fields(tmp_path):
    _store, record = build_store(tmp_path)

    payload = evidence_for(record).to_dict()

    assert payload == {
        "schema_version": "character_approval_evidence/1.0",
        "character_id": "atlas",
        "version_id": "version-v1",
        "revision_id": "revision-r1",
        "snapshot_hash": record.snapshot_hash,
        "decision": "HUMAN_APPROVED",
        "decided_by": "Ada Approver",
        "decided_at": DECIDED_AT,
    }


def test_evidence_round_trips_through_dict(tmp_path):
    _store, record = build_store(tmp_path)
    evidence = evidence_for(record)

    assert ApprovalEvidence.from_dict(evidence.to_dict()) == evidence


@pytest.mark.parametrize("key", [
    "schema_version", "character_id", "version_id", "revision_id",
    "snapshot_hash", "decision", "decided_by", "decided_at",
])
def test_from_dict_rejects_missing_key(tmp_path, key):
    _store, record = build_store(tmp_path)
    payload = evidence_for(record).to_dict()
    del payload[key]

    with pytest.raises(CharacterAuthoringValidationError):
        ApprovalEvidence.from_dict(payload)


def test_from_dict_rejects_extra_key_and_release_vocabulary(tmp_path):
    _store, record = build_store(tmp_path)
    for extra in ("releaseId", "aggregateHash", "packageHash", "note"):
        payload = evidence_for(record).to_dict()
        payload[extra] = "x"
        with pytest.raises(CharacterAuthoringValidationError):
            ApprovalEvidence.from_dict(payload)


def test_from_dict_rejects_unknown_schema_and_non_object(tmp_path):
    _store, record = build_store(tmp_path)
    payload = evidence_for(record).to_dict()
    payload["schema_version"] = "character_approval_evidence/2.0"

    with pytest.raises(CharacterAuthoringValidationError):
        ApprovalEvidence.from_dict(payload)
    with pytest.raises(CharacterAuthoringValidationError):
        ApprovalEvidence.from_dict([payload])


@pytest.mark.parametrize(
    "decision", ["APPROVED", "human_approved", "HUMAN_APPROVED ", "", None]
)
def test_decision_must_be_exactly_human_approved(tmp_path, decision):
    _store, record = build_store(tmp_path)

    with pytest.raises(CharacterAuthoringValidationError):
        evidence_for(record, decision=decision)


def test_identities_are_validated(tmp_path):
    _store, record = build_store(tmp_path)

    with pytest.raises(IdentifierValidationError):
        evidence_for(record, character_id="../escape")
    with pytest.raises(IdentifierValidationError):
        evidence_for(record, revision_id="Revision R1")
    with pytest.raises(CharacterAuthoringValidationError):
        evidence_for(record, snapshot_hash="abc")
    with pytest.raises(CharacterAuthoringInvariantError):
        evidence_for(record, version_id="atlas")


# -- decided_by -----------------------------------------------------------


@pytest.mark.parametrize("value", [None, 7, b"Ada", ["Ada"], "", " ", "\t\n  "])
def test_decided_by_rejects_missing_non_string_and_blank(value):
    with pytest.raises(CharacterAuthoringValidationError):
        validate_decided_by(value)


def test_decided_by_rejects_non_nfc_text():
    decomposed = "José"

    with pytest.raises(CharacterAuthoringValidationError):
        validate_decided_by(decomposed)


def test_decided_by_rejects_lone_surrogate():
    with pytest.raises(CharacterAuthoringValidationError):
        validate_decided_by("bad\ud800text")


@pytest.mark.parametrize(
    "value", ["Ada Approver", "  Ada  ", "Андрей", "José", "a", "Ada B"]
)
def test_decided_by_is_preserved_exactly(value):
    assert validate_decided_by(value) == value


def test_evidence_does_not_trim_or_normalize_decided_by(tmp_path):
    _store, record = build_store(tmp_path)

    evidence = evidence_for(record, decided_by="  Ada Approver  ")

    assert evidence.decided_by == "  Ada Approver  "
    assert evidence.to_dict()["decided_by"] == "  Ada Approver  "


# -- decided_at ---------------------------------------------------------


@pytest.mark.parametrize(
    "value", ["2026-03-04T05:06:07Z", "2024-02-29T23:59:59Z", "0001-01-01T00:00:00Z"]
)
def test_decided_at_accepts_only_canonical_utc_form(value):
    assert validate_decided_at(value) == value


@pytest.mark.parametrize(
    "value",
    [
        "2026-03-04T05:06:07+00:00",
        "2026-03-04T05:06:07.123Z",
        "2026-03-04T05:06:07z",
        "2026-03-04t05:06:07Z",
        "2026-03-04 05:06:07Z",
        "2026-03-04T05:06:07",
        "2026-03-04T05:06Z",
        "2026-3-4T5:6:7Z",
        "20260304T050607Z",
        "2026-03-04T05:06:07-00:00",
        "2026-03-04T05:06:07+01:00",
        "2026-02-30T05:06:07Z",
        "2025-02-29T05:06:07Z",
        "2026-13-01T05:06:07Z",
        "2026-00-10T05:06:07Z",
        "2026-03-04T24:00:00Z",
        "2026-03-04T05:60:07Z",
        "2026-03-04T05:06:60Z",
        "0000-01-01T00:00:00Z",
        "٢٠٢٦-03-04T05:06:07Z",
        " 2026-03-04T05:06:07Z",
        "2026-03-04T05:06:07Z\n",
        "",
        None,
        20260304,
    ],
)
def test_decided_at_rejects_every_other_form(value):
    with pytest.raises(CharacterAuthoringValidationError):
        validate_decided_at(value)


def test_format_decided_at_converts_to_utc_and_truncates_fraction():
    plus_three = timezone(timedelta(hours=3))
    moment = datetime(2026, 3, 4, 8, 6, 7, 999999, tzinfo=plus_three)

    assert format_decided_at(moment) == "2026-03-04T05:06:07Z"
    assert format_decided_at(
        datetime(2026, 3, 4, 5, 6, 7, tzinfo=timezone.utc)
    ) == DECIDED_AT


@pytest.mark.parametrize(
    "moment", [datetime(2026, 3, 4, 5, 6, 7), "2026-03-04T05:06:07Z", None, 1]
)
def test_format_decided_at_rejects_naive_or_non_datetime(moment):
    with pytest.raises(CharacterAuthoringValidationError):
        format_decided_at(moment)


# -- write-once store -----------------------------------------------------


def test_persist_writes_write_once_file_at_ratified_path(tmp_path):
    store, record = build_store(tmp_path)
    evidence = evidence_for(record)

    stored = store.persist_approval_evidence(evidence)

    assert stored == evidence
    path = approval_file(store)
    assert path.is_file()
    assert path.relative_to(store.root).as_posix() == (
        "atlas/versions/version-v1/approvals/revision-r1.json"
    )
    assert json.loads(path.read_text(encoding="utf-8")) == evidence.to_dict()
    raw = path.read_bytes()
    assert raw.endswith(b"\n") and not raw.endswith(b"\n\n")
    assert b"\r" not in raw and not raw.startswith(b"\xef\xbb\xbf")


def test_persist_then_load_round_trips(tmp_path):
    store, record = build_store(tmp_path)
    evidence = evidence_for(record)
    store.persist_approval_evidence(evidence)

    assert store.load_approval_evidence(
        "atlas", "version-v1", "revision-r1"
    ) == evidence


def test_persist_preserves_unicode_decided_by_on_disk(tmp_path):
    store, record = build_store(tmp_path)
    evidence = evidence_for(record, decided_by="Андрей Воевода")

    store.persist_approval_evidence(evidence)

    assert "Андрей Воевода" in approval_file(store).read_text(encoding="utf-8")
    assert store.load_approval_evidence(
        "atlas", "version-v1", "revision-r1"
    ).decided_by == "Андрей Воевода"


def test_identical_evidence_is_idempotent_and_leaves_bytes_unchanged(tmp_path):
    store, record = build_store(tmp_path)
    evidence = evidence_for(record)
    store.persist_approval_evidence(evidence)
    before = approval_file(store).read_bytes()

    again = store.persist_approval_evidence(evidence_for(record))

    assert again == evidence
    assert approval_file(store).read_bytes() == before


@pytest.mark.parametrize(
    "overrides",
    [
        {"decided_by": "Someone Else"},
        {"decided_at": "2026-03-04T05:06:08Z"},
    ],
)
def test_differing_evidence_never_overwrites(tmp_path, overrides):
    store, record = build_store(tmp_path)
    store.persist_approval_evidence(evidence_for(record))
    before = approval_file(store).read_bytes()

    with pytest.raises(ApprovalEvidenceConflictError):
        store.persist_approval_evidence(evidence_for(record, **overrides))

    assert approval_file(store).read_bytes() == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("character_id", "other"),
        ("version_id", "version-other"),
        ("revision_id", "revision-other"),
        ("snapshot_hash", "e" * 64),
        ("decision", "HUMAN_APPROVED"),
        ("decided_by", "Tampered"),
        ("decided_at", "2030-01-01T00:00:00Z"),
    ],
)
def test_existing_file_differing_in_any_field_fails_closed(tmp_path, field, value):
    store, record = build_store(tmp_path)
    evidence = evidence_for(record)
    store.persist_approval_evidence(evidence)
    path = approval_file(store)
    tampered = evidence.to_dict()
    tampered[field] = value
    path.write_text(json.dumps(tampered), encoding="utf-8")
    tampered_bytes = path.read_bytes()
    expect_conflict = tampered != evidence.to_dict()

    if expect_conflict:
        with pytest.raises(ApprovalEvidenceConflictError):
            store.persist_approval_evidence(evidence)
    else:
        assert store.persist_approval_evidence(evidence) == evidence
    assert path.read_bytes() == tampered_bytes


def test_persist_requires_existing_revision_and_creates_nothing(tmp_path):
    store, record = build_store(tmp_path)
    before = sorted(p.relative_to(store.root).as_posix() for p in store.root.rglob("*"))

    with pytest.raises(CharacterAuthoringNotFoundError):
        store.persist_approval_evidence(
            evidence_for(record, revision_id="revision-missing")
        )
    with pytest.raises(CharacterAuthoringNotFoundError):
        store.persist_approval_evidence(
            evidence_for(record, version_id="version-missing")
        )

    after = sorted(p.relative_to(store.root).as_posix() for p in store.root.rglob("*"))
    assert after == before


def test_persist_rejects_snapshot_not_matching_exact_revision(tmp_path):
    store, record = build_store(tmp_path)

    with pytest.raises(CharacterAuthoringInvariantError):
        store.persist_approval_evidence(evidence_for(record, snapshot_hash="d" * 64))

    assert not approval_file(store).exists()


def test_persist_rejects_non_evidence_objects(tmp_path):
    store, record = build_store(tmp_path)

    with pytest.raises(CharacterAuthoringValidationError):
        store.persist_approval_evidence(evidence_for(record).to_dict())


def test_load_missing_evidence_is_not_found(tmp_path):
    store, _record = build_store(tmp_path)

    with pytest.raises(CharacterAuthoringNotFoundError):
        store.load_approval_evidence("atlas", "version-v1", "revision-r1")


@pytest.mark.parametrize("raw", ["not json", "[]", '{"schema_version": 1}'])
def test_load_corrupt_evidence_fails_closed(tmp_path, raw):
    store, _record = build_store(tmp_path)
    path = approval_file(store)
    path.parent.mkdir(parents=True)
    path.write_text(raw, encoding="utf-8")

    with pytest.raises(CharacterAuthoringCorruptionError):
        store.load_approval_evidence("atlas", "version-v1", "revision-r1")


def test_load_rejects_evidence_stored_under_the_wrong_revision_path(tmp_path):
    store, record = build_store(tmp_path)
    store.persist_revision("atlas", "version-v1", "revision-r2", semantic("Other"))
    wrong = evidence_for(record)
    path = approval_file(store, revision_id="revision-r2")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(wrong.to_dict()), encoding="utf-8")

    with pytest.raises(CharacterAuthoringCorruptionError):
        store.load_approval_evidence("atlas", "version-v1", "revision-r2")


def test_load_rejects_evidence_whose_snapshot_no_longer_matches_revision(tmp_path):
    store, record = build_store(tmp_path)
    path = approval_file(store)
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(evidence_for(record, snapshot_hash="c" * 64).to_dict()),
        encoding="utf-8",
    )

    with pytest.raises(CharacterAuthoringCorruptionError):
        store.load_approval_evidence("atlas", "version-v1", "revision-r1")


def test_unsafe_identifiers_are_rejected_before_any_path_is_built(tmp_path):
    store, _record = build_store(tmp_path)

    with pytest.raises(IdentifierValidationError):
        store.load_approval_evidence("atlas", "version-v1", "../revision-r1")
    with pytest.raises(IdentifierValidationError):
        store.load_approval_evidence("..", "version-v1", "revision-r1")


def test_no_temp_files_remain_after_success_or_conflict(tmp_path):
    store, record = build_store(tmp_path)
    store.persist_approval_evidence(evidence_for(record))
    with pytest.raises(ApprovalEvidenceConflictError):
        store.persist_approval_evidence(evidence_for(record, decided_by="Other"))

    leftovers = [p for p in store.root.rglob(".tmp_*")]
    assert leftovers == []


def test_approvals_directory_does_not_disturb_listings_or_revisions(tmp_path):
    store, record = build_store(tmp_path)
    revision_before = (
        store.root / "atlas" / "versions" / "version-v1" / "revisions"
        / "revision-r1.json"
    ).read_bytes()

    store.persist_approval_evidence(evidence_for(record))

    assert store.list_versions("atlas") == ["version-v1"]
    assert store.list_revisions("atlas", "version-v1") == ["revision-r1"]
    assert store.load_revision("atlas", "version-v1", "revision-r1") == record
    assert (
        store.root / "atlas" / "versions" / "version-v1" / "revisions"
        / "revision-r1.json"
    ).read_bytes() == revision_before


def test_version_pointer_workflow_metadata_is_untouched(tmp_path):
    store, record = build_store(tmp_path)
    before = store.read_version_pointer("atlas", "version-v1")

    store.persist_approval_evidence(evidence_for(record))

    assert store.read_version_pointer("atlas", "version-v1") == before
    assert dict(before.workflow_metadata) == {}
