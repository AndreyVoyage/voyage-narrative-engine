#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Character Package dimension-semantics extension loader.

A dimension-semantics extension is a SEPARATE, versioned artifact that
attaches character-specific RELATIONSHIP / PSYCHOLOGY meaning to an already
Accepted Character Package WITHOUT modifying the immutable ``accepted/**``
payload. Dependency direction:

    character_packages/<id>/extensions/dimension_semantics/v1.json
        -> validated here + by services.character_core.dimensions
        -> runtime_context["dimension_definitions"]
        -> GroundedV2Policy semantic rendering

Character Core owns the DimensionDefinition schema, the generic bands, and the
renderer. This loader owns only three things:

- file resolution under ``character_packages/``;
- extension-identity validation (character_id / type / version);
- a FAIL-CLOSED binding to one specific Accepted Package source hash, so
  character-specific semantics can never be silently attached to a different
  package version.

Standard library only. No provider, no network, never writes ``accepted/**``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from services.character_core.dimensions import DimensionDefinitionError, DimensionSet

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EXTENSIONS_ROOT = _REPO_ROOT / "character_packages"

EXTENSION_TYPE = "dimension_semantics"
EXTENSION_FILENAME = "v1.json"
SUPPORTED_EXTENSION_VERSION = 1


class PackageExtensionError(RuntimeError):
    """Fail-closed error for a malformed or mis-bound package extension."""


@dataclass(frozen=True)
class DimensionSemanticsExtension:
    """A validated, hash-bound dimension-semantics extension."""

    character_id: str
    extension_type: str
    extension_version: int
    target_accepted_source_hash: str
    core_contract_version: Optional[str]
    dimension_set: DimensionSet
    source_path: str


def _extension_path(character_id: str, extensions_root) -> Path:
    root = (
        Path(extensions_root)
        if extensions_root is not None
        else DEFAULT_EXTENSIONS_ROOT
    )
    return root / character_id / "extensions" / EXTENSION_TYPE / EXTENSION_FILENAME


def load_dimension_semantics_extension(
    character_id: str,
    accepted_source_hash: str,
    *,
    extensions_root=None,
) -> Optional[DimensionSemanticsExtension]:
    """Load + validate + hash-bind the dimension-semantics extension.

    Returns ``None`` when NO extension file exists for the character (callers
    then fall back to Character Core's raw numeric rendering -- the Foundation
    hook's documented absent-definitions behavior).

    Raises :class:`PackageExtensionError` when a file exists but is malformed,
    carries the wrong identity/version, or is bound to a DIFFERENT Accepted
    Package source hash. Semantics are never silently attached to the wrong
    package version.
    """
    if not isinstance(character_id, str) or not character_id.strip():
        raise PackageExtensionError("character_id must be a non-empty string")
    if not isinstance(accepted_source_hash, str) or not accepted_source_hash.strip():
        raise PackageExtensionError("accepted_source_hash must be a non-empty string")

    path = _extension_path(character_id, extensions_root)
    if not path.exists():
        return None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PackageExtensionError(
            f"extension is not valid JSON: {path}: {exc}"
        ) from exc
    if not isinstance(data, dict):
        raise PackageExtensionError(f"extension must be a JSON object: {path}")

    def _req(key: str, typ) -> object:
        if key not in data:
            raise PackageExtensionError(
                f"extension missing required field {key!r}: {path}"
            )
        val = data[key]
        if isinstance(val, bool) and typ is int:
            raise PackageExtensionError(
                f"extension field {key!r} must be an integer: {path}"
            )
        if not isinstance(val, typ) or (typ is str and not val.strip()):
            raise PackageExtensionError(
                f"extension field {key!r} has invalid type/value: {path}"
            )
        return val

    ext_character = _req("character_id", str)
    ext_type = _req("extension_type", str)
    ext_version = _req("extension_version", int)
    target_hash = _req("target_accepted_source_hash", str)

    contract_version = data.get("core_contract_version")
    if contract_version is not None and (
        not isinstance(contract_version, str) or not contract_version.strip()
    ):
        raise PackageExtensionError(
            f"core_contract_version must be a non-empty string when present: {path}"
        )

    if ext_character != character_id:
        raise PackageExtensionError(
            f"extension character_id {ext_character!r} != requested {character_id!r}: {path}"
        )
    if ext_type != EXTENSION_TYPE:
        raise PackageExtensionError(
            f"extension_type {ext_type!r} != {EXTENSION_TYPE!r}: {path}"
        )
    if ext_version != SUPPORTED_EXTENSION_VERSION:
        raise PackageExtensionError(
            f"unsupported extension_version {ext_version!r} "
            f"(supported: {SUPPORTED_EXTENSION_VERSION}): {path}"
        )

    # Fail-closed reproducibility binding.
    if target_hash != accepted_source_hash:
        raise PackageExtensionError(
            "extension target_accepted_source_hash does not match the current "
            f"Accepted Package source hash for {character_id!r} "
            f"(extension={target_hash!r}, accepted={accepted_source_hash!r}); "
            "refusing to attach semantics to a different package version"
        )

    raw_dims = data.get("dimensions")
    if not isinstance(raw_dims, list) or not raw_dims:
        raise PackageExtensionError(
            f"extension 'dimensions' must be a non-empty list: {path}"
        )
    try:
        dimension_set = DimensionSet.from_dicts(raw_dims)
    except DimensionDefinitionError as exc:
        raise PackageExtensionError(
            f"invalid dimension definition in {path}: {exc}"
        ) from exc

    return DimensionSemanticsExtension(
        character_id=ext_character,
        extension_type=ext_type,
        extension_version=ext_version,
        target_accepted_source_hash=target_hash,
        core_contract_version=contract_version,
        dimension_set=dimension_set,
        source_path=str(path),
    )


def load_character_dimension_set(
    character_id: str,
    accepted_source_hash: str,
    *,
    extensions_root=None,
) -> Optional[DimensionSet]:
    """Convenience: just the validated :class:`DimensionSet`, or ``None`` when
    no extension file exists for the character."""
    ext = load_dimension_semantics_extension(
        character_id, accepted_source_hash, extensions_root=extensions_root
    )
    return ext.dimension_set if ext is not None else None
