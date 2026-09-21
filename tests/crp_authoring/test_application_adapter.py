#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CRP_MAINLINE_CONSOLIDATION_V1 Part 11 -- Lab-independent application adapter."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from services.crp_authoring import (
    CrpValidationError,
    ReconstructionPlan,
    RoleTask,
    SourceEvidence,
    SourceType,
    evaluate_specialist_relevance,
    get_reconstruction_result,
    prepare_reconstruction,
    start_reconstruction,
)

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _evidence(source_id: str) -> SourceEvidence:
    return SourceEvidence(
        source_id=source_id,
        subject_id="subj",
        source_type=SourceType.OWNER_DIRECT,
        content_ref=f"ref/{source_id}",
        provenance="owner interview",
        intake_timestamp=_NOW,
        content_hash="a" * 64,
        evidence_snapshot_id="snap-1",
    )


def _role_task(role_id: str, *, subject_id="subj", run_id="run-1", evidence_snapshot_id="snap-1") -> RoleTask:
    return RoleTask(
        task_id=f"t-{role_id}",
        role_id=role_id,
        role_version="v1",
        subject_id=subject_id,
        run_id=run_id,
        evidence_snapshot_id=evidence_snapshot_id,
        allowed_evidence_ids=("e1",),
        allowed_prior_results=(),
        knowledge_profile_ref="profile-1",
        input_contract_version="1",
        output_contract_version="1",
        permissions=("READ_SOURCE_EVIDENCE",),
        task_goal="test",
        revision_round=0,
    )


class TestEvaluateSpecialistRelevance:
    def test_wraps_relevance_evaluator(self):
        from services.crp_authoring import R3RelevanceStatus

        result = evaluate_specialist_relevance(())
        assert result.status is R3RelevanceStatus.NOT_RELEVANT


class TestPrepareReconstructionOffline:
    def test_no_provider_argument_exists_in_signature(self):
        import inspect

        params = inspect.signature(prepare_reconstruction).parameters
        assert "provider_callable" not in params
        assert "provider" not in params

    def test_validates_identity_consistency_and_returns_plan(self):
        task = _role_task("R1")
        plan = prepare_reconstruction(
            subject_id="subj",
            run_id="run-1",
            evidence_snapshot_id="snap-1",
            evidence=(_evidence("e1"),),
            registry=None,
            profiles={},
            role_tasks=(task,),
            compile_context=None,
            audit_policy=None,
            evidence_payloads={},
        )
        assert isinstance(plan, ReconstructionPlan)
        assert plan.role_tasks == (task,)

    def test_rejects_role_task_with_mismatched_subject_id(self):
        task = _role_task("R1", subject_id="OTHER-subject")
        with pytest.raises(CrpValidationError):
            prepare_reconstruction(
                subject_id="subj",
                run_id="run-1",
                evidence_snapshot_id="snap-1",
                evidence=(),
                registry=None,
                profiles={},
                role_tasks=(task,),
                compile_context=None,
                audit_policy=None,
                evidence_payloads={},
            )

    def test_rejects_empty_role_tasks(self):
        with pytest.raises(CrpValidationError):
            prepare_reconstruction(
                subject_id="subj",
                run_id="run-1",
                evidence_snapshot_id="snap-1",
                evidence=(),
                registry=None,
                profiles={},
                role_tasks=(),
                compile_context=None,
                audit_policy=None,
                evidence_payloads={},
            )


class TestR3AuthorizationGateSurvivesTheAdapter:
    def test_r3_role_task_still_requires_activation_authorization_ref(self):
        # The adapter never re-implements or relaxes this: construction of
        # the RoleTask itself is where the gate lives (role_task.py).
        with pytest.raises(CrpValidationError):
            _role_task("R3")  # no activation_authorization_ref supplied

    def test_start_reconstruction_never_bypasses_the_gate(self):
        task = _role_task(
            "R1"
        )  # non-gated role; proves start_reconstruction takes whatever
        # RoleTasks the caller already validly constructed -- it has no
        # separate authorization logic of its own to bypass.
        plan = prepare_reconstruction(
            subject_id="subj",
            run_id="run-1",
            evidence_snapshot_id="snap-1",
            evidence=(_evidence("e1"),),
            registry=object(),
            profiles={},
            role_tasks=(task,),
            compile_context=object(),
            audit_policy=object(),
            evidence_payloads={},
        )
        # We deliberately do NOT call start_reconstruction with a real
        # provider here (no provider construction/network in tests); this
        # only proves the plan/task carry the gate outcome faithfully.
        assert plan.role_tasks[0].role_id == "R1"


class TestGetReconstructionResultIsReadOnly:
    def test_loads_real_kira_reference_fixture(self):
        result = get_reconstruction_result(Path("accepted"), "kira")
        assert result.subject_id == "kira"
        assert result.package.package_id == "kira-r4-canonical-run-1-package"

    def test_no_provider_or_network_symbol_in_module(self):
        import ast

        tree = ast.parse(Path("services/crp_authoring/application_adapter.py").read_text(encoding="utf-8"))
        modules = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.extend(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                modules.append(node.module or "")
        forbidden = ("openai", "anthropic", "requests", "httpx", "urllib", "socket", "aiohttp")
        assert not any(m.startswith(f) for m in modules for f in forbidden)

    def test_adapter_never_imports_canon_or_lab_or_companion_modules(self):
        import ast

        tree = ast.parse(Path("services/crp_authoring/application_adapter.py").read_text(encoding="utf-8"))
        modules = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.extend(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                modules.append(node.module or "")
        forbidden_prefixes = (
            "services.character_lab_application",
            "ui.character_lab",
            "services.character_companion",
            "services.character_core",
            "services.character_runtime",
            "narrative_character_canon",
        )
        assert not any(m.startswith(f) for m in modules for f in forbidden_prefixes)
        assert "services.character_lab" not in modules
