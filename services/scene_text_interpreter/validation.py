#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scene Text Interpreter v0 -- deterministic validator + still selector.

This module is the trust boundary. It takes an UNTRUSTED
``ProposedInterpretation`` plus the closed ``InterpreterInput`` and returns a
frozen, grounded ``SceneStillPlan`` -- or fails closed.

Independent checks (never trusting the proposal because its JSON parsed):

- confidence must be "high" (OWNER_DECISION #4);
- no unresolved items;
- every character span is a verbatim substring of the source AND resolves,
  through the VNE-owned alias table, to the proposed character_id;
- exactly two distinct in-frame characters (OWNER_DECISION #6);
- one location: span grounded, resolves to the proposed id, exists in
  Location Canon, and the source mentions no other location;
- every scene tag is in the controlled v0 vocabulary and is not the location;
- every beat span/phrase is grounded; every beat actor is a resolved character;
- a contact beat needs an explicit grounded positioning phrase and is barred
  from still candidacy (hard safety filter);
- still candidates are re-scored deterministically with the preflight rubric;
  the winner is the highest score (tie-break: beat index, span length,
  lexical). The winning score must clear the v0 threshold, else fail closed;
- the chosen still's composed visual goal must not name a non-frame character.

No chain-of-thought is read or stored. Evidence is source substrings only.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any, Mapping

from services.location_canon import LocationCanonError, load_location

from .aliases import resolve_character, resolve_location
from .errors import (
    CharacterCountError,
    ConfidenceError,
    GroundingError,
    HallucinationError,
    LocationResolutionError,
    SceneTagError,
    StillSelectionError,
    UnresolvedItemsError,
)
from .hashing import canonical_source, compute_content_hash, match_key, source_text_hash
from .model import (
    CONFIDENCE_HIGH,
    DRAFT_STATUS,
    STILL_PLAN_SCHEMA_VERSION,
    AllowedCharacter,
    ChosenStill,
    InterpreterInput,
    PlanBeat,
    ProposedInterpretation,
    SceneStillPlan,
    StillCandidate,
)
from .vocab import is_allowed_scene_tag

# --- Still scoring rubric (preflight-fixed; do not redesign) -----------------

_STILL_SCORE_THRESHOLD = 3

_STATIC_MARKERS = (
    # ru stems
    "лежит", "лёжа", "лежа", "стоит", "стоя", "сидит", "сидя", "растяж",
    "наблюда", "смотр", "гляд", "держ", "тянет", "тянется", "опира", "склон",
    "на колен", "присел", "присев",
    # en
    "lie", "lying", "lies", "stand", "standing", "stands", "sit", "sitting",
    "stretch", "watch", "observ", "look", "gaze", "hold", "kneel", "lean",
    "reach", "rest",
)

_TRANSIENT_MARKERS = (
    # ru stems
    "поворачива", "поверн", "разворачива", "встаёт", "встает", "вставая",
    "подходит", "подойд", "идёт", "идет", "бежит", "прыга", "падает",
    "уходит", "входит", "затем", "после чего", "снова",
    # en
    "turn", "spin", "jump", "fall", "walk", "run", "enter", "leave", "step",
    "approach", "rise", "stand up", "then ", "again",
)


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    key = match_key(text)
    return any(m in key for m in markers)


def _is_static(action_phrase: str) -> bool:
    return _contains_any(action_phrase, _STATIC_MARKERS)


def _is_transient(*texts: str | None) -> bool:
    return any(t is not None and _contains_any(t, _TRANSIENT_MARKERS) for t in texts)


def _score_beat(beat: PlanBeat, frame: tuple[str, ...], *, has_location: bool) -> int:
    actors = set(beat.actor_character_ids)
    score = 0
    if set(frame) <= actors:
        score += 2
    elif len(actors) <= 1:
        score -= 1
    if _is_static(beat.action_phrase):
        score += 2
    if _is_transient(beat.text_span, beat.action_phrase):
        score -= 2
    if beat.gaze_phrase:
        score += 1
    if has_location:
        score += 1
    if beat.contact_flag:
        score -= 3
    return score


def _rationale_tags(beat: PlanBeat, frame: tuple[str, ...], *, has_location: bool) -> tuple[str, ...]:
    tags: list[str] = []
    actors = set(beat.actor_character_ids)
    if set(frame) <= actors:
        tags.append("both_characters_present")
    elif len(actors) <= 1:
        tags.append("single_character_only")
    if _is_static(beat.action_phrase):
        tags.append("static_pose")
    if _is_transient(beat.text_span, beat.action_phrase):
        tags.append("requires_temporal_context")
    if beat.gaze_phrase:
        tags.append("mutual_gaze")
    if has_location:
        tags.append("scene_cue_present")
    if beat.contact_flag:
        tags.append("contact_ambiguity")
    return tuple(tags)


# --- Grounding helpers ------------------------------------------------------


def _require_grounded(span: str | None, source_key: str, label: str) -> None:
    if span is None:
        return
    if match_key(span) not in source_key:
        raise GroundingError(f"{label}: {span!r} is not a verbatim substring of the source")


# --- Public entry point ---------------------------------------------------------


def validate_and_build_plan(
    proposal: ProposedInterpretation,
    inp: InterpreterInput,
    *,
    repo_root: Path,
    interpreter_meta: Mapping[str, Any],
) -> SceneStillPlan:
    """Validate an untrusted proposal into a frozen, grounded SceneStillPlan."""
    source_canon = canonical_source(inp.raw_scene_text)
    source_key = match_key(inp.raw_scene_text)
    src_hash = source_text_hash(inp.raw_scene_text)
    if not source_canon:
        raise GroundingError("source text is empty after normalization")

    # 1. Confidence + unresolved gates (fail closed).
    if proposal.confidence != CONFIDENCE_HIGH:
        raise ConfidenceError(
            f"proposer confidence is {proposal.confidence!r}; v0 requires "
            f"{CONFIDENCE_HIGH!r}"
        )
    if proposal.unresolved_items:
        raise UnresolvedItemsError(
            f"proposal left items unresolved: {list(proposal.unresolved_items)}"
        )

    roster_by_id: dict[str, AllowedCharacter] = {
        c.character_id: c for c in inp.allowed_characters
    }

    # 2. Characters: ground each span, resolve via alias table, cross-check id.
    resolved_spans: dict[str, list[str]] = {}
    first_pos: dict[str, int] = {}
    for pc in proposal.characters:
        span_ids: set[str] = set()
        for span in pc.source_spans:
            span_key = match_key(span)
            if span_key not in source_key:
                raise GroundingError(
                    f"character span {span!r} is not a verbatim substring of the source"
                )
            resolved = resolve_character(span, inp.allowed_characters)
            if resolved is None:
                raise HallucinationError(
                    f"character span {span!r} does not resolve to exactly one allowed "
                    f"character"
                )
            span_ids.add(resolved)
        if len(span_ids) != 1:
            raise HallucinationError(
                f"character {pc.character_id!r} spans resolve inconsistently: "
                f"{sorted(span_ids)}"
            )
        resolved_id = next(iter(span_ids))
        if resolved_id != pc.character_id:
            raise HallucinationError(
                f"proposed character_id {pc.character_id!r} != alias-resolved "
                f"{resolved_id!r}"
            )
        if resolved_id not in roster_by_id:
            raise HallucinationError(
                f"character {resolved_id!r} is outside the allowed roster"
            )
        if resolved_id in resolved_spans:
            raise HallucinationError(f"duplicate character {resolved_id!r} in proposal")
        resolved_spans[resolved_id] = list(pc.source_spans)
        first_pos[resolved_id] = min(source_key.index(match_key(s)) for s in pc.source_spans)

    n_chars = len(resolved_spans)
    if not (inp.min_characters_in_frame <= n_chars <= inp.max_characters_in_frame):
        raise CharacterCountError(
            f"v0 requires between {inp.min_characters_in_frame} and "
            f"{inp.max_characters_in_frame} in-frame characters; grounded {n_chars}"
        )
    characters_in_frame = tuple(sorted(resolved_spans, key=lambda c: first_pos[c]))

    # 3. Location: ground span, resolve, verify Location Canon, no other location.
    if not proposal.location_id or not proposal.location_span:
        raise LocationResolutionError("proposal did not provide a grounded location")
    _require_grounded(proposal.location_span, source_key, "location_span")
    resolved_location = resolve_location(
        source_match_key=source_key,
        location_span=proposal.location_span,
        roster=inp.allowed_locations,
    )
    if resolved_location != proposal.location_id:
        raise HallucinationError(
            f"proposed location_id {proposal.location_id!r} != alias-resolved "
            f"{resolved_location!r}"
        )
    try:
        load_location(Path(repo_root), resolved_location)
    except LocationCanonError as exc:
        raise LocationResolutionError(
            f"location {resolved_location!r} does not resolve against Location Canon: {exc}"
        ) from exc

    # 4. Scene tags: controlled vocabulary only; never the location id.
    scene_tags: list[str] = []
    for tag in proposal.scene_tags:
        if not is_allowed_scene_tag(tag):
            raise SceneTagError(
                f"scene tag {tag!r} is outside the controlled v0 vocabulary "
                f"{list(inp.allowed_scene_tags)}"
            )
        if tag == resolved_location:
            raise SceneTagError(
                f"scene tag {tag!r} duplicates the resolved location id; the AUTO "
                f"selector already prepends the location"
            )
        if tag not in scene_tags:
            scene_tags.append(tag)
    if not scene_tags:
        raise SceneTagError("proposal produced no valid scene tags")

    # 5. Beats: ground every span/phrase; every actor must be a resolved char.
    plan_beats: list[PlanBeat] = []
    for beat in proposal.beats:
        ctx = f"beat[{beat.index}]"
        _require_grounded(beat.text_span, source_key, f"{ctx}.text_span")
        _require_grounded(beat.action_phrase, source_key, f"{ctx}.action_phrase")
        _require_grounded(beat.gaze_phrase, source_key, f"{ctx}.gaze_phrase")
        _require_grounded(beat.positioning_phrase, source_key, f"{ctx}.positioning_phrase")
        for actor in beat.actor_character_ids:
            if actor not in resolved_spans:
                raise HallucinationError(
                    f"{ctx} actor {actor!r} is not a grounded in-frame character"
                )
        if beat.contact_flag and not beat.positioning_phrase:
            raise HallucinationError(
                f"{ctx} sets contact_flag without a grounded positioning phrase"
            )
        plan_beats.append(
            PlanBeat(
                index=beat.index,
                text_span=beat.text_span,
                actor_character_ids=tuple(beat.actor_character_ids),
                action_phrase=beat.action_phrase,
                gaze_phrase=beat.gaze_phrase,
                positioning_phrase=beat.positioning_phrase,
                contact_flag=beat.contact_flag,
            )
        )
    beats_by_index = {b.index: b for b in plan_beats}

    # 6. Still candidates: deterministic re-scoring + hard safety filter.
    ranked: list[tuple[int, int, int, Any]] = []
    for cand in proposal.still_candidates:
        if cand.beat_index not in beats_by_index:
            raise StillSelectionError(
                f"still candidate beat_index {cand.beat_index} is not a proposed beat"
            )
        beat = beats_by_index[cand.beat_index]
        if beat.contact_flag:
            # Hard filter: a contact beat can never be the chosen still.
            continue
        score = _score_beat(beat, characters_in_frame, has_location=True)
        ranked.append((score, beat.index, len(beat.text_span), cand))
    if not ranked:
        raise StillSelectionError(
            "no safe still candidate (every candidate was filtered or ungrounded)"
        )
    ranked.sort(key=lambda t: (-t[0], t[1], t[2], t[3].visual_goal_text))
    top = ranked[: inp.still_candidate_count]
    best_score, best_index, _best_len, best_cand = top[0]
    if best_score < _STILL_SCORE_THRESHOLD:
        raise StillSelectionError(
            f"best still candidate score {best_score} is below the v0 threshold "
            f"{_STILL_SCORE_THRESHOLD}; no clear single-frame moment"
        )

    # 7. Composed visual goal must not introduce a non-frame character.
    goal_key = match_key(best_cand.visual_goal_text)
    for entry in inp.allowed_characters:
        if entry.character_id in characters_in_frame:
            continue
        for alias in (entry.provider_alias, *entry.surface_aliases):
            if match_key(alias) in goal_key:
                raise HallucinationError(
                    f"chosen still visual goal names non-frame character "
                    f"{entry.character_id!r} (via {alias!r})"
                )

    still_candidates = tuple(
        StillCandidate(
            beat_index=cand.beat_index,
            score=score,
            rationale_tags=_rationale_tags(
                beats_by_index[cand.beat_index], characters_in_frame, has_location=True
            ),
        )
        for (score, _idx, _ln, cand) in top
    )
    chosen_still = ChosenStill(
        beat_index=best_index, visual_goal=best_cand.visual_goal_text
    )

    evidence = {
        "character_spans": {
            cid: list(resolved_spans[cid]) for cid in characters_in_frame
        },
        "location_span": proposal.location_span,
        "chosen_still_beat_span": beats_by_index[best_index].text_span,
    }
    interpreter = dict(interpreter_meta)
    interpreter.setdefault("source_language", proposal.source_language)

    provisional = SceneStillPlan(
        schema_version=STILL_PLAN_SCHEMA_VERSION,
        status=DRAFT_STATUS,
        source_text_hash=src_hash,
        characters_in_frame=characters_in_frame,
        provider_alias_by_character={
            cid: roster_by_id[cid].provider_alias for cid in characters_in_frame
        },
        location_id=resolved_location,
        scene_tags=tuple(scene_tags),
        beats=tuple(plan_beats),
        still_candidates=still_candidates,
        chosen_still=chosen_still,
        evidence=evidence,
        unresolved_items=(),
        interpreter=interpreter,
        content_hash="",
    )
    return dataclasses.replace(
        provisional, content_hash=compute_content_hash(provisional.semantic_payload())
    )
