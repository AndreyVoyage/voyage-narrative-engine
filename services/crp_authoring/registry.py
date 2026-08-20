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
from pathlib import Path
from typing import Mapping, Optional

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

    def resolve(self, role_id: str, version: str) -> RoleRegistryEntry:
        """Exact ``role_id`` → ``version`` lookup, fail-closed.

        No latest-wins, no fallback to another version. Unknown ``role_id`` or
        a version that does not match the registered entry raises
        ``CrpValidationError`` (CRP-OD-11 / D-CRP-11).
        """
        entry = self._entries.get(role_id)
        if entry is None:
            raise CrpValidationError(f"role_id {role_id!r} is not in the registry")
        if entry.version != version:
            raise CrpValidationError(
                f"role_id {role_id!r} is registered at version {entry.version!r}, "
                f"not {version!r}"
            )
        return entry


# Version pins that must never appear in a declarative registry entry.
_FORBIDDEN_VERSION_MARKERS = frozenset((
    "latest",
    "current",
    "auto",
    "*",
    "highest",
))


def load_role_registry(yaml_path=None) -> RoleRegistry:
    """Load and validate the declarative role registry YAML into a ``RoleRegistry``.

    Fail-closed, deterministic loader:

    - parses a single declared YAML file (no auto-discovery, no directory
      scanning to register roles);
    - rejects malformed structure and unknown enum values;
    - rejects duplicate ``(role_id, version)`` entries;
    - rejects forbidden version markers (``latest``/``current``/``*``/``auto``/
      ``highest``);
    - preserves file order (deterministic iteration);
    - verifies, for every ACTIVE LLM_ROLE entry only, that ``prompt_ref``
      resolves to a real file under the repository root (missing prompt path
      fails closed). Inactive/unimplemented roles are NOT required to resolve a
      prompt artifact.

    No provider, no network, no canon/PAC/Sandbox access.
    """
    if yaml_path is None:
        yaml_path = (
            Path(__file__).resolve().parents[2]
            / "roles"
            / "vnext"
            / "CRP_ROLE_REGISTRY_v1.yaml"
        )

    path = Path(yaml_path)
    if not path.is_file():
        raise CrpValidationError(f"registry YAML does not reference a file: {str(path)!r}")

    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - no such env in this repo
        raise CrpValidationError("PyYAML is required to load the role registry") from exc

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise CrpValidationError(f"registry YAML is malformed: {exc}") from exc

    if not isinstance(data, dict):
        raise CrpValidationError("registry YAML top-level must be a mapping")
    raw_roles = data.get("roles")
    if not isinstance(raw_roles, list):
        raise CrpValidationError("registry YAML must contain a 'roles' list")

    repo_root = Path(__file__).resolve().parents[2]
    seen_keys = set()
    entries = []
    for raw in raw_roles:
        entry = _entry_from_mapping(raw)
        key = (entry.role_id, entry.version)
        if key in seen_keys:
            raise CrpValidationError(
                f"duplicate registry (role_id, version) {entry.role_id!r}/{entry.version!r}"
            )
        seen_keys.add(key)
        _validate_prompt_resolution(entry, repo_root)
        entries.append(entry)

    return RoleRegistry(tuple(entries))


def _entry_from_mapping(raw) -> RoleRegistryEntry:
    if not isinstance(raw, dict):
        raise CrpValidationError("each registry role entry must be a mapping")

    version = _required_str(raw.get("version"), "version")
    if version.lower() in _FORBIDDEN_VERSION_MARKERS:
        raise CrpValidationError(
            f"version {version!r} is a forbidden marker; exact version pins only"
        )

    permissions_raw = raw.get("permissions", [])
    if not isinstance(permissions_raw, (list, tuple)):
        raise CrpValidationError("permissions must be a list")
    permissions = frozenset(_decode_permission(p) for p in permissions_raw)

    return RoleRegistryEntry(
        role_id=_required_str(raw.get("role_id"), "role_id"),
        display_name=_required_str(raw.get("display_name"), "display_name"),
        version=version,
        status=_decode_status(raw.get("status")),
        execution_type=_decode_execution_type(raw.get("execution_type")),
        prompt_ref=_required_str(raw.get("prompt_ref"), "prompt_ref"),
        knowledge_profile_ref=_required_str(raw.get("knowledge_profile_ref"), "knowledge_profile_ref"),
        input_contract_ref=_required_str(raw.get("input_contract_ref"), "input_contract_ref"),
        output_contract_ref=_required_str(raw.get("output_contract_ref"), "output_contract_ref"),
        permissions=permissions,
        activation_gate=_required_str(raw.get("activation_gate"), "activation_gate"),
        predecessor_version=raw.get("predecessor_version") or "",
        deprecation_note=raw.get("deprecation_note") or "",
    )


def _validate_prompt_resolution(entry: RoleRegistryEntry, repo_root: Path) -> None:
    """Fail-closed prompt-path check for ACTIVE LLM_ROLE entries only.

    Rejects absolute refs, ``..`` traversal, and any prompt that does not
    resolve to an existing file. Inactive/unimplemented roles and deterministic
    functions are exempt (no fake prompt requirement).
    """
    if entry.status is not RoleStatus.ACTIVE:
        return
    if entry.execution_type is not ExecutionType.LLM_ROLE:
        return

    ref = entry.prompt_ref
    pure = Path(ref)
    if pure.is_absolute():
        raise CrpValidationError(f"prompt_ref must be a relative path: {ref!r}")
    if ".." in pure.parts:
        raise CrpValidationError(f"prompt_ref must not contain path traversal: {ref!r}")
    candidate = (repo_root / pure).resolve()
    if not candidate.is_file():
        raise CrpValidationError(
            f"ACTIVE LLM role {entry.role_id!r} prompt_ref does not resolve to a file: {ref!r}"
        )


def _decode_status(value) -> RoleStatus:
    if value is None:
        raise CrpValidationError("status is required")
    if not isinstance(value, str):
        raise CrpValidationError("status must be a string")
    try:
        return RoleStatus(value)
    except ValueError:
        raise CrpValidationError(f"unknown RoleStatus value {value!r}") from None


def _decode_execution_type(value) -> ExecutionType:
    if value is None:
        raise CrpValidationError("execution_type is required")
    if not isinstance(value, str):
        raise CrpValidationError("execution_type must be a string")
    try:
        return ExecutionType(value)
    except ValueError:
        raise CrpValidationError(f"unknown ExecutionType value {value!r}") from None


def _decode_permission(value) -> Permission:
    if value is None:
        raise CrpValidationError("permission entries must be non-null")
    if not isinstance(value, str):
        raise CrpValidationError("permission entries must be strings")
    try:
        return Permission(value)
    except ValueError:
        raise CrpValidationError(f"unknown permission verb {value!r}") from None


def _required_str(value, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CrpValidationError(f"{field_name} must be a non-empty string")
    return value


def _req(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise CrpValidationError(f"{field_name} must be a non-empty string")
