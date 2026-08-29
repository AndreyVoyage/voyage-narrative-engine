#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CRP MVP Slice 7A -- R8 LLM judgment offline tests (mocked provider only).

Covers the typed LLM judgment contract, fail-closed parsing with exact-bound
identity validation, deterministic-wrapper composition (hard blocker cannot be
overridden), and adversarial cases. No provider, no network, no Kira.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.crp_authoring.auditor_checks import AuditPolicy, run_deterministic_audit
from services.crp_authoring.candidate_package import CandidateCharacterPackage
from services.crp_authoring.contracts import ClaimType, SourceType
from services.crp_authoring.dataset_freeze import canonical_json_sha256
from services.crp_authoring.errors import CrpValidationError
from services.crp_authoring.r8_llm_judgment import (
    CHECK_MODULE_PLACEMENT,
    CHECK_ROLE_BOUNDARY_SEMANTIC,
    CHECK_UNKNOWN_COVERAGE,
    R8_ROLE_ID,
    R8_ROLE_VERSION,
    _R8_PROMPT_PATH,
    compose_final_audit,
    parse_r8_llm_result,
    render_r8_messages,
    run_r8_analysis,
)
from services.crp_authoring.reconstruction_audit import (
    AuditCheckOutcome,
    AuditVerdict,
)

from tests.crp_authoring.conftest import (
    make_claim,
    make_package,
    make_payload_map,
    make_source,
)

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
            # Active R8 version is v2; the historical v1 role_version is rejected.
            parse_r8_llm_result(_clean_llm_json(role_version="v1"), pkg, ())

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
        msgs = render_r8_messages(pkg, (), deterministic, {})
        user = msgs[1]["content"]
        assert f"package_id: {PKG_ID}" in user
        assert f"subject_id: {SUBJECT}" in user
        assert "role_id: R8" in user
        assert "role_version: v2" in user

    def test_prompt_contains_no_raw_roleresult_or_hidden_eval(self) -> None:
        pkg = _clean_package()
        deterministic = run_deterministic_audit(pkg, (), AuditPolicy())
        msgs = render_r8_messages(pkg, (), deterministic, {})
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
        result = run_r8_analysis(pkg, (), lambda msgs: _clean_llm_json(), evidence_payloads={})
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
            evidence_payloads=make_payload_map("se-leak"),
        )
        # Fail-fast: deterministic BLOCKED skips the LLM entirely.
        assert calls == []
        assert result.verdict is AuditVerdict.BLOCKED

    def test_case_c_semantic_finding_survives(self) -> None:
        pkg = _clean_package()
        result = run_r8_analysis(
            pkg, (), lambda msgs: self._semantic_finding_check(), evidence_payloads={},
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
        run_r8_analysis(pkg, (), lambda msgs: _clean_llm_json(), evidence_payloads={})
        assert pkg.claims == claims_before


class TestR8NoneFailClosed:
    """MAT-02: evidence_payloads is required for R8 provider-bound paths."""

    def test_r8_none_01_explicit_none_fails_before_provider(self):
        pkg = _clean_package()
        evidence = _evidence("se-001")
        calls = []

        def counted(msgs):
            calls.append(msgs)
            return _clean_llm_json()

        with pytest.raises(CrpValidationError):
            run_r8_analysis(pkg, evidence, counted, evidence_payloads=None)
        assert len(calls) == 0

    def test_r8_none_02_omitted_argument_fails_at_api(self):
        pkg = _clean_package()
        evidence = _evidence("se-001")
        with pytest.raises(TypeError):
            run_r8_analysis(pkg, evidence, lambda msgs: _clean_llm_json())

    def test_r8_none_03_empty_map_with_nonempty_evidence_fails(self):
        pkg = _clean_package()
        evidence = _evidence("se-001")
        calls = []

        def counted(msgs):
            calls.append(msgs)
            return _clean_llm_json()

        with pytest.raises(CrpValidationError):
            run_r8_analysis(pkg, evidence, counted, evidence_payloads={})
        assert len(calls) == 0


class TestR8SubstantiveMaterialization:
    """CRP R4 pre-provider correction: R8 must receive substantive facts,
    hash-bound to authoritative evidence before the provider callable runs."""

    SENTINEL = "OWNER_FACT_SENTINEL_9F3B7"
    UNALLOWED = "UNALLOWED_SENTINEL_B7C21"

    def _facts(self):
        return [{"fact": self.SENTINEL, "detail": "owner-authored"}]

    def _evidence_with_payloads(self, *, evidence_id="se-001"):
        facts = self._facts()
        content_hash = canonical_json_sha256(facts)
        ev = make_source(source_id=evidence_id, content_ref="ref://raw/001",
                         content_hash=content_hash)
        payloads = {evidence_id: {"section_id": "s1", "title": "t", "facts": facts}}
        return (ev,), payloads

    def test_r8_mat01_substantive_reaches_provider(self):
        pkg = _clean_package()
        evidence, payloads = self._evidence_with_payloads()
        seen = {}

        def capture(msgs):
            seen["messages"] = msgs
            return _clean_llm_json()

        run_r8_analysis(pkg, evidence, capture, evidence_payloads=payloads)
        user = [m["content"] for m in seen["messages"] if m["role"] == "user"][0]
        assert self.SENTINEL in user
        assert "substantive_payload" in user

    def test_r8_mat02_identity_metadata_present(self):
        pkg = _clean_package()
        evidence, payloads = self._evidence_with_payloads()
        seen = {}

        def capture(msgs):
            seen["messages"] = msgs
            return _clean_llm_json()

        run_r8_analysis(pkg, evidence, capture, evidence_payloads=payloads)
        user = [m["content"] for m in seen["messages"] if m["role"] == "user"][0]
        assert "se-001" in user
        assert "content_ref" in user

    def test_r8_mat03_hash_mismatch_fails_before_provider(self):
        pkg = _clean_package()
        evidence, payloads = self._evidence_with_payloads()
        payloads["se-001"] = {"section_id": "s1", "title": "t",
                              "facts": [{"fact": "TAMPERED"}]}
        calls = []

        def counted(msgs):
            calls.append(msgs)
            return _clean_llm_json()

        with pytest.raises(CrpValidationError):
            run_r8_analysis(pkg, evidence, counted, evidence_payloads=payloads)
        assert len(calls) == 0

    def test_r8_mat04_missing_payload_fails_before_provider(self):
        pkg = _clean_package()
        evidence, _payloads = self._evidence_with_payloads()
        calls = []

        def counted(msgs):
            calls.append(msgs)
            return _clean_llm_json()

        with pytest.raises(CrpValidationError):
            run_r8_analysis(pkg, evidence, counted, evidence_payloads={})
        assert len(calls) == 0

    def test_r8_mat05_payload_map_only_extra_absent(self):
        pkg = _clean_package()
        evidence, payloads = self._evidence_with_payloads()
        payloads["ghost-id"] = {"section_id": "g", "title": "g",
                                "facts": [{"fact": self.UNALLOWED}]}
        seen = {}

        def capture(msgs):
            seen["messages"] = msgs
            return _clean_llm_json()

        run_r8_analysis(pkg, evidence, capture, evidence_payloads=payloads)
        user = [m["content"] for m in seen["messages"] if m["role"] == "user"][0]
        assert self.SENTINEL in user
        assert self.UNALLOWED not in user
        assert "ghost-id" not in user


def _prompt_low() -> str:
    pkg = _clean_package()
    deterministic = run_deterministic_audit(pkg, (), AuditPolicy())
    text = render_r8_messages(pkg, (), deterministic, {})[0]["content"]
    return " ".join(text.split()).lower()


class TestR8FieldGroundingGuard:
    """Deterministic post-parse guard: a finding must not make a mechanically
    false ``field=value`` assertion about an authoritative Candidate field."""

    def _package(self, *, claim_type=ClaimType.FACT, target="behavior.conflict_style",
                 role_id="R2"):
        claim = make_claim(claim_id="c1", claim_type=claim_type, role_id=role_id,
                           target_module_or_layer=target)
        pkg = make_package(package_id=PKG_ID, subject_id=SUBJECT, claims=(claim,))
        return _with_manifest(pkg, {target: ("c1",)})

    def _judgment(self, check_id, message, *, evidence_ids=None):
        data = json.loads(_clean_llm_json())
        for chk in data["checks"]:
            if chk["check_id"] == check_id:
                chk["outcome"] = "FAIL"
                finding = {"check_id": check_id, "message": message, "claim_id": "c1"}
                if evidence_ids is not None:
                    finding["evidence_ids"] = evidence_ids
                chk["findings"] = [finding]
        return json.dumps(data, ensure_ascii=False)

    def test_t1_target_misstatement_rejected(self) -> None:
        pkg = self._package(target="behavior.conflict_style")
        raw = self._judgment(CHECK_MODULE_PLACEMENT, "misplaced: target=psychology.P3")
        with pytest.raises(CrpValidationError) as ei:
            parse_r8_llm_result(raw, pkg, ())
        assert "target" in str(ei.value)

    def test_t2_claim_type_misstatement_rejected(self) -> None:
        pkg = self._package(claim_type=ClaimType.FACT)
        raw = self._judgment(CHECK_ROLE_BOUNDARY_SEMANTIC,
                             "claim_type=INFERENCE blurs direct evidence")
        with pytest.raises(CrpValidationError) as ei:
            parse_r8_llm_result(raw, pkg, ())
        assert "claim_type" in str(ei.value)

    def test_correct_field_assertions_not_rejected(self) -> None:
        pkg = self._package(claim_type=ClaimType.FACT, target="behavior.conflict_style")
        raw = self._judgment(CHECK_MODULE_PLACEMENT,
                             "target=behavior.conflict_style claim_type=FACT ok")
        assert parse_r8_llm_result(raw, pkg, ()).checks

    def test_prose_without_assignment_never_false_rejected(self) -> None:
        # A genuine placement finding phrased in prose (no field=value) must
        # survive -- R8 may still propose an alternative target.
        pkg = self._package(target="behavior.conflict_style")
        raw = self._judgment(CHECK_MODULE_PLACEMENT, "should be moved to psychology.P3")
        assert parse_r8_llm_result(raw, pkg, ()).checks


class TestR8PromptGrounding:
    """The R8 prompt must carry explicit grounding rules for the RUN_015 classes."""

    def test_t3_evidence_id_grounding_rule_present(self) -> None:
        low = _prompt_low()
        assert "content must come from the specific" in low
        assert "do not borrow wording from one evidence record" in low

    def test_t4_unknown_coverage_rule_present(self) -> None:
        low = _prompt_low()
        assert "package `unknowns`" in low
        assert "routed to `package.unknowns`" in low

    def test_t5_owner_direct_personality_not_auto_inference(self) -> None:
        low = _prompt_low()
        assert "personality" in low
        assert "not automatically an inference" in low

    def test_t6_owner_direct_emotional_state_not_auto_inference(self) -> None:
        low = _prompt_low()
        assert "emotion" in low

    def test_t7_r2_r3_not_defective_for_faithful_direct_fact(self) -> None:
        low = _prompt_low()
        assert "r2/r3 are not defective" in low

    def test_t8_undefined_p_layer_no_invented_taxonomy(self) -> None:
        low = _prompt_low()
        assert "do not invent a taxonomy" in low
        assert "only fail" in low


def _v1_prompt_text() -> str:
    return (
        Path(__file__).resolve().parents[2]
        / "roles/vnext/ROLE_8_INDEPENDENT_EVIDENCE_AUDITOR_v1_PROMPT.md"
    ).read_text(encoding="utf-8")


class TestR8VersionRouting:
    """R8 v1 is the immutable historical provider-facing prompt; the active
    dedicated semantic R8 version is v2, which carries the RUN_015 grounding
    correction. The historical v1 prompt must remain available and unchanged."""

    def test_active_dedicated_r8_version_is_v2(self) -> None:
        assert R8_ROLE_VERSION == "v2"

    def test_dedicated_prompt_path_points_to_v2(self) -> None:
        assert _R8_PROMPT_PATH.endswith(
            "ROLE_8_INDEPENDENT_EVIDENCE_AUDITOR_v2_PROMPT.md"
        )

    def test_historical_v1_available_and_unchanged(self) -> None:
        text = _v1_prompt_text()
        assert "prompt_version: v1" in text
        # The RUN_015 grounding correction must live ONLY in v2, never v1.
        assert "GROUNDING_RULES" not in text
        assert "must not state that a claim has a different claim_type" not in text

    def test_active_v2_system_prompt_contains_grounding_rules(self) -> None:
        pkg = _clean_package()
        deterministic = run_deterministic_audit(pkg, (), AuditPolicy())
        system = render_r8_messages(pkg, (), deterministic, {})[0]["content"]
        assert "GROUNDING_RULES" in system
        assert "prompt_version: v2" in system
