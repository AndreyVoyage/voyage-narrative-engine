#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CHARACTER_LAB_CRP_APPLICATION_WIRING_V1 -- application-service wiring tests.

Proves ``CharacterLabApplicationService`` connects to
``services.crp_authoring.application_adapter`` by pure delegation (no CRP
domain logic reimplemented, no provider constructed, no Canon/KIRA-fixture
mutation). Fully offline.
"""

from __future__ import annotations

import ast
import hashlib
from datetime import datetime, timezone
from pathlib import Path

import pytest

import services.character_lab_application.service as lab_service_module
from services.character_lab_application import CharacterLabApplicationError, CRP_VALIDATION_FAILED
from services.crp_authoring import (
    R3RelevanceStatus,
    RoleTask,
    SourceEvidence,
    SourceType,
)
from services.crp_authoring.application_adapter import ReconstructionPlan
from services.crp_authoring.errors import CrpValidationError

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
_ACCEPTED_ROOT = Path("accepted")
_EXPECTED_PACKAGE_ID = "kira-r4-canonical-run-1-package"
_EXPECTED_PACKAGE_HASH = "e26f83dafa26e61af82f29b654b592300c8f3f7bd295d07bd4d2b6527ae3eebd"


def _evidence(source_id: str, metadata: dict | None = None) -> SourceEvidence:
    return SourceEvidence(
        source_id=source_id,
        subject_id="subj",
        source_type=SourceType.OWNER_DIRECT,
        content_ref=f"ref/{source_id}",
        provenance="owner interview",
        intake_timestamp=_NOW,
        content_hash="a" * 64,
        evidence_snapshot_id="snap-1",
        metadata=metadata or {},
    )


def _role_task(role_id: str, **kw) -> RoleTask:
    defaults = dict(
        task_id=f"t-{role_id}",
        role_id=role_id,
        role_version="v1",
        subject_id="subj",
        run_id="run-1",
        evidence_snapshot_id="snap-1",
        allowed_evidence_ids=("e1",),
        allowed_prior_results=(),
        knowledge_profile_ref="profile-1",
        input_contract_version="1",
        output_contract_version="1",
        permissions=("READ_SOURCE_EVIDENCE",),
        task_goal="test",
        revision_round=0,
    )
    defaults.update(kw)
    return RoleTask(**defaults)


class TestLabCanAccessCrpFacade:
    def test_service_exposes_all_four_crp_operations(self, service):
        assert callable(service.evaluate_specialist_relevance)
        assert callable(service.prepare_reconstruction)
        assert callable(service.start_reconstruction)
        assert callable(service.get_reconstruction_result)


class TestRelevanceDelegation:
    def test_delegates_to_crp_relevance_boundary_not_relevant(self, service):
        result = service.evaluate_specialist_relevance(())
        assert result.status is R3RelevanceStatus.NOT_RELEVANT

    def test_explicit_intimacy_evidence_is_relevant(self, service):
        result = service.evaluate_specialist_relevance((_evidence("e1", {"explicit_sexual_trait": True}),))
        assert result.status is R3RelevanceStatus.RELEVANT_REQUIRES_AUTHORIZATION
        assert result.evidence_refs == ("e1",)

    def test_appearance_only_evidence_does_not_trigger_relevance(self, service):
        evidence = (
            _evidence(
                "e1",
                {
                    "gender": "female",
                    "attractiveness_note": "considered attractive",
                    "appearance_summary": "tall, athletic",
                },
            ),
        )
        result = service.evaluate_specialist_relevance(evidence)
        assert result.status is R3RelevanceStatus.NOT_RELEVANT

    def test_relevance_result_carries_no_authorization_capability(self, service):
        result = service.evaluate_specialist_relevance((_evidence("e1", {"explicit_sexual_trait": True}),))
        assert set(result.__dataclass_fields__) == {"status", "evidence_refs", "reason_codes"}
        assert not hasattr(result, "activation_authorization_ref")

    def test_delegation_is_pure_passthrough_no_reimplementation(self, service, monkeypatch):
        sentinel = object()
        called_with = {}

        def fake(evidence):
            called_with["evidence"] = evidence
            return sentinel

        monkeypatch.setattr(lab_service_module, "_crp_evaluate_specialist_relevance", fake)
        evidence = (_evidence("e1"),)
        result = service.evaluate_specialist_relevance(evidence)
        assert result is sentinel
        assert called_with["evidence"] is evidence

    def test_crp_validation_error_is_wrapped_not_swallowed(self, service):
        with pytest.raises(CharacterLabApplicationError) as excinfo:
            service.evaluate_specialist_relevance(({"not": "evidence"},))
        assert excinfo.value.code == CRP_VALIDATION_FAILED
        assert isinstance(excinfo.value.__cause__, CrpValidationError)


class TestR3AuthorizationBoundary:
    def test_r3_without_authorization_is_fail_closed(self):
        with pytest.raises(CrpValidationError):
            _role_task("R3")  # no activation_authorization_ref

    def test_explicit_authorization_passes_through_lab_boundary(self, service):
        task = _role_task("R3", activation_authorization_ref="CRP-OD-R4-KIRA-R3-01")
        plan = service.prepare_reconstruction(
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
        assert plan.role_tasks[0].role_id == "R3"
        assert plan.role_tasks[0].activation_authorization_ref == "CRP-OD-R4-KIRA-R3-01"

    def test_relevance_never_creates_authorization_for_a_role_task(self, service):
        result = service.evaluate_specialist_relevance((_evidence("e1", {"explicit_sexual_trait": True}),))
        assert result.status is R3RelevanceStatus.RELEVANT_REQUIRES_AUTHORIZATION
        # A RELEVANT verdict alone still does not let an R3 RoleTask be built
        # without an explicit, separately-supplied authorization ref.
        with pytest.raises(CrpValidationError):
            _role_task("R3")


class TestPrepareReconstructionDelegation:
    def test_delegates_rather_than_reimplementing(self, service):
        task = _role_task("R1")
        plan = service.prepare_reconstruction(
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

    def test_pure_passthrough_via_monkeypatch(self, service, monkeypatch):
        sentinel = object()
        captured = {}

        def fake(**kwargs):
            captured.update(kwargs)
            return sentinel

        monkeypatch.setattr(lab_service_module, "_crp_prepare_reconstruction", fake)
        result = service.prepare_reconstruction(
            subject_id="subj",
            run_id="run-1",
            evidence_snapshot_id="snap-1",
            evidence=(),
            registry=None,
            profiles={},
            role_tasks=(_role_task("R1"),),
            compile_context=None,
            audit_policy=None,
            evidence_payloads={},
        )
        assert result is sentinel
        assert captured["subject_id"] == "subj"

    def test_identity_mismatch_fails_closed_through_lab(self, service):
        task = _role_task("R1", subject_id="OTHER")
        with pytest.raises(CharacterLabApplicationError) as excinfo:
            service.prepare_reconstruction(
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
        assert excinfo.value.code == CRP_VALIDATION_FAILED


class TestStartReconstructionDelegation:
    def test_pure_passthrough_via_monkeypatch_no_reimplementation(self, service, monkeypatch):
        sentinel = object()
        captured = {}

        def fake(plan, provider_callable):
            captured["plan"] = plan
            captured["provider_callable"] = provider_callable
            return sentinel

        monkeypatch.setattr(lab_service_module, "_crp_start_reconstruction", fake)

        plan = object()  # opaque -- proves the Lab layer never inspects it

        def fake_provider(*args, **kwargs):
            raise AssertionError("no real provider must ever be invoked in tests")

        result = service.start_reconstruction(plan, fake_provider)
        assert result is sentinel
        assert captured["plan"] is plan
        assert captured["provider_callable"] is fake_provider

    def test_invalid_plan_fails_closed(self, service):
        with pytest.raises(CharacterLabApplicationError) as excinfo:
            service.start_reconstruction("not-a-plan", lambda *a, **k: None)
        assert excinfo.value.code == CRP_VALIDATION_FAILED


class TestGetReconstructionResultDelegation:
    def test_loads_real_kira_reference_fixture_read_only(self, service):
        result = service.get_reconstruction_result(_ACCEPTED_ROOT, "kira")
        assert result.subject_id == "kira"
        assert result.package.package_id == _EXPECTED_PACKAGE_ID

    def test_pure_passthrough_via_monkeypatch(self, service, monkeypatch):
        sentinel = object()
        captured = {}

        def fake(root, subject_id):
            captured["root"] = root
            captured["subject_id"] = subject_id
            return sentinel

        monkeypatch.setattr(lab_service_module, "_crp_get_reconstruction_result", fake)
        result = service.get_reconstruction_result(_ACCEPTED_ROOT, "kira")
        assert result is sentinel
        assert captured["subject_id"] == "kira"

    def test_missing_subject_fails_closed(self, service):
        with pytest.raises(CharacterLabApplicationError) as excinfo:
            service.get_reconstruction_result(_ACCEPTED_ROOT, "does-not-exist")
        assert excinfo.value.code == CRP_VALIDATION_FAILED


class TestNoCanonOrKiraFixtureMutation:
    def test_kira_fixture_files_are_byte_identical_before_and_after_lab_access(self, service):
        acceptance_path = _ACCEPTED_ROOT / "kira" / "ACCEPTANCE.json"
        candidate_path = _ACCEPTED_ROOT / "kira" / "source_candidate.json"
        before = (
            hashlib.sha256(acceptance_path.read_bytes()).hexdigest(),
            hashlib.sha256(candidate_path.read_bytes()).hexdigest(),
        )
        result = service.get_reconstruction_result(_ACCEPTED_ROOT, "kira")
        assert result.acceptance.package_hash == _EXPECTED_PACKAGE_HASH
        after = (
            hashlib.sha256(acceptance_path.read_bytes()).hexdigest(),
            hashlib.sha256(candidate_path.read_bytes()).hexdigest(),
        )
        assert before == after

    def test_lab_service_never_imports_character_canon_write_path(self, service):
        # get_character_detail/list_characters already prove read-only Canon
        # access elsewhere; this asserts the new CRP methods add no Canon
        # import of their own.
        import inspect

        src = inspect.getsource(lab_service_module)
        assert "narrative_character_canon" not in src
        assert ".write(" not in src


class TestOfflineOnly:
    def test_no_provider_or_network_symbol_in_service_module(self):
        tree = ast.parse(Path("services/character_lab_application/service.py").read_text(encoding="utf-8"))
        modules = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.extend(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                modules.append(node.module or "")
        forbidden = ("openai", "anthropic", "requests", "httpx", "urllib", "socket", "aiohttp", "deepseek")
        assert not any(m.startswith(f) for m in modules for f in forbidden)


class TestImportFirewall:
    """CRP_MAINLINE_CONSOLIDATION_V1 dependency direction:
    character_lab_application -> crp_authoring.application_adapter -> CRP
    internals. This package must import CRP only through that one module."""

    def _modules_in(self, py_file: Path) -> list[str]:
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        modules: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.extend(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                modules.append(node.module or "")
        return modules

    def test_only_application_adapter_is_imported_from_crp_authoring(self):
        violations = []
        for py_file in sorted(Path("services/character_lab_application").rglob("*.py")):
            for m in self._modules_in(py_file):
                if m.startswith("services.crp_authoring") and m != "services.crp_authoring.application_adapter":
                    violations.append(f"{py_file}: imports {m}")
        assert not violations, f"CRP imports bypassing application_adapter: {violations}"

    def test_no_provider_client_or_registry_internals_or_prompt_modules(self):
        forbidden = (
            "tools.crp_provider_adapter",
            "tools.crp_kira_r4_runner",
            "roles.vnext",
            "openai",
            "anthropic",
            "deepseek",
        )
        violations = []
        for py_file in sorted(Path("services/character_lab_application").rglob("*.py")):
            for m in self._modules_in(py_file):
                if any(m == f or m.startswith(f + ".") for f in forbidden):
                    violations.append(f"{py_file}: imports {m}")
        assert not violations, f"Forbidden internal imports: {violations}"

    def test_ui_character_lab_still_does_not_import_crp_authoring(self):
        # Redundant confirmation of the existing tests/ui/character_lab/
        # test_import_firewall.py invariant, scoped specifically to CRP.
        violations = []
        for py_file in sorted(Path("ui/character_lab").rglob("*.py")):
            for m in self._modules_in(py_file):
                if m.startswith("services.crp_authoring"):
                    violations.append(f"{py_file}: imports {m}")
        assert not violations, f"UI imports CRP directly: {violations}"


class TestNoUIFunctionalityAdded:
    def test_ui_character_lab_files_unchanged_set(self):
        # This task is application-layer only; confirm the known UI file set
        # is exactly what Foundation published (no new UI files introduced).
        expected = {
            "ui/character_lab/__init__.py",
            "ui/character_lab/__main__.py",
            "ui/character_lab/app.py",
            "ui/character_lab/main_window.py",
        }
        actual = {str(p).replace("\\", "/") for p in Path("ui/character_lab").rglob("*.py")}
        assert actual == expected
