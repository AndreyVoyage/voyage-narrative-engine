"""LAB-L3 MATERIALIZE_VERIFY_ARCHIVE_V1: verified portable .vchar orchestration."""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import json
import re
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType

import pytest

# VCP operational dependency wiring is deferred; without the distribution the
# module is skipped instead of failing collection.
pytest.importorskip("voyage_character_platform")

from services.character_authoring import (
    ApprovalEvidence,
    CharacterAuthoringStore,
    LifecycleState,
)
from services.character_publication import vcp_artifact
from services.character_publication.vcp_artifact import (
    ARTIFACT_FILENAME,
    PACKAGE_DIRNAME,
    ROUNDTRIP_DIRNAME,
    AuthoringVcpArtifactBuildError,
    BuiltVcpArtifact,
    VcpArtifactStage,
    build_verified_vchar_artifact,
)
from services.character_publication.vcp_release import (
    AuthoringVcpReleaseCompilation,
    compile_authoring_release,
)
from voyage_character_platform.package_v1 import (
    PackageV1ContractError,
    PackageV1IntegrityError,
    PackageV1PathError,
    verify_package_v1,
)
from voyage_character_platform.vchar import extract_vchar_v1

REPO_ROOT = Path(__file__).resolve().parents[2]
DECIDED_AT = "2026-03-04T05:06:07Z"

SIX = (
    "core_identity", "psychology", "speech",
    "relationships", "visual_identity", "interaction_boundaries",
)
PACKAGE_FILES = sorted(
    [
        "manifest.json",
        "package.json",
        "provenance/acceptance.json",
        "provenance/provenance.json",
        "provenance/contradictions.json",
        "unknowns/unknowns.json",
        *(f"domains/{d}.json" for d in SIX),
    ]
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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


def make_compilation(
    tmp_path: Path, *, release_id="release-one", display_name="Атлас", name="Atlas"
) -> AuthoringVcpReleaseCompilation:
    store = CharacterAuthoringStore(tmp_path / "authoring")
    store.create_character("atlas")
    store.create_version("atlas", "version-v1", version_label="Version 1")
    record = store.persist_revision("atlas", "version-v1", "revision-r1", semantic(name))
    store.persist_approval_evidence(
        ApprovalEvidence(
            character_id="atlas",
            version_id="version-v1",
            revision_id="revision-r1",
            snapshot_hash=record.snapshot_hash,
            decided_by="Ada Approver",
            decided_at=DECIDED_AT,
        )
    )
    return compile_authoring_release(
        store,
        character_id="atlas",
        version_id="version-v1",
        revision_id="revision-r1",
        snapshot_hash=record.snapshot_hash,
        release_id=release_id,
        display_name=display_name,
    )


@pytest.fixture
def compilation(tmp_path):
    return make_compilation(tmp_path)


def workspace_path(tmp_path: Path, name: str = "build") -> Path:
    holder = tmp_path / "workspaces"
    holder.mkdir(exist_ok=True)
    return holder / name


def snapshot(root: Path) -> dict[str, bytes | None]:
    return {
        path.relative_to(root).as_posix(): (path.read_bytes() if path.is_file() else None)
        for path in sorted(root.rglob("*"))
    }


def files_of(root: Path) -> list[str]:
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())


def build_ok(tmp_path, compilation, name="build") -> BuiltVcpArtifact:
    return build_verified_vchar_artifact(compilation, workspace_path(tmp_path, name))


# -- 1-10, 15: real authoritative chain, no mocks -----------------------------


def test_valid_compilation_builds_a_verified_artifact_through_the_real_chain(
    tmp_path, compilation
):
    result = build_ok(tmp_path, compilation)

    assert isinstance(result, BuiltVcpArtifact)
    assert result.artifact_path == workspace_path(tmp_path) / ARTIFACT_FILENAME
    assert result.artifact_path.is_file()
    assert result.package_root == workspace_path(tmp_path) / PACKAGE_DIRNAME
    assert result.roundtrip_root == workspace_path(tmp_path) / ROUNDTRIP_DIRNAME


def test_directory_package_is_independently_verified_against_the_package_hash(
    tmp_path, compilation
):
    result = build_ok(tmp_path, compilation)

    again = verify_package_v1(
        result.package_root, expected_package_hash=result.package_hash
    )
    manifest_bytes = (result.package_root / "manifest.json").read_bytes()
    assert again.package_hash == result.package_hash == sha(manifest_bytes)
    assert result.verified_package.package_hash == result.package_hash


def test_artifact_sha_and_size_match_the_actual_file(tmp_path, compilation):
    result = build_ok(tmp_path, compilation)

    raw = result.artifact_path.read_bytes()
    assert result.artifact_sha256 == sha(raw) == result.written.artifact_sha256
    assert result.byte_length == len(raw) == result.written.byte_length
    assert result.artifact_path.stat().st_size == result.byte_length


def test_independent_extraction_round_trips_to_the_same_identity(tmp_path, compilation):
    result = build_ok(tmp_path, compilation)

    verified = extract_vchar_v1(
        result.artifact_path,
        tmp_path / "independent_extract",
        expected_package_hash=result.package_hash,
    )

    assert verified.package_hash == result.package_hash
    assert verified.metadata.character_id == result.character_id == "atlas"
    assert verified.metadata.release_id == result.release_id == "release-one"
    assert result.verified_roundtrip.package_hash == result.package_hash
    assert result.verified_roundtrip.metadata.character_id == "atlas"
    assert result.verified_roundtrip.metadata.release_id == "release-one"
    assert result.verified_roundtrip.manifest == result.verified_package.manifest


def test_identity_agrees_with_the_l2_compilation_through_public_fields(
    tmp_path, compilation
):
    result = build_ok(tmp_path, compilation)

    package = json.loads((result.package_root / "package.json").read_bytes())
    assert (result.character_id, result.release_id) == ("atlas", "release-one")
    assert package["characterId"] == result.character_id
    assert package["releaseId"] == result.release_id
    assert package["acceptedAggregateHash"] == compilation.aggregate_hash == result.aggregate_hash
    assert package["acceptanceRecordHash"] == compilation.acceptance_record_hash
    for verified in (result.verified_package, result.verified_roundtrip):
        assert verified.metadata.accepted_aggregate_hash == compilation.aggregate_hash
        assert verified.metadata.acceptance_record_hash == compilation.acceptance_record_hash
    assert result.source == compilation.source
    assert result.approval == compilation.approval
    assert result.aggregate_candidate_id == compilation.aggregate_candidate_id


def test_hash_namespaces_are_derived_from_their_own_sources(tmp_path, compilation):
    result = build_ok(tmp_path, compilation)

    manifest = (result.package_root / "manifest.json").read_bytes()
    acceptance = (result.package_root / "provenance" / "acceptance.json").read_bytes()
    archive = result.artifact_path.read_bytes()
    assert result.package_hash == sha(manifest)  # packageHash: manifest bytes only
    assert result.acceptance_record_hash == sha(acceptance)  # raw acceptance bytes
    assert result.artifact_sha256 == sha(archive)  # transport bytes only
    assert result.aggregate_hash == compilation.aggregate_hash  # L2 aggregate, untouched
    # L2 exposes no packageHash; L3 is where it first exists.
    assert not hasattr(compilation, "package_hash")


def test_successful_workspace_contains_only_the_expected_outputs(tmp_path, compilation):
    result = build_ok(tmp_path, compilation)

    workspace = result.workspace_root
    assert sorted(p.name for p in workspace.iterdir()) == sorted(
        [PACKAGE_DIRNAME, ARTIFACT_FILENAME, ROUNDTRIP_DIRNAME]
    )
    assert files_of(result.package_root) == PACKAGE_FILES
    assert files_of(result.roundtrip_root) == PACKAGE_FILES
    assert not list(workspace.rglob("*.tmp"))
    assert not list(workspace.rglob(".vchar-*"))
    # Directory package and extracted package hold byte-identical files.
    for relative in PACKAGE_FILES:
        assert (result.package_root / relative).read_bytes() == (
            result.roundtrip_root / relative
        ).read_bytes()


def test_package_content_is_exactly_the_l2_logical_files_plus_manifest(
    tmp_path, compilation
):
    result = build_ok(tmp_path, compilation)

    for relative, package_file in compilation.files.items():
        assert (result.package_root / relative).read_bytes() == package_file.content
    assert sorted(files_of(result.package_root)) == PACKAGE_FILES
    provenance = (result.package_root / "provenance" / "provenance.json").read_bytes()
    assert provenance == b'{"provenance": []}'
    assert not (result.package_root / "assets").exists()
    assert not (result.package_root / "prompts").exists()


# -- 13-14: determinism -----------------------------------------------------


def test_same_compilation_in_two_fresh_workspaces_is_deterministic(tmp_path, compilation):
    first = build_ok(tmp_path, compilation, "one")
    second = build_ok(tmp_path, compilation, "two")

    assert first.package_hash == second.package_hash
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.byte_length == second.byte_length
    assert first.artifact_path.read_bytes() == second.artifact_path.read_bytes()
    assert first.artifact_path != second.artifact_path


def test_independently_compiled_equal_releases_build_identical_artifacts(tmp_path):
    first = build_ok(tmp_path / "a", make_compilation(tmp_path / "a"))
    second = build_ok(tmp_path / "b", make_compilation(tmp_path / "b"))

    assert first.package_hash == second.package_hash
    assert first.artifact_sha256 == second.artifact_sha256


def test_different_release_id_changes_package_identity(tmp_path):
    one = build_ok(tmp_path / "a", make_compilation(tmp_path / "a", release_id="release-one"))
    two = build_ok(tmp_path / "b", make_compilation(tmp_path / "b", release_id="release-two"))

    assert one.release_id != two.release_id
    assert one.package_hash != two.package_hash
    assert one.aggregate_hash == two.aggregate_hash  # same accepted aggregate


def test_authoritative_vcp_apis_are_called_in_order_with_exact_arguments(
    tmp_path, compilation, monkeypatch
):
    calls = []
    real = {
        name: getattr(vcp_artifact, name)
        for name in (
            "materialize_package_v1", "verify_package_v1",
            "write_vchar_v1", "extract_vchar_v1",
        )
    }

    def spy_materialize(destination, *, files):
        calls.append(("materialize", Path(destination), dict(files)))
        return real["materialize_package_v1"](destination, files=files)

    def spy_verify(root, *, expected_package_hash=None):
        calls.append(("verify", Path(root), expected_package_hash))
        return real["verify_package_v1"](root, expected_package_hash=expected_package_hash)

    def spy_write(package_root, destination):
        calls.append(("write", Path(package_root), Path(destination)))
        return real["write_vchar_v1"](package_root, destination)

    def spy_extract(archive, staging_root, *, expected_package_hash=None):
        calls.append(("extract", Path(archive), Path(staging_root), expected_package_hash))
        return real["extract_vchar_v1"](
            archive, staging_root, expected_package_hash=expected_package_hash
        )

    monkeypatch.setattr(vcp_artifact, "materialize_package_v1", spy_materialize)
    monkeypatch.setattr(vcp_artifact, "verify_package_v1", spy_verify)
    monkeypatch.setattr(vcp_artifact, "write_vchar_v1", spy_write)
    monkeypatch.setattr(vcp_artifact, "extract_vchar_v1", spy_extract)

    result = build_ok(tmp_path, compilation)

    workspace = result.workspace_root
    assert [call[0] for call in calls] == ["materialize", "verify", "write", "extract"]
    materialize, verify, write, extract = calls
    assert materialize[1] == workspace / "package"
    assert materialize[2] == dict(compilation.files)  # exactly the L2 logical files
    assert verify[1] == workspace / "package"
    assert verify[2] == result.package_hash  # explicit, exact packageHash
    assert write[1:] == (workspace / "package", workspace / "artifact.vchar")
    assert extract[1:3] == (workspace / "artifact.vchar", workspace / "roundtrip")
    assert extract[3] == result.package_hash


# -- 11-12: no recompilation, no Authoring read --------------------------------


def test_build_needs_no_authoring_store_and_never_recompiles(tmp_path, monkeypatch):
    compilation = make_compilation(tmp_path)
    shutil.rmtree(tmp_path / "authoring")  # the whole Authoring store is gone

    import services.character_publication.vcp_domains as domains_module
    import services.character_publication.vcp_release as release_module

    def forbidden(*_args, **_kwargs):
        raise AssertionError("LAB-L3 must not recompile or reload Authoring")

    monkeypatch.setattr(domains_module, "compile_authoring_revision_to_vcp_domains", forbidden)
    monkeypatch.setattr(release_module, "compile_authoring_release", forbidden)
    monkeypatch.setattr(release_module, "build_authoring_release_compilation", forbidden)

    result = build_ok(tmp_path, compilation)

    assert result.package_hash and result.artifact_path.is_file()


def test_build_does_not_read_the_lifecycle_pointer(tmp_path):
    store = CharacterAuthoringStore(tmp_path / "authoring")
    store.create_character("atlas")
    store.create_version("atlas", "version-v1", version_label="Version 1")
    record = store.persist_revision("atlas", "version-v1", "revision-r1", semantic())
    store.persist_approval_evidence(
        ApprovalEvidence("atlas", "version-v1", "revision-r1", record.snapshot_hash,
                         "Ada Approver", DECIDED_AT)
    )
    compilation = compile_authoring_release(
        store, character_id="atlas", version_id="version-v1", revision_id="revision-r1",
        snapshot_hash=record.snapshot_hash, release_id="r1", display_name="Atlas",
    )
    # The version is still a DRAFT and the pointer is then made unreadable.
    assert store.read_version_pointer("atlas", "version-v1").lifecycle_state is LifecycleState.DRAFT
    pointer = tmp_path / "authoring" / "atlas" / "versions" / "version-v1" / "pointer.json"
    pointer.write_text("{corrupt", encoding="utf-8")

    result = build_ok(tmp_path, compilation)

    assert result.artifact_path.is_file()


def test_module_uses_no_authoring_store_compiler_or_archive_internals():
    source = (REPO_ROOT / "services" / "character_publication" / "vcp_artifact.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.update(alias.name for alias in node.names)
            imported.add(node.module)
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
    for forbidden in (
        "CharacterAuthoringStore", "compile_authoring_release",
        "compile_authoring_revision_to_vcp_domains",
        "build_authoring_release_compilation", "zipfile", "struct", "zlib",
        "canonical_json_bytes", "create_manifest", "package_hash_from_manifest_bytes",
    ):
        assert forbidden not in imported
    assert "read_version_pointer" not in source and "load_approval_evidence" not in source
    assert "zipfile" not in source and "struct." not in source


# -- 16, 26: workspace preconditions ------------------------------------------


def test_existing_workspace_fails_closed_without_any_mutation(tmp_path, compilation):
    workspace = workspace_path(tmp_path)
    workspace.mkdir()
    (workspace / "keep.txt").write_bytes(b"caller data")
    (workspace / "artifact.vchar").write_bytes(b"pre-existing archive")
    before = snapshot(tmp_path / "workspaces")

    with pytest.raises(AuthoringVcpArtifactBuildError) as excinfo:
        build_verified_vchar_artifact(compilation, workspace)

    assert excinfo.value.stage is VcpArtifactStage.WORKSPACE
    assert snapshot(tmp_path / "workspaces") == before
    assert workspace.is_dir()


def test_existing_file_at_workspace_path_fails_closed(tmp_path, compilation):
    workspace = workspace_path(tmp_path)  # creates the holder directory
    workspace.write_bytes(b"i am a file")

    with pytest.raises(AuthoringVcpArtifactBuildError) as excinfo:
        build_verified_vchar_artifact(compilation, workspace)

    assert excinfo.value.stage is VcpArtifactStage.WORKSPACE
    assert workspace.read_bytes() == b"i am a file"


@pytest.mark.parametrize("bad", ["relative/build", "build", "..", "C:drive-relative"])
def test_relative_or_unsafe_workspace_is_rejected(tmp_path, compilation, bad, monkeypatch):
    monkeypatch.chdir(tmp_path)
    before = snapshot(tmp_path)

    with pytest.raises(AuthoringVcpArtifactBuildError) as excinfo:
        build_verified_vchar_artifact(compilation, bad)

    assert excinfo.value.stage is VcpArtifactStage.WORKSPACE
    assert snapshot(tmp_path) == before


def test_parent_traversal_segments_are_rejected(tmp_path, compilation):
    (tmp_path / "holder").mkdir()
    unsafe = tmp_path / "holder" / ".." / "escaped"

    with pytest.raises(AuthoringVcpArtifactBuildError) as excinfo:
        build_verified_vchar_artifact(compilation, unsafe)

    assert excinfo.value.stage is VcpArtifactStage.WORKSPACE
    assert not (tmp_path / "escaped").exists()


def test_missing_parent_is_rejected_and_not_created(tmp_path, compilation):
    workspace = tmp_path / "no_such_parent" / "build"

    with pytest.raises(AuthoringVcpArtifactBuildError) as excinfo:
        build_verified_vchar_artifact(compilation, workspace)

    assert excinfo.value.stage is VcpArtifactStage.WORKSPACE
    assert not (tmp_path / "no_such_parent").exists()


@pytest.mark.parametrize("bad", [None, 5, b"bytes"])
def test_non_path_workspace_is_rejected(compilation, bad):
    with pytest.raises(AuthoringVcpArtifactBuildError) as excinfo:
        build_verified_vchar_artifact(compilation, bad)  # type: ignore[arg-type]

    assert excinfo.value.stage is VcpArtifactStage.WORKSPACE


@pytest.mark.parametrize("bad", [None, {}, "compilation", object()])
def test_non_compilation_input_is_rejected_before_touching_the_filesystem(tmp_path, bad):
    before = snapshot(tmp_path)
    untouched = tmp_path / "workspaces" / "build"  # deliberately not pre-created

    with pytest.raises(AuthoringVcpArtifactBuildError) as excinfo:
        build_verified_vchar_artifact(bad, untouched)  # type: ignore[arg-type]

    assert excinfo.value.stage is VcpArtifactStage.INPUT
    assert snapshot(tmp_path) == before
    assert not (tmp_path / "workspaces").exists()


# -- 17-25: failure boundaries --------------------------------------------------


def assert_failed_and_clean(tmp_path, compilation, stage, *, before):
    workspace = workspace_path(tmp_path)
    with pytest.raises(AuthoringVcpArtifactBuildError) as excinfo:
        build_verified_vchar_artifact(compilation, workspace)
    assert excinfo.value.stage is stage
    assert excinfo.value.cleanup_complete is True
    assert not workspace.exists()
    assert snapshot(tmp_path / "workspaces") == before if (tmp_path / "workspaces").exists() else True
    return excinfo.value


def test_real_materialize_rejection_cleans_the_owned_workspace(tmp_path, compilation):
    files = dict(compilation.files)
    del files["domains/speech.json"]  # a genuinely incomplete package
    broken = replace(compilation, files=MappingProxyType(files))
    (tmp_path / "workspaces").mkdir()

    error = assert_failed_and_clean(
        tmp_path, broken, VcpArtifactStage.MATERIALIZE, before={}
    )

    assert isinstance(error.__cause__, PackageV1ContractError)


def test_materialize_failure_injection_cleans_the_owned_workspace(
    tmp_path, compilation, monkeypatch
):
    def boom(destination, *, files):
        Path(destination).mkdir(parents=True)
        (Path(destination) / "half.txt").write_bytes(b"partial")
        raise PackageV1ContractError("injected materialize failure")

    monkeypatch.setattr(vcp_artifact, "materialize_package_v1", boom)
    (tmp_path / "workspaces").mkdir()

    error = assert_failed_and_clean(
        tmp_path, compilation, VcpArtifactStage.MATERIALIZE, before={}
    )

    assert isinstance(error.__cause__, PackageV1ContractError)


def test_directory_verify_failure_cleans_the_owned_workspace(
    tmp_path, compilation, monkeypatch
):
    def boom(root, *, expected_package_hash=None):
        raise PackageV1IntegrityError("injected verify failure")

    monkeypatch.setattr(vcp_artifact, "verify_package_v1", boom)
    (tmp_path / "workspaces").mkdir()

    error = assert_failed_and_clean(
        tmp_path, compilation, VcpArtifactStage.DIRECTORY_VERIFY, before={}
    )

    assert isinstance(error.__cause__, PackageV1IntegrityError)


def test_verified_package_hash_mismatch_fails_closed(tmp_path, compilation, monkeypatch):
    real = vcp_artifact.verify_package_v1

    def lying(root, *, expected_package_hash=None):
        return replace(real(root), package_hash="0" * 64)

    monkeypatch.setattr(vcp_artifact, "verify_package_v1", lying)
    (tmp_path / "workspaces").mkdir()

    assert_failed_and_clean(tmp_path, compilation, VcpArtifactStage.DIRECTORY_VERIFY, before={})


@pytest.mark.parametrize("field", ["character_id", "release_id",
                                   "accepted_aggregate_hash", "acceptance_record_hash"])
def test_verified_metadata_disagreeing_with_l2_fails_closed(
    tmp_path, compilation, monkeypatch, field
):
    real = vcp_artifact.verify_package_v1
    other = "0" * 64 if "hash" in field else "different"

    def lying(root, *, expected_package_hash=None):
        verified = real(root, expected_package_hash=expected_package_hash)
        return replace(verified, metadata=replace(verified.metadata, **{field: other}))

    monkeypatch.setattr(vcp_artifact, "verify_package_v1", lying)
    (tmp_path / "workspaces").mkdir()

    assert_failed_and_clean(tmp_path, compilation, VcpArtifactStage.DIRECTORY_VERIFY, before={})


def test_vchar_write_failure_cleans_the_owned_workspace(tmp_path, compilation, monkeypatch):
    def boom(package_root, destination):
        raise PackageV1PathError("injected write failure")

    monkeypatch.setattr(vcp_artifact, "write_vchar_v1", boom)
    (tmp_path / "workspaces").mkdir()

    error = assert_failed_and_clean(
        tmp_path, compilation, VcpArtifactStage.VCHAR_WRITE, before={}
    )

    assert isinstance(error.__cause__, PackageV1PathError)


@pytest.mark.parametrize("field,value", [
    ("package_hash", "1" * 64), ("release_id", "other"), ("character_id", "other"),
])
def test_write_result_identity_disagreement_fails_closed(
    tmp_path, compilation, monkeypatch, field, value
):
    real = vcp_artifact.write_vchar_v1
    monkeypatch.setattr(
        vcp_artifact, "write_vchar_v1",
        lambda root, destination: replace(real(root, destination), **{field: value}),
    )
    (tmp_path / "workspaces").mkdir()

    assert_failed_and_clean(tmp_path, compilation, VcpArtifactStage.VCHAR_WRITE, before={})


def test_artifact_sha_mismatch_is_detected_and_cleaned(tmp_path, compilation, monkeypatch):
    real = vcp_artifact.write_vchar_v1
    monkeypatch.setattr(
        vcp_artifact, "write_vchar_v1",
        lambda root, destination: replace(real(root, destination), artifact_sha256="0" * 64),
    )
    (tmp_path / "workspaces").mkdir()

    error = assert_failed_and_clean(
        tmp_path, compilation, VcpArtifactStage.ARTIFACT_INTEGRITY, before={}
    )

    assert "SHA-256" in error.detail


def test_artifact_size_mismatch_is_detected_and_cleaned(tmp_path, compilation, monkeypatch):
    real = vcp_artifact.write_vchar_v1

    def wrong_size(root, destination):
        written = real(root, destination)
        return replace(written, byte_length=written.byte_length + 1)

    monkeypatch.setattr(vcp_artifact, "write_vchar_v1", wrong_size)
    (tmp_path / "workspaces").mkdir()

    error = assert_failed_and_clean(
        tmp_path, compilation, VcpArtifactStage.ARTIFACT_INTEGRITY, before={}
    )

    assert "size" in error.detail


def test_archive_tampering_after_write_is_rejected_by_authoritative_vcp(
    tmp_path, compilation, monkeypatch
):
    real = vcp_artifact.write_vchar_v1

    def tamper_consistently(root, destination):
        written = real(root, destination)
        data = bytearray(Path(destination).read_bytes())
        data[len(data) // 2] ^= 0xFF  # corrupt entry bytes
        Path(destination).write_bytes(bytes(data))
        # Report the tampered file's own SHA/size so only VCP extraction can object.
        return replace(written, artifact_sha256=sha(bytes(data)), byte_length=len(data))

    monkeypatch.setattr(vcp_artifact, "write_vchar_v1", tamper_consistently)
    (tmp_path / "workspaces").mkdir()

    error = assert_failed_and_clean(
        tmp_path, compilation, VcpArtifactStage.ROUNDTRIP, before={}
    )

    assert error.__cause__ is not None


def test_roundtrip_extract_failure_injection_cleans_the_owned_workspace(
    tmp_path, compilation, monkeypatch
):
    def boom(archive, staging_root, *, expected_package_hash=None):
        raise PackageV1IntegrityError("injected extraction failure")

    monkeypatch.setattr(vcp_artifact, "extract_vchar_v1", boom)
    (tmp_path / "workspaces").mkdir()

    assert_failed_and_clean(tmp_path, compilation, VcpArtifactStage.ROUNDTRIP, before={})


@pytest.mark.parametrize("field,value", [
    ("package_hash", "2" * 64),
])
def test_roundtrip_identity_disagreement_fails_closed(
    tmp_path, compilation, monkeypatch, field, value
):
    real = vcp_artifact.extract_vchar_v1
    monkeypatch.setattr(
        vcp_artifact, "extract_vchar_v1",
        lambda archive, staging_root, *, expected_package_hash=None: replace(
            real(archive, staging_root, expected_package_hash=expected_package_hash),
            **{field: value},
        ),
    )
    (tmp_path / "workspaces").mkdir()

    assert_failed_and_clean(tmp_path, compilation, VcpArtifactStage.ROUNDTRIP, before={})


def test_roundtrip_manifest_disagreement_fails_closed(tmp_path, compilation, monkeypatch):
    real = vcp_artifact.extract_vchar_v1

    def lying(archive, staging_root, *, expected_package_hash=None):
        verified = real(archive, staging_root, expected_package_hash=expected_package_hash)
        manifest = replace(verified.manifest, files=verified.manifest.files[:-1])
        return replace(verified, manifest=manifest)

    monkeypatch.setattr(vcp_artifact, "extract_vchar_v1", lying)
    (tmp_path / "workspaces").mkdir()

    assert_failed_and_clean(tmp_path, compilation, VcpArtifactStage.ROUNDTRIP, before={})


def test_stages_are_distinguishable_and_no_success_result_escapes(
    tmp_path, compilation, monkeypatch
):
    outcomes = {}
    injections = {
        VcpArtifactStage.MATERIALIZE: ("materialize_package_v1",
                                       lambda *a, **k: (_ for _ in ()).throw(PackageV1ContractError("x"))),
        VcpArtifactStage.DIRECTORY_VERIFY: ("verify_package_v1",
                                            lambda *a, **k: (_ for _ in ()).throw(PackageV1IntegrityError("x"))),
        VcpArtifactStage.VCHAR_WRITE: ("write_vchar_v1",
                                       lambda *a, **k: (_ for _ in ()).throw(PackageV1PathError("x"))),
        VcpArtifactStage.ROUNDTRIP: ("extract_vchar_v1",
                                     lambda *a, **k: (_ for _ in ()).throw(PackageV1IntegrityError("x"))),
    }
    for index, (stage, (name, fake)) in enumerate(injections.items()):
        with monkeypatch.context() as patch:
            patch.setattr(vcp_artifact, name, fake)
            try:
                result = build_verified_vchar_artifact(
                    compilation, workspace_path(tmp_path, f"w{index}")
                )
            except AuthoringVcpArtifactBuildError as exc:
                outcomes[stage] = exc.stage
            else:  # pragma: no cover - would be a defect
                outcomes[stage] = result
    assert outcomes == {stage: stage for stage in injections}
    assert not any(p.exists() for p in (workspace_path(tmp_path, f"w{i}") for i in range(4)))


def test_failed_build_can_be_retried_in_the_same_location(tmp_path, compilation, monkeypatch):
    workspace = workspace_path(tmp_path)
    with monkeypatch.context() as patch:
        patch.setattr(
            vcp_artifact, "write_vchar_v1",
            lambda *a, **k: (_ for _ in ()).throw(PackageV1PathError("transient")),
        )
        with pytest.raises(AuthoringVcpArtifactBuildError):
            build_verified_vchar_artifact(compilation, workspace)
    assert not workspace.exists()

    result = build_verified_vchar_artifact(compilation, workspace)

    assert result.artifact_path.is_file()


def test_cleanup_is_confined_to_the_created_workspace(tmp_path, compilation, monkeypatch):
    sibling = tmp_path / "workspaces" / "sibling"
    sibling.mkdir(parents=True)
    (sibling / "important.txt").write_bytes(b"do not touch")
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"outside")
    before = snapshot(tmp_path / "workspaces")
    monkeypatch.setattr(
        vcp_artifact, "extract_vchar_v1",
        lambda *a, **k: (_ for _ in ()).throw(PackageV1IntegrityError("x")),
    )

    with pytest.raises(AuthoringVcpArtifactBuildError):
        build_verified_vchar_artifact(compilation, workspace_path(tmp_path))

    assert snapshot(tmp_path / "workspaces") == before
    assert outside.read_bytes() == b"outside"
    assert (tmp_path / "authoring").is_dir()


def test_success_touches_nothing_outside_the_workspace(tmp_path, compilation):
    (tmp_path / "workspaces").mkdir()
    outside = tmp_path / "workspaces" / "neighbour.txt"
    outside.write_bytes(b"neighbour")
    before = {k: v for k, v in snapshot(tmp_path).items()}

    result = build_ok(tmp_path, compilation)

    after = snapshot(tmp_path)
    changed = {k for k in after if k not in before or after[k] != before[k]}
    workspace_rel = result.workspace_root.relative_to(tmp_path).as_posix()
    assert all(k == workspace_rel or k.startswith(workspace_rel + "/") for k in changed)
    assert {k for k in before if k not in after} == set()
    assert outside.read_bytes() == b"neighbour"


def test_two_builds_never_share_or_overwrite_a_workspace(tmp_path, compilation):
    first = build_ok(tmp_path, compilation, "same")
    before = snapshot(first.workspace_root)

    with pytest.raises(AuthoringVcpArtifactBuildError) as excinfo:
        build_ok(tmp_path, compilation, "same")

    assert excinfo.value.stage is VcpArtifactStage.WORKSPACE
    assert snapshot(first.workspace_root) == before


# -- result shape ---------------------------------------------------------------


def test_result_is_immutable_and_path_based(tmp_path, compilation):
    result = build_ok(tmp_path, compilation)

    assert dataclasses.is_dataclass(result)
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.package_hash = "x"  # type: ignore[misc]
    for name in ("workspace_root", "package_root", "roundtrip_root", "artifact_path"):
        assert isinstance(getattr(result, name), Path)
    assert re.fullmatch(r"[0-9a-f]{64}", result.package_hash)
    assert re.fullmatch(r"[0-9a-f]{64}", result.artifact_sha256)
    assert isinstance(result.byte_length, int) and result.byte_length > 0
    assert not any(isinstance(v, (bytes, bytearray)) for v in
                   (getattr(result, f.name) for f in dataclasses.fields(result)))


def test_builder_is_not_reexported_or_loaded_at_lab_startup():
    import services.character_publication as publication

    for name in ("build_verified_vchar_artifact", "BuiltVcpArtifact"):
        assert not hasattr(publication, name)
    probe = (
        "import sys\n"
        "import services.character_publication\n"
        "import services.character_lab_application\n"
        "assert 'voyage_character_platform' not in sys.modules\n"
        "assert 'services.character_publication.vcp_artifact' not in sys.modules\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", probe], cwd=REPO_ROOT,
        capture_output=True, text=True, check=False,
    )
    assert completed.returncode == 0, completed.stderr
