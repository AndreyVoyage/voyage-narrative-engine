"""LAB-L5 FIRST NATIVE E2E: a clean control character, end to end, no mocks.

Authoring API -> immutable revision -> LAB-L1 approval -> LAB-L5 facade
(LAB-L2 compile -> LAB-L3 build via real VCP -> LAB-L4 publish) -> explicit
current -> exact export -> authoritative VCP extraction of the export.

Nothing in this module is mocked or monkeypatched.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests._vcp_dependency_gate import require_pinned_vcp

require_pinned_vcp()  # hard VCP dependency gate (replaces silent importorskip)

from services.character_authoring import LifecycleState
from services.character_lab_application.release_publication import (
    CharacterReleasePublicationError,
    CurrentDesignationStatus,
    ReleaseExportStatus,
    designate_canonical_current,
    export_character_release,
    publish_character_release,
)
from services.character_publication.release_store import ReleaseIdHashCollisionError
from services.character_publication.vcp_release import compile_authoring_release
from voyage_character_platform.vchar import extract_vchar_v1

from tests.character_lab_application.native_release_support import (
    APPROVED_AT,
    CHARACTER_ID,
    DECIDED_BY,
    DISPLAY_NAME,
    RELEASE_A,
    RELEASE_B,
    durable_state,
    make_native_lab,
    native_semantic,
    native_semantic_with_sexology,
    sha,
    tree,
)


@pytest.fixture
def lab(tmp_path):
    return make_native_lab(tmp_path)


def test_pinned_vcp_dependency_identity_is_enforced():
    """The publication chain ran against the exact pinned VCP distribution.

    This is the missing dependency-slice assertion: it proves the imported
    ``voyage_character_platform`` is the pinned commit's wheel (via tracked
    provenance), not a live source checkout, ambient install or stale wheel.
    """
    from tests._vcp_dependency_gate import pinned_vcp_identity

    identity = pinned_vcp_identity()
    assert identity["source_commit"] == "ccade9e0ef943f63fec703b7ed5b436d7520324a"
    assert identity["dist_name"] == "voyage-character-platform"
    assert identity["dist_version"] == "0.1.0"
    assert identity["wheel_filename"] == "voyage_character_platform-0.1.0-py3-none-any.whl"
    assert "site-packages" in identity["module_file"].parts
    assert "build" in identity["module_file"].parts and "output" in identity["module_file"].parts


def test_first_native_control_character_end_to_end(lab):
    # -- 16/17: native Authoring creation + an edited immutable revision -------------
    created = lab.create_draft()
    assert created.lifecycle_state == "DRAFT"
    edited = lab.service.save_character(
        character_id=CHARACTER_ID, version_id="native-v1", revision_id="native-v1-r2",
        semantic=native_semantic("Synthetic control biography, edited."),
    )
    assert edited.snapshot_hash != created.snapshot_hash
    first = lab.authoring.load_revision(CHARACTER_ID, "native-v1", "native-v1-r1")
    second = lab.authoring.load_revision(CHARACTER_ID, "native-v1", "native-v1-r2")
    assert first.snapshot_hash == created.snapshot_hash  # earlier revision untouched
    assert second.snapshot_hash == edited.snapshot_hash

    # -- 18/19: real LAB-L1 approval, persisted ApprovalEvidence ---------------------
    approved = lab.approve("native-v1", "native-v1-r2", edited.snapshot_hash)
    pointer = lab.authoring.read_version_pointer(CHARACTER_ID, "native-v1")
    assert pointer.lifecycle_state is LifecycleState.APPROVED_AS_CANON
    assert pointer.selected_revision_id == "native-v1-r2"
    evidence = lab.authoring.load_approval_evidence(CHARACTER_ID, "native-v1", "native-v1-r2")
    assert evidence.decision == "HUMAN_APPROVED"
    assert evidence.decided_by == DECIDED_BY
    assert evidence.decided_at == "2026-09-01T12:00:00Z" == APPROVED_AT.strftime("%Y-%m-%dT%H:%M:%SZ")
    assert evidence.snapshot_hash == edited.snapshot_hash

    # -- 20-22: facade publish through real L2/L3/L4, current NOT requested ----------
    assert lab.releases.get_canonical_current(CHARACTER_ID) is None
    result = publish_character_release(**lab.publish_kwargs(approved))

    assert result.published is True and result.newly_published is True
    assert (result.character_id, result.release_id) == (CHARACTER_ID, RELEASE_A)
    assert (result.source_version_id, result.source_revision_id, result.source_snapshot_hash) == (
        "native-v1", "native-v1-r2", edited.snapshot_hash
    )
    # 23: publish != current
    assert result.current_status is CurrentDesignationStatus.NOT_REQUESTED
    assert result.current_generation is None
    assert result.export_status is ReleaseExportStatus.NOT_REQUESTED and result.export is None
    assert lab.releases.get_canonical_current(CHARACTER_ID) is None
    assert not (lab.releases.root / "current").exists()
    assert lab.releases.list_release_ids(CHARACTER_ID) == (RELEASE_A,)

    # 20: the L2 bindings are exactly what the pure LAB-L2 compiler yields
    compilation = compile_authoring_release(
        lab.authoring, character_id=CHARACTER_ID, version_id="native-v1",
        revision_id="native-v1-r2", snapshot_hash=edited.snapshot_hash,
        release_id=RELEASE_A, display_name=DISPLAY_NAME,
    )
    assert result.aggregate_candidate_id == compilation.aggregate_candidate_id
    assert result.aggregate_hash == compilation.aggregate_hash
    assert result.acceptance_record_hash == compilation.acceptance_record_hash

    # -- 25: the L5-owned build workspace is gone; durable state stands alone -------
    assert result.build_workspace_cleaned is True
    assert list(lab.builds.iterdir()) == []

    # 22: LAB-L4 durable verification (record + stored artifact through VCP)
    verified = lab.releases.verify_release(CHARACTER_ID, RELEASE_A)
    record = verified.record
    assert record.character_id == CHARACTER_ID and record.release_id == RELEASE_A
    assert record.package_hash == result.package_hash
    assert record.artifact_sha256 == result.artifact_sha256
    assert record.byte_length == result.byte_length
    assert record.aggregate_hash == result.aggregate_hash
    assert record.aggregate_candidate_id == result.aggregate_candidate_id
    assert record.acceptance_record_hash == result.acceptance_record_hash
    assert record.published_at == result.published_at
    assert record.approval.decided_by == DECIDED_BY
    durable_bytes = verified.artifact_path.read_bytes()
    assert sha(durable_bytes) == result.artifact_sha256
    assert len(durable_bytes) == result.byte_length

    # 21: real VCP extraction of the durable artifact (L3 package identity)
    durable_pkg = extract_vchar_v1(
        verified.artifact_path, lab.tmp / "durable_extract",
        expected_package_hash=result.package_hash,
    )
    assert durable_pkg.metadata.display_name == DISPLAY_NAME

    # -- 24: explicit current, without any rebuild ------------------------------------
    state_before_designation = tree(lab.releases.root / "artifacts")
    designation = designate_canonical_current(
        release_store=lab.releases, character_id=CHARACTER_ID, release_id=RELEASE_A,
    )
    assert designation.status is CurrentDesignationStatus.DESIGNATED
    assert designation.generation == 1
    current = lab.releases.get_canonical_current(CHARACTER_ID)
    assert (current.release_id, current.package_hash, current.generation) == (
        RELEASE_A, result.package_hash, 1
    )
    assert tree(lab.releases.root / "artifacts") == state_before_designation
    assert list(lab.builds.iterdir()) == []  # nothing was built to designate
    again = designate_canonical_current(
        release_store=lab.releases, character_id=CHARACTER_ID, release_id=RELEASE_A,
    )
    assert again.status is CurrentDesignationStatus.ALREADY_CURRENT and again.generation == 1

    # -- 26-32: exact export from the durable store, extracted by VCP ---------------
    exports = lab.tmp / "exports"
    exports.mkdir()
    exported = export_character_release(
        release_store=lab.releases, character_id=CHARACTER_ID, release_id=RELEASE_A,
        destination=exports / "native-control.vchar",
    )
    exported_bytes = exported.destination.read_bytes()
    assert exported_bytes == durable_bytes
    assert sha(exported_bytes) == exported.artifact_sha256 == record.artifact_sha256
    assert len(exported_bytes) == exported.byte_length == record.byte_length
    package = extract_vchar_v1(
        exported.destination, lab.tmp / "export_extract",
        expected_package_hash=result.package_hash,
    )
    assert package.metadata.character_id == CHARACTER_ID
    assert package.metadata.release_id == RELEASE_A
    assert package.package_hash == result.package_hash
    assert package.metadata.accepted_aggregate_hash == result.aggregate_hash
    assert package.metadata.acceptance_record_hash == result.acceptance_record_hash

    # -- 33/34: exact idempotent republish in a NEW temporary build workspace -------
    durable_before = durable_state(lab.releases)
    other_builds = lab.tmp / "builds-second"
    other_builds.mkdir()
    republished = publish_character_release(
        **lab.publish_kwargs(approved, build_workspace_root=other_builds)
    )
    assert republished.newly_published is False
    assert republished.package_hash == result.package_hash
    assert republished.artifact_sha256 == result.artifact_sha256
    assert republished.published_at == result.published_at
    assert republished.current_status is CurrentDesignationStatus.NOT_REQUESTED
    assert list(other_builds.iterdir()) == []
    assert durable_state(lab.releases) == durable_before  # no second durable release
    assert lab.releases.list_release_ids(CHARACTER_ID) == (RELEASE_A,)
    assert len(list((lab.releases.root / "artifacts").iterdir())) == 1
    assert lab.releases.get_canonical_current(CHARACTER_ID) == current


def test_native_release_id_collision_surfaces_unchanged(lab):
    first = lab.approved_v1()
    published = publish_character_release(**lab.publish_kwargs(first, set_current=True))
    assert published.current_status is CurrentDesignationStatus.DESIGNATED
    durable_before = durable_state(lab.releases)
    current_before = lab.releases.get_canonical_current(CHARACTER_ID)

    different = lab.approved_v2()  # genuinely different approved candidate
    assert different.snapshot_hash != first.snapshot_hash
    with pytest.raises(CharacterReleasePublicationError) as caught:
        publish_character_release(**lab.publish_kwargs(different, release_id=RELEASE_A))

    error = caught.value
    assert error.code == "PUBLICATION_FAILED"
    assert error.lower_code == "RELEASE_ID_HASH_COLLISION"
    assert isinstance(error.__cause__, ReleaseIdHashCollisionError)
    assert error.published is False and error.result is None
    assert durable_state(lab.releases) == durable_before
    assert lab.releases.get_canonical_current(CHARACTER_ID) == current_before
    assert lab.releases.verify_release(CHARACTER_ID, RELEASE_A).record.package_hash == (
        published.package_hash
    )
    assert list(lab.builds.iterdir()) == []


def test_native_designation_rollback_a_b_a(lab):
    release_a = publish_character_release(**lab.publish_kwargs(lab.approved_v1(), RELEASE_A))
    release_b = publish_character_release(**lab.publish_kwargs(lab.approved_v2(), RELEASE_B))
    assert release_a.package_hash != release_b.package_hash

    def release_state():
        return {
            name: value for name, value in durable_state(lab.releases).items()
            if name.startswith(("artifacts/", "releases/"))
        }

    before = release_state()
    assert len([k for k in before if k.startswith("artifacts/")]) == 2

    for release_id in (RELEASE_A, RELEASE_B, RELEASE_A):
        designate_canonical_current(
            release_store=lab.releases, character_id=CHARACTER_ID, release_id=release_id,
        )

    history = lab.releases.read_designation_history(CHARACTER_ID)
    assert [entry.generation for entry in history] == [1, 2, 3]
    assert [entry.to_release_id for entry in history] == [RELEASE_A, RELEASE_B, RELEASE_A]
    assert [entry.from_release_id for entry in history] == [None, RELEASE_A, RELEASE_B]
    assert lab.releases.pending_designation(CHARACTER_ID) is None
    final = lab.releases.get_canonical_current(CHARACTER_ID)
    assert (final.release_id, final.package_hash, final.generation) == (
        RELEASE_A, release_a.package_hash, 3
    )
    assert release_state() == before  # records and .vchar bytes untouched
    for release in (release_a, release_b):
        record = lab.releases.verify_release(CHARACTER_ID, release.release_id).record
        assert (record.package_hash, record.artifact_sha256, record.published_at) == (
            release.package_hash, release.artifact_sha256, release.published_at
        )


SEXOLOGY_CHARACTER_ID = "native-sexology-e2e"
SEXOLOGY_RELEASE_ID = "native-sexology-r1"


def test_native_release_with_sexology_end_to_end(lab):
    # Draft -> immutable revision with populated sexology + descriptions.
    created = lab.service.create_character(
        character_id=SEXOLOGY_CHARACTER_ID,
        version_id="sexology-v1",
        revision_id="sexology-v1-r1",
        version_label="Sexology v1",
        semantic=native_semantic_with_sexology(),
    )
    assert created.lifecycle_state == "DRAFT"

    # Human approval evidence.
    lab.service.submit_for_approval(
        character_id=SEXOLOGY_CHARACTER_ID,
        version_id="sexology-v1",
        revision_id="sexology-v1-r1",
        snapshot_hash=created.snapshot_hash,
    )
    approved = lab.service.approve_as_canon(
        character_id=SEXOLOGY_CHARACTER_ID,
        version_id="sexology-v1",
        revision_id="sexology-v1-r1",
        snapshot_hash=created.snapshot_hash,
        decided_by=DECIDED_BY,
    )
    assert approved.lifecycle_state == "APPROVED_AS_CANON"

    # LAB-L2 compile: six required + optional intimacy.
    compilation = compile_authoring_release(
        lab.authoring,
        character_id=SEXOLOGY_CHARACTER_ID,
        version_id="sexology-v1",
        revision_id="sexology-v1-r1",
        snapshot_hash=created.snapshot_hash,
        release_id=SEXOLOGY_RELEASE_ID,
        display_name="Sexology E2E",
    )
    assert tuple(d.domain_id for d in compilation.domains) == (
        "core_identity",
        "psychology",
        "speech",
        "relationships",
        "visual_identity",
        "interaction_boundaries",
        "intimacy",
    )
    assert "intimacy" in compilation.domain_hashes_at_accept

    # Publish through LAB-L2/L3/L4 (authoritative VCP verification inside).
    result = publish_character_release(
        authoring_store=lab.authoring,
        release_store=lab.releases,
        character_id=SEXOLOGY_CHARACTER_ID,
        version_id="sexology-v1",
        revision_id="sexology-v1-r1",
        snapshot_hash=created.snapshot_hash,
        release_id=SEXOLOGY_RELEASE_ID,
        display_name="Sexology E2E",
        build_workspace_root=lab.builds,
    )
    assert result.published is True and result.newly_published is True
    assert result.aggregate_hash == compilation.aggregate_hash
    assert list(lab.builds.iterdir()) == []

    # Durable stored verification.
    verified = lab.releases.verify_release(SEXOLOGY_CHARACTER_ID, SEXOLOGY_RELEASE_ID)
    record = verified.record
    assert record.package_hash == result.package_hash
    assert record.aggregate_hash == result.aggregate_hash

    # Authoritative extraction of the durable artifact: intimacy is present.
    durable_pkg = extract_vchar_v1(
        verified.artifact_path,
        lab.tmp / "durable_extract",
        expected_package_hash=result.package_hash,
    )
    assert durable_pkg.metadata.character_id == SEXOLOGY_CHARACTER_ID
    assert (durable_pkg.root / "domains" / "intimacy.json").exists()

    # Exact export of the stored .vchar, verified authoritatively.
    exports = lab.tmp / "exports"
    exports.mkdir()
    exported = export_character_release(
        release_store=lab.releases,
        character_id=SEXOLOGY_CHARACTER_ID,
        release_id=SEXOLOGY_RELEASE_ID,
        destination=exports / "sexology.vchar",
    )
    assert exported.package_hash == result.package_hash
    assert exported.artifact_sha256 == result.artifact_sha256
    exported_pkg = extract_vchar_v1(
        exported.destination,
        lab.tmp / "export_extract",
        expected_package_hash=result.package_hash,
    )
    assert (exported_pkg.root / "domains" / "intimacy.json").exists()
