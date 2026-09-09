#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Character Canon snapshot models.

Deeply immutable, stdlib-only. A snapshot freezes WHICH Character Canon state
was read, without copying the entire external repository and without ever
exposing an absolute machine path.

Vendoring note: copied near-as-is from
``services/character_canon_bridge/model.py`` in the VNE repo (frozen
dataclasses + fresh-plain serialization; only the module docstring/header was
adjusted).
"""

from __future__ import annotations

import dataclasses
from typing import Any, Optional, Tuple


@dataclasses.dataclass(frozen=True)
class CanonReference:
    """One repo-relative Canon reference path, keyed by logical role."""

    key: str
    path: str

    def to_dict(self) -> dict[str, Any]:
        return {"key": self.key, "path": self.path}


@dataclasses.dataclass(frozen=True)
class Provenance:
    """Portable, loader-generated source provenance.

    ``source_ref`` is repository-relative and must never carry an absolute
    machine path. ``source_hash`` is the deterministic SHA-256 of the
    canonicalized authoritative source JSON.
    """

    source_kind: str
    source_ref: str
    source_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_kind": self.source_kind,
            "source_ref": self.source_ref,
            "source_hash": self.source_hash,
        }


@dataclasses.dataclass(frozen=True)
class CharacterCanonSnapshot:
    """The immutable, serializable snapshot of one character's Canon state.

    ``status`` is the exact authoritative status string from the source; it is
    never rewritten or mapped to an invented equivalence in the snapshot.
    """

    schema_version: str
    character_id: str
    status: str
    references: Tuple[CanonReference, ...]
    content_hash: str
    provenance: Provenance
    active_version: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "references", tuple(self.references))

    def semantic_payload(self) -> dict[str, Any]:
        """Return exactly the hashed semantic payload (fresh plain data).

        Machine-specific roots, envelope metadata, and provenance are NOT part
        of the semantic payload.
        """
        payload: dict[str, Any] = {
            "character_id": self.character_id,
            "status": self.status,
            "references": [r.to_dict() for r in self.references],
        }
        if self.active_version is not None:
            payload["active_version"] = self.active_version
        return payload

    def to_dict(self) -> dict[str, Any]:
        """Return the full snapshot envelope (fresh plain data)."""
        result: dict[str, Any] = {
            "schema_version": self.schema_version,
            "character_id": self.character_id,
            "status": self.status,
            "references": [r.to_dict() for r in self.references],
            "content_hash": self.content_hash,
            "provenance": self.provenance.to_dict(),
        }
        if self.active_version is not None:
            result["active_version"] = self.active_version
        return result
