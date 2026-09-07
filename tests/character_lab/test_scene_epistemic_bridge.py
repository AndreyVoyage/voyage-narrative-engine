#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Scene Epistemic Claims V1 -- claim model + projection bridge (offline, no provider).

Proves the additive claim layer NEXT TO the free-form Scene:

- ``SceneEpistemicClaim`` validates fail-closed (blank meaning / unknown kind /
  duplicate-or-blank perceivers / invalid temporal bounds / bad confidence);
- ``project_scene_claim`` / ``project_scene_claims`` carry every claim field
  verbatim into an ``EpistemicEnvelope`` usable by the SAME Core selector;
- free-form scene text is NEVER auto-converted into epistemic facts;
- contradictory claims both project, unreconciled;
- the base ``Scene`` type is untouched (exact field set, hash, rendering).
"""

from __future__ import annotations

import pytest

from services.character_core.epistemics import (
    EpistemicEnvelope,
    EpistemicKind,
    select_visible_epistemic_context,
)
from services.character_lab.scene import (
    Scene,
    SceneEpistemicClaim,
    SceneError,
    SceneWithClaims,
    new_scene,
    render_scene_block,
    scene_from_jsonable,
    scene_hash,
    scene_to_jsonable,
    with_epistemic_claims,
)
from services.character_lab.scene_epistemic_bridge import (
    SceneEpistemicBridgeError,
    project_scene_claim,
    project_scene_claims,
)

DOOR_LOCKED = "Дверь на террасу заперта."
DOOR_OPEN = "Дверь на терраса открыта."  # intentionally distinct string


def _claim(**over):
    kwargs = dict(
        claim_id="claim-1",
        meaning=DOOR_LOCKED,
        epistemic_kind="WORLD_FACT",
        provenance="scene_authored",
        perceiver_ids=("kira",),
        valid_from_seq=3,
        valid_to_seq=None,
        confidence=0.9,
    )
    kwargs.update(over)
    return SceneEpistemicClaim(**kwargs)


def _base_scene(**over):
    kwargs = dict(
        title="Терраса",
        location="крыша",
        participants=["Кира"],
        prior_events=["Все поднялись наверх."],
        current_situation="Ночь, тихо.",
        scene_id="sc-1",
        created_at="2026-01-01T00:00:00+00:00",
    )
    kwargs.update(over)
    return new_scene(**kwargs)


# --------------------------------------------------------------------------
# 1-5 -- claim model validation
# --------------------------------------------------------------------------


class TestSceneEpistemicClaimValidation:
    def test_1_valid_claim_created(self):
        claim = _claim()
        assert claim.claim_id == "claim-1"
        assert claim.meaning == DOOR_LOCKED
        assert claim.epistemic_kind is EpistemicKind.WORLD_FACT
        assert claim.provenance == "scene_authored"
        assert claim.perceiver_ids == ("kira",)
        assert claim.valid_from_seq == 3
        assert claim.valid_to_seq is None
        assert claim.confidence == 0.9
        assert claim.holder_id is None

    def test_1b_kind_string_coerced_to_enum(self):
        assert _claim(epistemic_kind="USER_REPORT").epistemic_kind is EpistemicKind.USER_REPORT
        assert _claim(epistemic_kind=EpistemicKind.WORLD_FACT).epistemic_kind is EpistemicKind.WORLD_FACT

    def test_2_blank_meaning_rejected(self):
        for bad in ("", "   ", None, 42):
            with pytest.raises(SceneError):
                _claim(meaning=bad)

    def test_2b_blank_claim_id_and_provenance_rejected(self):
        for field in ("claim_id", "provenance"):
            for bad in ("", "  ", None):
                with pytest.raises(SceneError):
                    _claim(**{field: bad})

    def test_3_unknown_epistemic_kind_rejected(self):
        for bad in ("SOMETHING_ELSE", "world_fact", "", None, 7):
            with pytest.raises(SceneError):
                _claim(epistemic_kind=bad)

    def test_4_blank_perceiver_id_rejected(self):
        for bad in (("",), ("kira", "  "), (None,), (7,)):
            with pytest.raises(SceneError):
                _claim(perceiver_ids=bad)

    def test_4b_duplicate_perceiver_ids_rejected(self):
        with pytest.raises(SceneError):
            _claim(perceiver_ids=("kira", "kira"))

    def test_4c_perceiver_ids_must_be_a_tuple(self):
        for bad in ("kira", ["kira"], {"kira"}):
            with pytest.raises(SceneError):
                _claim(perceiver_ids=bad)

    def test_5_valid_to_before_valid_from_rejected(self):
        with pytest.raises(SceneError):
            _claim(valid_from_seq=10, valid_to_seq=9)

    def test_5b_non_int_temporal_bounds_rejected(self):
        for bad in (True, "3", 3.5):
            with pytest.raises(SceneError):
                _claim(valid_from_seq=bad)
            with pytest.raises(SceneError):
                _claim(valid_to_seq=bad)

    def test_5c_boundary_equal_bounds_allowed(self):
        claim = _claim(valid_from_seq=5, valid_to_seq=5)
        assert claim.valid_from_seq == 5 and claim.valid_to_seq == 5

    def test_confidence_validated(self):
        for bad in (-0.1, 1.1, float("nan"), float("inf"), True, "0.5"):
            with pytest.raises(SceneError):
                _claim(confidence=bad)
        assert _claim(confidence=1).confidence == 1.0  # int coerced to float

    def test_holder_addressable_kind_requires_holder(self):
        with pytest.raises(SceneError):
            _claim(epistemic_kind="CHARACTER_BELIEF")
        claim = _claim(epistemic_kind="CHARACTER_BELIEF", holder_id="kira")
        assert claim.holder_id == "kira"


# --------------------------------------------------------------------------
# 6-10 -- projection bridge
# --------------------------------------------------------------------------


class TestProjection:
    def test_6_8_projection_carries_every_field(self):
        claim = _claim(
            claim_id="claim-42",
            confidence=0.25,
            provenance="scene_authored_v1",
            valid_from_seq=7,
            valid_to_seq=12,
            perceiver_ids=("kira", "maksim"),
        )
        env = project_scene_claim(claim)
        assert isinstance(env, EpistemicEnvelope)
        assert env.meaning == claim.meaning
        assert env.epistemic_kind is EpistemicKind.WORLD_FACT
        assert env.provenance == "scene_authored_v1"
        assert env.basis_event_ids == ("claim-42",)  # the claim is its own basis
        assert env.confidence == 0.25
        assert env.perceiver_ids == ("kira", "maksim")
        assert env.valid_from_seq == 7
        assert env.valid_to_seq == 12
        assert env.holder_id is None

    def test_6b_holder_carried_for_belief_claim(self):
        env = project_scene_claim(
            _claim(epistemic_kind="CHARACTER_BELIEF", holder_id="kira", perceiver_ids=())
        )
        assert env.epistemic_kind is EpistemicKind.CHARACTER_BELIEF
        assert env.holder_id == "kira"
        # holder sees own belief even with no explicit perceivers (Core rule)
        visible = select_visible_epistemic_context((env,), perceiver_id="kira", at_seq=99)
        assert visible == (env,)

    def test_7_order_preserved(self):
        scene = with_epistemic_claims(
            _base_scene(),
            [_claim(claim_id="c-1", meaning="Первое."), _claim(claim_id="c-2", meaning="Второе.")],
        )
        envs = project_scene_claims(scene)
        assert [e.meaning for e in envs] == ["Первое.", "Второе."]
        assert [e.basis_event_ids for e in envs] == [("c-1",), ("c-2",)]

    def test_9_free_form_text_never_projected(self):
        scene = with_epistemic_claims(_base_scene(), [_claim()])
        envs = project_scene_claims(scene)
        assert len(envs) == 1
        for fragment in ("Терраса", "крыша", "Все поднялись наверх.", "Ночь, тихо."):
            assert all(fragment not in e.meaning for e in envs)
        # and a claim-less scene projects nothing at all
        assert project_scene_claims(_base_scene()) == ()
        assert project_scene_claims(None) == ()

    def test_10_contradictory_claims_both_project(self):
        scene = with_epistemic_claims(
            _base_scene(),
            [_claim(claim_id="c-lock", meaning=DOOR_LOCKED),
             _claim(claim_id="c-open", meaning=DOOR_OPEN)],
        )
        envs = project_scene_claims(scene)
        assert [e.meaning for e in envs] == [DOOR_LOCKED, DOOR_OPEN]  # no reconciliation

    def test_projection_rejects_non_claim(self):
        with pytest.raises(SceneEpistemicBridgeError) as ei:
            project_scene_claim("Дверь заперта.")
        assert ei.value.code == "unsupported_claim_input"

    def test_projected_envelope_passes_core_selector(self):
        env = project_scene_claim(_claim(valid_from_seq=3, valid_to_seq=5))
        # same pipeline as every other epistemic input: perceiver + window
        assert select_visible_epistemic_context((env,), perceiver_id="kira", at_seq=2) == ()
        assert select_visible_epistemic_context((env,), perceiver_id="kira", at_seq=3) == (env,)
        assert select_visible_epistemic_context((env,), perceiver_id="kira", at_seq=5) == (env,)
        assert select_visible_epistemic_context((env,), perceiver_id="kira", at_seq=6) == ()
        assert select_visible_epistemic_context((env,), perceiver_id="maksim", at_seq=4) == ()


# --------------------------------------------------------------------------
# SceneWithClaims -- additive subtype, base Scene untouched
# --------------------------------------------------------------------------


class TestSceneWithClaims:
    def test_is_a_scene_and_base_field_set_unchanged(self):
        scene = with_epistemic_claims(_base_scene(), [_claim()])
        assert isinstance(scene, Scene)
        assert isinstance(scene, SceneWithClaims)
        # the BASE Scene keeps exactly its historical field set
        assert set(vars(new_scene(title="x")).keys()) == {
            "scene_id", "title", "location", "participants",
            "prior_events", "current_situation", "created_at",
        }

    def test_claims_must_be_tuple_of_claims(self):
        base = dict(
            scene_id="sc-1", title="", location="", participants=(),
            prior_events=(), current_situation="", created_at="2026-01-01T00:00:00+00:00",
        )
        with pytest.raises(SceneError):
            SceneWithClaims(**base, epistemic_claims=["not-a-claim"])
        with pytest.raises(SceneError):
            SceneWithClaims(**base, epistemic_claims="claim-1")
        assert SceneWithClaims(**base, epistemic_claims=()).epistemic_claims == ()

    def test_content_preserved_field_for_field(self):
        base = _base_scene()
        scene = with_epistemic_claims(base, [_claim()])
        for f in ("scene_id", "title", "location", "participants",
                  "prior_events", "current_situation", "created_at"):
            assert getattr(scene, f) == getattr(base, f)

    def test_render_block_identical_with_and_without_claims(self):
        base = _base_scene()
        with_claims = with_epistemic_claims(base, [_claim()])
        assert render_scene_block(with_claims) == render_scene_block(base)
        assert DOOR_LOCKED not in render_scene_block(with_claims)  # claims stay out of free-form

    def test_hash_unchanged_without_claims_and_covers_claims(self):
        base = _base_scene()
        assert scene_to_jsonable(base) == scene_to_jsonable(_base_scene())
        assert "epistemic_claims" not in scene_to_jsonable(base)
        with_claims = with_epistemic_claims(base, [_claim()])
        assert scene_hash(with_claims) != scene_hash(base)  # claims are part of identity
        assert scene_hash(with_epistemic_claims(base, [_claim()])) == scene_hash(with_claims)

    def test_jsonable_roundtrip_with_claims(self):
        scene = with_epistemic_claims(_base_scene(), [_claim(), _claim(claim_id="c-2", meaning="Иное.")])
        restored = scene_from_jsonable(scene_to_jsonable(scene))
        assert isinstance(restored, SceneWithClaims)
        assert restored == scene

    def test_jsonable_roundtrip_without_claims_stays_base_scene(self):
        base = _base_scene()
        restored = scene_from_jsonable(scene_to_jsonable(base))
        assert type(restored) is Scene
        assert restored == base

    def test_from_jsonable_rejects_unknown_claim_fields(self):
        payload = scene_to_jsonable(with_epistemic_claims(_base_scene(), [_claim()]))
        payload["epistemic_claims"][0]["surprise"] = 1
        with pytest.raises(SceneError):
            scene_from_jsonable(payload)
