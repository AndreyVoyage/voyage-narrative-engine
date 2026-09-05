#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scene Editor domain lifecycle -- plain-data models.

``SceneVersion`` is the authoring/history artifact, NOT the downstream accepted
contract. ASS (``services.ass``) remains canonical for accepted scenes. The
authored ``body`` is now a ``SceneBody`` (``services/scene_body``), the single
authoritative ordered body; a plain dict input is converted via
``SceneBody.from_dict`` for the existing store boundary.

Models are ``@dataclass(frozen=True)`` and hold only detached, deeply immutable
plain data (``SceneBody`` itself is deeply frozen at its own construction).
``body_plain()``/``to_dict()`` always return freshly-allocated plain data (no
aliases).

``content_hash`` is computed in ``__post_init__`` from the canonical SceneBody
(including its explicit nulls / ordered entries) and is therefore deterministic
and unaffected by acceptance lifecycle metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from services.scene_body import SceneBody, SceneBodyError

from .errors import (
    SceneIdMismatchError,
    SceneInvariantError,
    SceneValidationError,
)
from .hashing import compute_authored_body_hash

LIFECYCLE_DRAFT = "DRAFT"
LIFECYCLE_ACCEPTED = "ACCEPTED"
LIFECYCLES = (LIFECYCLE_DRAFT, LIFECYCLE_ACCEPTED)


def _require_non_empty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or value == "":
        raise SceneValidationError(f"{field}: required non-empty string")
    return value


@dataclass(frozen=True)
class AcceptanceLink:
    """The link from an ACCEPTED SceneVersion to its exact ASS.

    Only the ASS identity and its content hash are retained; ASS itself remains
    the canonical accepted-scene contract and is never duplicated here.
    """

    ass_id: str
    ass_content_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "ass_id", _require_non_empty_string(self.ass_id, "ass_id"))
        object.__setattr__(
            self,
            "ass_content_hash",
            _require_non_empty_string(self.ass_content_hash, "ass_content_hash"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {"ass_id": self.ass_id, "ass_content_hash": self.ass_content_hash}

    @classmethod
    def from_dict(cls, data: Any) -> "AcceptanceLink":
        if not isinstance(data, dict):
            raise SceneValidationError("acceptance must be an object")
        return cls(ass_id=data.get("ass_id"), ass_content_hash=data.get("ass_content_hash"))


@dataclass(frozen=True)
class SceneVersion:
    """One persisted authored version of a scene.

    Required invariants (enforced in ``__post_init__``):

    - ``version`` is a positive integer;
    - ``lifecycle`` is exactly ``DRAFT`` or ``ACCEPTED``;
    - DRAFT implies ``acceptance is None``; ACCEPTED implies a valid link;
    - ``body`` is a valid ``SceneBody`` (a plain dict input is converted);
    - ``SceneVersion.scene_id`` exactly equals ``SceneBody.scene_id``;
    - ``content_hash`` is derived deterministically from the canonical SceneBody
      (including explicit nulls and ordered entries) only.
    """

    scene_id: str
    version: int
    lifecycle: str
    body: Any  # SceneBody, or a plain dict converted via SceneBody.from_dict
    acceptance: Optional[AcceptanceLink] = None
    content_hash: str = field(init=False, default="")

    def __post_init__(self) -> None:
        if not isinstance(self.version, int) or isinstance(self.version, bool) or self.version < 1:
            raise SceneInvariantError("version: expected positive integer")

        if self.lifecycle not in LIFECYCLES:
            raise SceneInvariantError(f"lifecycle: expected one of {LIFECYCLES!r}")

        body = self.body
        if isinstance(body, SceneBody):
            normalized = body
        elif isinstance(body, dict):
            try:
                normalized = SceneBody.from_dict(body)
            except SceneBodyError as exc:
                raise SceneValidationError(f"body failed validation: {exc}") from exc
        else:
            raise SceneValidationError("body: expected SceneBody or object")
        object.__setattr__(self, "body", normalized)

        if normalized.scene_id != self.scene_id:
            raise SceneIdMismatchError(
                f"scene_id {self.scene_id!r} does not equal SceneBody scene_id "
                f"{normalized.scene_id!r}"
            )

        if self.lifecycle == LIFECYCLE_DRAFT:
            if self.acceptance is not None:
                raise SceneInvariantError("DRAFT SceneVersion must have acceptance None")
        else:  # ACCEPTED
            if self.acceptance is None:
                raise SceneInvariantError("ACCEPTED SceneVersion requires an AcceptanceLink")
            if not isinstance(self.acceptance, AcceptanceLink):
                raise SceneInvariantError("acceptance must be an AcceptanceLink")

        object.__setattr__(self, "content_hash", compute_authored_body_hash(normalized.to_dict()))

    def body_plain(self) -> dict[str, Any]:
        """Return a fresh plain dict copy of the authored SceneBody (no aliases)."""
        return self.body.to_dict()

    def to_dict(self) -> dict[str, Any]:
        """Return the full persisted record as fresh plain JSON-compatible data."""
        return {
            "scene_id": self.scene_id,
            "version": self.version,
            "lifecycle": self.lifecycle,
            "body": self.body.to_dict(),
            "content_hash": self.content_hash,
            "acceptance": self.acceptance.to_dict() if self.acceptance is not None else None,
        }

    @classmethod
    def from_dict(cls, data: Any) -> "SceneVersion":
        """Build a SceneVersion from persisted plain dict data.

        ``__post_init__`` re-validates the SceneBody, re-checks ``scene_id``,
        and recomputes ``content_hash``. Callers that also need to verify a
        stored ``content_hash`` compare it against ``result.content_hash``.
        """
        if not isinstance(data, dict):
            raise SceneValidationError("record must be an object")

        scene_id = data.get("scene_id")
        if not isinstance(scene_id, str) or scene_id == "":
            raise SceneValidationError("scene_id: required non-empty string")

        acceptance = data.get("acceptance")
        if acceptance is not None:
            acceptance = AcceptanceLink.from_dict(acceptance)

        return cls(
            scene_id=scene_id,
            version=data.get("version"),
            lifecycle=data.get("lifecycle"),
            body=data.get("body"),
            acceptance=acceptance,
        )
