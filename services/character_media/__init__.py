#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Character Media v0 -- public API.

Bounded managed storage and deterministic validation for the Primary Portrait
slice only. No Gallery, no video, no Reference Library redesign.

Exposes the physical/managed asset model, the logical revision binding, the
deterministic image validators, and the content-addressed store.
"""

from __future__ import annotations

from .errors import (
    AnimatedImageError,
    AssetCollisionError,
    AssetNotFoundError,
    CharacterMediaError,
    CharacterMediaStorageError,
    CharacterMediaValidationError,
    InvalidBindingError,
    MalformedImageError,
    OversizedAssetError,
    OversizedDimensionError,
    Sha256MismatchError,
    SourceValidationError,
    UnsupportedFormatError,
)
from .model import (
    MAX_ASSET_BYTES,
    MAX_RASTER_DIMENSION,
    PRIMARY_PORTRAIT_ROLE,
    REFERENCE_ROLES,
    REFERENCE_ROLE_PACKAGE_TOKENS,
    SUPPORTED_FORMATS,
    ManagedPortraitRecord,
    MediaPublishability,
    PortraitBinding,
    ReferenceBinding,
    format_extension,
    format_mime_type,
    parse_publishability,
    reference_role_package_token,
    validate_visual_identity_portrait,
    validate_visual_identity_references,
)
from .store import (
    CharacterMediaStore,
    default_media_root,
    media_root_next_to,
)
from .validation import (
    FORMAT_JPEG,
    FORMAT_PNG,
    FORMAT_WEBP,
    ValidatedImage,
    inspect_image,
    is_animated,
    parse_image_dimensions,
    sniff_image_format,
    validate_image_bytes,
)

__all__ = [
    "CharacterMediaError",
    "CharacterMediaValidationError",
    "SourceValidationError",
    "UnsupportedFormatError",
    "AnimatedImageError",
    "OversizedAssetError",
    "OversizedDimensionError",
    "MalformedImageError",
    "InvalidBindingError",
    "Sha256MismatchError",
    "AssetCollisionError",
    "AssetNotFoundError",
    "CharacterMediaStorageError",
    "MediaPublishability",
    "PRIMARY_PORTRAIT_ROLE",
    "REFERENCE_ROLES",
    "REFERENCE_ROLE_PACKAGE_TOKENS",
    "SUPPORTED_FORMATS",
    "PortraitBinding",
    "ReferenceBinding",
    "ManagedPortraitRecord",
    "parse_publishability",
    "reference_role_package_token",
    "format_extension",
    "format_mime_type",
    "validate_visual_identity_portrait",
    "validate_visual_identity_references",
    "CharacterMediaStore",
    "default_media_root",
    "media_root_next_to",
    "FORMAT_PNG",
    "FORMAT_JPEG",
    "FORMAT_WEBP",
    "MAX_ASSET_BYTES",
    "MAX_RASTER_DIMENSION",
    "ValidatedImage",
    "inspect_image",
    "sniff_image_format",
    "parse_image_dimensions",
    "is_animated",
    "validate_image_bytes",
]
