#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministic per-snapshot reference manifest (read / validate / serialize).

The manifest lists the imported reference assets of ONE local snapshot version.
Every ``relative_path`` must be safe and strictly under that snapshot's
``references/`` directory -- a manifest path can never escape the snapshot root.

This module never scans, copies, imports, or deletes image files.

Vendoring note: adapted from ``services/reference_library/manifest.py`` in the
VNE repo. Adaptation: the asset root is the snapshot-local ``references/``
directory (not a repo-tracked global ``authoring/reference_library/assets``);
schema id renamed; drops the repo-manifest ``validate_manifest`` /
``lookup_record`` helpers not needed by this slice.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Sequence

from .errors import ReferenceManifestError, ReferenceSha256Error, ReferenceValidationError
from .hashing import is_valid_sha256
from .reference_model import ReferenceRecord

MANIFEST_SCHEMA_VERSION = "companion_reference_manifest/0.1"
#: All imported bytes live directly under this snapshot-relative directory.
REFERENCES_DIR = "references"

_DRIVE_RE = re.compile(r"^[A-Za-z]:")


def is_safe_relative_path(value: Any) -> bool:
    """True if ``value`` is a relative, forward-slash, traversal-free path.

    Rejects absolute paths, drive-qualified paths (``C:/...``), UNC paths,
    backslashes, and empty / ``.`` / ``..`` segments.
    """
    if not isinstance(value, str) or not value:
        return False
    if value.startswith(("/", "\\")):
        return False
    if _DRIVE_RE.match(value):
        return False
    if "\\" in value:
        return False
    parts = value.split("/")
    return all(part not in ("", ".", "..") for part in parts)


def is_under_references_dir(value: Any) -> bool:
    """True if ``value`` is a relative path under the snapshot ``references/``."""
    return isinstance(value, str) and value.startswith(REFERENCES_DIR + "/")


def is_valid_relative_path(value: Any) -> bool:
    """True if ``value`` is safe AND under the snapshot references directory."""
    return is_safe_relative_path(value) and is_under_references_dir(value)


def serialize_manifest(records: Sequence[ReferenceRecord]) -> str:
    """Deterministic UTF-8 JSON: sorted by asset_id, fixed key order, LF."""
    ordered = [rec.to_dict() for rec in sorted(records, key=lambda r: r.asset_id)]
    payload = {"schema_version": MANIFEST_SCHEMA_VERSION, "references": ordered}
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def parse_manifest(text: str) -> list[ReferenceRecord]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ReferenceManifestError(f"manifest is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ReferenceManifestError("manifest root must be an object")
    if data.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise ReferenceManifestError(f"schema_version: expected {MANIFEST_SCHEMA_VERSION!r}")
    refs = data.get("references")
    if not isinstance(refs, list):
        raise ReferenceManifestError("manifest root must have a 'references' array")
    records: list[ReferenceRecord] = []
    for index, item in enumerate(refs):
        try:
            record = ReferenceRecord.from_dict(item)
        except ReferenceValidationError as exc:
            raise ReferenceManifestError(f"references[{index}]: {exc}") from exc
        if not is_valid_relative_path(record.relative_path):
            raise ReferenceManifestError(
                f"references[{index}].relative_path escapes the snapshot references dir: "
                f"{record.relative_path!r}"
            )
        if record.filename != record.relative_path.split("/")[-1]:
            raise ReferenceManifestError(
                f"references[{index}].filename does not match relative_path basename"
            )
        records.append(record)
    return records


def load_manifest(manifest_path: Path) -> list[ReferenceRecord]:
    path = Path(manifest_path)
    if not path.exists():
        raise ReferenceManifestError(f"manifest does not exist: {path.name}")
    return parse_manifest(path.read_text(encoding="utf-8"))


def save_manifest(manifest_path: Path, records: Sequence[ReferenceRecord]) -> None:
    """Atomically write the deterministic serialization."""
    path = Path(manifest_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".refman_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(serialize_manifest(records))
        os.replace(tmp, str(path))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def find_records_by_sha256(records: Sequence[ReferenceRecord], sha256: str) -> list[ReferenceRecord]:
    if not is_valid_sha256(sha256):
        raise ReferenceSha256Error("sha256: expected 64-character lowercase hex digest")
    return [rec for rec in records if rec.sha256 == sha256]
