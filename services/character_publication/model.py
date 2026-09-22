"""Immutable models for Authoring Runtime Package V1."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from services.character_authoring import CharacterSemantic
from services.character_authoring.hashing import SEMANTIC_SCHEMA_VERSION
from services.character_authoring.validation import (
    validate_distinct_identities,
    validate_identifier,
    validate_snapshot_hash,
)

from .errors import PublicationValidationError

RUNTIME_PACKAGE_SCHEMA_VERSION = "character_authoring_runtime_package/1.0"
COMPILER_PROFILE = "authoring_runtime_compiler/1.0"
VISUAL_IDENTITY_EMPTY_STATE = "EXPLICITLY_EMPTY"

_PACKAGE_FIELDS = {
    "runtime_package_schema_version",
    "compiler_profile",
    "provenance",
    "semantic",
    "visual_identity_resolved",
}
_PROVENANCE_FIELDS = {
    "source_character_id",
    "source_version_id",
    "source_revision_id",
    "source_snapshot_hash",
}
_RESOLVED_VISUAL_IDENTITY = {
    "state": VISUAL_IDENTITY_EMPTY_STATE,
    "references": [],
}


def _require_exact_keys(
    value: Mapping[str, Any], expected: set[str], *, field: str
) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise PublicationValidationError(
            f"{field}: schema keys differ; missing={missing}, extra={extra}"
        )


def validate_slice1_visual_identity(semantic: CharacterSemantic) -> None:
    """Allow only the two explicit empty shapes ratified for Slice 1."""

    visual_identity = semantic.to_dict()["visual_identity"]
    if visual_identity not in ({}, {"references": []}):
        raise PublicationValidationError(
            "Slice 1 cannot publish a non-empty visual_identity without a "
            "local deterministic asset resolver"
        )


@dataclass(frozen=True, slots=True)
class SourceProvenance:
    source_character_id: str
    source_version_id: str
    source_revision_id: str
    source_snapshot_hash: str

    def __post_init__(self) -> None:
        try:
            validate_identifier(
                self.source_character_id, field="source_character_id"
            )
            validate_identifier(self.source_version_id, field="source_version_id")
            validate_identifier(
                self.source_revision_id, field="source_revision_id"
            )
            validate_snapshot_hash(
                self.source_snapshot_hash, field="source_snapshot_hash"
            )
            validate_distinct_identities(
                self.source_character_id,
                self.source_version_id,
                self.source_revision_id,
                self.source_snapshot_hash,
            )
        except Exception as exc:
            raise PublicationValidationError(str(exc)) from exc

    def to_dict(self) -> dict[str, str]:
        return {
            "source_character_id": self.source_character_id,
            "source_version_id": self.source_version_id,
            "source_revision_id": self.source_revision_id,
            "source_snapshot_hash": self.source_snapshot_hash,
        }

    @classmethod
    def from_dict(cls, data: object) -> "SourceProvenance":
        if not isinstance(data, Mapping):
            raise PublicationValidationError("provenance must be an object")
        _require_exact_keys(data, _PROVENANCE_FIELDS, field="provenance")
        return cls(**{key: data[key] for key in _PROVENANCE_FIELDS})


@dataclass(frozen=True, slots=True)
class AuthoringRuntimePackage:
    provenance: SourceProvenance
    semantic: CharacterSemantic

    def __post_init__(self) -> None:
        if not isinstance(self.provenance, SourceProvenance):
            raise PublicationValidationError(
                "provenance must be SourceProvenance"
            )
        if not isinstance(self.semantic, CharacterSemantic):
            raise PublicationValidationError("semantic must be CharacterSemantic")
        validate_slice1_visual_identity(self.semantic)

    def to_dict(self) -> dict[str, Any]:
        return {
            "runtime_package_schema_version": RUNTIME_PACKAGE_SCHEMA_VERSION,
            "compiler_profile": COMPILER_PROFILE,
            "provenance": self.provenance.to_dict(),
            "semantic": self.semantic.to_dict(),
            "visual_identity_resolved": {
                "state": VISUAL_IDENTITY_EMPTY_STATE,
                "references": [],
            },
        }

    @classmethod
    def from_dict(cls, data: object) -> "AuthoringRuntimePackage":
        if not isinstance(data, Mapping):
            raise PublicationValidationError("runtime package must be an object")
        _require_exact_keys(data, _PACKAGE_FIELDS, field="runtime package")
        if data["runtime_package_schema_version"] != RUNTIME_PACKAGE_SCHEMA_VERSION:
            raise PublicationValidationError("unsupported runtime package schema")
        if data["compiler_profile"] != COMPILER_PROFILE:
            raise PublicationValidationError("unsupported compiler profile")
        if data["visual_identity_resolved"] != _RESOLVED_VISUAL_IDENTITY:
            raise PublicationValidationError(
                "Slice 1 resolved visual identity must be explicitly empty"
            )
        try:
            semantic = CharacterSemantic.from_dict(data["semantic"])
        except Exception as exc:
            raise PublicationValidationError(
                "runtime package semantic is invalid"
            ) from exc
        return cls(
            provenance=SourceProvenance.from_dict(data["provenance"]),
            semantic=semantic,
        )


@dataclass(frozen=True, slots=True)
class PublishedRuntimePackage:
    runtime_package_schema_version: str
    character_id: str
    package_hash: str
    source_version_id: str
    source_revision_id: str
    source_snapshot_hash: str


@dataclass(frozen=True, slots=True)
class VerifiedRuntimePackage:
    runtime_package_schema_version: str
    compiler_profile: str
    package_hash: str
    provenance: SourceProvenance
    semantic: CharacterSemantic


def build_runtime_package(
    provenance: SourceProvenance, semantic: CharacterSemantic
) -> AuthoringRuntimePackage:
    """Build the complete validated in-memory package payload."""

    return AuthoringRuntimePackage(provenance=provenance, semantic=semantic)


__all__ = [
    "AuthoringRuntimePackage",
    "COMPILER_PROFILE",
    "PublishedRuntimePackage",
    "RUNTIME_PACKAGE_SCHEMA_VERSION",
    "SEMANTIC_SCHEMA_VERSION",
    "SourceProvenance",
    "VerifiedRuntimePackage",
    "VISUAL_IDENTITY_EMPTY_STATE",
    "build_runtime_package",
    "validate_slice1_visual_identity",
]
