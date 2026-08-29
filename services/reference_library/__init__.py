#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Reference Library v0 (SVA-RL1) -- public API.

Exposes the frozen ``ReferenceRecord`` model, deterministic manifest
serialize/load/validate, safe repo-relative path validation, and SHA-256
validation/query primitives. This package is foundation-only: it never copies,
imports, scans, or deletes external image files, and never mutates the manifest
from an external image. Controlled import (add/update/remove/copy) belongs to
SVA-RL2.
"""

from __future__ import annotations

from .errors import (
    ReferenceLibraryDuplicateError,
    ReferenceLibraryError,
    ReferenceLibraryFileTypeError,
    ReferenceLibraryManifestError,
    ReferenceLibraryNotFoundError,
    ReferenceLibraryPathError,
    ReferenceLibrarySha256Error,
    ReferenceLibraryValidationError,
)
from .hashing import compute_sha256, is_valid_sha256
from .manifest import (
    ASSET_ROOT,
    LIBRARY_ROOT,
    MANIFEST_FILENAME,
    MANIFEST_RELATIVE_PATH,
    MANIFEST_SCHEMA_VERSION,
    default_manifest_path,
    find_records_by_sha256,
    is_safe_relative_path,
    is_under_asset_root,
    is_valid_relative_path,
    load_manifest,
    lookup_record,
    parse_manifest,
    save_manifest,
    serialize_manifest,
    validate_manifest,
)
from .model import (
    OPTIONAL_FIELDS,
    REQUIRED_FIELDS,
    RECORD_FIELD_ORDER,
    SUPPORTED_FILE_TYPES,
    ReferenceRecord,
    canonical_file_type,
)

__all__ = [
    "ReferenceRecord",
    "SUPPORTED_FILE_TYPES",
    "canonical_file_type",
    "RECORD_FIELD_ORDER",
    "REQUIRED_FIELDS",
    "OPTIONAL_FIELDS",
    "LIBRARY_ROOT",
    "ASSET_ROOT",
    "MANIFEST_FILENAME",
    "MANIFEST_RELATIVE_PATH",
    "MANIFEST_SCHEMA_VERSION",
    "default_manifest_path",
    "serialize_manifest",
    "parse_manifest",
    "load_manifest",
    "save_manifest",
    "validate_manifest",
    "is_safe_relative_path",
    "is_under_asset_root",
    "is_valid_relative_path",
    "compute_sha256",
    "is_valid_sha256",
    "find_records_by_sha256",
    "lookup_record",
    "ReferenceLibraryError",
    "ReferenceLibraryManifestError",
    "ReferenceLibraryValidationError",
    "ReferenceLibraryPathError",
    "ReferenceLibrarySha256Error",
    "ReferenceLibraryFileTypeError",
    "ReferenceLibraryDuplicateError",
    "ReferenceLibraryNotFoundError",
]
