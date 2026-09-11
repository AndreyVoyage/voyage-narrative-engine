#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Editor Application Service v1 -- thin UI-agnostic facade over domain services.

Hides from UI code:

- filesystem storage paths;
- base32 authority-path encoding;
- ``SceneDraftStore`` internals;
- manifest/batch storage details;
- acceptance orchestration details;
- canon directory layout;
- raw domain exception types.

This is an application layer, NOT a new domain model. It never reimplements
domain semantics, never creates parallel persistence formats, never mutates
accepted authority merely to repair project inclusion state, and never chooses
a UI/desktop technology.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from services.ass import OrderedASSStore, OrderedASSStoreError
from services.character_canon_bridge import (
    CharacterCanonBridgeError,
    list_character_ids,
    read_character_canon,
)
from services.location_canon import (
    LocationCanonError,
    list_location_ids,
    load_location,
)
from services.scene_body import SceneBodyError, validate_acceptance_complete
from services.scene_draft import (
    LIFECYCLE_ACCEPTED,
    LIFECYCLE_DRAFT,
    AcceptedVersionImmutableError,
    AlreadyAcceptedError,
    SceneDraftError,
    SceneDraftStore,
    SceneHistoryExistsError,
    SceneIdMismatchError,
    SceneValidationError,
    SceneVersionNotFoundError,
    accept_draft,
)
from services.workspace_project import (
    ACCEPTED_BATCH_SCHEMA_VERSION,
    PROJECT_MANIFEST_SCHEMA_VERSION,
    SCENE,
    AcceptedBatchNotFoundError,
    AcceptedOrderedASSBatch,
    AcceptedOrderedASSRef,
    ProjectEntityRef,
    ProjectManifest,
    ProjectManifestNotFoundError,
    WorkspaceProjectError,
    load_accepted_batch,
    load_manifest,
    resolve_accepted_ordered_ass_batch,
    save_accepted_batch,
    save_manifest,
)

from .config import EditorApplicationConfig
from .errors import (
    ACCEPTED_IMMUTABLE,
    ALREADY_EXISTS,
    INTERNAL_ERROR,
    INVALID_INPUT,
    IO_FAILURE,
    NOT_FOUND,
    OK,
    PARTIAL_PROJECT_STATE,
    VALIDATION_FAILED,
    EditorApplicationError,
)
from .results import (
    EditorAcceptanceState,
    EditorCharacterSummary,
    EditorDiagnostic,
    EditorLocationSummary,
    EditorOperationResult,
    EditorSceneSummary,
    EditorSceneWorkspace,
)

_CHARACTER_USAGE_CONTEXT = "authoring"

# The validator prefixes entry-localized messages with "<kind> entry '<id>':".
# (Choice-OPTION messages carry an option_id, not an entry_id, and are left
# unlocalized: we do not guess entry identity from an option id.)
_ENTRY_ID_RE = re.compile(r"(?:text|choice|visual) entry '([^']+)'")


def _ok(message, *, scene_id=None, version=None, lifecycle=None, diagnostics=()):
    return EditorOperationResult(
        ok=True,
        code=OK,
        message=message,
        scene_id=scene_id,
        version=version,
        lifecycle=lifecycle,
        diagnostics=tuple(diagnostics),
    )


def _fail(code, message, *, scene_id=None, version=None, lifecycle=None, diagnostics=(), partial_state=False, recovery_required=False):
    return EditorOperationResult(
        ok=False,
        code=code,
        message=message,
        scene_id=scene_id,
        version=version,
        lifecycle=lifecycle,
        diagnostics=tuple(diagnostics),
        partial_state=partial_state,
        recovery_required=recovery_required,
    )


class EditorApplicationService:
    """UI-agnostic application facade over the scene-editor domain services.

    Constructed once from a bounded ``EditorApplicationConfig``. UI code then
    calls only stable-ID / version-keyed operations and receives structured
    DTOs / results.
    """

    def __init__(self, config: EditorApplicationConfig) -> None:
        self._config = config
        self._scene_store = SceneDraftStore(config.scene_drafts_root)
        self._ass_store = OrderedASSStore(config.accepted_ass_root)

    # ------------------------------------------------------------------ errors

    @staticmethod
    def _map_exception(exc: BaseException) -> str:
        if isinstance(exc, (SceneVersionNotFoundError, ProjectManifestNotFoundError)):
            return NOT_FOUND
        if isinstance(exc, (AcceptedVersionImmutableError, AlreadyAcceptedError)):
            return ACCEPTED_IMMUTABLE
        if isinstance(exc, SceneHistoryExistsError):
            return ALREADY_EXISTS
        if isinstance(exc, (SceneIdMismatchError, SceneValidationError, SceneBodyError)):
            return INVALID_INPUT
        if isinstance(exc, SceneDraftError):
            return IO_FAILURE
        if isinstance(exc, (WorkspaceProjectError, OrderedASSStoreError)):
            return IO_FAILURE
        return INTERNAL_ERROR

    @staticmethod
    def _normalize_body(body: Any, scene_id: str) -> dict[str, Any]:
        if not isinstance(body, dict):
            raise EditorApplicationError(INVALID_INPUT, "body must be an object")
        payload = dict(body)
        payload.setdefault("scene_id", scene_id)
        return payload

    @staticmethod
    def _diagnostic_from_error(message: str) -> EditorDiagnostic:
        entry_id: Optional[str] = None
        match = _ENTRY_ID_RE.search(message)
        if match:
            entry_id = match.group(1)
        return EditorDiagnostic(
            code=VALIDATION_FAILED,
            message=message,
            severity="error",
            entry_id=entry_id,
            field=None,
        )

    def _diagnostics_from_errors(self, errors) -> tuple[EditorDiagnostic, ...]:
        return tuple(self._diagnostic_from_error(message) for message in errors)

    # -------------------------------------------------------------- internals

    def _scene_source_ref(self, scene_id: str) -> str:
        return f"{self._config.scene_drafts_source_ref}/{scene_id}/pointer.json"

    def _ass_source_ref(self, scene_id: str, version: int) -> str:
        return f"{self._config.scene_drafts_source_ref}/{scene_id}/versions/{version}.json"

    def _latest_version(self, scene_id: str) -> Optional[int]:
        """Read the scene's ``latest_version`` pointer (mirrors SceneDraftStore layout)."""
        pointer_path = self._config.scene_drafts_root / scene_id / "pointer.json"
        if not pointer_path.exists():
            return None
        try:
            data = json.loads(pointer_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        if not isinstance(data, dict):
            return None
        latest = data.get("latest_version")
        if isinstance(latest, int) and not isinstance(latest, bool) and latest >= 1:
            return latest
        return None

    def _find_accepted(self, scene_id: str, latest: int):
        """Return ``(accepted_version, ass_id)`` of the highest ACCEPTED version."""
        for version in range(latest, 0, -1):
            try:
                record = self._scene_store.read_version(scene_id, version)
            except SceneDraftError:
                continue
            if record.lifecycle == LIFECYCLE_ACCEPTED and record.acceptance is not None:
                return version, record.acceptance.ass_id
        return None, None

    def _manifest_includes(self, scene_id: str) -> bool:
        try:
            manifest = load_manifest(self._config.manifest_path)
        except WorkspaceProjectError:
            return False
        return any(
            entity.entity_kind == SCENE and entity.stable_id == scene_id
            for entity in manifest.entities
        )

    def _batch_state(self, scene_id: str, version: int) -> tuple[bool, bool]:
        try:
            batch = load_accepted_batch(self._config.batch_path)
        except (AcceptedBatchNotFoundError, WorkspaceProjectError):
            return False, False
        included = any(
            ref.scene_id == scene_id and ref.version == version
            for ref in batch.scene_refs
        )
        try:
            manifest = load_manifest(self._config.manifest_path)
        except WorkspaceProjectError:
            return included, False
        try:
            resolve_accepted_ordered_ass_batch(
                batch,
                project_manifest=manifest,
                ass_store=self._ass_store,
                scene_draft_store=self._scene_store,
            )
        except (WorkspaceProjectError, OrderedASSStoreError):
            return included, False
        return included, True

    # --------------------------------------------------------------- discovery

    def list_scenes(self) -> tuple[EditorSceneSummary, ...]:
        """Return deterministic editor-facing scene summaries from the manifest."""
        try:
            manifest = load_manifest(self._config.manifest_path)
        except ProjectManifestNotFoundError:
            return ()
        except WorkspaceProjectError as exc:
            raise EditorApplicationError(IO_FAILURE, f"cannot load manifest: {exc}") from exc

        summaries: list[EditorSceneSummary] = []
        for entity in manifest.entities:
            if entity.entity_kind != SCENE:
                continue
            scene_id = entity.stable_id
            latest = self._latest_version(scene_id)
            lifecycle: Optional[str] = None
            title: Optional[str] = None
            accepted_version: Optional[int] = None
            ass_id: Optional[str] = None
            if latest is not None:
                try:
                    record = self._scene_store.read_version(scene_id, latest)
                except SceneDraftError:
                    record = None
                if record is not None:
                    lifecycle = record.lifecycle
                    title = record.body.scene_title
                    if record.lifecycle == LIFECYCLE_ACCEPTED:
                        accepted_version = latest
                        ass_id = record.acceptance.ass_id if record.acceptance else None
                    else:
                        accepted_version, ass_id = self._find_accepted(scene_id, latest)
            summaries.append(
                EditorSceneSummary(
                    scene_id=scene_id,
                    title=title,
                    latest_version=latest,
                    lifecycle=lifecycle,
                    accepted_version=accepted_version,
                    ass_id=ass_id,
                )
            )
        summaries.sort(key=lambda summary: summary.scene_id)
        return tuple(summaries)

    def list_characters(self) -> tuple[EditorCharacterSummary, ...]:
        """Return deterministic editor-facing character summaries.

        Returns an empty tuple when no Character Canon root is configured or the
        root has no discoverable entries (the external NCC canon is not part of
        this repository).
        """
        canon_root = self._config.character_canon_root
        if canon_root is None:
            return ()
        summaries: list[EditorCharacterSummary] = []
        for character_id in list_character_ids(canon_root):
            try:
                snapshot = read_character_canon(canon_root, character_id, _CHARACTER_USAGE_CONTEXT)
            except CharacterCanonBridgeError:
                continue
            summaries.append(
                EditorCharacterSummary(
                    character_id=character_id,
                    label=character_id,
                    status=snapshot.status,
                )
            )
        summaries.sort(key=lambda summary: summary.character_id)
        return tuple(summaries)

    def list_locations(self) -> tuple[EditorLocationSummary, ...]:
        """Return deterministic editor-facing location summaries."""
        summaries: list[EditorLocationSummary] = []
        for location_id in list_location_ids(self._config.repo_root):
            try:
                canon = load_location(self._config.repo_root, location_id)
            except LocationCanonError:
                continue
            summaries.append(
                EditorLocationSummary(
                    location_id=location_id,
                    label=location_id,
                    tier=canon.tier,
                )
            )
        summaries.sort(key=lambda summary: summary.location_id)
        return tuple(summaries)

    # --------------------------------------------------------------- workspace

    def get_scene_workspace(self, scene_id: str) -> EditorSceneWorkspace:
        """Return the aggregate editor-facing view of one scene."""
        latest = self._latest_version(scene_id)
        if latest is None:
            raise EditorApplicationError(
                NOT_FOUND, f"scene {scene_id!r} has no version history"
            )
        try:
            record = self._scene_store.read_version(scene_id, latest)
        except SceneDraftError as exc:
            raise EditorApplicationError(self._map_exception(exc), str(exc)) from exc
        acceptance = (
            record.acceptance.to_dict() if record.acceptance is not None else None
        )
        return EditorSceneWorkspace(
            scene_id=scene_id,
            latest_version=latest,
            lifecycle=record.lifecycle,
            body=record.body_plain(),
            acceptance=acceptance,
            can_fork_next_version=True,
            manifest_included=self._manifest_includes(scene_id),
        )

    # ---------------------------------------------------------------- lifecycle

    def create_scene(self, scene_id: str, body: dict[str, Any]) -> EditorOperationResult:
        payload = self._normalize_body(body, scene_id)
        try:
            record = self._scene_store.create_initial_draft(scene_id, payload)
        except SceneHistoryExistsError as exc:
            return _fail(ALREADY_EXISTS, str(exc), scene_id=scene_id)
        except SceneDraftError as exc:
            return _fail(self._map_exception(exc), str(exc), scene_id=scene_id)
        try:
            self._ensure_manifest_inclusion(scene_id)
        except WorkspaceProjectError as exc:
            return _fail(
                PARTIAL_PROJECT_STATE,
                f"scene {scene_id!r} created as draft but manifest registration failed: {exc}",
                scene_id=scene_id,
                version=record.version,
                lifecycle=record.lifecycle,
                recovery_required=True,
            )
        return _ok(
            f"scene {record.scene_id!r} created as version {record.version}",
            scene_id=record.scene_id,
            version=record.version,
            lifecycle=record.lifecycle,
        )

    def save_draft(self, scene_id: str, version: int, body: dict[str, Any]) -> EditorOperationResult:
        payload = self._normalize_body(body, scene_id)
        try:
            record = self._scene_store.save_draft(scene_id, version, payload)
        except AcceptedVersionImmutableError as exc:
            return _fail(ACCEPTED_IMMUTABLE, str(exc), scene_id=scene_id, version=version)
        except SceneVersionNotFoundError as exc:
            return _fail(NOT_FOUND, str(exc), scene_id=scene_id, version=version)
        except SceneDraftError as exc:
            return _fail(self._map_exception(exc), str(exc), scene_id=scene_id, version=version)
        return _ok(
            f"scene {record.scene_id!r} version {record.version} saved",
            scene_id=record.scene_id,
            version=record.version,
            lifecycle=record.lifecycle,
        )

    def fork_scene_version(self, scene_id: str, from_version: int) -> EditorOperationResult:
        try:
            record = self._scene_store.fork_draft_from_version(scene_id, from_version)
        except SceneVersionNotFoundError as exc:
            return _fail(NOT_FOUND, str(exc), scene_id=scene_id, version=from_version)
        except SceneDraftError as exc:
            return _fail(self._map_exception(exc), str(exc), scene_id=scene_id, version=from_version)
        return _ok(
            f"scene {record.scene_id!r} forked to version {record.version}",
            scene_id=record.scene_id,
            version=record.version,
            lifecycle=record.lifecycle,
        )

    def validate_scene(self, scene_id: str, version: int) -> EditorOperationResult:
        try:
            record = self._scene_store.read_version(scene_id, version)
        except SceneVersionNotFoundError as exc:
            return _fail(NOT_FOUND, str(exc), scene_id=scene_id, version=version)
        except SceneDraftError as exc:
            return _fail(self._map_exception(exc), str(exc), scene_id=scene_id, version=version)
        errors = validate_acceptance_complete(record.body)
        if errors:
            return _fail(
                VALIDATION_FAILED,
                f"scene {scene_id!r} version {version} is not acceptance-complete",
                scene_id=scene_id,
                version=version,
                lifecycle=record.lifecycle,
                diagnostics=self._diagnostics_from_errors(errors),
            )
        return _ok(
            f"scene {scene_id!r} version {version} is acceptance-complete",
            scene_id=scene_id,
            version=version,
            lifecycle=record.lifecycle,
        )

    # ---------------------------------------------------------------- acceptance

    def accept_scene(self, scene_id: str, version: int) -> EditorOperationResult:
        """Accept a DRAFT and coordinate manifest + batch inclusion.

        Deterministic and idempotent: if the version is already ACCEPTED (e.g. a
        prior run was interrupted after acceptance), the missing manifest/batch
        inclusion is completed rather than re-accepting. Accepted authority
        (SceneVersion + canonical ASS) is never rewritten to repair inclusion.
        """
        try:
            record = self._scene_store.read_version(scene_id, version)
        except SceneVersionNotFoundError as exc:
            return _fail(NOT_FOUND, str(exc), scene_id=scene_id, version=version)
        except SceneDraftError as exc:
            return _fail(self._map_exception(exc), str(exc), scene_id=scene_id, version=version)

        if record.lifecycle != LIFECYCLE_ACCEPTED:
            errors = validate_acceptance_complete(record.body)
            if errors:
                return _fail(
                    VALIDATION_FAILED,
                    f"scene {scene_id!r} version {version} is not acceptance-complete",
                    scene_id=scene_id,
                    version=version,
                    lifecycle=LIFECYCLE_DRAFT,
                    diagnostics=self._diagnostics_from_errors(errors),
                )
            ass_id = f"ass_{scene_id}_v{version}"
            source_ref = self._ass_source_ref(scene_id, version)
            try:
                updated, _persisted = accept_draft(
                    self._scene_store,
                    scene_id,
                    version,
                    ass_store=self._ass_store,
                    ass_id=ass_id,
                    source_ref=source_ref,
                )
            except AlreadyAcceptedError:
                updated = self._scene_store.read_version(scene_id, version)
            except SceneDraftError as exc:
                return _fail(
                    self._map_exception(exc),
                    str(exc),
                    scene_id=scene_id,
                    version=version,
                    lifecycle=LIFECYCLE_DRAFT,
                )
        else:
            updated = record

        acceptance = updated.acceptance
        if acceptance is None:
            return _fail(
                PARTIAL_PROJECT_STATE,
                f"scene {scene_id!r} version {version} is ACCEPTED but has no AcceptanceLink",
                scene_id=scene_id,
                version=version,
                lifecycle=updated.lifecycle,
                recovery_required=True,
            )

        try:
            self._ensure_manifest_inclusion(scene_id)
            self._ensure_batch_inclusion(
                scene_id, version, acceptance.ass_id, acceptance.ass_content_hash
            )
        except WorkspaceProjectError as exc:
            return _fail(
                PARTIAL_PROJECT_STATE,
                f"scene {scene_id!r} version {version} accepted but project inclusion incomplete: {exc}",
                scene_id=scene_id,
                version=version,
                lifecycle=LIFECYCLE_ACCEPTED,
                recovery_required=True,
            )

        return _ok(
            f"scene {scene_id!r} version {version} accepted and included",
            scene_id=scene_id,
            version=version,
            lifecycle=LIFECYCLE_ACCEPTED,
        )

    def _ensure_manifest_inclusion(self, scene_id: str) -> bool:
        """Add the scene as a SCENE member if missing; return True if changed."""
        try:
            manifest = load_manifest(self._config.manifest_path)
        except ProjectManifestNotFoundError:
            manifest = ProjectManifest(
                schema_version=PROJECT_MANIFEST_SCHEMA_VERSION,
                project_id=self._config.project_id,
                entities=(),
            )
        existing_ids = {
            entity.stable_id for entity in manifest.entities if entity.entity_kind == SCENE
        }
        if scene_id in existing_ids:
            return False
        new_entity = ProjectEntityRef(
            entity_kind=SCENE,
            stable_id=scene_id,
            source_ref=self._scene_source_ref(scene_id),
        )
        new_manifest = ProjectManifest(
            schema_version=manifest.schema_version,
            project_id=manifest.project_id,
            entities=manifest.entities + (new_entity,),
        )
        save_manifest(self._config.manifest_path, new_manifest)
        return True

    def _ensure_batch_inclusion(
        self, scene_id: str, version: int, ass_id: str, ass_content_hash: str
    ) -> bool:
        """Add/refresh the scene's accepted ref in the batch; return True if changed."""
        ref = AcceptedOrderedASSRef(
            scene_id=scene_id,
            version=version,
            ass_id=ass_id,
            ass_content_hash=ass_content_hash,
        )
        try:
            batch = load_accepted_batch(self._config.batch_path)
        except AcceptedBatchNotFoundError:
            batch = None

        if batch is None:
            new_batch = AcceptedOrderedASSBatch(
                schema_version=ACCEPTED_BATCH_SCHEMA_VERSION,
                project_id=self._config.project_id,
                scene_refs=(ref,),
            )
            save_accepted_batch(self._config.batch_path, new_batch)
            return True

        existing = {existing_ref.scene_id: existing_ref for existing_ref in batch.scene_refs}
        if existing.get(scene_id) == ref:
            return False

        if scene_id in existing:
            new_refs = tuple(
                ref if existing_ref.scene_id == scene_id else existing_ref
                for existing_ref in batch.scene_refs
            )
        else:
            new_refs = batch.scene_refs + (ref,)
        new_batch = AcceptedOrderedASSBatch(
            schema_version=batch.schema_version,
            project_id=batch.project_id,
            scene_refs=new_refs,
        )
        save_accepted_batch(self._config.batch_path, new_batch)
        return True

    def get_acceptance_state(self, scene_id: str, version: int) -> EditorAcceptanceState:
        """Return read-only acceptance/inclusion state for one scene version."""
        try:
            record = self._scene_store.read_version(scene_id, version)
        except SceneDraftError as exc:
            raise EditorApplicationError(self._map_exception(exc), str(exc)) from exc
        accepted = record.lifecycle == LIFECYCLE_ACCEPTED
        batch_included, batch_resolvable = self._batch_state(scene_id, version)
        return EditorAcceptanceState(
            scene_id=scene_id,
            version=version,
            lifecycle=record.lifecycle,
            accepted=accepted,
            ass_id=record.acceptance.ass_id if record.acceptance else None,
            ass_content_hash=(
                record.acceptance.ass_content_hash if record.acceptance else None
            ),
            manifest_included=self._manifest_includes(scene_id),
            batch_included=batch_included,
            batch_resolvable=batch_resolvable,
        )

    # ---------------------------------------------------------------- publication

    def get_publication_readiness(self) -> EditorOperationResult:
        """Read-only publication readiness query (does NOT publish).

        Reports whether the accepted batch fully resolves through the existing
        controlled domain pipeline. Canonical publication remains a separate,
        higher-impact downstream operation and is not performed here.
        """
        try:
            manifest = load_manifest(self._config.manifest_path)
        except ProjectManifestNotFoundError:
            return _fail(NOT_FOUND, "project manifest does not exist")
        except WorkspaceProjectError as exc:
            return _fail(IO_FAILURE, f"cannot load manifest: {exc}")

        try:
            batch = load_accepted_batch(self._config.batch_path)
        except AcceptedBatchNotFoundError:
            return _fail(NOT_FOUND, "accepted batch does not exist")
        except WorkspaceProjectError as exc:
            return _fail(IO_FAILURE, f"cannot load batch: {exc}")

        try:
            resolved = resolve_accepted_ordered_ass_batch(
                batch,
                project_manifest=manifest,
                ass_store=self._ass_store,
                scene_draft_store=self._scene_store,
            )
        except (WorkspaceProjectError, OrderedASSStoreError) as exc:
            return _fail(
                PARTIAL_PROJECT_STATE,
                f"accepted batch does not fully resolve: {exc}",
                diagnostics=(
                    EditorDiagnostic(
                        code=PARTIAL_PROJECT_STATE,
                        message=str(exc),
                        severity="error",
                    ),
                ),
            )

        return _ok(f"{len(resolved)} accepted scene(s) resolvable for publication")
