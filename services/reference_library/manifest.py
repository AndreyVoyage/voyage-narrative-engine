#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Reference Library v0 -- deterministic technical manifest (SVA-RL1).

Deterministic serialize/load and pure metadata validation of the git-tracked
technical manifest. This module is read/validate/serialize only: it never
scans, copies, imports, or deletes external image files, and never mutates the
manifest from an external image.

Manifest location (ratified)::

    authoring/reference_library/REFERENCE_LIBRARY_MANIFEST.json

Future asset bytes root (ratified planning)::

    authoring/reference_library/assets/

Future character convention::

    authoring/reference_library/assets/characters/<character_id>/...
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Sequence

from .errors import (
    ReferenceLibraryManifestError,
    ReferenceLibraryNotFoundError,
    ReferenceLibrarySha256Error,
    ReferenceLibraryValidationError,
)
from .hashing import is_valid_sha256
from .model import (
    OPTIONAL_FIELDS,
    REQUIRED_FIELDS,
    ReferenceRecord,
    canonical_file_type,
)

# Repo-relative paths (forward slashes).
LIBRARY_ROOT = "authoring/reference_library"
ASSET_ROOT = "authoring/reference_library/assets"
MANIFEST_FILENAME = "REFERENCE_LIBRARY_MANIFEST.json"
MANIFEST_RELATIVE_PATH = "authoring/reference_library/REFERENCE_LIBRARY_MANIFEST.json"

MANIFEST_SCHEMA_VERSION = "vne_reference_library/0.1"

_DRIVE_RE = re.compile(r"^[A-Za-z]:")


def default_manifest_path(repo_root: Path) -> Path:
    """Return the ratified manifest path for a repo root."""
    return Path(repo_root) / MANIFEST_RELATIVE_PATH


def is_safe_relative_path(value: Any) -> bool:
    """True if ``value`` is a repo-relative, forward-slash, traversal-free path.

    Rejects absolute paths, drive-qualified paths (``C:/...``), UNC paths
    (``//server/...`` or ``\\\\server\\...``), backslashes, and empty/``.``/
    ``..`` segments.
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


def is_under_asset_root(value: Any) -> bool:
    """True if ``value`` is a repo-relative path under the future asset bytes root."""
    if not isinstance(value, str):
        return False
    return value.startswith(ASSET_ROOT + "/")


def is_valid_relative_path(value: Any) -> bool:
    """True if ``value`` is safe and under the future asset bytes root."""
    return is_safe_relative_path(value) and is_under_asset_root(value)


def serialize_manifest(records: Sequence[ReferenceRecord]) -> str:
    """Return deterministic UTF-8 JSON: sorted by asset_id, fixed key order, LF."""
    ordered = [rec.to_dict() for rec in sorted(records, key=lambda r: r.asset_id)]
    payload = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "references": ordered,
    }
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def parse_manifest(text: str) -> list[ReferenceRecord]:
    """Parse manifest JSON text into validated records (raises on malformed input)."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ReferenceLibraryManifestError(f"manifest is not valid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise ReferenceLibraryManifestError("manifest root must be an object")
    if data.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise ReferenceLibraryManifestError(
            f"schema_version: expected {MANIFEST_SCHEMA_VERSION!r}"
        )
    refs = data.get("references")
    if not isinstance(refs, list):
        raise ReferenceLibraryManifestError("manifest root must have a 'references' array")

    records: list[ReferenceRecord] = []
    for index, item in enumerate(refs):
        try:
            records.append(ReferenceRecord.from_dict(item))
        except ReferenceLibraryValidationError as exc:
            raise ReferenceLibraryManifestError(f"references[{index}]: {exc}") from exc
    return records


def load_manifest(manifest_path: Path) -> list[ReferenceRecord]:
    """Load and validate the manifest at ``manifest_path`` into records."""
    path = Path(manifest_path)
    if not path.exists():
        raise ReferenceLibraryManifestError(f"manifest does not exist: {path.name}")
    return parse_manifest(path.read_text(encoding="utf-8"))


def save_manifest(manifest_path: Path, records: Sequence[ReferenceRecord]) -> None:
    """Atomically write the deterministic serialization to ``manifest_path``.

    This is a serialization-to-disk primitive only; it never copies or imports
    external image files and never derives records from external images.
    """
    path = Path(manifest_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".ref_", suffix=".tmp")
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


def validate_manifest(manifest_path: Path) -> list[str]:
    """Read-only metadata validation; returns a list of error strings ([] = valid).

    Validates schema/root shape, required/optional fields, sha256 format,
    file_type, asset_id uniqueness, relative-path safety (absolute/drive/UNC/
    traversal/asset-root), and filename/relative_path consistency. It never
    reads or hashes asset bytes and never scans the library directory.
    """
    path = Path(manifest_path)
    if not path.exists():
        return ["manifest does not exist"]

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"manifest is not valid JSON: {exc}"]

    if not isinstance(data, dict):
        return ["manifest root must be an object"]

    errors: list[str] = []
    if data.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        errors.append(f"schema_version: expected {MANIFEST_SCHEMA_VERSION!r}")

    refs = data.get("references")
    if not isinstance(refs, list):
        errors.append("manifest root must have a 'references' array")
        return errors

    seen_ids: dict[str, int] = {}
    for index, item in enumerate(refs):
        prefix = f"references[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix}: not an object")
            continue

        for field in REQUIRED_FIELDS:
            if field not in item:
                errors.append(f"{prefix}.{field}: required field missing")
        for field in OPTIONAL_FIELDS:
            value = item.get(field)
            if value is not None and not isinstance(value, str):
                errors.append(f"{prefix}.{field}: expected string")

        aid = item.get("asset_id")
        if isinstance(aid, str) and aid != "":
            if aid in seen_ids:
                errors.append(
                    f"{prefix}.asset_id: duplicate {aid!r} (also at {seen_ids[aid]})"
                )
            else:
                seen_ids[aid] = index
        elif "asset_id" in item:
            errors.append(f"{prefix}.asset_id: required non-empty string")

        cid = item.get("character_id")
        if "character_id" in item and (not isinstance(cid, str) or cid == ""):
            errors.append(f"{prefix}.character_id: required non-empty string")

        coll = item.get("collection")
        if coll is not None and not isinstance(coll, str):
            errors.append(f"{prefix}.collection: expected string metadata")

        ft = item.get("file_type")
        if "file_type" in item and canonical_file_type(ft) is None:
            errors.append(f"{prefix}.file_type: unsupported metadata file type {ft!r}")

        sha = item.get("sha256")
        if "sha256" in item and not is_valid_sha256(sha):
            errors.append(f"{prefix}.sha256: expected 64-character lowercase hex digest")

        rel = item.get("relative_path")
        if "relative_path" in item:
            if not isinstance(rel, str) or rel == "":
                errors.append(f"{prefix}.relative_path: required non-empty string")
            else:
                if not is_safe_relative_path(rel):
                    errors.append(
                        f"{prefix}.relative_path: absolute, drive-qualified, UNC, "
                        "or contains traversal"
                    )
                elif not is_under_asset_root(rel):
                    errors.append(
                        f"{prefix}.relative_path: outside future asset bytes root "
                        f"{ASSET_ROOT!r}"
                    )

        filename = item.get("filename")
        if "filename" in item and (not isinstance(filename, str) or filename == ""):
            errors.append(f"{prefix}.filename: required non-empty string")
        if isinstance(rel, str) and rel != "" and isinstance(filename, str):
            if filename != rel.split("/")[-1]:
                errors.append(f"{prefix}.filename: does not match relative_path basename")

    return errors


def find_records_by_sha256(
    records: Sequence[ReferenceRecord], sha256: str
) -> list[ReferenceRecord]:
    """Return records whose ``sha256`` equals ``sha256`` (query primitive).

    Invalid query digests are rejected before filtering.
    """
    if not is_valid_sha256(sha256):
        raise ReferenceLibrarySha256Error(
            "sha256: expected 64-character lowercase hex digest"
        )
    return [rec for rec in records if rec.sha256 == sha256]


def lookup_record(records: Sequence[ReferenceRecord], asset_id: str) -> ReferenceRecord:
    """Return exactly one record by ``asset_id``; fail closed on 0 or >1 matches."""
    matches = [rec for rec in records if rec.asset_id == asset_id]
    if not matches:
        raise ReferenceLibraryNotFoundError(f"asset_id {asset_id!r} not found")
    if len(matches) > 1:
        raise ReferenceLibraryValidationError(
            f"asset_id {asset_id!r} is ambiguous ({len(matches)} records)"
        )
    return matches[0]
