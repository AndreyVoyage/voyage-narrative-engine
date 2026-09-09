#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Exception hierarchy for the Companion controlled Character Canon import.

Single root so callers can catch the whole subsystem. Messages carry stable
logical identifiers only -- never absolute machine paths, never Canon content,
never raw asset bytes.

Vendoring note: the Canon-read and reference-import error taxonomies are
adapted from the VNE repo (see docs/character_companion/
VISUAL_PIPELINE_VENDOR_PROVENANCE_V1.md).
"""

from __future__ import annotations


class CharacterImportError(Exception):
    """Root of the Companion character-import exception hierarchy."""


# ---- Canon read (adapted from services/character_canon_bridge/errors.py) ----
class CanonRootMissingError(CharacterImportError):
    """The supplied Character Canon root does not exist."""


class CharacterNotFoundError(CharacterImportError):
    """The requested character has no authoritative Canon entry."""


class AmbiguousCharacterError(CharacterImportError):
    """A character cannot be resolved unambiguously (declared id mismatch)."""


class CanonFormatError(CharacterImportError):
    """The authoritative Canon metadata is missing or malformed."""


class CanonStatusUnknownError(CharacterImportError):
    """The Canon status is missing or not a known machine value."""


class ReferencePathSafetyError(CharacterImportError):
    """A Canon reference path is absolute, drive-qualified, UNC, or traverses."""


class ProductionNotAllowedError(CharacterImportError):
    """A production import was requested but the Canon status does not permit
    production use (only ``APPROVED_AS_CANON`` does)."""


class UnsupportedUsageContextError(CharacterImportError):
    """The usage_context is not a supported enumerated value."""


# ---- reference import (adapted from services/reference_library/errors.py) ----
class ReferenceValidationError(CharacterImportError):
    """A reference record is structurally unsound."""


class ReferenceSha256Error(ReferenceValidationError):
    """A sha256 is not a 64-character lowercase hex digest."""


class ReferenceFileTypeError(ReferenceValidationError):
    """A file_type is not a supported metadata file type (PNG/JPEG/WEBP)."""


class ReferenceManifestError(CharacterImportError):
    """The reference manifest is missing, unreadable, or has a wrong shape."""


class ReferenceImportError(CharacterImportError):
    """Root of the controlled single-file import failures."""


class SourceValidationError(ReferenceImportError):
    """The source is missing, not a regular file, a symlink, empty, unreadable."""


class UnsupportedFormatError(ReferenceImportError):
    """The source bytes are not a supported image format."""


class FormatMismatchError(ReferenceImportError):
    """The source extension disagrees with its magic-byte signature."""


class CrossCharacterDuplicateError(ReferenceImportError):
    """Identical bytes already exist under a different character_id."""


class AssetIdCollisionError(ReferenceImportError):
    """asset_id already exists with a different semantic asset."""


# ---- local snapshot ----------------------------------------------------
class SnapshotError(CharacterImportError):
    """Root of local-snapshot read/validate/activate failures."""


class SnapshotNotFoundError(SnapshotError):
    """No snapshot (or no active snapshot) exists for the character."""


class SnapshotValidationError(SnapshotError):
    """A persisted local snapshot failed a fail-closed integrity check."""


class SnapshotOperationError(SnapshotError):
    """An add/update/activate operation was invalid for the current state."""
