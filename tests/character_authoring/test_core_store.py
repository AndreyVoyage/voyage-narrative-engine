from __future__ import annotations

import json
from dataclasses import replace

import pytest

from services.character_authoring import (
    SEMANTIC_SCHEMA_VERSION,
    CharacterAuthoringCorruptionError,
    CharacterAuthoringInvariantError,
    CharacterAuthoringStore,
    CharacterAuthoringValidationError,
    CharacterPointer,
    CharacterSemantic,
    IdentifierValidationError,
    ImmutableRevisionError,
    LifecycleState,
    LifecycleValidationError,
    SnapshotHashMismatchError,
    VersionPointer,
    canonical_semantic_json,
    compute_snapshot_hash,
    default_store_root,
    validate_identifier,
)


def semantic(name: str = "Áster") -> dict:
    return {
        "identity": {"display_name": name, "stable_refs": ["identity-ref-1"]},
        "biography": "A complete standalone biography.",
        "psychology": {
            "personality": ["curious"],
            "behavioral_traits": ["observant"],
            "emotional_tendencies": ["reflective"],
            "goals_motivations": ["understand the unknown"],
        },
        "speech": {"speech_style": "measured", "register": None},
        "character_relations": {
            "relational_tendencies": ["builds trust gradually"],
            "attachment_traits": ["values consistency"],
        },
        "appearance": {"descriptors": ["dark hair"]},
        "boundaries": {"principles": ["respects explicit refusal"]},
        "visual_identity": {
            "reference_asset_id": "portrait-ref-1",
            "asset_sha256": "a" * 64,
        },
    }


def ready_store(tmp_path, character_id="atlas", version_id="draft-v1"):
    store = CharacterAuthoringStore(tmp_path / "store")
    store.create_character(character_id)
    store.create_version(character_id, version_id, version_label="First draft")
    return store


def revision_path(store, character_id="atlas", version_id="draft-v1", revision_id="r1"):
    return (
        store.root
        / character_id
        / "versions"
        / version_id
        / "revisions"
        / f"{revision_id}.json"
    )


def test_nfc_normalizes_recursive_values_and_dictionary_keys():
    decomposed = semantic("A\u0301ster")
    decomposed["identity"]["cafe\u0301"] = {"re\u0301sume\u0301": ["e\u0301"]}
    composed = semantic("Áster")
    composed["identity"]["café"] = {"résumé": ["é"]}
    assert compute_snapshot_hash(decomposed) == compute_snapshot_hash(composed)
    normalized = CharacterSemantic.from_dict(decomposed).to_dict()
    assert normalized["identity"]["café"]["résumé"] == ["é"]


def test_nfc_key_collision_fails_closed():
    data = semantic()
    data["identity"]["é"] = 1
    data["identity"]["e\u0301"] = 2
    with pytest.raises(CharacterAuthoringValidationError):
        compute_snapshot_hash(data)


def test_hash_is_deterministic_and_key_order_independent():
    first = semantic()
    second = dict(reversed(list(first.items())))
    assert first is not second
    assert compute_snapshot_hash(first) == compute_snapshot_hash(second)
    assert canonical_semantic_json(first) == canonical_semantic_json(second)
    assert not canonical_semantic_json(first).endswith("\n")
    assert SEMANTIC_SCHEMA_VERSION in canonical_semantic_json(first)


def test_hash_excludes_workflow_metadata_but_changes_with_semantics(tmp_path):
    store = ready_store(tmp_path)
    r1 = store.persist_revision(
        "atlas", "draft-v1", "r1", semantic(), workflow_metadata={"panel": "left"}
    )
    changed = semantic()
    changed["biography"] += " Changed."
    r2 = store.persist_revision(
        "atlas", "draft-v1", "r2", semantic(), workflow_metadata={"panel": "right"}
    )
    r3 = store.persist_revision("atlas", "draft-v1", "r3", changed)
    assert r1.snapshot_hash == r2.snapshot_hash
    assert r1.snapshot_hash != r3.snapshot_hash


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), object(), ("tuple",)])
def test_non_json_safe_semantic_values_fail_closed(bad):
    data = semantic()
    data["identity"]["bad"] = bad
    with pytest.raises(CharacterAuthoringValidationError):
        compute_snapshot_hash(data)


def test_semantic_schema_is_generic_and_exact():
    model = CharacterSemantic.from_dict(semantic("Nova"))
    assert model.to_dict()["identity"]["display_name"] == "Nova"
    with pytest.raises(CharacterAuthoringValidationError):
        bad = semantic()
        bad["psychology"]["anger"] = []
        CharacterSemantic.from_dict(bad)
    with pytest.raises(CharacterAuthoringValidationError):
        bad = semantic()
        bad["runtime_memory"] = {}
        CharacterSemantic.from_dict(bad)


def test_first_revision_write_is_full_standalone_snapshot(tmp_path):
    store = ready_store(tmp_path)
    record = store.persist_revision("atlas", "draft-v1", "r1", semantic())
    payload = json.loads(revision_path(store).read_text(encoding="utf-8"))
    assert payload["semantic"] == semantic()
    assert "patch" not in payload
    assert payload["snapshot_hash"] == record.snapshot_hash
    assert store.load_revision("atlas", "draft-v1", "r1") == record


def test_revision_is_immutable_even_for_identical_second_write(tmp_path):
    store = ready_store(tmp_path)
    store.persist_revision("atlas", "draft-v1", "r1", semantic())
    path = revision_path(store)
    original = path.read_bytes()
    with pytest.raises(ImmutableRevisionError):
        store.persist_revision("atlas", "draft-v1", "r1", semantic())
    assert path.read_bytes() == original


def test_save_creates_revisions_inside_same_version(tmp_path):
    store = ready_store(tmp_path)
    first = store.persist_revision("atlas", "draft-v1", "r1", semantic())
    updated = semantic()
    updated["biography"] = "Second full checkpoint."
    second = store.persist_revision("atlas", "draft-v1", "r2", updated)
    assert store.list_versions("atlas") == ["draft-v1"]
    assert store.list_revisions("atlas", "draft-v1") == ["r1", "r2"]
    assert store.load_revision("atlas", "draft-v1", "r1") == first
    assert store.load_revision("atlas", "draft-v1", "r2") == second


def test_two_versions_of_one_character_coexist_deterministically(tmp_path):
    store = CharacterAuthoringStore(tmp_path / "store")
    store.create_character("atlas")
    store.create_version("atlas", "version-z", version_label="Z")
    store.create_version("atlas", "version-a", version_label="A")
    store.persist_revision("atlas", "version-z", "r1", semantic())
    store.persist_revision("atlas", "version-a", "r1", semantic())
    assert store.list_versions("atlas") == ["version-a", "version-z"]


def test_pointer_updates_are_atomic_and_do_not_mutate_revisions(tmp_path):
    store = ready_store(tmp_path)
    store.persist_revision("atlas", "draft-v1", "r1", semantic())
    revision = revision_path(store)
    original = revision.read_bytes()
    character_pointer = replace(
        store.read_character_pointer("atlas"), selected_version_id="draft-v1"
    )
    version_pointer = replace(
        store.read_version_pointer("atlas", "draft-v1"),
        selected_revision_id="r1",
        lifecycle_state=LifecycleState.PENDING_APPROVAL,
    )
    store.update_character_pointer(character_pointer)
    store.update_version_pointer(version_pointer)
    assert store.read_character_pointer("atlas") == character_pointer
    assert store.read_version_pointer("atlas", "draft-v1") == version_pointer
    assert revision.read_bytes() == original
    assert list(store.root.rglob(".tmp_character_authoring_*")) == []


def test_restart_durability(tmp_path):
    root = tmp_path / "store"
    first = CharacterAuthoringStore(root)
    first.create_character("atlas")
    first.create_version("atlas", "draft-v1", version_label="Draft")
    written = first.persist_revision("atlas", "draft-v1", "r1", semantic())
    del first
    reopened = CharacterAuthoringStore(root)
    assert reopened.list_character_ids() == ["atlas"]
    assert reopened.list_versions("atlas") == ["draft-v1"]
    assert reopened.list_revisions("atlas", "draft-v1") == ["r1"]
    assert reopened.load_revision("atlas", "draft-v1", "r1") == written


@pytest.mark.parametrize(
    "bad_id", ["../x", "..\\x", "C:\\x", "/x", "a/b", "a\\b", ".", "..", ""]
)
def test_unsafe_identifiers_are_rejected(bad_id):
    with pytest.raises(IdentifierValidationError):
        validate_identifier(bad_id, field="test_id")


@pytest.mark.parametrize("bad_id", ["atlas.", "Atlas", "ATLAS"])
def test_character_ids_reject_windows_alias_forms_before_creation(tmp_path, bad_id):
    store = CharacterAuthoringStore(tmp_path / "store")
    with pytest.raises(IdentifierValidationError):
        store.create_character(bad_id)
    assert list(store.root.iterdir()) == []

    store.create_character("atlas")
    assert store.list_character_ids() == ["atlas"]


@pytest.mark.parametrize("bad_id", ["atlas.", "Atlas", "ATLAS"])
def test_version_ids_reject_windows_alias_forms_before_creation(tmp_path, bad_id):
    store = CharacterAuthoringStore(tmp_path / "store")
    store.create_character("atlas")
    with pytest.raises(IdentifierValidationError):
        store.create_version("atlas", bad_id, version_label="Invalid")
    assert store.list_versions("atlas") == []

    store.create_version("atlas", "version-v1", version_label="Valid")
    assert store.list_versions("atlas") == ["version-v1"]


@pytest.mark.parametrize("bad_id", ["atlas.", "Atlas", "ATLAS"])
def test_revision_ids_reject_windows_alias_forms_before_creation(tmp_path, bad_id):
    store = ready_store(tmp_path)
    with pytest.raises(IdentifierValidationError):
        store.persist_revision("atlas", "draft-v1", bad_id, semantic())
    assert store.list_revisions("atlas", "draft-v1") == []

    store.persist_revision("atlas", "draft-v1", "r1", semantic())
    assert store.list_revisions("atlas", "draft-v1") == ["r1"]


def test_tampered_semantic_payload_fails_hash_validation(tmp_path):
    store = ready_store(tmp_path)
    store.persist_revision("atlas", "draft-v1", "r1", semantic())
    path = revision_path(store)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["semantic"]["biography"] = "tampered"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(SnapshotHashMismatchError):
        store.load_revision("atlas", "draft-v1", "r1")


def test_tampered_stored_snapshot_hash_fails_validation(tmp_path):
    store = ready_store(tmp_path)
    store.persist_revision("atlas", "draft-v1", "r1", semantic())
    path = revision_path(store)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["snapshot_hash"] = "0" * 64
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(SnapshotHashMismatchError):
        store.load_revision("atlas", "draft-v1", "r1")


def test_malformed_revision_and_pointer_fail_as_corruption(tmp_path):
    store = ready_store(tmp_path)
    store.persist_revision("atlas", "draft-v1", "r1", semantic())
    revision_path(store).write_text("[]", encoding="utf-8")
    assert store.list_revisions("atlas", "draft-v1") == ["r1"]
    with pytest.raises(CharacterAuthoringCorruptionError):
        store.load_revision("atlas", "draft-v1", "r1")
    pointer = store.root / "atlas" / "pointer.json"
    pointer.write_text("not-json", encoding="utf-8")
    with pytest.raises(CharacterAuthoringCorruptionError):
        store.read_character_pointer("atlas")


def test_abandoned_internal_temp_alone_does_not_break_revision_listing(tmp_path):
    store = ready_store(tmp_path)
    revisions = revision_path(store).parent
    revisions.mkdir(parents=True)
    (revisions / ".tmp_character_authoring_abandoned.tmp").write_bytes(
        b"complete temporary artifact"
    )

    assert store.list_revisions("atlas", "draft-v1") == []


def test_abandoned_internal_temp_beside_revision_is_ignored(tmp_path):
    store = ready_store(tmp_path)
    written = store.persist_revision("atlas", "draft-v1", "r1", semantic())
    revisions = revision_path(store).parent
    (revisions / ".tmp_character_authoring_abandoned.tmp").write_bytes(
        b"complete temporary artifact"
    )

    assert store.list_revisions("atlas", "draft-v1") == ["r1"]
    assert store.load_revision("atlas", "draft-v1", "r1") == written


@pytest.mark.parametrize("state", list(LifecycleState))
def test_all_ratified_lifecycle_values_persist(state, tmp_path):
    store = CharacterAuthoringStore(tmp_path / state.value)
    store.create_character("nova")
    store.create_version("nova", "logical-v1", version_label="Version", lifecycle_state=state)
    pointer = store.read_version_pointer("nova", "logical-v1")
    assert pointer.lifecycle_state is state


def test_unknown_lifecycle_value_is_rejected(tmp_path):
    store = CharacterAuthoringStore(tmp_path / "store")
    store.create_character("nova")
    with pytest.raises(LifecycleValidationError):
        store.create_version(
            "nova", "logical-v1", version_label="Version", lifecycle_state="PUBLISHED"
        )
    assert not (store.root / "nova" / "versions" / "logical-v1").exists()


def test_invalid_pointer_metadata_leaves_no_partial_container(tmp_path):
    store = CharacterAuthoringStore(tmp_path / "store")
    with pytest.raises(CharacterAuthoringValidationError):
        store.create_character("nova", workflow_metadata=[])  # type: ignore[arg-type]
    assert not (store.root / "nova").exists()


def test_identity_invariants_are_enforced(tmp_path):
    store = CharacterAuthoringStore(tmp_path / "store")
    store.create_character("same")
    with pytest.raises(CharacterAuthoringInvariantError):
        store.create_version("same", "same", version_label="Invalid")
    store.create_version("same", "version-1", version_label="Valid")
    with pytest.raises(CharacterAuthoringInvariantError):
        store.persist_revision("same", "version-1", "version-1", semantic())


def test_derived_version_provenance_is_persisted(tmp_path):
    store = ready_store(tmp_path)
    record = store.persist_revision(
        "atlas",
        "draft-v1",
        "r1",
        semantic(),
        derived_from_version_id="source-v1",
        derived_from_revision_id="source-r9",
        derived_from_snapshot_hash="b" * 64,
    )
    loaded = store.load_revision("atlas", "draft-v1", "r1")
    assert loaded == record
    assert loaded.derived_from_version_id == "source-v1"
    assert loaded.derived_from_revision_id == "source-r9"
    assert loaded.derived_from_snapshot_hash == "b" * 64


def test_revision_inherits_derived_version_provenance(tmp_path):
    store = CharacterAuthoringStore(tmp_path / "store")
    store.create_character("atlas")
    store.create_version("atlas", "source-v1", version_label="Source")
    source = store.persist_revision("atlas", "source-v1", "source-r1", semantic())
    store.create_version(
        "atlas",
        "derived-v2",
        version_label="Derived",
        derived_from_version_id="source-v1",
        derived_from_revision_id="source-r1",
        derived_from_snapshot_hash=source.snapshot_hash,
    )
    derived = store.persist_revision("atlas", "derived-v2", "derived-r1", semantic())
    assert derived.derived_from_version_id == "source-v1"
    assert derived.derived_from_revision_id == "source-r1"
    assert derived.derived_from_snapshot_hash == source.snapshot_hash


def test_partial_provenance_is_rejected(tmp_path):
    store = ready_store(tmp_path)
    with pytest.raises(CharacterAuthoringInvariantError):
        store.persist_revision(
            "atlas",
            "draft-v1",
            "r1",
            semantic(),
            derived_from_version_id="source-v1",
        )


def test_two_generic_characters_are_independent_and_sorted(tmp_path):
    store = CharacterAuthoringStore(tmp_path / "store")
    for character_id, display_name in (("zephyr", "Zephyr"), ("atlas", "Atlas")):
        store.create_character(character_id)
        store.create_version(character_id, "draft-v1", version_label="Draft")
        store.persist_revision(character_id, "draft-v1", "r1", semantic(display_name))
    assert store.list_character_ids() == ["atlas", "zephyr"]
    assert (
        store.load_revision("atlas", "draft-v1", "r1")
        .semantic.to_dict()["identity"]["display_name"]
        == "Atlas"
    )
    assert (
        store.load_revision("zephyr", "draft-v1", "r1")
        .semantic.to_dict()["identity"]["display_name"]
        == "Zephyr"
    )


def test_pointer_types_are_identity_checked(tmp_path):
    store = ready_store(tmp_path)
    with pytest.raises(CharacterAuthoringValidationError):
        store.update_character_pointer(object())  # type: ignore[arg-type]
    with pytest.raises(CharacterAuthoringValidationError):
        store.update_version_pointer(object())  # type: ignore[arg-type]
    assert isinstance(store.read_character_pointer("atlas"), CharacterPointer)
    assert isinstance(store.read_version_pointer("atlas", "draft-v1"), VersionPointer)


def test_default_root_is_local_application_data(tmp_path):
    assert default_store_root(tmp_path) == tmp_path / "local_runs" / "character_authoring"
