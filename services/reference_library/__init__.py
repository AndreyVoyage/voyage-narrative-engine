#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Reference Library -- public API (SVA-RL1 foundation + SVA-RL2 controlled import).

Exposes the frozen ``ReferenceRecord`` model, deterministic manifest
serialize/load/validate, safe repo-relative path validation, SHA-256
validation/query primitives, and the SVA-RL2 controlled-import API
(``import_reference``). Import performs an explicit single-file COPY (never a
move/delete), validates format by magic bytes, enforces duplicate/ownership
policies, and atomically registers the manifest. There is no directory scan,
no synchronization, and no update/remove in v0.
"""

from __future__ import annotations

from .errors import (
    AssetIdCollisionError,
    CrossCharacterDuplicateError,
    FormatMismatchError,
    ReferenceLibraryDuplicateError,
    ReferenceLibraryError,
    ReferenceLibraryFileTypeError,
    ReferenceLibraryImportError,
    ReferenceLibraryManifestError,
    ReferenceLibraryNotFoundError,
    ReferenceLibraryPathError,
    ReferenceLibrarySha256Error,
    ReferenceLibraryValidationError,
    SourceValidationError,
    UnsupportedFormatError,
)
from .hashing import compute_sha256, is_valid_sha256
from .importer import (
    IMPORTED,
    NO_OP_DUPLICATE,
    NO_OP_EXISTING_ASSET,
    ImportResult,
    compute_destination_relative_path,
    import_reference,
    sniff_image_format,
)
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
    "import_reference",
    "ImportResult",
    "IMPORTED",
    "NO_OP_DUPLICATE",
    "NO_OP_EXISTING_ASSET",
    "sniff_image_format",
    "compute_destination_relative_path",
    "ReferenceLibraryError",
    "ReferenceLibraryManifestError",
    "ReferenceLibraryValidationError",
    "ReferenceLibraryPathError",
    "ReferenceLibrarySha256Error",
    "ReferenceLibraryFileTypeError",
    "ReferenceLibraryDuplicateError",
    "ReferenceLibraryNotFoundError",
    "ReferenceLibraryImportError",
    "SourceValidationError",
    "UnsupportedFormatError",
    "FormatMismatchError",
    "CrossCharacterDuplicateError",
    "AssetIdCollisionError",
]
