#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CRP MVP Slice 6 -- R8 deterministic audit tests (offline, no provider).

Covers the ReconstructionAudit contract and the deterministic R8 checks plus
the deterministic half of the one HYBRID check. No LLM judgment, no provider,
no RoleResult, no hidden evaluation, no accepted benchmark.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from services.crp_authoring.auditor_checks import (
    AuditPolicy,
    CHECK_CANON_WRITE,
    CHECK_CONFIDENCE,
    CHECK_LEAKAGE,
    CHECK_PROVENANCE,
    CHECK_ROLE_BOUNDARY,
    CHECK_UNSUPPORTED,
    run_deterministic_audit,
)
from services.crp_authoring.candidate_package import CandidateCharacterPackage
from services.crp_authoring.contracts import (
    ClaimType,
    Confidence,
    SourceType,
)
from services.crp_authoring.errors import CrpValidationError
from services.crp_authoring.reconstruction_audit import (
    AuditCheckClassification,
    AuditCheckOutcome,
    AuditCheckResult,
    AuditFinding,
    AuditVerdict,
    ReconstructionAudit,
    compose_verdict,
    resolve_final_verdict,
)

from tests.crp_authoring.conftest import (
    make_claim,
    make_compile_context,
    make_contradiction,
    make_package,
    make_source,
)


def _audit(checks, verdict=AuditVerdict.PASS):
    return ReconstructionAudit(
        audit_id="audit-1",
        package_id="pkg-001",
        package_hash="0" * 64,
        auditor_role_version="v1",
        evidence_snapshot_id="snapshot-1",
        checks=checks,
        verdict=verdict,
        defects=(),
        correction_requests=(),
        created_at=datetime.now(timezone.utc).replace(microsecond=0),
    )


def _check(check, outcome=AuditCheckOutcome.PASS, hard_blocker=False,
           classification=AuditCheckClassification.DETERMINISTIC):
    return AuditCheckResult(
        check=check,
        classification=classification,
        outcome=outcome,
        findings=(),
        hard_blocker=hard_blocker,
    )


class TestReconstructionAuditContract:
    def test_constructs(self) -> None:
        audit = _audit((_check("R8_PROVENANCE_COMPLETENESS"),))
        assert audit.verdict is AuditVerdict.PASS
        assert audit.audit_id == "audit-1"

    def test_requires_audit_id(self) -> None:
        with pytest.raises(CrpValidationError):
            ReconstructionAudit(
                audit_id="", package_id="pkg", package_hash="h",
                auditor_role_version="v1", evidence_snapshot_id="s",
                checks=(), verdict=AuditVerdict.PASS, defects=(),
                correction_requests=(),
                created_at=datetime.now(timezone.utc).replace(microsecond=0),
            )

    def test_requires_datetime_created_at(self) -> None:
        with pytest.raises(CrpValidationError):
            ReconstructionAudit(
                audit_id="a", package_id="pkg", package_hash="h",
                auditor_role_version="v1", evidence_snapshot_id="s",
                checks=(), verdict=AuditVerdict.PASS, defects=(),
                correction_requests=(), created_at="not-a-datetime",
            )

    def test_rejects_non_check_entries(self) -> None:
        with pytest.raises(CrpValidationError):
            ReconstructionAudit(
                audit_id="a", package_id="pkg", package_hash="h",
                auditor_role_version="v1", evidence_snapshot_id="s",
                checks=("not-a-check",), verdict=AuditVerdict.PASS,
                defects=(), correction_requests=(),
                created_at=datetime.now(timezone.utc).replace(microsecond=0),
            )

    def test_immutable(self) -> None:
        audit = _audit((_check("R8_PROVENANCE_COMPLETENESS"),))
        with pytest.raises(Exception):
            audit.verdict = AuditVerdict.FAIL  # frozen


class TestVerdictComposition:
    def test_hard_blocker_dominates(self) -> None:
        checks = (
            _check("x", outcome=AuditCheckOutcome.PASS),
            _check("R8_LEAKAGE", outcome=AuditCheckOutcome.BLOCKED, hard_blocker=True),
            _check("y", outcome=AuditCheckOutcome.FAIL),
        )
        assert compose_verdict(checks) is AuditVerdict.BLOCKED

    def test_fail_over_inconclusive_over_pass(self) -> None:
        assert compose_verdict((_check("a", AuditCheckOutcome.FAIL),)) is AuditVerdict.FAIL
        assert compose_verdict((_check("a", AuditCheckOutcome.INCONCLUSIVE),)) is AuditVerdict.INCONCLUSIVE
        assert compose_verdict((_check("a", AuditCheckOutcome.PASS),)) is AuditVerdict.PASS

    def test_llm_cannot_override_blocked(self) -> None:
        # Future LLM judgment cannot clear a deterministic hard BLOCKED.
        assert resolve_final_verdict(AuditVerdict.BLOCKED, AuditVerdict.PASS) is AuditVerdict.BLOCKED
        assert resolve_final_verdict(AuditVerdict.BLOCKED, AuditVerdict.FAIL) is AuditVerdict.BLOCKED

    def test_llm_cannot_upgrade_fail_to_pass(self) -> None:
        assert resolve_final_verdict(AuditVerdict.FAIL, AuditVerdict.PASS) is AuditVerdict.FAIL

    def test_llm_can_upgrade_pass_to_fail(self) -> None:
        assert resolve_final_verdict(AuditVerdict.PASS, AuditVerdict.FAIL) is AuditVerdict.FAIL

    def test_no_judgment_returns_deterministic(self) -> None:
        assert resolve_final_verdict(AuditVerdict.PASS, None) is AuditVerdict.PASS


class TestDeterministicAudit:
    def _clean_package(self, **overrides):
        claim = make_claim(claim_id="c1", claim_type=ClaimType.FACT,
                           source_type_summary=(SourceType.OWNER_DIRECT,),
                           target_module_or_layer="psychology.P0")
        pkg = make_package(claims=(claim,), **overrides)
        # make_package's provenance_manifest is empty by default; the compiler
        # normally populates it. For a clean audit, point the manifest at the
        # existing claim so there is no provenance break.
        pkg = _with_manifest(pkg, {"psychology.P0": ("c1",)})
        return pkg

    def _policy(self, **overrides):
        kwargs = dict(forbidden_refs=(), auditor_role_version="v1")
        kwargs.update(overrides)
        return AuditPolicy(**kwargs)

    def test_clean_package_passes(self) -> None:
        pkg = self._clean_package()
        audit = run_deterministic_audit(pkg, (), self._policy())
        assert audit.verdict is AuditVerdict.PASS

    def test_leakage_hard_blocker(self) -> None:
        pkg = self._clean_package()
        ev = make_source(source_id="se-leak", content_ref="personas/kira/profile.json")
        audit = run_deterministic_audit(
            pkg, (ev,), self._policy(forbidden_refs=("personas/kira/**",)),
        )
        assert audit.verdict is AuditVerdict.BLOCKED
        assert any(c.check == CHECK_LEAKAGE and c.outcome is AuditCheckOutcome.BLOCKED
                   for c in audit.checks)

    def test_leakage_near_miss_allowed(self) -> None:
        pkg = self._clean_package()
        ev = make_source(source_id="se-ok", content_ref="personas/kira2/profile.json")
        audit = run_deterministic_audit(
            pkg, (ev,), self._policy(forbidden_refs=("personas/kira/**",)),
        )
        assert audit.verdict is AuditVerdict.PASS

    def test_canon_write_hard_blocker(self) -> None:
        claim = make_claim(claim_id="c1", claim_type=ClaimType.FACT,
                           source_type_summary=(SourceType.OWNER_DIRECT,),
                           target_module_or_layer="psychology.P0",
                           claim="write this to personas/ path")
        pkg = make_package(claims=(claim,))
        pkg = _with_manifest(pkg, {"psychology.P0": ("c1",)})
        audit = run_deterministic_audit(pkg, (), self._policy())
        assert audit.verdict is AuditVerdict.BLOCKED
        assert any(c.check == CHECK_CANON_WRITE and c.outcome is AuditCheckOutcome.BLOCKED
                   for c in audit.checks)

    def test_unsupported_fact_without_direct_evidence_fails(self) -> None:
        claim = make_claim(claim_id="c1", claim_type=ClaimType.FACT,
                           source_type_summary=(SourceType.MODEL_INFERENCE,),
                           target_module_or_layer="psychology.P0")
        pkg = make_package(claims=(claim,))
        pkg = _with_manifest(pkg, {"psychology.P0": ("c1",)})
        audit = run_deterministic_audit(pkg, (), self._policy())
        assert audit.verdict is AuditVerdict.FAIL
        assert any(c.check == CHECK_UNSUPPORTED for c in audit.checks)

    def test_confidence_misuse_fails(self) -> None:
        claim = make_claim(claim_id="c1", claim_type=ClaimType.INFERENCE,
                           source_type_summary=(SourceType.MODEL_INFERENCE,),
                           confidence=Confidence.KNOWN,
                           target_module_or_layer="psychology.P0")
        pkg = make_package(claims=(claim,))
        pkg = _with_manifest(pkg, {"psychology.P0": ("c1",)})
        audit = run_deterministic_audit(pkg, (), self._policy())
        assert audit.verdict is AuditVerdict.FAIL
        assert any(c.check == CHECK_CONFIDENCE for c in audit.checks)

    def test_provenance_break_fails(self) -> None:
        pkg = self._clean_package()
        pkg = _with_manifest(pkg, {"psychology.P0": ("ghost-claim",)})
        audit = run_deterministic_audit(pkg, (), self._policy())
        assert audit.verdict is AuditVerdict.FAIL
        assert any(c.check == CHECK_PROVENANCE for c in audit.checks)

    def test_unknown_role_id_boundary(self) -> None:
        claim = make_claim(claim_id="c1", role_id="R99", claim_type=ClaimType.FACT,
                           source_type_summary=(SourceType.OWNER_DIRECT,),
                           target_module_or_layer="psychology.P0")
        pkg = make_package(claims=(claim,))
        pkg = _with_manifest(pkg, {"psychology.P0": ("c1",)})
        audit = run_deterministic_audit(pkg, (), self._policy())
        assert any(c.check == CHECK_ROLE_BOUNDARY for c in audit.checks)


class TestAuditNonMutation:
    def test_does_not_mutate_package_or_evidence(self) -> None:
        claim = make_claim(claim_id="c1", claim_type=ClaimType.FACT,
                           source_type_summary=(SourceType.OWNER_DIRECT,),
                           target_module_or_layer="psychology.P0")
        pkg = _with_manifest(
            make_package(claims=(claim,)), {"psychology.P0": ("c1",)},
        )
        ev = make_source(source_id="se-1", content_ref="ref://raw/001")
        claims_before = tuple(pkg.claims)
        evidence_before = ev.content_ref
        run_deterministic_audit(pkg, (ev,), AuditPolicy(forbidden_refs=()))
        assert pkg.claims == claims_before
        assert ev.content_ref == evidence_before


def _with_manifest(pkg, manifest):
    # Build a fresh immutable package with the given provenance_manifest.
    return CandidateCharacterPackage(
        package_id=pkg.package_id,
        subject_id=pkg.subject_id,
        package_version=pkg.package_version,
        source_snapshot_id=pkg.source_snapshot_id,
        role_result_refs=pkg.role_result_refs,
        claims=pkg.claims,
        contradictions=pkg.contradictions,
        unknowns=pkg.unknowns,
        psychology_candidate=pkg.psychology_candidate,
        voice_candidate=pkg.voice_candidate,
        validation_results=pkg.validation_results,
        audit_result=pkg.audit_result,
        provenance_manifest=manifest,
        created_at=pkg.created_at,
        status=pkg.status,
    )