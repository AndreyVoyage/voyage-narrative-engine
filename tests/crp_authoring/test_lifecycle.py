#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CRP MVP Slice 9 -- lifecycle + human acceptance tests (offline, synthetic).

No provider, no network, no Kira, no canon/PAC/Sandbox. Exercises the explicit
human-authority transitions: advance_to_audited, accept_candidate (PASS-only),
reject_candidate (explicit terminal), and the immutable AcceptanceRecord.
"""

from __future__ import annotations

import ast
import dataclasses
from pathlib import Path

import pytest

from services.crp_authoring import (
    ClaimType,
    Confidence,
    CrpValidationError,
    PackageStatus,
    accept_candidate,
    advance_to_audited,
    compute_package_hash,
    reject_candidate,
)
from services.crp_authoring.auditor_checks import AuditPolicy, run_deterministic_audit
from services.crp_authoring.candidate_package import CandidateCharacterPackage
from services.crp_authoring.lifecycle import AcceptanceRecord
from services.crp_authoring.reconstruction_audit import AuditVerdict, ReconstructionAudit
from services.crp_authoring.validator import ValidationReport

from tests.crp_authoring.conftest import make_claim, make_contradiction, make_package

PKG = "pkg-001"
SUBJECT = "char-subject-1"


def _draft(**overrides):
    return make_package(package_id=PKG, subject_id=SUBJECT, **overrides)


def _valid_report():
    return ValidationReport(valid=True, findings=())


def _pass_audit(package) -> ReconstructionAudit:
    return run_deterministic_audit(package, (), AuditPolicy())


def _audited(package=None, **overrides):
    pkg = package if package is not None else _draft(**overrides)
    audit = _pass_audit(pkg)
    return advance_to_audited(pkg, _valid_report(), audit), audit


# ---------------------------------------------------------------------------
# T1 — valid explicit human accept
# ---------------------------------------------------------------------------

class TestAccept:
    def test_t1_valid_explicit_human_accept(self):
        draft = _draft()
        audit = _pass_audit(draft)
        audited = advance_to_audited(draft, _valid_report(), audit)

        assert audited.status is PackageStatus.AUDITED
        assert draft.status is PackageStatus.DRAFT  # input unchanged
        assert audited.audit_result is audit
        assert audited.validation_results["report"].valid is True

        approved, record = accept_candidate(
            audited, audited.audit_result, accepted_by="owner-alice", acceptance_id="acc-1",
        )
        assert approved.status is PackageStatus.HUMAN_APPROVED
        assert audited.status is PackageStatus.AUDITED  # input unchanged
        assert isinstance(record, AcceptanceRecord)
        assert record.decision is PackageStatus.HUMAN_APPROVED
        assert record.audit_id == audit.audit_id

    def test_t2_no_auto_accept_from_advance(self):
        # advance_to_audited must NEVER produce HUMAN_APPROVED.
        draft = _draft()
        audited, _ = _audited(draft)
        assert audited.status is PackageStatus.AUDITED
        assert audited.status is not PackageStatus.HUMAN_APPROVED

    def test_t3_invalid_r7_cannot_advance(self):
        draft = _draft()
        audit = _pass_audit(draft)
        with pytest.raises(CrpValidationError):
            advance_to_audited(draft, ValidationReport(valid=False, findings=()), audit)

    def test_t4_missing_or_invalid_audit(self):
        draft = _draft()
        # accept_candidate requires a ReconstructionAudit; None fails closed.
        audited, _ = _audited(draft)
        with pytest.raises(CrpValidationError):
            accept_candidate(audited, None, accepted_by="x", acceptance_id="a")
        # advance_to_audited requires a ReconstructionAudit too.
        with pytest.raises(CrpValidationError):
            advance_to_audited(draft, _valid_report(), None)

    def test_t5_verdict_policy_pass_only(self):
        draft = _draft()
        pass_audit = _pass_audit(draft)
        audited = advance_to_audited(draft, _valid_report(), pass_audit)

        # PASS accepted.
        approved, _ = accept_candidate(
            audited, pass_audit, accepted_by="owner-alice", acceptance_id="acc-pass",
        )
        assert approved.status is PackageStatus.HUMAN_APPROVED

        # FAIL / INCONCLUSIVE / BLOCKED refused, even with a reason supplied.
        for verdict in (AuditVerdict.FAIL, AuditVerdict.INCONCLUSIVE, AuditVerdict.BLOCKED):
            # fresh DRAFT -> AUDITED package so status constraint does not mask verdict check
            d2 = _draft()
            a2 = _pass_audit(d2)
            audited2 = advance_to_audited(d2, _valid_report(), a2)
            bad_audit = dataclasses.replace(a2, verdict=verdict)
            with pytest.raises(CrpValidationError):
                accept_candidate(
                    audited2, bad_audit, accepted_by="owner-alice",
                    acceptance_id=f"acc-{verdict.value}", reason="override attempt",
                )

    def test_t6_identity_and_stale_hash(self):
        draft = _draft()
        audit = _pass_audit(draft)
        audited = advance_to_audited(draft, _valid_report(), audit)

        # Wrong package_id.
        other_pkg = make_package(package_id="pkg-OTHER", subject_id=SUBJECT)
        other_pkg_audited, other_audit = _audited(other_pkg)
        with pytest.raises(CrpValidationError):
            accept_candidate(
                other_pkg_audited, audit, accepted_by="x", acceptance_id="acc-wrong-id",
            )

        # Stale hash: same logical identity but different hashed content.
        tampered = _draft(claims=(make_claim(claim_id="c1", target_module_or_layer="psychology.P2"),))
        tampered_audit = _pass_audit(tampered)
        # Build an AUDITED package from tampered content, then try accepting with
        # the ORIGINAL draft's audit (different hash).
        with pytest.raises(CrpValidationError):
            accept_candidate(
                advance_to_audited(tampered, _valid_report(), tampered_audit),
                audit,  # original audit binds different content
                accepted_by="x", acceptance_id="acc-stale",
            )

        # Assert hash genuinely differs.
        assert compute_package_hash(tampered) != compute_package_hash(draft)

    def test_t7_unknown_preserved_not_blocking(self):
        u = make_claim(
            claim_id="u1", claim_type=ClaimType.UNKNOWN,
            target_module_or_layer="identity_biography.birthplace",
            source_evidence_ids=(), confidence=Confidence.UNKNOWN,
        )
        draft = _draft(unknowns=(u,))
        audited, audit = _audited(draft)
        approved, _ = accept_candidate(
            audited, audit, accepted_by="owner-alice", acceptance_id="acc-unknown",
        )
        assert approved.status is PackageStatus.HUMAN_APPROVED
        assert approved.unknowns == draft.unknowns
        assert approved.unknowns == (u,)

    def test_t8_contradictions_preserved_not_blocking(self):
        a = make_claim(claim_id="c-a", target_module_or_layer="behavior.conflict_style")
        b = make_claim(claim_id="c-b", target_module_or_layer="behavior.conflict_style")
        crd = make_contradiction(contradiction_id="crd-1", claim_ids=("c-a", "c-b"))
        draft = _draft(claims=(a, b), contradictions=(crd,))
        audited, audit = _audited(draft)
        approved, _ = accept_candidate(
            audited, audit, accepted_by="owner-alice", acceptance_id="acc-crd",
        )
        assert approved.status is PackageStatus.HUMAN_APPROVED
        assert approved.contradictions == draft.contradictions == (crd,)

    def test_t9_seed_memory_preserved(self):
        sm = make_claim(claim_id="sm1", target_module_or_layer="seed_memory.first_meeting")
        draft = _draft(seed_memory_candidate={"first_meeting": (sm,)}, claims=(sm,))
        audited, audit = _audited(draft)
        approved, _ = accept_candidate(
            audited, audit, accepted_by="owner-alice", acceptance_id="acc-sm",
        )
        assert approved.seed_memory_candidate == draft.seed_memory_candidate

    def test_t10_immutability(self):
        draft = _draft()
        a0 = _pass_audit(draft)
        audited = advance_to_audited(draft, _valid_report(), a0)
        approved, _ = accept_candidate(
            audited, a0, accepted_by="owner-alice", acceptance_id="acc-imm",
        )
        rejected, _ = reject_candidate(
            _draft(), rejected_by="owner-bob", acceptance_id="acc-rej", reason="nope",
        )

        # Original untouched; each transition returns a distinct frozen instance.
        assert draft.status is PackageStatus.DRAFT
        assert audited is not draft
        assert approved is not audited
        assert rejected is not draft

        with pytest.raises(Exception):
            draft.status = PackageStatus.AUDITED
        with pytest.raises(Exception):
            audited.status = PackageStatus.DRAFT
        with pytest.raises(Exception):
            approved.status = PackageStatus.DRAFT

    def test_t11_repeated_accept_hard_fail(self):
        draft = _draft()
        audited, audit = _audited(draft)
        approved, _ = accept_candidate(
            audited, audit, accepted_by="owner-alice", acceptance_id="acc-once",
        )
        # Accepting an already HUMAN_APPROVED package hard-fails.
        with pytest.raises(CrpValidationError):
            accept_candidate(
                approved, audit, accepted_by="owner-alice", acceptance_id="acc-twice",
            )

        # A REJECTED package cannot be accepted.
        rejected, _ = reject_candidate(
            _draft(), rejected_by="owner-bob", acceptance_id="acc-rej", reason="nope",
        )
        with pytest.raises(CrpValidationError):
            accept_candidate(rejected, audit, accepted_by="x", acceptance_id="acc-rejtoacc")

    def test_t15_identity_lineage_preserved(self):
        draft = _draft(lineage="lineage-v1")
        audited, audit = _audited(draft)
        approved, _ = accept_candidate(
            audited, audit, accepted_by="owner-alice", acceptance_id="acc-lin",
        )
        for p in (audited, approved):
            assert p.package_id == draft.package_id == PKG
            assert p.package_version == draft.package_version
            assert p.subject_id == draft.subject_id == SUBJECT
            assert p.source_snapshot_id == draft.source_snapshot_id
            assert p.lineage == draft.lineage == "lineage-v1"


# ---------------------------------------------------------------------------
# Rejection
# ---------------------------------------------------------------------------

class TestRejection:
    def test_draft_reject_allowed(self):
        draft = _draft(lineage="lineage-rej-1")
        rejected, record = reject_candidate(
            draft, rejected_by="owner-bob", acceptance_id="acc-rej", reason="insufficient scope",
        )
        assert rejected.status is PackageStatus.REJECTED
        assert record.decision is PackageStatus.REJECTED
        assert record.package_id == PKG
        assert record.package_version == draft.package_version
        assert rejected.lineage == draft.lineage == "lineage-rej-1"

    def test_audited_reject_allowed(self):
        draft = _draft()
        audited, audit = _audited(draft)
        rejected, record = reject_candidate(
            audited, rejected_by="owner-bob", acceptance_id="acc-rej-audited", reason="post-audit reject",
        )
        assert rejected.status is PackageStatus.REJECTED
        assert record.audit_id == audit.audit_id  # preserved bound audit reference

    def test_approved_reject_hard_fail(self):
        draft = _draft()
        audited, audit = _audited(draft)
        approved, _ = accept_candidate(
            audited, audit, accepted_by="owner-alice", acceptance_id="acc-1",
        )
        with pytest.raises(CrpValidationError):
            reject_candidate(approved, rejected_by="owner-bob", acceptance_id="x", reason="nope")

    def test_rejected_reject_again_hard_fail(self):
        rejected, _ = reject_candidate(
            _draft(), rejected_by="owner-bob", acceptance_id="acc-rej", reason="nope",
        )
        with pytest.raises(CrpValidationError):
            reject_candidate(rejected, rejected_by="owner-bob", acceptance_id="x", reason="nope2")

    def test_empty_rejected_by_hard_fail(self):
        with pytest.raises(CrpValidationError):
            reject_candidate(_draft(), rejected_by="", acceptance_id="x", reason="nope")

    def test_empty_reason_hard_fail(self):
        with pytest.raises(CrpValidationError):
            reject_candidate(_draft(), rejected_by="owner-bob", acceptance_id="x", reason="  ")


# ---------------------------------------------------------------------------
# Acceptance record + hash regression
# ---------------------------------------------------------------------------

class TestRecordsAndHash:
    def test_record_immutable_and_fields_match(self):
        draft = _draft()
        audited, audit = _audited(draft)
        approved, record = accept_candidate(
            audited, audit, accepted_by="owner-alice", acceptance_id="acc-1",
        )
        assert record.package_id == PKG
        assert record.package_version == draft.package_version
        assert record.subject_id == SUBJECT
        assert record.package_hash == compute_package_hash(draft)
        assert record.audit_id == audit.audit_id
        assert record.decision is PackageStatus.HUMAN_APPROVED
        assert record.decided_by == "owner-alice"
        assert record.decided_at
        with pytest.raises(Exception):
            record.acceptance_id = "mutated"  # type: ignore[misc]
        # No credential/provider fields exist.
        assert not hasattr(record, "api_key")
        assert not hasattr(record, "provider")
        assert not hasattr(record, "raw_output")

    def test_hash_regression_matches_audit(self):
        draft = _draft(claims=(make_claim(claim_id="c1", target_module_or_layer="psychology.P2"),))
        audit = run_deterministic_audit(draft, (), AuditPolicy())
        assert compute_package_hash(draft) == audit.package_hash
        # Public function is stable/deterministic.
        assert compute_package_hash(draft) == compute_package_hash(draft)


# ---------------------------------------------------------------------------
# Boundary / no-auto / terminal-API-only / no-kira
# ---------------------------------------------------------------------------

class TestBoundaries:
    def test_t12_terminal_states_only_via_lifecycle(self):
        # No production module other than lifecycle may assign the terminal
        # states (via dataclasses.replace status=...) or invoke the human
        # decision entrypoints. The enum DEFINITION itself lives in
        # candidate_package; prose/docstrings naming the states are fine.
        prod_root = Path("services/crp_authoring")
        terminal_assign = (
            "status=PackageStatus.HUMAN_APPROVED",
            "status=PackageStatus.REJECTED",
            "accept_candidate(",
            "reject_candidate(",
        )
        violations = []
        for py_file in sorted(prod_root.rglob("*.py")):
            if py_file.name == "lifecycle.py":
                continue
            text = py_file.read_text(encoding="utf-8")
            for marker in terminal_assign:
                if marker in text:
                    violations.append(f"{py_file.name}: {marker}")
        assert violations == [], f"terminal-state transition outside lifecycle: {violations}"

    def test_t13_no_provider_runtime_canon_persistence(self):
        text = Path("services/crp_authoring/lifecycle.py").read_text(encoding="utf-8")
        tree = ast.parse(text)
        mods = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods.extend(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                mods.append(node.module or "")
        forbidden = (
            "tools", "openai", "anthropic", "requests", "httpx", "urllib", "socket",
            "sqlite", "persona", "cis", "runtime", "renpy",
        )
        for m in mods:
            lower = m.lower()
            assert not any(f.lower() in lower for f in forbidden), f"forbidden import {m}"
        # No filesystem writes (no open(... 'w')-style calls).
        assert "open(" not in text

    def test_t14_no_kira_specific_logic(self):
        text = Path("services/crp_authoring/lifecycle.py").read_text(encoding="utf-8")
        for forbidden in ("kira", "hidden_eval", "accepted_benchmark", "benchmark"):
            assert forbidden not in text