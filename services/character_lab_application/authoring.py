"""S2/S3 Character Authoring application use-cases.

This module orchestrates the S1 domain/store without changing it. Character
Canon access is read-only and flows only through its public bridge.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, NoReturn, Optional

from services.character_authoring import (
    CharacterAuthoringAlreadyExistsError,
    CharacterAuthoringError,
    CharacterAuthoringNotFoundError,
    CharacterAuthoringStorageError,
    CharacterAuthoringStore,
    CharacterAuthoringValidationError,
    CharacterPointer,
    CharacterSemantic,
    ImmutableRevisionError,
    LifecycleState,
    RevisionRecord,
    VersionPointer,
    compute_snapshot_hash,
)
from services.character_canon_bridge import (
    CharacterCanonBridgeError,
    CharacterCanonSnapshot,
    read_character_canon,
)

from .errors import (
    AUTHORING_ALREADY_EXISTS,
    AUTHORING_INVALID_LIFECYCLE_TRANSITION,
    AUTHORING_NOT_EDITABLE,
    AUTHORING_NOT_FOUND,
    AUTHORING_PERSISTENCE_FAILED,
    AUTHORING_STALE_REVISION,
    AUTHORING_STALE_SNAPSHOT,
    AUTHORING_UNAVAILABLE,
    AUTHORING_VALIDATION_FAILED,
    DERIVATION_SOURCE_NOT_APPROVED,
    IMMUTABLE_PERSISTENCE_FAILED,
    IMPORT_REQUIRES_AUTHORING_COMPLETION,
    IMPORT_SOURCE_UNAVAILABLE,
    INTERNAL_ERROR,
    CharacterLabApplicationError,
)
from .results import CharacterAuthoringResult, CharacterSessionPin

CREATE = "CREATE"
SAVE = "SAVE"
NEW_VERSION = "NEW_VERSION"
IMPORT = "IMPORT"
SUBMIT = "SUBMIT_FOR_APPROVAL"
REQUEST_CHANGES = "REQUEST_CHANGES"
APPROVE = "APPROVE_AS_CANON"
WITHDRAW = "WITHDRAW_SUBMISSION"
DERIVE_VERSION = "DERIVE_VERSION"

_EDITABLE_STATES = frozenset(
    {LifecycleState.DRAFT, LifecycleState.CHANGES_REQUESTED}
)

CanonReader = Callable[[Path, str, str], CharacterCanonSnapshot]
CanonSemanticMapper = Callable[[CharacterCanonSnapshot], Mapping[str, Any]]


@dataclass(frozen=True)
class _PreparedInitialRevision:
    semantic: CharacterSemantic
    snapshot_hash: str


def _default_canon_semantic_mapper(
    snapshot: CharacterCanonSnapshot,
) -> Mapping[str, Any]:
    """Map only authoring facts directly exposed by the current bridge.

    The current bridge exposes stable identity and visual reference paths but
    not biography, psychology, speech, relations, appearance, or boundaries.
    The intentionally partial mapping is detected before persistence and
    reported as requiring authoring completion.
    """

    return {
        "identity": {"source_character_id": snapshot.character_id},
        "visual_identity": {
            "references": [reference.to_dict() for reference in snapshot.references]
        },
    }


def _missing_required_fields(value: object) -> tuple[str, ...]:
    if not isinstance(value, Mapping):
        return ("semantic",)

    missing: list[str] = []
    for domain in (
        "identity",
        "biography",
        "psychology",
        "speech",
        "character_relations",
        "appearance",
        "boundaries",
        "visual_identity",
    ):
        if domain not in value:
            missing.append(domain)

    nested = {
        "psychology": (
            "personality",
            "behavioral_traits",
            "emotional_tendencies",
            "goals_motivations",
        ),
        "speech": ("speech_style", "register"),
        "character_relations": (
            "relational_tendencies",
            "attachment_traits",
        ),
    }
    for domain, fields in nested.items():
        section = value.get(domain)
        if not isinstance(section, Mapping):
            continue
        for field in fields:
            if field not in section:
                missing.append(f"{domain}.{field}")
    return tuple(missing)


class _CharacterAuthoringUseCases:
    """Internal application orchestrator behind the Character Lab facade."""

    def __init__(
        self,
        authoring_root: Optional[Path],
        canon_root: Optional[Path],
        *,
        canon_reader: CanonReader = read_character_canon,
        canon_semantic_mapper: CanonSemanticMapper = _default_canon_semantic_mapper,
    ) -> None:
        self._canon_root = canon_root
        self._canon_reader = canon_reader
        self._canon_semantic_mapper = canon_semantic_mapper
        if authoring_root is None:
            self._store: Optional[CharacterAuthoringStore] = None
            return
        try:
            self._store = CharacterAuthoringStore(authoring_root)
        except CharacterAuthoringError as exc:
            self._raise_authoring(exc)

    def _require_store(self) -> CharacterAuthoringStore:
        if self._store is None:
            raise CharacterLabApplicationError(
                AUTHORING_UNAVAILABLE,
                "Character Authoring store root is not configured",
            )
        return self._store

    @staticmethod
    def _raise_authoring(
        exc: BaseException,
        *,
        details: Optional[dict[str, object]] = None,
    ) -> NoReturn:
        if isinstance(exc, ImmutableRevisionError):
            code = IMMUTABLE_PERSISTENCE_FAILED
        elif isinstance(exc, CharacterAuthoringAlreadyExistsError):
            code = AUTHORING_ALREADY_EXISTS
        elif isinstance(exc, CharacterAuthoringNotFoundError):
            code = AUTHORING_NOT_FOUND
        elif isinstance(exc, CharacterAuthoringValidationError):
            code = AUTHORING_VALIDATION_FAILED
        elif isinstance(exc, (CharacterAuthoringStorageError, OSError)):
            code = AUTHORING_PERSISTENCE_FAILED
        else:
            code = INTERNAL_ERROR
        message = str(exc) if not isinstance(exc, OSError) else "authoring persistence failed"
        raise CharacterLabApplicationError(code, message, details=details) from exc

    @staticmethod
    def _prepare_initial_revision(
        character_id: str,
        version_id: str,
        revision_id: str,
        version_label: str,
        semantic: Mapping[str, Any] | CharacterSemantic,
        workflow_metadata: Mapping[str, Any],
    ) -> _PreparedInitialRevision:
        semantic_model = (
            semantic
            if isinstance(semantic, CharacterSemantic)
            else CharacterSemantic.from_dict(semantic)
        )
        snapshot_hash = compute_snapshot_hash(semantic_model)
        CharacterPointer(character_id, selected_version_id=version_id)
        VersionPointer(
            character_id=character_id,
            version_id=version_id,
            version_label=version_label,
            lifecycle_state=LifecycleState.DRAFT,
            selected_revision_id=revision_id,
            workflow_metadata=workflow_metadata,
        )
        RevisionRecord(
            character_id=character_id,
            version_id=version_id,
            revision_id=revision_id,
            snapshot_hash=snapshot_hash,
            semantic=semantic_model,
            lifecycle_state=LifecycleState.DRAFT,
            workflow_metadata=workflow_metadata,
        )
        return _PreparedInitialRevision(semantic_model, snapshot_hash)

    @staticmethod
    def _result(
        operation: str,
        record: RevisionRecord,
        *,
        source_character_id: Optional[str] = None,
        source_revision_id: Optional[str] = None,
        source_snapshot_hash: Optional[str] = None,
        source_ref: Optional[str] = None,
    ) -> CharacterAuthoringResult:
        return CharacterAuthoringResult(
            operation=operation,
            character_id=record.character_id,
            version_id=record.version_id,
            revision_id=record.revision_id,
            snapshot_hash=record.snapshot_hash,
            lifecycle_state=record.lifecycle_state.value,
            source_character_id=source_character_id,
            source_revision_id=source_revision_id,
            source_snapshot_hash=source_snapshot_hash,
            source_ref=source_ref,
        )

    @staticmethod
    def _workflow_result(
        operation: str,
        record: RevisionRecord,
        lifecycle_state: LifecycleState,
    ) -> CharacterAuthoringResult:
        return CharacterAuthoringResult(
            operation=operation,
            character_id=record.character_id,
            version_id=record.version_id,
            revision_id=record.revision_id,
            snapshot_hash=record.snapshot_hash,
            lifecycle_state=lifecycle_state.value,
        )

    def _load_exact_selected_revision(
        self,
        store: CharacterAuthoringStore,
        *,
        character_id: str,
        version_id: str,
        revision_id: str,
        snapshot_hash: str,
    ) -> tuple[VersionPointer, RevisionRecord]:
        try:
            pointer = store.read_version_pointer(character_id, version_id)
        except (CharacterAuthoringError, OSError) as exc:
            self._raise_authoring(exc)

        if pointer.selected_revision_id != revision_id:
            raise CharacterLabApplicationError(
                AUTHORING_STALE_REVISION,
                "supplied revision is not the currently selected revision",
                details={
                    "supplied_revision_id": revision_id,
                    "selected_revision_id": pointer.selected_revision_id,
                },
            )

        try:
            record = store.load_revision(character_id, version_id, revision_id)
        except (CharacterAuthoringError, OSError) as exc:
            self._raise_authoring(exc)

        if record.snapshot_hash != snapshot_hash:
            raise CharacterLabApplicationError(
                AUTHORING_STALE_SNAPSHOT,
                "supplied snapshot hash does not match the selected revision",
                details={
                    "revision_id": revision_id,
                    "supplied_snapshot_hash": snapshot_hash,
                    "stored_snapshot_hash": record.snapshot_hash,
                },
            )
        return pointer, record

    def _transition_version(
        self,
        *,
        operation: str,
        character_id: str,
        version_id: str,
        revision_id: str,
        snapshot_hash: str,
        allowed_sources: frozenset[LifecycleState],
        target_state: LifecycleState,
    ) -> CharacterAuthoringResult:
        store = self._require_store()
        pointer, record = self._load_exact_selected_revision(
            store,
            character_id=character_id,
            version_id=version_id,
            revision_id=revision_id,
            snapshot_hash=snapshot_hash,
        )
        if pointer.lifecycle_state not in allowed_sources:
            raise CharacterLabApplicationError(
                AUTHORING_INVALID_LIFECYCLE_TRANSITION,
                f"transition from {pointer.lifecycle_state.value} to "
                f"{target_state.value} is not allowed",
                details={
                    "source_lifecycle_state": pointer.lifecycle_state.value,
                    "target_lifecycle_state": target_state.value,
                },
            )

        try:
            store.update_version_pointer(
                replace(pointer, lifecycle_state=target_state)
            )
        except (CharacterAuthoringError, OSError) as exc:
            self._raise_authoring(
                exc,
                details={
                    "previous_lifecycle_state": pointer.lifecycle_state.value,
                    "target_lifecycle_state": target_state.value,
                    "revision_id": record.revision_id,
                    "snapshot_hash": record.snapshot_hash,
                },
            )
        return self._workflow_result(operation, record, target_state)

    def _create_new_character(
        self,
        *,
        operation: str,
        character_id: str,
        version_id: str,
        revision_id: str,
        version_label: str,
        semantic: Mapping[str, Any] | CharacterSemantic,
        workflow_metadata: Mapping[str, Any],
        source_character_id: Optional[str] = None,
        source_revision_id: Optional[str] = None,
        source_snapshot_hash: Optional[str] = None,
        source_ref: Optional[str] = None,
    ) -> CharacterAuthoringResult:
        store = self._require_store()
        try:
            prepared = self._prepare_initial_revision(
                character_id,
                version_id,
                revision_id,
                version_label,
                semantic,
                workflow_metadata,
            )
        except CharacterAuthoringError as exc:
            self._raise_authoring(exc)

        try:
            character_pointer = store.create_character(
                character_id, workflow_metadata=workflow_metadata
            )
        except CharacterAuthoringError as exc:
            self._raise_authoring(exc)

        partial = {
            "partial_state": True,
            "character_id": character_id,
            "version_id": version_id,
            "revision_id": revision_id,
        }
        try:
            version_pointer = store.create_version(
                character_id,
                version_id,
                version_label=version_label,
                lifecycle_state=LifecycleState.DRAFT,
                workflow_metadata=workflow_metadata,
            )
            record = store.persist_revision(
                character_id,
                version_id,
                revision_id,
                prepared.semantic,
                lifecycle_state=LifecycleState.DRAFT,
                workflow_metadata=workflow_metadata,
            )
            store.update_version_pointer(
                replace(version_pointer, selected_revision_id=revision_id)
            )
            store.update_character_pointer(
                replace(character_pointer, selected_version_id=version_id)
            )
        except CharacterAuthoringError as exc:
            self._raise_authoring(exc, details=partial)

        return self._result(
            operation,
            record,
            source_character_id=source_character_id,
            source_revision_id=source_revision_id,
            source_snapshot_hash=source_snapshot_hash,
            source_ref=source_ref,
        )

    def create_character(
        self,
        *,
        character_id: str,
        version_id: str,
        revision_id: str,
        version_label: str,
        semantic: Mapping[str, Any] | CharacterSemantic,
    ) -> CharacterAuthoringResult:
        return self._create_new_character(
            operation=CREATE,
            character_id=character_id,
            version_id=version_id,
            revision_id=revision_id,
            version_label=version_label,
            semantic=semantic,
            workflow_metadata={},
        )

    def save_character(
        self,
        *,
        character_id: str,
        version_id: str,
        revision_id: str,
        semantic: Mapping[str, Any] | CharacterSemantic,
    ) -> CharacterAuthoringResult:
        store = self._require_store()
        try:
            semantic_model = (
                semantic
                if isinstance(semantic, CharacterSemantic)
                else CharacterSemantic.from_dict(semantic)
            )
            snapshot_hash = compute_snapshot_hash(semantic_model)
            version_pointer = store.read_version_pointer(character_id, version_id)
            RevisionRecord(
                character_id=character_id,
                version_id=version_id,
                revision_id=revision_id,
                snapshot_hash=snapshot_hash,
                semantic=semantic_model,
                lifecycle_state=version_pointer.lifecycle_state,
            )
        except CharacterAuthoringError as exc:
            self._raise_authoring(exc)

        if version_pointer.lifecycle_state not in _EDITABLE_STATES:
            raise CharacterLabApplicationError(
                AUTHORING_NOT_EDITABLE,
                f"version {version_id!r} is not editable in state "
                f"{version_pointer.lifecycle_state.value}",
                details={"lifecycle_state": version_pointer.lifecycle_state.value},
            )

        try:
            record = store.persist_revision(
                character_id,
                version_id,
                revision_id,
                semantic_model,
                lifecycle_state=version_pointer.lifecycle_state,
            )
        except CharacterAuthoringError as exc:
            self._raise_authoring(exc)

        try:
            store.update_version_pointer(
                replace(version_pointer, selected_revision_id=revision_id)
            )
        except CharacterAuthoringError as exc:
            self._raise_authoring(
                exc,
                details={
                    "partial_state": True,
                    "revision_persisted": True,
                    "character_id": character_id,
                    "version_id": version_id,
                    "revision_id": revision_id,
                },
            )
        return self._result(SAVE, record)

    def submit_for_approval(
        self,
        *,
        character_id: str,
        version_id: str,
        revision_id: str,
        snapshot_hash: str,
    ) -> CharacterAuthoringResult:
        return self._transition_version(
            operation=SUBMIT,
            character_id=character_id,
            version_id=version_id,
            revision_id=revision_id,
            snapshot_hash=snapshot_hash,
            allowed_sources=frozenset(
                {LifecycleState.DRAFT, LifecycleState.CHANGES_REQUESTED}
            ),
            target_state=LifecycleState.PENDING_APPROVAL,
        )

    def request_changes(
        self,
        *,
        character_id: str,
        version_id: str,
        revision_id: str,
        snapshot_hash: str,
    ) -> CharacterAuthoringResult:
        return self._transition_version(
            operation=REQUEST_CHANGES,
            character_id=character_id,
            version_id=version_id,
            revision_id=revision_id,
            snapshot_hash=snapshot_hash,
            allowed_sources=frozenset({LifecycleState.PENDING_APPROVAL}),
            target_state=LifecycleState.CHANGES_REQUESTED,
        )

    def approve_as_canon(
        self,
        *,
        character_id: str,
        version_id: str,
        revision_id: str,
        snapshot_hash: str,
    ) -> CharacterAuthoringResult:
        return self._transition_version(
            operation=APPROVE,
            character_id=character_id,
            version_id=version_id,
            revision_id=revision_id,
            snapshot_hash=snapshot_hash,
            allowed_sources=frozenset({LifecycleState.PENDING_APPROVAL}),
            target_state=LifecycleState.APPROVED_AS_CANON,
        )

    def withdraw_submission(
        self,
        *,
        character_id: str,
        version_id: str,
        revision_id: str,
        snapshot_hash: str,
    ) -> CharacterAuthoringResult:
        return self._transition_version(
            operation=WITHDRAW,
            character_id=character_id,
            version_id=version_id,
            revision_id=revision_id,
            snapshot_hash=snapshot_hash,
            allowed_sources=frozenset({LifecycleState.PENDING_APPROVAL}),
            target_state=LifecycleState.WITHDRAWN,
        )

    def derive_version_from_approved(
        self,
        *,
        character_id: str,
        source_version_id: str,
        source_revision_id: str,
        source_snapshot_hash: str,
        new_version_id: str,
        new_revision_id: str,
        new_version_label: str,
    ) -> CharacterAuthoringResult:
        store = self._require_store()
        source_pointer, source_record = self._load_exact_selected_revision(
            store,
            character_id=character_id,
            version_id=source_version_id,
            revision_id=source_revision_id,
            snapshot_hash=source_snapshot_hash,
        )
        if source_pointer.lifecycle_state is not LifecycleState.APPROVED_AS_CANON:
            raise CharacterLabApplicationError(
                DERIVATION_SOURCE_NOT_APPROVED,
                "derived versions require an approved local authoring source",
                details={
                    "source_lifecycle_state": source_pointer.lifecycle_state.value
                },
            )

        try:
            character_pointer = store.read_character_pointer(character_id)
            VersionPointer(
                character_id=character_id,
                version_id=new_version_id,
                version_label=new_version_label,
                lifecycle_state=LifecycleState.DRAFT,
                selected_revision_id=new_revision_id,
                derived_from_version_id=source_version_id,
                derived_from_revision_id=source_revision_id,
                derived_from_snapshot_hash=source_snapshot_hash,
            )
            RevisionRecord(
                character_id=character_id,
                version_id=new_version_id,
                revision_id=new_revision_id,
                snapshot_hash=source_record.snapshot_hash,
                semantic=source_record.semantic,
                lifecycle_state=LifecycleState.DRAFT,
                derived_from_version_id=source_version_id,
                derived_from_revision_id=source_revision_id,
                derived_from_snapshot_hash=source_snapshot_hash,
            )
            if new_version_id in store.list_versions(character_id):
                raise CharacterLabApplicationError(
                    AUTHORING_ALREADY_EXISTS,
                    f"version {new_version_id!r} already exists",
                )
        except CharacterLabApplicationError:
            raise
        except (CharacterAuthoringError, OSError) as exc:
            self._raise_authoring(exc)

        try:
            version_pointer = store.create_version(
                character_id,
                new_version_id,
                version_label=new_version_label,
                lifecycle_state=LifecycleState.DRAFT,
                derived_from_version_id=source_version_id,
                derived_from_revision_id=source_revision_id,
                derived_from_snapshot_hash=source_snapshot_hash,
            )
        except (CharacterAuthoringError, OSError) as exc:
            self._raise_authoring(exc)

        partial = {
            "partial_state": True,
            "character_id": character_id,
            "version_id": new_version_id,
            "revision_id": new_revision_id,
        }
        try:
            record = store.persist_revision(
                character_id,
                new_version_id,
                new_revision_id,
                source_record.semantic,
                lifecycle_state=LifecycleState.DRAFT,
                derived_from_version_id=source_version_id,
                derived_from_revision_id=source_revision_id,
                derived_from_snapshot_hash=source_snapshot_hash,
            )
            store.update_version_pointer(
                replace(version_pointer, selected_revision_id=new_revision_id)
            )
            store.update_character_pointer(
                replace(character_pointer, selected_version_id=new_version_id)
            )
        except (CharacterAuthoringError, OSError) as exc:
            self._raise_authoring(exc, details=partial)

        return self._result(DERIVE_VERSION, record)

    def create_session_pin(
        self,
        *,
        character_id: str,
        version_id: str,
        revision_id: str,
    ) -> CharacterSessionPin:
        store = self._require_store()
        try:
            store.read_character_pointer(character_id)
            store.read_version_pointer(character_id, version_id)
            record = store.load_revision(character_id, version_id, revision_id)
        except (CharacterAuthoringError, OSError) as exc:
            self._raise_authoring(exc)
        return CharacterSessionPin(
            character_id=record.character_id,
            version_id=record.version_id,
            revision_id=record.revision_id,
            snapshot_hash=record.snapshot_hash,
        )

    def create_new_version(
        self,
        *,
        character_id: str,
        version_id: str,
        revision_id: str,
        version_label: str,
        semantic: Mapping[str, Any] | CharacterSemantic,
    ) -> CharacterAuthoringResult:
        store = self._require_store()
        try:
            prepared = self._prepare_initial_revision(
                character_id,
                version_id,
                revision_id,
                version_label,
                semantic,
                {},
            )
            character_pointer = store.read_character_pointer(character_id)
        except CharacterAuthoringError as exc:
            self._raise_authoring(exc)

        try:
            version_pointer = store.create_version(
                character_id,
                version_id,
                version_label=version_label,
                lifecycle_state=LifecycleState.DRAFT,
            )
        except CharacterAuthoringError as exc:
            self._raise_authoring(exc)

        partial = {
            "partial_state": True,
            "character_id": character_id,
            "version_id": version_id,
            "revision_id": revision_id,
        }
        try:
            record = store.persist_revision(
                character_id,
                version_id,
                revision_id,
                prepared.semantic,
                lifecycle_state=LifecycleState.DRAFT,
            )
            store.update_version_pointer(
                replace(version_pointer, selected_revision_id=revision_id)
            )
            store.update_character_pointer(
                replace(character_pointer, selected_version_id=version_id)
            )
        except CharacterAuthoringError as exc:
            self._raise_authoring(exc, details=partial)
        return self._result(NEW_VERSION, record)

    def import_character(
        self,
        *,
        source_character_id: str,
        character_id: str,
        version_id: str,
        revision_id: str,
        version_label: str,
    ) -> CharacterAuthoringResult:
        self._require_store()

        # Validate target identities before touching either persistence boundary.
        try:
            CharacterPointer(character_id, selected_version_id=version_id)
            VersionPointer(
                character_id=character_id,
                version_id=version_id,
                version_label=version_label,
                lifecycle_state=LifecycleState.DRAFT,
                selected_revision_id=revision_id,
            )
        except CharacterAuthoringError as exc:
            self._raise_authoring(exc)

        if self._canon_root is None:
            raise CharacterLabApplicationError(
                IMPORT_SOURCE_UNAVAILABLE,
                "Character Canon root is not configured for import",
            )
        try:
            snapshot = self._canon_reader(
                self._canon_root, source_character_id, "authoring"
            )
        except CharacterCanonBridgeError as exc:
            raise CharacterLabApplicationError(
                IMPORT_SOURCE_UNAVAILABLE,
                f"Character Canon import source {source_character_id!r} is unavailable",
            ) from exc
        except OSError as exc:
            raise CharacterLabApplicationError(
                IMPORT_SOURCE_UNAVAILABLE,
                f"Character Canon import source {source_character_id!r} is unavailable",
            ) from exc

        try:
            mapped_semantic = self._canon_semantic_mapper(snapshot)
        except Exception as exc:
            raise CharacterLabApplicationError(
                INTERNAL_ERROR,
                "Character Canon semantic mapping failed",
            ) from exc

        missing_fields = _missing_required_fields(mapped_semantic)
        if missing_fields:
            raise CharacterLabApplicationError(
                IMPORT_REQUIRES_AUTHORING_COMPLETION,
                "Character Canon source does not directly provide a complete "
                "Character Authoring semantic snapshot",
                details={"missing_fields": missing_fields},
            )

        provenance: dict[str, Any] = {
            "source_character_id": snapshot.character_id,
            "source_status": snapshot.status,
            "source_content_hash": snapshot.content_hash,
            "source_kind": snapshot.provenance.source_kind,
            "source_ref": snapshot.provenance.source_ref,
            "source_hash": snapshot.provenance.source_hash,
        }
        if snapshot.active_version is not None:
            provenance["source_version_id"] = snapshot.active_version
        workflow_metadata = {"import_provenance": provenance}

        return self._create_new_character(
            operation=IMPORT,
            character_id=character_id,
            version_id=version_id,
            revision_id=revision_id,
            version_label=version_label,
            semantic=mapped_semantic,
            workflow_metadata=workflow_metadata,
            source_character_id=snapshot.character_id,
            source_revision_id=None,
            source_snapshot_hash=snapshot.content_hash,
            source_ref=snapshot.provenance.source_ref,
        )
