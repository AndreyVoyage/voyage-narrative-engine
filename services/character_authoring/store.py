"""Durable JSON file store for local Character Authoring application data."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Optional

from .errors import (
    CharacterAuthoringAlreadyExistsError,
    CharacterAuthoringCorruptionError,
    CharacterAuthoringNotFoundError,
    CharacterAuthoringStorageError,
    CharacterAuthoringValidationError,
    ImmutableRevisionError,
    SnapshotHashMismatchError,
)
from .hashing import compute_snapshot_hash
from .model import (
    CharacterPointer,
    CharacterSemantic,
    LifecycleState,
    RevisionRecord,
    VersionPointer,
    parse_lifecycle,
)
from .validation import validate_distinct_identities, validate_identifier


def default_store_root(repo_root: Path | str) -> Path:
    return Path(repo_root) / "local_runs" / "character_authoring"


class CharacterAuthoringStore:
    """Headless, restart-safe store with immutable full revision snapshots."""

    def __init__(self, root: Path | str) -> None:
        self._root = Path(root).resolve()
        try:
            self._root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise CharacterAuthoringStorageError("failed to initialize store root") from exc
        if not self._root.is_dir():
            raise CharacterAuthoringStorageError("store root is not a directory")

    @classmethod
    def for_repository(cls, repo_root: Path | str) -> "CharacterAuthoringStore":
        return cls(default_store_root(repo_root))

    @property
    def root(self) -> Path:
        return self._root

    def create_character(
        self,
        character_id: str,
        *,
        workflow_metadata: Optional[Mapping[str, Any]] = None,
    ) -> CharacterPointer:
        character_id = validate_identifier(character_id, field="character_id")
        pointer = CharacterPointer(
            character_id=character_id,
            workflow_metadata={} if workflow_metadata is None else workflow_metadata,
        )
        directory = self._character_dir(character_id)
        if directory.exists():
            raise CharacterAuthoringAlreadyExistsError(
                f"character {character_id!r} already exists"
            )
        try:
            directory.mkdir()
        except FileExistsError as exc:
            raise CharacterAuthoringAlreadyExistsError(
                f"character {character_id!r} already exists"
            ) from exc
        except OSError as exc:
            raise CharacterAuthoringStorageError("failed to create character") from exc
        _atomic_replace_json(self._character_pointer_path(character_id), pointer.to_dict())
        return pointer

    def create_version(
        self,
        character_id: str,
        version_id: str,
        *,
        version_label: str,
        lifecycle_state: LifecycleState | str = LifecycleState.DRAFT,
        derived_from_version_id: Optional[str] = None,
        derived_from_revision_id: Optional[str] = None,
        derived_from_snapshot_hash: Optional[str] = None,
        workflow_metadata: Optional[Mapping[str, Any]] = None,
    ) -> VersionPointer:
        character_id = validate_identifier(character_id, field="character_id")
        version_id = validate_identifier(version_id, field="version_id")
        validate_distinct_identities(character_id, version_id)
        self.read_character_pointer(character_id)
        pointer = VersionPointer(
            character_id=character_id,
            version_id=version_id,
            version_label=version_label,
            lifecycle_state=parse_lifecycle(lifecycle_state),
            derived_from_version_id=derived_from_version_id,
            derived_from_revision_id=derived_from_revision_id,
            derived_from_snapshot_hash=derived_from_snapshot_hash,
            workflow_metadata={} if workflow_metadata is None else workflow_metadata,
        )
        directory = self._version_dir(character_id, version_id)
        if directory.exists():
            raise CharacterAuthoringAlreadyExistsError(
                f"version {version_id!r} already exists"
            )
        try:
            directory.mkdir(parents=True)
        except FileExistsError as exc:
            raise CharacterAuthoringAlreadyExistsError(
                f"version {version_id!r} already exists"
            ) from exc
        except OSError as exc:
            raise CharacterAuthoringStorageError("failed to create version") from exc
        _atomic_replace_json(
            self._version_pointer_path(character_id, version_id), pointer.to_dict()
        )
        return pointer

    def persist_revision(
        self,
        character_id: str,
        version_id: str,
        revision_id: str,
        semantic: CharacterSemantic | Mapping[str, Any],
        *,
        lifecycle_state: LifecycleState | str = LifecycleState.DRAFT,
        derived_from_version_id: Optional[str] = None,
        derived_from_revision_id: Optional[str] = None,
        derived_from_snapshot_hash: Optional[str] = None,
        created_at: Optional[str] = None,
        workflow_metadata: Optional[Mapping[str, Any]] = None,
    ) -> RevisionRecord:
        character_id = validate_identifier(character_id, field="character_id")
        version_id = validate_identifier(version_id, field="version_id")
        revision_id = validate_identifier(revision_id, field="revision_id")
        validate_distinct_identities(character_id, version_id, revision_id)
        version_pointer = self.read_version_pointer(character_id, version_id)
        if all(
            value is None
            for value in (
                derived_from_version_id,
                derived_from_revision_id,
                derived_from_snapshot_hash,
            )
        ):
            derived_from_version_id = version_pointer.derived_from_version_id
            derived_from_revision_id = version_pointer.derived_from_revision_id
            derived_from_snapshot_hash = version_pointer.derived_from_snapshot_hash
        if not isinstance(semantic, CharacterSemantic):
            semantic = CharacterSemantic.from_dict(semantic)
        snapshot_hash = compute_snapshot_hash(semantic)
        record = RevisionRecord(
            character_id=character_id,
            version_id=version_id,
            revision_id=revision_id,
            snapshot_hash=snapshot_hash,
            semantic=semantic,
            lifecycle_state=parse_lifecycle(lifecycle_state),
            derived_from_version_id=derived_from_version_id,
            derived_from_revision_id=derived_from_revision_id,
            derived_from_snapshot_hash=derived_from_snapshot_hash,
            created_at=created_at,
            workflow_metadata={} if workflow_metadata is None else workflow_metadata,
        )
        target = self._revision_path(character_id, version_id, revision_id)
        _write_immutable_json(target, record.to_dict())
        return record

    def load_revision(
        self, character_id: str, version_id: str, revision_id: str
    ) -> RevisionRecord:
        character_id = validate_identifier(character_id, field="character_id")
        version_id = validate_identifier(version_id, field="version_id")
        revision_id = validate_identifier(revision_id, field="revision_id")
        validate_distinct_identities(character_id, version_id, revision_id)
        path = self._revision_path(character_id, version_id, revision_id)
        data = _read_json_object(path, label="revision")
        try:
            record = RevisionRecord.from_dict(data)
        except CharacterAuthoringValidationError as exc:
            raise CharacterAuthoringCorruptionError(
                f"revision {revision_id!r} violates its schema"
            ) from exc
        if (
            record.character_id != character_id
            or record.version_id != version_id
            or record.revision_id != revision_id
        ):
            raise CharacterAuthoringCorruptionError(
                "revision identity does not match its storage path"
            )
        actual_hash = compute_snapshot_hash(record.semantic)
        if actual_hash != record.snapshot_hash:
            raise SnapshotHashMismatchError(
                f"revision {revision_id!r} snapshot hash mismatch"
            )
        return record

    def list_character_ids(self) -> list[str]:
        result: list[str] = []
        for entry in self._root.iterdir():
            if not entry.is_dir():
                continue
            try:
                character_id = validate_identifier(entry.name, field="character_id")
                pointer = self.read_character_pointer(character_id)
            except CharacterAuthoringValidationError as exc:
                raise CharacterAuthoringCorruptionError(
                    "store contains an invalid character directory"
                ) from exc
            if pointer.character_id != entry.name:
                raise CharacterAuthoringCorruptionError(
                    "character pointer does not match directory"
                )
            result.append(character_id)
        return sorted(result)

    def list_versions(self, character_id: str) -> list[str]:
        character_id = validate_identifier(character_id, field="character_id")
        self.read_character_pointer(character_id)
        root = self._versions_dir(character_id)
        if not root.exists():
            return []
        result: list[str] = []
        for entry in root.iterdir():
            if not entry.is_dir():
                continue
            try:
                version_id = validate_identifier(entry.name, field="version_id")
                self.read_version_pointer(character_id, version_id)
            except CharacterAuthoringValidationError as exc:
                raise CharacterAuthoringCorruptionError(
                    "store contains an invalid version directory"
                ) from exc
            result.append(version_id)
        return sorted(result)

    def list_revisions(self, character_id: str, version_id: str) -> list[str]:
        character_id = validate_identifier(character_id, field="character_id")
        version_id = validate_identifier(version_id, field="version_id")
        self.read_version_pointer(character_id, version_id)
        root = self._revisions_dir(character_id, version_id)
        if not root.exists():
            return []
        result: list[str] = []
        for entry in root.iterdir():
            if not entry.is_file() or entry.suffix != ".json":
                continue
            try:
                revision_id = validate_identifier(entry.stem, field="revision_id")
            except CharacterAuthoringValidationError as exc:
                raise CharacterAuthoringCorruptionError(
                    "store contains an invalid revision filename"
                ) from exc
            result.append(revision_id)
        return sorted(result)

    def read_character_pointer(self, character_id: str) -> CharacterPointer:
        character_id = validate_identifier(character_id, field="character_id")
        path = self._character_pointer_path(character_id)
        data = _read_json_object(path, label="character pointer")
        try:
            pointer = CharacterPointer.from_dict(data)
        except CharacterAuthoringValidationError as exc:
            raise CharacterAuthoringCorruptionError(
                f"character {character_id!r} pointer is corrupt"
            ) from exc
        if pointer.character_id != character_id:
            raise CharacterAuthoringCorruptionError(
                "character pointer identity does not match its path"
            )
        return pointer

    def read_version_pointer(self, character_id: str, version_id: str) -> VersionPointer:
        character_id = validate_identifier(character_id, field="character_id")
        version_id = validate_identifier(version_id, field="version_id")
        validate_distinct_identities(character_id, version_id)
        path = self._version_pointer_path(character_id, version_id)
        data = _read_json_object(path, label="version pointer")
        try:
            pointer = VersionPointer.from_dict(data)
        except CharacterAuthoringValidationError as exc:
            raise CharacterAuthoringCorruptionError(
                f"version {version_id!r} pointer is corrupt"
            ) from exc
        if pointer.character_id != character_id or pointer.version_id != version_id:
            raise CharacterAuthoringCorruptionError(
                "version pointer identity does not match its path"
            )
        return pointer

    def update_character_pointer(self, pointer: CharacterPointer) -> CharacterPointer:
        if not isinstance(pointer, CharacterPointer):
            raise CharacterAuthoringValidationError(
                "pointer: expected CharacterPointer"
            )
        self.read_character_pointer(pointer.character_id)
        if pointer.selected_version_id is not None:
            self.read_version_pointer(pointer.character_id, pointer.selected_version_id)
        path = self._character_pointer_path(pointer.character_id)
        _atomic_replace_json(path, pointer.to_dict())
        return pointer

    def update_version_pointer(self, pointer: VersionPointer) -> VersionPointer:
        if not isinstance(pointer, VersionPointer):
            raise CharacterAuthoringValidationError("pointer: expected VersionPointer")
        self.read_version_pointer(pointer.character_id, pointer.version_id)
        if pointer.selected_revision_id is not None:
            self.load_revision(
                pointer.character_id, pointer.version_id, pointer.selected_revision_id
            )
        path = self._version_pointer_path(pointer.character_id, pointer.version_id)
        _atomic_replace_json(path, pointer.to_dict())
        return pointer

    def _safe_path(self, *parts: str) -> Path:
        candidate = self._root.joinpath(*parts)
        resolved = candidate.resolve(strict=False)
        try:
            resolved.relative_to(self._root)
        except ValueError as exc:
            raise CharacterAuthoringStorageError("resolved path escapes store root") from exc
        return resolved

    def _character_dir(self, character_id: str) -> Path:
        validate_identifier(character_id, field="character_id")
        return self._safe_path(character_id)

    def _versions_dir(self, character_id: str) -> Path:
        return self._character_dir(character_id) / "versions"

    def _character_pointer_path(self, character_id: str) -> Path:
        return self._safe_path(character_id, "pointer.json")

    def _version_dir(self, character_id: str, version_id: str) -> Path:
        validate_identifier(version_id, field="version_id")
        return self._safe_path(character_id, "versions", version_id)

    def _version_pointer_path(self, character_id: str, version_id: str) -> Path:
        validate_identifier(version_id, field="version_id")
        return self._safe_path(character_id, "versions", version_id, "pointer.json")

    def _revisions_dir(self, character_id: str, version_id: str) -> Path:
        return self._version_dir(character_id, version_id) / "revisions"

    def _revision_path(
        self, character_id: str, version_id: str, revision_id: str
    ) -> Path:
        validate_identifier(revision_id, field="revision_id")
        return self._safe_path(
            character_id, "versions", version_id, "revisions", f"{revision_id}.json"
        )


def _serialize_json(data: Mapping[str, Any]) -> str:
    try:
        return json.dumps(
            data,
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
            indent=2,
        ) + "\n"
    except (TypeError, ValueError) as exc:
        raise CharacterAuthoringValidationError(
            "persisted envelope is not JSON-compatible"
        ) from exc


def _write_temp_json(directory: Path, data: Mapping[str, Any]) -> str:
    directory.mkdir(parents=True, exist_ok=True)
    serialized = _serialize_json(data)
    fd, temp_path = tempfile.mkstemp(
        dir=str(directory), prefix=".tmp_character_authoring_", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(serialized)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise
    return temp_path


def _atomic_replace_json(target: Path, data: Mapping[str, Any]) -> None:
    temp_path = _write_temp_json(target.parent, data)
    try:
        os.replace(temp_path, target)
    except OSError as exc:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise CharacterAuthoringStorageError("atomic pointer replacement failed") from exc


def _write_immutable_json(target: Path, data: Mapping[str, Any]) -> None:
    if target.exists():
        raise ImmutableRevisionError(f"revision {target.stem!r} already exists")
    temp_path = _write_temp_json(target.parent, data)
    try:
        try:
            os.link(temp_path, target)
        except FileExistsError as exc:
            raise ImmutableRevisionError(
                f"revision {target.stem!r} already exists"
            ) from exc
        except OSError as exc:
            raise CharacterAuthoringStorageError(
                "immutable revision publication failed"
            ) from exc
    finally:
        try:
            os.unlink(temp_path)
        except OSError:
            pass


def _read_json_object(path: Path, *, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise CharacterAuthoringNotFoundError(f"{label} does not exist")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CharacterAuthoringCorruptionError(f"{label} is unreadable or invalid JSON") from exc
    if not isinstance(data, dict):
        raise CharacterAuthoringCorruptionError(f"{label} must be a JSON object")
    return data
