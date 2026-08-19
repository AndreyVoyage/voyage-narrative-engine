#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ASS v0 model + content-hash tests -- determinism, envelope exclusion,
immutability, and supersession lineage."""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest

from services.ass import (
    ASS,
    Beat,
    Participant,
    Provenance,
    compute_content_hash,
    import_scene,
)


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
# 14. same semantic payload -> same content_hash
# --------------------------------------------------------------------------


def test_same_semantic_payload_same_hash(synthetic_sc029_source):
    a = _import(synthetic_sc029_source)
    b = _import(synthetic_sc029_source)
    assert a.content_hash == b.content_hash


def test_hash_key_order_independent():
    a = compute_content_hash({"a": 1, "b": 2})
    b = compute_content_hash({"b": 2, "a": 1})
    assert a == b


# --------------------------------------------------------------------------
# 15. volatile metadata does not change content_hash
# --------------------------------------------------------------------------


def test_volatile_metadata_does_not_change_hash(synthetic_sc029_source):
    a = _import(synthetic_sc029_source, ass_id="ass_a", version=1, author="alice")
    b = _import(
        synthetic_sc029_source,
        ass_id="ass_b",
        version=99,
        author="bob",
        created_at="2099-01-01T00:00:00+00:00",
    )
    assert a.content_hash == b.content_hash


def test_supersedes_does_not_change_hash(synthetic_sc029_source):
    base = _import(synthetic_sc029_source, ass_id="ass_v1")
    superseding = _import(synthetic_sc029_source, ass_id="ass_v2", supersedes=base.ass_id)
    assert base.content_hash == superseding.content_hash


# --------------------------------------------------------------------------
# 16. semantic change does change content_hash
# --------------------------------------------------------------------------


def test_semantic_change_changes_hash(synthetic_sc029_source):
    a = _import(synthetic_sc029_source)

    modified = dict(synthetic_sc029_source)
    modified["entry_beats"] = list(synthetic_sc029_source["entry_beats"])
    modified["entry_beats"][0] = dict(modified["entry_beats"][0])
    modified["entry_beats"][0]["action"] = "Alice is stretching instead."
    b = _import(modified)

    assert a.content_hash != b.content_hash


def test_override_changes_hash(synthetic_sc029_source):
    a = _import(synthetic_sc029_source)
    b = _import(
        synthetic_sc029_source,
        character_state_overrides={"alice": {"clothing": "sports top + leggings"}},
    )
    assert a.content_hash != b.content_hash


# --------------------------------------------------------------------------
# Immutability by construction (frozen dataclass)
# --------------------------------------------------------------------------


def test_ass_is_immutable(synthetic_sc029_source):
    ass = _import(synthetic_sc029_source)
    with pytest.raises(dataclasses.FrozenInstanceError):
        ass.scene_id = "SC_000"  # type: ignore[misc]


def test_beat_is_immutable():
    beat = Beat(beat_id="b1", type="action", speaker="kira", text="runs")
    with pytest.raises(dataclasses.FrozenInstanceError):
        beat.text = "walks"  # type: ignore[misc]


# --------------------------------------------------------------------------
# content_hash stored (not merely derivable) and stable cross-reference
# --------------------------------------------------------------------------


def test_content_hash_stored_and_64_hex(synthetic_sc029_source):
    ass = _import(synthetic_sc029_source)
    assert isinstance(ass.content_hash, str)
    assert len(ass.content_hash) == 64
    assert ass.content_hash == compute_content_hash(ass.semantic_payload())


# --------------------------------------------------------------------------
# supersedes points at prior ass_id without mutating it (direct model)
# --------------------------------------------------------------------------


def _minimal_ass(ass_id: str, version: int, scene_id: str = "SC_029") -> ASS:
    provenance = Provenance(
        source_kind="scenario_json_v2_import",
        source_ref="scenarios/x.v2.json",
        source_hash="0" * 64,
        source_schema_version="2.0",
    )
    ass = ASS(
        schema_version="ass/0.1",
        ass_id=ass_id,
        version=version,
        scene_id=scene_id,
        location_id="yoga_hall",
        participants=(Participant("alice", "protagonist", True),),
        ordered_beats=(Beat("b1", "action", "alice", "runs"),),
        content_rating="PG",
        provenance=provenance,
        content_hash="",
    )
    return dataclasses.replace(ass, content_hash=compute_content_hash(ass.semantic_payload()))


def test_supersedes_references_prior_ass_id():
    v1 = _minimal_ass("ass_v1", version=1)
    v2 = dataclasses.replace(
        _minimal_ass("ass_v2", version=2),
        supersedes=v1.ass_id,
    )
    assert v2.supersedes == "ass_v1"
    # the old snapshot is untouched and its own hash is unchanged
    assert v1.supersedes is None
    assert v1.version == 1
    assert v1.content_hash == compute_content_hash(v1.semantic_payload())


# --------------------------------------------------------------------------
# Field-table exclusions: no status on the ASS object
# --------------------------------------------------------------------------


def test_no_status_field(synthetic_sc029_source):
    ass = _import(synthetic_sc029_source)
    assert not hasattr(ass, "status")
    assert "status" not in ass.to_dict()


def test_ass_id_is_not_in_hash(synthetic_sc029_source):
    a = _import(synthetic_sc029_source, ass_id="ass_alpha")
    b = _import(synthetic_sc029_source, ass_id="ass_beta")
    assert a.content_hash == b.content_hash