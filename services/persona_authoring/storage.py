#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PAC v0 filesystem storage.

All PAC runtime output is written under the gitignored ``local_runs/pac/``
directory.  No writes to canon paths are permitted.  Raw and approved
outputs are stored in separate subdirectories.

Atomic writes are used for JSONL append to prevent partial-line corruption.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .contracts import PacGeneration, PacTrainingExample, generate_run_id
from .errors import PacCanonError, PacStorageError

# Allowed extensions
_ALLOWED_EXTENSION = ".json"


class PacStorage:
    """Non-canonical PAC runtime filesystem persistence.

    All paths are resolved under ``base_path``; path traversal and
    absolute escapes are rejected.
    """

    def __init__(self, base_path: Path | str = Path("local_runs/pac")) -> None:
        self._base = Path(base_path).resolve()
        # Safety: reject canon directories as base.
        _reject_canon_path(self._base)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def base_path(self) -> Path:
        return self._base

    # -- Raw output ----------------------------------------------------

    def save_raw(self, generation: PacGeneration) -> Path:
        """Persist raw generation evidence.

        Writes to ``raw/{run_id}/generation.json``.
        Returns the written path.
        """
        target = self._resolve_run_dir("raw", generation.run_id) / "generation.json"
        return self._write_json(target, _generation_to_dict(generation))

    def load_raw(self, run_id: str) -> dict[str, Any]:
        """Load a previously saved raw generation."""
        target = self._resolve_run_dir("raw", run_id) / "generation.json"
        return self._read_json(target)

    # -- Accepted draft ------------------------------------------------

    def save_draft(self, run_id: str, variant_index: int, approved_output: str) -> Path:
        """Save an accepted draft (after ACCEPT_DRAFT).

        Writes to ``drafts/{run_id}/draft.json``.
        """
        target = self._resolve_run_dir("drafts", run_id) / "draft.json"
        payload = {
            "run_id": run_id,
            "variant_index": variant_index,
            "approved_output": approved_output,
        }
        return self._write_json(target, payload)

    def load_draft(self, run_id: str) -> dict[str, Any]:
        """Load a previously saved draft."""
        target = self._resolve_run_dir("drafts", run_id) / "draft.json"
        return self._read_json(target)

    def draft_exists(self, run_id: str) -> bool:
        """Return ``True`` when a draft has been saved for ``run_id``."""
        target = self._resolve_run_dir("drafts", run_id) / "draft.json"
        return target.is_file()

    # -- Approved scene ------------------------------------------------

    def save_approved_scene(self, run_id: str, scene_data: dict[str, Any]) -> Path:
        """Save an approved scene (after APPROVE_SCENE).

        Writes to ``approved_scenes/{run_id}/scene.json``.
        """
        target = self._resolve_run_dir("approved_scenes", run_id) / "scene.json"
        return self._write_json(target, scene_data)

    def load_approved_scene(self, run_id: str) -> dict[str, Any]:
        """Load a previously saved approved scene."""
        target = self._resolve_run_dir("approved_scenes", run_id) / "scene.json"
        return self._read_json(target)

    def scene_approved(self, run_id: str) -> bool:
        """Return ``True`` when a scene has been approved for ``run_id``."""
        target = self._resolve_run_dir("approved_scenes", run_id) / "scene.json"
        return target.is_file()

    # -- Dataset (JSONL) -----------------------------------------------

    def dataset_path(self) -> Path:
        """Return the path to ``training_dataset.jsonl``."""
        return self._resolve("dataset/training_dataset.jsonl")

    def append_dataset(self, example: PacTrainingExample) -> Path:
        """Atomically append one validated record to the JSONL dataset.

        Idempotent: if a record with the same ``example_id`` already exists,
        no write occurs and the existing path is returned.

        Raises ``PacStorageError`` when the dataset file is malformed.
        """
        target = self.dataset_path()
        record = example.to_dict()
        record_str = json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"

        # Check idempotency: load existing and reject duplicate.
        existing: dict[str, dict[str, Any]] = {}
        if target.is_file():
            existing = _load_existing_dataset(target)
            if example.example_id in existing:
                # Already present -- idempotent no-op.
                return target

        # Atomic write: write to temp in same directory, then rename.
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            dir=str(target.parent),
            prefix=".tmp_dataset_",
            suffix=".jsonl",
            text=True,
        )
        try:
            # Write existing lines unchanged.
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                for _existing_id, _existing_record in existing.items():
                    line = json.dumps(_existing_record, ensure_ascii=False, sort_keys=True) + "\n"
                    fh.write(line)
                fh.write(record_str)
            # Atomic rename on Windows works when target does not exist.
            # On Windows, os.replace requires the destination to not exist
            # when crossing filesystems, but within the same dir os.replace
            # is atomic.
            os.replace(tmp_path, target)
        except BaseException:
            # Clean up temp file on any failure.
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

        return target

    def load_dataset(self) -> dict[str, dict[str, Any]]:
        """Load the complete dataset as a mapping of example_id -> record."""
        target = self.dataset_path()
        if not target.is_file():
            return {}
        return _load_existing_dataset(target)

    def dataset_contains(self, example_id: str) -> bool:
        """Return ``True`` when ``example_id`` already exists in the dataset."""
        return example_id in self.load_dataset()

    # -- Eval ----------------------------------------------------------

    def save_eval_results(self, run_id: str, results: dict[str, Any]) -> Path:
        """Save evaluation results."""
        target = self._resolve_run_dir("eval/runs", run_id) / "results.json"
        return self._write_json(target, results)

    def save_calibration(self, run_id: str, calibration: dict[str, Any]) -> Path:
        """Save manual calibration evidence."""
        target = self._resolve_run_dir("eval/runs", run_id) / "calibration.json"
        return self._write_json(target, calibration)

    # -- Run manifest --------------------------------------------------

    def save_run_manifest(self, run_id: str, manifest: dict[str, Any]) -> Path:
        """Save a run manifest with approval state metadata."""
        target = self._resolve_run_dir("runs", run_id) / "manifest.json"
        return self._write_json(target, manifest)

    def load_run_manifest(self, run_id: str) -> dict[str, Any]:
        """Load a previously saved run manifest."""
        target = self._resolve_run_dir("runs", run_id) / "manifest.json"
        return self._read_json(target)

    def run_manifest_exists(self, run_id: str) -> bool:
        target = self._resolve_run_dir("runs", run_id) / "manifest.json"
        return target.is_file()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve(self, relative: str) -> Path:
        """Resolve a relative path under ``base_path``, rejecting escapes."""
        _reject_traversal(relative)
        resolved = (self._base / relative).resolve()
        _reject_escape(self._base, resolved)
        return resolved

    def _resolve_run_dir(self, category: str, run_id: str) -> Path:
        """Resolve ``{category}/{run_id}/`` and create directories."""
        _reject_traversal(category)
        _reject_traversal(run_id)
        parts = run_id.replace("\\", "/").split("/")
        if any(p in ("", ".", "..") for p in parts):
            raise PacStorageError(f"invalid run_id: {run_id!r}")
        d = self._base / category / run_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    @staticmethod
    def _write_json(target: Path, data: dict[str, Any]) -> Path:
        """Atomic JSON write (write to temp + rename)."""
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            dir=str(target.parent),
            prefix=".tmp_pac_",
            suffix=".json",
            text=True,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=2, sort_keys=True)
            os.replace(tmp_path, target)
        except BaseException:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
        return target

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        """Read and parse a JSON file."""
        if not path.is_file():
            raise PacStorageError(f"file not found: {path}")
        try:
            text = path.read_text(encoding="utf-8")
            data = json.loads(text)
            if not isinstance(data, dict):
                raise PacStorageError(f"expected JSON object at {path}")
            return data
        except json.JSONDecodeError as exc:
            raise PacStorageError(f"invalid JSON at {path}: {exc}") from exc
        except OSError as exc:
            raise PacStorageError(f"failed to read {path}: {exc}") from exc


# ----------------------------------------------------------------------
# Module helpers
# ----------------------------------------------------------------------


def _load_existing_dataset(target: Path) -> dict[str, dict[str, Any]]:
    """Read existing JSONL lines into a dict keyed by ``example_id``."""
    existing: dict[str, dict[str, Any]] = {}
    if not target.is_file():
        return existing
    try:
        text = target.read_text(encoding="utf-8")
    except OSError as exc:
        raise PacStorageError(f"failed to read dataset: {exc}") from exc
    for idx, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            record = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise PacStorageError(
                f"malformed JSONL at line {idx}: {exc}"
            ) from exc
        if not isinstance(record, dict):
            raise PacStorageError(
                f"expected JSON object at line {idx}"
            )
        eid = record.get("example_id")
        if not isinstance(eid, str) or not eid:
            raise PacStorageError(
                f"missing or invalid example_id at line {idx}"
            )
        if eid in existing:
            raise PacStorageError(
                f"duplicate example_id in existing dataset: {eid!r} (line {idx})"
            )
        existing[eid] = record
    return existing


def _reject_traversal(relative: str) -> None:
    """Reject path traversal in a relative string."""
    if not isinstance(relative, str) or not relative:
        raise PacStorageError("path must be a non-empty string")
    normalized = relative.replace("\\", "/")
    parts = normalized.split("/")
    if any(p in ("", ".", "..") for p in parts) or normalized.startswith("/"):
        raise PacStorageError(f"path traversal or absolute path rejected: {relative!r}")


def _reject_escape(base: Path, resolved: Path) -> None:
    """Ensure ``resolved`` is inside ``base``."""
    try:
        resolved.relative_to(base)
    except ValueError:
        raise PacStorageError(
            f"path escapes storage root: {resolved} not under {base}"
        )


def _reject_canon_path(path: Path) -> None:
    """Reject known canon directories as storage base."""
    canon_markers = [
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
    ]
    path_str = str(path).replace("\\", "/")
    for marker in canon_markers:
        if path_str.rstrip("/").endswith(marker):
            raise PacCanonError(
                f"storage base path must not be a canon directory: {path}"
            )


def _generation_to_dict(gen: PacGeneration) -> dict[str, Any]:
    """Serialize a ``PacGeneration`` to a plain dict."""
    return {
        "run_id": gen.run_id,
        "request": {
            "character_id": gen.request.character_id,
            "level": gen.request.level,
            "situation": gen.request.situation,
            "author_instruction": gen.request.author_instruction,
            "provider": gen.request.provider,
            "model": gen.request.model,
            "variant_count": gen.request.variant_count,
        },
        "variants": [
            {
                "index": v.index,
                "raw_text": v.raw_text,
                "fmdr_valid": v.fmdr_valid,
                "thoughts": v.thoughts,
                "actions": v.actions,
                "speech": v.speech,
                "fmdr_error": v.fmdr_error,
            }
            for v in gen.variants
        ],
        "created_at": gen.created_at,
        "canon_snapshot": gen.canon_snapshot,
        "system_prompt": gen.system_prompt,
    }