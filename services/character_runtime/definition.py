#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Neutral, immutable authored-character definition for future runtime use.

This module defines a binding over the existing CRP and Character Core types.
It deliberately contains no package discovery, installation, selection,
session, memory, provider, or Companion dependencies.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from services.character_core.dimensions import DimensionSet
from services.crp_authoring.candidate_package import CandidateCharacterPackage
from services.crp_authoring.lifecycle import AcceptanceRecord

__all__ = [
    "RuntimeCharacterDefinition",
    "RuntimeDefinitionAdapterIdentity",
    "RuntimeDefinitionError",
    "RuntimeDefinitionSourceKind",
    "RuntimeDimensionSemantics",
    "RuntimePackageIdentity",
]


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class RuntimeDefinitionError(ValueError):
    """The supplied authored-definition binding is internally inconsistent."""


class RuntimeDefinitionSourceKind(str, Enum):
    """Stable provenance kind for an authored runtime definition."""

    PACKAGE_V1_CRP_IMPORT = "PACKAGE_V1_CRP_IMPORT"


def _non_empty(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeDefinitionError(f"{field_name} must be a non-empty string")


def _sha256(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise RuntimeDefinitionError(f"{field_name} must be a lowercase SHA-256 digest")


@dataclass(frozen=True, slots=True)
class RuntimePackageIdentity:
    """Exact Package V1 release identity; this is not Platform acceptance."""

    character_id: str
    release_id: str
    display_name: str
    package_hash: str
    authority_class: str
    package_origin: str
    package_schema_version: str
    manifest_schema_version: str

    def __post_init__(self) -> None:
        for name in (
            "character_id",
            "release_id",
            "display_name",
            "authority_class",
            "package_origin",
            "package_schema_version",
            "manifest_schema_version",
        ):
            _non_empty(getattr(self, name), name)
        _sha256(self.package_hash, "package_hash")


@dataclass(frozen=True, slots=True)
class RuntimeDefinitionAdapterIdentity:
    """Identity of the deterministic source-to-definition interpretation."""

    adapter_id: str
    adapter_version: str

    def __post_init__(self) -> None:
        _non_empty(self.adapter_id, "adapter_id")
        _non_empty(self.adapter_version, "adapter_version")


@dataclass(frozen=True, slots=True)
class RuntimeDimensionSemantics:
    """Package extension identity bound to the existing Core dimension schema."""

    character_id: str
    extension_type: str
    extension_version: int
    target_accepted_source_hash: str
    core_contract_version: str | None
    dimension_set: DimensionSet

    def __post_init__(self) -> None:
        _non_empty(self.character_id, "dimension_semantics.character_id")
        _non_empty(self.extension_type, "dimension_semantics.extension_type")
        if (
            isinstance(self.extension_version, bool)
            or not isinstance(self.extension_version, int)
            or self.extension_version < 1
        ):
            raise RuntimeDefinitionError(
                "dimension_semantics.extension_version must be an int >= 1"
            )
        _sha256(
            self.target_accepted_source_hash,
            "dimension_semantics.target_accepted_source_hash",
        )
        if self.core_contract_version is not None:
            _non_empty(
                self.core_contract_version,
                "dimension_semantics.core_contract_version",
            )
        if not isinstance(self.dimension_set, DimensionSet) or not len(self.dimension_set):
            raise RuntimeDefinitionError(
                "dimension_semantics.dimension_set must be a non-empty DimensionSet"
            )


@dataclass(frozen=True, slots=True)
class RuntimeCharacterDefinition:
    """Exact immutable authored definition, with no accumulated consumer state.

    ``package_identity.package_hash`` identifies the exact Package V1
    manifest. ``runtime_definition_hash`` separately identifies this adapter's
    deterministic interpretation of that package and its consumed authored
    inputs. Neither hash confers a new acceptance authority.
    """

    source_kind: RuntimeDefinitionSourceKind
    package_identity: RuntimePackageIdentity
    adapter_identity: RuntimeDefinitionAdapterIdentity
    source_acceptance: AcceptanceRecord
    candidate: CandidateCharacterPackage
    dimension_semantics: RuntimeDimensionSemantics
    visual_identity_state: str
    runtime_definition_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.source_kind, RuntimeDefinitionSourceKind):
            raise RuntimeDefinitionError(
                "source_kind must be a RuntimeDefinitionSourceKind"
            )
        if not isinstance(self.package_identity, RuntimePackageIdentity):
            raise RuntimeDefinitionError(
                "package_identity must be a RuntimePackageIdentity"
            )
        if not isinstance(self.adapter_identity, RuntimeDefinitionAdapterIdentity):
            raise RuntimeDefinitionError(
                "adapter_identity must be a RuntimeDefinitionAdapterIdentity"
            )
        if not isinstance(self.source_acceptance, AcceptanceRecord):
            raise RuntimeDefinitionError("source_acceptance must be an AcceptanceRecord")
        if not isinstance(self.candidate, CandidateCharacterPackage):
            raise RuntimeDefinitionError("candidate must be a CandidateCharacterPackage")
        if not isinstance(self.dimension_semantics, RuntimeDimensionSemantics):
            raise RuntimeDefinitionError(
                "dimension_semantics must be RuntimeDimensionSemantics"
            )
        _non_empty(self.visual_identity_state, "visual_identity_state")
        _sha256(self.runtime_definition_hash, "runtime_definition_hash")

        character_id = self.package_identity.character_id
        if self.candidate.subject_id != character_id:
            raise RuntimeDefinitionError(
                "candidate subject does not match package character identity"
            )
        if self.source_acceptance.subject_id != character_id:
            raise RuntimeDefinitionError(
                "source acceptance subject does not match package character identity"
            )
        if self.dimension_semantics.character_id != character_id:
            raise RuntimeDefinitionError(
                "dimension semantics character does not match package character identity"
            )
        if (
            self.dimension_semantics.target_accepted_source_hash
            != self.source_acceptance.package_hash
        ):
            raise RuntimeDefinitionError(
                "dimension semantics is not bound to the accepted source hash"
            )

    @property
    def character_id(self) -> str:
        return self.package_identity.character_id

    @property
    def display_name(self) -> str:
        return self.package_identity.display_name

    @property
    def accepted_semantic_hash(self) -> str:
        return self.source_acceptance.package_hash
