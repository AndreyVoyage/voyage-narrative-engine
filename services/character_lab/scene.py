#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Character Lab V1 Scene object (minimal, ratified).

A Scene is owner-authored *situational* input for a test. It is:

- session-scoped (and therefore workspace-scoped);
- mutable by the operator;
- NOT Accepted Package data;
- NOT runtime memory (no scene-event commit in V1).

Exactly six content fields are allowed. A Scene must NEVER carry emotions,
attraction, intent, decisions, chosen actions, or pre-scripted replies -- those
are model outputs, not inputs, and Character Lab does not synthesise them.

``render_scene_block`` produces the deterministic Russian system-prompt block
that ``BetaV1CurrentPolicy`` injects ONLY when a Scene is active. With no Scene,
Beta v1 provider context is byte-for-byte the historical behaviour.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional, Sequence

_ALLOWED_KEYS = frozenset(
    {"scene_id", "title", "location", "participants", "prior_events", "current_situation", "created_at"}
)


class SceneError(ValueError):
    """Fail-closed Scene validation error."""


@dataclass(frozen=True)
class Scene:
    """An immutable Scene snapshot. Six content fields, nothing more."""

    scene_id: str
    title: str
    location: str
    participants: tuple
    prior_events: tuple
    current_situation: str
    created_at: str

    def __post_init__(self) -> None:
        for name, value in (
            ("scene_id", self.scene_id),
            ("created_at", self.created_at),
        ):
            if not isinstance(value, str) or not value.strip():
                raise SceneError(f"{name} must be a non-empty string")
        for name, value in (
            ("title", self.title),
            ("location", self.location),
            ("current_situation", self.current_situation),
        ):
            if not isinstance(value, str):
                raise SceneError(f"{name} must be a string")
        if not isinstance(self.participants, tuple) or any(
            not isinstance(p, str) for p in self.participants
        ):
            raise SceneError("participants must be a tuple of strings")
        if not isinstance(self.prior_events, tuple) or any(
            not isinstance(e, str) for e in self.prior_events
        ):
            raise SceneError("prior_events must be a tuple of strings")


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _as_str_tuple(value: Any, field: str) -> tuple:
    """Accept a list/tuple of strings, or a newline/comma-delimited string."""
    if value is None:
        return ()
    if isinstance(value, str):
        parts = [p.strip() for chunk in value.split("\n") for p in chunk.split(",")]
        return tuple(p for p in parts if p)
    if isinstance(value, Sequence):
        out = []
        for item in value:
            if not isinstance(item, str):
                raise SceneError(f"{field} entries must be strings")
            item = item.strip()
            if item:
                out.append(item)
        return tuple(out)
    raise SceneError(f"{field} must be a list of strings or a delimited string")


def new_scene(
    *,
    title: str = "",
    location: str = "",
    participants: Any = (),
    prior_events: Any = (),
    current_situation: str = "",
    scene_id: Optional[str] = None,
    created_at: Optional[str] = None,
) -> Scene:
    """Build a Scene from raw operator input (strings or lists)."""
    return Scene(
        scene_id=scene_id or f"scene-{uuid.uuid4().hex}",
        title=str(title or "").strip(),
        location=str(location or "").strip(),
        participants=_as_str_tuple(participants, "participants"),
        prior_events=_as_str_tuple(prior_events, "prior_events"),
        current_situation=str(current_situation or "").strip(),
        created_at=created_at or _now_iso(),
    )


def scene_to_jsonable(scene: Scene) -> dict:
    return {
        "scene_id": scene.scene_id,
        "title": scene.title,
        "location": scene.location,
        "participants": list(scene.participants),
        "prior_events": list(scene.prior_events),
        "current_situation": scene.current_situation,
        "created_at": scene.created_at,
    }


def scene_from_jsonable(data: Any) -> Scene:
    if not isinstance(data, dict):
        raise SceneError("scene must be an object")
    unknown = set(data.keys()) - _ALLOWED_KEYS
    if unknown:
        raise SceneError(f"scene has unknown field(s): {sorted(unknown)}")
    return Scene(
        scene_id=data["scene_id"],
        title=data.get("title", ""),
        location=data.get("location", ""),
        participants=tuple(data.get("participants") or ()),
        prior_events=tuple(data.get("prior_events") or ()),
        current_situation=data.get("current_situation", ""),
        created_at=data["created_at"],
    )


def scene_hash(scene: Scene) -> str:
    """Deterministic SHA-256 over canonical Scene content (for reproducibility)."""
    payload = scene_to_jsonable(scene)
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def render_scene_block(scene: Scene) -> str:
    """The deterministic Russian СЦЕНА system block.

    Pure projection of operator-supplied text. It does NOT add "Кира
    чувствует / хочет / решает" statements -- only what the owner typed.
    """
    participants = ", ".join(scene.participants) if scene.participants else "—"
    if scene.prior_events:
        prior = "\n".join(f"- {e}" for e in scene.prior_events)
    else:
        prior = "—"
    return (
        "СЦЕНА\n"
        f"Название: {scene.title}\n"
        f"Место: {scene.location}\n"
        f"Участники: {participants}\n"
        "Предыдущие события:\n"
        f"{prior}\n"
        "Текущая ситуация:\n"
        f"{scene.current_situation}"
    )
