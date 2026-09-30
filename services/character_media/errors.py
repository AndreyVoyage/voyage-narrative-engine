#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Character Media v0 -- named failure hierarchy.

Small, transport-independent, stdlib-only exceptions. Messages never carry raw
asset bytes, absolute machine paths, or external-source content. The package
spans managed Primary Portrait storage, deterministic image validation, and the
revision-binding shape (role + publishability).
"""

from __future__ import annotations


class CharacterMediaError(Exception):
    """Root of the Character Media exception hierarchy."""


class CharacterMediaValidationError(CharacterMediaError):
    """A managed asset or portrait binding violates the ratified contract."""


class SourceValidationError(CharacterMediaValidationError):
    """The source is missing, a symlink, not a regular file, empty, or unreadable."""


class UnsupportedFormatError(CharacterMediaValidationError):
    """The source bytes are not a supported V1 image format (PNG/JPEG/WEBP)."""


class AnimatedImageError(CharacterMediaValidationError):
    """The source is animated / multi-frame (GIF-like APNG / animated WEBP)."""


class OversizedAssetError(CharacterMediaValidationError):
    """The asset exceeds the ratified ``maxSingleFileBytes`` limit."""


class OversizedDimensionError(CharacterMediaValidationError):
    """The asset exceeds the ratified ``maxRasterDimension`` limit."""


class MalformedImageError(CharacterMediaValidationError):
    """The image header cannot be deterministically parsed."""


class InvalidBindingError(CharacterMediaValidationError):
    """A ``primary_portrait`` binding is structurally unsound or has unknown values."""


class Sha256MismatchError(CharacterMediaError):
    """Staged or managed bytes do not match the expected SHA-256 digest."""


class AssetCollisionError(CharacterMediaError):
    """A content-addressed path already holds different bytes."""


class AssetNotFoundError(CharacterMediaError):
    """A requested managed asset does not exist."""


class CharacterMediaStorageError(CharacterMediaError):
    """The managed store could not safely read or write local bytes."""
