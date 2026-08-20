#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CRP MVP Slice 7A -- R8 LLM judgment offline tests (mocked provider only).

Covers the typed LLM judgment contract, fail-closed parsing with exact-bound
identity validation, deterministic-wrapper composition (hard blocker cannot be
overridden), and adversarial cases. No provider, no network, no Kira.
"""

from __future__ import annotations

import json

import pytest

from services.crp_authoring.auditor_checks import AuditPolicy, run_deterministic_audit
from services.crp_authoring.candidate_package import CandidateCharacterPackage
from services.crp_authoring.contracts import ClaimType, SourceType
from services.crp_authoring.errors import CrpValidationError
from services.crp_authoring.r8_llm_judgment import (
    CHECK_MODULE_PLACEMENT,
    CHECK_ROLE_BOUNDARY_SEMANTIC,
    CHECK_UNKNOWN_COVERAGE,
    R8_ROLE_ID,
    R8_ROLE_VERSION,
    compose_final_audit,
    parse_r8_llm_result,
    render_r8_messages,
    run_r8_analysis,
)
from services.crp_authoring.reconstruction_audit import (
    AuditCheckOutcome,
    AuditVerdict,
)

from tests.crp_authoring.conftest import make_claim, make_package, make_source

SUBJECT = "char-subject-1"
PKG_ID = "pkg-001"


def _clean_package():
    claim = make_claim(claim_id="c1", claim_type=ClaimType.FACT,
                       source_type_summary=(SourceType.OWNER_DIRECT,),
                       target_module_or_layer="psychology.P0")
    pkg = make_package(package_id=PKG_ID, subject_id=SUBJECT, claims=(claim,))
    return _with_manifest(pkg, {"psychology.P0": ("c1",)})


def _with_manifest(pkg, manifest):
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


def _evidence(seed="se-001"):
    return (make_source(source_id=seed, content_ref="ref://raw/001"),)


def _clean_llm_json(**overrides):
    data = {
        "package_id": PKG_ID,
        "subject_id": SUBJECT,
        "role_id": R8_ROLE_ID,
        "role_version": R8_ROLE_VERSION,
        "checks": [
            {"check_id": CHECK_ROLE_BOUNDARY_SEMANTIC, "outcome": "PASS", "findings": []},
            {"check_id": CHECK_MODULE_PLACEMENT, "outcome": "PASS", "findings": []},
            {"check_id": CHECK_UNKNOWN_COVERAGE, "outcome": "PASS", "findings": []},
        ],
        "narrative": "clean",
    }
    data.update(overrides)
    return json.dumps(data, ensure_ascii=False)


class TestParseExactBound:
    def test_parses_clean(self) -> None:
        pkg = _clean_package()
        j = parse_r8_llm_result(_clean_llm_json(), pkg, ())
        assert j.role_id == "R8"
        assert j.package_id == PKG_ID
        assert len(j.checks) == 3

    def test_wrong_subject_id_rejected(self) -> None:
        pkg = _clean_package()
        with pytest.raises(CrpValidationError):
            parse_r8_llm_result(_clean_llm_json(subject_id="other"), pkg, ())

    def test_wrong_role_id_rejected(self) -> None:
        pkg = _clean_package()
        with pytest.raises(CrpValidationError):
            parse_r8_llm_result(_clean_llm_json(role_id="R2"), pkg, ())

    def test_wrong_role_version_rejected(self) -> None:
        pkg = _clean_package()
        with pytest.raises(CrpValidationError):
            parse_r8_llm_result(_clean_llm_json(role_version="v2"), pkg, ())

    def test_wrong_package_id_rejected(self) -> None:
        pkg = _clean_package()
        with pytest.raises(CrpValidationError):
            parse_r8_llm_result(_clean_llm_json(package_id="other"), pkg, ())

    def test_malformed_json_rejected(self) -> None:
        pkg = _clean_package()
        with pytest.raises(CrpValidationError):
            parse_r8_llm_result("not json", pkg, ())

    def test_empty_output_rejected(self) -> None:
        pkg = _clean_package()
        with pytest.raises(CrpValidationError):
            parse_r8_llm_result("  ", pkg, ())

    def test_unknown_field_rejected(self) -> None:
        pkg = _clean_package()
        bad = _clean_llm_json()
        bad = json.loads(bad)
        bad["extra"] = "x"
        with pytest.raises(CrpValidationError):
            parse_r8_llm_result(json.dumps(bad), pkg, ())

    def test_unknown_check_id_rejected(self) -> None:
        pkg = _clean_package()
        data = json.loads(_clean_llm_json())
        data["checks"][0]["check_id"] = "R8_BOGUS"
        with pytest.raises(CrpValidationError):
            parse_r8_llm_result(json.dumps(data), pkg, ())

    def test_missing_required_semantic_check_rejected(self) -> None:
        pkg = _clean_package()
        data = json.loads(_clean_llm_json())
        data["checks"] = data["checks"][:2]
        with pytest.raises(CrpValidationError):
            parse_r8_llm_result(json.dumps(data), pkg, ())

    def test_invented_claim_id_rejected(self) -> None:
        pkg = _clean_package()
        data = json.loads(_clean_llm_json())
        data["checks"][1]["outcome"] = "FAIL"
        data["checks"][1]["findings"] = [{
            "check_id": CHECK_MODULE_PLACEMENT,
            "message": "misplaced",
            "claim_id": "ghost-claim",
        }]
        with pytest.raises(CrpValidationError):
            parse_r8_llm_result(json.dumps(data), pkg, ())

    def test_invented_evidence_id_rejected(self) -> None:
        pkg = _clean_package()
        ev = _evidence("se-real")
        data = json.loads(_clean_llm_json())
        data["checks"][2]["outcome"] = "FAIL"
        data["checks"][2]["findings"] = [{
            "check_id": CHECK_UNKNOWN_COVERAGE,
            "message": "gap",
            "evidence_ids": ["ghost-ev"],
        }]
        with pytest.raises(CrpValidationError):
            parse_r8_llm_result(json.dumps(data), pkg, ev)

    def test_llm_blocked_outcome_rejected(self) -> None:
        pkg = _clean_package()
        data = json.loads(_clean_llm_json())
        data["checks"][0]["outcome"] = "BLOCKED"
        with pytest.raises(CrpValidationError):
            parse_r8_llm_result(json.dumps(data), pkg, ())


class TestPromptRendering:
    def test_exposes_all_exact_bound_fields(self) -> None:
        pkg = _clean_package()
        deterministic = run_deterministic_audit(pkg, (), AuditPolicy())
        msgs = render_r8_messages(pkg, (), deterministic)
        user = msgs[1]["content"]
        assert f"package_id: {PKG_ID}" in user
        assert f"subject_id: {SUBJECT}" in user
        assert "role_id: R8" in user
        assert "role_version: v1" in user

    def test_prompt_contains_no_raw_roleresult_or_hidden_eval(self) -> None:
        pkg = _clean_package()
        deterministic = run_deterministic_audit(pkg, (), AuditPolicy())
        msgs = render_r8_messages(pkg, (), deterministic)
        user_data = msgs[1]["content"]
        # The system prompt may name "RoleResult" as a forbidden input; the
        # actual rendered DATA block must not carry any raw RoleResult payload.
        assert "claims=" not in user_data  # no raw role-output framing beyond package claims
        assert "FORBIDDEN_INPUTS" in msgs[0]["content"]  # prompt boundary present
        combined_lower = (msgs[0]["content"] + user_data).lower()
        # No accepted benchmark answer-key marker.
        assert "recognizability" not in combined_lower


class TestCompositionRunner:
    def _semantic_finding_check(self, outcome="FAIL", check_id=CHECK_MODULE_PLACEMENT,
                                message="misplaced"):
        data = json.loads(_clean_llm_json())
        for chk in data["checks"]:
            if chk["check_id"] == check_id:
                chk["outcome"] = outcome
                chk["findings"] = [{
                    "check_id": check_id,
                    "message": message,
                    "claim_id": "c1",
                }]
        return json.dumps(data, ensure_ascii=False)

    def test_case_a_clean_clean(self) -> None:
        pkg = _clean_package()
        result = run_r8_analysis(pkg, (), lambda msgs: _clean_llm_json())
        assert result.verdict is AuditVerdict.PASS

    def test_case_b_hard_blocker_not_overrideable(self) -> None:
        pkg = _clean_package()
        ev = make_source(source_id="se-leak", content_ref="personas/kira/profile.json")
        calls = []
        def fake_provider(msgs):
            calls.append(msgs)
            return _clean_llm_json()
        result = run_r8_analysis(
            pkg, (ev,), fake_provider, forbidden_refs=("personas/kira/**",),
        )
        # Fail-fast: deterministic BLOCKED skips the LLM entirely.
        assert calls == []
        assert result.verdict is AuditVerdict.BLOCKED

    def test_case_c_semantic_finding_survives(self) -> None:
        pkg = _clean_package()
        result = run_r8_analysis(
            pkg, (), lambda msgs: self._semantic_finding_check(),
        )
        assert result.verdict is AuditVerdict.FAIL
        assert any(c.check == CHECK_MODULE_PLACEMENT for c in result.checks)
        assert result.defects

    def test_compose_hard_blocker_cannot_be_cleared(self) -> None:
        pkg = _clean_package()
        ev = make_source(source_id="se-leak", content_ref="personas/kira/profile.json")
        deterministic = run_deterministic_audit(
            pkg, (ev,), AuditPolicy(forbidden_refs=("personas/kira/**",)),
        )
        judgment = parse_r8_llm_result(_clean_llm_json(), pkg, (ev,))
        final = compose_final_audit(deterministic, judgment)
        assert final.verdict is AuditVerdict.BLOCKED

    def test_inputs_not_mutated(self) -> None:
        pkg = _clean_package()
        claims_before = tuple(pkg.claims)
        run_r8_analysis(pkg, (), lambda msgs: _clean_llm_json())
        assert pkg.claims == claims_before