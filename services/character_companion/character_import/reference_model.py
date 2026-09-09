#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Frozen per-asset reference record for a Companion character snapshot.

Metadata only: this model never reads, writes, copies, or decodes image bytes.

Required: ``asset_id``, ``character_id``, ``relative_path``, ``filename``,
``sha256``, ``file_type``. Optional import metadata: ``source_filename``,
``created``.

Semantic role(s) for an asset live on ``CharacterLocalSnapshot`` (not here),
so this record stays a thin technical manifest entry.

Vendoring note: adapted from ``services/reference_library/model.py`` in the VNE
repo. Adaptation: dropped ``collection`` / ``mime_type`` / ``notes`` fields
(schema minimization); ``relative_path`` is snapshot-relative (validated by
``reference_manifest``), not repo-relative.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from .errors import ReferenceFileTypeError, ReferenceSha256Error, ReferenceValidationError
from .hashing import is_valid_sha256

SUPPORTED_FILE_TYPES = ("PNG", "JPEG", "WEBP")

# JPG/JPEG both canonicalize to JPEG.
_FILE_TYPE_ALIASES = {"PNG": "PNG", "JPEG": "JPEG", "JPG": "JPEG", "WEBP": "WEBP"}

RECORD_FIELD_ORDER = (
    "asset_id",
    "character_id",
    "relative_path",
    "filename",
    "sha256",
    "file_type",
    "source_filename",
    "created",
)

REQUIRED_FIELDS = ("asset_id", "character_id", "relative_path", "filename", "sha256", "file_type")
OPTIONAL_FIELDS = ("source_filename", "created")


def canonical_file_type(value: Any) -> Optional[str]:
    """Return the canonical metadata file type, or None if unsupported."""
    if not isinstance(value, str):
        return None
    return _FILE_TYPE_ALIASES.get(value.upper())


def _require_non_empty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or value == "":
        raise ReferenceValidationError(f"{field}: required non-empty string")
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
    source_filename: Optional[str] = None
    created: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "asset_id", _require_non_empty_string(self.asset_id, "asset_id"))
        object.__setattr__(self, "character_id", _require_non_empty_string(self.character_id, "character_id"))
        object.__setattr__(self, "relative_path", _require_non_empty_string(self.relative_path, "relative_path"))
        object.__setattr__(self, "filename", _require_non_empty_string(self.filename, "filename"))
        object.__setattr__(self, "sha256", _require_non_empty_string(self.sha256, "sha256"))
        if not is_valid_sha256(self.sha256):
            raise ReferenceSha256Error("sha256: expected 64-character lowercase hex digest")

        canonical = canonical_file_type(self.file_type)
        if canonical is None:
            raise ReferenceFileTypeError(f"file_type: unsupported metadata file type {self.file_type!r}")
        object.__setattr__(self, "file_type", canonical)

        for field in OPTIONAL_FIELDS:
            value = getattr(self, field)
            if value is not None and not isinstance(value, str):
                raise ReferenceValidationError(f"{field}: expected string")

    def to_dict(self) -> dict[str, Any]:
        """Fresh plain dict, deterministic key order, omitting None."""
        result: dict[str, Any] = {}
        for key in RECORD_FIELD_ORDER:
            value = getattr(self, key)
            if value is not None:
                result[key] = value
        return result

    @classmethod
    def from_dict(cls, data: Any) -> "ReferenceRecord":
        if not isinstance(data, dict):
            raise ReferenceValidationError("record must be an object")
        for field in REQUIRED_FIELDS:
            if field not in data:
                raise ReferenceValidationError(f"{field}: required field missing")
        kwargs: dict[str, Any] = {field: data[field] for field in REQUIRED_FIELDS}
        for field in OPTIONAL_FIELDS:
            if field in data:
                kwargs[field] = data[field]
        return cls(**kwargs)
