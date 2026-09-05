#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scene Editor domain lifecycle -- persistence and lifecycle operations.

An explicit caller-provided root is required; no database, no migrations, no
directory-wide scene discovery. A small deterministic internal layout is used
because this slice genuinely requires persistence:

    <root>/<scene_id>/pointer.json             -> {scene_id, latest_version}
    <root>/<scene_id>/versions/<version>.json  -> one SceneVersion record

Logical identity is ``(scene_id, version)``; a path is a locator only. Next
version allocation reads ONLY the persisted ``latest_version`` pointer (never a
directory scan, filename, path name, or timestamp).

All writes use the established VNE house style: write to a sibling temp file,
then ``os.replace`` into place, so a reader never observes a partial write.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .errors import (
    AcceptedVersionImmutableError,
    AlreadyAcceptedError,
    PersistenceError,
    SceneDraftError,
    SceneHistoryExistsError,
    SceneVersionNotFoundError,
)
from .model import (
    LIFECYCLE_ACCEPTED,
    LIFECYCLE_DRAFT,
    AcceptanceLink,
    SceneVersion,
)

_POINTER_FILENAME = "pointer.json"
_VERSIONS_DIRNAME = "versions"


def serialize_version_record(record: SceneVersion) -> str:
    """Return the deterministic UTF-8 JSON serialization of one SceneVersion."""
    return json.dumps(record.to_dict(), indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def serialize_pointer(scene_id: str, latest_version: int) -> str:
    """Return the deterministic UTF-8 JSON serialization of a pointer record.

    The pointer contains only ``scene_id`` and ``latest_version`` -- no content,
    no acceptance, no speculative metadata.
    """
    payload = {"scene_id": scene_id, "latest_version": latest_version}
    return json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def _is_safe_scene_id(scene_id: Any) -> bool:
    return (
        isinstance(scene_id, str)
        and scene_id != ""
        and scene_id not in (".", "..")
        and "/" not in scene_id
        and "\\" not in scene_id
    )


class SceneDraftStore:
    """Persistent store for per-scene authored versions and latest-version pointers."""

    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    # ------------------------------------------------------------------ paths

    def _scene_dir(self, scene_id: str) -> Path:
        if not _is_safe_scene_id(scene_id):
            raise PersistenceError(f"unsafe scene_id: {scene_id!r}")
        return self._root / scene_id

    def _pointer_path(self, scene_id: str) -> Path:
        return self._scene_dir(scene_id) / _POINTER_FILENAME

    def _version_path(self, scene_id: str, version: int) -> Path:
        return self._scene_dir(scene_id) / _VERSIONS_DIRNAME / f"{version}.json"

    # -------------------------------------------------------------- io utils

    def _atomic_write(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".scene_draft_", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(text)
            os.replace(tmp, str(path))
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def _remove_version_file(self, scene_id: str, version: int) -> None:
        path = self._version_path(scene_id, version)
        try:
            if path.exists():
                path.unlink()
        except OSError:
            pass

    # -------------------------------------------------------------- pointers

    def _write_pointer(self, scene_id: str, latest_version: int) -> None:
        self._atomic_write(
            self._pointer_path(scene_id), serialize_pointer(scene_id, latest_version)
        )

    def _read_pointer(self, scene_id: str) -> int:
        path = self._pointer_path(scene_id)
        if not path.exists():
            raise PersistenceError(f"scene {scene_id!r} has no latest_version pointer")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise PersistenceError(f"pointer is malformed: {exc}") from exc
        if not isinstance(data, dict):
            raise PersistenceError("pointer root must be an object")
        if data.get("scene_id") != scene_id:
            raise PersistenceError("pointer scene_id mismatch")
        latest = data.get("latest_version")
        if not isinstance(latest, int) or isinstance(latest, bool) or latest < 1:
            raise PersistenceError("pointer latest_version must be a positive integer")
        return latest

    # -------------------------------------------------------------- records

    def _write_version_record(self, record: SceneVersion) -> None:
        self._atomic_write(
            self._version_path(record.scene_id, record.version),
            serialize_version_record(record),
        )

    def _read_version_record(self, scene_id: str, version: int) -> SceneVersion:
        path = self._version_path(scene_id, version)
        if not path.exists():
            raise SceneVersionNotFoundError(f"scene {scene_id!r} version {version} not found")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise PersistenceError(f"version record is malformed: {exc}") from exc
        try:
            record = SceneVersion.from_dict(data)
        except SceneDraftError as exc:
            raise PersistenceError(f"version record is malformed: {exc}") from exc
        if record.scene_id != scene_id:
            raise PersistenceError("version record scene_id mismatch")
        if record.version != version:
            raise PersistenceError("version record version mismatch")
        if data.get("content_hash") != record.content_hash:
            raise PersistenceError("version record content_hash mismatch")
        return record

    # ------------------------------------------------------- domain ops

    def create_initial_draft(self, scene_id: str, body: dict[str, Any]) -> SceneVersion:
        """Create version 1 as DRAFT. Fails if the scene history already exists."""
        if self._pointer_path(scene_id).exists():
            raise SceneHistoryExistsError(f"scene {scene_id!r} already has a version history")
        record = SceneVersion(scene_id=scene_id, version=1, lifecycle=LIFECYCLE_DRAFT, body=body)
        self._write_version_record(record)
        try:
            self._write_pointer(scene_id, 1)
        except BaseException:
            self._remove_version_file(scene_id, 1)
            raise
        return record

    def save_draft(self, scene_id: str, version: int, body: dict[str, Any]) -> SceneVersion:
        """Replace an existing DRAFT record in place; never increments version.

        Trusts the persisted lifecycle, not caller claims. ACCEPTED versions are
        immutable and raise ``AcceptedVersionImmutableError`` without touching the
        file.
        """
        existing = self._read_version_record(scene_id, version)
        if existing.lifecycle == LIFECYCLE_ACCEPTED:
            raise AcceptedVersionImmutableError(
                f"scene {scene_id!r} version {version} is ACCEPTED and immutable"
            )
        record = SceneVersion(scene_id=scene_id, version=version, lifecycle=LIFECYCLE_DRAFT, body=body)
        self._write_version_record(record)
        return record

    def fork_draft_from_version(self, scene_id: str, source_version: int) -> SceneVersion:
        """Create a new highest-versioned DRAFT copied from an existing version.

        Covers both "edit Accepted" and "restore an old version". Never modifies
        the source record. Allocates ``latest_version + 1``.
        """
        source = self._read_version_record(scene_id, source_version)
        latest = self._read_pointer(scene_id)
        new_version = latest + 1
        record = SceneVersion(
            scene_id=scene_id,
            version=new_version,
            lifecycle=LIFECYCLE_DRAFT,
            body=source.body_plain(),
        )
        self._write_version_record(record)
        try:
            self._write_pointer(scene_id, new_version)
        except BaseException:
            self._remove_version_file(scene_id, new_version)
            raise
        return record

    def read_version(self, scene_id: str, version: int) -> SceneVersion:
        """Read a persisted version; read-only, fail closed, no mutation."""
        return self._read_version_record(scene_id, version)

    def commit_acceptance(
        self, scene_id: str, version: int, acceptance: AcceptanceLink
    ) -> SceneVersion:
        """Atomically transition an existing DRAFT to ACCEPTED in place.

        Re-reads the persisted record (state on disk is authority), requires
        DRAFT, and preserves the exact authored body and content hash. The
        pointer is NOT changed. One-time: a second call raises
        ``AlreadyAcceptedError``.
        """
        existing = self._read_version_record(scene_id, version)
        if existing.lifecycle != LIFECYCLE_DRAFT:
            raise AlreadyAcceptedError(
                f"scene {scene_id!r} version {version} is not DRAFT"
            )
        record = SceneVersion(
            scene_id=scene_id,
            version=version,
            lifecycle=LIFECYCLE_ACCEPTED,
            body=existing.body_plain(),
            acceptance=acceptance,
        )
        self._write_version_record(record)
        return record
