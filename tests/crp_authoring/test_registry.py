#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CRP MVP S2A -- RoleRegistryEntry / RoleRegistry tests."""

from __future__ import annotations

import pytest

from services.crp_authoring import (
    ExecutionType,
    RoleRegistry,
    RoleStatus,
)

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