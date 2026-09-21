"""Immutable domain records for Character Authoring persistence."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Optional

from .errors import (
    CharacterAuthoringInvariantError,
    CharacterAuthoringValidationError,
    LifecycleValidationError,
)
from .hashing import SEMANTIC_SCHEMA_VERSION, normalize_json_value
from .validation import (
    validate_distinct_identities,
    validate_identifier,
    validate_provenance,
    validate_snapshot_hash,
)

REVISION_SCHEMA_VERSION = "character_authoring_revision/0.1"
CHARACTER_POINTER_SCHEMA_VERSION = "character_authoring_character_pointer/0.1"
VERSION_POINTER_SCHEMA_VERSION = "character_authoring_version_pointer/0.1"

_SEMANTIC_DOMAINS = {
    "identity",
    "biography",
    "psychology",
    "speech",
    "character_relations",
    "appearance",
    "boundaries",
    "visual_identity",
}
_PSYCHOLOGY_FIELDS = {
    "personality",
    "behavioral_traits",
    "emotional_tendencies",
    "goals_motivations",
}
_SPEECH_FIELDS = {"speech_style", "register"}
_RELATION_FIELDS = {"relational_tendencies", "attachment_traits"}


class LifecycleState(str, Enum):
    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    APPROVED_AS_CANON = "APPROVED_AS_CANON"
    WITHDRAWN = "WITHDRAWN"


def parse_lifecycle(value: object) -> LifecycleState:
    if isinstance(value, LifecycleState):
        return value
    try:
        return LifecycleState(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise LifecycleValidationError(f"unknown lifecycle state: {value!r}") from exc


def _require_exact_keys(value: Mapping[str, Any], expected: set[str], *, field: str) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise CharacterAuthoringValidationError(
            f"{field}: schema keys differ; missing={missing}, extra={extra}"
        )


def _require_string_list(value: object, *, field: str) -> None:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise CharacterAuthoringValidationError(f"{field}: expected list[str]")


def _validate_semantic(data: dict[str, Any]) -> None:
    _require_exact_keys(data, _SEMANTIC_DOMAINS, field="semantic")
    for domain in ("identity", "appearance", "boundaries", "visual_identity"):
        if not isinstance(data[domain], dict):
            raise CharacterAuthoringValidationError(f"semantic.{domain}: expected object")
    if not isinstance(data["biography"], str):
        raise CharacterAuthoringValidationError("semantic.biography: expected string")

    psychology = data["psychology"]
    if not isinstance(psychology, dict):
        raise CharacterAuthoringValidationError("semantic.psychology: expected object")
    _require_exact_keys(psychology, _PSYCHOLOGY_FIELDS, field="semantic.psychology")
    for name in sorted(_PSYCHOLOGY_FIELDS):
        _require_string_list(psychology[name], field=f"semantic.psychology.{name}")

    speech = data["speech"]
    if not isinstance(speech, dict):
        raise CharacterAuthoringValidationError("semantic.speech: expected object")
    _require_exact_keys(speech, _SPEECH_FIELDS, field="semantic.speech")
    if not isinstance(speech["speech_style"], str):
        raise CharacterAuthoringValidationError("semantic.speech.speech_style: expected string")
    if speech["register"] is not None and not isinstance(speech["register"], str):
        raise CharacterAuthoringValidationError(
            "semantic.speech.register: expected string or null"
        )

    relations = data["character_relations"]
    if not isinstance(relations, dict):
        raise CharacterAuthoringValidationError(
            "semantic.character_relations: expected object"
        )
    _require_exact_keys(
        relations, _RELATION_FIELDS, field="semantic.character_relations"
    )
    for name in sorted(_RELATION_FIELDS):
        _require_string_list(
            relations[name], field=f"semantic.character_relations.{name}"
        )


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def _metadata(value: object, *, field_name: str = "workflow_metadata") -> Mapping[str, Any]:
    normalized = normalize_json_value(value)
    if not isinstance(normalized, dict):
        raise CharacterAuthoringValidationError(f"{field_name}: expected object")
    return _freeze(normalized)


@dataclass(frozen=True)
class CharacterSemantic:
    """A detached, deeply immutable semantic snapshot under schema 0.1."""

    _data: Mapping[str, Any] = field(repr=False)

    def __post_init__(self) -> None:
        normalized = normalize_json_value(self._data)
        if not isinstance(normalized, dict):
            raise CharacterAuthoringValidationError("semantic snapshot must be an object")
        _validate_semantic(normalized)
        object.__setattr__(self, "_data", _freeze(normalized))

    @classmethod
    def from_dict(cls, data: object) -> "CharacterSemantic":
        if not isinstance(data, Mapping):
            raise CharacterAuthoringValidationError("semantic snapshot must be an object")
        return cls(data)

    def to_dict(self) -> dict[str, Any]:
        return _thaw(self._data)


@dataclass(frozen=True)
class CharacterPointer:
    character_id: str
    selected_version_id: Optional[str] = None
    workflow_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_identifier(self.character_id, field="character_id")
        if self.selected_version_id is not None:
            validate_identifier(self.selected_version_id, field="selected_version_id")
            validate_distinct_identities(self.character_id, self.selected_version_id)
        object.__setattr__(self, "workflow_metadata", _metadata(self.workflow_metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "pointer_schema_version": CHARACTER_POINTER_SCHEMA_VERSION,
            "character_id": self.character_id,
            "selected_version_id": self.selected_version_id,
            "workflow_metadata": _thaw(self.workflow_metadata),
        }

    @classmethod
    def from_dict(cls, data: object) -> "CharacterPointer":
        if not isinstance(data, dict):
            raise CharacterAuthoringValidationError("character pointer must be an object")
        expected = {
            "pointer_schema_version",
            "character_id",
            "selected_version_id",
            "workflow_metadata",
        }
        _require_exact_keys(data, expected, field="character pointer")
        if data["pointer_schema_version"] != CHARACTER_POINTER_SCHEMA_VERSION:
            raise CharacterAuthoringValidationError("unsupported character pointer schema")
        return cls(
            character_id=data["character_id"],
            selected_version_id=data["selected_version_id"],
            workflow_metadata=data["workflow_metadata"],
        )


@dataclass(frozen=True)
class VersionPointer:
    character_id: str
    version_id: str
    version_label: str
    lifecycle_state: LifecycleState = LifecycleState.DRAFT
    selected_revision_id: Optional[str] = None
    derived_from_version_id: Optional[str] = None
    derived_from_revision_id: Optional[str] = None
    derived_from_snapshot_hash: Optional[str] = None
    workflow_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_identifier(self.character_id, field="character_id")
        validate_identifier(self.version_id, field="version_id")
        validate_distinct_identities(self.character_id, self.version_id)
        if not isinstance(self.version_label, str):
            raise CharacterAuthoringValidationError("version_label: expected string")
        object.__setattr__(self, "lifecycle_state", parse_lifecycle(self.lifecycle_state))
        if self.selected_revision_id is not None:
            validate_identifier(self.selected_revision_id, field="selected_revision_id")
            validate_distinct_identities(
                self.character_id, self.version_id, self.selected_revision_id
            )
        provenance = validate_provenance(
            self.derived_from_version_id,
            self.derived_from_revision_id,
            self.derived_from_snapshot_hash,
        )
        object.__setattr__(self, "derived_from_version_id", provenance[0])
        object.__setattr__(self, "derived_from_revision_id", provenance[1])
        object.__setattr__(self, "derived_from_snapshot_hash", provenance[2])
        object.__setattr__(self, "workflow_metadata", _metadata(self.workflow_metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "pointer_schema_version": VERSION_POINTER_SCHEMA_VERSION,
            "character_id": self.character_id,
            "version_id": self.version_id,
            "version_label": self.version_label,
            "lifecycle_state": self.lifecycle_state.value,
            "selected_revision_id": self.selected_revision_id,
            "derived_from_version_id": self.derived_from_version_id,
            "derived_from_revision_id": self.derived_from_revision_id,
            "derived_from_snapshot_hash": self.derived_from_snapshot_hash,
            "workflow_metadata": _thaw(self.workflow_metadata),
        }

    @classmethod
    def from_dict(cls, data: object) -> "VersionPointer":
        if not isinstance(data, dict):
            raise CharacterAuthoringValidationError("version pointer must be an object")
        expected = {
            "pointer_schema_version",
            "character_id",
            "version_id",
            "version_label",
            "lifecycle_state",
            "selected_revision_id",
            "derived_from_version_id",
            "derived_from_revision_id",
            "derived_from_snapshot_hash",
            "workflow_metadata",
        }
        _require_exact_keys(data, expected, field="version pointer")
        if data["pointer_schema_version"] != VERSION_POINTER_SCHEMA_VERSION:
            raise CharacterAuthoringValidationError("unsupported version pointer schema")
        return cls(**{key: data[key] for key in expected if key != "pointer_schema_version"})


@dataclass(frozen=True)
class RevisionRecord:
    character_id: str
    version_id: str
    revision_id: str
    snapshot_hash: str
    semantic: CharacterSemantic
    lifecycle_state: LifecycleState
    derived_from_version_id: Optional[str] = None
    derived_from_revision_id: Optional[str] = None
    derived_from_snapshot_hash: Optional[str] = None
    created_at: Optional[str] = None
    workflow_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_identifier(self.character_id, field="character_id")
        validate_identifier(self.version_id, field="version_id")
        validate_identifier(self.revision_id, field="revision_id")
        validate_snapshot_hash(self.snapshot_hash)
        validate_distinct_identities(
            self.character_id, self.version_id, self.revision_id, self.snapshot_hash
        )
        if not isinstance(self.semantic, CharacterSemantic):
            raise CharacterAuthoringValidationError(
                "semantic: expected CharacterSemantic"
            )
        object.__setattr__(self, "lifecycle_state", parse_lifecycle(self.lifecycle_state))
        provenance = validate_provenance(
            self.derived_from_version_id,
            self.derived_from_revision_id,
            self.derived_from_snapshot_hash,
        )
        object.__setattr__(self, "derived_from_version_id", provenance[0])
        object.__setattr__(self, "derived_from_revision_id", provenance[1])
        object.__setattr__(self, "derived_from_snapshot_hash", provenance[2])
        if self.created_at is not None and not isinstance(self.created_at, str):
            raise CharacterAuthoringValidationError("created_at: expected string or null")
        object.__setattr__(self, "workflow_metadata", _metadata(self.workflow_metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "revision_schema_version": REVISION_SCHEMA_VERSION,
            "semantic_schema_version": SEMANTIC_SCHEMA_VERSION,
            "character_id": self.character_id,
            "version_id": self.version_id,
            "revision_id": self.revision_id,
            "snapshot_hash": self.snapshot_hash,
            "lifecycle_state": self.lifecycle_state.value,
            "derived_from_version_id": self.derived_from_version_id,
            "derived_from_revision_id": self.derived_from_revision_id,
            "derived_from_snapshot_hash": self.derived_from_snapshot_hash,
            "created_at": self.created_at,
            "workflow_metadata": _thaw(self.workflow_metadata),
            "semantic": self.semantic.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: object) -> "RevisionRecord":
        if not isinstance(data, dict):
            raise CharacterAuthoringValidationError("revision must be an object")
        expected = {
            "revision_schema_version",
            "semantic_schema_version",
            "character_id",
            "version_id",
            "revision_id",
            "snapshot_hash",
            "lifecycle_state",
            "derived_from_version_id",
            "derived_from_revision_id",
            "derived_from_snapshot_hash",
            "created_at",
            "workflow_metadata",
            "semantic",
        }
        _require_exact_keys(data, expected, field="revision")
        if data["revision_schema_version"] != REVISION_SCHEMA_VERSION:
            raise CharacterAuthoringValidationError("unsupported revision schema")
        if data["semantic_schema_version"] != SEMANTIC_SCHEMA_VERSION:
            raise CharacterAuthoringValidationError("unsupported semantic schema")
        return cls(
            character_id=data["character_id"],
            version_id=data["version_id"],
            revision_id=data["revision_id"],
            snapshot_hash=data["snapshot_hash"],
            semantic=CharacterSemantic.from_dict(data["semantic"]),
            lifecycle_state=data["lifecycle_state"],
            derived_from_version_id=data["derived_from_version_id"],
            derived_from_revision_id=data["derived_from_revision_id"],
            derived_from_snapshot_hash=data["derived_from_snapshot_hash"],
            created_at=data["created_at"],
            workflow_metadata=data["workflow_metadata"],
        )
