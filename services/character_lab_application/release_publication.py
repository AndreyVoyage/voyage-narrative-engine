#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Character Lab Application Service -- LAB-L5 native release publication facade.

Orchestration only, over the closed publication chain:

    exact approved Authoring coordinate
        -> LAB-L2 ``compile_authoring_release``       (pure logical release)
        -> LAB-L3 ``build_verified_vchar_artifact``   (verified ``.vchar``)
        -> LAB-L4 ``CharacterReleaseStore.publish_release``
        -> optional explicit ``set_canonical_current``
        -> optional ``export_release`` of the STORED artifact

No semantic, package, archive or store logic is reimplemented here.

PUBLISH != SET CURRENT: publication never designates current unless the caller
explicitly asks (``set_current=True``), and designation only runs after the
release is durably committed. A later designation or export failure never
rolls back or deletes the published release; the raised
``CharacterReleasePublicationError`` carries the partial ``result``.

Workspace ownership: the caller supplies an existing directory; each
publication allocates one fresh L5-owned operation directory beneath it, lets
LAB-L3 build there, and removes exactly that directory once LAB-L4 has
committed (or reused) the durable release, or once the attempt has failed.
Nothing else is ever deleted. Designation and export run after that cleanup,
so they depend only on durable release-store state.

Like the LAB-L2..L4 modules this module imports the VCP distribution and is
therefore deliberately NOT re-exported from ``services.character_lab_application``.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Optional

from services.character_authoring import (
    CharacterAuthoringError,
    CharacterAuthoringStore,
    LifecycleState,
)
from services.character_publication.release_store import (
    CharacterReleaseStore,
    CharacterReleaseStoreError,
    validate_release_id,
)
from services.character_publication.vcp_artifact import (
    AuthoringVcpArtifactBuildError,
    build_verified_vchar_artifact,
)
from services.character_publication.vcp_domains import (
    AuthoringVcpDomainCompilationError,
)
from services.character_publication.vcp_release import (
    AuthoringVcpApprovalEvidenceError,
    compile_authoring_release,
)

from .errors import (
    ARTIFACT_BUILD_FAILED,
    AUTHORING_NOT_APPROVED,
    CURRENT_DESIGNATION_FAILED,
    EXPORT_FAILED,
    INVALID_INPUT,
    PUBLICATION_FAILED,
    RELEASE_COMPILATION_FAILED,
    CharacterLabApplicationError,
)

_OPERATION_PREFIX = "lab-release-build-"
_BUILD_DIRNAME = "build"


class CurrentDesignationStatus(str, Enum):
    NOT_REQUESTED = "NOT_REQUESTED"
    DESIGNATED = "DESIGNATED"
    ALREADY_CURRENT = "ALREADY_CURRENT"
    FAILED = "FAILED"


class ReleaseExportStatus(str, Enum):
    NOT_REQUESTED = "NOT_REQUESTED"
    EXPORTED = "EXPORTED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class CharacterReleaseExportResult:
    """The exact stored ``.vchar`` copied to the caller's destination."""

    destination: Path
    character_id: str
    release_id: str
    package_hash: str
    artifact_sha256: str
    byte_length: int


@dataclass(frozen=True)
class CharacterCurrentDesignationResult:
    """Outcome of one explicit canonical-current designation."""

    character_id: str
    release_id: str
    package_hash: str
    generation: int
    status: CurrentDesignationStatus


@dataclass(frozen=True)
class CharacterReleasePublicationResult:
    """Path-free identity and status of one durable Character Lab release.

    ``published`` is True whenever this object exists: it is only produced
    after LAB-L4 committed (``newly_published=True``) or reused
    (``newly_published=False``) the durable release. Temporary build paths are
    never part of it; the durable identity is
    (``character_id``, ``release_id``, ``package_hash``).
    """

    character_id: str
    release_id: str
    package_hash: str
    artifact_sha256: str
    byte_length: int
    aggregate_candidate_id: str
    aggregate_hash: str
    acceptance_record_hash: str
    source_version_id: str
    source_revision_id: str
    source_snapshot_hash: str
    published_at: str
    newly_published: bool
    current_status: CurrentDesignationStatus = CurrentDesignationStatus.NOT_REQUESTED
    current_generation: Optional[int] = None
    export_status: ReleaseExportStatus = ReleaseExportStatus.NOT_REQUESTED
    export: Optional[CharacterReleaseExportResult] = None
    build_workspace_cleaned: bool = True

    @property
    def published(self) -> bool:
        return True


class CharacterReleasePublicationError(CharacterLabApplicationError):
    """A LAB-L5 stage failed; ``code`` names the stage.

    ``lower_code`` is the closed-service category (for example LAB-L4
    ``RELEASE_ID_HASH_COLLISION``) and the closed-service exception is kept as
    ``__cause__``. ``result`` is set only when the release was already durably
    published before the failing stage (designation or export): the release
    then remains valid and ``published`` is True.
    """

    def __init__(
        self,
        code: str,
        message: str,
        *,
        lower_code: Optional[str] = None,
        result: Optional[CharacterReleasePublicationResult] = None,
    ) -> None:
        details: dict[str, object] = {"published": result is not None}
        if lower_code is not None:
            details["lower_code"] = lower_code
        super().__init__(code, message, details=details)
        self.lower_code = lower_code
        self.result = result

    @property
    def published(self) -> bool:
        return self.result is not None


def _lower_code(exc: BaseException) -> Optional[str]:
    code = getattr(exc, "code", None)
    if isinstance(code, str):
        return code
    stage = getattr(exc, "stage", None)
    if isinstance(stage, Enum):
        return str(stage.value)
    return type(exc).__name__


def _stage_error(
    code: str,
    exc: BaseException,
    *,
    result: Optional[CharacterReleasePublicationResult] = None,
) -> CharacterReleasePublicationError:
    lower = _lower_code(exc)
    error = CharacterReleasePublicationError(
        code, f"{code}: {exc}", lower_code=lower, result=result
    )
    error.__cause__ = exc
    return error


def _invalid(message: str) -> CharacterReleasePublicationError:
    return CharacterReleasePublicationError(INVALID_INPUT, message)


def _require_release_store(release_store: object) -> CharacterReleaseStore:
    if not isinstance(release_store, CharacterReleaseStore):
        raise _invalid("release_store must be a LAB-L4 CharacterReleaseStore")
    return release_store


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
    except (ValueError, OSError):
        return False
    return True


def _require_approved(
    authoring_store: CharacterAuthoringStore,
    character_id: str,
    version_id: str,
    revision_id: str,
) -> None:
    """Caller-side lifecycle gate that LAB-L2 leaves to its caller."""

    try:
        pointer = authoring_store.read_version_pointer(character_id, version_id)
    except CharacterAuthoringError as exc:
        raise _stage_error(AUTHORING_NOT_APPROVED, exc) from exc
    if pointer.lifecycle_state is not LifecycleState.APPROVED_AS_CANON:
        raise CharacterReleasePublicationError(
            AUTHORING_NOT_APPROVED,
            f"version is {pointer.lifecycle_state.value}, not APPROVED_AS_CANON",
            lower_code=pointer.lifecycle_state.value,
        )
    if pointer.selected_revision_id != revision_id:
        raise CharacterReleasePublicationError(
            AUTHORING_NOT_APPROVED,
            "revision is not the approved selected revision of the version",
        )


def _allocate_operation_dir(
    build_workspace_root: object, release_store: CharacterReleaseStore
) -> Path:
    if not isinstance(build_workspace_root, (str, os.PathLike)):
        raise _invalid("build_workspace_root must be a path")
    parent = Path(build_workspace_root)
    if not parent.is_absolute() or ".." in parent.parts:
        raise _invalid("build_workspace_root must be an absolute path without '..'")
    if not parent.is_dir():
        raise _invalid("build_workspace_root must be an existing directory")
    if _is_within(parent, release_store.root):
        raise _invalid("build_workspace_root must be outside the release store")
    try:
        return Path(tempfile.mkdtemp(prefix=_OPERATION_PREFIX, dir=str(parent)))
    except OSError as exc:
        raise _invalid(f"build workspace cannot be allocated: {exc}") from exc


def _cleanup_operation_dir(operation_dir: Path) -> bool:
    """Remove exactly the L5-owned operation directory; report completeness."""

    shutil.rmtree(operation_dir, ignore_errors=True)
    return not os.path.lexists(operation_dir)


def designate_canonical_current(
    *,
    release_store: CharacterReleaseStore,
    character_id: str,
    release_id: str,
) -> CharacterCurrentDesignationResult:
    """Explicitly designate an already-published release current (also rollback).

    Never builds or publishes anything; delegates to LAB-L4
    ``set_canonical_current``.
    """

    store = _require_release_store(release_store)
    try:
        before = store.get_canonical_current(character_id)
    except CharacterReleaseStoreError:
        before = None  # LAB-L4 designation itself decides whether state is usable
    try:
        current = store.set_canonical_current(character_id, release_id)
    except CharacterReleaseStoreError as exc:
        raise _stage_error(CURRENT_DESIGNATION_FAILED, exc) from exc
    unchanged = before is not None and before == current
    return CharacterCurrentDesignationResult(
        character_id=current.character_id,
        release_id=current.release_id,
        package_hash=current.package_hash,
        generation=current.generation,
        status=(
            CurrentDesignationStatus.ALREADY_CURRENT
            if unchanged
            else CurrentDesignationStatus.DESIGNATED
        ),
    )


def export_character_release(
    *,
    release_store: CharacterReleaseStore,
    character_id: str,
    release_id: str,
    destination: Path | str,
) -> CharacterReleaseExportResult:
    """Export the exact STORED ``.vchar`` of a durable release (LAB-L4)."""

    store = _require_release_store(release_store)
    try:
        exported = store.export_release(character_id, release_id, destination)
    except CharacterReleaseStoreError as exc:
        raise _stage_error(EXPORT_FAILED, exc) from exc
    return CharacterReleaseExportResult(
        destination=exported.path,
        character_id=exported.character_id,
        release_id=exported.release_id,
        package_hash=exported.package_hash,
        artifact_sha256=exported.artifact_sha256,
        byte_length=exported.byte_length,
    )


def publish_character_release(
    *,
    authoring_store: CharacterAuthoringStore,
    release_store: CharacterReleaseStore,
    character_id: str,
    version_id: str,
    revision_id: str,
    snapshot_hash: str,
    release_id: str,
    display_name: str,
    build_workspace_root: Path | str,
    set_current: bool = False,
    export_destination: Optional[Path | str] = None,
) -> CharacterReleasePublicationResult:
    """Publish one exact approved Authoring revision as a durable Lab release.

    ``release_id`` and ``display_name`` are explicit operator input and are
    never derived. Current is designated only when ``set_current`` is True,
    and only after durable publication.
    """

    if not isinstance(authoring_store, CharacterAuthoringStore):
        raise _invalid("authoring_store must be a CharacterAuthoringStore")
    store = _require_release_store(release_store)
    if not isinstance(set_current, bool):
        raise _invalid("set_current must be an explicit bool")
    try:
        validate_release_id(release_id)
    except CharacterReleaseStoreError as exc:
        raise _stage_error(INVALID_INPUT, exc) from exc

    _require_approved(authoring_store, character_id, version_id, revision_id)

    try:
        compilation = compile_authoring_release(
            authoring_store,
            character_id=character_id,
            version_id=version_id,
            revision_id=revision_id,
            snapshot_hash=snapshot_hash,
            release_id=release_id,
            display_name=display_name,
        )
    except AuthoringVcpApprovalEvidenceError as exc:
        # No LAB-L1 evidence bound to the exact revision: not approved.
        raise _stage_error(AUTHORING_NOT_APPROVED, exc) from exc
    except (AuthoringVcpDomainCompilationError, CharacterAuthoringError) as exc:
        raise _stage_error(RELEASE_COMPILATION_FAILED, exc) from exc

    operation_dir = _allocate_operation_dir(build_workspace_root, store)
    try:
        try:
            built = build_verified_vchar_artifact(
                compilation, operation_dir / _BUILD_DIRNAME
            )
        except AuthoringVcpArtifactBuildError as exc:
            raise _stage_error(ARTIFACT_BUILD_FAILED, exc) from exc
        try:
            published = store.publish_release(built, authoring_store=authoring_store)
        except CharacterReleaseStoreError as exc:
            raise _stage_error(PUBLICATION_FAILED, exc) from exc
    finally:
        cleaned = _cleanup_operation_dir(operation_dir)

    record = published.record
    result = CharacterReleasePublicationResult(
        character_id=record.character_id,
        release_id=record.release_id,
        package_hash=record.package_hash,
        artifact_sha256=record.artifact_sha256,
        byte_length=record.byte_length,
        aggregate_candidate_id=record.aggregate_candidate_id,
        aggregate_hash=record.aggregate_hash,
        acceptance_record_hash=record.acceptance_record_hash,
        source_version_id=record.source.source_version_id,
        source_revision_id=record.source.source_revision_id,
        source_snapshot_hash=record.source.source_snapshot_hash,
        published_at=record.published_at,
        newly_published=published.newly_published,
        build_workspace_cleaned=cleaned,
    )

    if set_current:
        try:
            designation = designate_canonical_current(
                release_store=store,
                character_id=record.character_id,
                release_id=record.release_id,
            )
        except CharacterReleasePublicationError as exc:
            partial = replace(result, current_status=CurrentDesignationStatus.FAILED)
            raise _stage_error(
                CURRENT_DESIGNATION_FAILED, exc.__cause__ or exc, result=partial
            ) from (exc.__cause__ or exc)
        result = replace(
            result,
            current_status=designation.status,
            current_generation=designation.generation,
        )

    if export_destination is not None:
        try:
            exported = export_character_release(
                release_store=store,
                character_id=record.character_id,
                release_id=record.release_id,
                destination=export_destination,
            )
        except CharacterReleasePublicationError as exc:
            partial = replace(result, export_status=ReleaseExportStatus.FAILED)
            raise _stage_error(
                EXPORT_FAILED, exc.__cause__ or exc, result=partial
            ) from (exc.__cause__ or exc)
        result = replace(
            result, export_status=ReleaseExportStatus.EXPORTED, export=exported
        )
    return result


__all__ = [
    "CharacterCurrentDesignationResult",
    "CharacterReleaseExportResult",
    "CharacterReleasePublicationError",
    "CharacterReleasePublicationResult",
    "CurrentDesignationStatus",
    "ReleaseExportStatus",
    "designate_canonical_current",
    "export_character_release",
    "publish_character_release",
]
