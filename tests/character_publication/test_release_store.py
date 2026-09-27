"""LAB-L4 RELEASE_STORE_AND_CURRENT_V1: durable releases, explicit current, export."""

from __future__ import annotations

import ast
import hashlib
import itertools
import json
import os
import shutil
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tests._vcp_dependency_gate import require_pinned_vcp

require_pinned_vcp()  # hard VCP dependency gate (replaces silent importorskip)

from services.character_authoring import (
    ApprovalEvidence,
    CharacterAuthoringStore,
    LifecycleState,
)
from services.character_lab_application import (
    CharacterLabApplicationConfig,
    CharacterLabApplicationService,
)
from services.character_publication import release_store as rs
from services.character_publication import vcp_artifact, vcp_release
from services.character_publication.model import SourceProvenance
from services.character_publication.release_store import (
    CanonicalCurrent,
    CharacterReleaseStore,
    CharacterReleaseStoreError,
    CurrentDesignationError,
    DurableArtifactCorruptError,
    ReleaseExportError,
    ReleaseIdHashCollisionError,
    ReleaseInputError,
    ReleaseNotFoundError,
    ReleasePublishabilityError,
    ReleaseRecordConflictError,
    ReleaseRecordCorruptError,
    ReleaseSourceArtifactError,
    ReleaseStorageError,
    validate_release_id,
)
from services.character_publication.vcp_artifact import (
    BuiltVcpArtifact,
    build_verified_vchar_artifact,
)
from services.character_publication.vcp_release import compile_authoring_release
from voyage_character_platform.vchar import extract_vchar_v1

REPO_ROOT = Path(__file__).resolve().parents[2]
APPROVED_AT = datetime(2026, 3, 4, 5, 6, 7, tzinfo=timezone.utc)
PUBLISHED_1 = datetime(2027, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
PUBLISHED_2 = datetime(2028, 6, 7, 8, 9, 10, tzinfo=timezone.utc)
DECIDED_BY = "Ada  Approver "


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def semantic(name="Atlas") -> dict:
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


class Clock:
    """Returns the queued moments in order, then repeats the last."""

    def __init__(self, *moments):
        self.moments = list(moments) or [PUBLISHED_1]
        self.calls = 0

    def __call__(self):
        self.calls += 1
        return self.moments[min(self.calls, len(self.moments)) - 1]


@dataclass
class Env:
    tmp: Path
    service: CharacterLabApplicationService
    authoring: CharacterAuthoringStore
    created: object
    counter: itertools.count

    def build(self, release_id="release-one", display_name="Атлас") -> BuiltVcpArtifact:
        compilation = compile_authoring_release(
            self.authoring,
            character_id="atlas",
            version_id="version-v1",
            revision_id="revision-r1",
            snapshot_hash=self.created.snapshot_hash,
            release_id=release_id,
            display_name=display_name,
        )
        holder = self.tmp / "l3"
        holder.mkdir(exist_ok=True)
        return build_verified_vchar_artifact(compilation, holder / f"ws{next(self.counter)}")

    def store(self, *clock_moments, name="store") -> CharacterReleaseStore:
        return CharacterReleaseStore(self.tmp / name, clock=Clock(*clock_moments))


def make_env(tmp_path: Path, *, approve=True) -> Env:
    root = tmp_path / "authoring"
    service = CharacterLabApplicationService(
        CharacterLabApplicationConfig(character_authoring_root=root),
        approval_clock=lambda: APPROVED_AT,
    )
    created = service.create_character(
        character_id="atlas", version_id="version-v1", revision_id="revision-r1",
        version_label="Version 1", semantic=semantic(),
    )
    service.submit_for_approval(
        character_id="atlas", version_id="version-v1", revision_id="revision-r1",
        snapshot_hash=created.snapshot_hash,
    )
    if approve:
        service.approve_as_canon(
            character_id="atlas", version_id="version-v1", revision_id="revision-r1",
            snapshot_hash=created.snapshot_hash, decided_by=DECIDED_BY,
        )
    return Env(tmp_path, service, CharacterAuthoringStore(root), created, itertools.count())


@pytest.fixture
def env(tmp_path):
    return make_env(tmp_path)


def publish(store, env, built):
    return store.publish_release(built, authoring_store=env.authoring)


def tree(root: Path) -> dict[str, bytes | None]:
    return {
        p.relative_to(root).as_posix(): (p.read_bytes() if p.is_file() else None)
        for p in sorted(root.rglob("*"))
    }


def record_file(store, release_id="release-one") -> Path:
    return store.root / "releases" / "atlas" / f"{release_id}.json"


def artifact_file(store, package_hash) -> Path:
    return store.root / "artifacts" / f"{package_hash}.vchar"


def write_canonical(path: Path, data) -> None:
    path.write_bytes(
        (json.dumps(data, ensure_ascii=False, sort_keys=True, allow_nan=False, indent=2) + "\n")
        .encode("utf-8")
    )


def edit_record(store, release_id="release-one", **changes):
    path = record_file(store, release_id)
    data = json.loads(path.read_text(encoding="utf-8"))
    for key, value in changes.items():
        data[key] = value
    write_canonical(path, data)


def no_scratch_leftovers(store):
    scratch = store.root / "tmp"
    assert not scratch.exists() or list(scratch.iterdir()) == []
    for path in store.root.rglob(".tmp_release_*"):
        raise AssertionError(f"leftover temp file {path}")


# ===== publication ===============================================================


def test_publish_valid_built_artifact_creates_one_immutable_release(env):
    built = env.build()
    store = env.store()

    result = publish(store, env, built)

    assert result.newly_published is True
    assert result.record.character_id == "atlas" and result.record.release_id == "release-one"
    assert result.record.package_hash == built.package_hash
    assert record_file(store).is_file()
    assert result.artifact_path == artifact_file(store, built.package_hash)
    no_scratch_leftovers(store)


def test_source_artifact_size_is_verified(env):
    built = env.build()
    store = env.store()
    with built.artifact_path.open("ab") as stream:
        stream.write(b"\x00")

    with pytest.raises(ReleaseSourceArtifactError):
        publish(store, env, built)

    assert not record_file(store).exists()
    assert not (store.root / "artifacts").exists() or not list((store.root / "artifacts").iterdir())
    no_scratch_leftovers(store)


def test_source_artifact_sha_is_verified_at_equal_size(env):
    built = env.build()
    store = env.store()
    data = bytearray(built.artifact_path.read_bytes())
    data[len(data) // 2] ^= 0xFF
    built.artifact_path.write_bytes(bytes(data))

    with pytest.raises(ReleaseSourceArtifactError):
        publish(store, env, built)

    assert not record_file(store).exists()
    no_scratch_leftovers(store)


def test_missing_or_linked_source_artifact_fails(env):
    built = env.build()
    store = env.store()
    built.artifact_path.unlink()

    with pytest.raises(ReleaseSourceArtifactError):
        publish(store, env, built)


def test_source_is_reverified_through_authoritative_vcp(env, monkeypatch):
    built = env.build()
    store = env.store()
    calls = []
    real = rs.extract_vchar_v1

    def spy(archive, staging_root, *, expected_package_hash=None):
        calls.append((Path(archive), expected_package_hash))
        return real(archive, staging_root, expected_package_hash=expected_package_hash)

    monkeypatch.setattr(rs, "extract_vchar_v1", spy)

    publish(store, env, built)

    assert calls[0] == (built.artifact_path, built.package_hash)  # the source, first
    assert calls[-1] == (artifact_file(store, built.package_hash), built.package_hash)
    assert len(calls) == 2  # source + durable copy


def test_exact_bytes_are_persisted_and_verified(env):
    built = env.build()
    store = env.store()

    result = publish(store, env, built)

    source = built.artifact_path.read_bytes()
    durable = result.artifact_path.read_bytes()
    assert durable == source
    assert sha(durable) == built.artifact_sha256 == result.record.artifact_sha256
    assert len(durable) == built.byte_length == result.record.byte_length
    verified = extract_vchar_v1(
        result.artifact_path, env.tmp / "independent", expected_package_hash=built.package_hash
    )
    assert verified.metadata.character_id == built.character_id
    assert verified.metadata.release_id == built.release_id
    assert verified.package_hash == built.package_hash


def test_release_record_content_is_exact(env):
    built = env.build()
    store = env.store(PUBLISHED_1)

    publish(store, env, built)

    assert json.loads(record_file(store).read_text(encoding="utf-8")) == {
        "schema_version": "character_release_record/1.0",
        "character_id": "atlas",
        "release_id": "release-one",
        "package_hash": built.package_hash,
        "artifact_sha256": built.artifact_sha256,
        "byte_length": built.byte_length,
        "artifact_ref": f"artifacts/{built.package_hash}.vchar",
        "source": {
            "character_id": "atlas",
            "version_id": "version-v1",
            "revision_id": "revision-r1",
            "snapshot_hash": env.created.snapshot_hash,
        },
        "aggregate_candidate_id": built.aggregate_candidate_id,
        "aggregate_hash": built.aggregate_hash,
        "acceptance_record_hash": built.acceptance_record_hash,
        "approval": {
            "decision": "HUMAN_APPROVED",
            "decided_by": DECIDED_BY,
            "decided_at": "2026-03-04T05:06:07Z",
        },
        "published_at": "2027-01-02T03:04:05Z",
    }
    raw = record_file(store).read_bytes()
    assert raw.endswith(b"\n") and b"\r" not in raw


def test_published_at_is_a_lab_time_distinct_from_approval_time(env):
    built = env.build()
    store = env.store(PUBLISHED_1)

    record = publish(store, env, built).record

    assert record.published_at == "2027-01-02T03:04:05Z"
    assert record.approval.decided_at == "2026-03-04T05:06:07Z"
    assert env.authoring.load_approval_evidence(
        "atlas", "version-v1", "revision-r1"
    ).decided_at == "2026-03-04T05:06:07Z"  # evidence itself untouched


def test_published_at_is_captured_exactly_once(env):
    clock = Clock(PUBLISHED_1, PUBLISHED_2)
    store = CharacterReleaseStore(env.tmp / "store", clock=clock)

    publish(store, env, env.build())

    assert clock.calls == 1


def test_exact_republish_is_idempotent_and_keeps_original_published_at(env):
    built = env.build()
    clock = Clock(PUBLISHED_1, PUBLISHED_2)
    store = CharacterReleaseStore(env.tmp / "store", clock=clock)
    first = publish(store, env, built)
    before = tree(store.root)

    again = publish(store, env, built)

    assert again.newly_published is False
    assert again.record == first.record
    assert again.record.published_at == "2027-01-02T03:04:05Z"
    assert clock.calls == 1  # no second publication timestamp was even requested
    assert tree(store.root) == before  # nothing changed on disk


def test_exact_retry_from_a_rebuilt_but_identical_artifact_is_idempotent(env):
    store = env.store(PUBLISHED_1, PUBLISHED_2)
    first = publish(store, env, env.build())

    again = publish(store, env, env.build())  # a fresh L3 build of the same release

    assert again.newly_published is False and again.record == first.record


def test_same_release_id_with_a_different_package_hash_is_a_collision(env):
    store = env.store()
    first = publish(store, env, env.build(display_name="Первый"))
    other = env.build(display_name="Второй")
    before = tree(store.root)

    with pytest.raises(ReleaseIdHashCollisionError) as excinfo:
        publish(store, env, other)

    assert excinfo.value.code == "RELEASE_ID_HASH_COLLISION"
    assert other.package_hash != first.record.package_hash
    assert tree(store.root) == before  # nothing written, nothing overwritten
    assert not artifact_file(store, other.package_hash).exists()


def test_same_hash_with_conflicting_immutable_fields_fails_closed(env):
    built = env.build()
    store = env.store()
    publish(store, env, built)
    edit_record(store, aggregate_candidate_id="vcprec1-" + "0" * 64)
    before = record_file(store).read_bytes()

    with pytest.raises(ReleaseRecordConflictError):
        publish(store, env, built)

    assert record_file(store).read_bytes() == before


def test_historical_approval_without_evidence_cannot_publish(env):
    built = env.build()
    store = env.store()
    shutil.rmtree(env.authoring.root / "atlas" / "versions" / "version-v1" / "approvals")

    with pytest.raises(ReleasePublishabilityError) as excinfo:
        publish(store, env, built)

    assert "evidence" in str(excinfo.value)
    assert not record_file(store).exists()
    assert not (store.root / "artifacts").exists()


def test_pending_approval_with_existing_evidence_cannot_publish(tmp_path):
    env = make_env(tmp_path, approve=False)
    record = env.authoring.load_revision("atlas", "version-v1", "revision-r1")
    env.authoring.persist_approval_evidence(
        ApprovalEvidence(
            "atlas", "version-v1", "revision-r1", record.snapshot_hash,
            DECIDED_BY, "2026-03-04T05:06:07Z",
        )
    )
    assert env.authoring.read_version_pointer(
        "atlas", "version-v1"
    ).lifecycle_state is LifecycleState.PENDING_APPROVAL
    built = env.build()  # L2/L3 are pure and deliberately do not gate on lifecycle
    store = env.store()

    with pytest.raises(ReleasePublishabilityError) as excinfo:
        publish(store, env, built)

    assert "PENDING_APPROVAL" in str(excinfo.value)
    assert not record_file(store).exists()


def test_wrong_selected_revision_cannot_publish(env):
    built = env.build()
    store = env.store()
    env.authoring.persist_revision("atlas", "version-v1", "revision-r2", semantic("Other"))
    pointer = env.authoring.read_version_pointer("atlas", "version-v1")
    env.authoring.update_version_pointer(replace(pointer, selected_revision_id="revision-r2"))

    with pytest.raises(ReleasePublishabilityError):
        publish(store, env, built)

    assert not record_file(store).exists()


def test_wrong_snapshot_or_approval_lineage_cannot_publish(env):
    built = env.build()
    store = env.store()
    wrong_source = SourceProvenance("atlas", "version-v1", "revision-r1", "e" * 64)
    other_approval = replace(built.approval, decided_by="Someone Else")

    with pytest.raises(ReleasePublishabilityError):
        publish(store, env, replace(built, source=wrong_source))
    with pytest.raises(ReleasePublishabilityError):
        publish(store, env, replace(built, approval=other_approval))

    assert not record_file(store).exists()


def test_copy_failure_creates_no_release_record_and_no_partial_artifact(env, monkeypatch):
    built = env.build()
    store = env.store()

    def failing_copy(source, temp_path):
        temp_path.write_bytes(b"partial")
        raise OSError("simulated disk failure")

    monkeypatch.setattr(rs, "_stream_copy", failing_copy)

    with pytest.raises(ReleaseStorageError):
        publish(store, env, built)

    assert not record_file(store).exists()
    assert not artifact_file(store, built.package_hash).exists()
    no_scratch_leftovers(store)


def test_orphan_exact_artifact_is_reused_on_retry(env, monkeypatch):
    built = env.build()
    store = env.store(PUBLISHED_1)
    real_commit = CharacterReleaseStore._commit_record

    def failing_commit(self, record):
        raise OSError("simulated record write failure")

    monkeypatch.setattr(CharacterReleaseStore, "_commit_record", failing_commit)
    with pytest.raises(ReleaseStorageError):
        publish(store, env, built)
    assert artifact_file(store, built.package_hash).is_file()  # orphan, harmless
    assert not record_file(store).exists()  # no release exists yet
    orphan = artifact_file(store, built.package_hash).read_bytes()

    monkeypatch.setattr(CharacterReleaseStore, "_commit_record", real_commit)
    copies = []
    real_copy = rs._stream_copy
    monkeypatch.setattr(rs, "_stream_copy", lambda s, t: copies.append(1) or real_copy(s, t))
    result = publish(store, env, built)

    assert result.newly_published is True and record_file(store).is_file()
    assert copies == []  # the exact orphan was reused, not copied again
    assert artifact_file(store, built.package_hash).read_bytes() == orphan


def test_corrupt_preexisting_durable_artifact_fails_closed(env):
    built = env.build()
    store = env.store()
    target = artifact_file(store, built.package_hash)
    target.parent.mkdir(parents=True)
    target.write_bytes(b"garbage, not a vchar")

    with pytest.raises(DurableArtifactCorruptError):
        publish(store, env, built)

    assert target.read_bytes() == b"garbage, not a vchar"  # never overwritten
    assert not record_file(store).exists()


# -- OD-LAB-L4-DURABILITY-01: a committed release's artifact is never restored --------


def test_committed_release_with_missing_artifact_fails_closed_and_is_not_restored(
    env, monkeypatch
):
    built = env.build()
    store = env.store(PUBLISHED_1, PUBLISHED_2)
    first = publish(store, env, built)
    artifact_file(store, first.record.package_hash).unlink()
    record_before = record_file(store).read_bytes()
    copies = []
    real_copy = rs._stream_copy
    monkeypatch.setattr(rs, "_stream_copy", lambda s, t: copies.append(1) or real_copy(s, t))

    with pytest.raises(DurableArtifactCorruptError):
        publish(store, env, built)  # the source is healthy, and must NOT be copied back

    assert copies == []
    assert not artifact_file(store, first.record.package_hash).exists()
    assert record_file(store).read_bytes() == record_before
    no_scratch_leftovers(store)


@pytest.mark.parametrize("damage", ["garbage", "flipped_byte", "truncated", "extended"])
def test_committed_release_with_corrupt_artifact_fails_closed_and_is_not_replaced(
    env, damage
):
    built = env.build()
    store = env.store()
    record = publish(store, env, built).record
    path = artifact_file(store, record.package_hash)
    original = path.read_bytes()
    damaged = {
        "garbage": b"garbage, not a vchar",
        "flipped_byte": original[:20] + bytes([original[20] ^ 0xFF]) + original[21:],
        "truncated": original[:-1],
        "extended": original + b"\x00",
    }[damage]
    path.write_bytes(damaged)
    record_before = record_file(store).read_bytes()

    with pytest.raises(DurableArtifactCorruptError):
        publish(store, env, built)

    assert path.read_bytes() == damaged  # no replacement occurred
    assert record_file(store).read_bytes() == record_before


def test_healthy_committed_release_republish_stays_idempotent(env):
    built = env.build()
    store = env.store(PUBLISHED_1, PUBLISHED_2)
    first = publish(store, env, built)

    again = publish(store, env, built)

    assert again.newly_published is False
    assert again.record.published_at == first.record.published_at == "2027-01-02T03:04:05Z"
    assert again.artifact_path == first.artifact_path


def test_pre_commit_orphan_exact_artifact_may_be_reused_and_then_committed(env):
    built = env.build()
    store = env.store(PUBLISHED_1)
    target = artifact_file(store, built.package_hash)
    target.parent.mkdir(parents=True)
    shutil.copyfile(built.artifact_path, target)  # exact orphan, no record yet
    assert not record_file(store).exists()

    result = publish(store, env, built)

    assert result.newly_published is True and record_file(store).is_file()
    assert target.read_bytes() == built.artifact_path.read_bytes()


def test_publish_never_rebuilds_or_rematerializes(env, monkeypatch):
    built = env.build()
    store = env.store()

    def forbidden(*_a, **_k):
        raise AssertionError("LAB-L4 must never rebuild")

    import voyage_character_platform.package_v1 as vcp_pkg
    import voyage_character_platform.vchar as vcp_vchar

    monkeypatch.setattr(vcp_release, "compile_authoring_release", forbidden)
    monkeypatch.setattr(vcp_release, "build_authoring_release_compilation", forbidden)
    monkeypatch.setattr(vcp_artifact, "build_verified_vchar_artifact", forbidden)
    monkeypatch.setattr(vcp_artifact, "materialize_package_v1", forbidden)
    monkeypatch.setattr(vcp_artifact, "write_vchar_v1", forbidden)
    monkeypatch.setattr(vcp_pkg, "materialize_package_v1", forbidden)
    monkeypatch.setattr(vcp_vchar, "write_vchar_v1", forbidden)

    publish(store, env, built)
    store.set_canonical_current("atlas", "release-one")
    store.export_release("atlas", "release-one", env.tmp / "exported.vchar")


def test_module_imports_no_compiler_builder_or_archive_writer():
    source = (REPO_ROOT / "services" / "character_publication" / "release_store.py").read_text(
        encoding="utf-8"
    )
    imported = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.update(alias.name for alias in node.names)
            imported.add(node.module)
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
    for forbidden in (
        "compile_authoring_release", "build_authoring_release_compilation",
        "compile_authoring_revision_to_vcp_domains", "materialize_package_v1",
        "write_vchar_v1", "build_verified_vchar_artifact", "zipfile", "struct", "zlib",
        "canonical_json_bytes", "create_manifest",
    ):
        assert forbidden not in imported


def test_durable_state_does_not_depend_on_the_l3_workspace(env):
    built = env.build()
    store = env.store()
    publish(store, env, built)
    shutil.rmtree(built.workspace_root)

    verified = store.verify_release("atlas", "release-one")

    assert verified.artifact_path.is_file()
    assert built.workspace_root not in verified.artifact_path.parents


def test_invalid_inputs_are_rejected(env, tmp_path):
    store = env.store()
    with pytest.raises(ReleaseInputError):
        store.publish_release("not built", authoring_store=env.authoring)  # type: ignore[arg-type]
    with pytest.raises(ReleaseInputError):
        store.publish_release(env.build(), authoring_store="nope")  # type: ignore[arg-type]
    with pytest.raises(ReleaseInputError):
        CharacterReleaseStore("relative/store")
    with pytest.raises(ReleaseInputError):
        CharacterReleaseStore(tmp_path / "a" / ".." / "b")


@pytest.mark.parametrize("bad", [None, 3, "", " v1", "v 1", "a/b", "a\\b", "../x", ".hidden",
                                 "con", "NUL", "v1\n", "ве", "x" * 129])
def test_invalid_release_ids_are_rejected(bad):
    with pytest.raises(ReleaseInputError):
        validate_release_id(bad)


@pytest.mark.parametrize("ok", ["v1", "release-2026.03", "A_b-c.9"])
def test_valid_release_ids_are_accepted(ok):
    assert validate_release_id(ok) == ok


def test_release_ids_differing_only_by_case_are_refused(env):
    store = env.store()
    publish(store, env, env.build(release_id="Rel-One"))
    other = env.build(release_id="rel-one", display_name="Другой")

    with pytest.raises(ReleaseRecordConflictError):
        publish(store, env, other)


# ===== canonical current / history / rollback ===================================


def two_releases(env, store):
    a = publish(store, env, env.build(release_id="release-a")).record
    b = publish(store, env, env.build(release_id="release-b")).record
    return a, b


def test_publication_does_not_auto_set_current(env):
    store = env.store()

    two_releases(env, store)

    assert store.get_canonical_current("atlas") is None
    assert store.read_designation_history("atlas") == ()
    assert not (store.root / "current").exists() and not (store.root / "history").exists()


def test_explicit_set_current_works_and_stores_only_the_pointer(env):
    store = env.store(PUBLISHED_1, PUBLISHED_2)
    a, _b = two_releases(env, store)

    current = store.set_canonical_current("atlas", "release-a")

    assert current == CanonicalCurrent("atlas", "release-a", a.package_hash, 1)
    assert store.get_canonical_current("atlas") == current
    pointer = json.loads((store.root / "current" / "atlas.json").read_text(encoding="utf-8"))
    assert pointer == {
        "schema_version": "character_current_release/1.0",
        "character_id": "atlas", "release_id": "release-a",
        "package_hash": a.package_hash, "generation": 1,
    }


def test_target_artifact_is_reverified_before_current_changes(env, monkeypatch):
    store = env.store()
    a, _b = two_releases(env, store)
    calls = []
    real = rs.extract_vchar_v1
    monkeypatch.setattr(
        rs, "extract_vchar_v1",
        lambda archive, staging, *, expected_package_hash=None: (
            calls.append(expected_package_hash) or real(archive, staging, expected_package_hash=expected_package_hash)
        ),
    )

    store.set_canonical_current("atlas", "release-a")

    assert calls == [a.package_hash]


def test_tampered_target_artifact_cannot_become_current(env):
    store = env.store()
    a, _b = two_releases(env, store)
    path = artifact_file(store, a.package_hash)
    data = bytearray(path.read_bytes())
    data[len(data) // 2] ^= 0xFF
    path.write_bytes(bytes(data))

    with pytest.raises(DurableArtifactCorruptError):
        store.set_canonical_current("atlas", "release-a")

    assert store.get_canonical_current("atlas") is None
    assert not (store.root / "history").exists()


def test_missing_release_cannot_become_current(env):
    store = env.store()

    with pytest.raises(ReleaseNotFoundError):
        store.set_canonical_current("atlas", "no-such-release")

    assert store.get_canonical_current("atlas") is None


def test_corrupt_release_record_cannot_become_current(env):
    store = env.store()
    two_releases(env, store)
    record_file(store, "release-a").write_text("{corrupt", encoding="utf-8")

    with pytest.raises(ReleaseRecordCorruptError):
        store.set_canonical_current("atlas", "release-a")

    assert store.get_canonical_current("atlas") is None


def test_exact_set_current_noop_is_idempotent_and_adds_no_history(env):
    clock = Clock(PUBLISHED_1, PUBLISHED_2)
    store = CharacterReleaseStore(env.tmp / "store", clock=clock)
    two_releases(env, store)
    calls_after_publish = clock.calls

    first = store.set_canonical_current("atlas", "release-a")
    again = store.set_canonical_current("atlas", "release-a")

    assert first == again and again.generation == 1
    assert len(store.read_designation_history("atlas")) == 1
    assert clock.calls == calls_after_publish + 1  # one designation, one timestamp


def test_generations_history_and_rollback(env):
    store = env.store()
    a, b = two_releases(env, store)

    g1 = store.set_canonical_current("atlas", "release-a")
    g2 = store.set_canonical_current("atlas", "release-b")
    g3 = store.set_canonical_current("atlas", "release-a")  # rollback B -> A

    assert (g1.generation, g2.generation, g3.generation) == (1, 2, 3)
    history = store.read_designation_history("atlas")
    assert [(e.generation, e.from_release_id, e.to_release_id) for e in history] == [
        (1, None, "release-a"), (2, "release-a", "release-b"), (3, "release-b", "release-a"),
    ]
    assert history[0].from_package_hash is None
    assert (history[1].from_package_hash, history[1].to_package_hash) == (a.package_hash, b.package_hash)
    assert (history[2].from_package_hash, history[2].to_package_hash) == (b.package_hash, a.package_hash)
    assert store.get_canonical_current("atlas") == g3
    assert g3.release_id == "release-a" and g3.package_hash == a.package_hash


def test_designation_never_mutates_releases_or_artifacts(env):
    store = env.store()
    two_releases(env, store)
    before = {**tree(store.root / "releases"), **tree(store.root / "artifacts")}

    store.set_canonical_current("atlas", "release-a")
    store.set_canonical_current("atlas", "release-b")
    store.set_canonical_current("atlas", "release-a")

    after = {**tree(store.root / "releases"), **tree(store.root / "artifacts")}
    assert after == before


def test_history_entries_are_write_once_records(env):
    store = env.store(PUBLISHED_1, PUBLISHED_2)
    two_releases(env, store)
    store.set_canonical_current("atlas", "release-a")
    entry_path = store.root / "history" / "atlas" / "00000001.json"
    raw = entry_path.read_bytes()

    store.set_canonical_current("atlas", "release-b")

    assert entry_path.read_bytes() == raw
    assert sorted(p.name for p in entry_path.parent.iterdir()) == [
        "00000001.json", "00000002.json"
    ]


def test_pointer_write_failure_leaves_previous_current_valid_and_is_recoverable(env, monkeypatch):
    store = env.store()
    a, b = two_releases(env, store)
    store.set_canonical_current("atlas", "release-a")
    history_before = store.read_designation_history("atlas")
    real = rs._atomic_replace_json

    def failing(target, data):
        if target.parent.name == "current":
            raise OSError("simulated pointer failure")
        return real(target, data)

    monkeypatch.setattr(rs, "_atomic_replace_json", failing)
    with pytest.raises(CurrentDesignationError):
        store.set_canonical_current("atlas", "release-b")

    monkeypatch.setattr(rs, "_atomic_replace_json", real)
    assert store.get_canonical_current("atlas").release_id == "release-a"  # previous valid
    assert store.read_designation_history("atlas") == history_before  # committed unchanged
    pending = store.pending_designation("atlas")
    assert pending is not None and pending.generation == 2 and pending.to_release_id == "release-b"
    # Releases and artifacts are untouched by the failed designation.
    assert store.verify_release("atlas", "release-a").record == a
    assert store.verify_release("atlas", "release-b").record == b

    retry = store.set_canonical_current("atlas", "release-b")  # same target completes it

    assert retry.generation == 2 and retry.release_id == "release-b"
    assert store.pending_designation("atlas") is None
    assert len(store.read_designation_history("atlas")) == 2  # no duplicate generation


def test_pending_claim_is_rolled_forward_before_a_different_request(env, monkeypatch):
    store = env.store()
    two_releases(env, store)
    store.set_canonical_current("atlas", "release-a")
    real = rs._atomic_replace_json
    monkeypatch.setattr(
        rs, "_atomic_replace_json",
        lambda target, data: (_ for _ in ()).throw(OSError("boom")) if target.parent.name == "current" else real(target, data),
    )
    with pytest.raises(CurrentDesignationError):
        store.set_canonical_current("atlas", "release-b")
    monkeypatch.setattr(rs, "_atomic_replace_json", real)

    final = store.set_canonical_current("atlas", "release-a")  # a different request

    history = store.read_designation_history("atlas")
    assert [e.to_release_id for e in history] == ["release-a", "release-b", "release-a"]
    assert final.generation == 3 and final.release_id == "release-a"


def test_claim_write_failure_changes_nothing(env, monkeypatch):
    store = env.store()
    two_releases(env, store)
    store.set_canonical_current("atlas", "release-a")
    before = tree(store.root)
    real = rs._write_once_json
    monkeypatch.setattr(
        rs, "_write_once_json",
        lambda target, data: (_ for _ in ()).throw(OSError("boom")) if target.parent.name == "atlas" and "history" in target.parts else real(target, data),
    )

    with pytest.raises(CurrentDesignationError):
        store.set_canonical_current("atlas", "release-b")

    monkeypatch.setattr(rs, "_write_once_json", real)
    assert tree(store.root) == before
    assert store.get_canonical_current("atlas").release_id == "release-a"
    assert store.pending_designation("atlas") is None


# -- OD-LAB-L4-DESIGNATION-TX-01: per-character cross-process designation lock ----


def assert_linear_state(store, character_id="atlas"):
    """Pointer, history and pending agree; generations are contiguous."""

    current = store.get_canonical_current(character_id)
    history = store.read_designation_history(character_id)
    assert store.pending_designation(character_id) is None
    assert [e.generation for e in history] == list(range(1, len(history) + 1))
    assert current is None if not history else current.generation == len(history)
    if history:
        assert (current.release_id, current.package_hash) == (
            history[-1].to_release_id, history[-1].to_package_hash)
    return current, history


def leave_pending_claim(store, monkeypatch, release_id):
    """Fail the pointer write once so a designation claim stays pending."""

    real = rs._atomic_replace_json

    def failing(target, data):
        if target.parent.name == "current":
            raise OSError("simulated crash before the pointer commit")
        return real(target, data)

    monkeypatch.setattr(rs, "_atomic_replace_json", failing)
    with pytest.raises(CurrentDesignationError):
        store.set_canonical_current("atlas", release_id)
    monkeypatch.setattr(rs, "_atomic_replace_json", real)
    assert store.pending_designation("atlas") is not None


def start_child(code, *args):
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8",
                       PYTHONPATH=os.pathsep.join(p for p in sys.path if p))
    return subprocess.Popen(
        [sys.executable, "-B", "-c", code, *map(str, args)], cwd=REPO_ROOT, env=environment,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )


DESIGNATE_CHILD = (
    "import json, os, sys, time\n"
    "from services.character_publication.release_store import (\n"
    "    CharacterReleaseStore, CharacterReleaseStoreError)\n"
    "root, release_id, gate = sys.argv[1], sys.argv[2], sys.argv[3]\n"
    "store = CharacterReleaseStore(root)\n"
    "while not os.path.exists(gate):\n"
    "    time.sleep(0.002)\n"
    "try:\n"
    "    current = store.set_canonical_current('atlas', release_id)\n"
    "    print(json.dumps({'ok': True, 'generation': current.generation,\n"
    "                      'release_id': current.release_id}))\n"
    "except CharacterReleaseStoreError as exc:\n"
    "    print(json.dumps({'ok': False, 'code': exc.code, 'message': str(exc)}))\n"
)

HOLD_LOCK_CHILD = (
    "import sys\n"
    "from services.character_publication.release_store import CharacterReleaseStore\n"
    "store = CharacterReleaseStore(sys.argv[1])\n"
    "with store._designation_lock(sys.argv[2]):\n"
    "    print('LOCKED', flush=True)\n"
    "    sys.stdin.readline()\n"
)


def run_designators(env, store, targets):
    gate = env.tmp / "gate"
    children = [start_child(DESIGNATE_CHILD, store.root, rid, gate) for rid in targets]
    gate.write_text("go")  # release every child together once all are started
    results = []
    for child in children:
        stdout, stderr = child.communicate(timeout=180)
        assert child.returncode == 0, stderr
        results.append(json.loads(stdout.strip().splitlines()[-1]))
    return results


def test_stale_pending_roll_forward_cannot_regress_a_newer_generation(env, monkeypatch):
    """The race found by independent review, made deterministic.

    T1 rolls a pending claim (B, generation 2) forward and is paused right before
    its pointer write. T2 then designates A (generation 3). Without serialization
    T1 resumes and overwrites the pointer with generation 2 after T2 succeeded.
    """

    store = env.store()
    two_releases(env, store)
    store.set_canonical_current("atlas", "release-a")
    leave_pending_claim(store, monkeypatch, "release-b")
    real = rs._atomic_replace_json
    t1_at_write, t2_done = threading.Event(), threading.Event()
    results, errors = {}, {}

    def gated(target, data):
        if (target.parent.name == "current" and data["generation"] == 2
                and threading.current_thread().name == "t1"):
            t1_at_write.set()
            t2_done.wait(timeout=2.0)  # only opens early if T2 is NOT serialized behind T1
        return real(target, data)

    monkeypatch.setattr(rs, "_atomic_replace_json", gated)

    def designate(name, release_id):
        try:
            results[name] = store.set_canonical_current("atlas", release_id)
        except CharacterReleaseStoreError as exc:
            errors[name] = exc
        finally:
            if name == "t2":
                t2_done.set()

    t1 = threading.Thread(target=designate, args=("t1", "release-b"), name="t1")
    t2 = threading.Thread(target=designate, args=("t2", "release-a"), name="t2")
    t1.start()
    assert t1_at_write.wait(timeout=30)
    t2.start()
    t1.join(timeout=60)
    t2.join(timeout=60)

    assert errors == {}
    assert results["t1"].generation == 2 and results["t1"].release_id == "release-b"
    assert results["t2"].generation == 3 and results["t2"].release_id == "release-a"
    current, history = assert_linear_state(store)
    assert [e.to_release_id for e in history] == ["release-a", "release-b", "release-a"]
    assert current.generation == 3  # no lower generation overwrote a higher one


def test_simultaneous_same_target_roll_forward_completes_once(env, monkeypatch):
    store = env.store()
    two_releases(env, store)
    store.set_canonical_current("atlas", "release-a")
    leave_pending_claim(store, monkeypatch, "release-b")
    writes = []
    real = CharacterReleaseStore._write_pointer

    def counting(self, character_id, entry):
        writes.append(entry.generation)
        return real(self, character_id, entry)

    monkeypatch.setattr(CharacterReleaseStore, "_write_pointer", counting)
    barrier = threading.Barrier(3, timeout=30)

    def designate():
        barrier.wait()
        return store.set_canonical_current("atlas", "release-b")

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = [f.result(timeout=90) for f in [pool.submit(designate) for _ in range(3)]]

    assert {(r.generation, r.release_id) for r in results} == {(2, "release-b")}
    assert writes == [2]  # the pending claim was completed exactly once, logically
    current, history = assert_linear_state(store)
    assert current.generation == 2 and len(history) == 2


def test_simultaneous_same_target_designation_is_idempotent(env):
    store = env.store()
    two_releases(env, store)
    barrier = threading.Barrier(4, timeout=30)

    def designate():
        barrier.wait()
        return store.set_canonical_current("atlas", "release-a")

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = [f.result(timeout=90) for f in [pool.submit(designate) for _ in range(4)]]

    assert {(r.generation, r.release_id) for r in results} == {(1, "release-a")}
    assert len(assert_linear_state(store)[1]) == 1


def test_simultaneous_different_targets_serialize_into_a_valid_total_order(env):
    store = env.store()
    two_releases(env, store)
    barrier = threading.Barrier(6, timeout=30)
    targets = ["release-a", "release-b"] * 3

    def designate(release_id):
        barrier.wait()
        return store.set_canonical_current("atlas", release_id)

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = [f.result(timeout=120) for f in [pool.submit(designate, t) for t in targets]]

    current, history = assert_linear_state(store)
    for result in results:  # every returned value is a committed, ordered state
        assert history[result.generation - 1].to_release_id == result.release_id
    assert [e.generation for e in history] == list(range(1, len(history) + 1))
    for earlier, later in zip(history, history[1:]):
        assert (later.from_release_id, later.from_package_hash) == (
            earlier.to_release_id, earlier.to_package_hash)
        assert later.to_release_id != later.from_release_id  # only actual changes recorded
    assert 2 <= len(history) <= 6 and current.generation == len(history)


def test_cross_process_designators_are_serialized_by_the_os_lock(env):
    store = env.store()
    two_releases(env, store)

    results = run_designators(env, store, ["release-a", "release-b", "release-a", "release-b"])

    assert all(r["ok"] for r in results), results
    current, history = assert_linear_state(store)
    for result in results:
        assert history[result["generation"] - 1].to_release_id == result["release_id"]
    assert len(history) >= 2 and current.generation == len(history)


def test_cross_process_same_target_converges_to_one_history_entry(env):
    store = env.store()
    two_releases(env, store)

    results = run_designators(env, store, ["release-a"] * 3)

    assert [r["ok"] for r in results] == [True] * 3
    assert {(r["generation"], r["release_id"]) for r in results} == {(1, "release-a")}
    assert len(assert_linear_state(store)[1]) == 1


def test_cross_process_lock_blocks_designation_and_a_dead_holder_releases_it(
    env, monkeypatch
):
    store = env.store()
    two_releases(env, store)
    store.set_canonical_current("atlas", "release-a")
    before = tree(store.root / "releases") | tree(store.root / "artifacts")
    holder = start_child(HOLD_LOCK_CHILD, store.root, "atlas")
    try:
        assert holder.stdout.readline().strip() == "LOCKED"
        monkeypatch.setattr(rs, "_LOCK_TIMEOUT_SECONDS", 0.3)

        with pytest.raises(CurrentDesignationError) as excinfo:
            store.set_canonical_current("atlas", "release-b")

        assert "timed out" in str(excinfo.value)
        # Lock failure mutated nothing; readers take no lock and still work.
        assert store.get_canonical_current("atlas").release_id == "release-a"
        assert len(store.read_designation_history("atlas")) == 1
        assert store.pending_designation("atlas") is None
        assert tree(store.root / "releases") | tree(store.root / "artifacts") == before
    finally:
        holder.kill()  # the holder dies without releasing anything itself
        holder.communicate(timeout=30)

    monkeypatch.setattr(rs, "_LOCK_TIMEOUT_SECONDS", 30.0)
    assert store.set_canonical_current("atlas", "release-b").generation == 2  # OS released it


def test_different_characters_do_not_block_each_other(env, monkeypatch):
    store = env.store()
    two_releases(env, store)
    monkeypatch.setattr(rs, "_LOCK_TIMEOUT_SECONDS", 0.3)
    with store._designation_lock("atlas"):
        with store._designation_lock("someone-else"):  # independent lock, immediate
            pass
        # Another character proceeds to its own semantic checks (no lock timeout).
        with pytest.raises(ReleaseNotFoundError):
            store.set_canonical_current("someone-else", "no-such-release")
        with pytest.raises(CurrentDesignationError) as blocked:
            store.set_canonical_current("atlas", "release-a")
        assert "timed out" in str(blocked.value)
        assert store.get_canonical_current("atlas") is None  # readers are not blocked


def test_failed_designation_releases_the_lock_and_later_designation_proceeds(
    env, monkeypatch
):
    store = env.store()
    two_releases(env, store)
    store.set_canonical_current("atlas", "release-a")
    monkeypatch.setattr(rs, "_LOCK_TIMEOUT_SECONDS", 0.3)
    leave_pending_claim(store, monkeypatch, "release-b")  # a designation failed mid-way

    with store._designation_lock("atlas"):  # immediately available: nothing leaked
        pass
    assert store.set_canonical_current("atlas", "release-b").generation == 2
    assert_linear_state(store)


def test_exception_inside_the_lock_releases_it(env, monkeypatch):
    store = env.store()
    monkeypatch.setattr(rs, "_LOCK_TIMEOUT_SECONDS", 0.3)

    with pytest.raises(RuntimeError):
        with store._designation_lock("atlas"):
            raise RuntimeError("boom")

    with store._designation_lock("atlas"):
        pass


def test_lock_file_is_coordination_state_and_persists(env):
    store = env.store()
    two_releases(env, store)
    lock_file = store.root / "locks" / "atlas.lock"

    store.set_canonical_current("atlas", "release-a")

    assert lock_file.is_file() and lock_file.read_bytes() == b""
    store.set_canonical_current("atlas", "release-b")
    assert lock_file.is_file()  # never deleted merely because a designation completed
    assert "lock" not in json.dumps(
        [e.to_dict() for e in store.read_designation_history("atlas")]
    ).lower()


@pytest.mark.parametrize("kind", ["directory", "locks_is_a_file"])
def test_invalid_lock_path_fails_closed_without_mutation(env, kind):
    store = env.store()
    two_releases(env, store)
    if kind == "directory":
        (store.root / "locks" / "atlas.lock").mkdir(parents=True)
    else:
        (store.root / "locks").write_bytes(b"not a directory")
    before = tree(store.root / "releases") | tree(store.root / "artifacts")

    with pytest.raises(CurrentDesignationError):
        store.set_canonical_current("atlas", "release-a")

    assert not (store.root / "current").exists() and not (store.root / "history").exists()
    assert tree(store.root / "releases") | tree(store.root / "artifacts") == before
    no_scratch_leftovers(store)


def test_success_is_never_returned_unless_the_designation_actually_committed(env, monkeypatch):
    store = env.store()
    two_releases(env, store)
    store.set_canonical_current("atlas", "release-a")
    real = rs._atomic_replace_json
    # A pointer write that silently does nothing (a lost update) must not look like success.
    monkeypatch.setattr(
        rs, "_atomic_replace_json",
        lambda target, data: None if target.parent.name == "current" else real(target, data),
    )

    with pytest.raises(CurrentDesignationError):
        store.set_canonical_current("atlas", "release-b")

    monkeypatch.setattr(rs, "_atomic_replace_json", real)
    assert store.get_canonical_current("atlas").release_id == "release-a"


def test_non_regular_lock_paths_are_refused_by_the_lock_itself(tmp_path):
    with pytest.raises(CurrentDesignationError):
        rs._DesignationLock._require_regular(os.stat(tmp_path))  # a directory
    regular = tmp_path / "file"
    regular.write_bytes(b"")
    rs._DesignationLock._require_regular(os.stat(regular))  # a regular file is fine


def test_symlinked_lock_path_is_refused(env):
    store = env.store()
    two_releases(env, store)
    target = env.tmp / "elsewhere.lock"
    target.write_bytes(b"")
    (store.root / "locks").mkdir()
    try:
        os.symlink(target, store.root / "locks" / "atlas.lock")
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is not permitted in this environment")

    with pytest.raises(CurrentDesignationError):
        store.set_canonical_current("atlas", "release-a")

    assert not (store.root / "history").exists() and not (store.root / "current").exists()


def test_out_of_order_pending_completion_is_refused(env, monkeypatch):
    store = env.store()
    two_releases(env, store)
    store.set_canonical_current("atlas", "release-a")
    leave_pending_claim(store, monkeypatch, "release-b")
    pending = store.pending_designation("atlas")

    with pytest.raises(CurrentDesignationError):
        store._complete_pending("atlas", None, pending)  # claims generation 2 with no generation 1

    assert store.get_canonical_current("atlas").generation == 1  # pointer untouched


def test_designation_after_success_is_never_exposed_as_an_older_generation(env):
    store = env.store()
    two_releases(env, store)
    seen = []
    for release_id in ("release-a", "release-b", "release-a", "release-b"):
        returned = store.set_canonical_current("atlas", release_id)
        seen.append(returned.generation)
        assert store.get_canonical_current("atlas") == returned  # never an older state
    assert seen == [1, 2, 3, 4]


def test_gap_in_history_is_detected_even_beyond_the_pointer(env):
    store = env.store()
    a, b = two_releases(env, store)
    store.set_canonical_current("atlas", "release-a")  # pointer at generation 1
    history_dir = store.root / "history" / "atlas"
    stray = json.loads((history_dir / "00000001.json").read_text(encoding="utf-8"))
    stray.update(generation=3, from_release_id="release-a", from_package_hash=a.package_hash,
                 to_release_id="release-b", to_package_hash=b.package_hash)
    write_canonical(history_dir / "00000003.json", stray)  # 1, 3: generation 2 missing

    with pytest.raises(CurrentDesignationError):
        store.get_canonical_current("atlas")


@pytest.mark.parametrize("scenario", ["ahead", "wrong_target", "gap", "broken_chain", "two_pending"])
def test_history_and_current_disagreement_is_detected(env, scenario):
    store = env.store()
    a, b = two_releases(env, store)
    store.set_canonical_current("atlas", "release-a")
    store.set_canonical_current("atlas", "release-b")
    pointer_path = store.root / "current" / "atlas.json"
    history_dir = store.root / "history" / "atlas"
    pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    if scenario == "ahead":
        pointer["generation"] = 5
        write_canonical(pointer_path, pointer)
    elif scenario == "wrong_target":
        pointer.update(release_id="release-a", package_hash=a.package_hash)
        write_canonical(pointer_path, pointer)
    elif scenario == "gap":
        (history_dir / "00000001.json").unlink()
    elif scenario == "broken_chain":
        entry = json.loads((history_dir / "00000002.json").read_text(encoding="utf-8"))
        entry.update(from_release_id="release-b", from_package_hash=b.package_hash)
        write_canonical(history_dir / "00000002.json", entry)
    else:
        pointer.update(generation=1, release_id="release-a", package_hash=a.package_hash)
        write_canonical(pointer_path, pointer)
        third = json.loads((history_dir / "00000002.json").read_text(encoding="utf-8"))
        third.update(generation=3, from_release_id="release-b", from_package_hash=b.package_hash,
                     to_release_id="release-a", to_package_hash=a.package_hash)
        write_canonical(history_dir / "00000003.json", third)

    with pytest.raises(CurrentDesignationError):
        store.get_canonical_current("atlas")
    with pytest.raises(CurrentDesignationError):
        store.set_canonical_current("atlas", "release-a")


def test_current_pointing_at_a_missing_release_is_detected(env):
    store = env.store()
    two_releases(env, store)
    store.set_canonical_current("atlas", "release-a")
    record_file(store, "release-a").unlink()

    with pytest.raises(CurrentDesignationError):
        store.get_canonical_current("atlas")


def test_current_pointing_at_a_mismatched_release_is_detected(env):
    store = env.store()
    a, b = two_releases(env, store)
    store.set_canonical_current("atlas", "release-a")
    # The record for release-a is replaced by a different (valid) release's record.
    record_file(store, "release-a").write_bytes(record_file(store, "release-b").read_bytes())

    with pytest.raises((CurrentDesignationError, ReleaseRecordCorruptError)):
        store.get_canonical_current("atlas")


def test_current_state_is_per_character_and_unknown_character_has_none(env):
    store = env.store()

    assert store.get_canonical_current("someone-else") is None
    assert store.list_release_ids("someone-else") == ()


# ===== export ====================================================================


def test_export_copies_the_exact_stored_bytes(env):
    store = env.store()
    result = publish(store, env, env.build())
    destination = env.tmp / "out" / "kira.vchar"
    destination.parent.mkdir()

    exported = store.export_release("atlas", "release-one", destination)

    raw = destination.read_bytes()
    assert raw == result.artifact_path.read_bytes()
    assert sha(raw) == exported.artifact_sha256 == result.record.artifact_sha256
    assert len(raw) == exported.byte_length == result.record.byte_length
    assert exported.path == destination
    assert (exported.character_id, exported.release_id, exported.package_hash) == (
        "atlas", "release-one", result.record.package_hash)
    assert sorted(p.name for p in destination.parent.iterdir()) == ["kira.vchar"]


def test_export_needs_no_authoring_and_no_rebuild(env, monkeypatch):
    store = env.store()
    publish(store, env, env.build())
    shutil.rmtree(env.authoring.root)  # Authoring is gone entirely
    monkeypatch.setattr(
        vcp_release, "compile_authoring_release",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no rebuild")),
    )

    exported = store.export_release("atlas", "release-one", env.tmp / "x.vchar")

    assert exported.path.is_file()


def test_export_does_not_change_current_records_or_artifacts(env):
    store = env.store()
    two_releases(env, store)
    store.set_canonical_current("atlas", "release-a")
    before = tree(store.root)

    store.export_release("atlas", "release-b", env.tmp / "b.vchar")

    assert tree(store.root) == before
    assert store.get_canonical_current("atlas").release_id == "release-a"


def test_export_never_overwrites_an_existing_destination(env):
    store = env.store()
    publish(store, env, env.build())
    destination = env.tmp / "existing.vchar"
    destination.write_bytes(b"keep me")

    with pytest.raises(ReleaseExportError):
        store.export_release("atlas", "release-one", destination)

    assert destination.read_bytes() == b"keep me"


@pytest.mark.parametrize("kind", ["relative", "traversal", "missing_parent", "inside_store"])
def test_unsafe_export_destinations_are_refused(env, kind):
    store = env.store()
    publish(store, env, env.build())
    destination = {
        "relative": Path("rel.vchar"),
        "traversal": env.tmp / "a" / ".." / "t.vchar",
        "missing_parent": env.tmp / "nope" / "x.vchar",
        "inside_store": store.root / "artifacts" / "copy.vchar",
    }[kind]
    before = tree(env.tmp)

    with pytest.raises(ReleaseExportError):
        store.export_release("atlas", "release-one", destination)

    assert tree(env.tmp) == before


def test_failed_export_leaves_publication_and_current_intact(env, monkeypatch):
    store = env.store()
    store.set_canonical_current("atlas", publish(store, env, env.build()).record.release_id)
    before = tree(store.root)
    destination_dir = env.tmp / "dest"
    destination_dir.mkdir()

    def failing_copy(source, temp_path):
        temp_path.write_bytes(b"partial")
        raise OSError("simulated export failure")

    monkeypatch.setattr(rs, "_stream_copy", failing_copy)
    with pytest.raises(ReleaseExportError):
        store.export_release("atlas", "release-one", destination_dir / "out.vchar")

    assert tree(store.root) == before
    assert list(destination_dir.iterdir()) == []  # neither destination nor temp remains
    monkeypatch.undo()
    assert store.get_canonical_current("atlas").release_id == "release-one"
    assert store.verify_release("atlas", "release-one")


def test_tampered_stored_artifact_refuses_export(env):
    store = env.store()
    record = publish(store, env, env.build()).record
    path = artifact_file(store, record.package_hash)
    data = bytearray(path.read_bytes())
    data[10] ^= 0xFF
    path.write_bytes(bytes(data))
    destination_dir = env.tmp / "dest"
    destination_dir.mkdir()

    with pytest.raises(DurableArtifactCorruptError):
        store.export_release("atlas", "release-one", destination_dir / "out.vchar")

    assert list(destination_dir.iterdir()) == []


def test_export_touches_only_the_requested_path(env):
    store = env.store()
    publish(store, env, env.build())
    destination_dir = env.tmp / "dest"
    destination_dir.mkdir()
    (destination_dir / "neighbour.txt").write_bytes(b"neighbour")
    other = env.tmp / "elsewhere.txt"
    other.write_bytes(b"elsewhere")

    store.export_release("atlas", "release-one", destination_dir / "out.vchar")

    assert sorted(p.name for p in destination_dir.iterdir()) == ["neighbour.txt", "out.vchar"]
    assert (destination_dir / "neighbour.txt").read_bytes() == b"neighbour"
    assert other.read_bytes() == b"elsewhere"


# ===== concurrent publication =====================================================


def _publish_concurrently(env, builts, monkeypatch):
    stores = [CharacterReleaseStore(env.tmp / "store", clock=Clock(PUBLISHED_1)) for _ in builts]
    barrier = threading.Barrier(len(builts), timeout=30)
    real = CharacterReleaseStore._existing_for_publication

    def gated(self, built):
        result = real(self, built)  # both callers see "no record yet"
        barrier.wait(timeout=30)
        return result

    monkeypatch.setattr(CharacterReleaseStore, "_existing_for_publication", gated)
    with ThreadPoolExecutor(max_workers=len(builts)) as pool:
        futures = [
            pool.submit(store.publish_release, built, authoring_store=env.authoring)
            for store, built in zip(stores, builts)
        ]
        outcomes = []
        for future in futures:
            try:
                outcomes.append(future.result(timeout=90))
            except CharacterReleaseStoreError as exc:
                outcomes.append(exc)
    return stores[0], outcomes


def test_concurrent_exact_publish_converges_to_one_release(env, monkeypatch):
    built = env.build()

    store, outcomes = _publish_concurrently(env, [built, built], monkeypatch)

    assert all(not isinstance(o, Exception) for o in outcomes)
    assert sorted(o.newly_published for o in outcomes) == [False, True]
    assert outcomes[0].record == outcomes[1].record
    assert [p.name for p in (store.root / "releases" / "atlas").iterdir()] == ["release-one.json"]
    assert store.verify_release("atlas", "release-one").record == outcomes[0].record
    no_scratch_leftovers(store)


def test_concurrent_collision_lets_exactly_one_identity_win(env, monkeypatch):
    first = env.build(display_name="Первый")
    second = env.build(display_name="Второй")
    assert first.package_hash != second.package_hash

    store, outcomes = _publish_concurrently(env, [first, second], monkeypatch)

    winners = [o for o in outcomes if not isinstance(o, Exception)]
    losers = [o for o in outcomes if isinstance(o, Exception)]
    assert len(winners) == 1 and len(losers) == 1
    assert isinstance(losers[0], ReleaseIdHashCollisionError)
    record = store.load_release_record("atlas", "release-one")
    assert record.package_hash == winners[0].record.package_hash
    assert store.verify_release("atlas", "release-one").record == record


# ===== corruption detection =========================================================


def test_read_boundary_cheap_and_full(env):
    store = env.store()
    published = publish(store, env, env.build())

    assert store.load_release_record("atlas", "release-one") == published.record
    verified = store.verify_release("atlas", "release-one")
    assert verified.record == published.record and verified.artifact_path.is_file()
    assert store.load_release("atlas", "release-one") == published.record
    assert store.list_release_ids("atlas") == ("release-one",)


@pytest.mark.parametrize("kind", ["minified", "extra_key", "invalid_json", "duplicate_key",
                                  "bad_timestamp", "bad_artifact_ref", "wrong_schema"])
def test_tampered_release_record_is_detected(env, kind):
    store = env.store()
    publish(store, env, env.build())
    path = record_file(store)
    data = json.loads(path.read_text(encoding="utf-8"))
    if kind == "minified":
        path.write_text(json.dumps(data), encoding="utf-8")
    elif kind == "extra_key":
        data["note"] = "x"
        write_canonical(path, data)
    elif kind == "invalid_json":
        path.write_text("{oops", encoding="utf-8")
    elif kind == "duplicate_key":
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace('  "byte_length"', '  "release_id": "release-one",\n  "byte_length"', 1), encoding="utf-8")
    elif kind == "bad_timestamp":
        data["published_at"] = "yesterday"
        write_canonical(path, data)
    elif kind == "bad_artifact_ref":
        data["artifact_ref"] = "artifacts/other.vchar"
        write_canonical(path, data)
    else:
        data["schema_version"] = "character_release_record/9.9"
        write_canonical(path, data)

    with pytest.raises(ReleaseRecordCorruptError):
        store.load_release_record("atlas", "release-one")
    with pytest.raises(ReleaseRecordCorruptError):
        store.verify_release("atlas", "release-one")


def test_release_record_path_identity_mismatch_is_detected(env):
    store = env.store()
    two_releases(env, store)
    record_file(store, "release-b").write_bytes(record_file(store, "release-a").read_bytes())

    with pytest.raises(ReleaseRecordCorruptError):
        store.load_release_record("atlas", "release-b")


def test_missing_stored_artifact_is_detected(env):
    store = env.store()
    record = publish(store, env, env.build()).record
    artifact_file(store, record.package_hash).unlink()

    with pytest.raises(DurableArtifactCorruptError):
        store.verify_release("atlas", "release-one")
    assert store.load_release_record("atlas", "release-one") == record  # metadata still reads


def test_wrong_artifact_sha_or_size_is_detected(env):
    store = env.store()
    record = publish(store, env, env.build()).record
    path = artifact_file(store, record.package_hash)
    original = path.read_bytes()

    flipped = bytearray(original)
    flipped[len(flipped) // 2] ^= 0xFF
    path.write_bytes(bytes(flipped))
    with pytest.raises(DurableArtifactCorruptError):
        store.verify_release("atlas", "release-one")

    path.write_bytes(original + b"\x00")
    with pytest.raises(DurableArtifactCorruptError):
        store.verify_release("atlas", "release-one")

    path.write_bytes(original)
    edit_record(store, artifact_sha256="0" * 64)
    with pytest.raises(DurableArtifactCorruptError):
        store.verify_release("atlas", "release-one")


def test_wrong_artifact_package_hash_is_detected_through_vcp(env):
    store = env.store()
    a, b = two_releases(env, store)
    b_bytes = artifact_file(store, b.package_hash).read_bytes()
    # release-a's record and storage now describe release-b's (valid) archive.
    artifact_file(store, a.package_hash).write_bytes(b_bytes)
    edit_record(store, "release-a", artifact_sha256=b.artifact_sha256, byte_length=b.byte_length)

    with pytest.raises(DurableArtifactCorruptError) as excinfo:
        store.verify_release("atlas", "release-a")

    assert "VCP" in str(excinfo.value) or "packageHash" in str(excinfo.value)


def test_another_releases_artifact_is_refused_even_with_self_consistent_hashes(env):
    store = env.store()
    a, b = two_releases(env, store)
    # release-a's record now claims release-b's package, artifact and hashes entirely.
    edit_record(
        store, "release-a",
        package_hash=b.package_hash, artifact_sha256=b.artifact_sha256,
        byte_length=b.byte_length, aggregate_hash=b.aggregate_hash,
        acceptance_record_hash=b.acceptance_record_hash,
        artifact_ref=f"artifacts/{b.package_hash}.vchar",
    )

    with pytest.raises(DurableArtifactCorruptError) as excinfo:
        store.verify_release("atlas", "release-a")

    assert "releaseId" in str(excinfo.value)


@pytest.mark.parametrize("field", ["package_hash", "character_id", "release_id",
                                   "accepted_aggregate_hash", "acceptance_record_hash"])
def test_vcp_reported_identity_disagreement_is_refused(env, monkeypatch, field):
    store = env.store()
    publish(store, env, env.build())
    real = rs.extract_vchar_v1
    other = "0" * 64 if "hash" in field else "different"

    def lying(archive, staging, *, expected_package_hash=None):
        verified = real(archive, staging, expected_package_hash=expected_package_hash)
        if field == "package_hash":
            return replace(verified, package_hash=other)
        return replace(verified, metadata=replace(verified.metadata, **{field: other}))

    monkeypatch.setattr(rs, "extract_vchar_v1", lying)

    with pytest.raises(DurableArtifactCorruptError):
        store.verify_release("atlas", "release-one")


def test_symlinked_or_non_regular_artifact_is_refused(env):
    store = env.store()
    record = publish(store, env, env.build()).record
    path = artifact_file(store, record.package_hash)
    path.unlink()
    path.mkdir()  # a directory where the archive should be

    with pytest.raises(DurableArtifactCorruptError):
        store.verify_release("atlas", "release-one")


# ===== layout / hygiene =================================================================


def test_store_layout_keeps_four_namespaces_distinct(env):
    store = env.store()
    two_releases(env, store)
    store.set_canonical_current("atlas", "release-a")

    top = sorted(p.name for p in store.root.iterdir())
    assert top == ["artifacts", "current", "history", "locks", "releases", "tmp"]
    assert [p.name for p in (store.root / "locks").iterdir()] == ["atlas.lock"]
    assert [p.suffix for p in (store.root / "artifacts").iterdir()] == [".vchar", ".vchar"]
    assert [p.name for p in (store.root / "releases" / "atlas").iterdir()] == [
        "release-a.json", "release-b.json"]
    assert [p.name for p in (store.root / "current").iterdir()] == ["atlas.json"]
    assert [p.name for p in (store.root / "history" / "atlas").iterdir()] == ["00000001.json"]
    no_scratch_leftovers(store)
    # No mutable current state inside an immutable release record.
    for record in (store.root / "releases" / "atlas").iterdir():
        text = record.read_text(encoding="utf-8")
        assert "generation" not in text and "current" not in text


def test_publication_writes_only_inside_the_store_root(env):
    store = env.store()
    built = env.build()
    outside_before = tree(env.tmp / "authoring") | tree(built.workspace_root)

    publish(store, env, built)

    assert tree(env.tmp / "authoring") | tree(built.workspace_root) == outside_before


def test_no_delete_or_gc_api_exists():
    public = {name for name in dir(CharacterReleaseStore) if not name.startswith("_")}
    assert not {n for n in public if any(w in n for w in ("delete", "remove", "prune", "gc", "purge"))}


def test_release_store_is_not_reexported_or_loaded_at_lab_startup():
    import services.character_publication as publication

    # (the submodule attribute exists once imported; the API must not be re-exported)
    for name in ("CharacterReleaseStore", "ReleaseRecord", "CanonicalCurrent"):
        assert not hasattr(publication, name)
    probe = (
        "import sys\n"
        "import services.character_publication\n"
        "import services.character_lab_application\n"
        "assert 'voyage_character_platform' not in sys.modules\n"
        "assert 'services.character_publication.release_store' not in sys.modules\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", probe], cwd=REPO_ROOT, capture_output=True, text=True, check=False
    )
    assert completed.returncode == 0, completed.stderr
