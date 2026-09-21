"""Pure validation helpers for Character Authoring identities and references."""

from __future__ import annotations

import re
from typing import Optional

from .errors import CharacterAuthoringInvariantError, IdentifierValidationError

_IDENTIFIER_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$", re.ASCII)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$", re.ASCII)


def validate_identifier(value: object, *, field: str) -> str:
    """Return an ASCII-safe opaque identifier or fail closed.

    Separators, drive-qualified values, traversal segments, empty strings, and
    editable display labels containing arbitrary Unicode are not valid machine
    identities.
    """
    if not isinstance(value, str) or value in ("", ".", ".."):
        raise IdentifierValidationError(f"{field}: invalid machine identifier")
    if _IDENTIFIER_RE.fullmatch(value) is None or value.endswith("."):
        raise IdentifierValidationError(
            f"{field}: expected 1-128 lowercase ASCII letters, digits, '.', '_' or '-', "
            "without a trailing '.'"
        )
    return value


def validate_snapshot_hash(value: object, *, field: str = "snapshot_hash") -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise CharacterAuthoringInvariantError(
            f"{field}: expected 64-character lowercase SHA-256"
        )
    return value


def validate_distinct_identities(
    character_id: str,
    version_id: str,
    revision_id: Optional[str] = None,
    snapshot_hash: Optional[str] = None,
) -> None:
    if character_id == version_id:
        raise CharacterAuthoringInvariantError(
            "character_id and version_id must be distinct"
        )
    if revision_id is not None and version_id == revision_id:
        raise CharacterAuthoringInvariantError(
            "version_id and revision_id must be distinct"
        )
    if revision_id is not None and snapshot_hash is not None and revision_id == snapshot_hash:
        raise CharacterAuthoringInvariantError(
            "revision_id and snapshot_hash must be distinct"
        )


def validate_provenance(
    derived_from_version_id: object,
    derived_from_revision_id: object,
    derived_from_snapshot_hash: object,
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    values = (
        derived_from_version_id,
        derived_from_revision_id,
        derived_from_snapshot_hash,
    )
    if all(value is None for value in values):
        return None, None, None
    if any(value is None for value in values):
        raise CharacterAuthoringInvariantError(
            "derived-version provenance must be entirely present or entirely null"
        )
    version_id = validate_identifier(derived_from_version_id, field="derived_from_version_id")
    revision_id = validate_identifier(
        derived_from_revision_id, field="derived_from_revision_id"
    )
    snapshot_hash = validate_snapshot_hash(
        derived_from_snapshot_hash, field="derived_from_snapshot_hash"
    )
    return version_id, revision_id, snapshot_hash
