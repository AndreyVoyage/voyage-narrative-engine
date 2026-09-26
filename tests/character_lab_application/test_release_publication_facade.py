"""LAB-L5 release publication facade: orchestration, ownership, failure model.

Happy paths run the real LAB-L2/L3/L4 chain. Monkeypatching is used only to
spy on the real calls or to inject a targeted failure.
"""

from __future__ import annotations

import ast
import dataclasses
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("voyage_character_platform")

from services.character_lab_application import release_publication as rp
from services.character_lab_application.errors import ERROR_CODES
from services.character_lab_application.release_publication import (
    CharacterReleasePublicationError,
    CharacterReleasePublicationResult,
    CurrentDesignationStatus,
    ReleaseExportStatus,
    designate_canonical_current,
    publish_character_release,
)
from services.character_publication import vcp_artifact
from services.character_publication.release_store import (
    CharacterReleaseStore,
    CurrentDesignationError,
    ReleaseExportError,
    ReleaseStorageError,
)
from services.character_publication.vcp_artifact import (
    AuthoringVcpArtifactBuildError,
    BuiltVcpArtifact,
)
from services.character_publication.vcp_domains import AuthoringVcpSourcePinMismatchError
from services.character_publication.vcp_release import AuthoringVcpReleaseCompilation

from tests.character_lab_application.native_release_support import (
    CHARACTER_ID,
    RELEASE_A,
    Approved,
    durable_state,
    make_native_lab,
    sha,
    tree,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
STAGE_CODES = (
    "AUTHORING_NOT_APPROVED", "RELEASE_COMPILATION_FAILED", "ARTIFACT_BUILD_FAILED",
    "PUBLICATION_FAILED", "CURRENT_DESIGNATION_FAILED", "EXPORT_FAILED",
)


@pytest.fixture
def lab(tmp_path):
    return make_native_lab(tmp_path)


def assert_no_release(lab):
    assert lab.releases.list_release_ids(CHARACTER_ID) == ()
    assert not (lab.releases.root / "releases").exists() or not list(
        (lab.releases.root / "releases").rglob("*.json")
    )
    assert lab.releases.get_canonical_current(CHARACTER_ID) is None


def test_stage_codes_are_registered_application_codes():
    for code in STAGE_CODES:
        assert code in ERROR_CODES


# ===== orchestration ===============================================================


def test_facade_orchestrates_exact_coordinate_through_l2_l3_l4(lab, monkeypatch):
    approved = lab.approved_v1()
    calls = []
    real_compile = rp.compile_authoring_release
    real_build = rp.build_verified_vchar_artifact
    real_publish = CharacterReleaseStore.publish_release

    def compile_spy(store, **kwargs):
        compilation = real_compile(store, **kwargs)
        calls.append(("L2", kwargs, compilation))
        return compilation

    def build_spy(compilation, workspace_root):
        built = real_build(compilation, workspace_root)
        calls.append(("L3", compilation, built))
        return built

    def publish_spy(self, built, *, authoring_store):
        published = real_publish(self, built, authoring_store=authoring_store)
        calls.append(("L4", built, published))
        return published

    monkeypatch.setattr(rp, "compile_authoring_release", compile_spy)
    monkeypatch.setattr(rp, "build_verified_vchar_artifact", build_spy)
    monkeypatch.setattr(CharacterReleaseStore, "publish_release", publish_spy)

    result = publish_character_release(**lab.publish_kwargs(approved))

    assert [c[0] for c in calls] == ["L2", "L3", "L4"]
    assert calls[0][1] == dict(
        character_id=CHARACTER_ID, version_id=approved.version_id,
        revision_id=approved.revision_id, snapshot_hash=approved.snapshot_hash,
        release_id=RELEASE_A, display_name="Native Control E2E",
    )
    compilation = calls[0][2]
    assert isinstance(compilation, AuthoringVcpReleaseCompilation)
    assert calls[1][1] is compilation  # L3 consumes the exact L2 result
    built = calls[1][2]
    assert isinstance(built, BuiltVcpArtifact)
    assert calls[2][1] is built  # L4 consumes the exact L3 artifact
    assert built.workspace_root.parent.parent == lab.builds  # L5-owned op dir
    assert result.package_hash == built.package_hash
    assert result.artifact_sha256 == built.artifact_sha256
    assert result.newly_published is True


def test_default_does_not_set_current(lab, monkeypatch):
    designations = []
    real = CharacterReleaseStore.set_canonical_current
    monkeypatch.setattr(
        CharacterReleaseStore, "set_canonical_current",
        lambda self, *a: designations.append(a) or real(self, *a),
    )

    result = publish_character_release(**lab.publish_kwargs(lab.approved_v1()))

    assert designations == []
    assert result.current_status is CurrentDesignationStatus.NOT_REQUESTED
    assert lab.releases.get_canonical_current(CHARACTER_ID) is None


def test_explicit_current_designates_after_publication(lab, monkeypatch):
    order = []
    real_publish = CharacterReleaseStore.publish_release
    real_set = CharacterReleaseStore.set_canonical_current

    def publish_spy(self, built, *, authoring_store):
        published = real_publish(self, built, authoring_store=authoring_store)
        order.append(("publish", published.newly_published))
        return published

    def set_spy(self, character_id, release_id):
        # the release is already durable when designation starts
        assert self.load_release_record(character_id, release_id)
        order.append(("set_current", release_id))
        return real_set(self, character_id, release_id)

    monkeypatch.setattr(CharacterReleaseStore, "publish_release", publish_spy)
    monkeypatch.setattr(CharacterReleaseStore, "set_canonical_current", set_spy)

    result = publish_character_release(**lab.publish_kwargs(lab.approved_v1(), set_current=True))

    assert order == [("publish", True), ("set_current", RELEASE_A)]
    assert result.current_status is CurrentDesignationStatus.DESIGNATED
    assert result.current_generation == 1
    current = lab.releases.get_canonical_current(CHARACTER_ID)
    assert (current.release_id, current.package_hash) == (RELEASE_A, result.package_hash)


def test_set_current_on_already_current_release_reports_already_current(lab):
    approved = lab.approved_v1()
    publish_character_release(**lab.publish_kwargs(approved, set_current=True))

    again = publish_character_release(**lab.publish_kwargs(approved, set_current=True))

    assert again.newly_published is False
    assert again.current_status is CurrentDesignationStatus.ALREADY_CURRENT
    assert again.current_generation == 1


# ===== partial success ================================================================


def test_publication_survives_designation_failure(lab, monkeypatch):
    lower = CurrentDesignationError("injected designation failure")

    def fail(self, character_id, release_id):
        raise lower

    monkeypatch.setattr(CharacterReleaseStore, "set_canonical_current", fail)

    with pytest.raises(CharacterReleasePublicationError) as caught:
        publish_character_release(**lab.publish_kwargs(lab.approved_v1(), set_current=True))

    error = caught.value
    assert error.code == "CURRENT_DESIGNATION_FAILED"
    assert error.lower_code == "CURRENT_DESIGNATION_FAILED"
    assert error.__cause__ is lower
    assert error.published is True and error.details["published"] is True
    partial = error.result
    assert partial.newly_published is True
    assert partial.current_status is CurrentDesignationStatus.FAILED
    assert partial.current_generation is None
    # the release is durable and was NOT rolled back
    verified = lab.releases.verify_release(CHARACTER_ID, RELEASE_A)
    assert verified.record.package_hash == partial.package_hash
    assert lab.releases.get_canonical_current(CHARACTER_ID) is None
    assert list(lab.builds.iterdir()) == []


def test_export_failure_keeps_release_and_current(lab, tmp_path):
    exports = tmp_path / "exports"
    exports.mkdir()
    occupied = exports / "taken.vchar"
    occupied.write_bytes(b"caller data")

    with pytest.raises(CharacterReleasePublicationError) as caught:
        publish_character_release(
            **lab.publish_kwargs(
                lab.approved_v1(), set_current=True, export_destination=occupied
            )
        )

    error = caught.value
    assert error.code == "EXPORT_FAILED" and error.lower_code == "RELEASE_EXPORT_FAILED"
    assert isinstance(error.__cause__, ReleaseExportError)
    partial = error.result
    assert error.published is True
    assert partial.current_status is CurrentDesignationStatus.DESIGNATED
    assert partial.export_status is ReleaseExportStatus.FAILED and partial.export is None
    assert occupied.read_bytes() == b"caller data"
    assert lab.releases.verify_release(CHARACTER_ID, RELEASE_A)
    current = lab.releases.get_canonical_current(CHARACTER_ID)
    assert current.release_id == RELEASE_A and current.generation == 1


def test_export_reads_the_durable_store_after_workspace_cleanup(lab, tmp_path, monkeypatch):
    seen = []
    real_export = CharacterReleaseStore.export_release

    def export_spy(self, character_id, release_id, destination):
        seen.append(list(lab.builds.iterdir()))  # workspace already removed
        return real_export(self, character_id, release_id, destination)

    monkeypatch.setattr(CharacterReleaseStore, "export_release", export_spy)
    target = tmp_path / "out.vchar"

    result = publish_character_release(
        **lab.publish_kwargs(lab.approved_v1(), export_destination=target)
    )

    assert seen == [[]]
    assert result.export_status is ReleaseExportStatus.EXPORTED
    assert result.export.destination == target
    durable = lab.releases.verify_release(CHARACTER_ID, RELEASE_A).artifact_path.read_bytes()
    assert target.read_bytes() == durable
    assert sha(durable) == result.export.artifact_sha256 == result.artifact_sha256
    assert result.current_status is CurrentDesignationStatus.NOT_REQUESTED


# ===== pre-publication failures ====================================================


@pytest.mark.parametrize("stage", ["draft", "pending"])
def test_unapproved_authoring_is_rejected_before_any_build(lab, stage, monkeypatch):
    built = []
    monkeypatch.setattr(rp, "build_verified_vchar_artifact", lambda *a: built.append(a))
    created = lab.create_draft()
    if stage == "pending":
        lab.service.submit_for_approval(
            character_id=CHARACTER_ID, version_id="native-v1",
            revision_id="native-v1-r1", snapshot_hash=created.snapshot_hash,
        )

    with pytest.raises(CharacterReleasePublicationError) as caught:
        publish_character_release(
            **lab.publish_kwargs(Approved("native-v1", "native-v1-r1", created.snapshot_hash))
        )

    assert caught.value.code == "AUTHORING_NOT_APPROVED"
    assert caught.value.published is False
    assert built == []
    assert list(lab.builds.iterdir()) == []
    assert_no_release(lab)


def test_stale_snapshot_is_a_compilation_failure_with_cause(lab):
    approved = lab.approved_v1()
    stale = dataclasses.replace(approved, snapshot_hash="0" * 64)

    with pytest.raises(CharacterReleasePublicationError) as caught:
        publish_character_release(**lab.publish_kwargs(stale))

    assert caught.value.code == "RELEASE_COMPILATION_FAILED"
    assert isinstance(caught.value.__cause__, AuthoringVcpSourcePinMismatchError)
    assert list(lab.builds.iterdir()) == []
    assert_no_release(lab)


def test_artifact_build_failure_cleans_owned_workspace_only(lab, monkeypatch):
    sentinel = lab.builds / "caller-owned.txt"
    sentinel.write_text("keep me", encoding="utf-8")
    lower = ValueError("injected writer failure")

    def failing_writer(*_a, **_k):
        raise lower

    monkeypatch.setattr(vcp_artifact, "write_vchar_v1", failing_writer)

    with pytest.raises(CharacterReleasePublicationError) as caught:
        publish_character_release(**lab.publish_kwargs(lab.approved_v1()))

    error = caught.value
    assert error.code == "ARTIFACT_BUILD_FAILED" and error.lower_code == "VCHAR_WRITE"
    assert isinstance(error.__cause__, AuthoringVcpArtifactBuildError)
    assert error.__cause__.__cause__ is lower
    assert [p.name for p in lab.builds.iterdir()] == ["caller-owned.txt"]
    assert sentinel.read_text(encoding="utf-8") == "keep me"
    assert_no_release(lab)


def test_publication_failure_commits_nothing_and_cleans_workspace(lab, monkeypatch):
    def failing_commit(self, record):
        raise OSError("injected commit failure")

    monkeypatch.setattr(CharacterReleaseStore, "_commit_record", failing_commit)

    with pytest.raises(CharacterReleasePublicationError) as caught:
        publish_character_release(**lab.publish_kwargs(lab.approved_v1()))

    error = caught.value
    assert error.code == "PUBLICATION_FAILED" and error.lower_code == "RELEASE_STORAGE_FAILED"
    assert isinstance(error.__cause__, ReleaseStorageError)
    assert error.published is False and error.result is None
    assert list(lab.builds.iterdir()) == []
    assert_no_release(lab)


def test_invalid_inputs_are_rejected_before_any_work(lab):
    approved = lab.approved_v1()
    cases = [
        dict(release_id="bad id"),
        dict(release_id=""),
        dict(set_current="yes"),
        dict(build_workspace_root="relative/builds"),
        dict(build_workspace_root=lab.tmp / "missing"),
        dict(build_workspace_root=lab.releases.root),
        dict(release_store=object()),
        dict(authoring_store=object()),
    ]
    for override in cases:
        with pytest.raises(CharacterReleasePublicationError) as caught:
            publish_character_release(**lab.publish_kwargs(approved, **override))
        assert caught.value.code == "INVALID_INPUT", override
    assert list(lab.builds.iterdir()) == []
    assert_no_release(lab)


def test_release_id_and_display_name_are_never_derived(lab):
    approved = lab.approved_v1()
    result = publish_character_release(
        **lab.publish_kwargs(approved, release_id="operator-chosen-7",
                             display_name="Operator Display")
    )
    assert result.release_id == "operator-chosen-7"
    for derived in (approved.version_id, approved.revision_id, approved.snapshot_hash):
        assert derived not in result.release_id


# ===== ownership, immutability, leaks ============================================


def test_cleanup_never_touches_store_authoring_or_caller_data(lab):
    keep_dir = lab.builds / "caller-dir"
    keep_dir.mkdir()
    (keep_dir / "note.txt").write_text("caller", encoding="utf-8")
    approved = lab.approved_v1()
    authoring_before = tree(lab.authoring.root)
    assert authoring_before

    result = publish_character_release(**lab.publish_kwargs(approved))

    assert result.build_workspace_cleaned is True
    assert [p.name for p in lab.builds.iterdir()] == ["caller-dir"]
    assert (keep_dir / "note.txt").read_text(encoding="utf-8") == "caller"
    assert tree(lab.authoring.root) == authoring_before
    durable = durable_state(lab.releases)
    assert f"releases/{CHARACTER_ID}/{RELEASE_A}.json" in durable
    assert f"artifacts/{result.package_hash}.vchar" in durable


def test_result_is_immutable_and_path_free(lab):
    result = publish_character_release(**lab.publish_kwargs(lab.approved_v1()))

    with pytest.raises(dataclasses.FrozenInstanceError):
        result.release_id = "other"  # type: ignore[misc]
    for field in dataclasses.fields(CharacterReleasePublicationResult):
        value = getattr(result, field.name)
        assert not isinstance(value, Path), field.name
        if isinstance(value, str):
            assert str(lab.builds) not in value and str(lab.releases.root) not in value
            for internal in ("artifact.vchar", "roundtrip", ".vchar", "/", "\\"):
                assert internal not in value, (field.name, value)
    assert result.published is True


def test_designation_facade_is_explicit_and_path_free(lab):
    publish_character_release(**lab.publish_kwargs(lab.approved_v1()))

    designation = designate_canonical_current(
        release_store=lab.releases, character_id=CHARACTER_ID, release_id=RELEASE_A
    )
    assert designation.status is CurrentDesignationStatus.DESIGNATED
    with pytest.raises(dataclasses.FrozenInstanceError):
        designation.generation = 9  # type: ignore[misc]

    with pytest.raises(CharacterReleasePublicationError) as caught:
        designate_canonical_current(
            release_store=lab.releases, character_id=CHARACTER_ID, release_id="never-published"
        )
    assert caught.value.code == "CURRENT_DESIGNATION_FAILED"
    assert caught.value.lower_code == "RELEASE_NOT_FOUND"
    assert lab.releases.get_canonical_current(CHARACTER_ID).release_id == RELEASE_A


# ===== no reimplementation / import boundary =====================================


def test_facade_does_not_reimplement_vcp_package_or_store_semantics():
    source = Path(rp.__file__).read_text(encoding="utf-8")
    tree_ = ast.parse(source)
    imported = set()
    for node in ast.walk(tree_):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
    assert not any(name.startswith("voyage_character_platform") for name in imported)
    for forbidden in ("hashlib", "json", "zipfile"):
        assert forbidden not in imported
    for vcp_call in ("materialize_package_v1", "verify_package_v1", "write_vchar_v1",
                     "extract_vchar_v1", "create_manifest", "canonical_json_bytes"):
        assert vcp_call not in source


def test_facade_is_not_loaded_at_lab_startup():
    import services.character_lab_application as application

    assert not hasattr(application, "publish_character_release")
    probe = (
        "import sys\n"
        "import services.character_lab_application\n"
        "assert 'voyage_character_platform' not in sys.modules\n"
        "assert 'services.character_lab_application.release_publication' not in sys.modules\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", probe], cwd=REPO_ROOT, capture_output=True, text=True, check=False
    )
    assert completed.returncode == 0, completed.stderr
