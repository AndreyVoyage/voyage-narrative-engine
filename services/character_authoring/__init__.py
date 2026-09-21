"""Public API for Character Authoring domain models and durable local storage."""

from __future__ import annotations

from .errors import (
    CharacterAuthoringAlreadyExistsError,
    CharacterAuthoringCorruptionError,
    CharacterAuthoringError,
    CharacterAuthoringInvariantError,
    CharacterAuthoringNotFoundError,
    CharacterAuthoringStorageError,
    CharacterAuthoringValidationError,
    IdentifierValidationError,
    ImmutableRevisionError,
    LifecycleValidationError,
    SnapshotHashMismatchError,
)
from .hashing import (
    SEMANTIC_SCHEMA_VERSION,
    canonical_semantic_json,
    canonical_semantic_payload,
    compute_snapshot_hash,
    normalize_json_value,
)
from .model import (
    CHARACTER_POINTER_SCHEMA_VERSION,
    REVISION_SCHEMA_VERSION,
    VERSION_POINTER_SCHEMA_VERSION,
    CharacterPointer,
    CharacterSemantic,
    LifecycleState,
    RevisionRecord,
    VersionPointer,
)
from .store import CharacterAuthoringStore, default_store_root
from .validation import validate_identifier

__all__ = [
    "SEMANTIC_SCHEMA_VERSION",
    "REVISION_SCHEMA_VERSION",
    "CHARACTER_POINTER_SCHEMA_VERSION",
    "VERSION_POINTER_SCHEMA_VERSION",
    "LifecycleState",
    "CharacterSemantic",
    "RevisionRecord",
    "CharacterPointer",
    "VersionPointer",
    "CharacterAuthoringStore",
    "default_store_root",
    "normalize_json_value",
    "canonical_semantic_payload",
    "canonical_semantic_json",
    "compute_snapshot_hash",
    "validate_identifier",
    "CharacterAuthoringError",
    "CharacterAuthoringValidationError",
    "IdentifierValidationError",
    "LifecycleValidationError",
    "CharacterAuthoringInvariantError",
    "CharacterAuthoringStorageError",
    "CharacterAuthoringNotFoundError",
    "CharacterAuthoringAlreadyExistsError",
    "ImmutableRevisionError",
    "CharacterAuthoringCorruptionError",
    "SnapshotHashMismatchError",
]
