#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CRP MVP S2A/Slice4 -- RoleRegistryEntry / RoleRegistry / YAML loader tests."""

from __future__ import annotations

import pytest

from services.crp_authoring import (
    ExecutionType,
    RoleRegistry,
    RoleStatus,
)
from services.crp_authoring.registry import load_role_registry
from services.crp_authoring.errors import CrpValidationError

from tests.crp_authoring.conftest import make_registry_entry


class TestRegistryEntry:
    def test_inactive_entry_constructible(self) -> None:
        entry = make_registry_entry(role_id="R3", status=RoleStatus.INACTIVE)
        assert entry.status is RoleStatus.INACTIVE

    def test_requires_activation_gate(self) -> None:
        with pytest.raises(Exception):
            make_registry_entry(activation_gate="")

    def test_execution_types(self) -> None:
        assert make_registry_entry(execution_type=ExecutionType.LLM_ROLE).execution_type is ExecutionType.LLM_ROLE


class TestRoleRegistry:
    def test_get_by_role_id(self) -> None:
        r1 = make_registry_entry(role_id="R1")
        r2 = make_registry_entry(role_id="R2")
        registry = RoleRegistry((r1, r2))
        assert registry.get("R2") is r2

    def test_absent_returns_none(self) -> None:
        registry = RoleRegistry((make_registry_entry(role_id="R1"),))
        assert registry.get("R8") is None

    def test_duplicate_role_id_rejected(self) -> None:
        with pytest.raises(Exception):
            RoleRegistry((make_registry_entry(role_id="R1"), make_registry_entry(role_id="R1")))

    def test_no_auto_discovery_and_no_latest(self) -> None:
        # The registry only holds explicitly-constructed entries; role
        # resolution is exact-version, not "latest".
        registry = RoleRegistry((make_registry_entry(role_id="R1", version="v1"),))
        assert "R2" not in registry
        assert "R1" in registry


class TestExactVersionResolve:
    def test_resolve_exact_version(self) -> None:
        registry = RoleRegistry((make_registry_entry(role_id="R1", version="v1"),))
        assert registry.resolve("R1", "v1").role_id == "R1"

    def test_resolve_unknown_role_fails_closed(self) -> None:
        registry = RoleRegistry((make_registry_entry(role_id="R1", version="v1"),))
        with pytest.raises(CrpValidationError):
            registry.resolve("R2", "v1")

    def test_resolve_wrong_version_fails_closed(self) -> None:
        registry = RoleRegistry((make_registry_entry(role_id="R1", version="v1"),))
        with pytest.raises(CrpValidationError):
            registry.resolve("R1", "v2")

    def test_resolve_no_latest_fallback(self) -> None:
        # A version mismatch must not fall back to the registered entry.
        registry = RoleRegistry((make_registry_entry(role_id="R1", version="v1"),))
        with pytest.raises(CrpValidationError):
            registry.resolve("R1", "latest")


class TestDeclarativeRegistryLoad:
    def test_registry_loads(self) -> None:
        registry = load_role_registry()
        # All eight roles present, registered at their authoritative v1 pin.
        assert {e.role_id for e in registry} == {
            "R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8",
        }

    def test_r1_resolves_exact_version(self) -> None:
        registry = load_role_registry()
        entry = registry.resolve("R1", "v2")
        assert entry.status is RoleStatus.ACTIVE
        assert entry.execution_type is ExecutionType.LLM_ROLE

    def test_r2_resolves_exact_version(self) -> None:
        registry = load_role_registry()
        entry = registry.resolve("R2", "v2")
        assert entry.status is RoleStatus.ACTIVE
        assert entry.execution_type is ExecutionType.LLM_ROLE

    def test_r1_old_version_not_resolvable(self) -> None:
        # The registry stores only the current authoritative pin (no full
        # history); the old v1 file remains on disk but is not a resolvable
        # registry entry. No latest-wins, no fallback.
        registry = load_role_registry()
        with pytest.raises(CrpValidationError):
            registry.resolve("R1", "v1")

    def test_r2_old_version_not_resolvable(self) -> None:
        registry = load_role_registry()
        with pytest.raises(CrpValidationError):
            registry.resolve("R2", "v1")

    def test_r1_predecessor_version_recorded(self) -> None:
        registry = load_role_registry()
        assert registry.get("R1").predecessor_version == "v1"

    def test_r2_predecessor_version_recorded(self) -> None:
        registry = load_role_registry()
        assert registry.get("R2").predecessor_version == "v1"

    def test_r4_resolves_exact_version(self) -> None:
        registry = load_role_registry()
        entry = registry.resolve("R4", "v1")
        assert entry.status is RoleStatus.ACTIVE
        assert entry.execution_type is ExecutionType.LLM_ROLE

    def test_r3_gated_inactive_by_default(self) -> None:
        registry = load_role_registry()
        entry = registry.get("R3")
        assert entry is not None
        assert entry.status is RoleStatus.INACTIVE
        assert entry.activation_gate != ""

    def test_r5_cannot_become_executable_via_registry(self) -> None:
        registry = load_role_registry()
        entry = registry.get("R5")
        assert entry is not None
        assert entry.status is RoleStatus.INACTIVE

    def test_r8_not_executable_before_implementation(self) -> None:
        registry = load_role_registry()
        entry = registry.get("R8")
        assert entry is not None
        # R8 is ratified but not implemented; the registry must not make it
        # immediately runnable as a ready ACTIVE role.
        assert entry.status is not RoleStatus.ACTIVE

    def test_r6_and_r7_represented_without_llm_prompt(self) -> None:
        registry = load_role_registry()
        r6 = registry.get("R6")
        r7 = registry.get("R7")
        assert r6.execution_type is ExecutionType.DETERMINISTIC_FUNCTION
        assert r7.execution_type is ExecutionType.DETERMINISTIC_FUNCTION

    def test_defines_expected_orders_canonical_active_set(self) -> None:
        registry = load_role_registry()
        active = {e.role_id for e in registry if e.status is RoleStatus.ACTIVE}
        assert active == {"R1", "R2", "R4", "R6"}


class TestDeclarativeRegistryFailClosed:
    def test_missing_file_fails_closed(self, tmp_path) -> None:
        missing = tmp_path / "nope.yaml"
        with pytest.raises(CrpValidationError):
            load_role_registry(str(missing))

    def test_malformed_registry_fails_closed(self, tmp_path) -> None:
        bad = tmp_path / "bad.yaml"
        bad.write_text("roles: [\n  - this is broken", encoding="utf-8")
        with pytest.raises(CrpValidationError):
            load_role_registry(str(bad))

    def test_duplicate_role_version_fails_closed(self, tmp_path) -> None:
        dup = tmp_path / "dup.yaml"
        dup.write_text(
            "roles:\n"
            "  - role_id: R1\n"
            "    display_name: A\n"
            "    version: v1\n"
            "    status: ACTIVE\n"
            "    execution_type: LLM_ROLE\n"
            "    prompt_ref: roles/vnext/ROLE_1_EVIDENCE_INTERVIEWER_v1_PROMPT.md\n"
            "    knowledge_profile_ref: profile-r1\n"
            "    input_contract_ref: role_task_v1\n"
            "    output_contract_ref: role_result_v1\n"
            "    permissions: []\n"
            "    activation_gate: gate-1\n"
            "  - role_id: R1\n"
            "    display_name: B\n"
            "    version: v1\n"
            "    status: INACTIVE\n"
            "    execution_type: LLM_ROLE\n"
            "    prompt_ref: roles/vnext/ROLE_1_EVIDENCE_INTERVIEWER_v1_PROMPT.md\n"
            "    knowledge_profile_ref: profile-r1\n"
            "    input_contract_ref: role_task_v1\n"
            "    output_contract_ref: role_result_v1\n"
            "    permissions: []\n"
            "    activation_gate: gate-2\n",
            encoding="utf-8",
        )
        with pytest.raises(CrpValidationError):
            load_role_registry(str(dup))

    def test_unknown_status_fails_closed(self, tmp_path) -> None:
        bad = tmp_path / "status.yaml"
        bad.write_text(
            "roles:\n"
            "  - role_id: R1\n"
            "    display_name: A\n"
            "    version: v1\n"
            "    status: FOO\n"
            "    execution_type: LLM_ROLE\n"
            "    prompt_ref: p.md\n"
            "    knowledge_profile_ref: profile-r1\n"
            "    input_contract_ref: role_task_v1\n"
            "    output_contract_ref: role_result_v1\n"
            "    permissions: []\n"
            "    activation_gate: gate-1\n",
            encoding="utf-8",
        )
        with pytest.raises(CrpValidationError):
            load_role_registry(str(bad))

    def test_forbidden_latest_version_marker_fails_closed(self, tmp_path) -> None:
        bad = tmp_path / "latest.yaml"
        bad.write_text(
            "roles:\n"
            "  - role_id: R1\n"
            "    display_name: A\n"
            "    version: latest\n"
            "    status: ACTIVE\n"
            "    execution_type: LLM_ROLE\n"
            "    prompt_ref: roles/vnext/ROLE_1_EVIDENCE_INTERVIEWER_v1_PROMPT.md\n"
            "    knowledge_profile_ref: profile-r1\n"
            "    input_contract_ref: role_task_v1\n"
            "    output_contract_ref: role_result_v1\n"
            "    permissions: []\n"
            "    activation_gate: gate-1\n",
            encoding="utf-8",
        )
        with pytest.raises(CrpValidationError):
            load_role_registry(str(bad))

    def test_active_llm_role_missing_prompt_fails_closed(self, tmp_path) -> None:
        bad = tmp_path / "missing_prompt.yaml"
        bad.write_text(
            "roles:\n"
            "  - role_id: R1\n"
            "    display_name: A\n"
            "    version: v1\n"
            "    status: ACTIVE\n"
            "    execution_type: LLM_ROLE\n"
            "    prompt_ref: roles/vnext/DOES_NOT_EXIST_PROMPT.md\n"
            "    knowledge_profile_ref: profile-r1\n"
            "    input_contract_ref: role_task_v1\n"
            "    output_contract_ref: role_result_v1\n"
            "    permissions: []\n"
            "    activation_gate: gate-1\n",
            encoding="utf-8",
        )
        with pytest.raises(CrpValidationError):
            load_role_registry(str(bad))