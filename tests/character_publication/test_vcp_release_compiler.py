"""LAB-L2 RELEASE_COMPILER_V1: pure ACCEPTED_RELEASE logical-file compilation."""

from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

# VCP operational dependency wiring is deferred; without the distribution the
# module is skipped instead of failing collection.
pytest.importorskip("voyage_character_platform")

from services.character_authoring import (
    ApprovalEvidence,
    CharacterAuthoringStore,
    LifecycleState,
)
from services.character_lab_application import (
    CharacterLabApplicationConfig,
    CharacterLabApplicationService,
)
from services.character_publication.vcp_domains import (
    AuthoringVcpDomainCompilation,
    AuthoringVcpSourcePinMismatchError,
    AuthoringVcpVisualMappingError,
    compile_authoring_revision_to_vcp_domains,
)
from services.character_publication.vcp_release import (
    AuthoringVcpApprovalEvidenceError,
    AuthoringVcpReleaseCompilation,
    AuthoringVcpReleaseCompilationError,
    build_authoring_release_compilation,
    compile_authoring_release,
    compute_aggregate_hash,
)
from voyage_character_platform.contracts import ContentState, DomainEnvelope
from voyage_character_platform.package_v1 import (
    PackageV1Error,
    materialize_package_v1,
    verify_package_v1,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DECIDED_AT = "2026-03-04T05:06:07Z"
DECIDED_BY = "Андрей  Approver "
FIXED_MOMENT = datetime(2026, 3, 4, 5, 6, 7, tzinfo=timezone.utc)

SIX = (
    "core_identity",
    "psychology",
    "speech",
    "relationships",
    "visual_identity",
    "interaction_boundaries",
)
EXPECTED_PATHS = sorted(
    [
        "package.json",
        "provenance/acceptance.json",
        "provenance/provenance.json",
        "provenance/contradictions.json",
        "unknowns/unknowns.json",
        *(f"domains/{domain}.json" for domain in SIX),
    ]
)


# -- independent oracle (deliberately not the implementation's helpers) -----


def canon(payload) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def expected_candidate_id(character_id, version_id, revision_id, snapshot_hash):
    return "vcprec1-" + sha(
        canon(
            {
                "aggregate_candidate_id_schema_version": "vcp_aggregate_candidate_id/1.0",
                "character_id": character_id,
                "version_id": version_id,
                "revision_id": revision_id,
                "snapshot_hash": snapshot_hash,
            }
        )
    )


def expected_domain_hashes(store, character_id, version_id, revision_id, snapshot_hash):
    compilation = compile_authoring_revision_to_vcp_domains(
        store,
        character_id=character_id,
        version_id=version_id,
        revision_id=revision_id,
        snapshot_hash=snapshot_hash,
    )
    return {
        domain.domain_id: sha(canon(domain.to_dict())) for domain in compilation.domains
    }, compilation


# -- fixtures ---------------------------------------------------------------


def semantic(name="Atlas", **overrides) -> dict:
    value = {
        "identity": {"display_name": name, "kind": "IDENTITY_KIND_SENTINEL"},
        "biography": "BIOGRAPHY_SENTINEL",
        "psychology": {
            "personality": ["PSYCHOLOGY_SENTINEL"],
            "behavioral_traits": ["BEHAVIOR_SENTINEL"],
            "emotional_tendencies": ["EMOTION_SENTINEL"],
            "goals_motivations": ["GOAL_SENTINEL"],
        },
        "speech": {"speech_style": "SPEECH_SENTINEL", "register": None},
        "character_relations": {
            "relational_tendencies": ["RELATIONSHIP_SENTINEL"],
            "attachment_traits": ["ATTACHMENT_SENTINEL"],
        },
        "appearance": {"descriptors": ["APPEARANCE_SENTINEL"], "height_cm": 181},
        "boundaries": {"principles": ["BOUNDARY_SENTINEL"]},
        "visual_identity": {},
    }
    value.update(overrides)
    return value


def empty_semantic() -> dict:
    return {
        "identity": {},
        "biography": "",
        "psychology": {
            "personality": [],
            "behavioral_traits": [],
            "emotional_tendencies": [],
            "goals_motivations": [],
        },
        "speech": {"speech_style": "", "register": None},
        "character_relations": {"relational_tendencies": [], "attachment_traits": []},
        "appearance": {},
        "boundaries": {},
        "visual_identity": {"references": []},
    }


def approved(tmp_path, *, body=None, decided_by=DECIDED_BY):
    """Create, submit and approve through the real LAB-L1 workflow."""

    root = tmp_path / "authoring"
    service = CharacterLabApplicationService(
        CharacterLabApplicationConfig(character_authoring_root=root),
        approval_clock=lambda: FIXED_MOMENT,
    )
    created = service.create_character(
        character_id="atlas",
        version_id="version-v1",
        revision_id="revision-r1",
        version_label="Version 1",
        semantic=semantic() if body is None else body,
    )
    service.submit_for_approval(
        character_id="atlas",
        version_id="version-v1",
        revision_id="revision-r1",
        snapshot_hash=created.snapshot_hash,
    )
    service.approve_as_canon(
        character_id="atlas",
        version_id="version-v1",
        revision_id="revision-r1",
        snapshot_hash=created.snapshot_hash,
        decided_by=decided_by,
    )
    return CharacterAuthoringStore(root), created


def compile_release(store, created, *, release_id="release-one", display_name="Атлас"):
    return compile_authoring_release(
        store,
        character_id="atlas",
        version_id="version-v1",
        revision_id="revision-r1",
        snapshot_hash=created.snapshot_hash,
        release_id=release_id,
        display_name=display_name,
    )


def files_under(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def load(result, path):
    return json.loads(result.files[path].content.decode("utf-8"))


# -- 1-3: valid compile, exact file set, six domains ------------------------


def test_valid_exact_revision_and_evidence_compile(tmp_path):
    store, created = approved(tmp_path)

    result = compile_release(store, created)

    assert isinstance(result, AuthoringVcpReleaseCompilation)
    assert result.source.to_dict() == {
        "source_character_id": "atlas",
        "source_version_id": "version-v1",
        "source_revision_id": "revision-r1",
        "source_snapshot_hash": created.snapshot_hash,
    }


def test_output_is_exactly_the_required_logical_package_files(tmp_path):
    store, created = approved(tmp_path)

    result = compile_release(store, created)

    assert sorted(result.files) == EXPECTED_PATHS
    assert list(result.files) == EXPECTED_PATHS  # deterministic order
    for package_file in result.files.values():
        assert package_file.normalization == "CANONICAL_JSON_V1"
        assert package_file.required is True
        assert isinstance(package_file.content, bytes)
    roles = {path: f.semantic_role for path, f in result.files.items()}
    assert roles["package.json"] == "PACKAGE_METADATA"
    assert roles["provenance/acceptance.json"] == "ACCEPTANCE"
    assert roles["provenance/provenance.json"] == "PROVENANCE"
    assert roles["provenance/contradictions.json"] == "CONTRADICTIONS"
    assert roles["unknowns/unknowns.json"] == "UNKNOWNS"
    assert {roles[f"domains/{d}.json"] for d in SIX} == {"DOMAIN"}


def test_exactly_six_domains_and_no_intimacy(tmp_path):
    store, created = approved(tmp_path)

    result = compile_release(store, created)

    assert tuple(d.domain_id for d in result.domains) == SIX
    assert len(result.domains) == 6
    assert "domains/intimacy.json" not in result.files
    assert not any("intimacy" in path for path in result.files)
    assert set(result.domain_hashes_at_accept) == set(SIX)


# -- 4-5: domain hashes ------------------------------------------------------


def test_domain_files_and_hashes_match_independent_recomputation(tmp_path):
    store, created = approved(tmp_path)

    result = compile_release(store, created)

    expected, slice_b = expected_domain_hashes(
        store, "atlas", "version-v1", "revision-r1", created.snapshot_hash
    )
    assert dict(result.domain_hashes_at_accept) == expected
    assert list(result.domain_hashes_at_accept) == sorted(SIX)
    for envelope in slice_b.domains:
        raw = result.files[f"domains/{envelope.domain_id}.json"].content
        assert raw == canon(envelope.to_dict())
        assert sha(raw) == expected[envelope.domain_id]
    assert load(result, "provenance/acceptance.json")["domainHashesAtAccept"] == expected


def test_explicitly_empty_domains_are_hashed_like_any_other(tmp_path):
    store, created = approved(tmp_path, body=empty_semantic())

    result = compile_release(store, created)

    states = {d.domain_id: d.content_state.value for d in result.domains}
    assert set(states.values()) == {"EXPLICITLY_EMPTY"}
    hashes = dict(result.domain_hashes_at_accept)
    assert set(hashes) == set(SIX)
    for domain_id in SIX:
        raw = result.files[f"domains/{domain_id}.json"].content
        assert hashes[domain_id] == sha(raw)
    assert len(set(hashes.values())) == 6  # distinct domainIds keep hashes distinct


# -- 6-7: aggregate identity --------------------------------------------------


def test_aggregate_candidate_id_matches_ratified_producer_formula(tmp_path):
    store, created = approved(tmp_path)

    result = compile_release(store, created)

    expected = expected_candidate_id(
        "atlas", "version-v1", "revision-r1", created.snapshot_hash
    )
    assert result.aggregate_candidate_id == expected
    assert re.fullmatch(r"[a-z][a-z0-9._-]{0,127}", expected)
    assert load(result, "provenance/acceptance.json")["aggregateCandidateId"] == expected


def test_aggregate_candidate_id_depends_only_on_the_authoring_source(tmp_path):
    store_a, created_a = approved(tmp_path / "a")
    store_b, created_b = approved(tmp_path / "b")

    first = compile_release(store_a, created_a, release_id="alpha", display_name="One")
    second = compile_release(store_b, created_b, release_id="beta", display_name="Two")

    assert first.aggregate_candidate_id == second.aggregate_candidate_id
    assert first.aggregate_hash == second.aggregate_hash


def test_aggregate_hash_matches_independent_recomputation(tmp_path):
    store, created = approved(tmp_path)

    result = compile_release(store, created)

    hashes, _ = expected_domain_hashes(
        store, "atlas", "version-v1", "revision-r1", created.snapshot_hash
    )
    candidate = expected_candidate_id(
        "atlas", "version-v1", "revision-r1", created.snapshot_hash
    )
    expected = sha(
        canon(
            {
                "aggregate_schema_version": "vcp_aggregate_candidate/1.0",
                "characterId": "atlas",
                "aggregateCandidateId": candidate,
                "domainHashesAtAccept": hashes,
            }
        )
    )
    assert result.aggregate_hash == expected
    assert re.fullmatch(r"[0-9a-f]{64}", expected)
    assert expected != created.snapshot_hash  # never the authoring namespace


# -- 8-10: acceptance record --------------------------------------------------


def test_acceptance_record_has_exactly_the_seven_v1_fields(tmp_path):
    store, created = approved(tmp_path)

    result = compile_release(store, created)

    record = load(result, "provenance/acceptance.json")
    assert set(record) == {
        "characterId",
        "aggregateCandidateId",
        "aggregateHash",
        "domainHashesAtAccept",
        "decision",
        "decidedBy",
        "decidedAt",
    }
    assert record["characterId"] == "atlas"
    assert record["decision"] == "HUMAN_APPROVED"
    assert record["aggregateHash"] == result.aggregate_hash


def test_acceptance_uses_exact_lab_l1_decided_by_and_decided_at(tmp_path):
    store, created = approved(tmp_path)
    evidence = store.load_approval_evidence("atlas", "version-v1", "revision-r1")

    result = compile_release(store, created)

    record = load(result, "provenance/acceptance.json")
    assert record["decidedBy"] == DECIDED_BY == evidence.decided_by
    assert record["decidedAt"] == DECIDED_AT == evidence.decided_at
    assert result.approval == evidence


def test_acceptance_bytes_are_canonical_and_hash_is_recomputed(tmp_path):
    store, created = approved(tmp_path)

    result = compile_release(store, created)

    raw = result.files["provenance/acceptance.json"].content
    assert raw == canon(json.loads(raw.decode("utf-8")))
    assert result.acceptance_record_hash == sha(raw)
    assert load(result, "package.json")["acceptanceRecordHash"] == sha(raw)


# -- 11-15: package metadata and explicit inputs ------------------------------


def test_package_metadata_is_accepted_release_bound_to_the_aggregate(tmp_path):
    store, created = approved(tmp_path)

    result = compile_release(store, created, release_id="release-one", display_name="Атлас")

    package = load(result, "package.json")
    assert package == {
        "packageSchemaVersion": "1.0",
        "characterId": "atlas",
        "releaseId": "release-one",
        "displayName": "Атлас",
        "authorityClass": "ACCEPTED_RELEASE",
        "packageOrigin": "ACCEPTED_AGGREGATE",
        "acceptedAggregateHash": result.aggregate_hash,
        "acceptanceRecordHash": result.acceptance_record_hash,
    }
    assert package["acceptedAggregateHash"] == load(
        result, "provenance/acceptance.json"
    )["aggregateHash"]
    assert result.files["package.json"].content == canon(package)


@pytest.mark.parametrize("release_id", ["v1", "release-2026.03", "A_b-c.9", "legacy-compat-v1"])
def test_explicit_release_id_is_preserved(tmp_path, release_id):
    store, created = approved(tmp_path)

    result = compile_release(store, created, release_id=release_id)

    assert load(result, "package.json")["releaseId"] == release_id
    assert result.metadata.release_id == release_id


@pytest.mark.parametrize(
    "release_id",
    [None, 1, b"v1", "", "   ", "v 1", "v1\n", " v1", "a/b", "a\\b", "../x", ".hidden",
     "-lead", "verсия", "Vé", "con", "CON", "nul", "v1:stream"],
)
def test_invalid_release_id_fails_closed(tmp_path, release_id):
    store, created = approved(tmp_path)

    with pytest.raises(AuthoringVcpReleaseCompilationError):
        compile_release(store, created, release_id=release_id)


def test_release_id_is_independent_of_authoring_identity_and_hashes(tmp_path):
    store, created = approved(tmp_path)
    first = compile_release(store, created, release_id="rel-alpha")
    second = compile_release(store, created, release_id="rel-beta")

    for authoring_value in (
        "atlas", "version-v1", "revision-r1", created.snapshot_hash,
        first.aggregate_candidate_id, first.aggregate_hash,
    ):
        assert first.metadata.release_id != authoring_value
    # Only package.json depends on release_id.
    assert first.files["package.json"].content != second.files["package.json"].content
    for path in EXPECTED_PATHS:
        if path != "package.json":
            assert first.files[path] == second.files[path]
    assert first.aggregate_hash == second.aggregate_hash
    assert first.acceptance_record_hash == second.acceptance_record_hash


@pytest.mark.parametrize(
    "display_name", ["Атлас", "  Atlas  Prime ", "A", "Ünïcode ✓"]
)
def test_explicit_display_name_is_preserved_exactly(tmp_path, display_name):
    store, created = approved(tmp_path)

    result = compile_release(store, created, display_name=display_name)

    assert load(result, "package.json")["displayName"] == display_name
    assert result.metadata.display_name == display_name


@pytest.mark.parametrize("display_name", [None, 5, b"x", "", "   ", "\t\n", "Vé"])
def test_invalid_display_name_fails_closed(tmp_path, display_name):
    store, created = approved(tmp_path)

    with pytest.raises(AuthoringVcpReleaseCompilationError):
        compile_release(store, created, display_name=display_name)


def test_display_name_is_not_inferred_from_authoring_semantic(tmp_path):
    store, created = approved(tmp_path, body=semantic(name="SEMANTIC_DISPLAY_NAME"))

    result = compile_release(store, created, display_name="Explicit Name")

    assert load(result, "package.json")["displayName"] == "Explicit Name"
    assert b"SEMANTIC_DISPLAY_NAME" not in result.files["package.json"].content


# -- 16-20: things L2 must not produce ---------------------------------------


def test_no_manifest_no_vchar_no_package_hash(tmp_path):
    store, created = approved(tmp_path)

    result = compile_release(store, created)

    assert "manifest.json" not in result.files
    assert not any(path.lower().endswith(".vchar") for path in result.files)
    assert not hasattr(result, "package_hash")
    assert not hasattr(result, "manifest")
    everything = b"".join(f.content for f in result.files.values()).lower()
    assert b"packagehash" not in everything
    assert b"package_hash" not in everything
    assert not list(tmp_path.rglob("*.vchar"))


def test_no_optional_asset_or_prompt_indexes_under_zero_artifact_profile(tmp_path):
    store, created = approved(tmp_path)

    result = compile_release(store, created)

    assert not any(path.startswith(("assets/", "prompts/")) for path in result.files)
    assert "assets/asset_index.json" not in result.files
    assert "prompts/prompt_index.json" not in result.files


def test_cross_cutting_files_are_canonical_empty_collections(tmp_path):
    store, created = approved(tmp_path)

    result = compile_release(store, created)

    assert result.files["provenance/provenance.json"].content == b'{"provenance": []}'
    assert result.files["provenance/contradictions.json"].content == b'{"contradictions": []}'
    assert result.files["unknowns/unknowns.json"].content == b'{"unknowns": []}'


def test_no_provenance_record_or_authorship_claim_is_fabricated(tmp_path):
    store, created = approved(tmp_path)

    result = compile_release(store, created)

    every_file = b"".join(f.content for f in result.files.values()).decode("utf-8")
    for method in (
        "OWNER_AUTHORED", "GUIDED_CREATION", "VISUAL_AUTHORING", "MIXED", "CRP",
        "LEGACY_IMPORT", "authoringMethod", "provenanceId",
    ):
        assert method not in every_file
    for domain in result.domains:
        assert domain.provenance_refs == ()
        assert domain.legacy_payload == ()


# -- 21-24: approval binding --------------------------------------------------


def second_revision_and_evidence(store, created):
    other = store.persist_revision(
        "atlas", "version-v1", "revision-r2", semantic(name="OTHER_REVISION")
    )
    evidence = store.persist_approval_evidence(
        ApprovalEvidence(
            character_id="atlas",
            version_id="version-v1",
            revision_id="revision-r2",
            snapshot_hash=other.snapshot_hash,
            decided_by="Other Approver",
            decided_at="2027-01-02T03:04:05Z",
        )
    )
    return other, evidence


def slice_b(store, created):
    return compile_authoring_revision_to_vcp_domains(
        store,
        character_id="atlas",
        version_id="version-v1",
        revision_id="revision-r1",
        snapshot_hash=created.snapshot_hash,
    )


def test_evidence_for_a_different_revision_fails(tmp_path):
    store, created = approved(tmp_path)
    _other, foreign = second_revision_and_evidence(store, created)

    with pytest.raises(AuthoringVcpApprovalEvidenceError):
        build_authoring_release_compilation(
            slice_b(store, created), foreign, release_id="r1", display_name="A"
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("character_id", "other-character"),
        ("version_id", "other-version"),
        ("revision_id", "other-revision"),
        ("snapshot_hash", "e" * 64),
    ],
)
def test_any_coordinate_or_snapshot_mismatch_fails_closed(tmp_path, field, value):
    store, created = approved(tmp_path)
    evidence = store.load_approval_evidence("atlas", "version-v1", "revision-r1")

    with pytest.raises(AuthoringVcpApprovalEvidenceError):
        build_authoring_release_compilation(
            slice_b(store, created),
            replace(evidence, **{field: value}),
            release_id="r1",
            display_name="A",
        )


def test_decision_other_than_human_approved_fails(tmp_path):
    store, created = approved(tmp_path)
    evidence = store.load_approval_evidence("atlas", "version-v1", "revision-r1")
    tampered = replace(evidence)
    object.__setattr__(tampered, "decision", "APPROVED")

    with pytest.raises(AuthoringVcpApprovalEvidenceError):
        build_authoring_release_compilation(
            slice_b(store, created), tampered, release_id="r1", display_name="A"
        )


@pytest.mark.parametrize(
    "field,value", [("decided_by", "   "), ("decided_at", "2026-03-04T05:06:07+00:00")]
)
def test_invalid_approval_metadata_fails_closed(tmp_path, field, value):
    store, created = approved(tmp_path)
    evidence = store.load_approval_evidence("atlas", "version-v1", "revision-r1")
    tampered = replace(evidence)
    object.__setattr__(tampered, field, value)

    with pytest.raises(AuthoringVcpApprovalEvidenceError):
        build_authoring_release_compilation(
            slice_b(store, created), tampered, release_id="r1", display_name="A"
        )


@pytest.mark.parametrize("bogus", [None, {}, "HUMAN_APPROVED", object()])
def test_non_evidence_object_is_rejected(tmp_path, bogus):
    store, created = approved(tmp_path)

    with pytest.raises(AuthoringVcpApprovalEvidenceError):
        build_authoring_release_compilation(
            slice_b(store, created), bogus, release_id="r1", display_name="A"
        )


def test_snapshot_pin_mismatch_is_rejected_by_slice_b(tmp_path):
    store, created = approved(tmp_path)

    with pytest.raises(AuthoringVcpSourcePinMismatchError):
        compile_authoring_release(
            store,
            character_id="atlas",
            version_id="version-v1",
            revision_id="revision-r1",
            snapshot_hash="f" * 64,
            release_id="r1",
            display_name="A",
        )


def test_missing_approval_evidence_fails_at_the_service_boundary(tmp_path):
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
    store = CharacterAuthoringStore(root)

    with pytest.raises(AuthoringVcpApprovalEvidenceError):
        compile_release(store, created)


def test_historical_approved_state_without_evidence_cannot_compile(tmp_path):
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
    store = CharacterAuthoringStore(root)
    pointer = store.read_version_pointer("atlas", "version-v1")
    store.update_version_pointer(
        replace(pointer, lifecycle_state=LifecycleState.APPROVED_AS_CANON)
    )

    with pytest.raises(AuthoringVcpApprovalEvidenceError):
        compile_release(store, created)
    assert not (root / "atlas" / "versions" / "version-v1" / "approvals").exists()


def test_corrupt_approval_evidence_fails_closed(tmp_path):
    store, created = approved(tmp_path)
    path = (
        store.root / "atlas" / "versions" / "version-v1" / "approvals"
        / "revision-r1.json"
    )
    path.write_text("{not json", encoding="utf-8")

    with pytest.raises(AuthoringVcpApprovalEvidenceError):
        compile_release(store, created)


def test_compiler_reads_only_exact_revision_and_evidence_not_pointers(tmp_path):
    store, created = approved(tmp_path)

    class ExactOnlyStore:
        def __init__(self, delegate):
            self._delegate = delegate
            self.calls = []

        def load_revision(self, *coordinate):
            self.calls.append(("load_revision", coordinate))
            return self._delegate.load_revision(*coordinate)

        def load_approval_evidence(self, *coordinate):
            self.calls.append(("load_approval_evidence", coordinate))
            return self._delegate.load_approval_evidence(*coordinate)

        def __getattr__(self, name):
            raise AssertionError(f"compiler must not access store.{name}")

    exact = ExactOnlyStore(store)

    result = compile_release(exact, created)

    assert {name for name, _ in exact.calls} == {"load_revision", "load_approval_evidence"}
    assert all(coordinate[:3] == ("atlas", "version-v1", "revision-r1")
               for _, coordinate in exact.calls)
    assert result.approval.decided_by == DECIDED_BY


def test_slice_b_visual_mapping_failures_propagate_unchanged(tmp_path):
    body = semantic()
    body["visual_identity"] = {"reference_asset_id": "raw-local-portrait"}
    store, created = approved(tmp_path, body=body)

    with pytest.raises(AuthoringVcpVisualMappingError):
        compile_release(store, created)


def test_wrong_domain_set_from_domain_compilation_fails_closed(tmp_path):
    store, created = approved(tmp_path)
    good = slice_b(store, created)
    evidence = store.load_approval_evidence("atlas", "version-v1", "revision-r1")

    five = AuthoringVcpDomainCompilation(source=good.source, domains=good.domains[:5])
    duplicated = AuthoringVcpDomainCompilation(
        source=good.source, domains=good.domains[:5] + (good.domains[0],)
    )
    for broken in (five, duplicated):
        with pytest.raises(AuthoringVcpReleaseCompilationError):
            build_authoring_release_compilation(
                broken, evidence, release_id="r1", display_name="A"
            )
    with pytest.raises(AuthoringVcpReleaseCompilationError):
        build_authoring_release_compilation(
            "not a compilation", evidence, release_id="r1", display_name="A"
        )


# -- 25 + purity + determinism -------------------------------------------------


def test_repeated_compilation_is_byte_identical(tmp_path):
    store, created = approved(tmp_path)

    first = compile_release(store, created)
    second = compile_release(store, created)

    assert first == second
    assert list(first.files) == list(second.files)
    for path in first.files:
        assert first.files[path].content == second.files[path].content
    assert dict(first.domain_hashes_at_accept) == dict(second.domain_hashes_at_accept)
    assert first.aggregate_candidate_id == second.aggregate_candidate_id
    assert first.aggregate_hash == second.aggregate_hash
    assert first.acceptance_record_hash == second.acceptance_record_hash


def test_independent_stores_with_same_content_compile_identically(tmp_path):
    store_a, created_a = approved(tmp_path / "a")
    store_b, created_b = approved(tmp_path / "b")

    first = compile_release(store_a, created_a)
    second = compile_release(store_b, created_b)

    assert {p: f.content for p, f in first.files.items()} == {
        p: f.content for p, f in second.files.items()
    }


def test_compilation_performs_no_persistent_write(tmp_path):
    store, created = approved(tmp_path)
    before = files_under(tmp_path)

    compile_release(store, created)
    compile_release(store, created, release_id="another")

    assert files_under(tmp_path) == before


def test_compiler_module_uses_no_clock_randomness_or_filesystem_api():
    source = (
        REPO_ROOT / "services" / "character_publication" / "vcp_release.py"
    ).read_text(encoding="utf-8")
    imported = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            imported.add(node.module.split(".")[0])
    assert imported.isdisjoint(
        {"time", "datetime", "random", "secrets", "uuid", "os", "pathlib",
         "tempfile", "shutil", "socket", "subprocess"}
    )
    assert "open(" not in source and "write_bytes" not in source


def test_result_is_immutable(tmp_path):
    store, created = approved(tmp_path)
    result = compile_release(store, created)

    with pytest.raises(TypeError):
        result.files["extra.json"] = None  # type: ignore[index]
    with pytest.raises(TypeError):
        result.domain_hashes_at_accept["core_identity"] = "x"  # type: ignore[index]
    with pytest.raises(Exception):
        result.aggregate_hash = "x"  # type: ignore[misc]


def test_release_compiler_is_not_reexported_or_loaded_at_lab_startup():
    import services.character_publication as publication

    for name in ("compile_authoring_release", "build_authoring_release_compilation"):
        assert not hasattr(publication, name)
    probe = (
        "import sys\n"
        "import services.character_publication\n"
        "import services.character_lab_application\n"
        "assert 'voyage_character_platform' not in sys.modules\n"
        "assert 'services.character_publication.vcp_release' not in sys.modules\n"
        "assert 'services.character_publication.vcp_domains' not in sys.modules\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", probe], cwd=REPO_ROOT,
        capture_output=True, text=True, check=False,
    )
    assert completed.returncode == 0, completed.stderr


# -- optional strong oracle: authoritative VCP materialize + verify (temp only) --


def test_result_materializes_and_verifies_under_authoritative_vcp(tmp_path):
    store, created = approved(tmp_path)
    result = compile_release(store, created, release_id="release-one", display_name="Атлас")
    destination = tmp_path / "oracle" / "package"

    materialized = materialize_package_v1(destination, files=dict(result.files))
    verified = verify_package_v1(destination, expected_package_hash=materialized.package_hash)

    assert re.fullmatch(r"[0-9a-f]{64}", verified.package_hash)
    assert verified.metadata.release_id == "release-one"
    assert verified.metadata.display_name == "Атлас"
    assert verified.metadata.authority_class.value == "ACCEPTED_RELEASE"
    assert verified.metadata.accepted_aggregate_hash == result.aggregate_hash
    assert verified.metadata.acceptance_record_hash == result.acceptance_record_hash
    assert sorted(entry.path for entry in verified.manifest.files) == EXPECTED_PATHS
    assert sorted(files_under(destination)) == sorted(EXPECTED_PATHS + ["manifest.json"])
    # Materialization is a test oracle only: the compiler result stays hash-free.
    assert sha(files_under(destination)["manifest.json"]) == verified.package_hash


def test_oracle_package_hash_is_deterministic_and_release_id_sensitive(tmp_path):
    store, created = approved(tmp_path)
    one = compile_release(store, created, release_id="release-one")
    again = compile_release(store, created, release_id="release-one")
    other = compile_release(store, created, release_id="release-two")

    hashes = [
        materialize_package_v1(tmp_path / name, files=dict(result.files)).package_hash
        for name, result in (("a", one), ("b", again), ("c", other))
    ]

    assert hashes[0] == hashes[1]
    assert hashes[0] != hashes[2]


def test_oracle_rejects_a_release_whose_domain_no_longer_matches_acceptance(tmp_path):
    store, created = approved(tmp_path)
    result = compile_release(store, created)
    files = dict(result.files)
    original = json.loads(files["domains/speech.json"].content.decode("utf-8"))
    original["content"]["structured"]["speech_style"] = "TAMPERED"
    files["domains/speech.json"] = replace(
        files["domains/speech.json"], content=canon(original)
    )

    with pytest.raises(PackageV1Error):
        materialize_package_v1(tmp_path / "tampered", files=files)
    assert not (tmp_path / "tampered").exists()


# -- sexology -> optional intimacy (OD-VCP-OPTIONAL-ACCEPTED-DOMAINS-01) ----


def sexology_semantic() -> dict:
    body = semantic()
    body["sexology"] = {
        "intimacy_attitudes": ["tender"],
        "preferences": ["slow"],
        "emotional_dynamics": ["trust"],
        "communication": ["verbal"],
        "vulnerabilities": ["rejection"],
        "intimacy_boundaries": ["no coercion"],
    }
    return body


def test_populated_sexology_compiles_six_plus_intimacy(tmp_path):
    store, created = approved(tmp_path, body=sexology_semantic())

    result = compile_release(store, created)

    assert tuple(d.domain_id for d in result.domains) == SIX + ("intimacy",)
    assert "domains/intimacy.json" in result.files
    assert set(result.domain_hashes_at_accept) == set(SIX) | {"intimacy"}


def test_empty_sexology_compiles_six_domains_only(tmp_path):
    body = semantic()
    body["sexology"] = {
        "intimacy_attitudes": [],
        "preferences": [],
        "emotional_dynamics": [],
        "communication": [],
        "vulnerabilities": [],
        "intimacy_boundaries": [],
    }
    store, created = approved(tmp_path, body=body)

    result = compile_release(store, created)

    assert tuple(d.domain_id for d in result.domains) == SIX
    assert "domains/intimacy.json" not in result.files


def test_intimacy_hash_equals_canonical_envelope_bytes(tmp_path):
    store, created = approved(tmp_path, body=sexology_semantic())

    result = compile_release(store, created)

    intimacy_bytes = result.files["domains/intimacy.json"].content
    assert result.domain_hashes_at_accept["intimacy"] == sha(intimacy_bytes)


def test_aggregate_hash_changes_when_intimacy_included(tmp_path):
    store, created = approved(tmp_path, body=sexology_semantic())

    result = compile_release(store, created)

    six_only = {
        k: v for k, v in result.domain_hashes_at_accept.items() if k != "intimacy"
    }
    with_intimacy = dict(result.domain_hashes_at_accept)
    assert compute_aggregate_hash(
        "atlas", result.aggregate_candidate_id, six_only
    ) != compute_aggregate_hash("atlas", result.aggregate_candidate_id, with_intimacy)
    assert compute_aggregate_hash(
        "atlas", result.aggregate_candidate_id, with_intimacy
    ) == result.aggregate_hash


def test_seven_domain_release_materializes_and_verifies_vcp(tmp_path):
    store, created = approved(tmp_path, body=sexology_semantic())

    result = compile_release(store, created)

    materialized = materialize_package_v1(tmp_path / "pkg", files=dict(result.files))
    verified = verify_package_v1(
        materialized.root, expected_package_hash=materialized.package_hash
    )
    assert verified.metadata.character_id == "atlas"
    assert verified.metadata.authority_class.value == "ACCEPTED_RELEASE"
    assert (materialized.root / "domains" / "intimacy.json").exists()


def test_unknown_seventh_domain_is_rejected(tmp_path):
    store, created = approved(tmp_path)

    domain_compilation = compile_authoring_revision_to_vcp_domains(
        store,
        character_id="atlas",
        version_id="version-v1",
        revision_id="revision-r1",
        snapshot_hash=created.snapshot_hash,
    )
    extra = DomainEnvelope(
        domain_id="voice_identity",
        domain_schema_version="1.0",
        content_state=ContentState.EXPLICITLY_EMPTY,
        provenance_refs=(),
        structured={},
    )
    forged = AuthoringVcpDomainCompilation(
        source=domain_compilation.source,
        domains=tuple(domain_compilation.domains) + (extra,),
    )
    evidence = store.load_approval_evidence("atlas", "version-v1", "revision-r1")

    with pytest.raises(AuthoringVcpReleaseCompilationError):
        build_authoring_release_compilation(
            forged, evidence, release_id="release-one", display_name="Атлас"
        )
