#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scene Editor domain lifecycle -- plain-data models.

``SceneVersion`` is the authoring/history artifact, NOT the downstream accepted
contract. ASS (``services.ass``) remains canonical for accepted scenes.

Models are ``@dataclass(frozen=True)`` and hold only detached, **deeply
immutable** plain data. The authored ``body`` is recursively frozen to
``types.MappingProxyType`` (mappings) and ``tuple`` (sequences) at construction
time, so a caller can neither mutate a SceneVersion through a retained input
reference nor through the object itself. ``body_plain()``/``to_dict()`` always
return **freshly-allocated** plain JSON-compatible data (no aliases).

``content_hash`` is computed in ``__post_init__`` from the frozen authored body
and is therefore deterministic and unaffected by acceptance lifecycle metadata.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Optional

from tools.narrative_schema_v2 import validate_scene

from .errors import (
    SceneIdMismatchError,
    SceneInvariantError,
    SceneValidationError,
)
from .hashing import compute_authored_body_hash

LIFECYCLE_DRAFT = "DRAFT"
LIFECYCLE_ACCEPTED = "ACCEPTED"
LIFECYCLES = (LIFECYCLE_DRAFT, LIFECYCLE_ACCEPTED)


def _freeze(value: Any) -> Any:
    """Deeply convert a value into an immutable representation.

    Mirrors ``services/ass/model.py``: dict/Mapping -> MappingProxyType of
    recursively-frozen values; list/tuple -> tuple of recursively-frozen items.
    A fresh dict is built first, severing any caller alias.
    """
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _to_plain(value: Any) -> Any:
    """Deeply convert a (possibly frozen) value into fresh plain data.

    Always allocates new dicts/lists; the result shares no storage with internal
    SceneVersion state and can never mutate it.
    """
    if isinstance(value, Mapping):
        return {key: _to_plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_plain(item) for item in value]
    return value


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
    - ``body`` passes the existing unmodified ``validate_scene``;
    - ``body["id"]`` exactly equals ``scene_id``;
    - ``content_hash`` is derived deterministically from the authored body only.
    """

    scene_id: str
    version: int
    lifecycle: str
    body: Any
    acceptance: Optional[AcceptanceLink] = None
    content_hash: str = field(init=False, default="")

    def __post_init__(self) -> None:
        if not isinstance(self.version, int) or isinstance(self.version, bool) or self.version < 1:
            raise SceneInvariantError("version: expected positive integer")

        if self.lifecycle not in LIFECYCLES:
            raise SceneInvariantError(f"lifecycle: expected one of {LIFECYCLES!r}")

        if not isinstance(self.body, dict):
            raise SceneValidationError("body: expected object")

        errors, _warnings = validate_scene(self.body)
        if errors:
            raise SceneValidationError(f"body failed validation: {errors[0]}")

        body_id = self.body.get("id")
        if body_id != self.scene_id:
            raise SceneIdMismatchError(
                f"scene_id {self.scene_id!r} does not equal body id {body_id!r}"
            )

        if self.lifecycle == LIFECYCLE_DRAFT:
            if self.acceptance is not None:
                raise SceneInvariantError("DRAFT SceneVersion must have acceptance None")
        else:  # ACCEPTED
            if self.acceptance is None:
                raise SceneInvariantError("ACCEPTED SceneVersion requires an AcceptanceLink")
            if not isinstance(self.acceptance, AcceptanceLink):
                raise SceneInvariantError("acceptance must be an AcceptanceLink")

        frozen_body = _freeze(self.body)
        object.__setattr__(self, "body", frozen_body)
        object.__setattr__(self, "content_hash", compute_authored_body_hash(_to_plain(frozen_body)))

    def body_plain(self) -> dict[str, Any]:
        """Return a fresh plain dict/list copy of the authored body (no aliases)."""
        return _to_plain(self.body)

    def to_dict(self) -> dict[str, Any]:
        """Return the full persisted record as fresh plain JSON-compatible data."""
        return {
            "scene_id": self.scene_id,
            "version": self.version,
            "lifecycle": self.lifecycle,
            "body": _to_plain(self.body),
            "content_hash": self.content_hash,
            "acceptance": self.acceptance.to_dict() if self.acceptance is not None else None,
        }

    @classmethod
    def from_dict(cls, data: Any) -> "SceneVersion":
        """Build a SceneVersion from persisted plain dict data.

        ``__post_init__`` re-validates the body, re-checks ``scene_id``, and
        recomputes ``content_hash``. Callers that also need to verify a stored
        ``content_hash`` compare it against ``result.content_hash``.
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
