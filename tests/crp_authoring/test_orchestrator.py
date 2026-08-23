#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CRP MVP Slice 8 -- Reconstruction Orchestrator tests (fake providers only).

Hermetic, synthetic, offline. No real provider, no network, no Kira, no
canon/PAC/Sandbox material. Uses the existing injected-provider convention and
existing real vNext prompt refs so fail-closed executor prompt assembly works.

Stage contract under test (single RunControl entrypoint ``run_reconstruction``):

    role execution (caller tuple order)
    -> R6 compile_candidate_package (once)
    -> R7 validate_package (fail-closed before R8)
    -> R8 run_r8_analysis (single entrypoint; deterministic hard blockers
       fail-fast internally)
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from services.crp_authoring import (
    CrpValidationError,
    ExecutorError,
    RoleRegistry,
    RoleStatus,
    SourceType,
    run_reconstruction,
)
from services.crp_authoring.auditor_checks import AuditPolicy
from services.crp_authoring.candidate_package import CandidateCharacterPackage, PackageStatus
from services.crp_authoring.dataset_freeze import canonical_json_sha256
from services.crp_authoring.reconstruction_audit import AuditVerdict, ReconstructionAudit
from services.crp_authoring.role_task import RoleResult
from services.crp_authoring.validator import ValidationReport
from services.crp_authoring import orchestrator as orch

from tests.crp_authoring.conftest import (
    make_compile_context,
    make_knowledge_profile,
    make_payload_map,
    make_registry_entry,
    make_role_task,
    make_source,
)

SUBJECT = "char-subject-1"
SNAPSHOT = "snapshot-1"
RUN_ID = "run-1"
PKG_ID = "pkg-001"

# Exact real vNext prompt refs (fail-closed executor prompt assembly).
_PROMPT_REFS = {
    "R1": "roles/vnext/ROLE_1_EVIDENCE_INTERVIEWER_v1_PROMPT.md",
    "R2": "roles/vnext/ROLE_2_PSYCHOLOGICAL_HYPOTHESIS_ANALYST_v1_PROMPT.md",
    "R4": "roles/vnext/ROLE_4_VOICE_RECONSTRUCTION_ANALYST_v1_PROMPT.md",
}


# ---------------------------------------------------------------------------
# Payload helpers
# ---------------------------------------------------------------------------

def _claim(claim_id, role_id, claim_type, target, *, source_summary=("OWNER_DIRECT",),
           confidence="KNOWN", evidence_ids=("se-001",), claim_text="synthetic"):
    return {
        "claim_id": claim_id,
        "subject_id": SUBJECT,
        "role_id": role_id,
        "claim": claim_text,
        "claim_type": claim_type,
        "source_evidence_ids": list(evidence_ids),
        "source_type_summary": list(source_summary),
        "confidence": confidence,
        "rationale_summary": "synthetic offline orchestrator test",
        "status": "PROPOSED",
        "target_module_or_layer": target,
    }


def _role_result_json(task_id, role_id, claims, *, contradictions=(), unknowns=()):
    return json.dumps({
        "task_id": task_id,
        "role_id": role_id,
        "role_version": "v1",
        "completion_status": "COMPLETE",
        "claims": claims,
        "unknowns": list(unknowns),
        "contradictions": list(contradictions),
        "provenance_summary": {"used_evidence": ["se-001"]},
        "requests_for_more_evidence": [],
        "warnings": [],
        "questions_for_r1": [],
        "new_source_evidence": [],
    }, ensure_ascii=False)


def _r8_judgment_json(package_id=PKG_ID, subject_id=SUBJECT):
    return json.dumps({
        "package_id": package_id,
        "subject_id": subject_id,
        "role_id": "R8",
        "role_version": "v1",
        "checks": [
            {"check_id": "R8_ROLE_BOUNDARY_SEMANTIC", "outcome": "PASS", "findings": []},
            {"check_id": "R8_MODULE_PLACEMENT", "outcome": "PASS", "findings": []},
            {"check_id": "R8_UNKNOWN_COVERAGE", "outcome": "PASS", "findings": []},
        ],
        "narrative": "clean",
    }, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Scope builders
# ---------------------------------------------------------------------------

def _evidence(content_ref="ref://raw/001", provenance="synthetic-fixture"):
    return (
        make_source(
            source_id="se-001", source_type=SourceType.OWNER_DIRECT,
            subject_id=SUBJECT, evidence_snapshot_id=SNAPSHOT,
            content_ref=content_ref, provenance=provenance,
        ),
    )


def _build_scope(role_ids, evidence, *, run_id=RUN_ID, snapshot=SNAPSHOT):
    """Build one shared registry + profiles + tasks for the given roles."""
    registry = RoleRegistry(tuple(
        make_registry_entry(role_id=r, version="v1", prompt_ref=_PROMPT_REFS[r])
        for r in role_ids
    ))
    profiles = {
        f"profile-{r.lower()}": make_knowledge_profile(
            profile_id=f"profile-{r.lower()}", role_id=r,
        )
        for r in role_ids
    }
    tasks = tuple(
        make_role_task(
            task_id=f"task-{r.lower()}", role_id=r, role_version="v1",
            allowed_evidence_ids=("se-001",),
            run_id=run_id, evidence_snapshot_id=snapshot, subject_id=SUBJECT,
        )
        for r in role_ids
    )
    return registry, profiles, tasks


def _dispatch_provider(role_payloads, r8_json=None, *, on_r8=None):
    """Return an injected provider that dispatches role vs R8 calls.

    Role calls are identified by ``- role_id: <id>`` in the assembled user
    message; the R8 call is identified by its ``AUDIT_IDENTITY`` data marker.
    """
    calls = {"count": 0}
    r8_calls = {"count": 0}

    def provider(messages):
        calls["count"] += 1
        user_content = "".join(
            m["content"] for m in messages if m.get("role") == "user"
        )
        if "AUDIT_IDENTITY" in user_content:
            r8_calls["count"] += 1
            if on_r8 is not None:
                on_r8()
            if r8_json is None:
                raise AssertionError("unexpected R8 semantic provider call")
            return r8_json
        for role_id, payload in role_payloads.items():
            if f"- role_id: {role_id}" in user_content:
                return payload
        raise AssertionError("provider received an unrecognized call")

    return provider, calls, r8_calls


def _happy_role_payloads():
    return {
        "R1": _role_result_json("task-r1", "R1", [
            _claim("c-ident", "R1", "FACT", "identity_biography.birthplace",
                   claim_text="subject born in a coastal town"),
        ]),
        "R2": _role_result_json("task-r2", "R2", [
            _claim("c-behav", "R2", "HYPOTHESIS", "behavior.conflict_style",
                   confidence="POSSIBLE", claim_text="subject avoids confrontation"),
        ]),
        "R4": _role_result_json("task-r4", "R4", [
            _claim("c-voice", "R4", "OBSERVATION", "voice.lexicon",
                   claim_text="subject uses clipped sentences"),
        ]),
    }


def _call(role_ids=("R1", "R2", "R4"), *, provider=None, run_id=RUN_ID,
          snapshot=SNAPSHOT, evidence=None, audit_policy=None, compile_context=None,
          evidence_payloads=None):
    evidence = evidence if evidence is not None else _evidence()
    registry, profiles, tasks = _build_scope(role_ids, evidence, run_id=run_id, snapshot=snapshot)
    return run_reconstruction(
        subject_id=SUBJECT,
        run_id=run_id,
        evidence_snapshot_id=snapshot,
        evidence=evidence,
        registry=registry,
        profiles=profiles,
        role_tasks=tasks,
        provider_callable=provider,
        compile_context=compile_context or make_compile_context(subject_id=SUBJECT, package_id=PKG_ID),
        audit_policy=audit_policy or AuditPolicy(),
        evidence_payloads=evidence_payloads if evidence_payloads is not None else make_payload_map("se-001"),
    )


# ---------------------------------------------------------------------------
# T1 .. T12 + additional contract tests
# ---------------------------------------------------------------------------

class TestOrchestratorHappyPath:
    def test_t1_happy_path_broad_core_e2e(self):
        provider, calls, r8_calls = _dispatch_provider(
            _happy_role_payloads(), _r8_judgment_json(),
        )
        result = _call(provider=provider)

        package, audit, validation, role_results = result
        # Return tuple of exactly the four existing contract types.
        assert isinstance(package, CandidateCharacterPackage)
        assert isinstance(audit, ReconstructionAudit)
        assert isinstance(validation, ValidationReport)
        assert isinstance(role_results, tuple) and all(
            isinstance(r, RoleResult) for r in role_results
        )

        # Broad-core families reached their candidate buckets (R7-compatible).
        assert package.identity_biography_candidate != {}
        assert package.behavior_candidate != {}
        assert package.voice_candidate != {}

        # R7 valid, R8 composed to PASS.
        assert validation.valid is True
        assert audit.verdict is AuditVerdict.PASS

        # Exactly three role calls + one R8 semantic call.
        assert calls["count"] == 4
        assert r8_calls["count"] == 1

        # Deterministic caller ordering preserved in the result tuple.
        assert [r.role_id for r in role_results] == ["R1", "R2", "R4"]

    def test_compile_validate_r8_called_once(self, monkeypatch):
        counts = {"compile": 0, "validate": 0, "r8": 0}
        real_compile = orch.compile_candidate_package
        real_validate = orch.validate_package
        real_r8 = orch.run_r8_analysis

        def c_compile(*a, **k):
            counts["compile"] += 1
            return real_compile(*a, **k)

        def c_validate(*a, **k):
            counts["validate"] += 1
            return real_validate(*a, **k)

        def c_r8(*a, **k):
            counts["r8"] += 1
            return real_r8(*a, **k)

        monkeypatch.setattr(orch, "compile_candidate_package", c_compile)
        monkeypatch.setattr(orch, "validate_package", c_validate)
        monkeypatch.setattr(orch, "run_r8_analysis", c_r8)

        provider, _, _ = _dispatch_provider(_happy_role_payloads(), _r8_judgment_json())
        _call(provider=provider)

        assert counts == {"compile": 1, "validate": 1, "r8": 1}


class TestOrchestratorFailClosed:
    def test_t2_role_identity_mismatch_fail_closed(self, monkeypatch):
        # Registry version pin v2 vs task role_version v1 -> executor fails
        # before any provider call; pipeline stops; R6/R7/R8 not reached.
        evidence = _evidence()
        registry, profiles, _tasks = _build_scope(("R1",), evidence)
        # Override the registry entry version to v2 (registry truth mismatch).
        registry = RoleRegistry((
            make_registry_entry(role_id="R1", version="v2", prompt_ref=_PROMPT_REFS["R1"]),
        ))
        task = make_role_task(
            task_id="task-r1", role_id="R1", role_version="v1",
            allowed_evidence_ids=("se-001",), run_id=RUN_ID,
            evidence_snapshot_id=SNAPSHOT, subject_id=SUBJECT,
        )

        reached = {"compile": False, "r8": False}
        monkeypatch.setattr(orch, "compile_candidate_package",
                            lambda *a, **k: reached.__setitem__("compile", True))

        def failing_provider(messages):
            raise AssertionError("provider must not be reached")

        with pytest.raises(ExecutorError):
            run_reconstruction(
                subject_id=SUBJECT,
                run_id=RUN_ID,
                evidence_snapshot_id=SNAPSHOT,
                evidence=evidence,
                registry=registry,
                profiles=profiles,
                role_tasks=(task,),
                provider_callable=failing_provider,
                compile_context=make_compile_context(subject_id=SUBJECT, package_id=PKG_ID),
                audit_policy=AuditPolicy(),
                evidence_payloads=make_payload_map("se-001"),
            )
        assert reached["compile"] is False

    def test_t7_provider_failure_no_retry(self):
        calls = {"count": 0}

        def failing_provider(messages):
            calls["count"] += 1
            raise ExecutorError("provider failure (synthetic)")

        with pytest.raises(ExecutorError):
            _call(provider=failing_provider)

        assert calls["count"] == 1  # single attempt, no retry/fallback

    def test_t10_invalid_r7_stops_before_r8(self, monkeypatch):
        provider, _, _ = _dispatch_provider(_happy_role_payloads(), _r8_judgment_json())

        invalid = ValidationReport(
            valid=False,
            findings=(),
        )
        monkeypatch.setattr(orch, "validate_package", lambda *a, **k: invalid)
        r8_called = {"value": False}

        def r8_guard(*a, **k):
            r8_called["value"] = True
            raise AssertionError("R8 must not be reached")

        monkeypatch.setattr(orch, "run_r8_analysis", r8_guard)

        with pytest.raises(CrpValidationError):
            _call(provider=provider)

        assert r8_called["value"] is False

    def test_empty_role_tasks_fail_closed(self):
        evidence = _evidence()
        registry, profiles, _tasks = _build_scope(("R1",), evidence)
        with pytest.raises(CrpValidationError):
            run_reconstruction(
                subject_id=SUBJECT,
                run_id=RUN_ID,
                evidence_snapshot_id=SNAPSHOT,
                evidence=evidence,
                registry=registry,
                profiles=profiles,
                role_tasks=(),
                provider_callable=lambda msgs: "{}",
                compile_context=make_compile_context(subject_id=SUBJECT, package_id=PKG_ID),
                audit_policy=AuditPolicy(),
                evidence_payloads=make_payload_map("se-001"),
            )

    def test_inactive_role_not_bypassed(self):
        evidence = _evidence()
        registry = RoleRegistry((
            make_registry_entry(role_id="R2", version="v1", status=RoleStatus.INACTIVE),
        ))
        profiles = {"profile-r2": make_knowledge_profile(profile_id="profile-r2", role_id="R2")}
        task = make_role_task(
            task_id="task-r2", role_id="R2", role_version="v1",
            allowed_evidence_ids=("se-001",), run_id=RUN_ID,
            evidence_snapshot_id=SNAPSHOT, subject_id=SUBJECT,
        )
        with pytest.raises(ExecutorError):
            run_reconstruction(
                subject_id=SUBJECT,
                run_id=RUN_ID,
                evidence_snapshot_id=SNAPSHOT,
                evidence=evidence,
                registry=registry,
                profiles=profiles,
                role_tasks=(task,),
                provider_callable=lambda msgs: "{}",
                compile_context=make_compile_context(subject_id=SUBJECT, package_id=PKG_ID),
                audit_policy=AuditPolicy(),
                evidence_payloads=make_payload_map("se-001"),
            )


class TestUnknownAndContradiction:
    def test_t3_unknown_preserved(self):
        r1_payload = _role_result_json("task-r1", "R1", [
            _claim("r1-gap-1", "R1", "UNKNOWN", "identity_biography.birthplace",
                   evidence_ids=(), confidence="UNKNOWN",
                   claim_text="missing evidence for birthplace"),
        ])
        provider, _, r8_calls = _dispatch_provider({"R1": r1_payload}, _r8_judgment_json())
        package, audit, validation, role_results = _call(role_ids=("R1",), provider=provider)

        assert package.unknowns != ()
        assert any(c.claim_id == "r1-gap-1" and c.claim_type.value == "UNKNOWN"
                   for c in package.unknowns)
        assert package.identity_biography_candidate == {}
        assert validation.valid is True
        assert audit.verdict is AuditVerdict.PASS
        assert r8_calls["count"] == 1

    def test_t4_contradiction_preserved(self):
        # A single role emits two conflicting claims + one ContradictionRecord.
        contradiction = {
            "contradiction_id": "crd-1",
            "subject_id": SUBJECT,
            "claim_ids": ["c-a", "c-b"],
            "source_evidence_ids": ["se-001", "se-001"],
            "description": "source conflict",
            "severity": "MATERIAL",
            "resolution_status": "OPEN",
            "requires_human": False,
            "created_by": "R2",
        }
        r2_payload = _role_result_json("task-r2", "R2", [
            _claim("c-a", "R2", "HYPOTHESIS", "behavior.conflict_style",
                   confidence="POSSIBLE", claim_text="prefers solitude"),
            _claim("c-b", "R2", "HYPOTHESIS", "behavior.conflict_style",
                   confidence="POSSIBLE", claim_text="prefers company"),
        ], contradictions=[contradiction])
        provider, _, r8_calls = _dispatch_provider({"R2": r2_payload}, _r8_judgment_json())
        package, audit, validation, role_results = _call(role_ids=("R2",), provider=provider)

        assert package.contradictions != ()
        record = package.contradictions[0]
        assert set(record.claim_ids) == {"c-a", "c-b"}
        assert record.resolution_status.value == "OPEN"
        # Both conflicting claims still present in the package.
        assert {c.claim_id for c in package.claims} == {"c-a", "c-b"}
        assert validation.valid is True
        assert r8_calls["count"] == 1


class TestR8HardBlocker:
    def test_t5_deterministic_hard_blocker_skips_semantic_provider(self):
        # Evidence whose content_ref matches the audit-policy forbidden pattern
        # trips R8 leakage (hard gate) WITHOUT tripping the role executor (the
        # role KnowledgeProfile forbids nothing). R8 semantic provider must NOT
        # be invoked.
        evidence = _evidence(content_ref="personas/kira/notes.md")
        policy = AuditPolicy(forbidden_refs=("personas/kira/**",))

        r1_payload = _role_result_json("task-r1", "R1", [
            _claim("c-ident", "R1", "FACT", "identity_biography.birthplace"),
        ])
        provider, calls, r8_calls = _dispatch_provider(
            {"R1": r1_payload},
            None,
            on_r8=lambda: (_ for _ in ()).throw(
                AssertionError("R8 semantic provider must not be reached after hard blocker")),
        )

        package, audit, validation, role_results = _call(
            role_ids=("R1",), provider=provider, evidence=evidence,
            audit_policy=policy,
        )

        assert audit.verdict is AuditVerdict.BLOCKED
        assert r8_calls["count"] == 0
        assert calls["count"] == 1  # only the single role call


class TestR8Semantic:
    def test_t6_r8_semantic_composition(self):
        provider, _, r8_calls = _dispatch_provider(
            _happy_role_payloads(), _r8_judgment_json(),
        )
        package, audit, validation, role_results = _call(provider=provider)

        assert audit.verdict is AuditVerdict.PASS
        semantic_ids = {
            "R8_ROLE_BOUNDARY_SEMANTIC",
            "R8_MODULE_PLACEMENT",
            "R8_UNKNOWN_COVERAGE",
        }
        present_ids = {c.check for c in audit.checks}
        assert semantic_ids <= present_ids
        assert r8_calls["count"] == 1


class TestLifecycleAndBoundaries:
    def test_t8_pre_acceptance_only(self):
        provider, _, _ = _dispatch_provider(_happy_role_payloads(), _r8_judgment_json())
        package, _, _, _ = _call(provider=provider)
        assert package.status is PackageStatus.DRAFT
        assert package.status not in (PackageStatus.HUMAN_APPROVED, PackageStatus.REJECTED)

    def test_t9_runtime_boundary(self):
        src = Path("services/crp_authoring/orchestrator.py")
        tree = ast.parse(src.read_text(encoding="utf-8"))
        mods = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods.extend(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                mods.append(node.module or "")
        forbidden_substrings = ("runtime", "cis", "state", "persona", "stem")
        for m in mods:
            lower = m.lower()
            assert not any(sub in lower for sub in forbidden_substrings), f"runtime import {m}"

    def test_t11_no_smoke_runner_dependency(self):
        text = Path("services/crp_authoring/orchestrator.py").read_text(encoding="utf-8")
        assert "crp_r8_smoke_runner" not in text
        assert "tools." not in text

    def test_t12_no_kira_hidden_eval_leakage(self):
        text = Path("services/crp_authoring/orchestrator.py").read_text(encoding="utf-8")
        for forbidden in ("kira", "benchmark", "hidden_eval", "accepted_benchmark"):
            assert forbidden not in text


class TestOrchestratorNoneFailClosed:
    """MAT-02: evidence_payloads is required for run_reconstruction."""

    def test_orch_none_01_omitted_argument_fails_before_provider(self):
        evidence = _evidence()
        registry, profiles, tasks = _build_scope(("R1",), evidence)
        calls = []

        def counted(messages):
            calls.append(messages)
            return _r8_judgment_json()

        with pytest.raises(TypeError):
            run_reconstruction(
                subject_id=SUBJECT,
                run_id=RUN_ID,
                evidence_snapshot_id=SNAPSHOT,
                evidence=evidence,
                registry=registry,
                profiles=profiles,
                role_tasks=tasks,
                provider_callable=counted,
                compile_context=make_compile_context(subject_id=SUBJECT, package_id=PKG_ID),
                audit_policy=AuditPolicy(),
            )
        assert len(calls) == 0

    def test_orch_none_02_explicit_none_fails_before_provider(self):
        evidence = _evidence()
        registry, profiles, tasks = _build_scope(("R1",), evidence)
        calls = []

        def counted(messages):
            calls.append(messages)
            return _r8_judgment_json()

        with pytest.raises(ExecutorError):
            run_reconstruction(
                subject_id=SUBJECT,
                run_id=RUN_ID,
                evidence_snapshot_id=SNAPSHOT,
                evidence=evidence,
                registry=registry,
                profiles=profiles,
                role_tasks=tasks,
                provider_callable=counted,
                compile_context=make_compile_context(subject_id=SUBJECT, package_id=PKG_ID),
                audit_policy=AuditPolicy(),
                evidence_payloads=None,
            )
        assert len(calls) == 0


class TestOrchestratorSubstantiveMaterialization:
    """CRP R4 pre-provider correction: evidence + evidence_payloads flow through
    run_reconstruction to every provider-bound authoring role and to R8, without
    filesystem lookup (synthetic payloads only)."""

    SENTINEL = "OWNER_FACT_SENTINEL_9F3B7"

    def _scope(self):
        facts = [{"fact": self.SENTINEL, "detail": "owner-authored substantive"}]
        content_hash = canonical_json_sha256(facts)
        evidence = (
            make_source(
                source_id="se-001", source_type=SourceType.OWNER_DIRECT,
                subject_id=SUBJECT, evidence_snapshot_id=SNAPSHOT,
                content_ref="ref://raw/001", content_hash=content_hash,
            ),
        )
        payloads = {"se-001": {"section_id": "s1", "title": "t", "facts": facts}}
        registry, profiles, tasks = _build_scope(("R1", "R2", "R4"), evidence)
        return evidence, payloads, registry, profiles, tasks

    def _capturing_provider(self):
        seen = {"roles": [], "r8": None}

        def provider(messages):
            user_content = "".join(
                m["content"] for m in messages if m.get("role") == "user"
            )
            if "AUDIT_IDENTITY" in user_content:
                seen["r8"] = user_content
                return _r8_judgment_json()
            seen["roles"].append(user_content)
            for role_id, payload in _happy_role_payloads().items():
                if f"- role_id: {role_id}" in user_content:
                    return payload
            raise AssertionError("unrecognized provider call")

        return provider, seen

    def test_substantive_facts_reach_roles_and_r8(self):
        evidence, payloads, registry, profiles, tasks = self._scope()
        provider, seen = self._capturing_provider()

        run_reconstruction(
            subject_id=SUBJECT,
            run_id=RUN_ID,
            evidence_snapshot_id=SNAPSHOT,
            evidence=evidence,
            registry=registry,
            profiles=profiles,
            role_tasks=tasks,
            provider_callable=provider,
            compile_context=make_compile_context(subject_id=SUBJECT, package_id=PKG_ID),
            audit_policy=AuditPolicy(),
            evidence_payloads=payloads,
        )

        # Each provider-bound authoring role received the substantive sentinel.
        assert len(seen["roles"]) == 3
        for user_content in seen["roles"]:
            assert self.SENTINEL in user_content
            assert "substantive_payload" in user_content
        # R8 also received the substantive sentinel.
        assert self.SENTINEL in seen["r8"]
        assert "substantive_payload" in seen["r8"]


class TestOrderingAndNoNewSchema:
    def test_prior_results_forwarded_in_order(self):
        # R2 allowed_prior_results references R1's task; executor resolves and
        # verifies it, proving prior_results are forwarded in execution order.
        evidence = _evidence()
        registry = RoleRegistry(tuple(
            make_registry_entry(role_id=r, version="v1", prompt_ref=_PROMPT_REFS[r])
            for r in ("R1", "R2")
        ))
        profiles = {
            f"profile-{r.lower()}": make_knowledge_profile(
                profile_id=f"profile-{r.lower()}", role_id=r,
            )
            for r in ("R1", "R2")
        }
        r1_task = make_role_task(
            task_id="task-r1", role_id="R1", role_version="v1",
            allowed_evidence_ids=("se-001",), run_id=RUN_ID,
            evidence_snapshot_id=SNAPSHOT, subject_id=SUBJECT,
        )
        r2_task = make_role_task(
            task_id="task-r2", role_id="R2", role_version="v1",
            allowed_evidence_ids=("se-001",), allowed_prior_results=("task-r1",),
            run_id=RUN_ID, evidence_snapshot_id=SNAPSHOT, subject_id=SUBJECT,
        )
        payloads = {
            "R1": _role_result_json("task-r1", "R1", [
                _claim("c-ident", "R1", "FACT", "identity_biography.birthplace"),
            ]),
            "R2": _role_result_json("task-r2", "R2", [
                _claim("c-behav", "R2", "HYPOTHESIS", "behavior.conflict_style",
                       confidence="POSSIBLE"),
            ]),
        }
        provider, _, r8_calls = _dispatch_provider(payloads, _r8_judgment_json())
        result = run_reconstruction(
            subject_id=SUBJECT,
            run_id=RUN_ID,
            evidence_snapshot_id=SNAPSHOT,
            evidence=evidence,
            registry=registry,
            profiles=profiles,
            role_tasks=(r1_task, r2_task),
            provider_callable=provider,
            compile_context=make_compile_context(subject_id=SUBJECT, package_id=PKG_ID),
            audit_policy=AuditPolicy(),
            evidence_payloads=make_payload_map("se-001"),
        )
        assert [r.role_id for r in result[3]] == ["R1", "R2"]
        assert r8_calls["count"] == 1

    def test_no_new_result_schema(self):
        provider, _, _ = _dispatch_provider(_happy_role_payloads(), _r8_judgment_json())
        result = _call(provider=provider)
        assert isinstance(result, tuple) and len(result) == 4
        package, audit, validation, role_results = result
        assert isinstance(package, CandidateCharacterPackage)
        assert isinstance(audit, ReconstructionAudit)
        assert isinstance(validation, ValidationReport)
        assert isinstance(role_results, tuple)

    def test_r3_r5_not_auto_run(self):
        provider, _, _ = _dispatch_provider(_happy_role_payloads(), _r8_judgment_json())
        package, _, _, role_results = _call(provider=provider)
        assert [r.role_id for r in role_results] == ["R1", "R2", "R4"]
        assert package.intimacy_candidate == {}  # R3 never ran
        # R5 produces nothing here (not part of the role set).
        assert all(r.role_id != "R5" for r in role_results)