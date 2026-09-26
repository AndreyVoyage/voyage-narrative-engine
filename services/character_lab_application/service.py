#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Character Lab Application Service v1 -- thin UI-agnostic facade.

Hides from UI code:

- Character Canon storage layout and raw domain exception types;
- session identity/storage details;
- CRP reconstruction-engine internals (role prompts, registry storage,
  provider transport).

This is an application layer, NOT a new domain model. It never reimplements
Character Canon read semantics, never mutates Character Canon, and never
chooses a UI/desktop technology. Sessions are a local, offline, in-memory
application concept only -- there is no provider/network call anywhere in
this module.

CRP delegation methods (see bottom of ``CharacterLabApplicationService``) are
pure pass-through wrappers over ``services.crp_authoring.application_adapter``
-- the sole authorized CRP import surface for this package (dependency
direction: this module -> ``crp_authoring.application_adapter`` -> CRP
internals; never the reverse, never a deeper CRP submodule directly). No CRP
domain/reconstruction logic is reimplemented here, and no provider is ever
constructed by this module.
"""

from __future__ import annotations

import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Tuple

from services.character_canon_bridge import (
    CharacterCanonBridgeError,
    list_character_ids,
    read_character_canon,
)
from services.character_canon_bridge.status import is_production_approved
from services.character_authoring import ApprovalClock, CharacterAuthoringNotFoundError
from services.character_publication import (
    CharacterPublicationService,
    PublicationNotApprovedError,
    PublicationPackageCollisionError,
    PublicationSourceCorruptError,
    PublicationStaleRevisionError,
    PublicationStaleSnapshotError,
    PublicationStorageError,
    PublicationValidationError,
)
from services.crp_authoring.application_adapter import (
    AcceptedReconstructionResult,
    CandidateCharacterPackage,
    CrpValidationError,
    KnowledgeProfile,
    R3RelevanceResult,
    ReconstructionAudit,
    ReconstructionPlan,
    RoleRegistry,
    RoleResult,
    RoleTask,
    SourceEvidence,
    ValidationReport,
)
from services.crp_authoring.application_adapter import evaluate_specialist_relevance as _crp_evaluate_specialist_relevance
from services.crp_authoring.application_adapter import get_reconstruction_result as _crp_get_reconstruction_result
from services.crp_authoring.application_adapter import prepare_reconstruction as _crp_prepare_reconstruction
from services.crp_authoring.application_adapter import start_reconstruction as _crp_start_reconstruction

from .authoring import (
    CanonReader,
    CanonSemanticMapper,
    _CharacterAuthoringUseCases,
    _default_canon_semantic_mapper,
)
from .config import CharacterLabApplicationConfig
from .errors import (
    AUTHORING_NOT_FOUND,
    AUTHORING_UNAVAILABLE,
    CANON_UNAVAILABLE,
    CRP_VALIDATION_FAILED,
    INVALID_INPUT,
    NOT_FOUND,
    PUBLICATION_NOT_APPROVED,
    PUBLICATION_PACKAGE_COLLISION,
    PUBLICATION_SOURCE_CORRUPT,
    PUBLICATION_STALE_REVISION,
    PUBLICATION_STALE_SNAPSHOT,
    PUBLICATION_STORAGE_FAILED,
    PUBLICATION_VALIDATION_FAILED,
    RELEASE_STORE_UNAVAILABLE,
    VCP_UNAVAILABLE,
    CharacterLabApplicationError,
)
from .results import (
    AuthoringCharacterSummary,
    AuthoringRevisionSummary,
    AuthoringVersionSummary,
    CanonicalCurrentSummary,
    CharacterAuthoringResult,
    CharacterPublicationResult,
    CharacterSessionPin,
    CharacterInspectorDetail,
    CharacterSummary,
    CharacterVersionSummary,
    LabSession,
    Message,
    PublishedReleaseSummary,
    RevisionSemanticData,
)

_CHARACTER_USAGE_CONTEXT = "authoring"


class CharacterLabApplicationService:
    """Character Lab facade: character read-side + local session model."""

    def __init__(
        self,
        config: CharacterLabApplicationConfig,
        *,
        canon_import_reader: Optional[CanonReader] = None,
        canon_semantic_mapper: Optional[CanonSemanticMapper] = None,
        approval_clock: Optional[ApprovalClock] = None,
    ) -> None:
        self._config = config
        self._sessions: dict[str, LabSession] = {}
        self._session_order: list[str] = []
        self._authoring = _CharacterAuthoringUseCases(
            config.character_authoring_root,
            config.character_canon_root,
            canon_reader=canon_import_reader or read_character_canon,
            canon_semantic_mapper=(
                canon_semantic_mapper or _default_canon_semantic_mapper
            ),
            approval_clock=approval_clock,
        )

    # -- Local Character Authoring S2 use-cases ---------------------------

    def create_character(
        self,
        *,
        character_id: str,
        version_id: str,
        revision_id: str,
        version_label: str,
        semantic: Mapping[str, Any],
    ) -> CharacterAuthoringResult:
        """Create one local DRAFT character/version/initial revision."""

        return self._authoring.create_character(
            character_id=character_id,
            version_id=version_id,
            revision_id=revision_id,
            version_label=version_label,
            semantic=semantic,
        )

    def save_character(
        self,
        *,
        character_id: str,
        version_id: str,
        revision_id: str,
        semantic: Mapping[str, Any],
    ) -> CharacterAuthoringResult:
        """Save a full snapshot as a new revision in the same version."""

        return self._authoring.save_character(
            character_id=character_id,
            version_id=version_id,
            revision_id=revision_id,
            semantic=semantic,
        )

    def submit_for_approval(
        self,
        *,
        character_id: str,
        version_id: str,
        revision_id: str,
        snapshot_hash: str,
    ) -> CharacterAuthoringResult:
        """Freeze the exact selected revision for human approval review."""

        return self._authoring.submit_for_approval(
            character_id=character_id,
            version_id=version_id,
            revision_id=revision_id,
            snapshot_hash=snapshot_hash,
        )

    def request_changes(
        self,
        *,
        character_id: str,
        version_id: str,
        revision_id: str,
        snapshot_hash: str,
    ) -> CharacterAuthoringResult:
        """Return the exact pending revision to editable workflow state."""

        return self._authoring.request_changes(
            character_id=character_id,
            version_id=version_id,
            revision_id=revision_id,
            snapshot_hash=snapshot_hash,
        )

    def approve_as_canon(
        self,
        *,
        character_id: str,
        version_id: str,
        revision_id: str,
        snapshot_hash: str,
        decided_by: str,
    ) -> CharacterAuthoringResult:
        """Record explicit human approval of one immutable local artifact.

        ``decided_by`` is the human approver, supplied explicitly by the
        caller. The approval time is captured by Character Lab itself, and
        both are persisted as write-once approval evidence before the version
        transitions to ``APPROVED_AS_CANON``.
        """

        return self._authoring.approve_as_canon(
            character_id=character_id,
            version_id=version_id,
            revision_id=revision_id,
            snapshot_hash=snapshot_hash,
            decided_by=decided_by,
        )

    def withdraw_submission(
        self,
        *,
        character_id: str,
        version_id: str,
        revision_id: str,
        snapshot_hash: str,
    ) -> CharacterAuthoringResult:
        """Withdraw the exact pending submission into terminal local state."""

        return self._authoring.withdraw_submission(
            character_id=character_id,
            version_id=version_id,
            revision_id=revision_id,
            snapshot_hash=snapshot_hash,
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
        """Copy an exact approved snapshot into a new editable DRAFT version."""

        return self._authoring.derive_version_from_approved(
            character_id=character_id,
            source_version_id=source_version_id,
            source_revision_id=source_revision_id,
            source_snapshot_hash=source_snapshot_hash,
            new_version_id=new_version_id,
            new_revision_id=new_revision_id,
            new_version_label=new_version_label,
        )

    def create_session_pin(
        self,
        *,
        character_id: str,
        version_id: str,
        revision_id: str,
    ) -> CharacterSessionPin:
        """Return an exact immutable revision identity without changing state."""

        return self._authoring.create_session_pin(
            character_id=character_id,
            version_id=version_id,
            revision_id=revision_id,
        )

    def publish_character_version(
        self,
        *,
        character_id: str,
        version_id: str,
        revision_id: str,
        snapshot_hash: str,
    ) -> CharacterPublicationResult:
        """Publish one exact approved revision as an immutable local package."""

        authoring_root = self._config.character_authoring_root
        if authoring_root is None:
            raise CharacterLabApplicationError(
                AUTHORING_UNAVAILABLE,
                "Character Authoring store root is not configured",
            )
        publication_root = authoring_root.parent / "character_authoring_publication"
        try:
            published = CharacterPublicationService(
                authoring_root, publication_root
            ).publish_character_version(
                character_id=character_id,
                version_id=version_id,
                revision_id=revision_id,
                snapshot_hash=snapshot_hash,
            )
        except CharacterAuthoringNotFoundError as exc:
            raise CharacterLabApplicationError(
                AUTHORING_NOT_FOUND, str(exc)
            ) from exc
        except PublicationNotApprovedError as exc:
            raise CharacterLabApplicationError(
                PUBLICATION_NOT_APPROVED, str(exc)
            ) from exc
        except PublicationStaleRevisionError as exc:
            raise CharacterLabApplicationError(
                PUBLICATION_STALE_REVISION, str(exc)
            ) from exc
        except PublicationStaleSnapshotError as exc:
            raise CharacterLabApplicationError(
                PUBLICATION_STALE_SNAPSHOT, str(exc)
            ) from exc
        except PublicationSourceCorruptError as exc:
            raise CharacterLabApplicationError(
                PUBLICATION_SOURCE_CORRUPT, str(exc)
            ) from exc
        except PublicationValidationError as exc:
            raise CharacterLabApplicationError(
                PUBLICATION_VALIDATION_FAILED, str(exc)
            ) from exc
        except PublicationPackageCollisionError as exc:
            raise CharacterLabApplicationError(
                PUBLICATION_PACKAGE_COLLISION, str(exc)
            ) from exc
        except PublicationStorageError as exc:
            raise CharacterLabApplicationError(
                PUBLICATION_STORAGE_FAILED, str(exc)
            ) from exc
        return CharacterPublicationResult(
            runtime_package_schema_version=(
                published.runtime_package_schema_version
            ),
            character_id=published.character_id,
            package_hash=published.package_hash,
            source_version_id=published.source_version_id,
            source_revision_id=published.source_revision_id,
            source_snapshot_hash=published.source_snapshot_hash,
        )

    def create_new_version(
        self,
        *,
        character_id: str,
        version_id: str,
        revision_id: str,
        version_label: str,
        semantic: Mapping[str, Any],
    ) -> CharacterAuthoringResult:
        """Explicitly create a new DRAFT logical version and initial revision."""

        return self._authoring.create_new_version(
            character_id=character_id,
            version_id=version_id,
            revision_id=revision_id,
            version_label=version_label,
            semantic=semantic,
        )

    def import_character(
        self,
        *,
        source_character_id: str,
        character_id: str,
        version_id: str,
        revision_id: str,
        version_label: str,
    ) -> CharacterAuthoringResult:
        """Import a directly mappable Canon source into a new local DRAFT."""

        return self._authoring.import_character(
            source_character_id=source_character_id,
            character_id=character_id,
            version_id=version_id,
            revision_id=revision_id,
            version_label=version_label,
        )

    # -- Local Character Authoring read-side (thin, over the S1 store) ---

    def list_authoring_characters(self) -> tuple[AuthoringCharacterSummary, ...]:
        """List local Character Authoring characters (not Character Canon)."""

        if self._config.character_authoring_root is None:
            return ()
        result: list[AuthoringCharacterSummary] = []
        for character_id in self._authoring.list_character_ids():
            try:
                pointer = self._authoring.read_character_pointer(character_id)
                selected_version_id = pointer.selected_version_id
            except CharacterLabApplicationError:
                selected_version_id = None
            result.append(
                AuthoringCharacterSummary(
                    character_id=character_id,
                    selected_version_id=selected_version_id,
                )
            )
        return tuple(result)

    def list_authoring_versions(
        self, character_id: str
    ) -> tuple[AuthoringVersionSummary, ...]:
        """List local Authoring versions for one character."""

        if self._config.character_authoring_root is None:
            return ()
        result: list[AuthoringVersionSummary] = []
        for version_id in self._authoring.list_versions(character_id):
            pointer = self._authoring.read_version_pointer(character_id, version_id)
            result.append(
                AuthoringVersionSummary(
                    version_id=pointer.version_id,
                    version_label=pointer.version_label,
                    lifecycle_state=pointer.lifecycle_state.value,
                    selected_revision_id=pointer.selected_revision_id,
                )
            )
        return tuple(result)

    def list_authoring_revisions(
        self, character_id: str, version_id: str
    ) -> tuple[AuthoringRevisionSummary, ...]:
        """List immutable local Authoring revisions for one version."""

        if self._config.character_authoring_root is None:
            return ()
        result: list[AuthoringRevisionSummary] = []
        for revision_id in self._authoring.list_revisions(character_id, version_id):
            record = self._authoring.load_revision(character_id, version_id, revision_id)
            result.append(
                AuthoringRevisionSummary(
                    revision_id=revision_id,
                    snapshot_hash=record.snapshot_hash,
                    lifecycle_state=record.lifecycle_state.value,
                    created_at=record.created_at,
                )
            )
        return tuple(result)

    def load_revision_semantic(
        self, character_id: str, version_id: str, revision_id: str
    ) -> RevisionSemanticData:
        """Load one exact revision's identity plus its editable semantic data."""

        record = self._authoring.load_revision(character_id, version_id, revision_id)
        return RevisionSemanticData(
            character_id=record.character_id,
            version_id=record.version_id,
            revision_id=record.revision_id,
            snapshot_hash=record.snapshot_hash,
            lifecycle_state=record.lifecycle_state.value,
            semantic=record.semantic.to_dict(),
        )

    def read_version_lifecycle(
        self, character_id: str, version_id: str
    ) -> AuthoringVersionSummary:
        """Read the current version/lifecycle pointer for one version."""

        pointer = self._authoring.read_version_pointer(character_id, version_id)
        return AuthoringVersionSummary(
            version_id=pointer.version_id,
            version_label=pointer.version_label,
            lifecycle_state=pointer.lifecycle_state.value,
            selected_revision_id=pointer.selected_revision_id,
        )

    # -- LAB-L5 release read-side + publication boundary (lazy VCP) ------

    def _release_store(self) -> Any:
        """Construct the LAB-L4 release store, lazily importing VCP."""

        root = self._config.character_release_store_root
        if root is None:
            raise CharacterLabApplicationError(
                RELEASE_STORE_UNAVAILABLE,
                "Character Release store root is not configured",
            )
        try:
            from services.character_publication.release_store import (
                CharacterReleaseStore,
            )
        except ImportError as exc:
            raise CharacterLabApplicationError(
                VCP_UNAVAILABLE,
                "Character Release store requires the Voyage Character Platform (VCP)",
            ) from exc
        return CharacterReleaseStore(root)

    def list_published_releases(
        self, character_id: str
    ) -> tuple[PublishedReleaseSummary, ...]:
        """List durable LAB-L5 releases for one character (path-free)."""

        if self._config.character_release_store_root is None:
            return ()
        store = self._release_store()
        result: list[PublishedReleaseSummary] = []
        for release_id in store.list_release_ids(character_id):
            record = store.load_release_record(character_id, release_id)
            result.append(
                PublishedReleaseSummary(
                    release_id=record.release_id,
                    package_hash=record.package_hash,
                    artifact_sha256=record.artifact_sha256,
                    byte_length=record.byte_length,
                    published_at=record.published_at,
                    source_version_id=record.source.source_version_id,
                    source_revision_id=record.source.source_revision_id,
                    source_snapshot_hash=record.source.source_snapshot_hash,
                )
            )
        return tuple(result)

    def read_canonical_current(
        self, character_id: str
    ) -> Optional[CanonicalCurrentSummary]:
        """Read the mutable canonical-current pointer, if present."""

        if self._config.character_release_store_root is None:
            return None
        store = self._release_store()
        current = store.get_canonical_current(character_id)
        if current is None:
            return None
        return CanonicalCurrentSummary(
            character_id=current.character_id,
            release_id=current.release_id,
            package_hash=current.package_hash,
            generation=current.generation,
        )

    def publish_character_release(
        self,
        *,
        character_id: str,
        version_id: str,
        revision_id: str,
        snapshot_hash: str,
        release_id: str,
        display_name: str,
        set_current: bool = False,
        build_workspace_root: Optional[Path] = None,
        export_destination: Optional[Path] = None,
    ) -> Any:
        """Publish one exact approved revision through the closed LAB-L5 facade.

        PUBLISH != SET CURRENT: publication never designates current unless
        ``set_current`` is True. VCP is imported lazily so normal startup does
        not require it. Partial-success semantics are preserved: a late-stage
        failure raises the LAB-L5 ``CharacterReleasePublicationError`` subtype
        whose ``result``/``published`` expose the already-durable release.
        """

        authoring_store = self._authoring._require_store()
        release_store = self._release_store()

        from services.character_lab_application.release_publication import (
            publish_character_release as _publish_character_release,
        )

        workspace = build_workspace_root
        owned_workspace: Optional[Path] = None
        if workspace is None:
            owned_workspace = Path(tempfile.mkdtemp(prefix="lab-release-build-"))
            workspace = owned_workspace
        try:
            return _publish_character_release(
                authoring_store=authoring_store,
                release_store=release_store,
                character_id=character_id,
                version_id=version_id,
                revision_id=revision_id,
                snapshot_hash=snapshot_hash,
                release_id=release_id,
                display_name=display_name,
                build_workspace_root=workspace,
                set_current=set_current,
                export_destination=export_destination,
            )
        finally:
            if owned_workspace is not None:
                shutil.rmtree(owned_workspace, ignore_errors=True)

    def designate_canonical_current(
        self,
        *,
        character_id: str,
        release_id: str,
    ) -> Any:
        """Explicitly designate an already-published release current (no build)."""

        release_store = self._release_store()

        from services.character_lab_application.release_publication import (
            designate_canonical_current as _designate_canonical_current,
        )

        return _designate_canonical_current(
            release_store=release_store,
            character_id=character_id,
            release_id=release_id,
        )

    def export_character_release(
        self,
        *,
        character_id: str,
        release_id: str,
        destination: Path | str,
    ) -> Any:
        """Export the exact STORED ``.vchar`` of a durable release (no rebuild)."""

        release_store = self._release_store()

        from services.character_lab_application.release_publication import (
            export_character_release as _export_character_release,
        )

        return _export_character_release(
            release_store=release_store,
            character_id=character_id,
            release_id=release_id,
            destination=destination,
        )

    # -- Character read-side (READ-ONLY over Character Canon) -----------

    def list_characters(self) -> tuple[CharacterSummary, ...]:
        """Return deterministic Character Lab-facing character summaries.

        Returns an empty tuple when no Character Canon root is configured,
        the root has no discoverable entries, or an individual character
        entry cannot be read -- never raises for this read path (the same
        graceful-degradation contract as ``services.editor_application``).
        """
        canon_root = self._config.character_canon_root
        if canon_root is None:
            return ()
        summaries: list[CharacterSummary] = []
        for character_id in list_character_ids(canon_root):
            try:
                snapshot = read_character_canon(canon_root, character_id, _CHARACTER_USAGE_CONTEXT)
            except CharacterCanonBridgeError:
                continue
            summaries.append(
                CharacterSummary(
                    character_id=character_id,
                    label=character_id,
                    status=snapshot.status,
                )
            )
        summaries.sort(key=lambda summary: summary.character_id)
        return tuple(summaries)

    def get_character_detail(self, character_id: str) -> CharacterInspectorDetail:
        """Return inspector detail for one character.

        Raises ``CharacterLabApplicationError`` (never a raw traceback) when
        Character Canon is not configured, the character is unknown, or its
        Canon entry cannot be read.
        """
        if not isinstance(character_id, str) or not character_id:
            raise CharacterLabApplicationError(INVALID_INPUT, "character_id must be a non-empty string")
        canon_root = self._config.character_canon_root
        if canon_root is None:
            raise CharacterLabApplicationError(CANON_UNAVAILABLE, "Character Canon root is not configured")
        try:
            snapshot = read_character_canon(canon_root, character_id, _CHARACTER_USAGE_CONTEXT)
        except CharacterCanonBridgeError as exc:
            raise CharacterLabApplicationError(
                NOT_FOUND, f"Character Canon unavailable for {character_id!r}: {exc}"
            ) from exc
        return CharacterInspectorDetail(
            character_id=snapshot.character_id,
            label=snapshot.character_id,
            status=snapshot.status,
            canon_approved=is_production_approved(snapshot.status),
            active_version_id=snapshot.active_version,
            source_ref=snapshot.provenance.source_ref,
        )

    def list_versions(self, character_id: str) -> tuple[CharacterVersionSummary, ...]:
        """Return the character's versions exactly as represented by current data.

        Current-main Character Canon carries a single ``active_version``
        string tag per character (no version history store). This returns
        zero entries when no tag is present, or exactly one entry -- marked
        active -- when it is. Never invents additional demo versions.
        """
        detail = self.get_character_detail(character_id)
        if detail.active_version_id is None:
            return ()
        return (CharacterVersionSummary(version_id=detail.active_version_id, is_active=True),)

    # -- Local session model (offline; no provider/network call) --------

    def create_session(self, character_id: str, version_id: Optional[str] = None) -> LabSession:
        """Create and bind a new local, offline session. Works without network."""
        if not isinstance(character_id, str) or not character_id:
            raise CharacterLabApplicationError(INVALID_INPUT, "character_id must be a non-empty string")
        session_id = uuid.uuid4().hex
        session = LabSession(
            session_id=session_id,
            character_id=character_id,
            version_id=version_id,
            transcript=(),
        )
        self._sessions[session_id] = session
        self._session_order.append(session_id)
        return session

    def list_sessions(self) -> tuple[LabSession, ...]:
        """Return sessions in creation order."""
        return tuple(self._sessions[session_id] for session_id in self._session_order)

    def get_session(self, session_id: str) -> LabSession:
        session = self._sessions.get(session_id)
        if session is None:
            raise CharacterLabApplicationError(NOT_FOUND, f"no session with id {session_id!r}")
        return session

    def append_message(self, session_id: str, role: str, content: str) -> LabSession:
        """Append one local transcript entry. Offline only -- no provider call.

        Returns the updated session; the session's ``character_id``/
        ``version_id`` binding is unchanged by this call.
        """
        session = self.get_session(session_id)
        if not isinstance(role, str) or not role:
            raise CharacterLabApplicationError(INVALID_INPUT, "role must be a non-empty string")
        if not isinstance(content, str) or not content:
            raise CharacterLabApplicationError(INVALID_INPUT, "content must be a non-empty string")
        updated = LabSession(
            session_id=session.session_id,
            character_id=session.character_id,
            version_id=session.version_id,
            transcript=session.transcript + (Message(role=role, content=content),),
        )
        self._sessions[session_id] = updated
        return updated

    # -- CRP reconstruction delegation ------------------------------------
    #
    # Pure pass-through wrappers over services.crp_authoring.application_adapter.
    # No CRP domain/reconstruction logic is reimplemented here. No provider is
    # ever constructed by this class; provider_callable is always supplied by
    # the caller, exactly as the CRP adapter itself requires. Evaluating R3
    # relevance NEVER authorizes execution and NEVER fabricates an
    # activation_authorization_ref -- that remains a separate, explicit,
    # caller-supplied value on the RoleTask itself (CRP's existing hard gate,
    # unchanged and unweakened by this class).

    def evaluate_specialist_relevance(self, evidence: Iterable[SourceEvidence]) -> R3RelevanceResult:
        """Delegate to CRP's R3 relevance boundary. Relevance is data only."""
        try:
            return _crp_evaluate_specialist_relevance(evidence)
        except CrpValidationError as exc:
            raise CharacterLabApplicationError(CRP_VALIDATION_FAILED, str(exc)) from exc

    def prepare_reconstruction(
        self,
        *,
        subject_id: str,
        run_id: str,
        evidence_snapshot_id: str,
        evidence: Tuple[SourceEvidence, ...],
        registry: RoleRegistry,
        profiles: Mapping[str, KnowledgeProfile],
        role_tasks: Tuple[RoleTask, ...],
        compile_context: Any,
        audit_policy: Any,
        evidence_payloads: Mapping[str, Mapping[str, Any]],
    ) -> ReconstructionPlan:
        """Delegate to CRP's ``prepare_reconstruction``. No provider call.

        Identity-consistency validation (subject/run/evidence-snapshot across
        every role task) and the R3 authorization gate are both enforced by
        the CRP layer itself, unchanged; this method neither re-implements
        nor relaxes either.
        """
        try:
            return _crp_prepare_reconstruction(
                subject_id=subject_id,
                run_id=run_id,
                evidence_snapshot_id=evidence_snapshot_id,
                evidence=evidence,
                registry=registry,
                profiles=profiles,
                role_tasks=role_tasks,
                compile_context=compile_context,
                audit_policy=audit_policy,
                evidence_payloads=evidence_payloads,
            )
        except CrpValidationError as exc:
            raise CharacterLabApplicationError(CRP_VALIDATION_FAILED, str(exc)) from exc

    def start_reconstruction(
        self,
        plan: ReconstructionPlan,
        provider_callable: Any,
    ) -> Tuple[CandidateCharacterPackage, ReconstructionAudit, ValidationReport, Tuple[RoleResult, ...]]:
        """Delegate to CRP's existing synchronous orchestrator entrypoint.

        ``provider_callable`` is always caller-supplied; this method never
        constructs a provider and never performs network I/O itself.
        """
        try:
            return _crp_start_reconstruction(plan, provider_callable)
        except CrpValidationError as exc:
            raise CharacterLabApplicationError(CRP_VALIDATION_FAILED, str(exc)) from exc

    def get_reconstruction_result(self, root: Any, subject_id: str) -> AcceptedReconstructionResult:
        """Delegate to CRP's read-only loader for a previously ACCEPTED package.

        Never writes, never mutates Character Canon, never promotes anything.
        """
        try:
            return _crp_get_reconstruction_result(root, subject_id)
        except CrpValidationError as exc:
            raise CharacterLabApplicationError(CRP_VALIDATION_FAILED, str(exc)) from exc
