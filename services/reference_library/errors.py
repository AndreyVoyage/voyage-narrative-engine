#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exception hierarchy for Reference Library v0 (SVA-RL1 + SVA-RL2).

Small, transport-independent, named exceptions. Messages never carry raw asset
bytes, absolute machine paths, or external-source content. This package spans
the RL1 foundation (read/validate/serialize) and the RL2 controlled import
(explicit single-file copy-in). Import never scans, synchronizes, moves, or
deletes sources and never mutates the manifest from an external image.
"""

from __future__ import annotations


class ReferenceLibraryError(Exception):
    """Root of the Reference Library exception hierarchy."""


class ReferenceLibraryManifestError(ReferenceLibraryError):
    """Raised when the manifest is missing, unreadable, not valid JSON, or has
    a wrong root shape / schema version."""


class ReferenceLibraryValidationError(ReferenceLibraryError):
    """Raised when a reference record is structurally unsound."""


class ReferenceLibraryPathError(ReferenceLibraryValidationError):
    """Raised when a ``relative_path`` is absolute, drive-qualified, a UNC path,
    contains traversal, or falls outside the future asset bytes root."""


class ReferenceLibrarySha256Error(ReferenceLibraryValidationError):
    """Raised when a ``sha256`` is not a 64-character lowercase hex digest."""


class ReferenceLibraryFileTypeError(ReferenceLibraryValidationError):
    """Raised when a ``file_type`` is not a supported metadata file type."""


class ReferenceLibraryDuplicateError(ReferenceLibraryValidationError):
    """Raised when an ``asset_id`` appears more than once (or a lookup is
    ambiguous)."""


class ReferenceLibraryNotFoundError(ReferenceLibraryError):
    """Raised when a requested ``asset_id`` has no manifest record."""


class ReferenceLibraryImportError(ReferenceLibraryError):
    """Root of the controlled-import (SVA-RL2) exception hierarchy."""


class SourceValidationError(ReferenceLibraryImportError):
    """Raised when the source is missing, not a regular file, a symlink, empty,
    or unreadable."""


class UnsupportedFormatError(ReferenceLibraryImportError):
    """Raised when the source bytes are not a supported image format."""


class FormatMismatchError(ReferenceLibraryImportError):
    """Raised when the source extension disagrees with its magic-byte signature."""


class CrossCharacterDuplicateError(ReferenceLibraryImportError):
    """Raised when identical bytes already exist under a different character_id."""


class AssetIdCollisionError(ReferenceLibraryImportError):
    """Raised when ``asset_id`` already exists with a different semantic asset."""
