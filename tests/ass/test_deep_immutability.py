#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deep-immutability regression tests for ASS v0.

These directly reproduce the integration-review MAJOR: a caller must not be
able to alter ASS semantic content (nor invalidate the stored content_hash)
via a retained input reference, via the ASS object, or via the plain data
returned by semantic_payload()/to_dict().
"""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest

from services.ass import compute_content_hash, import_scene


def _import(
    source: dict[str, Any],
    *,
    ass_id: str = "ass_test_1",
    version: int = 1,
    location_id: str = "yoga_hall",
    source_ref: str = "scenarios/SCENARIO_017_SERGEY_WRITES_AGAIN.v2.json",
    **kwargs,
):
    return import_scene(
        source,
        ass_id=ass_id,
        version=version,
        location_id=location_id,
        source_ref=source_ref,
        **kwargs,
    )


# --------------------------------------------------------------------------
# A. external character_state_overrides alias mutation does not change ASS
# --------------------------------------------------------------------------


def test_external_character_override_alias_protected(synthetic_sc029_source):
    overrides = {"alice": {"clothing": "sports top + leggings"}}
    ass = _import(synthetic_sc029_source, character_state_overrides=overrides)
    stored = ass.content_hash

    overrides["alice"]["clothing"] = "changed by caller"

    assert ass.character_state_overrides["alice"]["clothing"] == "sports top + leggings"
    assert compute_content_hash(ass.semantic_payload()) == stored


# --------------------------------------------------------------------------
# B. external accepted_states alias mutation does not change Beat.accepted_state
# --------------------------------------------------------------------------


def test_external_accepted_state_alias_protected(synthetic_sc029_source):
    accepted = {"b1": {"emotion": {"primary": "anxious", "signals": ["tense"]}}}
    ass = _import(synthetic_sc029_source, accepted_states=accepted)
    stored = ass.content_hash
    b1 = next(b for b in ass.ordered_beats if b.beat_id == "b1")

    accepted["b1"]["emotion"]["signals"].append("watchful")
    accepted["b1"]["emotion"]["primary"] = "calm"

    assert b1.accepted_state["emotion"]["primary"] == "anxious"
    assert b1.accepted_state["emotion"]["signals"] == ("tense",)
    assert compute_content_hash(ass.semantic_payload()) == stored


# --------------------------------------------------------------------------
# C. external location_state_overrides alias mutation does not change ASS
# --------------------------------------------------------------------------


def test_external_location_override_alias_protected(synthetic_sc029_source):
    overrides = [{"predicate": "lights", "value": "off"}]
    ass = _import(synthetic_sc029_source, location_state_overrides=overrides)
    stored = ass.content_hash

    overrides[0]["value"] = "on"

    assert ass.location_state_overrides[0].value == "off"
    assert compute_content_hash(ass.semantic_payload()) == stored


# --------------------------------------------------------------------------
# D. mutate nested character_state_overrides through ASS is rejected
# --------------------------------------------------------------------------


def test_mutation_through_ass_character_state_blocked(synthetic_sc029_source):
    ass = _import(
        synthetic_sc029_source,
        character_state_overrides={"alice": {"clothing": "sports top"}},
    )
    with pytest.raises(TypeError):
        ass.character_state_overrides["alice"]["clothing"] = "changed"  # type: ignore[index]


# --------------------------------------------------------------------------
# E. mutate Beat.accepted_state through ASS is rejected
# --------------------------------------------------------------------------


def test_mutation_through_beat_accepted_state_blocked(synthetic_sc029_source):
    ass = _import(synthetic_sc029_source, accepted_states={"b1": {"emotion": "focused"}})
    b1 = next(b for b in ass.ordered_beats if b.beat_id == "b1")
    with pytest.raises(TypeError):
        b1.accepted_state["emotion"] = "changed"  # type: ignore[index]


# --------------------------------------------------------------------------
# F. nested list/dict values inside accepted_state/overrides are protected
# --------------------------------------------------------------------------


def test_nested_list_dict_mutation_protected(synthetic_sc029_source):
    accepted = {
        "b1": {"emotion": {"primary": "anxious", "signals": ["tense", "watchful"]}}
    }
    ass = _import(synthetic_sc029_source, accepted_states=accepted)
    b1 = next(b for b in ass.ordered_beats if b.beat_id == "b1")
    stored = ass.content_hash

    # Nested list is stored as a tuple and must not be independently mutable.
    signals = b1.accepted_state["emotion"]["signals"]
    with pytest.raises(TypeError):
        signals[0] = "third"  # type: ignore[index]

    assert b1.accepted_state["emotion"]["signals"] == ("tense", "watchful")
    assert compute_content_hash(ass.semantic_payload()) == stored


# --------------------------------------------------------------------------
# G. semantic_payload()/to_dict() do not expose mutable aliases back into ASS
# --------------------------------------------------------------------------


def test_semantic_payload_alias_safe(synthetic_sc029_source):
    ass = _import(
        synthetic_sc029_source,
        character_state_overrides={"alice": {"clothing": "sports top"}},
    )
    stored = ass.content_hash

    payload = ass.semantic_payload()
    payload["character_state_overrides"]["alice"]["clothing"] = "hacked"
    payload["scene_id"] = "SC_000"
    payload["ordered_beats"][0]["text"] = "hacked text"

    assert ass.scene_id == "SC_029"
    assert ass.character_state_overrides["alice"]["clothing"] == "sports top"
    assert ass.ordered_beats[0].text != "hacked text"
    assert compute_content_hash(ass.semantic_payload()) == stored


def test_to_dict_alias_safe(synthetic_sc029_source):
    ass = _import(
        synthetic_sc029_source,
        character_state_overrides={"alice": {"clothing": "sports top"}},
    )
    stored = ass.content_hash

    envelope = ass.to_dict()
    envelope["character_state_overrides"]["alice"]["clothing"] = "hacked"
    envelope["content_hash"] = "0" * 64

    assert ass.character_state_overrides["alice"]["clothing"] == "sports top"
    assert ass.content_hash == stored


# --------------------------------------------------------------------------
# H. after all attempted external mutations, stored hash == recomputed
# --------------------------------------------------------------------------


def test_stored_hash_equals_recomputed_after_mutation_attempts(synthetic_sc029_source):
    overrides = {"alice": {"clothing": "sports top + leggings"}}
    accepted = {"b1": {"emotion": {"primary": "anxious", "signals": ["tense"]}}}
    loc = [{"predicate": "lights", "value": "off"}]

    ass = _import(
        synthetic_sc029_source,
        character_state_overrides=overrides,
        accepted_states=accepted,
        location_state_overrides=loc,
    )
    stored = ass.content_hash

    # Attempt every external mutation vector.
    overrides["alice"]["clothing"] = "hacked"
    accepted["b1"]["emotion"]["signals"].append("hacked")
    loc[0]["value"] = "on"

    assert ass.character_state_overrides["alice"]["clothing"] == "sports top + leggings"
    assert compute_content_hash(ass.semantic_payload()) == stored


# --------------------------------------------------------------------------
# I. existing top-level frozen-dataclass behavior remains intact
# --------------------------------------------------------------------------


def test_top_level_frozen_behavior_unchanged(synthetic_sc029_source):
    ass = _import(synthetic_sc029_source)
    with pytest.raises(dataclasses.FrozenInstanceError):
        ass.scene_id = "SC_000"  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        ass.character_state_overrides = None  # type: ignore[misc]