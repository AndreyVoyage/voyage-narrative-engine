"""Named failures for the local Character Authoring store."""

from __future__ import annotations


class CharacterAuthoringError(Exception):
    """Base class for Character Authoring failures."""


class CharacterAuthoringValidationError(CharacterAuthoringError):
    """A domain object violates the ratified structural contract."""


class IdentifierValidationError(CharacterAuthoringValidationError):
    """A machine identifier is empty, unsafe, or not ASCII-safe."""


class LifecycleValidationError(CharacterAuthoringValidationError):
    """A lifecycle value is outside the ratified vocabulary."""


class CharacterAuthoringInvariantError(CharacterAuthoringValidationError):
    """Two otherwise valid values violate an identity invariant."""


class CharacterAuthoringStorageError(CharacterAuthoringError):
    """The store could not safely read or write local application data."""


class CharacterAuthoringNotFoundError(CharacterAuthoringStorageError):
    """A requested character, version, revision, or pointer does not exist."""


class CharacterAuthoringAlreadyExistsError(CharacterAuthoringStorageError):
    """A character or logical version already exists."""


class ImmutableRevisionError(CharacterAuthoringStorageError):
    """An operation attempted to overwrite an immutable revision."""


class CharacterAuthoringCorruptionError(CharacterAuthoringStorageError):
    """Persisted JSON is malformed or violates its structural contract."""


class SnapshotHashMismatchError(CharacterAuthoringCorruptionError):
    """A revision's stored hash does not match its semantic snapshot."""
