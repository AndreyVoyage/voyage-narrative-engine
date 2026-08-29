#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Reference Library v0 -- plain-data model (SVA-RL1).

Frozen, stdlib-only plain data for one technical manifest record. The model is
metadata only: it never reads, writes, copies, or decodes image bytes.

Required fields: ``asset_id``, ``character_id``, ``relative_path``,
``filename``, ``sha256``, ``file_type``.

Optional free-string metadata: ``collection``, ``mime_type``,
``source_filename``, ``created``, ``notes``.

- ``character_id`` is required, opaque, generic, non-empty, and never mapped to
  a production enum or a filesystem directory.
- ``collection`` is optional free-string metadata (never a path segment and
  never a slug-derived filesystem path).
- ``file_type`` is normalized to the supported metadata set (PNG/JPEG/WEBP);
  ``JPG``/``JPEG`` both canonicalize to ``JPEG``.

Path safety (absolute/drive/UNC/traversal/asset-root) is enforced by
``services.reference_library.manifest``; the model only validates field
presence, types, sha256 format, and file_type.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from .errors import (
    ReferenceLibraryFileTypeError,
    ReferenceLibrarySha256Error,
    ReferenceLibraryValidationError,
)
from .hashing import is_valid_sha256

SUPPORTED_FILE_TYPES = ("PNG", "JPEG", "WEBP")

# Metadata file-type normalization: JPG/JPEG both canonicalize to JPEG.
_FILE_TYPE_ALIASES = {
    "PNG": "PNG",
    "JPEG": "JPEG",
    "JPG": "JPEG",
    "WEBP": "WEBP",
}

# Fixed key order for deterministic record serialization.
RECORD_FIELD_ORDER = (
    "asset_id",
    "character_id",
    "collection",
    "relative_path",
    "filename",
    "sha256",
    "file_type",
    "mime_type",
    "source_filename",
    "created",
    "notes",
)

REQUIRED_FIELDS = (
    "asset_id",
    "character_id",
    "relative_path",
    "filename",
    "sha256",
    "file_type",
)

OPTIONAL_FIELDS = (
    "collection",
    "mime_type",
    "source_filename",
    "created",
    "notes",
)


def canonical_file_type(value: Any) -> Optional[str]:
    """Return the canonical metadata file type, or None if unsupported."""
    if not isinstance(value, str):
        return None
    return _FILE_TYPE_ALIASES.get(value.upper())


def _require_non_empty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or value == "":
        raise ReferenceLibraryValidationError(f"{field}: required non-empty string")
    return value


@dataclass(frozen=True)
class ReferenceRecord:
    """One frozen technical manifest record (asset metadata only)."""

    asset_id: str
    character_id: str
    relative_path: str
    filename: str
    sha256: str
    file_type: str
    collection: Optional[str] = None
    mime_type: Optional[str] = None
    source_filename: Optional[str] = None
    created: Optional[str] = None
    notes: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "asset_id", _require_non_empty_string(self.asset_id, "asset_id")
        )
        object.__setattr__(
            self, "character_id", _require_non_empty_string(self.character_id, "character_id")
        )
        object.__setattr__(
            self, "relative_path", _require_non_empty_string(self.relative_path, "relative_path")
        )
        object.__setattr__(
            self, "filename", _require_non_empty_string(self.filename, "filename")
        )
        object.__setattr__(
            self, "sha256", _require_non_empty_string(self.sha256, "sha256")
        )
        if not is_valid_sha256(self.sha256):
            raise ReferenceLibrarySha256Error(
                "sha256: expected 64-character lowercase hex digest"
            )

        canonical = canonical_file_type(self.file_type)
        if canonical is None:
            raise ReferenceLibraryFileTypeError(
                f"file_type: unsupported metadata file type {self.file_type!r}"
            )
        object.__setattr__(self, "file_type", canonical)

        collection = self.collection
        if collection == "":
            collection = None
        if collection is not None and not isinstance(collection, str):
            raise ReferenceLibraryValidationError("collection: expected string metadata")
        object.__setattr__(self, "collection", collection)

        for field in OPTIONAL_FIELDS:
            if field == "collection":
                continue
            value = getattr(self, field)
            if value is not None and not isinstance(value, str):
                raise ReferenceLibraryValidationError(f"{field}: expected string")

    def to_dict(self) -> dict[str, Any]:
        """Return a fresh plain dict with deterministic key order, omitting None."""
        result: dict[str, Any] = {}
        for key in RECORD_FIELD_ORDER:
            value = getattr(self, key)
            if value is not None:
                result[key] = value
        return result

    @classmethod
    def from_dict(cls, data: Any) -> "ReferenceRecord":
        """Build a validated record from plain dict data.

        Raises ``ReferenceLibraryValidationError`` (or a subclass) on any
        missing/invalid field. Path safety is enforced at the manifest layer,
        not here.
        """
        if not isinstance(data, dict):
            raise ReferenceLibraryValidationError("record must be an object")

        for field in REQUIRED_FIELDS:
            if field not in data:
                raise ReferenceLibraryValidationError(f"{field}: required field missing")

        kwargs: dict[str, Any] = {field: data[field] for field in REQUIRED_FIELDS}
        for field in OPTIONAL_FIELDS:
            if field in data:
                kwargs[field] = data[field]

        return cls(**kwargs)
