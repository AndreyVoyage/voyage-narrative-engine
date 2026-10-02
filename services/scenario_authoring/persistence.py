#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scenario Authoring foundation (SE-1.2) -- local W1 Project/Card persistence.

W1 is the smallest practical, versioned local working layout with independent
Card-level persistence. It is deliberately NOT the portable P1 ZIP container
(that is SE-1.4). Layout::

    <root>/
        project.json            # atomically-replaced Project INDEX (membership,
                                #   ordering, start card, characters, per-card hashes)
        cards/<card_id>.json    # one independent Card snapshot (raw card.to_dict())
        recovery/               # previous-good copies used by explicit recovery
            project.json
            cards/<card_id>.json

Storage schema id: ``scenario_authoring_storage/0.1`` -- distinct from the
in-memory authoring schema ``scenario_authoring/0.1``.

Design guarantees (OD-SE-STORAGE-CONTRACT-01):

- Project membership and ordering are stored explicitly: the index ``cards``
  array is ordered and preserves the authoring order.
- Each Card is persisted independently; saving one existing Card rewrites only
  that Card's file plus the index -- no unrelated Card file is touched.
- Filesystem paths are never entity identities: a Card file name is derived
  from the stable ``card_id``, and identity is the ``card_id`` field, verified
  against the index entry on load.
- Only safe internal relative paths are used; every derived path is verified to
  stay under the project root.
- The Project is reconstructed through the validated ``project_from_dict``
  interface (plus ``validate_project``), never by ad-hoc dict assembly.
- Incomplete/malformed data, missing Card data, and hash-mismatched Card data
  are rejected (fail closed); no silent partial-data acceptance.
- Writes are atomic per-file (temp + os.replace + fsync) and published in a
  safe order: Cards first, then the authoritative Project index last, so the
  index never points at incomplete Card content.
- A previous-good snapshot is kept under ``recovery/`` and restored only by the
  explicit ``ProjectStore.recover()`` method. Several independent file
  replacements are NOT claimed to form one atomic transaction.

No media bytes are copied; MediaReference data is preserved as plain data
(media-file copying / portable packaging / deduplication belong to SE-1.4).
No provider settings or credentials are introduced; ordinary literary words
such as "password"/"token" are never treated as secrets.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, List

from .errors import ScenarioAuthoringError, ScenarioAuthoringValidationError
from .model import (
    SCENARIO_AUTHORING_SCHEMA_VERSION,
    STABLE_ID_RE,
    Card,
    Project,
    project_from_dict,
)
from .validation import validate_project

# Storage schema id for the W1 local working directory. NOT the authoring model
# schema and NOT a portable-package manifest (P1 is SE-1.4).
STORAGE_SCHEMA_VERSION = "scenario_authoring_storage/0.1"

_CARDS_DIRNAME = "cards"
_RECOVERY_DIRNAME = "recovery"
_INDEX_FILENAME = "project.json"
_TEMP_PREFIX = ".scenario_authoring_"
_TEMP_SUFFIX = ".tmp"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ScenarioAuthoringStorageError(ScenarioAuthoringError):
    """Base persistence failure (I/O, path safety, publication)."""


class ScenarioAuthoringNotFoundError(ScenarioAuthoringStorageError):
    """A required persisted artifact (index or Card) does not exist."""


class ScenarioAuthoringCorruptionError(ScenarioAuthoringStorageError):
    """Stored data is malformed, incomplete, or integrity-mismatched."""


class ScenarioAuthoringRecoveryError(ScenarioAuthoringStorageError):
    """Explicit recovery could not be performed (e.g. no previous-good state)."""


# --------------------------------------------------------------------- hashing


def _canonical_json(payload: Any) -> str:
    """Deterministic JSON used for content hashing (mirrors services/ass/hashing)."""
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, allow_nan=False)


def _content_hash(payload: Any) -> str:
    """Lowercase hex SHA-256 over the canonical JSON of a semantic payload."""
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _serialize(payload: Any) -> str:
    """Deterministic, human-readable UTF-8 JSON for a persisted file."""
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
            indent=2,
        )
        + "\n"
    )


# ------------------------------------------------------------------------ paths


def _require_safe_card_id(card_id: str) -> str:
    """Reject anything but a stable lowercase-slug id (also filename-safe)."""
    if not isinstance(card_id, str) or STABLE_ID_RE.match(card_id) is None:
        raise ScenarioAuthoringStorageError(f"unsafe card_id: {card_id!r}")
    return card_id


def _cards_dir(root: Path) -> Path:
    return root / _CARDS_DIRNAME


def _recovery_cards_dir(root: Path) -> Path:
    return root / _RECOVERY_DIRNAME / _CARDS_DIRNAME


def _index_path(root: Path) -> Path:
    return root / _INDEX_FILENAME


def _recovery_index_path(root: Path) -> Path:
    return root / _RECOVERY_DIRNAME / _INDEX_FILENAME


def _card_path(root: Path, card_id: str) -> Path:
    return _cards_dir(root) / f"{_require_safe_card_id(card_id)}.json"


def _recovery_card_path(root: Path, card_id: str) -> Path:
    return _recovery_cards_dir(root) / f"{_require_safe_card_id(card_id)}.json"


def _ensure_within_root(root: Path, path: Path) -> Path:
    """Defense-in-depth: the resolved path must stay under the resolved root."""
    resolved_root = os.path.abspath(os.path.normpath(str(root)))
    resolved_path = os.path.abspath(os.path.normpath(str(path)))
    if os.path.commonpath([resolved_root, resolved_path]) != resolved_root:
        raise ScenarioAuthoringStorageError("derived path escapes the project root")
    return path


# -------------------------------------------------------------------- validation


def _reject_duplicate_key(pairs: List[tuple]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ScenarioAuthoringCorruptionError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ScenarioAuthoringCorruptionError(f"non-finite JSON number {value!r}")


def _parse_json_text(text: str, *, label: str) -> Any:
    try:
        return json.loads(
            text,
            object_pairs_hook=_reject_duplicate_key,
            parse_constant=_reject_constant,
        )
    except json.JSONDecodeError as exc:
        raise ScenarioAuthoringCorruptionError(f"{label} is not valid JSON") from exc


def _require_index_shape(data: Any) -> Dict[str, Any]:
    if not isinstance(data, dict):
        raise ScenarioAuthoringCorruptionError("project index must be a JSON object")
    if data.get("schema_version") != STORAGE_SCHEMA_VERSION:
        raise ScenarioAuthoringCorruptionError(
            f"project index schema_version: expected {STORAGE_SCHEMA_VERSION!r}, "
            f"got {data.get('schema_version')!r}"
        )
    for key in ("project_id", "authoring_schema_version", "start_card_id", "cards"):
        if key not in data:
            raise ScenarioAuthoringCorruptionError(
                f"project index missing required field {key!r}"
            )
    if data.get("authoring_schema_version") != SCENARIO_AUTHORING_SCHEMA_VERSION:
        raise ScenarioAuthoringCorruptionError(
            "project index authoring_schema_version: expected "
            f"{SCENARIO_AUTHORING_SCHEMA_VERSION!r}"
        )
    raw_cards = data["cards"]
    if not isinstance(raw_cards, list):
        raise ScenarioAuthoringCorruptionError("project index cards: expected an array")
    seen: Dict[str, int] = {}
    for index, entry in enumerate(raw_cards):
        if not isinstance(entry, dict):
            raise ScenarioAuthoringCorruptionError(
                f"project index cards[{index}]: expected object"
            )
        card_id = entry.get("card_id")
        _require_safe_card_id(card_id)
        content_hash = entry.get("content_hash")
        if not isinstance(content_hash, str) or _SHA256_RE.fullmatch(content_hash) is None:
            raise ScenarioAuthoringCorruptionError(
                f"project index cards[{index}]: invalid content_hash"
            )
        if card_id in seen:
            raise ScenarioAuthoringCorruptionError(
                f"project index: duplicate card_id {card_id!r}"
            )
        seen[card_id] = index
    if "characters" in data and not isinstance(data["characters"], list):
        raise ScenarioAuthoringCorruptionError("project index characters: expected an array")
    return data


def _require_card_shape(data: Any, expected_card_id: str, expected_hash: str) -> Dict[str, Any]:
    if not isinstance(data, dict):
        raise ScenarioAuthoringCorruptionError(
            f"card {expected_card_id!r}: must be a JSON object"
        )
    if data.get("card_id") != expected_card_id:
        raise ScenarioAuthoringCorruptionError(
            f"card file identity mismatch: expected {expected_card_id!r}, "
            f"got {data.get('card_id')!r}"
        )
    if _content_hash(data) != expected_hash:
        raise ScenarioAuthoringCorruptionError(
            f"card {expected_card_id!r}: content hash mismatch (corrupted or stale content)"
        )
    return data


# ------------------------------------------------------------------------ index


def _build_index(project: Project) -> Dict[str, Any]:
    cards = [
        {"card_id": card.card_id, "content_hash": _content_hash(card.to_dict())}
        for card in project.cards
    ]
    index: Dict[str, Any] = {
        "schema_version": STORAGE_SCHEMA_VERSION,
        "project_id": project.project_id,
        "authoring_schema_version": project.schema_version,
        "start_card_id": project.start_card_id,
        "cards": cards,
    }
    if project.characters:
        index["characters"] = [c.to_dict() for c in project.characters]
    return index


def _assemble_project(index: Dict[str, Any], card_dicts: List[Dict[str, Any]]) -> Project:
    project_dict: Dict[str, Any] = {
        "schema_version": index["authoring_schema_version"],
        "project_id": index["project_id"],
        "cards": card_dicts,
        "start_card_id": index["start_card_id"],
    }
    if index.get("characters"):
        project_dict["characters"] = index["characters"]
    return project_from_dict(project_dict)


# -------------------------------------------------------------------------- I/O


def _atomic_write_text(root: Path, path: Path, text: str) -> None:
    _ensure_within_root(root, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=_TEMP_PREFIX, suffix=_TEMP_SUFFIX)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, str(path))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _copy_file_atomic(root: Path, source: Path, dest: Path) -> None:
    """Best-effort atomic copy (used for the recovery snapshot/restore)."""
    _ensure_within_root(root, dest)
    data = source.read_bytes()
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(dest.parent), prefix=_TEMP_PREFIX, suffix=_TEMP_SUFFIX)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, str(dest))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# ------------------------------------------------------------------------ store


class ProjectStore:
    """UI-independent W1 persistence for one local authoring Project."""

    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    # ------------------------------------------------------------------ read

    def _read_index_at(self, path: Path) -> Dict[str, Any]:
        if not path.is_file():
            raise ScenarioAuthoringNotFoundError("project index does not exist")
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ScenarioAuthoringCorruptionError("project index is unreadable") from exc
        return _require_index_shape(_parse_json_text(text, label="project index"))

    def _read_card_at(self, cards_dir: Path, card_id: str, expected_hash: str) -> Dict[str, Any]:
        path = _ensure_within_root(
            self._root, cards_dir / f"{_require_safe_card_id(card_id)}.json"
        )
        if not path.is_file():
            raise ScenarioAuthoringNotFoundError(f"card {card_id!r} data is missing")
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ScenarioAuthoringCorruptionError(f"card {card_id!r} is unreadable") from exc
        data = _parse_json_text(text, label=f"card {card_id!r}")
        return _require_card_shape(data, card_id, expected_hash)

    def _load_from(self, index_path: Path, cards_dir: Path) -> Project:
        index = self._read_index_at(index_path)
        card_dicts = [
            self._read_card_at(cards_dir, entry["card_id"], entry["content_hash"])
            for entry in index["cards"]
        ]
        project = _assemble_project(index, card_dicts)
        violations = validate_project(project)
        if violations:
            raise ScenarioAuthoringCorruptionError(
                "stored project is internally inconsistent: " + "; ".join(violations)
            )
        return project

    # ----------------------------------------------------------------- write

    def _snapshot_previous_good(self) -> None:
        """Copy the current good main state into ``recovery/`` (if loadable)."""
        if not _index_path(self._root).is_file():
            return
        try:
            current = self._read_index_at(_index_path(self._root))
            for entry in current["cards"]:
                self._read_card_at(_cards_dir(self._root), entry["card_id"], entry["content_hash"])
        except ScenarioAuthoringStorageError:
            return
        _copy_file_atomic(self._root, _index_path(self._root), _recovery_index_path(self._root))
        for entry in current["cards"]:
            _copy_file_atomic(
                self._root,
                _card_path(self._root, entry["card_id"]),
                _recovery_card_path(self._root, entry["card_id"]),
            )

    def _write_card(self, card: Card) -> None:
        _require_safe_card_id(card.card_id)
        _atomic_write_text(
            self._root, _card_path(self._root, card.card_id), _serialize(card.to_dict())
        )

    def _write_index(self, index: Dict[str, Any]) -> None:
        _atomic_write_text(self._root, _index_path(self._root), _serialize(index))

    # -------------------------------------------------------------- public API

    def save(self, project: Project) -> None:
        """Persist a complete Project (Cards first, then the index last)."""
        if not isinstance(project, Project):
            raise ScenarioAuthoringValidationError("save: expected a Project")
        violations = validate_project(project)
        if violations:
            raise ScenarioAuthoringValidationError(
                "save: project is inconsistent: " + "; ".join(violations)
            )
        if project_from_dict(project.to_dict()) != project:
            raise ScenarioAuthoringValidationError(
                "save: project does not round-trip through plain data"
            )
        self._snapshot_previous_good()
        for card in project.cards:
            self._write_card(card)
        self._write_index(_build_index(project))

    def save_card(self, card: Card) -> None:
        """Persist one already-existing Card independently.

        Rewrites only that Card's file plus the index entry; no unrelated Card
        file is touched. The Card must already be a member of the stored index.
        """
        if not isinstance(card, Card):
            raise ScenarioAuthoringValidationError("save_card: expected a Card")
        _require_safe_card_id(card.card_id)
        index = self._read_index_at(_index_path(self._root))
        entry = next((e for e in index["cards"] if e["card_id"] == card.card_id), None)
        if entry is None:
            raise ScenarioAuthoringNotFoundError(
                f"card {card.card_id!r} is not part of this stored project"
            )
        entry["content_hash"] = _content_hash(card.to_dict())
        self._snapshot_previous_good()
        self._write_card(card)
        self._write_index(index)

    def load(self) -> Project:
        """Reopen and validate the stored Project (fail closed)."""
        return self._load_from(_index_path(self._root), _cards_dir(self._root))

    def recover(self) -> Project:
        """Explicitly restore the previous-good state, then return it.

        Raises :class:`ScenarioAuthoringRecoveryError` when no previous-good
        snapshot exists. Recovery never invents authored content: it restores
        exactly the snapshot, or fails.
        """
        recovery_index = _recovery_index_path(self._root)
        if not recovery_index.is_file():
            raise ScenarioAuthoringRecoveryError("no previous-good state to recover")
        project = self._load_from(recovery_index, _recovery_cards_dir(self._root))
        entries = self._read_index_at(recovery_index)["cards"]
        for entry in entries:
            _copy_file_atomic(
                self._root,
                _recovery_card_path(self._root, entry["card_id"]),
                _card_path(self._root, entry["card_id"]),
            )
        _copy_file_atomic(self._root, recovery_index, _index_path(self._root))
        return project

    def exists(self) -> bool:
        """True when a Project index has been persisted at this root."""
        return _index_path(self._root).is_file()

    def has_recovery(self) -> bool:
        """True when a previous-good snapshot is available for recovery."""
        return _recovery_index_path(self._root).is_file()
