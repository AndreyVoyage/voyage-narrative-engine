#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scene Text Interpreter v0 -- persisted plan replay loader.

``load_scene_still_plan`` reads a previously emitted ``SceneStillPlan`` JSON
(``vne_scene_still_plan/0.1``, status ``DRAFT``), strictly deserializes it,
RECOMPUTES and verifies ``content_hash`` (fail closed on a tampered file), then
re-checks the invariants needed to safely bridge to the existing Profile:

- exactly two in-frame characters, no duplicate ids;
- every character id is an allowed VNE character and its provider alias
  matches the VNE-owned roster;
- ``location_id`` is an allowed location AND resolves against Location Canon;
- every scene tag is in the controlled v0 vocabulary and is not the location;
- ``unresolved_items`` is empty;
- ``chosen_still`` is present and points at a real plan beat;
- every still candidate points at a real plan beat.

No LLM, no network, no proposer instantiation. A malformed / tampered / stale
plan fails closed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from services.location_canon import LocationCanonError, load_location

from .aliases import load_character_roster, load_location_roster
from .errors import PlanLoadError
from .model import SceneStillPlan
from .vocab import is_allowed_scene_tag

_V0_CHARACTERS_IN_FRAME = 2


def load_scene_still_plan(path: Path, *, repo_root: Path) -> SceneStillPlan:
    """Load + integrity-check + bridge-revalidate a persisted SceneStillPlan."""
    p = Path(path)
    try:
        data: Any = json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise PlanLoadError(f"plan file not found: {p}") from None
    except Exception as exc:  # noqa: BLE001 - fail closed with a clean message
        raise PlanLoadError(f"cannot read plan file: {exc}") from None

    # Structural parse + content_hash recompute/verify.
    plan = SceneStillPlan.from_dict(data)

    # --- Bridge invariants against VNE-owned data (deterministic) ---
    roster = load_character_roster(Path(repo_root))
    roster_by_id = {c.character_id: c for c in roster}

    if len(plan.characters_in_frame) != _V0_CHARACTERS_IN_FRAME:
        raise PlanLoadError(
            f"plan must have exactly {_V0_CHARACTERS_IN_FRAME} characters_in_frame "
            f"for v0; got {len(plan.characters_in_frame)}"
        )
    for cid in plan.characters_in_frame:
        if cid not in roster_by_id:
            raise PlanLoadError(
                f"plan character {cid!r} is not an allowed VNE character"
            )
        expected_alias = roster_by_id[cid].provider_alias
        if plan.provider_alias_by_character.get(cid) != expected_alias:
            raise PlanLoadError(
                f"plan provider_alias for {cid!r} does not match the VNE roster"
            )

    allowed_locations = {l.location_id for l in load_location_roster(Path(repo_root))}
    if plan.location_id not in allowed_locations:
        raise PlanLoadError(
            f"plan location_id {plan.location_id!r} is not an allowed location"
        )
    try:
        load_location(Path(repo_root), plan.location_id)
    except LocationCanonError as exc:
        raise PlanLoadError(
            f"plan location_id {plan.location_id!r} does not resolve against "
            f"Location Canon: {exc}"
        ) from None

    for tag in plan.scene_tags:
        if not is_allowed_scene_tag(tag):
            raise PlanLoadError(
                f"plan scene tag {tag!r} is outside the controlled v0 vocabulary"
            )
        if tag == plan.location_id:
            raise PlanLoadError(
                "plan scene_tags must not duplicate the location id"
            )

    if plan.unresolved_items:
        raise PlanLoadError(
            f"plan has unresolved items: {list(plan.unresolved_items)}"
        )

    if not plan.chosen_still or not plan.chosen_still.visual_goal.strip():
        raise PlanLoadError("plan chosen_still is missing or empty")

    beat_indices = {b.index for b in plan.beats}
    if plan.chosen_still.beat_index not in beat_indices:
        raise PlanLoadError(
            "plan chosen_still.beat_index does not refer to a plan beat"
        )
    for cand in plan.still_candidates:
        if cand.beat_index not in beat_indices:
            raise PlanLoadError(
                f"plan still_candidate beat_index {cand.beat_index} is not a plan beat"
            )

    return plan
