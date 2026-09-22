"""Publication V1 domain, package, verifier, and immutable-store tests."""

from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import fields, replace
from pathlib import Path

import pytest

from services.character_authoring import (
    CharacterAuthoringStore,
    LifecycleState,
)
from services.character_publication import (
    COMPILER_PROFILE,
    RUNTIME_PACKAGE_SCHEMA_VERSION,
    CharacterPublicationService,
    CharacterPublicationStore,
    PublicationNotApprovedError,
    PublicationPackageCollisionError,
    PublicationSourceCorruptError,
    PublicationStaleRevisionError,
    PublicationStaleSnapshotError,
    PublicationValidationError,
    SourceProvenance,
    build_runtime_package,
    canonical_runtime_package_bytes,
    compute_package_hash,
    verify_runtime_package,
)


def semantic(*, visual_identity=None, name="Atlas") -> dict:
    return {
        "identity": {"display_name": name, "kind": "generic"},
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
        "appearance": {"descriptors": ["dark hair"], "height_cm": 180},
        "boundaries": {"principles": ["respects refusal"]},
        "visual_identity": {} if visual_identity is None else visual_identity,
    }


def build_source(
    tmp_path: Path,
    *,
    lifecycle_state: LifecycleState = LifecycleState.APPROVED_AS_CANON,
    visual_identity=None,
    revision_id: str = "revision-r1",
):
    authoring_root = tmp_path / "character_authoring"
    publication_root = tmp_path / "character_authoring_publication"
    store = CharacterAuthoringStore(authoring_root)
    store.create_character("atlas")
    pointer = store.create_version(
        "atlas",
        "version-v1",
        version_label="Version 1",
        lifecycle_state=LifecycleState.DRAFT,
    )
    record = store.persist_revision(
        "atlas",
        "version-v1",
        revision_id,
        semantic(visual_identity=visual_identity),
        lifecycle_state=LifecycleState.DRAFT,
    )
    store.update_version_pointer(
        replace(
            pointer,
            lifecycle_state=lifecycle_state,
            selected_revision_id=revision_id,
        )
    )
    publisher = CharacterPublicationService(
        store, CharacterPublicationStore(publication_root)
    )
    return store, publication_root, record, publisher


def publish(publisher, record, *, revision_id=None, snapshot_hash=None):
    return publisher.publish_character_version(
        character_id="atlas",
        version_id="version-v1",
        revision_id=revision_id or record.revision_id,
        snapshot_hash=snapshot_hash or record.snapshot_hash,
    )


def artifact_path(root: Path, result) -> Path:
    return root / result.character_id / result.package_hash


def source_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def write_canonical_payload(root: Path, payload: dict) -> tuple[Path, str]:
    raw = canonical_runtime_package_bytes(payload)
    digest = hashlib.sha256(raw).hexdigest()
    path = root / digest
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return path, digest


def test_approved_selected_revision_publishes_exact_package(tmp_path):
    store, root, record, publisher = build_source(tmp_path)

    result = publish(publisher, record)
    path = artifact_path(root, result)
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert result.runtime_package_schema_version == RUNTIME_PACKAGE_SCHEMA_VERSION
    assert path.name == result.package_hash
    assert hashlib.sha256(path.read_bytes()).hexdigest() == result.package_hash
    assert set(payload) == {
        "runtime_package_schema_version",
        "compiler_profile",
        "provenance",
        "semantic",
        "visual_identity_resolved",
    }
    assert payload["runtime_package_schema_version"] == RUNTIME_PACKAGE_SCHEMA_VERSION
    assert payload["compiler_profile"] == COMPILER_PROFILE
    assert payload["provenance"] == {
        "source_character_id": "atlas",
        "source_version_id": "version-v1",
        "source_revision_id": "revision-r1",
        "source_snapshot_hash": record.snapshot_hash,
    }
    assert store.read_version_pointer(
        "atlas", "version-v1"
    ).lifecycle_state is LifecycleState.APPROVED_AS_CANON


@pytest.mark.parametrize(
    "state",
    [
        LifecycleState.DRAFT,
        LifecycleState.PENDING_APPROVAL,
        LifecycleState.CHANGES_REQUESTED,
        LifecycleState.WITHDRAWN,
    ],
)
def test_non_approved_states_are_rejected_before_publication(tmp_path, state):
    _store, root, record, publisher = build_source(
        tmp_path, lifecycle_state=state
    )

    with pytest.raises(PublicationNotApprovedError):
        publish(publisher, record)

    assert not root.exists()


def test_non_selected_revision_is_stale(tmp_path):
    _store, root, record, publisher = build_source(tmp_path)

    with pytest.raises(PublicationStaleRevisionError):
        publish(publisher, record, revision_id="revision-r2")

    assert not root.exists()


def test_caller_snapshot_mismatch_is_stale(tmp_path):
    _store, root, record, publisher = build_source(tmp_path)

    with pytest.raises(PublicationStaleSnapshotError):
        publish(publisher, record, snapshot_hash="f" * 64)

    assert not root.exists()


def test_corrupt_source_revision_fails_closed(tmp_path):
    store, root, record, publisher = build_source(tmp_path)
    path = (
        store.root
        / "atlas"
        / "versions"
        / "version-v1"
        / "revisions"
        / "revision-r1.json"
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["semantic"]["biography"] = "tampered"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(PublicationSourceCorruptError):
        publish(publisher, record)

    assert not root.exists()


@pytest.mark.parametrize("empty_visual", [{}, {"references": []}])
def test_allowed_empty_visual_identity_round_trips_without_fabrication(
    tmp_path, empty_visual
):
    _store, root, record, publisher = build_source(
        tmp_path, visual_identity=empty_visual
    )

    result = publish(publisher, record)
    payload = json.loads(artifact_path(root, result).read_text(encoding="utf-8"))

    assert payload["semantic"] == record.semantic.to_dict()
    assert payload["semantic"]["appearance"] == {
        "descriptors": ["dark hair"],
        "height_cm": 180,
    }
    assert payload["semantic"]["visual_identity"] == empty_visual
    assert payload["visual_identity_resolved"] == {
        "state": "EXPLICITLY_EMPTY",
        "references": [],
    }


@pytest.mark.parametrize(
    "declared_visual",
    [
        {"reference_asset_id": "portrait-1"},
        {"references": [{"asset_id": "portrait-1"}]},
        {"references": [], "style": "painted"},
    ],
)
def test_non_empty_visual_identity_fails_closed(tmp_path, declared_visual):
    _store, root, record, publisher = build_source(
        tmp_path, visual_identity=declared_visual
    )

    with pytest.raises(PublicationValidationError):
        publish(publisher, record)

    assert not root.exists()


def test_same_input_has_identical_bytes_and_hash_and_idempotent_publish(tmp_path):
    _store, root, record, publisher = build_source(tmp_path)

    first = publish(publisher, record)
    path = artifact_path(root, first)
    before = path.read_bytes()
    second = publish(publisher, record)

    assert second == first
    assert path.read_bytes() == before
    assert not before.endswith(b"\n")
    assert hashlib.sha256(before).hexdigest() == first.package_hash


def test_concurrent_identical_publishers_converge_without_overwrite(tmp_path):
    store, root, record, _publisher = build_source(tmp_path)

    def run_publish(_index):
        service = CharacterPublicationService(
            store, CharacterPublicationStore(root)
        )
        return publish(service, record)

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = tuple(executor.map(run_publish, range(8)))

    assert len({result.package_hash for result in results}) == 1
    assert len(tuple((root / "atlas").iterdir())) == 1


def test_existing_corrupt_target_is_collision_and_is_not_overwritten(tmp_path):
    _store, root, record, publisher = build_source(tmp_path)
    result = publish(publisher, record)
    path = artifact_path(root, result)
    path.write_bytes(b"{}")

    with pytest.raises(PublicationPackageCollisionError):
        publish(publisher, record)

    assert path.read_bytes() == b"{}"


def test_tampered_package_fails_public_verification(tmp_path):
    _store, root, record, publisher = build_source(tmp_path)
    result = publish(publisher, record)
    path = artifact_path(root, result)
    path.write_bytes(path.read_bytes() + b" ")

    with pytest.raises(PublicationValidationError):
        verify_runtime_package(path, expected_package_hash=result.package_hash)


@pytest.mark.parametrize(
    "field,value",
    [
        ("runtime_package_schema_version", "unknown/9"),
        ("compiler_profile", "unknown/9"),
    ],
)
def test_unknown_schema_or_compiler_profile_fails_closed(tmp_path, field, value):
    _store, root, record, publisher = build_source(tmp_path)
    result = publish(publisher, record)
    payload = json.loads(artifact_path(root, result).read_text(encoding="utf-8"))
    payload[field] = value
    path, digest = write_canonical_payload(tmp_path / "verify", payload)

    with pytest.raises(PublicationValidationError):
        verify_runtime_package(path, expected_package_hash=digest)


def test_unknown_package_field_fails_closed(tmp_path):
    _store, root, record, publisher = build_source(tmp_path)
    result = publish(publisher, record)
    payload = json.loads(artifact_path(root, result).read_text(encoding="utf-8"))
    payload["unexpected"] = True
    path, digest = write_canonical_payload(tmp_path / "verify", payload)

    with pytest.raises(PublicationValidationError):
        verify_runtime_package(path, expected_package_hash=digest)


def test_source_snapshot_mismatch_inside_package_fails_verification(tmp_path):
    _store, root, record, publisher = build_source(tmp_path)
    result = publish(publisher, record)
    payload = json.loads(artifact_path(root, result).read_text(encoding="utf-8"))
    payload["provenance"]["source_snapshot_hash"] = "f" * 64
    path, digest = write_canonical_payload(tmp_path / "verify", payload)

    with pytest.raises(PublicationValidationError):
        verify_runtime_package(path, expected_package_hash=digest)


def test_same_semantic_different_revision_provenance_changes_package_hash(tmp_path):
    _store, _root, record, _publisher = build_source(tmp_path)
    first = build_runtime_package(
        SourceProvenance(
            "atlas", "version-v1", "revision-r1", record.snapshot_hash
        ),
        record.semantic,
    )
    second = build_runtime_package(
        SourceProvenance(
            "atlas", "version-v1", "revision-r2", record.snapshot_hash
        ),
        record.semantic,
    )

    assert compute_package_hash(first) != compute_package_hash(second)


def test_publication_does_not_change_any_source_file(tmp_path):
    store, _root, record, publisher = build_source(tmp_path)
    before = source_bytes(store.root)

    publish(publisher, record)

    assert source_bytes(store.root) == before
    pointer = store.read_version_pointer("atlas", "version-v1")
    loaded = store.load_revision("atlas", "version-v1", "revision-r1")
    assert pointer.selected_revision_id == "revision-r1"
    assert pointer.lifecycle_state is LifecycleState.APPROVED_AS_CANON
    assert loaded.snapshot_hash == record.snapshot_hash


def test_store_creates_no_latest_or_active_pointer(tmp_path):
    _store, root, record, publisher = build_source(tmp_path)
    result = publish(publisher, record)

    relative_files = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    }
    assert relative_files == {f"atlas/{result.package_hash}"}


def test_normalized_key_collision_is_rejected():
    with pytest.raises(PublicationValidationError):
        canonical_runtime_package_bytes({"e\u0301": 1, "é": 2})


@pytest.mark.parametrize("non_finite", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_numbers_are_rejected(non_finite):
    with pytest.raises(PublicationValidationError):
        canonical_runtime_package_bytes({"value": non_finite})


def test_result_and_package_expose_no_filesystem_path(tmp_path):
    _store, root, record, publisher = build_source(tmp_path)
    result = publish(publisher, record)
    payload = artifact_path(root, result).read_text(encoding="utf-8")

    assert {field.name for field in fields(result)} == {
        "runtime_package_schema_version",
        "character_id",
        "package_hash",
        "source_version_id",
        "source_revision_id",
        "source_snapshot_hash",
    }
    assert str(tmp_path) not in payload
    assert "path" not in json.loads(payload)
