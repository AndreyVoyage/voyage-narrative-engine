#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CRP MVP S2A -- Role Registry mechanism (entry contract + in-memory container).

S2A builds the *mechanism* only; the real populated YAML data file
(``roles/vnext/CRP_ROLE_REGISTRY_v1.yaml``) is deferred to S2B together with
the actual vNext prompts it would reference. The registry never auto-discovers,
never auto-activates, and never resolves "latest" -- every resolution is an
explicit, exact ``role_id`` → ``version`` lookup (D-CRP-11).

No provider, no network, no canon/PAC/Sandbox access, no legacy-KB import.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping

from .errors import CrpValidationError
from .permissions import Permission


class RoleStatus(Enum):
    """Registry entry status (CRP_MVP_CONTRACTS_v1.md §F.1)."""

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    REFERENCE = "REFERENCE"
    DEPRECATED = "DEPRECATED"


class ExecutionType(Enum):
    """How a role is executed (CRP_MVP_CONTRACTS_v1.md §F)."""

    LLM_ROLE = "LLM_ROLE"
    DETERMINISTIC_FUNCTION = "DETERMINISTIC_FUNCTION"


@dataclass(frozen=True)
class RoleRegistryEntry:
    """One registry record (CRP_MVP_CONTRACTS_v1.md §F).

    Exact, explicit version; human-approved ``activation_gate`` required before
    a version may be usable as ``ACTIVE``. No auto-promotion.
    """

    role_id: str
    display_name: str
    version: str
    status: RoleStatus
    execution_type: ExecutionType
    prompt_ref: str
    knowledge_profile_ref: str
    input_contract_ref: str
    output_contract_ref: str
    permissions: frozenset
    activation_gate: str

    predecessor_version: str = ""
    deprecation_note: str = ""

    def __post_init__(self) -> None:
        _req(self.role_id, "role_id")
        _req(self.display_name, "display_name")
        _req(self.version, "version")
        if not isinstance(self.status, RoleStatus):
            raise CrpValidationError("status must be a RoleStatus")
        if not isinstance(self.execution_type, ExecutionType):
            raise CrpValidationError("execution_type must be an ExecutionType")
        _req(self.prompt_ref, "prompt_ref")
        _req(self.knowledge_profile_ref, "knowledge_profile_ref")
        _req(self.input_contract_ref, "input_contract_ref")
        _req(self.output_contract_ref, "output_contract_ref")
        if not isinstance(self.permissions, frozenset):
            raise CrpValidationError("permissions must be a frozenset of Permission")
        for p in self.permissions:
            if not isinstance(p, Permission):
                raise CrpValidationError("permissions must contain Permission values")
        _req(self.activation_gate, "activation_gate")
        if not isinstance(self.predecessor_version, str):
            raise CrpValidationError("predecessor_version must be a string")
        if not isinstance(self.deprecation_note, str):
            raise CrpValidationError("deprecation_note must be a string")


class RoleRegistry:
    """Explicit, in-memory registry: a mapping ``role_id -> RoleRegistryEntry``.

    No auto-discovery (caller constructs every entry explicitly), no
    latest-wins (exact version required), no automatic activation. Duplicate
    ``role_id`` in construction is rejected fail-closed.
    """

    def __init__(self, entries: tuple = ()) -> None:
        mapping: dict[str, RoleRegistryEntry] = {}
        for entry in entries:
            if not isinstance(entry, RoleRegistryEntry):
                raise CrpValidationError("registry entries must be RoleRegistryEntry instances")
            if entry.role_id in mapping:
                raise CrpValidationError(f"duplicate registry role_id {entry.role_id!r}")
            mapping[entry.role_id] = entry
        self._entries: Mapping[str, RoleRegistryEntry] = mapping

    def get(self, role_id: str):
        """Return the entry for ``role_id`` or ``None`` if absent."""
        return self._entries.get(role_id)

    def __contains__(self, role_id: str) -> bool:
        return role_id in self._entries

    def __iter__(self):
        return iter(self._entries.values())


def _req(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise CrpValidationError(f"{field_name} must be a non-empty string")