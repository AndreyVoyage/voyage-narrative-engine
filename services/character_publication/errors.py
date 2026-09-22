"""Named failures for deterministic Character Authoring publication."""

from __future__ import annotations


class CharacterPublicationError(Exception):
    """Base class for Character Publication failures."""


class PublicationValidationError(CharacterPublicationError):
    """Input or package content violates the Publication V1 contract."""


class PublicationNotApprovedError(CharacterPublicationError):
    """The selected authoring version is not approved for publication."""


class PublicationStaleRevisionError(CharacterPublicationError):
    """The requested revision is not the version's selected revision."""


class PublicationStaleSnapshotError(CharacterPublicationError):
    """The caller's snapshot hash does not match the immutable revision."""


class PublicationSourceCorruptError(CharacterPublicationError):
    """The persisted Authoring source failed its integrity checks."""


class PublicationPackageCollisionError(CharacterPublicationError):
    """An immutable target exists but is not the identical valid package."""


class PublicationStorageError(CharacterPublicationError):
    """The publication store could not safely read or publish an artifact."""
