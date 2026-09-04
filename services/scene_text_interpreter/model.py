#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scene Text Interpreter v0 -- plain-data models.

Three layers, deliberately separated:

A. ``InterpreterInput``       -- the closed allowlists handed to the proposer.
B. ``ProposedInterpretation`` -- the UNTRUSTED proposal (parsed, not trusted).
C. ``SceneStillPlan``         -- the DETERMINISTICALLY VALIDATED, frozen output.

The plan is an AUTHORING / DRAFT artifact. It is NOT an accepted ASS and never
mutates one. ``status`` is a frozen ``"DRAFT"`` literal to make that explicit.

Immutability mirrors the ASS / Scene Interpretation convention: frozen
dataclasses, recursive ``MappingProxyType`` / ``tuple`` freezing, and a
fresh-plain ``to_dict`` / ``semantic_payload``. Stdlib only; no provider import.
"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Optional, Tuple

from .errors import PlanLoadError, ProposalSchemaError
from .hashing import compute_content_hash

_HEX64 = re.compile(r"^[0-9a-f]{64}$")

STILL_PLAN_SCHEMA_VERSION = "vne_scene_still_plan/0.1"
PROPOSAL_SCHEMA_VERSION = "vne_scene_text_proposal/0.1"
DRAFT_STATUS = "DRAFT"

CONFIDENCE_HIGH = "high"
CONFIDENCE_LOW = "low"


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({k: _freeze(v) for k, v in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(v) for v in value)
    return value


def _to_plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {k: _to_plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_plain(v) for v in value]
    return value


# ---------------------------------------------------------------------------
# A. Interpreter input (closed allowlists).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AllowedCharacter:
    character_id: str
    provider_alias: str
    surface_aliases: Tuple[str, ...]


@dataclass(frozen=True)
class AllowedLocation:
    location_id: str
    surface_aliases: Tuple[str, ...]


@dataclass(frozen=True)
class InterpreterInput:
    raw_scene_text: str
    allowed_characters: Tuple[AllowedCharacter, ...]
    allowed_locations: Tuple[AllowedLocation, ...]
    allowed_scene_tags: Tuple[str, ...]
    min_characters_in_frame: int = 2
    max_characters_in_frame: int = 2
    still_candidate_count: int = 3

    def allowed_character_ids(self) -> Tuple[str, ...]:
        return tuple(c.character_id for c in self.allowed_characters)

    def allowed_location_ids(self) -> Tuple[str, ...]:
        return tuple(l.location_id for l in self.allowed_locations)


# ---------------------------------------------------------------------------
# B. Untrusted proposal.
# ---------------------------------------------------------------------------


def _req_str(data: Mapping[str, Any], key: str, ctx: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ProposalSchemaError(f"{ctx}.{key}: required non-empty string")
    return value


def _opt_str(data: Mapping[str, Any], key: str, ctx: str) -> Optional[str]:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ProposalSchemaError(f"{ctx}.{key}: must be a non-empty string or null")
    return value


def _str_tuple(data: Mapping[str, Any], key: str, ctx: str, *, required: bool) -> Tuple[str, ...]:
    value = data.get(key)
    if value is None and not required:
        return ()
    if not isinstance(value, list) or (required and not value):
        raise ProposalSchemaError(
            f"{ctx}.{key}: required non-empty array of strings"
            if required
            else f"{ctx}.{key}: must be an array of strings"
        )
    out: list[str] = []
    for i, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise ProposalSchemaError(f"{ctx}.{key}[{i}]: expected non-empty string")
        out.append(item)
    return tuple(out)


@dataclass(frozen=True)
class ProposedCharacter:
    character_id: str
    source_spans: Tuple[str, ...]

    @staticmethod
    def from_dict(data: Any, ctx: str) -> "ProposedCharacter":
        if not isinstance(data, Mapping):
            raise ProposalSchemaError(f"{ctx}: expected object")
        return ProposedCharacter(
            character_id=_req_str(data, "character_id", ctx),
            source_spans=_str_tuple(data, "source_spans", ctx, required=True),
        )


@dataclass(frozen=True)
class ProposedBeat:
    index: int
    text_span: str
    actor_character_ids: Tuple[str, ...]
    action_phrase: str
    gaze_phrase: Optional[str] = None
    positioning_phrase: Optional[str] = None
    contact_flag: bool = False

    @staticmethod
    def from_dict(data: Any, ctx: str) -> "ProposedBeat":
        if not isinstance(data, Mapping):
            raise ProposalSchemaError(f"{ctx}: expected object")
        index = data.get("index")
        if not isinstance(index, int) or isinstance(index, bool) or index < 0:
            raise ProposalSchemaError(f"{ctx}.index: expected non-negative integer")
        contact = data.get("contact_flag", False)
        if not isinstance(contact, bool):
            raise ProposalSchemaError(f"{ctx}.contact_flag: expected boolean")
        return ProposedBeat(
            index=index,
            text_span=_req_str(data, "text_span", ctx),
            actor_character_ids=_str_tuple(data, "actor_character_ids", ctx, required=True),
            action_phrase=_req_str(data, "action_phrase", ctx),
            gaze_phrase=_opt_str(data, "gaze_phrase", ctx),
            positioning_phrase=_opt_str(data, "positioning_phrase", ctx),
            contact_flag=contact,
        )


@dataclass(frozen=True)
class ProposedStillCandidate:
    beat_index: int
    rationale_tags: Tuple[str, ...]
    visual_goal_text: str

    @staticmethod
    def from_dict(data: Any, ctx: str) -> "ProposedStillCandidate":
        if not isinstance(data, Mapping):
            raise ProposalSchemaError(f"{ctx}: expected object")
        beat_index = data.get("beat_index")
        if not isinstance(beat_index, int) or isinstance(beat_index, bool) or beat_index < 0:
            raise ProposalSchemaError(f"{ctx}.beat_index: expected non-negative integer")
        return ProposedStillCandidate(
            beat_index=beat_index,
            rationale_tags=_str_tuple(data, "rationale_tags", ctx, required=False),
            visual_goal_text=_req_str(data, "visual_goal_text", ctx),
        )


@dataclass(frozen=True)
class ProposedInterpretation:
    """The untrusted structured proposal. Parsing here enforces SHAPE only;
    every semantic claim is re-verified by the deterministic validator."""

    characters: Tuple[ProposedCharacter, ...]
    location_id: Optional[str]
    location_span: Optional[str]
    beats: Tuple[ProposedBeat, ...]
    scene_tags: Tuple[str, ...]
    still_candidates: Tuple[ProposedStillCandidate, ...]
    confidence: str
    unresolved_items: Tuple[str, ...] = ()
    source_language: Optional[str] = None

    @staticmethod
    def from_dict(data: Any) -> "ProposedInterpretation":
        if not isinstance(data, Mapping):
            raise ProposalSchemaError("proposal: expected object")

        chars_raw = data.get("characters")
        if not isinstance(chars_raw, list) or not chars_raw:
            raise ProposalSchemaError("proposal.characters: required non-empty array")
        characters = tuple(
            ProposedCharacter.from_dict(c, f"proposal.characters[{i}]")
            for i, c in enumerate(chars_raw)
        )

        beats_raw = data.get("beats")
        if not isinstance(beats_raw, list) or not beats_raw:
            raise ProposalSchemaError("proposal.beats: required non-empty array")
        beats = tuple(
            ProposedBeat.from_dict(b, f"proposal.beats[{i}]") for i, b in enumerate(beats_raw)
        )
        if len({b.index for b in beats}) != len(beats):
            raise ProposalSchemaError("proposal.beats: duplicate beat index")

        cands_raw = data.get("still_candidates")
        if not isinstance(cands_raw, list) or not cands_raw:
            raise ProposalSchemaError(
                "proposal.still_candidates: required non-empty array"
            )
        still_candidates = tuple(
            ProposedStillCandidate.from_dict(c, f"proposal.still_candidates[{i}]")
            for i, c in enumerate(cands_raw)
        )

        confidence = data.get("confidence")
        if confidence not in (CONFIDENCE_HIGH, CONFIDENCE_LOW):
            raise ProposalSchemaError(
                f"proposal.confidence: expected {CONFIDENCE_HIGH!r} or {CONFIDENCE_LOW!r}"
            )

        location_id = _opt_str(data, "location_id", "proposal")
        location_span = _opt_str(data, "location_span", "proposal")

        return ProposedInterpretation(
            characters=characters,
            location_id=location_id,
            location_span=location_span,
            beats=beats,
            scene_tags=_str_tuple(data, "scene_tags", "proposal", required=False),
            still_candidates=still_candidates,
            confidence=confidence,
            unresolved_items=_str_tuple(data, "unresolved_items", "proposal", required=False),
            source_language=_opt_str(data, "source_language", "proposal"),
        )


# ---------------------------------------------------------------------------
# C. Validated output artifact.
# ---------------------------------------------------------------------------


def _plan_req(data: Mapping[str, Any], key: str) -> Any:
    if not isinstance(data, Mapping) or key not in data:
        raise PlanLoadError(f"plan.{key}: required field missing")
    return data[key]


def _plan_str(data: Mapping[str, Any], key: str, ctx: str = "plan") -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise PlanLoadError(f"{ctx}.{key}: required non-empty string")
    return value


def _plan_opt_str(data: Mapping[str, Any], key: str, ctx: str) -> Optional[str]:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise PlanLoadError(f"{ctx}.{key}: must be a non-empty string or null")
    return value


def _plan_int(data: Mapping[str, Any], key: str, ctx: str) -> int:
    value = data.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise PlanLoadError(f"{ctx}.{key}: expected integer")
    return value


def _plan_str_list(value: Any, ctx: str) -> Tuple[str, ...]:
    if not isinstance(value, list) or not all(
        isinstance(x, str) and x for x in value
    ):
        raise PlanLoadError(f"{ctx}: expected a list of non-empty strings")
    return tuple(value)


@dataclass(frozen=True)
class PlanBeat:
    index: int
    text_span: str
    actor_character_ids: Tuple[str, ...]
    action_phrase: str
    gaze_phrase: Optional[str]
    positioning_phrase: Optional[str]
    contact_flag: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "text_span": self.text_span,
            "actor_character_ids": list(self.actor_character_ids),
            "action_phrase": self.action_phrase,
            "gaze_phrase": self.gaze_phrase,
            "positioning_phrase": self.positioning_phrase,
            "contact_flag": self.contact_flag,
        }


@dataclass(frozen=True)
class StillCandidate:
    beat_index: int
    score: int
    rationale_tags: Tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "beat_index": self.beat_index,
            "score": self.score,
            "rationale_tags": list(self.rationale_tags),
        }


@dataclass(frozen=True)
class ChosenStill:
    beat_index: int
    visual_goal: str

    def to_dict(self) -> dict[str, Any]:
        return {"beat_index": self.beat_index, "visual_goal": self.visual_goal}


@dataclass(frozen=True)
class SceneStillPlan:
    """Deterministically validated, frozen DRAFT still plan.

    Every string field is grounded in the submitted source text or drawn from a
    closed allowlist. ``status`` is always ``"DRAFT"`` -- this artifact never
    represents accepted scene state.
    """

    schema_version: str
    status: str
    source_text_hash: str
    characters_in_frame: Tuple[str, ...]
    provider_alias_by_character: Mapping[str, str]
    location_id: str
    scene_tags: Tuple[str, ...]
    beats: Tuple[PlanBeat, ...]
    still_candidates: Tuple[StillCandidate, ...]
    chosen_still: ChosenStill
    evidence: Mapping[str, Any]
    unresolved_items: Tuple[str, ...]
    interpreter: Mapping[str, Any]
    content_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "characters_in_frame", tuple(self.characters_in_frame))
        object.__setattr__(
            self, "provider_alias_by_character", _freeze(self.provider_alias_by_character)
        )
        object.__setattr__(self, "scene_tags", tuple(self.scene_tags))
        object.__setattr__(self, "beats", tuple(self.beats))
        object.__setattr__(self, "still_candidates", tuple(self.still_candidates))
        object.__setattr__(self, "evidence", _freeze(self.evidence))
        object.__setattr__(self, "unresolved_items", tuple(self.unresolved_items))
        object.__setattr__(self, "interpreter", _freeze(self.interpreter))

    def semantic_payload(self) -> dict[str, Any]:
        """Exactly the hashed content. Envelope/provenance
        (``schema_version``, ``status``, ``content_hash``, ``interpreter``) is
        excluded so provenance metadata never changes plan identity."""
        return {
            "source_text_hash": self.source_text_hash,
            "characters_in_frame": list(self.characters_in_frame),
            "provider_alias_by_character": _to_plain(self.provider_alias_by_character),
            "location_id": self.location_id,
            "scene_tags": list(self.scene_tags),
            "beats": [b.to_dict() for b in self.beats],
            "still_candidates": [c.to_dict() for c in self.still_candidates],
            "chosen_still": self.chosen_still.to_dict(),
            "evidence": _to_plain(self.evidence),
            "unresolved_items": list(self.unresolved_items),
        }

    def to_dict(self) -> dict[str, Any]:
        """Full artifact envelope as fresh plain data (deterministic JSON)."""
        payload = self.semantic_payload()
        payload.update(
            {
                "schema_version": self.schema_version,
                "status": self.status,
                "content_hash": self.content_hash,
                "interpreter": _to_plain(self.interpreter),
            }
        )
        return payload

    @staticmethod
    def from_dict(data: Any) -> "SceneStillPlan":
        """Strictly deserialize a persisted plan and VERIFY its content_hash.

        Enforces schema version and ``DRAFT`` status, parses every serialized
        field, then recomputes ``content_hash`` from the reconstructed semantic
        payload and rejects any mismatch (fail closed on a tampered file). This
        is pure structural + integrity validation -- the caller still applies
        the VNE-owned bridge invariants (roster / Location Canon / vocab).
        """
        if not isinstance(data, Mapping):
            raise PlanLoadError("plan: expected a JSON object")
        if data.get("schema_version") != STILL_PLAN_SCHEMA_VERSION:
            raise PlanLoadError(
                f"plan.schema_version must be {STILL_PLAN_SCHEMA_VERSION!r}"
            )
        if data.get("status") != DRAFT_STATUS:
            raise PlanLoadError(f"plan.status must be {DRAFT_STATUS!r}")

        source_text_hash = _plan_str(data, "source_text_hash")
        if not _HEX64.match(source_text_hash):
            raise PlanLoadError("plan.source_text_hash must be 64 lowercase hex chars")

        characters_in_frame = _plan_str_list(
            _plan_req(data, "characters_in_frame"), "plan.characters_in_frame"
        )
        if len(set(characters_in_frame)) != len(characters_in_frame):
            raise PlanLoadError("plan.characters_in_frame contains duplicate ids")

        pab_raw = _plan_req(data, "provider_alias_by_character")
        if not isinstance(pab_raw, Mapping) or not all(
            isinstance(k, str) and k and isinstance(v, str) and v
            for k, v in pab_raw.items()
        ):
            raise PlanLoadError(
                "plan.provider_alias_by_character must be a non-empty str->str map"
            )
        if set(pab_raw) != set(characters_in_frame):
            raise PlanLoadError(
                "plan.provider_alias_by_character keys must equal characters_in_frame"
            )

        location_id = _plan_str(data, "location_id")
        scene_tags = _plan_str_list(_plan_req(data, "scene_tags"), "plan.scene_tags")

        beats_raw = _plan_req(data, "beats")
        if not isinstance(beats_raw, list) or not beats_raw:
            raise PlanLoadError("plan.beats: expected a non-empty array")
        beats: list[PlanBeat] = []
        for i, b in enumerate(beats_raw):
            ctx = f"plan.beats[{i}]"
            if not isinstance(b, Mapping):
                raise PlanLoadError(f"{ctx}: expected object")
            contact = b.get("contact_flag", False)
            if not isinstance(contact, bool):
                raise PlanLoadError(f"{ctx}.contact_flag: expected boolean")
            beats.append(
                PlanBeat(
                    index=_plan_int(b, "index", ctx),
                    text_span=_plan_str(b, "text_span", ctx),
                    actor_character_ids=_plan_str_list(
                        b.get("actor_character_ids"), f"{ctx}.actor_character_ids"
                    ),
                    action_phrase=_plan_str(b, "action_phrase", ctx),
                    gaze_phrase=_plan_opt_str(b, "gaze_phrase", ctx),
                    positioning_phrase=_plan_opt_str(b, "positioning_phrase", ctx),
                    contact_flag=contact,
                )
            )
        if len({b.index for b in beats}) != len(beats):
            raise PlanLoadError("plan.beats: duplicate beat index")

        cands_raw = _plan_req(data, "still_candidates")
        if not isinstance(cands_raw, list) or not cands_raw:
            raise PlanLoadError("plan.still_candidates: expected a non-empty array")
        still_candidates: list[StillCandidate] = []
        for i, c in enumerate(cands_raw):
            ctx = f"plan.still_candidates[{i}]"
            if not isinstance(c, Mapping):
                raise PlanLoadError(f"{ctx}: expected object")
            still_candidates.append(
                StillCandidate(
                    beat_index=_plan_int(c, "beat_index", ctx),
                    score=_plan_int(c, "score", ctx),
                    rationale_tags=_plan_str_list(
                        c.get("rationale_tags", []), f"{ctx}.rationale_tags"
                    ),
                )
            )

        chosen_raw = _plan_req(data, "chosen_still")
        if not isinstance(chosen_raw, Mapping):
            raise PlanLoadError("plan.chosen_still: expected object")
        chosen_still = ChosenStill(
            beat_index=_plan_int(chosen_raw, "beat_index", "plan.chosen_still"),
            visual_goal=_plan_str(chosen_raw, "visual_goal", "plan.chosen_still"),
        )

        evidence = _plan_req(data, "evidence")
        if not isinstance(evidence, Mapping) or not isinstance(
            evidence.get("character_spans"), Mapping
        ):
            raise PlanLoadError(
                "plan.evidence must be an object with a character_spans object"
            )

        unresolved_raw = data.get("unresolved_items", [])
        if not isinstance(unresolved_raw, list) or not all(
            isinstance(x, str) for x in unresolved_raw
        ):
            raise PlanLoadError("plan.unresolved_items must be a list of strings")

        interpreter = data.get("interpreter", {})
        if not isinstance(interpreter, Mapping):
            raise PlanLoadError("plan.interpreter must be an object")

        stored_hash = data.get("content_hash")
        if not isinstance(stored_hash, str) or not _HEX64.match(stored_hash):
            raise PlanLoadError("plan.content_hash must be 64 lowercase hex chars")

        provisional = SceneStillPlan(
            schema_version=STILL_PLAN_SCHEMA_VERSION,
            status=DRAFT_STATUS,
            source_text_hash=source_text_hash,
            characters_in_frame=characters_in_frame,
            provider_alias_by_character=dict(pab_raw),
            location_id=location_id,
            scene_tags=scene_tags,
            beats=tuple(beats),
            still_candidates=tuple(still_candidates),
            chosen_still=chosen_still,
            evidence=_to_plain(evidence),
            unresolved_items=tuple(unresolved_raw),
            interpreter=_to_plain(interpreter),
            content_hash="",
        )
        recomputed = compute_content_hash(provisional.semantic_payload())
        if recomputed != stored_hash:
            raise PlanLoadError(
                f"plan.content_hash mismatch: stored {stored_hash}, "
                f"recomputed {recomputed} (plan is malformed or tampered)"
            )
        return dataclasses.replace(provisional, content_hash=recomputed)
