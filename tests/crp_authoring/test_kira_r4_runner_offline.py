#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CRP R4 -- canonical Kira runner tests (fake providers only, fully OFFLINE).

Zero network, zero provider construction, zero credential read. Uses the real
A-only Kira A_AUTHORING projection (via the established ``load_a_projection``
loader) but only injected fake provider callables -- ``--live`` and the real
``build_provider_callable`` are never exercised against a live provider.

Deliberately does NOT import/open Hidden-B, Legacy-C, or any
``personas/kira/**`` content, and does NOT run
``tests/crp_authoring/test_dataset_freeze.py``. Leakage assertions use only
the technical forbidden-ref path tokens already exposed by the manifest's
public ``knowledge_policy`` control-plane field (never substantive B/C text).
"""

from __future__ import annotations

import dataclasses
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_TOOLS_DIR = os.path.join(_PROJECT_ROOT, "tools")
for _p in (_PROJECT_ROOT, _TOOLS_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import crp_kira_r4_runner as runner  # noqa: E402
import crp_provider_adapter  # noqa: E402  (patched transport boundary only; no network)

from services.crp_authoring import (  # noqa: E402
    ClaimStatus,
    ClaimType,
    Confidence,
    CrpError,
    CrpValidationError,
    ExecutorError,
    RoleClaim,
    RoleResult,
    SourceType,
    compute_package_hash,
)
from services.crp_authoring.candidate_package import CandidateCharacterPackage, PackageStatus  # noqa: E402
from services.crp_authoring.reconstruction_audit import AuditVerdict, ReconstructionAudit  # noqa: E402
from services.crp_authoring.validator import ValidationReport  # noqa: E402
# Reused verbatim (not reimplemented) so the evidence-exactness assertions
# below compare against the SAME canonical rendering production uses.
from services.crp_authoring.executor import _render_payload as _prod_render_payload  # noqa: E402


# Forbidden-ref tokens -- technical path literals only, sourced from the
# manifest's public knowledge_policy field (never Hidden-B/C substantive
# content). Safe, contamination-boundary-compliant leakage sentinels.
_FORBIDDEN_TOKENS = (
    "B_HIDDEN_EVALUATION",
    "C_LEGACY_BENCHMARK",
    "SCENARIOS.json",
    "OWNER_REFERENCE_ANSWERS.json",
    "LEGACY_REFERENCES.json",
    "personas/kira",
    "personas\\kira",
    "KIRA_MODULE_v15",
)


@pytest.fixture(scope="module")
def plan():
    return runner.build_kira_r4_plan()


# ---------------------------------------------------------------------------
# Fake provider payloads
# ---------------------------------------------------------------------------

def _claim(claim_id, role_id, claim_type, target, evidence_id, *,
           confidence="POSSIBLE", claim_text="synthetic offline test claim"):
    # ``evidence_id`` may be a single id (str) or an iterable of ids (a merged /
    # corroborated claim citing the union of every supporting source).
    ids = (
        [evidence_id] if isinstance(evidence_id, str)
        else list(evidence_id)
    )
    return {
        "claim_id": claim_id,
        "subject_id": "kira",
        "role_id": role_id,
        "claim": claim_text,
        "claim_type": claim_type,
        "source_evidence_ids": ids,
        "source_type_summary": ["OWNER_DIRECT"],
        "confidence": confidence,
        "rationale_summary": "synthetic offline R4 runner test",
        "status": "PROPOSED",
        "target_module_or_layer": target,
    }


def _role_result_json(task_id, role_id, role_version, claims, *, provenance_summary=None):
    # ``provenance_summary`` defaults to the v2-style ``used_evidence`` mirror
    # (unchanged for R2/R3/R4/R8). R1 v3 callers pass an explicit
    # ``{"sources_used": [...]}`` object so the executor's R1-v3 gate can check
    # it against the claim-level evidence union.
    if provenance_summary is None:
        provenance_summary = {"used_evidence": [c["source_evidence_ids"][0] for c in claims]}
    return json.dumps({
        "task_id": task_id,
        "role_id": role_id,
        "role_version": role_version,
        "completion_status": "COMPLETE",
        "claims": claims,
        "unknowns": [],
        "contradictions": [],
        "provenance_summary": provenance_summary,
        "requests_for_more_evidence": [],
        "warnings": [],
        "questions_for_r1": [],
        "new_source_evidence": [],
    }, ensure_ascii=False)


def _r1_task(plan_):
    return next(t for t in plan_.role_tasks if t.role_id == "R1")


def _r1_v3_full_coverage_json(plan_, *, claim_text=None, provenance_ids=None):
    """A gate-passing R1 v3 payload: one self-contained, corroboration-merged
    claim whose ``source_evidence_ids`` is the full union of the task's
    ``allowed_evidence_ids``, with ``provenance_summary.sources_used`` mirroring
    that union exactly. ``provenance_ids`` overrides only the summary (used by
    the negative gate tests)."""
    r1 = _r1_task(plan_)
    all_ids = list(r1.allowed_evidence_ids)
    claim = _claim(
        "c-r1", "R1", "FACT", "identity_biography.birthplace", all_ids,
        confidence="KNOWN",
        claim_text=claim_text or (
            "Kira's core identity facts are corroborated across the full "
            "authorized A evidence set."
        ),
    )
    summary_ids = all_ids if provenance_ids is None else list(provenance_ids)
    return _role_result_json(
        r1.task_id, "R1", "v3", [claim],
        provenance_summary={"sources_used": summary_ids},
    )


def _r8_judgment_json(package_id, subject_id="kira"):
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


def _happy_payloads(plan_):
    ev_id = plan_.projection.evidence[0].source_id
    task_ids = {t.role_id: t.task_id for t in plan_.role_tasks}
    return {
        "R1": _r1_v3_full_coverage_json(plan_),
        "R2": _role_result_json(task_ids["R2"], "R2", "v2", [
            _claim("c-r2", "R2", "HYPOTHESIS", "behavior.conflict_style", ev_id),
        ]),
        "R3": _role_result_json(task_ids["R3"], "R3", "v1", [
            _claim("c-r3", "R3", "OBSERVATION", "intimacy.communication_style", ev_id),
        ]),
        "R4": _role_result_json(task_ids["R4"], "R4", "v1", [
            _claim("c-r4", "R4", "OBSERVATION", "voice.lexicon", ev_id),
        ]),
    }


def _dispatch_provider(role_payloads, r8_json, *, seen=None):
    calls = {"count": 0}
    r8_calls = {"count": 0}

    def provider(messages):
        calls["count"] += 1
        user_content = "".join(m["content"] for m in messages if m.get("role") == "user")
        if seen is not None:
            seen.append(user_content)
        if "AUDIT_IDENTITY" in user_content:
            r8_calls["count"] += 1
            return r8_json
        for role_id, payload in role_payloads.items():
            if f"- role_id: {role_id}" in user_content:
                return payload
        raise AssertionError("provider received an unrecognized call")

    return provider, calls, r8_calls


# ---------------------------------------------------------------------------
# 1-7: plan shape (order, versions, R3 authorization, identity, evidence,
# prior-result exposure)
# ---------------------------------------------------------------------------

class TestPlanShape:
    def test_role_order(self, plan):
        assert [t.role_id for t in plan.role_tasks] == ["R1", "R2", "R3", "R4"]

    def test_role_versions(self, plan):
        assert {t.role_id: t.role_version for t in plan.role_tasks} == {
            "R1": "v3", "R2": "v2", "R3": "v1", "R4": "v1",
        }

    def test_r3_activation_authorization_ref(self, plan):
        r3 = next(t for t in plan.role_tasks if t.role_id == "R3")
        assert r3.activation_authorization_ref == "CRP-OD-R4-KIRA-R3-01"

    def test_r1_r2_r4_have_no_invented_authorization(self, plan):
        for role_id in ("R1", "R2", "R4"):
            task = next(t for t in plan.role_tasks if t.role_id == role_id)
            assert task.activation_authorization_ref is None

    def test_shared_subject_run_snapshot_identity(self, plan):
        subjects = {t.subject_id for t in plan.role_tasks}
        run_ids = {t.run_id for t in plan.role_tasks}
        snapshots = {t.evidence_snapshot_id for t in plan.role_tasks}
        assert subjects == {plan.projection.subject_id}
        assert run_ids == {plan.run_id}
        assert snapshots == {plan.projection.evidence_snapshot_id}

    def test_allowed_evidence_ids_from_a_projection_only(self, plan):
        expected = tuple(ev.source_id for ev in plan.projection.evidence)
        assert expected  # real Kira A evidence is non-empty
        for task in plan.role_tasks:
            assert task.allowed_evidence_ids == expected

    def test_no_prior_result_exposure(self, plan):
        for task in plan.role_tasks:
            assert task.allowed_prior_results == ()

    def test_registry_resolves_all_four_exact_versions(self, plan):
        for role_id, version in runner.ROLE_VERSIONS.items():
            entry = plan.registry.resolve(role_id, version)
            assert entry.role_id == role_id
            assert entry.version == version


# ---------------------------------------------------------------------------
# 8-13: full pre-provider plan validation fails closed
# ---------------------------------------------------------------------------

class TestPreProviderPlanValidationFailsClosed:
    def _validate(self, plan, role_tasks):
        allowed_evidence_ids = tuple(ev.source_id for ev in plan.projection.evidence)
        runner.validate_role_plan(
            role_tasks, plan.registry,
            subject_id=plan.projection.subject_id, run_id=plan.run_id,
            evidence_snapshot_id=plan.projection.evidence_snapshot_id,
            allowed_evidence_ids=allowed_evidence_ids,
        )

    def test_missing_role_fails(self, plan):
        r1, r2, r3, r4 = plan.role_tasks
        with pytest.raises(CrpValidationError):
            self._validate(plan, (r1, r2, r4))

    def test_duplicate_role_fails(self, plan):
        r1, r2, r3, r4 = plan.role_tasks
        with pytest.raises(CrpValidationError):
            self._validate(plan, (r1, r1, r3, r4))

    def test_extra_role_fails(self, plan):
        r1, r2, r3, r4 = plan.role_tasks
        extra = dataclasses.replace(r1, task_id="extra-task")
        with pytest.raises(CrpValidationError):
            self._validate(plan, (r1, r2, r3, r4, extra))

    def test_wrong_order_fails(self, plan):
        r1, r2, r3, r4 = plan.role_tasks
        with pytest.raises(CrpValidationError):
            self._validate(plan, (r1, r3, r2, r4))

    def test_wrong_version_fails(self, plan):
        r1, r2, r3, r4 = plan.role_tasks
        bad_r4 = dataclasses.replace(r4, role_version="v2")
        with pytest.raises(CrpValidationError):
            self._validate(plan, (r1, r2, r3, bad_r4))

    def test_invalid_r3_authorization_fails(self, plan):
        r1, r2, r3, r4 = plan.role_tasks
        bad_r3 = dataclasses.replace(r3, activation_authorization_ref="WRONG-REF-NOT-CANONICAL")
        with pytest.raises(CrpValidationError):
            self._validate(plan, (r1, r2, bad_r3, r4))

    def test_invented_authorization_on_non_gated_role_fails(self, plan):
        r1, r2, r3, r4 = plan.role_tasks
        bad_r1 = dataclasses.replace(r1, activation_authorization_ref="SOME-INVENTED-REF")
        with pytest.raises(CrpValidationError):
            self._validate(plan, (bad_r1, r2, r3, r4))

    def test_subject_mismatch_fails(self, plan):
        r1, r2, r3, r4 = plan.role_tasks
        bad_r2 = dataclasses.replace(r2, subject_id="not-kira")
        with pytest.raises(CrpValidationError):
            self._validate(plan, (r1, bad_r2, r3, r4))

    def test_run_mismatch_fails(self, plan):
        r1, r2, r3, r4 = plan.role_tasks
        bad_r3 = dataclasses.replace(r3, run_id="a-different-run")
        with pytest.raises(CrpValidationError):
            self._validate(plan, (r1, r2, bad_r3, r4))

    def test_evidence_snapshot_mismatch_fails(self, plan):
        r1, r2, r3, r4 = plan.role_tasks
        bad_r4 = dataclasses.replace(r4, evidence_snapshot_id="a-different-snapshot")
        with pytest.raises(CrpValidationError):
            self._validate(plan, (r1, r2, r3, bad_r4))

    def test_wrong_r4_version_caught_before_any_provider_call(self, plan, monkeypatch):
        """Detect a bad R4 version BEFORE spending calls on R1/R2/R3."""
        r1, r2, r3, r4 = plan.role_tasks
        bad_r4 = dataclasses.replace(r4, role_version="v2")
        poisoned = dataclasses.replace(plan, role_tasks=(r1, r2, r3, bad_r4))

        def never_called(messages):
            raise AssertionError("provider must not be reached: plan validation must fail first")

        with pytest.raises(CrpValidationError):
            runner.execute_kira_r4_reconstruction(never_called, poisoned)


# ---------------------------------------------------------------------------
# Execution-boundary fail-closed tests: every malformed COMPLETE plan is
# driven through execute_kira_r4_reconstruction (not just validate_role_plan
# directly), proving zero provider calls were made -- the real boundary a
# future --live run would rely on.
# ---------------------------------------------------------------------------

def _counting_provider(response="{}"):
    calls = {"count": 0}

    def provider(messages):
        calls["count"] += 1
        return response

    return provider, calls


def _missing_r1(r1, r2, r3, r4):
    return (r2, r3, r4)


def _missing_r2(r1, r2, r3, r4):
    return (r1, r3, r4)


def _missing_r3(r1, r2, r3, r4):
    return (r1, r2, r4)


def _missing_r4(r1, r2, r3, r4):
    return (r1, r2, r3)


def _duplicate_role(r1, r2, r3, r4):
    return (r1, r1, r3, r4)


def _extra_role(r1, r2, r3, r4):
    return (r1, r2, r3, r4, dataclasses.replace(r1, task_id="extra-task"))


def _wrong_order(r1, r2, r3, r4):
    return (r1, r3, r2, r4)


def _wrong_version(r1, r2, r3, r4):
    return (r1, r2, r3, dataclasses.replace(r4, role_version="v2"))


def _subject_mismatch(r1, r2, r3, r4):
    return (r1, dataclasses.replace(r2, subject_id="not-kira"), r3, r4)


def _run_mismatch(r1, r2, r3, r4):
    return (r1, r2, dataclasses.replace(r3, run_id="a-different-run"), r4)


def _evidence_snapshot_mismatch(r1, r2, r3, r4):
    return (r1, r2, r3, dataclasses.replace(r4, evidence_snapshot_id="a-different-snapshot"))


def _incorrect_r3_authorization(r1, r2, r3, r4):
    return (r1, r2, dataclasses.replace(r3, activation_authorization_ref="WRONG-REF-NOT-CANONICAL"), r4)


_MALFORMED_PLAN_MUTATORS = {
    "missing_r1": _missing_r1,
    "missing_r2": _missing_r2,
    "missing_r3": _missing_r3,
    "missing_r4": _missing_r4,
    "duplicate_role": _duplicate_role,
    "extra_role": _extra_role,
    "wrong_order": _wrong_order,
    "wrong_version": _wrong_version,
    "subject_mismatch": _subject_mismatch,
    "run_mismatch": _run_mismatch,
    "evidence_snapshot_mismatch": _evidence_snapshot_mismatch,
    "incorrect_r3_authorization": _incorrect_r3_authorization,
}


class TestExecutionBoundaryFailClosed:
    @pytest.mark.parametrize("case_id", list(_MALFORMED_PLAN_MUTATORS))
    def test_malformed_plan_fails_before_provider_call(self, plan, case_id):
        mutator = _MALFORMED_PLAN_MUTATORS[case_id]
        r1, r2, r3, r4 = plan.role_tasks
        poisoned = dataclasses.replace(plan, role_tasks=mutator(r1, r2, r3, r4))

        provider, calls = _counting_provider()
        with pytest.raises(CrpValidationError):
            runner.execute_kira_r4_reconstruction(provider, poisoned)
        assert calls["count"] == 0, f"{case_id}: provider was reached before validation failed"

    def test_missing_r3_authorization_fails_at_construction_before_any_call(self, plan):
        """A genuinely empty R3 activation_authorization_ref fails even
        earlier, at RoleTask construction -- stronger than an execution-time
        rejection. No provider is ever constructed or invoked in this path."""
        r1, r2, r3, r4 = plan.role_tasks
        provider, calls = _counting_provider()

        with pytest.raises(CrpValidationError):
            dataclasses.replace(r3, activation_authorization_ref=None)

        assert calls["count"] == 0


# ---------------------------------------------------------------------------
# Counting guard: max 5, no retry, no fallback, 6th attempt blocked
# ---------------------------------------------------------------------------

class TestCountingGuard:
    def test_allows_up_to_budget(self):
        calls = {"count": 0}

        def stub(messages):
            calls["count"] += 1
            return "ok"

        guard = runner.CountingGuard(stub, max_calls=5)
        for _ in range(5):
            assert guard(["m"]) == "ok"
        assert guard.attempts == 5
        assert calls["count"] == 5

    def test_sixth_attempt_blocked_before_wrapped_provider(self):
        calls = {"count": 0}

        def stub(messages):
            calls["count"] += 1
            return "ok"

        guard = runner.CountingGuard(stub, max_calls=5)
        for _ in range(5):
            guard(["m"])
        with pytest.raises(CrpValidationError):
            guard(["m"])
        assert calls["count"] == 5  # the wrapped provider was never reached a 6th time
        assert guard.attempts == 5

    def test_default_budget_is_five(self):
        guard = runner.CountingGuard(lambda messages: "ok")
        assert guard.max_calls == runner.PROVIDER_CALL_BUDGET == 5

    def test_no_retry_on_wrapped_failure(self):
        calls = {"count": 0}

        def failing(messages):
            calls["count"] += 1
            raise RuntimeError("synthetic provider failure")

        guard = runner.CountingGuard(failing)
        with pytest.raises(RuntimeError):
            guard(["m"])
        assert calls["count"] == 1
        assert guard.attempts == 1  # failure still consumed the attempt; no auto-retry


# ---------------------------------------------------------------------------
# Full offline happy path
# ---------------------------------------------------------------------------

class TestFullOfflineHappyPath:
    def test_exactly_four_role_calls_plus_at_most_one_r8_call(self, plan):
        provider, calls, r8_calls = _dispatch_provider(
            _happy_payloads(plan), _r8_judgment_json(plan.compile_context.package_id),
        )
        result = runner.execute_kira_r4_reconstruction(provider, plan)

        assert len(result.role_results) == 4
        assert [r.role_id for r in result.role_results] == ["R1", "R2", "R3", "R4"]
        assert r8_calls["count"] <= 1
        assert calls["count"] == 5  # 4 authoring roles + exactly one R8 call
        assert result.provider_attempts == 5
        assert result.provider_attempts <= result.provider_call_budget == 5

    def test_run_reconstruction_invoked_exactly_once(self, plan, monkeypatch):
        counts = {"n": 0}
        real = runner.run_reconstruction

        def counted(*a, **k):
            counts["n"] += 1
            return real(*a, **k)

        monkeypatch.setattr(runner, "run_reconstruction", counted)
        provider, _, _ = _dispatch_provider(
            _happy_payloads(plan), _r8_judgment_json(plan.compile_context.package_id),
        )
        runner.execute_kira_r4_reconstruction(provider, plan)
        assert counts["n"] == 1

    def test_package_stays_draft_pre_acceptance(self, plan):
        provider, _, _ = _dispatch_provider(
            _happy_payloads(plan), _r8_judgment_json(plan.compile_context.package_id),
        )
        result = runner.execute_kira_r4_reconstruction(provider, plan)
        assert result.package.status is PackageStatus.DRAFT
        assert result.package.status not in (PackageStatus.HUMAN_APPROVED, PackageStatus.REJECTED)

    def test_r3_claims_actually_reach_intimacy_candidate(self, plan):
        provider, _, _ = _dispatch_provider(
            _happy_payloads(plan), _r8_judgment_json(plan.compile_context.package_id),
        )
        result = runner.execute_kira_r4_reconstruction(provider, plan)
        assert result.audit.verdict is AuditVerdict.PASS
        assert result.validation_report.valid is True
        assert result.package.intimacy_candidate != {}

    def test_substantive_payloads_reach_all_authoring_roles_and_r8(self, plan):
        seen = []
        provider, _, r8_calls = _dispatch_provider(
            _happy_payloads(plan), _r8_judgment_json(plan.compile_context.package_id), seen=seen,
        )
        runner.execute_kira_r4_reconstruction(provider, plan)

        role_messages = [m for m in seen if "AUDIT_IDENTITY" not in m]
        r8_messages = [m for m in seen if "AUDIT_IDENTITY" in m]
        assert len(role_messages) == 4
        assert len(r8_messages) == 1
        for m in role_messages:
            assert "substantive_payload" in m
        assert "substantive_payload" in r8_messages[0]

    def test_no_hidden_b_c_or_legacy_content_visible_to_provider(self, plan):
        seen = []
        provider, _, _ = _dispatch_provider(
            _happy_payloads(plan), _r8_judgment_json(plan.compile_context.package_id), seen=seen,
        )
        runner.execute_kira_r4_reconstruction(provider, plan)
        full_text = "\n".join(seen)
        for token in _FORBIDDEN_TOKENS:
            assert token not in full_text

    def test_no_retry_no_fallback_on_role_failure(self, plan):
        calls = {"count": 0}

        def failing_provider(messages):
            calls["count"] += 1
            raise RuntimeError("synthetic role failure")

        with pytest.raises(RuntimeError):
            runner.execute_kira_r4_reconstruction(failing_provider, plan)
        assert calls["count"] == 1  # single attempt, no retry, no fallback


# ---------------------------------------------------------------------------
# Live gate: no --live => no provider construction, no credential read
# ---------------------------------------------------------------------------

class TestLiveGate:
    def test_default_cli_is_safe_dry_run(self, monkeypatch, capsys):
        def must_not_be_called(config):
            raise AssertionError("build_provider_callable must not be called without --live")

        monkeypatch.setattr(runner, "build_provider_callable", must_not_be_called)
        exit_code = runner.main([])
        assert exit_code == 0

        out = json.loads(capsys.readouterr().out)
        assert out["status"] == "PLAN_VALID_OFFLINE_DRY_RUN"
        assert out["role_order"] == ["R1", "R2", "R3", "R4"]
        assert out["r3_activation_authorization_ref"] == "CRP-OD-R4-KIRA-R3-01"
        assert out["provider_call_budget"] == 5

    def test_default_cli_does_not_read_credential_env(self, monkeypatch, capsys):
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

        def must_not_be_called(config):
            raise AssertionError("provider construction (and credential read) must not occur")

        monkeypatch.setattr(runner, "build_provider_callable", must_not_be_called)
        exit_code = runner.main([])
        assert exit_code == 0  # no KeyError / credential-missing failure was ever triggered

    def test_default_cli_never_touches_the_actual_credential_lookup_seam(self, monkeypatch, capsys):
        """Intercept the EXACT ``os.environ.get`` seam ``llm_provider.py`` uses
        to read ``credential_env`` (tools/llm_provider.py, ``_complete_cloud``).
        Proves the non-live path never reaches it -- not merely that
        ``build_provider_callable`` was skipped, but that the underlying
        environment lookup itself never fires for this key."""
        real_get = os.environ.get
        accessed = {"value": False}

        def guarded_get(key, *a, **k):
            if key == "DEEPSEEK_API_KEY":
                accessed["value"] = True
                raise AssertionError("DEEPSEEK_API_KEY must not be looked up without --live")
            return real_get(key, *a, **k)

        monkeypatch.setattr(os.environ, "get", guarded_get)

        exit_code = runner.main([])
        assert exit_code == 0
        assert accessed["value"] is False

    def test_live_flag_reaches_provider_construction(self, monkeypatch, capsys):
        constructed = {"called": False}
        real_plan = runner.build_kira_r4_plan()

        def fake_build_provider_callable(config):
            constructed["called"] = True
            provider, _, _ = _dispatch_provider(
                _happy_payloads(real_plan),
                _r8_judgment_json(real_plan.compile_context.package_id),
            )
            return provider

        monkeypatch.setattr(runner, "build_provider_callable", fake_build_provider_callable)
        exit_code = runner.main(["--live"])
        assert exit_code == 0
        assert constructed["called"] is True

        out = json.loads(capsys.readouterr().out)
        assert out["status"] == "RECONSTRUCTION_COMPLETE_PRE_ACCEPTANCE"
        assert out["provider_attempts"] == 5
        assert out["provider_call_budget"] == 5

    def test_live_flag_passes_the_actual_providerconfigs_main_constructs(self, monkeypatch, capsys):
        """Capture the REAL ``ProviderConfig`` objects ``main()`` builds and
        passes to ``build_provider_callable`` -- not module constants that
        merely happen to match by construction.

        Owner-approved CRP R4 R1-only correction: ``main()`` now builds exactly
        two configs -- an unchanged default (8192, no extra_params) and an R1
        override (65536, thinking disabled). Every other transport field is
        identical between them.
        """
        captured = []
        real_plan = runner.build_kira_r4_plan()

        def fake_build_provider_callable(config):
            captured.append(config)
            provider, _, _ = _dispatch_provider(
                _happy_payloads(real_plan),
                _r8_judgment_json(real_plan.compile_context.package_id),
            )
            return provider

        monkeypatch.setattr(runner, "build_provider_callable", fake_build_provider_callable)
        exit_code = runner.main(["--live"])
        assert exit_code == 0
        assert len(captured) == 2  # exactly one default + one R1 override config

        by_max_tokens = {c.max_tokens: c for c in captured}
        assert set(by_max_tokens) == {8192, 65536}
        default_config = by_max_tokens[8192]
        r1_config = by_max_tokens[65536]

        # Every non-overridden transport field is identical across both configs.
        for config in captured:
            assert config.provider_id == "deepseek"
            assert config.model == "deepseek-v4-pro"
            assert config.base_url == "https://api.deepseek.com"
            assert config.timeout_s == 180.0
            assert config.credential_env == "DEEPSEEK_API_KEY"
            assert config.json_mode is True
            # No secret value is ever stored on the config, and no retry/fallback
            # surface is introduced on top of the existing ProviderConfig contract.
            assert not hasattr(config, "api_key")
            assert not hasattr(config, "retry")
            assert not hasattr(config, "fallback")

        # Default transport carries NO thinking override; R1 disables thinking.
        assert dict(default_config.extra_params) == {}
        assert dict(r1_config.extra_params) == {"thinking": {"type": "disabled"}}
        assert default_config.max_tokens == runner.LIVE_MAX_TOKENS == 8192
        assert r1_config.max_tokens == runner.LIVE_R1_MAX_TOKENS == 65536


# ---------------------------------------------------------------------------
# No accept / no persistence (static source-boundary checks)
# ---------------------------------------------------------------------------

class TestNoAcceptNoPersistence:
    _SOURCE = Path("tools/crp_kira_r4_runner.py").read_text(encoding="utf-8")

    def test_no_accept_candidate_or_human_approved(self):
        # Prose in the module docstring explains what this runner does NOT do
        # (and legitimately names both symbols); what must never appear is an
        # actual call/assignment.
        assert "accept_candidate(" not in self._SOURCE
        assert not hasattr(runner, "accept_candidate")
        assert "PackageStatus.HUMAN_APPROVED" not in self._SOURCE
        assert "= HUMAN_APPROVED" not in self._SOURCE

    def test_no_file_persistence(self):
        assert "write_bytes" not in self._SOURCE
        assert "write_text" not in self._SOURCE
        assert "with open(" not in self._SOURCE

    def test_no_alternate_r8_execution_path(self):
        assert "execute_role_task" not in self._SOURCE
        assert "compile_candidate_package" not in self._SOURCE
        assert "validate_package(" not in self._SOURCE
        assert "run_r8_analysis" not in self._SOURCE


# ---------------------------------------------------------------------------
# Full live-result capture: a successful run must be fully recoverable as
# structured JSON on stdout (result-loss-risk correction). No repository
# writes -- the runner's only job is FULL JSON -> stdout; external capture is
# proven here only via pytest's own out-of-repo tmp_path fixture.
# ---------------------------------------------------------------------------

def _run_happy(plan):
    provider, _, _ = _dispatch_provider(
        _happy_payloads(plan), _r8_judgment_json(plan.compile_context.package_id),
    )
    result = runner.execute_kira_r4_reconstruction(provider, plan)
    envelope = runner.build_result_envelope(plan, result)
    return result, envelope


class TestFullResultCapture:
    # TEST 1 -- full CandidateCharacterPackage field coverage, reflection-based
    # (never a hand-duplicated field list) so a future field addition that the
    # capture forgets to serialize is caught automatically.
    def test_serialized_candidate_package_has_every_current_public_field(self, plan):
        _result, envelope = _run_happy(plan)
        expected_fields = {f.name for f in dataclasses.fields(CandidateCharacterPackage)}
        actual_fields = set(envelope["candidate_package"].keys())
        assert actual_fields == expected_fields

    # TEST 2 -- canonical package hash, no alternate implementation.
    def test_candidate_package_hash_matches_canonical_compute_package_hash(self, plan):
        result, envelope = _run_happy(plan)
        assert envelope["candidate_package_hash"] == compute_package_hash(result.package)

    # TEST 3 -- role results complete, not reduced to counts/IDs.
    def test_role_results_fully_structured_not_reduced_to_ids(self, plan):
        result, envelope = _run_happy(plan)
        assert len(envelope["role_results"]) == 4
        assert [rr["role_id"] for rr in envelope["role_results"]] == ["R1", "R2", "R3", "R4"]

        expected_fields = {f.name for f in dataclasses.fields(RoleResult)}
        for role_result, serialized in zip(result.role_results, envelope["role_results"]):
            assert set(serialized.keys()) == expected_fields
            assert serialized["task_id"] == role_result.task_id
            assert serialized["role_version"] == role_result.role_version
            assert len(serialized["claims"]) == len(role_result.claims)
            assert serialized["claims"][0]["claim_id"] == role_result.claims[0].claim_id

    # TEST 4 -- complete ReconstructionAudit, not merely audit_verdict.
    def test_reconstruction_audit_fully_structured(self, plan):
        result, envelope = _run_happy(plan)
        expected_fields = {f.name for f in dataclasses.fields(ReconstructionAudit)}
        serialized = envelope["reconstruction_audit"]
        assert set(serialized.keys()) == expected_fields
        assert serialized["verdict"] == result.audit.verdict.value
        assert serialized["audit_id"] == result.audit.audit_id
        assert serialized["package_hash"] == result.audit.package_hash
        assert len(serialized["checks"]) == len(result.audit.checks)

    # TEST 5 -- complete ValidationReport, not merely validation_valid.
    def test_validation_report_fully_structured(self, plan):
        result, envelope = _run_happy(plan)
        expected_fields = {f.name for f in dataclasses.fields(ValidationReport)}
        serialized = envelope["validation_report"]
        assert set(serialized.keys()) == expected_fields
        assert serialized["valid"] == result.validation_report.valid
        assert len(serialized["findings"]) == len(result.validation_report.findings)

    # TEST 6 -- valid, re-parseable JSON; Unicode survives unescaped.
    def test_envelope_is_valid_json_and_unicode_safe(self, plan):
        sentinel = "café résumé — офлайн-тест"
        unicode_payloads = _happy_payloads(plan)
        # Keep the R1 v3 gate satisfied (full-coverage claim + matching
        # sources_used); only the claim text carries the Unicode sentinel.
        unicode_payloads["R1"] = _r1_v3_full_coverage_json(plan, claim_text=sentinel)
        provider, _, _ = _dispatch_provider(
            unicode_payloads, _r8_judgment_json(plan.compile_context.package_id),
        )
        result = runner.execute_kira_r4_reconstruction(provider, plan)
        envelope = runner.build_result_envelope(plan, result)

        text = json.dumps(envelope, ensure_ascii=False, indent=2)
        assert sentinel in text  # not escaped as \uXXXX
        reparsed = json.loads(text)
        assert reparsed == envelope

    # TEST 7 -- determinism: serializing the SAME immutable result twice
    # produces byte-identical JSON (dict/tuple iteration order is stable for
    # the same in-memory object across calls).
    def test_serializing_same_result_twice_is_byte_identical(self, plan):
        result, envelope1 = _run_happy(plan)
        envelope2 = runner.build_result_envelope(plan, result)
        assert envelope1 == envelope2
        text1 = json.dumps(envelope1, ensure_ascii=False, indent=2)
        text2 = json.dumps(envelope2, ensure_ascii=False, indent=2)
        assert text1 == text2

    # TEST 8 -- secret exclusion: a synthetic credential sentinel never
    # appears in the envelope; only the non-secret credential_env NAME does.
    def test_no_secret_or_credential_value_leaks_into_envelope(self, plan, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "DO_NOT_LEAK_SYNTHETIC_SECRET")
        _result, envelope = _run_happy(plan)
        text = json.dumps(envelope, ensure_ascii=False)

        assert "DO_NOT_LEAK_SYNTHETIC_SECRET" not in text
        assert envelope["run_metadata"]["credential_env_name"] == "DEEPSEEK_API_KEY"
        for forbidden_key in ("api_key", "authorization", "credential_value", "credential_env"):
            assert forbidden_key not in envelope["run_metadata"]

    # TEST 9 -- CLI success layer: exactly one parseable JSON document on
    # stdout, all provider/network dependencies faked, zero real --live.
    def test_live_stdout_emits_exactly_one_parseable_json_result_document(self, monkeypatch, capsys):
        real_plan = runner.build_kira_r4_plan()

        def fake_build_provider_callable(config):
            provider, _, _ = _dispatch_provider(
                _happy_payloads(real_plan),
                _r8_judgment_json(real_plan.compile_context.package_id),
            )
            return provider

        monkeypatch.setattr(runner, "build_provider_callable", fake_build_provider_callable)
        exit_code = runner.main(["--live"])
        assert exit_code == 0

        out = capsys.readouterr().out
        parsed = json.loads(out)  # fails if stdout is not exactly one JSON document
        assert parsed["artifact_type"] == runner.RESULT_ARTIFACT_TYPE
        assert parsed["schema_version"] == runner.RESULT_SCHEMA_VERSION
        assert "candidate_package" in parsed
        assert "candidate_package_hash" in parsed
        assert "reconstruction_audit" in parsed
        assert "validation_report" in parsed
        assert len(parsed["role_results"]) == 4

    # TEST 10 moved to TestRealProcessStdoutCapture below: proving the real
    # transport boundary (child process stdout -> external file -> UTF-8 ->
    # strict JSON) requires an actual child process, not json.dumps(envelope)
    # dumped directly by the parent test.


# ---------------------------------------------------------------------------
# Mapping-key and non-finite-float safety (Codex CORE_SERIALIZATION_GAP_FOUND
# corrections 1-2). Behavioral: exercises the real ``_to_jsonable`` function
# with concrete inputs, never a source-substring check or a duplicated
# expected-value reconstruction of the same logic.
# ---------------------------------------------------------------------------

class TestMappingKeySafety:
    def test_string_keyed_mapping_serializes_normally(self):
        assert runner._to_jsonable({"valid": "ok"}) == {"valid": "ok"}

    def test_integer_key_fails_closed(self):
        with pytest.raises(TypeError):
            runner._to_jsonable({1: "integer-key"})

    def test_integer_and_string_key_collision_fails_closed_not_silently_collapsed(self):
        # If str(k) coercion were still present, {1: ..., "1": ...} would
        # silently collapse onto one JSON key (whichever dict.items() yields
        # last). It must instead raise before any such collapse can occur.
        with pytest.raises(TypeError):
            runner._to_jsonable({1: "integer-key", "1": "string-key"})

    def test_nested_mapping_with_non_string_key_fails_closed(self):
        with pytest.raises(TypeError):
            runner._to_jsonable({"outer": {2: "nested-int-key"}})

    def test_non_string_key_inside_a_dataclass_field_fails_closed(self):
        @dataclasses.dataclass(frozen=True)
        class _SyntheticMappingHolder:
            data: dict

        with pytest.raises(TypeError):
            runner._to_jsonable(_SyntheticMappingHolder(data={7: "bad-key"}))


class TestNonFiniteFloatSafety:
    def test_finite_float_serializes_normally(self):
        assert runner._to_jsonable(3.14) == 3.14

    def test_nan_fails_closed(self):
        with pytest.raises(ValueError):
            runner._to_jsonable(float("nan"))

    def test_positive_infinity_fails_closed(self):
        with pytest.raises(ValueError):
            runner._to_jsonable(float("inf"))

    def test_negative_infinity_fails_closed(self):
        with pytest.raises(ValueError):
            runner._to_jsonable(float("-inf"))

    def test_nan_nested_inside_mapping_and_list_fails_closed(self):
        with pytest.raises(ValueError):
            runner._to_jsonable({"scores": [1.0, 2.0, float("nan")]})

    def test_nan_nested_inside_a_dataclass_field_fails_closed(self):
        @dataclasses.dataclass(frozen=True)
        class _SyntheticFloatHolder:
            value: float

        with pytest.raises(ValueError):
            runner._to_jsonable(_SyntheticFloatHolder(value=float("inf")))


class TestUnsupportedTypesFailClosed:
    def test_arbitrary_unsupported_object_fails_closed_without_repr_or_str_fallback(self):
        class _NotJsonable:
            def __repr__(self):
                return "<should never appear in output>"

        with pytest.raises(TypeError):
            runner._to_jsonable(_NotJsonable())


def _strict_json_loads(text: str):
    """Stdlib-only strict JSON parse: reject the permissive NaN/Infinity/
    -Infinity constant tokens that Python's ``json.loads`` accepts by default
    but that are not valid interoperable strict JSON."""

    def _reject_constant(constant: str):
        raise ValueError(f"non-finite constant {constant!r} is not valid strict JSON")

    return json.loads(text, parse_constant=_reject_constant)


class TestStrictJsonRoundtrip:
    def test_strict_loader_rejects_permissive_nan_token(self):
        with pytest.raises(ValueError):
            _strict_json_loads('{"x": NaN}')

    def test_strict_loader_rejects_permissive_infinity_token(self):
        with pytest.raises(ValueError):
            _strict_json_loads('{"x": Infinity}')

    def test_successful_envelope_is_strict_json(self, plan):
        _result, envelope = _run_happy(plan)
        text = json.dumps(envelope, ensure_ascii=False, indent=2, allow_nan=False)
        parsed = _strict_json_loads(text)
        assert parsed == envelope


# ---------------------------------------------------------------------------
# Real process stdout -> external file capture (Codex correction 3). Proves
# the actual transport boundary a future --live run would rely on:
#     real child Python process -> runner CLI stdout -> external temp file
#     -> strict UTF-8 decode -> strict JSON parse -> full-envelope structure.
# The child process replaces build_provider_callable with an in-process
# synthetic fake BEFORE calling runner.main(["--live"]) -- no production
# --test-mode flag, no real provider, no real credential read, no network.
# ---------------------------------------------------------------------------

_CHILD_SCRIPT_TEMPLATE = r'''
import json
import sys
from pathlib import Path

_REPO_ROOT = Path({repo_root!r})
_TOOLS_DIR = _REPO_ROOT / "tools"
for _p in (str(_REPO_ROOT), str(_TOOLS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import crp_kira_r4_runner as runner

_UNICODE = {unicode_sentinel!r}
_FIRST_EVIDENCE_ID = {first_evidence_id!r}
_ALL_EVIDENCE_IDS = {all_evidence_ids!r}
_TARGETS = {{
    "R1": "identity_biography.birthplace",
    "R2": "behavior.conflict_style",
    "R3": "intimacy.communication_style",
    "R4": "voice.lexicon",
}}


def _role_result_json(task_id, role_id, role_version, target):
    # R1 v3 must satisfy the executor's R1-v3 quality gate: one corroboration-
    # merged claim citing the full allowed-evidence union, and a
    # provenance_summary.sources_used mirroring that union exactly. R2/R3/R4
    # keep the single-source shape and the v2-style used_evidence mirror.
    is_r1 = role_id == "R1"
    ev_ids = list(_ALL_EVIDENCE_IDS) if is_r1 else [_FIRST_EVIDENCE_ID]
    provenance_summary = (
        {{"sources_used": list(_ALL_EVIDENCE_IDS)}} if is_r1
        else {{"used_evidence": [_FIRST_EVIDENCE_ID]}}
    )
    return json.dumps({{
        "task_id": task_id,
        "role_id": role_id,
        "role_version": role_version,
        "completion_status": "COMPLETE",
        "claims": [{{
            "claim_id": "c-" + role_id.lower(),
            "subject_id": "kira",
            "role_id": role_id,
            "claim": _UNICODE,
            "claim_type": "FACT" if is_r1 else "OBSERVATION",
            "source_evidence_ids": ev_ids,
            "source_type_summary": ["OWNER_DIRECT"],
            "confidence": "KNOWN" if is_r1 else "POSSIBLE",
            "rationale_summary": "subprocess capture test (synthetic)",
            "status": "PROPOSED",
            "target_module_or_layer": target,
        }}],
        "unknowns": [],
        "contradictions": [],
        "provenance_summary": provenance_summary,
        "requests_for_more_evidence": [],
        "warnings": [],
        "questions_for_r1": [],
        "new_source_evidence": [],
    }}, ensure_ascii=False)


_plan = runner.build_kira_r4_plan()
_task_ids = {{t.role_id: t.task_id for t in _plan.role_tasks}}
_role_payloads = {{
    rid: _role_result_json(_task_ids[rid], rid, runner.ROLE_VERSIONS[rid], _TARGETS[rid])
    for rid in runner.ROLE_ORDER
}}
_r8_json = json.dumps({{
    "package_id": _plan.compile_context.package_id,
    "subject_id": "kira",
    "role_id": "R8",
    "role_version": "v1",
    "checks": [
        {{"check_id": "R8_ROLE_BOUNDARY_SEMANTIC", "outcome": "PASS", "findings": []}},
        {{"check_id": "R8_MODULE_PLACEMENT", "outcome": "PASS", "findings": []}},
        {{"check_id": "R8_UNKNOWN_COVERAGE", "outcome": "PASS", "findings": []}},
    ],
    "narrative": "clean",
}}, ensure_ascii=False)


def _fake_provider(messages):
    user_content = "".join(m["content"] for m in messages if m.get("role") == "user")
    if "AUDIT_IDENTITY" in user_content:
        return _r8_json
    for role_id, payload in _role_payloads.items():
        if "- role_id: " + role_id in user_content:
            return payload
    raise AssertionError("subprocess fake provider received an unrecognized call")


def _fake_build_provider_callable(config):
    return _fake_provider


# In-process, test-only replacement -- no production --test-mode flag, no
# real DeepSeek construction, no network, no credential value read.
runner.build_provider_callable = _fake_build_provider_callable

sys.exit(runner.main(["--live"]))
'''


class TestRealProcessStdoutCapture:
    # Deterministic synthetic claim identities the child script's fake role
    # payloads use (kept in sync with _CHILD_SCRIPT_TEMPLATE's _TARGETS /
    # claim_id construction). Used by the parent ONLY to build an
    # independently-derived expected CandidateCharacterPackage for the
    # canonical package-hash check -- never to weaken the strict field-set
    # checks, which compare against dataclasses.fields(...) instead.
    _EXPECTED_TARGETS = {
        "R1": "identity_biography.birthplace",
        "R2": "behavior.conflict_style",
        "R3": "intimacy.communication_style",
        "R4": "voice.lexicon",
    }

    def test_real_child_process_stdout_to_external_file_roundtrip(self, plan, tmp_path):
        sentinel_secret = "DO_NOT_LEAK_SYNTHETIC_SECRET"
        unicode_sentinel = "café résumé — офлайн-тест"
        first_evidence_id = plan.projection.evidence[0].source_id
        all_evidence_ids = [ev.source_id for ev in plan.projection.evidence]

        child_script = _CHILD_SCRIPT_TEMPLATE.format(
            repo_root=_PROJECT_ROOT,
            unicode_sentinel=unicode_sentinel,
            first_evidence_id=first_evidence_id,
            all_evidence_ids=all_evidence_ids,
        )

        # Minimal, from-scratch child environment -- exactly these three
        # variables, nothing else. NEVER dict(os.environ) / os.environ.copy()
        # / {**os.environ} / any full-environment materialization: that would
        # read every parent variable, including a possible real
        # DEEPSEEK_API_KEY, before any sanitization could happen.
        # DEEPSEEK_API_KEY below is a synthetic sentinel constructed here,
        # never read from the parent's environment. sys.executable is an
        # absolute path (PATH is not needed to locate Python) and cwd is
        # explicit (PYTHONPATH is not needed either). Verified empirically on
        # this host: no additional OS variable (SYSTEMROOT/WINDIR/TEMP/TMP)
        # is required for python.exe to launch with this exact environment.
        child_env = {
            "PYTHONIOENCODING": "utf-8",
            "PYTHONDONTWRITEBYTECODE": "1",
            "DEEPSEEK_API_KEY": sentinel_secret,
        }

        capture_file = tmp_path / "kira_r4_live_run_capture.json"
        with capture_file.open("wb") as capture:
            proc = subprocess.run(
                [sys.executable, "-c", child_script],
                stdout=capture,
                stderr=subprocess.PIPE,
                env=child_env,
                cwd=_PROJECT_ROOT,
                check=False,
            )

        assert proc.returncode == 0, proc.stderr.decode("utf-8", errors="replace")

        captured_bytes = capture_file.read_bytes()
        assert captured_bytes  # 2. non-empty

        text = captured_bytes.decode("utf-8", errors="strict")  # 3. strict UTF-8 decode
        assert text.strip().startswith("{") and text.strip().endswith("}")  # 16. no decorative wrapper

        # 4+5. exactly one JSON document, and the ACTUAL captured artifact
        # itself (not a separately-dumped copy) must pass STRICT JSON parsing
        # (no permissive NaN/Infinity/-Infinity constants).
        parsed = _strict_json_loads(text)

        assert parsed["artifact_type"] == runner.RESULT_ARTIFACT_TYPE  # 6
        assert parsed["schema_version"] == runner.RESULT_SCHEMA_VERSION  # 7

        # 8. Full CandidateCharacterPackage field coverage in the CAPTURED
        # artifact, reflection-based against the real contract (never a
        # hand-duplicated list, never derived from the captured data itself).
        assert set(parsed["candidate_package"].keys()) == {
            f.name for f in dataclasses.fields(CandidateCharacterPackage)
        }
        # 10. Full ReconstructionAudit field coverage in the captured artifact.
        assert set(parsed["reconstruction_audit"].keys()) == {
            f.name for f in dataclasses.fields(ReconstructionAudit)
        }
        # 11. Full ValidationReport field coverage in the captured artifact.
        assert set(parsed["validation_report"].keys()) == {
            f.name for f in dataclasses.fields(ValidationReport)
        }
        # 12. Exactly four RoleResults, correct identity/order, each with
        # full RoleResult field coverage in the captured artifact.
        assert len(parsed["role_results"]) == 4
        assert [rr["role_id"] for rr in parsed["role_results"]] == ["R1", "R2", "R3", "R4"]
        expected_role_result_fields = {f.name for f in dataclasses.fields(RoleResult)}
        for serialized in parsed["role_results"]:
            assert set(serialized.keys()) == expected_role_result_fields

        # 9. Canonical package hash: the expected value is derived using the
        # REAL compute_package_hash over an independently-constructed
        # CandidateCharacterPackage built from the same deterministic
        # synthetic claim/target identities the child script uses -- never
        # from the captured JSON, and never a duplicated hashing algorithm.
        # compute_package_hash only depends on package_id / package_version /
        # subject_id / claim_ids / provenance_manifest, so the remaining
        # fields below only need to satisfy the dataclass's own validation.
        expected_claims = tuple(
            RoleClaim(
                claim_id=f"c-{role_id.lower()}",
                subject_id=plan.projection.subject_id,
                role_id=role_id,
                claim=unicode_sentinel,
                claim_type=ClaimType.FACT if role_id == "R1" else ClaimType.OBSERVATION,
                source_evidence_ids=(first_evidence_id,),
                source_type_summary=(SourceType.OWNER_DIRECT,),
                confidence=Confidence.KNOWN if role_id == "R1" else Confidence.POSSIBLE,
                rationale_summary="subprocess capture test (synthetic)",
                status=ClaimStatus.PROPOSED,
                target_module_or_layer=self._EXPECTED_TARGETS[role_id],
            )
            for role_id in runner.ROLE_ORDER
        )
        expected_package = CandidateCharacterPackage(
            package_id=f"{runner.KIRA_RUN_ID}-package",
            subject_id=plan.projection.subject_id,
            package_version=0,
            source_snapshot_id=plan.projection.evidence_snapshot_id,
            role_result_refs=(),
            claims=expected_claims,
            contradictions=(),
            unknowns=(),
            psychology_candidate={},
            voice_candidate={},
            validation_results={},
            audit_result=None,
            provenance_manifest={c.target_module_or_layer: (c.claim_id,) for c in expected_claims},
            created_at=datetime.now(timezone.utc),
            status=PackageStatus.DRAFT,
        )
        assert parsed["candidate_package_hash"] == compute_package_hash(expected_package)

        # 13. provider attempt metadata present.
        assert "provider_attempts" in parsed and "provider_call_budget" in parsed

        # 14. Unicode survives the real process + external-file roundtrip.
        assert unicode_sentinel in text
        # 15. synthetic secret is absent from the ACTUAL captured bytes.
        assert sentinel_secret not in text


# ---------------------------------------------------------------------------
# Provider-visible evidence boundary: bounded to EXACTLY the authorized A
# projection -- not a subset, not a superset. The extractors below parse the
# COMPLETE renderer-defined evidence block (every structural evidence entry,
# regardless of its ``content_ref`` prefix) and then compare the complete
# parsed set against an INDEPENDENTLY derived projection set. There is
# deliberately NO pre-filter on "A_AUTHORING/", "OWNER_DIRECT", known expected
# ids, or any expected path prefix, so an unexpected source with a foreign
# content_ref is still observed and therefore breaks exact equality.
#
# Reuses production's own ``_render_payload`` only as the canonical payload
# REPRESENTATION (never re-duplicating serialization); the expected source
# set still derives independently from ``projection.evidence``.
# ---------------------------------------------------------------------------

# Structural entry markers (no content_ref/prefix requirement):
#   authoring roles:  "- <source_id>: <content_ref>"  (executor._assemble_messages)
#   R8 ledger:        "- <source_id> type=..."        (r8_llm_judgment._render_data_block)
# Both share the indented "  substantive_payload: ..." sub-line.
_AUTHORING_ENTRY_LINE = re.compile(r"^- (\S+): (.*)$")
_AUTHORING_PAYLOAD_LINE = re.compile(r"^  substantive_payload: (.*)$")
_R8_ENTRY_LINE = re.compile(r"^- (\S+) type=.*$")
_R8_PAYLOAD_LINE = re.compile(r"^  substantive_payload: (.*)$")

# Purely synthetic, test-only unauthorized sentinels (never sourced from
# Hidden-B / Legacy-C / personas content).
_UNAUTHORIZED_SOURCE_ID = "synthetic-unauthorized-source"
_UNAUTHORIZED_CONTENT_REF = "SYNTHETIC_UNAUTHORIZED/source"
_UNAUTHORIZED_PAYLOAD_MARKER = "synthetic_unauthorized_payload_marker"


def _extract_authoring_evidence(message):
    """Parse the whole ``allowed_evidence`` block of an authoring-role provider
    message into ``(source_ids, payloads_by_source_id)``.

    The block spans from the literal ``allowed_evidence:`` marker line to the
    literal ``allowed_prior_results:`` marker line. Every entry line of the
    form ``- <source_id>: <content_ref>`` inside that block is captured
    verbatim (no content_ref-prefix filter), and each following
    ``  substantive_payload: ...`` sub-line is bound to the most recent entry.
    """
    ids = set()
    payloads = {}
    current_id = None
    in_block = False
    for raw in message.splitlines():
        stripped = raw.rstrip()
        if stripped == "allowed_evidence:":
            in_block = True
            current_id = None
            continue
        if in_block and stripped == "allowed_prior_results:":
            break
        if not in_block:
            continue
        m = _AUTHORING_ENTRY_LINE.match(raw)
        if m:
            current_id = m.group(1)
            ids.add(current_id)
            continue
        p = _AUTHORING_PAYLOAD_LINE.match(raw)
        if p and current_id is not None:
            payloads[current_id] = p.group(1)
    return ids, payloads


def _extract_r8_evidence(message):
    """Parse the whole ``EVIDENCE_LEDGER`` block of an R8 provider message into
    ``(source_ids, payloads_by_source_id)``.

    The block spans from the literal ``EVIDENCE_LEDGER`` marker line to the
    literal ``DETERMINISTIC_AUDIT_SUMMARY`` marker line. Entries are
    ``- <source_id> type=...``; no content_ref/prefix filter is applied.
    """
    ids = set()
    payloads = {}
    current_id = None
    in_block = False
    for raw in message.splitlines():
        stripped = raw.rstrip()
        if stripped == "EVIDENCE_LEDGER":
            in_block = True
            current_id = None
            continue
        if in_block and stripped == "DETERMINISTIC_AUDIT_SUMMARY":
            break
        if not in_block:
            continue
        m = _R8_ENTRY_LINE.match(raw)
        if m:
            current_id = m.group(1)
            ids.add(current_id)
            continue
        p = _R8_PAYLOAD_LINE.match(raw)
        if p and current_id is not None:
            payloads[current_id] = p.group(1)
    return ids, payloads


def _happy_seen(plan):
    seen = []
    provider, _, _ = _dispatch_provider(
        _happy_payloads(plan), _r8_judgment_json(plan.compile_context.package_id), seen=seen,
    )
    runner.execute_kira_r4_reconstruction(provider, plan)
    return seen


class TestProviderVisibleEvidenceSetExactness:
    @staticmethod
    def _expected(plan):
        source_ids = tuple(ev.source_id for ev in plan.projection.evidence)
        assert source_ids  # real, non-empty A projection
        payloads = {
            source_id: _prod_render_payload(payload)
            for source_id, payload in plan.projection.payloads.items()
        }
        # The substantive payload map must cover exactly the evidence ledger.
        assert set(payloads) == set(source_ids)
        return set(source_ids), payloads

    def test_each_authoring_role_visible_evidence_ids_equal_projection_exactly(self, plan):
        seen = _happy_seen(plan)
        role_messages = [m for m in seen if "AUDIT_IDENTITY" not in m]
        assert len(role_messages) == 4
        expected_ids, _ = self._expected(plan)

        for message in role_messages:
            visible_ids, _ = _extract_authoring_evidence(message)
            assert visible_ids == expected_ids, (
                "authoring-role provider message exposed evidence id set "
                f"{sorted(visible_ids)} != projection {sorted(expected_ids)}"
            )

    def test_each_authoring_role_visible_payloads_equal_projection_exactly(self, plan):
        seen = _happy_seen(plan)
        role_messages = [m for m in seen if "AUDIT_IDENTITY" not in m]
        assert len(role_messages) == 4
        _, expected_payloads = self._expected(plan)

        for message in role_messages:
            _, visible_payloads = _extract_authoring_evidence(message)
            assert visible_payloads == expected_payloads, (
                "authoring-role provider message exposed substantive payloads "
                "that do not exactly match the projection"
            )

    def test_r8_visible_evidence_ids_equal_projection_exactly(self, plan):
        seen = _happy_seen(plan)
        r8_messages = [m for m in seen if "AUDIT_IDENTITY" in m]
        assert len(r8_messages) == 1
        expected_ids, _ = self._expected(plan)
        visible_ids, _ = _extract_r8_evidence(r8_messages[0])
        assert visible_ids == expected_ids

    def test_r8_visible_payloads_equal_projection_exactly(self, plan):
        seen = _happy_seen(plan)
        r8_messages = [m for m in seen if "AUDIT_IDENTITY" in m]
        assert len(r8_messages) == 1
        _, expected_payloads = self._expected(plan)
        _, visible_payloads = _extract_r8_evidence(r8_messages[0])
        assert visible_payloads == expected_payloads


class TestEvidenceExtractorDetectsUnexpectedEntries:
    """Prove the extractor/assertion is NOT tautological: a synthetic, purely
    test-only unauthorized entry (foreign ``content_ref``, foreign source id,
    foreign payload marker) MUST be observed by the extractor, which in turn
    breaks the exact-set/exact-payload equality. These sentinels exist only in
    test code and are never sourced from Hidden-B / Legacy-C / personas."""

    _SYNTHETIC_SUBLINES = (
        f"  source_id: {_UNAUTHORIZED_SOURCE_ID}\n"
        f"  content_ref: {_UNAUTHORIZED_CONTENT_REF}\n"
        "  content_hash: 0000000000000000000000000000000000000000000000000000000000000000\n"
        f'  substantive_payload: {{"facts":["{_UNAUTHORIZED_PAYLOAD_MARKER}"]}}\n'
    )

    def test_authoring_extractor_sees_foreign_content_ref_source(self):
        block = (
            "allowed_evidence:\n"
            f"- {_UNAUTHORIZED_SOURCE_ID}: {_UNAUTHORIZED_CONTENT_REF}\n"
            + self._SYNTHETIC_SUBLINES
            + "allowed_prior_results:\n"
        )
        ids, payloads = _extract_authoring_evidence(block)
        assert _UNAUTHORIZED_SOURCE_ID in ids
        assert _UNAUTHORIZED_PAYLOAD_MARKER in next(iter(payloads.values()))

    def test_r8_extractor_sees_foreign_content_ref_source(self):
        block = (
            "EVIDENCE_LEDGER\n"
            f"- {_UNAUTHORIZED_SOURCE_ID} type=OWNER_DIRECT subject=kira "
            f"content_ref={_UNAUTHORIZED_CONTENT_REF}\n"
            + self._SYNTHETIC_SUBLINES
            + "DETERMINISTIC_AUDIT_SUMMARY\n"
        )
        ids, payloads = _extract_r8_evidence(block)
        assert _UNAUTHORIZED_SOURCE_ID in ids
        assert _UNAUTHORIZED_PAYLOAD_MARKER in next(iter(payloads.values()))

    def test_injected_unauthorized_source_breaks_exact_set_assertion(self, plan):
        seen = _happy_seen(plan)
        expected_ids = {ev.source_id for ev in plan.projection.evidence}
        role_message = next(m for m in seen if "AUDIT_IDENTITY" not in m)

        injected = role_message.replace(
            "allowed_prior_results:",
            f"- {_UNAUTHORIZED_SOURCE_ID}: {_UNAUTHORIZED_CONTENT_REF}\n"
            + self._SYNTHETIC_SUBLINES
            + "allowed_prior_results:",
        )
        visible_ids, visible_payloads = _extract_authoring_evidence(injected)

        assert _UNAUTHORIZED_SOURCE_ID in visible_ids
        assert visible_ids != expected_ids  # the exact-set assertion WOULD fail
        assert _UNAUTHORIZED_SOURCE_ID in visible_payloads


# ---------------------------------------------------------------------------
# Behavioral no-persistence proof: a successful fake-provider run leaves the
# git worktree byte-identical and never invokes a Path write during
# execution.
# ---------------------------------------------------------------------------

def _git_status_snapshot():
    result = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=_PROJECT_ROOT, capture_output=True, text=True, check=True,
    )
    return result.stdout


# ---------------------------------------------------------------------------
# Owner-approved CRP R4 R1-only provider-options correction.
#
# Exercises the REAL runner-local dispatcher + REAL crp_provider_adapter
# ProviderConfig/build_provider_callable path; only the transport boundary
# (crp_provider_adapter.complete -> llm_provider) is replaced by an in-process
# capturing fake. Zero network, zero real --live, zero credential value read.
# ---------------------------------------------------------------------------

def _canonical_user_content(role_id, user_text):
    """True iff ``user_text`` is the canonical current_task block for ``role_id``
    (leading ``current_task:`` header, exactly one matching ``- role_id:`` line)
    -- the SAME rule the production dispatcher applies."""
    return runner._extract_current_task_role_id(
        [{"role": "user", "content": user_text}]
    ) == role_id


class TestR1OnlyProviderOptionsOutbound:
    """R1 (v3) alone gets max_tokens=65536 + thinking disabled; R2/R3/R4/R8 keep
    the unchanged default transport (8192, no thinking)."""

    def _capture(self, monkeypatch, plan):
        calls = []
        happy = _happy_payloads(plan)
        r8_json = _r8_judgment_json(plan.compile_context.package_id)

        def fake_complete(messages, *, provider, model=None, system=None, params=None):
            params = dict(params or {})
            user_content = "".join(
                m.get("content", "") for m in messages if m.get("role") == "user"
            )
            calls.append({"params": params, "user": user_content, "model": model})
            if "AUDIT_IDENTITY" in user_content:
                return r8_json
            role_id = runner._extract_current_task_role_id(messages)
            if role_id in happy:
                return happy[role_id]
            raise AssertionError(
                f"fake_complete: unrecognized call (role_id={role_id!r})"
            )

        # Patch ONLY the transport boundary; the real ProviderConfig +
        # build_provider_callable + dispatcher all run unchanged.
        monkeypatch.setattr(crp_provider_adapter, "complete", fake_complete)
        result = runner.execute_kira_r4_reconstruction(
            runner.build_live_provider_callable(), plan
        )
        return result, calls

    def _role_params(self, calls, role_id):
        hits = [
            c for c in calls
            if "AUDIT_IDENTITY" not in c["user"]
            and _canonical_user_content(role_id, c["user"])
        ]
        assert len(hits) == 1, f"{role_id}: expected exactly one outbound call, got {len(hits)}"
        return hits[0]["params"]

    def _r8_params(self, calls):
        hits = [c for c in calls if "AUDIT_IDENTITY" in c["user"]]
        assert len(hits) == 1
        return hits[0]["params"]

    def test_r1_outbound_uses_65536_and_thinking_disabled(self, monkeypatch, plan):
        _result, calls = self._capture(monkeypatch, plan)
        params = self._role_params(calls, "R1")
        assert params["max_tokens"] == 65536
        assert params["thinking"] == {"type": "disabled"}

    def test_r2_outbound_uses_default_8192_no_thinking(self, monkeypatch, plan):
        _result, calls = self._capture(monkeypatch, plan)
        params = self._role_params(calls, "R2")
        assert params["max_tokens"] == 8192
        assert "thinking" not in params

    def test_r3_outbound_uses_default_8192_no_thinking(self, monkeypatch, plan):
        _result, calls = self._capture(monkeypatch, plan)
        params = self._role_params(calls, "R3")
        assert params["max_tokens"] == 8192
        assert "thinking" not in params

    def test_r4_outbound_uses_default_8192_no_thinking(self, monkeypatch, plan):
        _result, calls = self._capture(monkeypatch, plan)
        params = self._role_params(calls, "R4")
        assert params["max_tokens"] == 8192
        assert "thinking" not in params

    def test_r8_outbound_uses_default_8192_no_thinking(self, monkeypatch, plan):
        _result, calls = self._capture(monkeypatch, plan)
        params = self._r8_params(calls)
        assert params["max_tokens"] == 8192
        assert "thinking" not in params

    def test_exactly_one_provider_bound_role_uses_thinking_override(self, monkeypatch, plan):
        _result, calls = self._capture(monkeypatch, plan)
        with_thinking = [c for c in calls if "thinking" in c["params"]]
        assert len(with_thinking) == 1
        assert _canonical_user_content("R1", with_thinking[0]["user"])
        assert with_thinking[0]["params"]["thinking"] == {"type": "disabled"}

    def test_exactly_five_outbound_calls_single_shared_budget(self, monkeypatch, plan):
        result, calls = self._capture(monkeypatch, plan)
        assert len(calls) == 5  # R1 + R2 + R3 + R4 + one R8
        assert result.provider_attempts == 5
        assert result.provider_call_budget == 5
        assert result.provider_attempts <= result.provider_call_budget

    def test_single_counting_guard_wraps_the_one_dispatcher(self, monkeypatch, plan):
        instances = {"n": 0}
        real_guard = runner.CountingGuard

        def counting_guard(*args, **kwargs):
            instances["n"] += 1
            return real_guard(*args, **kwargs)

        monkeypatch.setattr(runner, "CountingGuard", counting_guard)
        result, calls = self._capture(monkeypatch, plan)
        assert instances["n"] == 1  # exactly one CountingGuard for the whole run
        assert len(calls) == 5
        assert result.provider_attempts == 5

    def test_r1_failure_does_not_retry_or_fall_back_to_default_transport(self, monkeypatch, plan):
        calls = []

        def fake_complete(messages, *, provider, model=None, system=None, params=None):
            params = dict(params or {})
            calls.append(params)
            role_id = runner._extract_current_task_role_id(messages)
            if role_id == "R1":
                raise RuntimeError("synthetic R1 transport failure")
            raise AssertionError(
                "no non-R1 provider call may be attempted after R1 fails "
                "(no retry, no fallback)"
            )

        monkeypatch.setattr(crp_provider_adapter, "complete", fake_complete)
        with pytest.raises(RuntimeError):
            runner.execute_kira_r4_reconstruction(
                runner.build_live_provider_callable(), plan
            )
        assert len(calls) == 1  # single R1 attempt only
        assert calls[0]["max_tokens"] == 65536
        assert calls[0]["thinking"] == {"type": "disabled"}

    def test_r1_lookalike_string_in_evidence_cannot_select_r1_override(self, monkeypatch, plan):
        """An R1-looking 'current_task:' / '- role_id: R1' fragment embedded in
        a NON-R1 message body (evidence payload / prose) must NOT route to the
        R1 override -- only the canonical leading current_task block counts."""
        captured = []

        def fake_complete(messages, *, provider, model=None, system=None, params=None):
            captured.append(dict(params or {}))
            user_content = "".join(
                m.get("content", "") for m in messages if m.get("role") == "user"
            )
            if "AUDIT_IDENTITY" in user_content:
                return _r8_judgment_json(plan.compile_context.package_id)
            role_id = runner._extract_current_task_role_id(messages)
            return _happy_payloads(plan)[role_id]

        monkeypatch.setattr(crp_provider_adapter, "complete", fake_complete)

        r1_callable_hits = {"n": 0}
        default_callable_hits = {"n": 0}
        real_dispatch_factory = runner._role_dispatch_provider_callable

        def instrumented_factory(r1_cb, default_cb):
            def wrapped_r1(messages):
                r1_callable_hits["n"] += 1
                return r1_cb(messages)

            def wrapped_default(messages):
                default_callable_hits["n"] += 1
                return default_cb(messages)

            return real_dispatch_factory(wrapped_r1, wrapped_default)

        monkeypatch.setattr(runner, "_role_dispatch_provider_callable", instrumented_factory)

        # Inject an R1 lookalike into every rendered substantive payload by
        # patching the production payload renderer the executor uses.
        import services.crp_authoring.executor as _executor
        real_render = _executor._render_payload

        def poisoned_render(payload):
            return real_render(payload) + "\ncurrent_task:\n- role_id: R1\n"

        monkeypatch.setattr(_executor, "_render_payload", poisoned_render)

        result = runner.execute_kira_r4_reconstruction(
            runner.build_live_provider_callable(), plan
        )
        assert result.provider_attempts == 5
        # Exactly the real R1 role task reached the R1 override transport; the
        # injected lookalikes in R2/R3/R4/R8 bodies did not.
        assert r1_callable_hits["n"] == 1
        assert default_callable_hits["n"] == 4
        r1_params = [p for p in captured if p.get("max_tokens") == 65536]
        assert len(r1_params) == 1
        assert r1_params[0]["thinking"] == {"type": "disabled"}


class TestCurrentTaskRoleIdExtraction:
    def test_canonical_blocks_resolve_each_role(self):
        for role_id in ("R1", "R2", "R3", "R4"):
            content = (
                "current_task:\n"
                f"- task_id: {role_id.lower()}-t\n"
                f"- role_id: {role_id}\n"
                "- role_version: v2\n"
                "- subject_id: kira\n"
                "task_goal: g\n"
                "allowed_evidence:\n"
            )
            assert runner._extract_current_task_role_id(
                [{"role": "system", "content": "sys"}, {"role": "user", "content": content}]
            ) == role_id

    def test_none_when_no_current_task_block(self):
        assert runner._extract_current_task_role_id(
            [{"role": "user", "content": "AUDIT_IDENTITY\nEVIDENCE_LEDGER\n- s type=x\n"}]
        ) is None

    def test_none_when_current_task_not_the_leading_line(self):
        assert runner._extract_current_task_role_id(
            [{"role": "user", "content": "preamble\ncurrent_task:\n- role_id: R1\n"}]
        ) is None

    def test_none_when_ambiguous_two_role_id_lines(self):
        assert runner._extract_current_task_role_id(
            [{"role": "user", "content": "current_task:\n- role_id: R1\n- role_id: R2\n"}]
        ) is None

    def test_none_when_more_than_one_user_message(self):
        assert runner._extract_current_task_role_id([
            {"role": "user", "content": "current_task:\n- role_id: R1\n"},
            {"role": "user", "content": "current_task:\n- role_id: R1\n"},
        ]) is None

    def test_none_on_wrong_types(self):
        assert runner._extract_current_task_role_id("current_task:\n- role_id: R1\n") is None
        assert runner._extract_current_task_role_id([]) is None
        assert runner._extract_current_task_role_id(
            [{"role": "user", "content": None}]
        ) is None

    def test_dispatch_routes_r1_only_from_canonical_block(self):
        seen = {"r1": 0, "default": 0}
        dispatch = runner._role_dispatch_provider_callable(
            lambda m: seen.__setitem__("r1", seen["r1"] + 1) or "{}",
            lambda m: seen.__setitem__("default", seen["default"] + 1) or "{}",
        )
        dispatch([{"role": "user", "content":
                   "current_task:\n- task_id: t\n- role_id: R1\n- role_version: v2\n"
                   "- subject_id: kira\ntask_goal: g\n"}])
        dispatch([{"role": "user", "content":
                   "current_task:\n- task_id: t\n- role_id: R2\n- role_version: v2\n"
                   "- subject_id: kira\ntask_goal: g\nnote: - role_id: R1 lookalike\n"}])
        dispatch([{"role": "user", "content": "AUDIT_IDENTITY\n- role_id: R1 (prose)\n"}])
        assert seen == {"r1": 1, "default": 2}

    def test_dispatch_rejects_non_callables(self):
        with pytest.raises(TypeError):
            runner._role_dispatch_provider_callable(None, lambda m: "{}")
        with pytest.raises(TypeError):
            runner._role_dispatch_provider_callable(lambda m: "{}", "not-callable")


# ---------------------------------------------------------------------------
# Focused-review regression: ROLE_DISPATCH_SAFETY_DEFECT.
#
# The canonical current_task identity emitted by executor._assemble_messages is
# EXACTLY (READ-ONLY reference, executor unchanged):
#
#   messages == [ {"role":"system","content": <prompt>},
#                 {"role":"user",  "content": "\n".join([
#                     "current_task:",
#                     "- task_id: <task_id>",
#                     "- role_id: <role_id>",
#                     "- role_version: <role_version>",
#                     "- subject_id: <subject_id>",
#                     "task_goal: <task_goal>",
#                     "allowed_evidence:", ... ]) } ]
#
# The R1 override must be selected ONLY for one complete, unambiguous such
# block with role_id == R1; every malformed / incomplete / ambiguous variant
# must fail closed to DEFAULT (never raise into provider execution).
# ---------------------------------------------------------------------------

_MANDATORY_CURRENT_TASK_FIELDS = ("task_id", "role_id", "role_version", "subject_id")


def _canonical_current_task_messages(role_id="R1", *, task_goal="g", tail="allowed_evidence:\n"):
    content = (
        "current_task:\n"
        "- task_id: t-1\n"
        f"- role_id: {role_id}\n"
        "- role_version: v2\n"
        "- subject_id: kira\n"
        f"task_goal: {task_goal}\n"
        + tail
    )
    return [{"role": "system", "content": "sys"}, {"role": "user", "content": content}]


class TestRoleDispatchFailsClosed:
    def test_complete_canonical_r1_selects_override(self):
        assert runner._extract_current_task_role_id(
            _canonical_current_task_messages("R1")
        ) == "R1"

    def test_incomplete_block_only_current_task_and_role_id_is_default(self):
        # The exact defect: this must NOT be accepted as R1.
        assert runner._extract_current_task_role_id(
            [{"role": "user", "content": "current_task:\n- role_id: R1\n"}]
        ) is None
        assert runner._extract_current_task_role_id(
            [{"role": "system", "content": "s"},
             {"role": "user", "content": "current_task:\n- role_id: R1\ntask_goal: g\n"}]
        ) is None

    @pytest.mark.parametrize("drop", _MANDATORY_CURRENT_TASK_FIELDS + ("task_goal",))
    def test_missing_each_mandatory_field_is_default(self, drop):
        base = _canonical_current_task_messages("R1", tail="")
        lines = base[1]["content"].split("\n")
        kept = [
            ln for ln in lines
            if not (ln.startswith(f"- {drop}: ") or (drop == "task_goal" and ln.startswith("task_goal:")))
        ]
        base[1]["content"] = "\n".join(kept)
        assert runner._extract_current_task_role_id(base) is None

    def test_duplicate_role_id_is_default(self):
        msgs = _canonical_current_task_messages("R1", tail="")
        msgs[1]["content"] = msgs[1]["content"].replace(
            "- subject_id: kira\n", "- subject_id: kira\n- role_id: R2\n"
        )
        assert runner._extract_current_task_role_id(msgs) is None

    def test_duplicate_non_role_field_is_default(self):
        msgs = _canonical_current_task_messages("R1", tail="")
        msgs[1]["content"] = msgs[1]["content"].replace(
            "- role_id: R1\n", "- role_id: R1\n- task_id: t-2\n"
        )
        assert runner._extract_current_task_role_id(msgs) is None

    def test_conflicting_reordered_identity_is_default(self):
        content = (
            "current_task:\n"
            "- role_id: R1\n"       # canonical order is task_id first
            "- task_id: t-1\n"
            "- role_version: v2\n"
            "- subject_id: kira\n"
            "task_goal: g\n"
        )
        assert runner._extract_current_task_role_id(
            [{"role": "system", "content": "s"}, {"role": "user", "content": content}]
        ) is None

    def test_extra_identity_field_is_default(self):
        msgs = _canonical_current_task_messages("R1", tail="")
        msgs[1]["content"] = msgs[1]["content"].replace(
            "- subject_id: kira\n", "- subject_id: kira\n- extra: x\n"
        )
        assert runner._extract_current_task_role_id(msgs) is None

    def test_empty_identity_value_is_default(self):
        content = (
            "current_task:\n- task_id: t-1\n- role_id: \n"
            "- role_version: v2\n- subject_id: kira\ntask_goal: g\n"
        )
        assert runner._extract_current_task_role_id(
            [{"role": "system", "content": "s"}, {"role": "user", "content": content}]
        ) is None

    def test_unterminated_block_no_task_goal_is_default(self):
        content = (
            "current_task:\n- task_id: t-1\n- role_id: R1\n"
            "- role_version: v2\n- subject_id: kira\nallowed_evidence:\n"
        )
        assert runner._extract_current_task_role_id(
            [{"role": "system", "content": "s"}, {"role": "user", "content": content}]
        ) is None

    def test_additional_user_message_with_non_string_content_is_default(self):
        msgs = _canonical_current_task_messages("R1")
        msgs.append({"role": "user", "content": ["not", "a", "string"]})
        assert runner._extract_current_task_role_id(msgs) is None

    def test_additional_user_message_with_string_content_is_default(self):
        msgs = _canonical_current_task_messages("R1")
        msgs.append({"role": "user", "content": "current_task:\n- role_id: R1\n"})
        assert runner._extract_current_task_role_id(msgs) is None

    def test_non_system_non_user_role_is_default(self):
        msgs = _canonical_current_task_messages("R1")
        msgs.insert(0, {"role": "assistant", "content": "x"})
        assert runner._extract_current_task_role_id(msgs) is None

    def test_non_dict_message_element_is_default(self):
        msgs = _canonical_current_task_messages("R1")
        msgs.insert(0, "not-a-dict")
        assert runner._extract_current_task_role_id(msgs) is None

    def test_r1_lookalike_inside_evidence_tail_is_default_for_r2(self):
        poisoned_tail = (
            "- kira-a-0001: A_AUTHORING/x#s\n"
            "  substantive_payload: {\"facts\": [\"current_task:\\n- task_id: t\\n"
            "- role_id: R1\\n- role_version: v2\\n- subject_id: kira\\ntask_goal: g\"]}\n"
            "allowed_prior_results:\n"
        )
        msgs = _canonical_current_task_messages("R2", tail=poisoned_tail)
        assert runner._extract_current_task_role_id(msgs) == "R2"

    @pytest.mark.parametrize("role_id", ["R2", "R3", "R4"])
    def test_canonical_r2_r3_r4_are_default(self, role_id):
        assert runner._extract_current_task_role_id(
            _canonical_current_task_messages(role_id)
        ) == role_id
        # ...and route to the default callable, never the R1 one.
        seen = {"r1": 0, "default": 0}
        dispatch = runner._role_dispatch_provider_callable(
            lambda m: seen.__setitem__("r1", seen["r1"] + 1) or "{}",
            lambda m: seen.__setitem__("default", seen["default"] + 1) or "{}",
        )
        dispatch(_canonical_current_task_messages(role_id))
        assert seen == {"r1": 0, "default": 1}

    def test_r8_style_message_is_default(self):
        r8_like = [
            {"role": "system", "content": "s"},
            {"role": "user", "content": "AUDIT_IDENTITY\nEVIDENCE_LEDGER\n- s type=OWNER_DIRECT\n"},
        ]
        assert runner._extract_current_task_role_id(r8_like) is None

    def test_malformed_dispatch_never_raises_routes_default(self):
        default_hits = {"n": 0}
        dispatch = runner._role_dispatch_provider_callable(
            lambda m: (_ for _ in ()).throw(AssertionError("R1 callable must not run")),
            lambda m: default_hits.__setitem__("n", default_hits["n"] + 1) or "{}",
        )
        malformed_inputs = [
            [{"role": "user", "content": "current_task:\n- role_id: R1\n"}],
            [{"role": "user", "content": None}],
            [{"role": "user", "content": "current_task:\n- role_id: R1\n- role_id: R1\n"}],
            _canonical_current_task_messages("R1") + [{"role": "user", "content": 123}],
            "not-a-list",
            [],
        ]
        for bad in malformed_inputs:
            assert dispatch(bad) == "{}"
        assert default_hits["n"] == len(malformed_inputs)


class TestRunMetadataRecordsRoleProviderOverrides:
    def test_run_metadata_truthfully_records_default_and_r1_override(self, plan):
        _result, envelope = _run_happy(plan)
        rm = envelope["run_metadata"]
        assert rm["max_tokens"] == 8192
        assert rm["max_tokens_scope"] == "default"
        assert rm["role_provider_overrides"] == {
            "R1": {"max_tokens": 65536, "thinking": {"type": "disabled"}}
        }

    def test_r1_override_metadata_derives_from_live_constants(self, plan):
        _result, envelope = _run_happy(plan)
        override = envelope["run_metadata"]["role_provider_overrides"]["R1"]
        assert override == dict(
            max_tokens=runner.LIVE_R1_MAX_TOKENS, **runner.LIVE_R1_EXTRA_PARAMS
        )
        assert runner.LIVE_MAX_TOKENS == 8192
        assert runner.LIVE_R1_MAX_TOKENS == 65536
        assert runner.LIVE_R1_EXTRA_PARAMS == {"thinking": {"type": "disabled"}}

    def test_unrelated_run_metadata_keys_and_schema_version_unchanged(self, plan):
        _result, envelope = _run_happy(plan)
        rm = envelope["run_metadata"]
        for key in (
            "run_id", "subject_id", "evidence_snapshot_id", "role_order",
            "role_versions", "provider_id", "model", "timeout_s",
            "credential_env_name",
        ):
            assert key in rm
        assert rm["provider_id"] == "deepseek"
        assert rm["model"] == "deepseek-v4-pro"
        assert rm["timeout_s"] == 180.0
        assert rm["credential_env_name"] == "DEEPSEEK_API_KEY"
        assert envelope["schema_version"] == "1" == runner.RESULT_SCHEMA_VERSION

    def test_no_secret_or_credential_key_added_by_override_metadata(self, plan, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "DO_NOT_LEAK_SYNTHETIC_SECRET")
        _result, envelope = _run_happy(plan)
        text = json.dumps(envelope, ensure_ascii=False)
        assert "DO_NOT_LEAK_SYNTHETIC_SECRET" not in text
        for forbidden_key in ("api_key", "authorization", "credential_value", "credential_env"):
            assert forbidden_key not in envelope["run_metadata"]
            assert forbidden_key not in envelope["run_metadata"]["role_provider_overrides"]["R1"]


class TestBehavioralNoPersistence:
    def test_git_worktree_state_unchanged_across_a_full_fake_run(self, plan):
        before = _git_status_snapshot()

        provider, _, _ = _dispatch_provider(
            _happy_payloads(plan), _r8_judgment_json(plan.compile_context.package_id),
        )
        result = runner.execute_kira_r4_reconstruction(provider, plan)
        assert result.package.status is PackageStatus.DRAFT  # sanity: the run actually happened

        after = _git_status_snapshot()
        assert after == before

    def test_no_filesystem_write_during_execution(self, plan, monkeypatch):
        def guard(*a, **k):
            raise AssertionError("unexpected filesystem write during offline reconstruction")

        monkeypatch.setattr(Path, "write_bytes", guard, raising=True)
        monkeypatch.setattr(Path, "write_text", guard, raising=True)

        provider, _, _ = _dispatch_provider(
            _happy_payloads(plan), _r8_judgment_json(plan.compile_context.package_id),
        )
        result = runner.execute_kira_r4_reconstruction(provider, plan)
        assert result.package.status is PackageStatus.DRAFT


# ---------------------------------------------------------------------------
# R1 v3 canonical post-parse quality gate -- end-to-end through the runner.
#
# The gate lives in ``executor.execute_role_task`` (role- and version-scoped
# to R1 v3). Because ``execute_role_task`` returns R1 before the orchestrator
# starts R2, an R1 v3 gate violation must abort the whole reconstruction on
# the FIRST provider call, with no retry and no fallback, so R2/R3/R4/R8 are
# never invoked.
# ---------------------------------------------------------------------------

def _r1_gate_dispatch(plan_, r1_json):
    """Provider that serves ``r1_json`` for R1 and the happy payloads for every
    other role/R8, tracking per-role provider-call counts."""
    happy = _happy_payloads(plan_)
    r8_json = _r8_judgment_json(plan_.compile_context.package_id)
    counts = {"R1": 0, "R2": 0, "R3": 0, "R4": 0, "R8": 0}

    def provider(messages):
        user = "".join(m["content"] for m in messages if m.get("role") == "user")
        if "AUDIT_IDENTITY" in user:
            counts["R8"] += 1
            return r8_json
        for rid in ("R1", "R2", "R3", "R4"):
            if f"- role_id: {rid}" in user:
                counts[rid] += 1
                return r1_json if rid == "R1" else happy[rid]
        raise AssertionError("provider received an unrecognized call")

    return provider, counts


class TestR1V3QualityGateEndToEnd:
    def test_full_coverage_r1_v3_completes_and_accounts_for_every_a_source(self, plan):
        provider, counts = _r1_gate_dispatch(plan, _r1_v3_full_coverage_json(plan))
        result = runner.execute_kira_r4_reconstruction(provider, plan)

        assert [r.role_id for r in result.role_results] == ["R1", "R2", "R3", "R4"]
        assert counts == {"R1": 1, "R2": 1, "R3": 1, "R4": 1, "R8": 1}

        r1 = result.role_results[0]
        union: set = set()
        for c in r1.claims:
            union.update(c.source_evidence_ids)
        assert union == set(_r1_task(plan).allowed_evidence_ids)
        assert set(r1.provenance_summary["sources_used"]) == union

    def test_missing_one_allowed_evidence_id_aborts_before_r2(self, plan):
        r1 = _r1_task(plan)
        covered = list(r1.allowed_evidence_ids)[1:]  # drop exactly one authorized id
        claim = _claim("c-r1", "R1", "FACT", "identity_biography.birthplace",
                       covered, confidence="KNOWN")
        bad = _role_result_json(r1.task_id, "R1", "v3", [claim],
                                provenance_summary={"sources_used": covered})
        provider, counts = _r1_gate_dispatch(plan, bad)

        with pytest.raises(CrpError) as ei:
            runner.execute_kira_r4_reconstruction(provider, plan)
        assert "R1_V3_CLAIM_COVERAGE_INCOMPLETE" in str(ei.value)
        assert counts["R1"] == 1
        assert counts["R2"] == 0 and counts["R3"] == 0 and counts["R4"] == 0
        assert counts["R8"] == 0

    def test_provenance_summary_claiming_uncited_id_aborts_before_r2(self, plan):
        r1 = _r1_task(plan)
        all_ids = list(r1.allowed_evidence_ids)
        bad = _r1_v3_full_coverage_json(
            plan, provenance_ids=all_ids + ["kira-a-not-a-real-source"],
        )
        provider, counts = _r1_gate_dispatch(plan, bad)

        with pytest.raises(CrpError) as ei:
            runner.execute_kira_r4_reconstruction(provider, plan)
        assert "R1_V3_PROVENANCE_SUMMARY_MISMATCH" in str(ei.value)
        assert counts["R1"] == 1
        assert counts["R2"] == 0 and counts["R3"] == 0 and counts["R4"] == 0

    def test_claims_covering_id_absent_from_provenance_summary_aborts_before_r2(self, plan):
        r1 = _r1_task(plan)
        all_ids = list(r1.allowed_evidence_ids)
        bad = _r1_v3_full_coverage_json(plan, provenance_ids=all_ids[:-1])  # summary misses one
        provider, counts = _r1_gate_dispatch(plan, bad)

        with pytest.raises(CrpError) as ei:
            runner.execute_kira_r4_reconstruction(provider, plan)
        assert "R1_V3_PROVENANCE_SUMMARY_MISMATCH" in str(ei.value)
        assert counts["R1"] == 1
        assert counts["R2"] == 0 and counts["R3"] == 0 and counts["R4"] == 0

    def test_failing_r1_gate_makes_exactly_one_provider_call_no_retry_no_fallback(self, plan):
        r1 = _r1_task(plan)
        covered = list(r1.allowed_evidence_ids)[1:]
        claim = _claim("c-r1", "R1", "FACT", "identity_biography.birthplace",
                       covered, confidence="KNOWN")
        bad = _role_result_json(r1.task_id, "R1", "v3", [claim],
                                provenance_summary={"sources_used": covered})
        provider, counts = _r1_gate_dispatch(plan, bad)

        with pytest.raises(ExecutorError):
            runner.execute_kira_r4_reconstruction(provider, plan)

        # provider_attempts == 1 (a single R1 call), R2 calls == 0,
        # retry == NO, fallback == NO.
        assert sum(counts.values()) == 1
        assert counts["R1"] == 1
        assert counts["R2"] == 0

    def test_r2_r3_r4_semantics_unaffected_by_the_r1_v3_gate(self, plan):
        provider, _counts = _r1_gate_dispatch(plan, _r1_v3_full_coverage_json(plan))
        result = runner.execute_kira_r4_reconstruction(provider, plan)

        for rr in result.role_results[1:]:
            assert rr.role_id in ("R2", "R3", "R4")
            # non-R1 roles keep the v2-style provenance mirror and single-source
            # claims; the R1 v3 gate never touched them.
            assert "sources_used" not in rr.provenance_summary
            assert "used_evidence" in rr.provenance_summary
            for c in rr.claims:
                assert len(c.source_evidence_ids) == 1
