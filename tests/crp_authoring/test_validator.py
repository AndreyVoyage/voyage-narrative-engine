#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CRP MVP S1 -- R7 deterministic consistency-validator tests."""

from __future__ import annotations

import pytest

from services.crp_authoring import (
    ClaimType,
    Confidence,
    SourceType,
)
from services.crp_authoring.compiler import compile_candidate_package
from services.crp_authoring.validator import (
    CHECK_CONFIDENCE,
    CHECK_CONTRADICTION_PRESERVED,
    CHECK_DUP_CLAIM_ID,
    CHECK_DUP_SEMANTIC,
    CHECK_INVALID_TARGET,
    CHECK_MISSING_CONTRADICTION,
    CHECK_MISSING_EVIDENCE,
    CHECK_PROVENANCE,
    CHECK_SUBJECT,
    CHECK_UNKNOWN_INTEGRITY,
    CHECK_UNKNOWN_MUTUAL_EXCLUSION,
    DEFERRED_CHECKS,
    SEVERITY_ERROR,
    validate_package,
)

from tests.crp_authoring.conftest import (
    make_claim,
    make_compile_context,
    make_contradiction,
    make_package,
    make_source,
)


def _claims_findings(report, check):
    return [f for f in report.findings if f.check == check]


class TestValidator:
    def test_valid_package_no_findings(self) -> None:
        ctx = make_compile_context()
        claim = make_claim(claim_id="c1", target_module_or_layer="psychology.P2")
        pkg = compile_candidate_package(ctx, (claim,), ())
        report = validate_package(pkg)
        assert report.valid is True
        assert report.findings == ()

    def test_two_deferred_checks_recorded(self) -> None:
        assert DEFERRED_CHECKS == ("SCHEMA_FULL_VALIDATION", "ROLE_PERMISSION_VIOLATION")

    def test_duplicate_claim_id_detected(self) -> None:
        ctx = make_compile_context()
        a = make_claim(claim_id="dup", target_module_or_layer="psychology.P1")
        b = make_claim(claim_id="dup", target_module_or_layer="psychology.P2")
        pkg = compile_candidate_package(ctx, (a, b), ())
        report = validate_package(pkg)
        assert _claims_findings(report, CHECK_DUP_CLAIM_ID)
        assert report.valid is False

    def test_exact_duplicate_semantic_detected(self) -> None:
        ctx = make_compile_context()
        a = make_claim(claim_id="c1", target_module_or_layer="psychology.P1",
                       claim="same text", role_id="R2")
        b = make_claim(claim_id="c2", target_module_or_layer="psychology.P1",
                       claim="same text", role_id="R2")
        pkg = compile_candidate_package(ctx, (a, b), ())
        report = validate_package(pkg)
        assert _claims_findings(report, CHECK_DUP_SEMANTIC)

    def test_missing_evidence_ref_detected(self) -> None:
        ctx = make_compile_context()
        claim = make_claim(claim_id="c1", target_module_or_layer="psychology.P2",
                           source_evidence_ids=("se-missing",))
        pkg = compile_candidate_package(ctx, (claim,), ())
        report = validate_package(pkg, evidence=(make_source(source_id="se-present"),))
        assert _claims_findings(report, CHECK_MISSING_EVIDENCE)

    def test_missing_contradiction_ref_detected(self) -> None:
        ctx = make_compile_context()
        claim = make_claim(claim_id="c1", target_module_or_layer="psychology.P2",
                           contradiction_ids=("crd-missing",))
        pkg = compile_candidate_package(ctx, (claim,), ())
        report = validate_package(pkg)
        assert _claims_findings(report, CHECK_MISSING_CONTRADICTION)

    def test_subject_mismatch_detected(self) -> None:
        ctx = make_compile_context(subject_id="package-subject")
        claim = make_claim(claim_id="c1", target_module_or_layer="psychology.P2")
        # claim.subject_id defaults to "char-subject-1" in the fixture
        pkg = compile_candidate_package(ctx, (claim,), ())
        report = validate_package(pkg)
        assert _claims_findings(report, CHECK_SUBJECT)

    def test_provenance_break_detected(self) -> None:
        # Craft a package whose provenance_manifest references a claim id not
        # present in package.claims.
        claim = make_claim(claim_id="real-claim", target_module_or_layer="psychology.P2")
        pkg = make_package(
            claims=(claim,),
            psychology_candidate={"P2": (claim,)},
            provenance_manifest={"psychology.P2": ("real-claim", "ghost-claim")},
        )
        report = validate_package(pkg)
        assert _claims_findings(report, CHECK_PROVENANCE)

    def test_confidence_misuse_detected(self) -> None:
        ctx = make_compile_context()
        claim = make_claim(
            claim_id="c1", target_module_or_layer="psychology.P2",
            claim_type=ClaimType.INFERENCE,
            source_type_summary=(SourceType.MODEL_INFERENCE,),
            confidence=Confidence.KNOWN,
        )
        pkg = compile_candidate_package(ctx, (claim,), ())
        report = validate_package(pkg)
        assert _claims_findings(report, CHECK_CONFIDENCE)

    def test_contradiction_dropped_detected(self) -> None:
        ctx = make_compile_context()
        c1 = make_claim(claim_id="c1", target_module_or_layer="psychology.P3")
        c2 = make_claim(claim_id="c2", target_module_or_layer="psychology.P3")
        record = make_contradiction(contradiction_id="crd-1", claim_ids=("c1", "c2"))
        pkg = compile_candidate_package(ctx, (c1, c2), (record,))
        # Drop the record from the package to simulate silent deletion.
        stripped = make_package(
            claims=(c1, c2),
            contradictions=(),
            psychology_candidate={"P3": (c1, c2)},
            provenance_manifest={"psychology.P3": ("c1", "c2")},
        )
        report = validate_package(stripped, input_contradictions=(record,))
        assert _claims_findings(report, CHECK_CONTRADICTION_PRESERVED)

    def test_deterministic_findings_stable(self) -> None:
        ctx = make_compile_context()
        a = make_claim(claim_id="dup", target_module_or_layer="psychology.P1")
        b = make_claim(claim_id="dup", target_module_or_layer="psychology.P2")
        pkg = compile_candidate_package(ctx, (a, b), ())
        r1 = validate_package(pkg)
        r2 = validate_package(pkg)
        assert r1.findings == r2.findings
        assert [f.message for f in r1.findings] == [f.message for f in r2.findings]


class TestIntimacyValidation:
    def test_intimacy_claim_validates_cleanly(self) -> None:
        # A valid intimacy.* claim compiles and passes validation without
        # INVALID_TARGET or PROVENANCE_BREAK findings.
        ctx = make_compile_context()
        c = make_claim(claim_id="c1", target_module_or_layer="intimacy.boundaries")
        pkg = compile_candidate_package(ctx, (c,), ())
        report = validate_package(pkg)
        assert report.valid is True
        assert report.findings == ()

    def test_intimacy_provenance_break_detected(self) -> None:
        # R7 still catches a provenance break in intimacy_candidate (symmetric
        # with psychology/voice).
        claim = make_claim(claim_id="real-claim", target_module_or_layer="intimacy.boundaries")
        pkg = make_package(
            claims=(claim,),
            intimacy_candidate={"boundaries": (claim,)},
            provenance_manifest={"intimacy.boundaries": ("real-claim", "ghost-claim")},
        )
        report = validate_package(pkg)
        assert _claims_findings(report, CHECK_PROVENANCE)

    def test_invalid_target_still_fail_closed(self) -> None:
        # A claim with an unmappable target still fails closed.
        ctx = make_compile_context()
        c = make_claim(claim_id="c1", target_module_or_layer="no_prefix_here")
        # classify_target raises before package construction
        from services.crp_authoring import CompilerError
        with pytest.raises(CompilerError):
            compile_candidate_package(ctx, (c,), ())


class TestUnknownValidation:
    """Slice 3: R7 structural checks over package.unknowns."""

    def _unknown(self, claim_id, target="psychology.P2"):
        return make_claim(
            claim_id=claim_id, claim_type=ClaimType.UNKNOWN,
            target_module_or_layer=target,
            source_evidence_ids=(),
            confidence=Confidence.UNKNOWN,
        )

    def test_valid_unknown_package_passes(self) -> None:
        ctx = make_compile_context()
        u = self._unknown("u1", "behavior.conflict_style")
        pkg = compile_candidate_package(ctx, (u,), ())
        report = validate_package(pkg)
        assert report.valid is True
        assert report.findings == ()

    def test_non_roleclaim_unknown_entry_detected(self) -> None:
        pkg = make_package(unknowns=("not-a-claim",))
        report = validate_package(pkg)
        assert _claims_findings(report, CHECK_UNKNOWN_INTEGRITY)

    def test_non_unknown_claim_in_unknowns_detected(self) -> None:
        plain = make_claim(claim_id="c1", target_module_or_layer="psychology.P2")
        pkg = make_package(unknowns=(plain,))
        report = validate_package(pkg)
        assert _claims_findings(report, CHECK_UNKNOWN_INTEGRITY)

    def test_mutual_exclusion_detected(self) -> None:
        # Same claim present both in package.unknowns and a family bucket.
        u = self._unknown("u1", "psychology.P2")
        pkg = make_package(unknowns=(u,), psychology_candidate={"P2": (u,)})
        report = validate_package(pkg)
        assert _claims_findings(report, CHECK_UNKNOWN_MUTUAL_EXCLUSION)

    def test_unknown_subject_mismatch_detected(self) -> None:
        # Unknown claim subject differs from package subject -> existing
        # CHECK_SUBJECT still catches it (subject integrity per §12.D).
        ctx = make_compile_context(subject_id="package-subject")
        u = self._unknown("u1", "psychology.P2")  # subject defaults to char-subject-1
        pkg = compile_candidate_package(ctx, (u,), ())
        report = validate_package(pkg)
        assert _claims_findings(report, CHECK_SUBJECT)


class TestTargetFamilyCompatibility:
    """Slice 8 pre-orchestrator: R7 CHECK_INVALID_TARGET accepts the full
    authoritative claim-family set (R6 classify_target + permissions)."""

    # ---- T1: legacy families still accepted (no INVALID_TARGET) -----------
    @pytest.mark.parametrize("target", [
        "psychology.P0", "psychology.P2", "psychology.P5",
        "voice.prosody", "intimacy.boundaries",
    ])
    def test_legacy_families_pass(self, target: str) -> None:
        ctx = make_compile_context()
        claim = make_claim(claim_id="c1", target_module_or_layer=target)
        pkg = compile_candidate_package(ctx, (claim,), ())
        report = validate_package(pkg)
        assert _claims_findings(report, CHECK_INVALID_TARGET) == []

    # ---- T2: newly recognized broad-core families pass --------------------
    @pytest.mark.parametrize("target", [
        "identity_biography.birthplace",
        "behavior.conflict_style",
        "relationships.friend_circle",
        "boundaries.touch",
        "seed_memory.first_meeting",
    ])
    def test_broad_core_families_pass(self, target: str) -> None:
        ctx = make_compile_context()
        claim = make_claim(claim_id="c1", target_module_or_layer=target)
        pkg = compile_candidate_package(ctx, (claim,), ())
        report = validate_package(pkg)
        assert _claims_findings(report, CHECK_INVALID_TARGET) == []

    # ---- T3: truly invalid arbitrary family still fails -------------------
    def test_arbitrary_namespace_fails(self) -> None:
        claim = make_claim(claim_id="c1", target_module_or_layer="totally_invalid.foo")
        pkg = make_package(claims=(claim,))
        report = validate_package(pkg)
        assert _claims_findings(report, CHECK_INVALID_TARGET)

    # ---- T4: near-miss prefixes do NOT become valid ----------------------
    @pytest.mark.parametrize("target", [
        "identity_biographyX.foo",
        "behaviorX.foo",
        "relationships_extra.foo",
        "boundaries_extra.foo",
        "seed_memoryX.foo",
    ])
    def test_near_miss_prefixes_fail(self, target: str) -> None:
        claim = make_claim(claim_id="c1", target_module_or_layer=target)
        pkg = make_package(claims=(claim,))
        report = validate_package(pkg)
        assert _claims_findings(report, CHECK_INVALID_TARGET)

    # ---- T5: UNKNOWN exemption unchanged --------------------------------
    def test_unknown_exemption_unchanged(self) -> None:
        # UNKNOWN claims are exempt from INVALID_TARGET even with a weird target.
        u = make_claim(
            claim_id="u1", claim_type=ClaimType.UNKNOWN,
            target_module_or_layer="totally_invalid.foo",
            source_evidence_ids=(),
            confidence=Confidence.UNKNOWN,
        )
        ctx = make_compile_context()
        pkg = compile_candidate_package(ctx, (u,), ())
        report = validate_package(pkg)
        assert _claims_findings(report, CHECK_INVALID_TARGET) == []
        assert report.valid is True

    # ---- T6: finding identity / severity unchanged ------------------------
    def test_invalid_target_finding_contract_unchanged(self) -> None:
        claim = make_claim(claim_id="c1", target_module_or_layer="totally_invalid.foo")
        pkg = make_package(claims=(claim,))
        report = validate_package(pkg)
        findings = _claims_findings(report, CHECK_INVALID_TARGET)
        assert len(findings) == 1
        assert findings[0].check == CHECK_INVALID_TARGET
        assert findings[0].severity == SEVERITY_ERROR
        assert "invalid target" in findings[0].message
