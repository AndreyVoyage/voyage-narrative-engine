"""Application-neutral publication command for approved Authoring revisions."""

from __future__ import annotations

from pathlib import Path

from services.character_authoring import (
    CharacterAuthoringCorruptionError,
    CharacterAuthoringNotFoundError,
    CharacterAuthoringStorageError,
    CharacterAuthoringStore,
    CharacterAuthoringValidationError,
    LifecycleState,
)
from services.character_authoring.validation import (
    validate_distinct_identities,
    validate_identifier,
    validate_snapshot_hash,
)

from .errors import (
    PublicationNotApprovedError,
    PublicationSourceCorruptError,
    PublicationStaleRevisionError,
    PublicationStaleSnapshotError,
    PublicationStorageError,
    PublicationValidationError,
)
from .hashing import canonical_runtime_package_bytes, compute_package_hash
from .model import (
    PublishedRuntimePackage,
    RUNTIME_PACKAGE_SCHEMA_VERSION,
    SourceProvenance,
    build_runtime_package,
    validate_slice1_visual_identity,
)
from .store import CharacterPublicationStore


class CharacterPublicationService:
    """Publish one exact approved selected revision without source mutation."""

    def __init__(
        self,
        authoring_store: CharacterAuthoringStore | Path | str,
        publication_store: CharacterPublicationStore | Path | str,
    ) -> None:
        try:
            self._authoring = (
                authoring_store
                if isinstance(authoring_store, CharacterAuthoringStore)
                else CharacterAuthoringStore(authoring_store)
            )
        except CharacterAuthoringStorageError as exc:
            raise PublicationStorageError(
                "authoring store could not be initialized"
            ) from exc
        self._publication = (
            publication_store
            if isinstance(publication_store, CharacterPublicationStore)
            else CharacterPublicationStore(publication_store)
        )

    def publish_character_version(
        self,
        *,
        character_id: str,
        version_id: str,
        revision_id: str,
        snapshot_hash: str,
    ) -> PublishedRuntimePackage:
        try:
            validate_identifier(character_id, field="character_id")
            validate_identifier(version_id, field="version_id")
            validate_identifier(revision_id, field="revision_id")
            validate_snapshot_hash(snapshot_hash)
            validate_distinct_identities(
                character_id, version_id, revision_id, snapshot_hash
            )
        except CharacterAuthoringValidationError as exc:
            raise PublicationValidationError(str(exc)) from exc

        try:
            pointer = self._authoring.read_version_pointer(
                character_id, version_id
            )
        except CharacterAuthoringNotFoundError:
            raise
        except CharacterAuthoringCorruptionError as exc:
            raise PublicationSourceCorruptError(
                "authoring version pointer is corrupt"
            ) from exc
        except CharacterAuthoringStorageError as exc:
            raise PublicationStorageError(
                "authoring version pointer could not be read"
            ) from exc

        if pointer.lifecycle_state is not LifecycleState.APPROVED_AS_CANON:
            raise PublicationNotApprovedError(
                f"version {version_id!r} is not APPROVED_AS_CANON"
            )
        if pointer.selected_revision_id != revision_id:
            raise PublicationStaleRevisionError(
                "supplied revision is not the currently selected revision"
            )

        try:
            record = self._authoring.load_revision(
                character_id, version_id, revision_id
            )
        except CharacterAuthoringNotFoundError:
            raise
        except CharacterAuthoringCorruptionError as exc:
            raise PublicationSourceCorruptError(
                "authoring revision failed integrity verification"
            ) from exc
        except CharacterAuthoringStorageError as exc:
            raise PublicationStorageError(
                "authoring revision could not be read"
            ) from exc

        if record.snapshot_hash != snapshot_hash:
            raise PublicationStaleSnapshotError(
                "supplied snapshot_hash does not match the selected revision"
            )
        if (
            record.character_id != character_id
            or record.version_id != version_id
            or record.revision_id != revision_id
        ):
            raise PublicationSourceCorruptError(
                "authoring revision identity does not match publication request"
            )

        validate_slice1_visual_identity(record.semantic)
        provenance = SourceProvenance(
            source_character_id=character_id,
            source_version_id=version_id,
            source_revision_id=revision_id,
            source_snapshot_hash=snapshot_hash,
        )
        package = build_runtime_package(provenance, record.semantic)
        canonical_bytes = canonical_runtime_package_bytes(package)
        package_hash = compute_package_hash(package)
        self._publication.publish(
            character_id=character_id,
            package_hash=package_hash,
            canonical_bytes=canonical_bytes,
        )
        return PublishedRuntimePackage(
            runtime_package_schema_version=RUNTIME_PACKAGE_SCHEMA_VERSION,
            character_id=character_id,
            package_hash=package_hash,
            source_version_id=version_id,
            source_revision_id=revision_id,
            source_snapshot_hash=snapshot_hash,
        )


__all__ = ["CharacterPublicationService"]
