#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CIS Kira Pilot -- Slice 4 non-canonical runtime storage.

WRAP of the ``services/persona_authoring/storage.py`` (PacStorage) pattern
(plan §4: copy the pattern, do NOT import it -- PAC is a different track and
its methods are typed to PAC domain objects). Stdlib only; the canon-marker
list is intentionally duplicated locally per the plan rather than imported
across tracks.

Scope and guarantees:

* All writes are confined to ``base_path`` (production default
  ``local_runs/cis_pilot/``, gitignored ``.gitignore:50``). The constructor
  accepts an explicit base so tests can use ``tmp_path``; confinement is
  always enforced relative to the base actually given.
* Canon-path rejection: a known canon directory as the storage base is
  refused (``CisPilotCanonError``).
* Path-traversal rejection: ``..`` segments, empty/``.`` segments, absolute
  paths, and backslash separators are refused; symlink escapes are caught by
  resolving the target and requiring it to stay under the base.
* Atomic JSON write: tempfile in the target directory + ``os.replace`` --
  a crash mid-write never leaves a partial file.
* Overwrite policy: FAIL IF EXISTS by default
  (``CisPilotStorageConflictError``); overwriting requires the explicit
  ``overwrite=True`` opt-in. JSONL append is a separate, explicit API
  (TD-8b) -- never implicit.
* No SQLite, no network, no canon writes, no Aside/Ren'Py persistence.
  This is pilot runtime output only. Importing this module creates nothing.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Union

# Known canon roots that must never serve as the storage base. Duplicated
# from the PacStorage pattern on purpose (plan §4 -- no cross-track import).
_CANON_MARKERS = (
    "personas",
    "scenarios",
    "knowledge_base",
    "core",
    "novel",
    "governance",
    "services/persona_gateway",
    "state",
    "schemas",
    ".voyage",
)

# Production default output root (repo-relative; gitignored). Tests always
# pass an explicit tmp_path base instead.
DEFAULT_BASE_PATH = Path("local_runs/cis_pilot")


class CisPilotStorageError(RuntimeError):
    """Base fail-closed storage error (traversal, escape, I/O, malformed
    JSON, missing file)."""


class CisPilotCanonError(CisPilotStorageError):
    """Raised when a canon directory is used as the storage base."""


class CisPilotStorageConflictError(CisPilotStorageError):
    """Raised when a JSON target already exists and ``overwrite`` was not
    explicitly requested (default policy: FAIL IF EXISTS)."""


class CisPilotStorage:
    """Non-canonical CIS pilot runtime filesystem persistence.

    All paths are resolved under ``base_path``; traversal, absolute escapes,
    and canon bases are rejected. JSON writes are atomic; JSONL appends are
    an explicit separate API.
    """

    def __init__(self, base_path: Union[Path, str] = DEFAULT_BASE_PATH) -> None:
        self._base = Path(base_path).resolve()
        _reject_canon_path(self._base)

    @property
    def base_path(self) -> Path:
        return self._base

    # ------------------------------------------------------------------
    # JSON (atomic, fail-if-exists by default)
    # ------------------------------------------------------------------

    def write_json(
        self, relative_path: str, data: Dict[str, Any], *, overwrite: bool = False
    ) -> Path:
        """Atomically write ``data`` as UTF-8 JSON (sorted keys, indented).

        Fails closed with ``CisPilotStorageConflictError`` when the target
        already exists, unless ``overwrite=True`` is explicitly passed.
        """
        if not isinstance(data, dict):
            raise CisPilotStorageError("JSON payload must be a dict")
        target = self._resolve(relative_path)
        if target.exists() and not overwrite:
            raise CisPilotStorageConflictError(
                f"target already exists (default policy: fail-if-exists; "
                f"pass overwrite=True to replace): {relative_path!r}"
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            dir=str(target.parent),
            prefix=".tmp_cis_pilot_",
            suffix=".json",
            text=True,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.write("\n")
            os.replace(tmp_path, target)
        except BaseException:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
        return target

    def read_json(self, relative_path: str) -> Dict[str, Any]:
        """Read and parse a previously written JSON object."""
        target = self._resolve(relative_path)
        if not target.is_file():
            raise CisPilotStorageError(f"file not found: {relative_path!r}")
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CisPilotStorageError(f"invalid JSON at {relative_path!r}: {exc}") from exc
        except OSError as exc:
            raise CisPilotStorageError(f"failed to read {relative_path!r}: {exc}") from exc
        if not isinstance(data, dict):
            raise CisPilotStorageError(f"expected JSON object at {relative_path!r}")
        return data

    def exists(self, relative_path: str) -> bool:
        """Return ``True`` when the confined target exists (file or dir)."""
        return self._resolve(relative_path).exists()

    # ------------------------------------------------------------------
    # JSONL (explicit append API, TD-8b)
    # ------------------------------------------------------------------

    def append_jsonl(self, relative_path: str, record: Dict[str, Any]) -> Path:
        """Append one JSON record as a single line (explicit append API).

        Creates the file when absent; never truncates. One record per line,
        UTF-8, sorted keys. This is the crash-resilient per-sample durability
        path (TD-8b) -- it is intentionally separate from ``write_json`` so
        appending can never happen implicitly.
        """
        if not isinstance(record, dict):
            raise CisPilotStorageError("JSONL record must be a dict")
        target = self._resolve(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
        with target.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(line)
        return target

    def read_jsonl(self, relative_path: str) -> List[Dict[str, Any]]:
        """Read all records of a JSONL file (empty list when absent).

        Fails closed on any malformed line -- a partially corrupted sample
        log is never silently skipped."""
        target = self._resolve(relative_path)
        if not target.is_file():
            return []
        try:
            text = target.read_text(encoding="utf-8")
        except OSError as exc:
            raise CisPilotStorageError(f"failed to read JSONL {relative_path!r}: {exc}") from exc
        records: List[Dict[str, Any]] = []
        for line_no, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise CisPilotStorageError(
                    f"malformed JSONL at {relative_path!r} line {line_no}: {exc}"
                ) from exc
            if not isinstance(record, dict):
                raise CisPilotStorageError(
                    f"expected JSON object at {relative_path!r} line {line_no}"
                )
            records.append(record)
        return records

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve(self, relative_path: str) -> Path:
        """Resolve ``relative_path`` under the base, rejecting traversal,
        absolute escapes, and symlink escapes (the resolved target must stay
        under the resolved base)."""
        _reject_traversal(relative_path)
        resolved = (self._base / relative_path).resolve()
        try:
            resolved.relative_to(self._base)
        except ValueError:
            raise CisPilotStorageError(
                f"path escapes storage root: {relative_path!r}"
            ) from None
        return resolved


# ----------------------------------------------------------------------
# Module helpers (PacStorage pattern, duplicated per plan §4)
# ----------------------------------------------------------------------


def _reject_traversal(relative: str) -> None:
    """Reject path traversal / absolute paths in a relative string."""
    if not isinstance(relative, str) or not relative:
        raise CisPilotStorageError("path must be a non-empty string")
    normalized = relative.replace("\\", "/")
    parts = normalized.split("/")
    if any(p in ("", ".", "..") for p in parts) or normalized.startswith("/"):
        raise CisPilotStorageError(f"path traversal or absolute path rejected: {relative!r}")


def _reject_canon_path(path: Path) -> None:
    """Reject known canon directories as the storage base."""
    path_str = str(path).replace("\\", "/")
    for marker in _CANON_MARKERS:
        if path_str.rstrip("/").endswith(marker):
            raise CisPilotCanonError(f"storage base path must not be a canon directory: {path}")
