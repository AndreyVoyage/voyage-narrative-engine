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

Additive claim layer (SCENE EPISTEMIC CLAIMS V1): ``SceneEpistemicClaim`` is an
author-defined claim-level fact attached ``рядом с`` the free-form Scene via the
``SceneWithClaims`` subtype. The base ``Scene`` keeps EXACTLY its six content
fields; free-form scene text is NEVER auto-converted into epistemic facts --
only explicitly authored claims are, via ``scene_epistemic_bridge``.
"""

from __future__ import annotations

import hashlib
import json
import math
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional, Sequence

from services.character_core.epistemics import EpistemicKind, is_holder_addressable

_ALLOWED_KEYS = frozenset(
    {"scene_id", "title", "location", "participants", "prior_events", "current_situation", "created_at"}
)

_CLAIM_ALLOWED_KEYS = frozenset(
    {
        "claim_id", "meaning", "epistemic_kind", "provenance", "perceiver_ids",
        "valid_from_seq", "valid_to_seq", "confidence", "holder_id",
    }
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


@dataclass(frozen=True)
class SceneEpistemicClaim:
    """One author-defined claim-level epistemic fact attached to a Scene.

    Unlike the free-form Scene text (pure situational prose), a claim carries
    explicit epistemic metadata so it can be projected into an
    ``EpistemicEnvelope`` and pass through the SAME Character Core visibility
    selector as every other epistemic input. Nothing here decides visibility:
    ``perceiver_ids`` / ``valid_from_seq`` / ``valid_to_seq`` are only carried;
    Character Core evaluates them.

    Validation is fail-closed and mirrors the Core envelope contract so a
    malformed claim is rejected at authoring time, not mid-turn.
    """

    claim_id: str
    meaning: str
    epistemic_kind: Any  # EpistemicKind or its string value; coerced below
    provenance: str
    perceiver_ids: tuple = ()
    valid_from_seq: Optional[int] = None
    valid_to_seq: Optional[int] = None
    confidence: float = 1.0
    holder_id: Optional[str] = None

    def __post_init__(self) -> None:
        for name, value in (
            ("claim_id", self.claim_id),
            ("meaning", self.meaning),
            ("provenance", self.provenance),
        ):
            if not isinstance(value, str) or not value.strip():
                raise SceneError(f"{name} must be a non-empty string")

        kind = self.epistemic_kind
        if isinstance(kind, str):
            try:
                kind = EpistemicKind(kind.strip())
            except ValueError:
                kind = None
        if not isinstance(kind, EpistemicKind):
            raise SceneError(
                f"epistemic_kind must be one of {[k.value for k in EpistemicKind]}, "
                f"got {self.epistemic_kind!r}"
            )
        object.__setattr__(self, "epistemic_kind", kind)

        if isinstance(self.perceiver_ids, str) or not isinstance(self.perceiver_ids, tuple):
            raise SceneError("perceiver_ids must be a tuple of strings")
        seen: set = set()
        for pid in self.perceiver_ids:
            if not isinstance(pid, str) or not pid.strip():
                raise SceneError("each perceiver id must be a non-empty string")
            if pid in seen:
                raise SceneError(f"duplicate perceiver id: {pid!r}")
            seen.add(pid)

        for name, value in (
            ("valid_from_seq", self.valid_from_seq),
            ("valid_to_seq", self.valid_to_seq),
        ):
            if value is not None and (isinstance(value, bool) or not isinstance(value, int)):
                raise SceneError(f"{name} must be an int or None")
        if (
            self.valid_from_seq is not None
            and self.valid_to_seq is not None
            and self.valid_to_seq < self.valid_from_seq
        ):
            raise SceneError("valid_to_seq must be >= valid_from_seq")

        conf = self.confidence
        if isinstance(conf, bool) or not isinstance(conf, (int, float)):
            raise SceneError("confidence must be a real number")
        conf = float(conf)
        if math.isnan(conf) or math.isinf(conf):
            raise SceneError("confidence must be a finite number")
        if not (0.0 <= conf <= 1.0):
            raise SceneError("confidence must be within [0.0, 1.0] inclusive")
        object.__setattr__(self, "confidence", conf)

        if self.holder_id is not None and (
            not isinstance(self.holder_id, str) or not self.holder_id.strip()
        ):
            raise SceneError("holder_id (when supplied) must be a non-empty string")
        if is_holder_addressable(kind) and self.holder_id is None:
            raise SceneError(
                f"{kind.value} requires a holder_id -- it is defined as belonging to a subject"
            )


@dataclass(frozen=True)
class SceneWithClaims(Scene):
    """A Scene plus author-defined claim-level epistemic facts.

    Purely additive: it IS a ``Scene`` (same six content fields, same
    rendering, same validation) and additionally carries
    ``epistemic_claims``. The base ``Scene`` type is deliberately left
    untouched so every existing ``Scene(...)`` construction and the exact
    free-form behaviour stay unchanged.
    """

    epistemic_claims: tuple = ()

    def __post_init__(self) -> None:
        super().__post_init__()
        if not isinstance(self.epistemic_claims, tuple) or any(
            not isinstance(c, SceneEpistemicClaim) for c in self.epistemic_claims
        ):
            raise SceneError("epistemic_claims must be a tuple of SceneEpistemicClaim")


def with_epistemic_claims(scene: Scene, claims: Any) -> SceneWithClaims:
    """Return a ``SceneWithClaims`` copy of ``scene`` carrying ``claims``.

    The scene content is preserved field-for-field; only the claim layer is
    attached. Free-form text is never reinterpreted.
    """
    if not isinstance(scene, Scene):
        raise SceneError("scene must be a Scene")
    if isinstance(claims, (str, bytes)) or not isinstance(claims, Sequence):
        raise SceneError("claims must be a sequence of SceneEpistemicClaim")
    return SceneWithClaims(
        scene_id=scene.scene_id,
        title=scene.title,
        location=scene.location,
        participants=scene.participants,
        prior_events=scene.prior_events,
        current_situation=scene.current_situation,
        created_at=scene.created_at,
        epistemic_claims=tuple(claims),
    )


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


def scene_claim_to_jsonable(claim: SceneEpistemicClaim) -> dict:
    if not isinstance(claim, SceneEpistemicClaim):
        raise SceneError("claim must be a SceneEpistemicClaim")
    return {
        "claim_id": claim.claim_id,
        "meaning": claim.meaning,
        "epistemic_kind": claim.epistemic_kind.value,
        "provenance": claim.provenance,
        "perceiver_ids": list(claim.perceiver_ids),
        "valid_from_seq": claim.valid_from_seq,
        "valid_to_seq": claim.valid_to_seq,
        "confidence": claim.confidence,
        "holder_id": claim.holder_id,
    }


def scene_claim_from_jsonable(data: Any) -> SceneEpistemicClaim:
    if not isinstance(data, dict):
        raise SceneError("scene claim must be an object")
    unknown = set(data.keys()) - _CLAIM_ALLOWED_KEYS
    if unknown:
        raise SceneError(f"scene claim has unknown field(s): {sorted(unknown)}")
    return SceneEpistemicClaim(
        claim_id=data["claim_id"],
        meaning=data["meaning"],
        epistemic_kind=data["epistemic_kind"],
        provenance=data["provenance"],
        perceiver_ids=tuple(data.get("perceiver_ids") or ()),
        valid_from_seq=data.get("valid_from_seq"),
        valid_to_seq=data.get("valid_to_seq"),
        confidence=data.get("confidence", 1.0),
        holder_id=data.get("holder_id"),
    )


def scene_to_jsonable(scene: Scene) -> dict:
    payload = {
        "scene_id": scene.scene_id,
        "title": scene.title,
        "location": scene.location,
        "participants": list(scene.participants),
        "prior_events": list(scene.prior_events),
        "current_situation": scene.current_situation,
        "created_at": scene.created_at,
    }
    # Additive: the claims key appears ONLY when claims exist, so the jsonable
    # form (and therefore ``scene_hash``) of a claim-less Scene is unchanged.
    claims = getattr(scene, "epistemic_claims", ()) or ()
    if claims:
        payload["epistemic_claims"] = [scene_claim_to_jsonable(c) for c in claims]
    return payload


def scene_from_jsonable(data: Any) -> Scene:
    if not isinstance(data, dict):
        raise SceneError("scene must be an object")
    unknown = set(data.keys()) - (_ALLOWED_KEYS | {"epistemic_claims"})
    if unknown:
        raise SceneError(f"scene has unknown field(s): {sorted(unknown)}")
    base = {
        "scene_id": data["scene_id"],
        "title": data.get("title", ""),
        "location": data.get("location", ""),
        "participants": tuple(data.get("participants") or ()),
        "prior_events": tuple(data.get("prior_events") or ()),
        "current_situation": data.get("current_situation", ""),
        "created_at": data["created_at"],
    }
    claims_data = data.get("epistemic_claims") or ()
    if claims_data:
        return SceneWithClaims(
            **base,
            epistemic_claims=tuple(scene_claim_from_jsonable(c) for c in claims_data),
        )
    return Scene(**base)


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
