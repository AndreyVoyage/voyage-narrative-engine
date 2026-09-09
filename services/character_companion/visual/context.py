#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""VisualContext -- the small, bounded, deterministic input to visual prompt
assembly.

Built ENTIRELY from Companion-local state: the active ``CharacterLocalSnapshot``
(identity/version), the ``CompanionScene`` fields, an optional explicit user
image description, and a bounded LINEAR conversation excerpt. No LLM, no
provider, no inference, no Character Canon, no Runtime causal memory, no
Character Package.

Conversation bound mirrors the existing product rule
``CompanionService._CONTEXT_EXCERPT_MAX`` (8): only the last <= 8 plain
USER/CHARACTER messages, chronological, no SYSTEM/tool/metadata. Presentation
("hidden") state is a UI concern and never independently filters the raw
history handed in here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence, Tuple

from ..character_import.local_snapshot import CharacterLocalSnapshot
from .errors import VisualContextError
from .hashing import content_hash

VISUAL_CONTEXT_SCHEMA_VERSION = "companion_visual_context/0.1"

REQUEST_KIND_CUSTOM = "custom"     # "Создать изображение..." -- explicit description
REQUEST_KIND_CONTEXT = "context"   # "Кадр по контексту" -- scene + bounded chat
_REQUEST_KINDS = (REQUEST_KIND_CUSTOM, REQUEST_KIND_CONTEXT)

#: Mirror of CompanionService._CONTEXT_EXCERPT_MAX. Do NOT diverge.
VISUAL_RECENT_MESSAGE_LIMIT = 8
#: Same cap the composer Writing Assistant uses for a single user draft.
MAX_DESCRIPTION_CHARS = 4000

_SCENE_FIELDS = ("place", "time", "situation", "mood", "freeform")
_MESSAGE_ROLES = ("user", "character")


def _clean_str(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


@dataclass(frozen=True)
class VisualMessage:
    role: str
    text: str

    def to_dict(self) -> dict:
        return {"role": self.role, "text": self.text}


@dataclass(frozen=True)
class VisualLocation:
    """Optional explicitly-rendered local location descriptor. An id/hash anchor
    alone is never enough -- the descriptive lists must be present to be used."""

    identity: Tuple[str, ...] = ()
    fixed_features: Tuple[str, ...] = ()
    palette: Tuple[str, ...] = ()
    location_id: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "identity", tuple(str(x).strip() for x in self.identity if str(x).strip()))
        object.__setattr__(self, "fixed_features", tuple(str(x).strip() for x in self.fixed_features if str(x).strip()))
        object.__setattr__(self, "palette", tuple(str(x).strip() for x in self.palette if str(x).strip()))

    def is_empty(self) -> bool:
        return not (self.identity or self.fixed_features or self.palette)

    def to_dict(self) -> dict:
        out: dict = {}
        if self.location_id:
            out["locationId"] = self.location_id
        if self.identity:
            out["identity"] = list(self.identity)
        if self.fixed_features:
            out["fixedFeatures"] = list(self.fixed_features)
        if self.palette:
            out["palette"] = list(self.palette)
        return out


@dataclass(frozen=True)
class VisualScene:
    place: str = ""
    time: str = ""
    situation: str = ""
    mood: str = ""
    freeform: str = ""
    location: Optional[VisualLocation] = None

    def is_empty(self) -> bool:
        text_empty = not any(getattr(self, f) for f in _SCENE_FIELDS)
        loc_empty = self.location is None or self.location.is_empty()
        return text_empty and loc_empty

    def to_dict(self) -> dict:
        out = {f: getattr(self, f) for f in _SCENE_FIELDS}
        if self.location is not None and not self.location.is_empty():
            out["location"] = self.location.to_dict()
        return out


@dataclass(frozen=True)
class VisualContext:
    schema_version: str
    character_id: str
    character_snapshot_version: str
    request_kind: str
    explicit_description: Optional[str]
    scene: Optional[VisualScene]
    recent_messages: Tuple[VisualMessage, ...]
    content_hash: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "recent_messages", tuple(self.recent_messages))

    def semantic_payload(self) -> dict:
        # No timestamps, no absolute paths, no hashes-not-needed-for-identity.
        return {
            "characterId": self.character_id,
            "characterSnapshotVersion": self.character_snapshot_version,
            "requestKind": self.request_kind,
            "explicitDescription": self.explicit_description,
            "scene": self.scene.to_dict() if self.scene is not None else None,
            "recentMessages": [m.to_dict() for m in self.recent_messages],
        }

    def compute_hash(self) -> str:
        return content_hash(self.semantic_payload())

    def to_dict(self) -> dict:
        return {
            "schemaVersion": self.schema_version,
            **self.semantic_payload(),
            "contentHash": self.content_hash or self.compute_hash(),
        }


def _coerce_message(item: Any) -> Optional[VisualMessage]:
    if isinstance(item, Mapping):
        role = _clean_str(item.get("role")).lower()
        text = _clean_str(item.get("text"))
    else:
        role = _clean_str(getattr(item, "role", "")).lower()
        text = _clean_str(getattr(item, "text", ""))
    if role not in _MESSAGE_ROLES or not text:
        return None
    return VisualMessage(role=role, text=text)


def _bounded_messages(raw: Optional[Sequence[Any]]) -> Tuple[VisualMessage, ...]:
    if not raw:
        return ()
    cleaned = [m for m in (_coerce_message(x) for x in raw) if m is not None]
    return tuple(cleaned[-VISUAL_RECENT_MESSAGE_LIMIT:])   # keep the newest <=8, chronological


def _scene_from(scene: Any, location: Any) -> Optional[VisualScene]:
    if scene is None:
        fields = {f: "" for f in _SCENE_FIELDS}
    elif isinstance(scene, Mapping):
        fields = {f: _clean_str(scene.get(f)) for f in _SCENE_FIELDS}
    elif hasattr(scene, "to_row"):
        row = scene.to_row()
        fields = {f: _clean_str(row.get(f)) for f in _SCENE_FIELDS}
    else:
        fields = {f: _clean_str(getattr(scene, f, "")) for f in _SCENE_FIELDS}

    loc: Optional[VisualLocation] = None
    if isinstance(location, Mapping):
        loc = VisualLocation(
            identity=tuple(location.get("identity") or ()),
            fixed_features=tuple(location.get("fixed_features") or location.get("fixedFeatures") or ()),
            palette=tuple(location.get("palette") or ()),
            location_id=_clean_str(location.get("location_id") or location.get("locationId")) or None,
        )
        if loc.is_empty():
            loc = None

    vs = VisualScene(**fields, location=loc)
    return None if vs.is_empty() else vs


def build_visual_context(
    *,
    snapshot: CharacterLocalSnapshot,
    request_kind: str,
    scene: Any = None,
    explicit_description: Optional[str] = None,
    recent_messages: Optional[Sequence[Any]] = None,
    location: Optional[Mapping[str, Any]] = None,
) -> VisualContext:
    """Assemble the bounded, deterministic VisualContext (offline, no LLM).

    * ``request_kind`` must be ``custom`` or ``context``.
    * ``custom``  -> ``explicit_description`` is required; ``recent_messages`` are
      dropped (V1 rule: a custom image is built from the explicit description).
    * ``context`` -> ``scene`` and/or the bounded recent conversation carry the
      intent; a description is optional.
    """
    if request_kind not in _REQUEST_KINDS:
        raise VisualContextError(f"request_kind must be one of {_REQUEST_KINDS}")
    if not isinstance(snapshot, CharacterLocalSnapshot):
        raise VisualContextError("snapshot must be a CharacterLocalSnapshot")

    desc = _clean_str(explicit_description) or None
    if desc is not None and len(desc) > MAX_DESCRIPTION_CHARS:
        raise VisualContextError(f"explicit_description exceeds {MAX_DESCRIPTION_CHARS} chars")

    vs = _scene_from(scene, location)

    if request_kind == REQUEST_KIND_CUSTOM:
        if desc is None:
            raise VisualContextError("a custom image request requires an explicit description")
        messages: Tuple[VisualMessage, ...] = ()
    else:  # context
        messages = _bounded_messages(recent_messages)
        if vs is None and not messages and desc is None:
            raise VisualContextError(
                "a context-frame request needs a scene, recent conversation, or a description"
            )

    ctx = VisualContext(
        schema_version=VISUAL_CONTEXT_SCHEMA_VERSION,
        character_id=snapshot.character_id,
        character_snapshot_version=snapshot.snapshot_version,
        request_kind=request_kind,
        explicit_description=desc,
        scene=vs,
        recent_messages=messages,
        content_hash="",
    )
    object.__setattr__(ctx, "content_hash", ctx.compute_hash())
    return ctx
