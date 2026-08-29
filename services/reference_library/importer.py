#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Reference Library v0 -- controlled import (SVA-RL2).

Explicit single-file controlled import into the VNE Reference Library:

    explicit source file
    -> validate (exists / regular / non-empty / non-symlink)
    -> sniff supported image format (magic bytes, not extension alone)
    -> SHA-256 (source)
    -> duplicate / ownership checks
    -> atomic COPY (never move) with post-write SHA verification
    -> deterministic manifest registration (atomic replace)

No directory scanning, no synchronization, no source mutation, no provider,
no ReferenceBundle, and no UI. ``role``/``source_type`` are intentionally not
implemented here: they are not fields of the RL1 ``ReferenceRecord`` model, and
adding them would materially change the published RL1 manifest contract.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union

from .errors import (
    AssetIdCollisionError,
    CrossCharacterDuplicateError,
    FormatMismatchError,
    ReferenceLibraryImportError,
    ReferenceLibraryValidationError,
    SourceValidationError,
    UnsupportedFormatError,
)
from .hashing import compute_sha256
from .manifest import (
    ASSET_ROOT,
    default_manifest_path,
    find_records_by_sha256,
    is_valid_relative_path,
    load_manifest,
    save_manifest,
)
from .model import ReferenceRecord

# Import outcome statuses (deterministic).
IMPORTED = "IMPORTED"
NO_OP_DUPLICATE = "NO_OP_DUPLICATE"
NO_OP_EXISTING_ASSET = "NO_OP_EXISTING_ASSET"

# Supported formats: canonical key -> (canonical extension, file_type, mime).
_SUPPORTED_FORMATS = {
    "png": ("png", "PNG", "image/png"),
    "jpg": ("jpg", "JPEG", "image/jpeg"),
    "webp": ("webp", "WEBP", "image/webp"),
}

# Source filename extension -> canonical format key (None when unsupported).
_SOURCE_EXT_ALIASES = {
    "png": "png",
    "jpg": "jpg",
    "jpeg": "jpg",
    "webp": "webp",
}

_PNG_SIG = b"\x89PNG\r\n\x1a\n"
_JPEG_SIG = b"\xff\xd8\xff"


def sniff_image_format(data: bytes) -> Optional[str]:
    """Return the canonical format key (png/jpg/webp) or None."""
    if data.startswith(_PNG_SIG):
        return "png"
    if data.startswith(_JPEG_SIG):
        return "jpg"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def _source_ext_format(name: str) -> Optional[str]:
    if "." not in name:
        return None
    ext = name.rsplit(".", 1)[-1].lower()
    return _SOURCE_EXT_ALIASES.get(ext)


def _is_safe_path_segment(value: str) -> bool:
    """True for a non-empty single path segment (no separators/traversal)."""
    return (
        isinstance(value, str)
        and value != ""
        and value not in (".", "..")
        and "/" not in value
        and "\\" not in value
    )


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def compute_destination_relative_path(character_id: str, asset_id: str, ext: str) -> str:
    """Return the canonical repo-relative destination path (forward slashes)."""
    return f"{ASSET_ROOT}/characters/{character_id}/{asset_id}.{ext}"


@dataclass(frozen=True)
class ImportResult:
    """Deterministic outcome of one controlled import attempt."""

    status: str
    record: ReferenceRecord
    copied: bool
    relative_path: str
    sha256: str


def _read_and_validate_source(source_path: Path) -> tuple[bytes, str, str, str, str]:
    """Return (data, format_key, ext, file_type, mime); raise on source failure."""
    if not source_path.exists():
        raise SourceValidationError("source does not exist")
    if source_path.is_symlink():
        raise SourceValidationError("symlinked sources are rejected")
    if not source_path.is_file():
        raise SourceValidationError("source is not a regular file")
    try:
        size = source_path.stat().st_size
    except OSError as exc:
        raise SourceValidationError(f"source is unreadable: {exc}") from exc
    if size <= 0:
        raise SourceValidationError("source file is empty")
    try:
        data = source_path.read_bytes()
    except OSError as exc:
        raise SourceValidationError(f"source is unreadable: {exc}") from exc

    fmt = sniff_image_format(data)
    if fmt is None:
        raise UnsupportedFormatError("unsupported or unrecognized image format")

    declared = _source_ext_format(source_path.name)
    if declared is not None and declared != fmt:
        raise FormatMismatchError(
            f"extension/signature mismatch: bytes are {fmt!r}"
        )

    ext, file_type, mime = _SUPPORTED_FORMATS[fmt]
    return data, fmt, ext, file_type, mime


def _atomic_copy_verified(data: bytes, expected_sha: str, dest: Path) -> None:
    """Stage bytes to a temp file, verify SHA, then atomically install at dest."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(dest.parent), prefix=".ref_", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
        actual = compute_sha256(Path(tmp).read_bytes())
        if actual != expected_sha:
            raise ReferenceLibraryImportError("staged copy SHA mismatch")
        os.replace(tmp, str(dest))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def import_reference(
    source_path: Union[str, Path],
    *,
    repo_root: Path,
    asset_id: str,
    character_id: str,
    manifest_path: Optional[Path] = None,
    collection: Optional[str] = None,
    source_filename: Optional[str] = None,
    notes: Optional[str] = None,
) -> ImportResult:
    """Import exactly one explicit source file into the Reference Library.

    COPY-only (never moves/deletes the source). Fails closed on invalid source,
    unsafe identifiers, cross-character duplicates, and asset_id collisions.
    Never overwrites an existing asset. Returns a deterministic ImportResult.
    """
    source = Path(source_path)
    root = Path(repo_root)
    manifest = (
        Path(manifest_path) if manifest_path is not None else default_manifest_path(root)
    )

    if not _is_safe_path_segment(asset_id):
        raise ReferenceLibraryValidationError(
            f"asset_id is not a safe path segment: {asset_id!r}"
        )
    if not _is_safe_path_segment(character_id):
        raise ReferenceLibraryValidationError(
            f"character_id is not a safe path segment: {character_id!r}"
        )

    data, fmt, ext, file_type, mime = _read_and_validate_source(source)
    source_sha = compute_sha256(data)

    relative_path = compute_destination_relative_path(character_id, asset_id, ext)
    if not is_valid_relative_path(relative_path):
        raise ReferenceLibraryValidationError(
            f"computed destination is unsafe: {relative_path!r}"
        )

    dest = root / relative_path

    records = load_manifest(manifest) if manifest.exists() else []

    # asset_id collision policy (OD-SVA-RL2-IMPL-03).
    existing_by_id = {r.asset_id: r for r in records}
    if asset_id in existing_by_id:
        existing = existing_by_id[asset_id]
        if existing.sha256 == source_sha and existing.character_id == character_id:
            return ImportResult(
                status=NO_OP_EXISTING_ASSET,
                record=existing,
                copied=False,
                relative_path=existing.relative_path,
                sha256=existing.sha256,
            )
        raise AssetIdCollisionError(
            f"asset_id {asset_id!r} already exists with a different semantic asset"
        )

    # duplicate SHA ownership policy (OD-SVA-RL2-IMPL-02).
    matches = find_records_by_sha256(records, source_sha)
    if matches:
        same_char = sorted(
            (r for r in matches if r.character_id == character_id),
            key=lambda r: r.asset_id,
        )
        if same_char:
            existing = same_char[0]
            return ImportResult(
                status=NO_OP_DUPLICATE,
                record=existing,
                copied=False,
                relative_path=existing.relative_path,
                sha256=existing.sha256,
            )
        raise CrossCharacterDuplicateError(
            "identical bytes already exist under a different character_id"
        )

    if dest.exists():
        raise ReferenceLibraryImportError(
            f"destination already exists but has no manifest record: {relative_path!r}"
        )

    # atomic COPY with post-write SHA verification (never move source).
    _atomic_copy_verified(data, source_sha, dest)

    record = ReferenceRecord(
        asset_id=asset_id,
        character_id=character_id,
        relative_path=relative_path,
        filename=f"{asset_id}.{ext}",
        sha256=source_sha,
        file_type=file_type,
        collection=collection,
        mime_type=mime,
        source_filename=source_filename if source_filename is not None else source.name,
        created=_utcnow(),
        notes=notes,
    )

    try:
        save_manifest(manifest, records + [record])
    except Exception:
        # Roll back ONLY the destination created by this operation.
        try:
            os.unlink(dest)
        except OSError:
            pass
        raise

    return ImportResult(
        status=IMPORTED,
        record=record,
        copied=True,
        relative_path=relative_path,
        sha256=source_sha,
    )
