"""Immutable human-approval evidence for exact Character Authoring revisions.

The evidence records who approved which exact immutable revision and when, at
the moment of the approval event. It is deliberately independent of the mutable
version pointer and carries no release, aggregate, package, or publication
identity.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .errors import CharacterAuthoringValidationError
from .validation import (
    validate_distinct_identities,
    validate_identifier,
    validate_snapshot_hash,
)

APPROVAL_EVIDENCE_SCHEMA_VERSION = "character_approval_evidence/1.0"
APPROVAL_DECISION_HUMAN_APPROVED = "HUMAN_APPROVED"

_DECIDED_AT_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
_DECIDED_AT_RE = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", re.ASCII
)
_EVIDENCE_FIELDS = {
    "schema_version",
    "character_id",
    "version_id",
    "revision_id",
    "snapshot_hash",
    "decision",
    "decided_by",
    "decided_at",
}

ApprovalClock = Callable[[], datetime]


def system_utc_clock() -> datetime:
    """Default approval clock: the current UTC instant."""

    return datetime.now(timezone.utc)


def validate_decided_by(value: object) -> str:
    """Return the supplied approver text unchanged, or fail closed.

    The value must be an explicitly supplied string that is non-empty after
    stripping and already NFC-normalized. It is never trimmed, normalized, or
    defaulted, and it is never inferred from the operating system or Git.
    """

    if not isinstance(value, str) or not value.strip():
        raise CharacterAuthoringValidationError(
            "decided_by: expected an explicitly supplied non-empty string"
        )
    if unicodedata.normalize("NFC", value) != value:
        raise CharacterAuthoringValidationError(
            "decided_by: expected NFC-normalized text"
        )
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise CharacterAuthoringValidationError(
            "decided_by: text is not valid Unicode"
        ) from exc
    return value


def validate_decided_at(value: object) -> str:
    """Accept only the single canonical ``YYYY-MM-DDTHH:MM:SSZ`` UTC form."""

    if not isinstance(value, str) or _DECIDED_AT_RE.fullmatch(value) is None:
        raise CharacterAuthoringValidationError(
            "decided_at: expected UTC timestamp form YYYY-MM-DDTHH:MM:SSZ"
        )
    try:
        datetime.strptime(value, _DECIDED_AT_FORMAT)
    except ValueError as exc:
        raise CharacterAuthoringValidationError(
            "decided_at: not a valid calendar date and time"
        ) from exc
    return value


def format_decided_at(moment: object) -> str:
    """Serialize a timezone-aware instant as canonical UTC ``decided_at``."""

    if not isinstance(moment, datetime) or moment.tzinfo is None:
        raise CharacterAuthoringValidationError(
            "approval clock must return a timezone-aware datetime"
        )
    utc = moment.astimezone(timezone.utc).replace(microsecond=0)
    return validate_decided_at(utc.strftime(_DECIDED_AT_FORMAT))


@dataclass(frozen=True)
class ApprovalEvidence:
    """One write-once approval event bound to an exact immutable revision."""

    character_id: str
    version_id: str
    revision_id: str
    snapshot_hash: str
    decided_by: str
    decided_at: str
    decision: str = APPROVAL_DECISION_HUMAN_APPROVED

    def __post_init__(self) -> None:
        validate_identifier(self.character_id, field="character_id")
        validate_identifier(self.version_id, field="version_id")
        validate_identifier(self.revision_id, field="revision_id")
        validate_snapshot_hash(self.snapshot_hash)
        validate_distinct_identities(
            self.character_id, self.version_id, self.revision_id, self.snapshot_hash
        )
        if self.decision != APPROVAL_DECISION_HUMAN_APPROVED:
            raise CharacterAuthoringValidationError(
                f"decision: expected {APPROVAL_DECISION_HUMAN_APPROVED!r}"
            )
        validate_decided_by(self.decided_by)
        validate_decided_at(self.decided_at)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": APPROVAL_EVIDENCE_SCHEMA_VERSION,
            "character_id": self.character_id,
            "version_id": self.version_id,
            "revision_id": self.revision_id,
            "snapshot_hash": self.snapshot_hash,
            "decision": self.decision,
            "decided_by": self.decided_by,
            "decided_at": self.decided_at,
        }

    @classmethod
    def from_dict(cls, data: object) -> "ApprovalEvidence":
        if not isinstance(data, dict):
            raise CharacterAuthoringValidationError(
                "approval evidence must be an object"
            )
        actual = set(data)
        if actual != _EVIDENCE_FIELDS:
            missing = sorted(_EVIDENCE_FIELDS - actual)
            extra = sorted(actual - _EVIDENCE_FIELDS)
            raise CharacterAuthoringValidationError(
                "approval evidence: schema keys differ; "
                f"missing={missing}, extra={extra}"
            )
        if data["schema_version"] != APPROVAL_EVIDENCE_SCHEMA_VERSION:
            raise CharacterAuthoringValidationError(
                "unsupported approval evidence schema"
            )
        return cls(
            character_id=data["character_id"],
            version_id=data["version_id"],
            revision_id=data["revision_id"],
            snapshot_hash=data["snapshot_hash"],
            decision=data["decision"],
            decided_by=data["decided_by"],
            decided_at=data["decided_at"],
        )
