#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Character Media v0 -- plain-data models.

Two deliberately distinct concepts:

- ``ManagedPortraitRecord`` -- the PHYSICAL managed asset (content-addressed
  bytes). ``relative_path`` is operational/Lab-local only and is never part of
  portable serialization or package identity.

- ``PortraitBinding`` -- the LOGICAL role assignment serialized onto an
  immutable Character Authoring revision under
  ``semantic.visual_identity.primary_portrait``. It references the physical
  asset by exact SHA-256 and carries ``publishability``.

Physical asset identity and logical role are kept separate: one physical asset
may later serve multiple roles without duplicating bytes, and this slice only
implements the Primary Portrait role.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from services.reference_library.hashing import is_valid_sha256

from .errors import InvalidBindingError

# Logical role vocabulary for this slice.
PRIMARY_PORTRAIT_ROLE = "primary_portrait"

# Technical reference role vocabulary (OD-MEDIA-REF-02). ``motion`` denotes a
# static movement/pose reference image, never video.
REFERENCE_ROLES = ("face", "body", "expression", "identity", "motion")

# Canonical uppercase Package V1 ``assetRef.semanticRole`` tokens per role.
REFERENCE_ROLE_PACKAGE_TOKENS = {
    "face": "FACE",
    "body": "BODY",
    "expression": "EXPRESSION",
    "identity": "IDENTITY",
    "motion": "MOTION",
}

# V1 supported formats (metadata file-type tokens, JPEG canonical).
SUPPORTED_FORMATS = ("PNG", "JPEG", "WEBP")

# Ratified limits (VCP-PKG-001 Section 13, FROZEN_BASELINE).
MAX_ASSET_BYTES = 64 * 1024 * 1024  # maxSingleFileBytes
MAX_RASTER_DIMENSION = 8192  # maxRasterDimension (8192 x 8192)

_FORMAT_TO_MIME = {
    "PNG": "image/png",
    "JPEG": "image/jpeg",
    "WEBP": "image/webp",
}

_FORMAT_TO_EXT = {
    "PNG": "png",
    "JPEG": "jpg",
    "WEBP": "webp",
}


class MediaPublishability(str, Enum):
    """The two ratified publication states (OD-MEDIA-PUBLISHABILITY-01)."""

    AUTHORING_ONLY = "AUTHORING_ONLY"
    PUBLISHABLE = "PUBLISHABLE"


def parse_publishability(value: object) -> MediaPublishability:
    """Return the canonical enum member, or fail closed on unknown values."""
    if isinstance(value, MediaPublishability):
        return value
    if isinstance(value, str):
        try:
            return MediaPublishability(value)
        except ValueError as exc:
            raise InvalidBindingError(
                f"publishability: unknown value {value!r}"
            ) from exc
    raise InvalidBindingError("publishability: expected a string or enum")


_BINDING_FIELDS = (
    "role",
    "asset_sha256",
    "format",
    "mime_type",
    "byte_length",
    "publishability",
)


@dataclass(frozen=True)
class PortraitBinding:
    """The revision-bound logical Primary Portrait assignment.

    ``asset_sha256`` is the physical asset reference (exact raw-bytes SHA-256).
    ``role`` is fixed to ``primary_portrait``. The managed local absolute path
    is never present here.
    """

    asset_sha256: str
    format: str
    mime_type: str
    byte_length: int
    publishability: MediaPublishability
    role: str = PRIMARY_PORTRAIT_ROLE

    def __post_init__(self) -> None:
        if self.role != PRIMARY_PORTRAIT_ROLE:
            raise InvalidBindingError(
                f"role: expected {PRIMARY_PORTRAIT_ROLE!r}"
            )
        if not is_valid_sha256(self.asset_sha256):
            raise InvalidBindingError(
                "asset_sha256: expected 64-character lowercase hex digest"
            )
        if self.format not in SUPPORTED_FORMATS:
            raise InvalidBindingError(
                f"format: unsupported {self.format!r}; expected one of "
                f"{list(SUPPORTED_FORMATS)}"
            )
        expected_mime = _FORMAT_TO_MIME[self.format]
        if self.mime_type != expected_mime:
            raise InvalidBindingError(
                f"mime_type: {self.mime_type!r} does not match format "
                f"{self.format!r} ({expected_mime!r})"
            )
        if type(self.byte_length) is not int or self.byte_length <= 0:
            raise InvalidBindingError("byte_length: expected a positive integer")
        if self.byte_length > MAX_ASSET_BYTES:
            raise InvalidBindingError(
                f"byte_length: exceeds maxSingleFileBytes ({MAX_ASSET_BYTES})"
            )
        object.__setattr__(
            self, "publishability", parse_publishability(self.publishability)
        )

    def to_dict(self) -> dict[str, Any]:
        """Return the exact serializable binding (no operational paths)."""
        return {
            "role": self.role,
            "asset_sha256": self.asset_sha256,
            "format": self.format,
            "mime_type": self.mime_type,
            "byte_length": self.byte_length,
            "publishability": self.publishability.value,
        }

    @classmethod
    def from_dict(cls, data: object) -> "PortraitBinding":
        """Build a validated binding from plain dict data (fail closed)."""
        if not isinstance(data, Mapping):
            raise InvalidBindingError("primary_portrait: expected an object")
        actual = set(data)
        expected = set(_BINDING_FIELDS)
        if actual != expected:
            missing = sorted(expected - actual)
            extra = sorted(actual - expected)
            raise InvalidBindingError(
                "primary_portrait: schema keys differ; "
                f"missing={missing}, extra={extra}"
            )
        return cls(
            role=data["role"],
            asset_sha256=data["asset_sha256"],
            format=data["format"],
            mime_type=data["mime_type"],
            byte_length=data["byte_length"],
            publishability=data["publishability"],
        )


def reference_role_package_token(role: str) -> str:
    """Return the canonical Package V1 ``semanticRole`` token for a role."""
    if role not in REFERENCE_ROLES:
        raise InvalidBindingError(f"role: unsupported reference role {role!r}")
    return REFERENCE_ROLE_PACKAGE_TOKENS[role]


@dataclass(frozen=True)
class ReferenceBinding:
    """One revision-bound technical reference role assignment.

    ``role`` is one of the five ratified reference roles (OD-MEDIA-REF-02):
    face, body, expression, identity, motion. ``asset_sha256`` is the physical
    managed asset reference (exact raw-bytes SHA-256); the managed local path is
    never present here. One physical asset may back multiple logical
    ``ReferenceBinding`` records without duplicating bytes (OD-MEDIA-REF-04).
    """

    role: str
    asset_sha256: str
    format: str
    mime_type: str
    byte_length: int
    publishability: MediaPublishability

    def __post_init__(self) -> None:
        if self.role not in REFERENCE_ROLES:
            raise InvalidBindingError(
                f"role: unsupported reference role {self.role!r}; expected one of "
                f"{list(REFERENCE_ROLES)}"
            )
        if not is_valid_sha256(self.asset_sha256):
            raise InvalidBindingError(
                "asset_sha256: expected 64-character lowercase hex digest"
            )
        if self.format not in SUPPORTED_FORMATS:
            raise InvalidBindingError(
                f"format: unsupported {self.format!r}; expected one of "
                f"{list(SUPPORTED_FORMATS)}"
            )
        expected_mime = _FORMAT_TO_MIME[self.format]
        if self.mime_type != expected_mime:
            raise InvalidBindingError(
                f"mime_type: {self.mime_type!r} does not match format "
                f"{self.format!r} ({expected_mime!r})"
            )
        if type(self.byte_length) is not int or self.byte_length <= 0:
            raise InvalidBindingError("byte_length: expected a positive integer")
        if self.byte_length > MAX_ASSET_BYTES:
            raise InvalidBindingError(
                f"byte_length: exceeds maxSingleFileBytes ({MAX_ASSET_BYTES})"
            )
        object.__setattr__(
            self, "publishability", parse_publishability(self.publishability)
        )

    @property
    def package_token(self) -> str:
        """The canonical Package V1 ``semanticRole`` token for this role."""
        return reference_role_package_token(self.role)

    def to_dict(self) -> dict[str, Any]:
        """Return the exact serializable binding (no operational paths)."""
        return {
            "role": self.role,
            "asset_sha256": self.asset_sha256,
            "format": self.format,
            "mime_type": self.mime_type,
            "byte_length": self.byte_length,
            "publishability": self.publishability.value,
        }

    @classmethod
    def from_dict(cls, data: object) -> "ReferenceBinding":
        """Build a validated binding from plain dict data (fail closed)."""
        if not isinstance(data, Mapping):
            raise InvalidBindingError("reference: expected an object")
        actual = set(data)
        expected = set(_BINDING_FIELDS)
        if actual != expected:
            missing = sorted(expected - actual)
            extra = sorted(actual - expected)
            raise InvalidBindingError(
                "reference: schema keys differ; "
                f"missing={missing}, extra={extra}"
            )
        return cls(
            role=data["role"],
            asset_sha256=data["asset_sha256"],
            format=data["format"],
            mime_type=data["mime_type"],
            byte_length=data["byte_length"],
            publishability=data["publishability"],
        )


@dataclass(frozen=True)
class ManagedPortraitRecord:
    """One immutable content-addressed managed asset (physical, Lab-local).

    ``relative_path`` is the Lab-local managed storage location and is
    operational only; it is never serialized as character authority and never
    travels inside a published ``.vchar``.
    """

    character_id: str
    asset_sha256: str
    format: str
    mime_type: str
    byte_length: int
    relative_path: str

    def __post_init__(self) -> None:
        if not self.character_id or not self.character_id.strip():
            raise InvalidBindingError("character_id: required non-empty string")
        if not is_valid_sha256(self.asset_sha256):
            raise InvalidBindingError(
                "asset_sha256: expected 64-character lowercase hex digest"
            )
        if self.format not in SUPPORTED_FORMATS:
            raise InvalidBindingError(f"format: unsupported {self.format!r}")
        if type(self.byte_length) is not int or self.byte_length <= 0:
            raise InvalidBindingError("byte_length: expected a positive integer")

    def binding(self, publishability: MediaPublishability) -> PortraitBinding:
        """Project this physical record into a logical Primary Portrait binding."""
        return PortraitBinding(
            asset_sha256=self.asset_sha256,
            format=self.format,
            mime_type=self.mime_type,
            byte_length=self.byte_length,
            publishability=publishability,
        )

    def reference_binding(
        self, role: str, publishability: MediaPublishability
    ) -> ReferenceBinding:
        """Project this physical record into a logical reference binding.

        ``role`` must be one of the five ratified reference roles. Identical
        managed bytes may be projected into any number of logical reference
        bindings (or the Primary Portrait) without duplicating the physical
        asset.
        """
        return ReferenceBinding(
            role=role,
            asset_sha256=self.asset_sha256,
            format=self.format,
            mime_type=self.mime_type,
            byte_length=self.byte_length,
            publishability=publishability,
        )


def format_extension(fmt: str) -> str:
    """Return the canonical storage extension for a supported format token."""
    if fmt not in SUPPORTED_FORMATS:
        raise InvalidBindingError(f"format: unsupported {fmt!r}")
    return _FORMAT_TO_EXT[fmt]


def format_mime_type(fmt: str) -> str:
    """Return the canonical MIME type for a supported format token."""
    if fmt not in SUPPORTED_FORMATS:
        raise InvalidBindingError(f"format: unsupported {fmt!r}")
    return _FORMAT_TO_MIME[fmt]


def validate_visual_identity_portrait(visual_identity: object) -> None:
    """Validate the reserved optional ``primary_portrait`` key when present.

    ``visual_identity`` itself remains an open/extensible dict (owner boundary):
    this function only inspects the reserved optional key ``primary_portrait``.
    When absent, it is a no-op. When present, it must be a strictly valid
    ``PortraitBinding``. Fails closed on any malformed type/field/value.
    """
    if visual_identity is None:
        return
    if not isinstance(visual_identity, Mapping):
        raise InvalidBindingError("visual_identity: expected an object")
    portrait = visual_identity.get("primary_portrait")
    if portrait is None:
        return
    # Raises InvalidBindingError for malformed dicts / missing fields /
    # unknown values (exact-key, role, sha256, format, MIME, byte_length,
    # publishability).
    PortraitBinding.from_dict(portrait)


def validate_visual_identity_references(visual_identity: object) -> None:
    """Validate the reserved optional ``references`` key when present.

    ``visual_identity`` itself remains an open/extensible dict (owner boundary):
    this function only inspects the reserved optional key ``references``. When
    absent it is a no-op. When present it must be a list.

    Each managed reference binding (a dict carrying the reserved ``role`` key)
    must be a strictly valid ``ReferenceBinding`` and fails closed on any
    malformed field/value (role vocabulary, SHA-256, format, MIME, byte length,
    publishability). Two managed bindings with the same ``(role, asset_sha256)``
    pair are rejected as duplicates (structural guard, not ranking). Legacy/
    unresolved Canon reference entries (dicts without a ``role`` key, e.g. the
    historical ``{key, path}`` shape) are left untouched and are never silently
    reinterpreted as managed bindings (OD-MEDIA-REF-06 compatibility boundary).
    Unrelated ``visual_identity`` keys are not closed.
    """
    if visual_identity is None:
        return
    if not isinstance(visual_identity, Mapping):
        raise InvalidBindingError("visual_identity: expected an object")
    references = visual_identity.get("references")
    if references is None:
        return
    if not isinstance(references, list):
        raise InvalidBindingError("references: expected a list")
    seen: set[tuple[str, str]] = set()
    for entry in references:
        if isinstance(entry, Mapping) and "role" in entry:
            # Managed reference binding: strict validation, fail closed.
            binding = ReferenceBinding.from_dict(entry)
            key = (binding.role, binding.asset_sha256)
            if key in seen:
                raise InvalidBindingError(
                    "reference: duplicate binding "
                    f"role={binding.role!r} asset_sha256={binding.asset_sha256!r}"
                )
            seen.add(key)
