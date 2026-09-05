#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OrderedASS (ass/0.2) -- the ordered canonical accepted-scene contract.

OrderedASS is the SAME canonical Accepted Scene contract concept as the legacy
``ASS`` (ass/0.1), carrying the same accepted envelope plus a complete
``ordered_flow`` instead of the legacy ``ordered_beats`` payload. It is NOT a
second canonical artifact kind.

It reuses the immutable SceneBody entry/option/target value types verbatim
(``services.scene_body.model``) as the ordered flow payload: the values are
frozen/deeply immutable, there is only one semantic payload shape, and
incomplete authoring values are blocked by acceptance-completeness validation
before construction. No independently editable duplicate payload classes are
created here.

``build_ordered_ass`` deterministically projects a complete SceneBody into an
OrderedASS without semantic loss. It never calls the legacy ``import_scene``
and never produces a Scenario V2 intermediate representation.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, Optional, Tuple

from services.scene_body.model import (
    AUTHORING_SCHEMA_VERSION,
    ChoiceEntry,
    Entry,
    SceneBody,
    TextEntry,
    VisualChangeEvent,
)
from services.scene_body.validation import validate_acceptance_complete

from .errors import ASSInvariantError
from .hashing import compute_content_hash
from .model import (
    LocationStateOverride,
    Participant,
    Provenance,
)

ORDERED_ASS_SCHEMA_VERSION = "ass/0.2"

# Provenance source kind for the ordered acceptance path (SceneBody -> OrderedASS).
SOURCE_KIND_ORDERED_ACCEPT = "scene_body_ordered_acceptance"

_ORDERED_FLOW_ENTRY_TYPES = (TextEntry, ChoiceEntry, VisualChangeEvent)


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _to_plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _to_plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_plain(item) for item in value]
    return value


def _require_non_empty(value: Optional[str], field: str) -> str:
    if not isinstance(value, str) or value.strip() == "":
        raise ASSInvariantError(f"{field}: required non-empty string")
    return value


@dataclasses.dataclass(frozen=True)
class OrderedASS:
    """The immutable ordered accepted-scene snapshot (ass/0.2).

    ``ordered_flow`` is the complete, acceptance-valid ordered entry flow
    (reusing SceneBody entry value types). An ass/0.2 object without a complete
    ordered flow is impossible to construct.
    """

    schema_version: str
    ass_id: str
    version: int
    scene_id: str
    location_id: str
    participants: Tuple[Participant, ...]
    ordered_flow: Tuple[Entry, ...]
    content_rating: str
    provenance: Provenance
    content_hash: str
    scene_title: Optional[str] = None
    character_state_overrides: Optional[dict[str, dict[str, Any]]] = None
    location_state_overrides: Optional[Tuple[LocationStateOverride, ...]] = None
    supersedes: Optional[str] = None
    created_at: Optional[str] = None
    author: Optional[str] = None

    def __post_init__(self) -> None:
        if self.schema_version != ORDERED_ASS_SCHEMA_VERSION:
            raise ASSInvariantError(
                f"OrderedASS schema_version {self.schema_version!r} unsupported; "
                f"expected {ORDERED_ASS_SCHEMA_VERSION!r}"
            )
        object.__setattr__(self, "participants", tuple(self.participants))
        flow = tuple(self.ordered_flow)
        if len(flow) == 0:
            raise ASSInvariantError("OrderedASS requires a complete non-empty ordered_flow")
        for entry in flow:
            if not isinstance(entry, _ORDERED_FLOW_ENTRY_TYPES):
                raise ASSInvariantError("ordered_flow contains an unrecognized entry type")
        object.__setattr__(self, "ordered_flow", flow)
        if self.location_state_overrides is not None:
            object.__setattr__(self, "location_state_overrides", tuple(self.location_state_overrides))
        if self.character_state_overrides is not None:
            object.__setattr__(self, "character_state_overrides", _freeze(self.character_state_overrides))

    def semantic_payload(self) -> dict[str, Any]:
        """Return exactly the hashed semantic payload (complete accepted state)."""
        payload: dict[str, Any] = {
            "schema_version": self.schema_version,
            "scene_id": self.scene_id,
            "location_id": self.location_id,
            "participants": [p.to_dict() for p in self.participants],
            "ordered_flow": [e.to_dict() for e in self.ordered_flow],
            "content_rating": self.content_rating,
        }
        if self.scene_title is not None:
            payload["scene_title"] = self.scene_title
        if self.character_state_overrides is not None:
            payload["character_state_overrides"] = _to_plain(self.character_state_overrides)
        if self.location_state_overrides is not None:
            payload["location_state_overrides"] = [
                o.to_dict() for o in self.location_state_overrides
            ]
        return payload

    def to_dict(self) -> dict[str, Any]:
        """Return the full OrderedASS envelope (hashed + non-hashed fields)."""
        result: dict[str, Any] = {
            "schema_version": self.schema_version,
            "ass_id": self.ass_id,
            "version": self.version,
            "scene_id": self.scene_id,
            "location_id": self.location_id,
            "participants": [p.to_dict() for p in self.participants],
            "ordered_flow": [e.to_dict() for e in self.ordered_flow],
            "content_rating": self.content_rating,
            "provenance": self.provenance.to_dict(),
            "content_hash": self.content_hash,
        }
        if self.scene_title is not None:
            result["scene_title"] = self.scene_title
        if self.character_state_overrides is not None:
            result["character_state_overrides"] = _to_plain(self.character_state_overrides)
        if self.location_state_overrides is not None:
            result["location_state_overrides"] = [
                o.to_dict() for o in self.location_state_overrides
            ]
        if self.supersedes is not None:
            result["supersedes"] = self.supersedes
        if self.created_at is not None:
            result["created_at"] = self.created_at
        if self.author is not None:
            result["author"] = self.author
        return result


def build_ordered_ass(
    body: SceneBody,
    *,
    ass_id: str,
    version: int,
    source_ref: str,
    source_hash: str,
    supersedes: Optional[str] = None,
    created_at: Optional[str] = None,
    author: Optional[str] = None,
) -> OrderedASS:
    """Deterministically project a complete SceneBody into an OrderedASS.

    - location comes from ``SceneBody.location_id`` (authoritative);
    - participants are normalized deterministically to accepted ASS values;
    - ordered flow reuses the immutable SceneBody entry values verbatim;
    - provenance records the source schema ``scene_body/1.0`` and binds its
      source hash to the SceneVersion authored ``content_hash``.

    Fails closed (before any OrderedASS is constructed) if the body is not
    acceptance-complete.
    """
    if not isinstance(body, SceneBody):
        raise ASSInvariantError("body: expected SceneBody")

    errors = validate_acceptance_complete(body)
    if errors:
        raise ASSInvariantError(f"SceneBody is not acceptance-complete: {errors[0]}")

    ass_id = _require_non_empty(ass_id, "ass_id")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise ASSInvariantError("version: expected integer >= 1")
    source_ref = _require_non_empty(source_ref, "source_ref")
    source_hash = _require_non_empty(source_hash, "source_hash")

    location_id = _require_non_empty(body.location_id, "body.location_id")
    content_rating = _require_non_empty(body.content_rating, "body.content_rating")

    participants = tuple(
        Participant(character_id=p.character_id, role=p.role, present=p.present)
        for p in body.participants
    )

    ordered_flow = tuple(body.entries)

    character_state_overrides = (
        _to_plain(body.character_state_overrides)
        if body.character_state_overrides is not None
        else None
    )
    location_state_overrides = (
        tuple(
            LocationStateOverride(predicate=o.predicate, value=_to_plain(o.value))
            for o in body.location_state_overrides
        )
        if body.location_state_overrides is not None
        else None
    )

    provenance = Provenance(
        source_kind=SOURCE_KIND_ORDERED_ACCEPT,
        source_ref=source_ref,
        source_hash=source_hash,
        source_schema_version=AUTHORING_SCHEMA_VERSION,
    )

    provisional = OrderedASS(
        schema_version=ORDERED_ASS_SCHEMA_VERSION,
        ass_id=ass_id,
        version=version,
        scene_id=body.scene_id,
        location_id=location_id,
        participants=participants,
        ordered_flow=ordered_flow,
        content_rating=content_rating,
        provenance=provenance,
        content_hash="",
        scene_title=body.scene_title,
        character_state_overrides=character_state_overrides,
        location_state_overrides=location_state_overrides,
        supersedes=supersedes,
        created_at=created_at,
        author=author,
    )
    content_hash = compute_content_hash(provisional.semantic_payload())
    return dataclasses.replace(provisional, content_hash=content_hash)
