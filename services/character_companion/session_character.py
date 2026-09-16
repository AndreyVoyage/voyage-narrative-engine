#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Immutable typed contracts for exact character selection and session pinning.

S8B bounded slice: these types carry the exact Package V1 identity required to
create a NEW pinned Companion session, and the immutable pin persisted with it.
They deliberately contain no memory, state, runtime wiring, catalog, provider,
or package filesystem logic.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Mapping

__all__ = [
    "ExactCharacterSelectionV1",
    "LEGACY_UNPINNED",
    "PINNED_V1",
    "SessionCharacterError",
    "SessionCharacterPinStatus",
    "SessionCharacterPinV1",
]

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

#: Code-level storage-namespace scheme bound into the pinned namespace preimage.
_PINNED_STORAGE_SCHEME = "pinned-storage-v1"


class SessionCharacterError(ValueError):
    """A selection or persisted pin does not satisfy the immutable V1 contract."""


class SessionCharacterPinStatus(str, Enum):
    """Explicit session character-binding classification at read time.

    ``LEGACY_UNPINNED`` means the historical exact authored definition is not
    known; it never implies ``release_id == legacy-compat-v1``.
    """

    PINNED_V1 = "PINNED_V1"
    LEGACY_UNPINNED = "LEGACY_UNPINNED"


PINNED_V1 = SessionCharacterPinStatus.PINNED_V1
LEGACY_UNPINNED = SessionCharacterPinStatus.LEGACY_UNPINNED


def _require_exact_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SessionCharacterError(f"{field_name} must be a non-empty string")
    return value


def _require_sha256(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise SessionCharacterError(f"{field_name} must be a lowercase SHA-256 digest")
    return value


def _validate_four_fields(
    character_id: object,
    release_id: object,
    package_hash: object,
    runtime_definition_hash: object,
) -> None:
    _require_exact_string(character_id, "character_id")
    _require_exact_string(release_id, "release_id")
    _require_sha256(package_hash, "package_hash")
    _require_sha256(runtime_definition_hash, "runtime_definition_hash")


@dataclass(frozen=True, slots=True)
class ExactCharacterSelectionV1:
    """Exact, caller-supplied Package V1 identity for a NEW pinned session.

    There is no latest / current / active / highest-version / lexicographic /
    directory / catalog fallback. All four values must match the installed
    package exactly or the session is never written.
    """

    character_id: str
    release_id: str
    package_hash: str
    runtime_definition_hash: str

    def __post_init__(self) -> None:
        _validate_four_fields(
            self.character_id,
            self.release_id,
            self.package_hash,
            self.runtime_definition_hash,
        )

    def to_pin(self) -> "SessionCharacterPinV1":
        return SessionCharacterPinV1(
            character_id=self.character_id,
            release_id=self.release_id,
            package_hash=self.package_hash,
            runtime_definition_hash=self.runtime_definition_hash,
        )


@dataclass(frozen=True, slots=True)
class SessionCharacterPinV1:
    """Immutable persisted identity bound to a session row at creation time.

    The persisted identity is ONLY these four fields; anything else is either
    transitively bound by ``runtime_definition_hash`` or belongs to a later
    slice (S8B2 memory/state namespace).
    """

    character_id: str
    release_id: str
    package_hash: str
    runtime_definition_hash: str

    def __post_init__(self) -> None:
        _validate_four_fields(
            self.character_id,
            self.release_id,
            self.package_hash,
            self.runtime_definition_hash,
        )

    def to_json(self) -> dict:
        return {
            "character_id": self.character_id,
            "release_id": self.release_id,
            "package_hash": self.package_hash,
            "runtime_definition_hash": self.runtime_definition_hash,
        }

    def storage_namespace_id(self) -> str:
        """Deterministic immutable storage-namespace identity (SHA-256).

        Binds exactly (character_id, release_id, package_hash) under the
        ``pinned-storage-v1`` scheme. ``runtime_definition_hash`` deliberately
        does NOT participate: it encodes adapter interpretation, not the
        immutable character-package identity whose lived memory/state must be
        stable. Returns a full 64-character lowercase hex digest -- never raw
        identity values -- so filesystem safety does not depend on raw-ID path
        safety.
        """
        payload = {
            "character_id": self.character_id,
            "package_hash": self.package_hash,
            "release_id": self.release_id,
            "scheme": _PINNED_STORAGE_SCHEME,
        }
        canonical = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    @classmethod
    def from_json(cls, data: object) -> "SessionCharacterPinV1":
        if not isinstance(data, Mapping):
            raise SessionCharacterError("character pin must be a JSON object")
        expected = {"character_id", "release_id", "package_hash", "runtime_definition_hash"}
        if set(data) != expected:
            raise SessionCharacterError(
                "character pin must contain exactly character_id, release_id, "
                "package_hash, runtime_definition_hash"
            )
        return cls(
            character_id=data["character_id"],
            release_id=data["release_id"],
            package_hash=data["package_hash"],
            runtime_definition_hash=data["runtime_definition_hash"],
        )
