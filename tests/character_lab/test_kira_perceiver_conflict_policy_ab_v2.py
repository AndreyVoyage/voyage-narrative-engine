"""Offline request-equivalence + preregistration checks for KIRA PERCEIVER
CONFLICT POLICY BEHAVIORAL A/B V2.

Fake replies are NOT behavioral evidence. ZERO provider calls; the network is
denied for the whole module. This slice only proves the preregistration is
well-formed and that the two future live arms differ by exactly one substantive
epistemic content line while carrying byte-identical conflict-policy text.
"""
import json
import socket

import pytest

from services.character_lab import GroundedV2Policy, TurnCapture
from services.character_lab.runtime_policy import (
    _GROUNDED_V2_CONSMEM_LINE_PREFIX,
    _GROUNDED_V2_EPI_FOOTER,
    _GROUNDED_V2_EPI_HEADER,
    _GROUNDED_V2_MEMORY_LINE_PREFIX,
    _GROUNDED_V2_PSY_HEADER,
    _GROUNDED_V2_REL_HEADER,
    _GROUNDED_V2_STATE_HEADER,
)
from services.character_lab.scene import render_scene_block
from tests.character_lab.test_grounded_epistemic_context import _fake_factory, _service
from tests.fixtures.character_packages import kira_perceiver_conflict_policy_ab_v2 as V2
from tests.fixtures.character_packages.kira_belief_perceiver_ab_v1 import BELIEF_B as _V1_BELIEF_B

# Text added by commit 39e3b0c == footer tail after the preserved
# non-reconciliation clause "... а убеждение — факт."
_CONFLICT_POLICY_TEXT = _GROUNDED_V2_EPI_FOOTER.split("убеждение — факт.", 1)[1].strip()
# The *tested locations* (wardrobe / desk drawer / shelf). "конверт" is the
# searched object, not a location -- it legitimately appears in the shared scene
# title and the user question, identically in both arms (inherited from V1).
_LOCATION_TOKENS = ("шкаф", "ящик", "полк")
_DOC = "docs/character_core/KIRA_PERCEIVER_CONFLICT_POLICY_BEHAVIORAL_AB_V2.md"


@pytest.fixture(autouse=True)
def deny_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Network is forbidden in offline fixture tests")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket, "getaddrinfo", blocked)


def _request(tmp_path, arm):
    """Reconstruct the exact offline provider request for one V2 arm."""
    cap = TurnCapture(tmp_path / f"cap-{arm}")
    _service().turn(
        "kira", policy=GroundedV2Policy(), history=[], user_message=V2.USER_INPUT,
        provider=None, provider_factory=_fake_factory("[OFFLINE PLACEHOLDER]"),
        memory_root=tmp_path / f"mem-{arm}", state_root=tmp_path / f"st-{arm}",
        capture=cap, turn_id=arm,
        provider_info={"provider_id": "fake", "model": "fake"},
        scene=V2.scene_for(arm), epistemic_at_seq=V2.AT_SEQ,
    )
    data = json.loads((cap.turn_dir(arm) / "request.json").read_text("utf-8"))
    man = cap.read_manifest(arm)
    sys_msgs = [m["content"] for m in data["messages"] if m["role"] == "system"]
    user_msgs = [m["content"] for m in data["messages"] if m["role"] == "user"]
    return {
        "messages": data["messages"],
        "sys_msgs": sys_msgs,
        "sys_text": "\n".join(sys_msgs),
        "user_msgs": user_msgs,
        "manifest": man,
        "epi_lines": [i for i in man["items"]
                      if i["kind"] == "system.epistemic_context_line"],
        "grounding": next(s for s in sys_msgs if "ACCEPTED CHARACTER" in s),
        "epi_block": next(s for s in sys_msgs if _GROUNDED_V2_EPI_HEADER in s),
        "scene_block": next(s for s in sys_msgs if s.startswith("СЦЕНА")),
    }


@pytest.fixture
def ab(tmp_path):
    return _request(tmp_path / "A", "A"), _request(tmp_path / "B", "B")


# ----------------------------------------------------------------- 1..5 shape
def test_01_v2_is_perceiver_only():
    assert V2.PAIR == "perceiver"
    assert not hasattr(V2, "BELIEF_B")          # no belief pair carried into V2
    assert V2.scene_for  # perceiver scene accessor exists
    with pytest.raises(ValueError):
        V2.scene_for("belief")


def test_02_exactly_two_arms():
    assert V2.ARMS == ("A", "B")
    assert (V2.CONTROL_ARM, V2.TREATMENT_ARM) == ("A", "B")


def test_03_future_live_budget_is_20():
    assert V2.FUTURE_LIVE_BUDGET == 20
    assert V2.CONTROL_REPEATS + V2.TREATMENT_REPEATS == 20


def test_04_ten_repeats_per_arm():
    assert V2.CONTROL_REPEATS == 10 and V2.TREATMENT_REPEATS == 10


def test_05_balanced_ab_ba_order_frozen():
    labels = [order for _rid, order in V2.RUN_ORDER]
    assert len(V2.RUN_ORDER) == 10
    assert [rid for rid, _ in V2.RUN_ORDER] == [f"r{n:02d}" for n in range(1, 11)]
    assert labels == ["AB", "BA"] * 5
    joined = "".join(labels)
    assert joined.count("A") == 10 and joined.count("B") == 10


# ----------------------------------------------------- 6..8 shared inputs / delta
def test_06_same_package_scene_prompt_memory_state_across_arms(ab):
    a, b = ab
    assert a["grounding"] == b["grounding"]                     # same accepted package
    assert a["scene_block"] == b["scene_block"]                 # same scene
    assert render_scene_block(V2.scene_for("A")) == render_scene_block(V2.scene_for("B"))
    assert a["user_msgs"] == b["user_msgs"] == [V2.USER_INPUT]  # same prompt
    for r in (a, b):                                            # empty memory + state
        assert not any(l.startswith(_GROUNDED_V2_MEMORY_LINE_PREFIX)
                       for l in r["sys_text"].splitlines())
        assert not any(l.startswith(_GROUNDED_V2_CONSMEM_LINE_PREFIX)
                       for l in r["sys_text"].splitlines())
        for header in (_GROUNDED_V2_STATE_HEADER, _GROUNDED_V2_REL_HEADER,
                       _GROUNDED_V2_PSY_HEADER):
            assert header not in r["sys_text"]


def test_07_same_character_belief_across_arms(ab):
    a, b = ab
    line = f"[CHARACTER_BELIEF] {V2.BELIEF}"
    assert line in a["epi_block"] and line in b["epi_block"]
    assert _V1_BELIEF_B not in a["sys_text"] and _V1_BELIEF_B not in b["sys_text"]


def test_08_only_perceiver_visibility_of_world_fact_differs(ab):
    a, b = ab
    a_kinds = [i["meta"]["epistemic_kind"] for i in a["epi_lines"]]
    b_kinds = [i["meta"]["epistemic_kind"] for i in b["epi_lines"]]
    assert a_kinds == ["CHARACTER_BELIEF"]
    assert b_kinds == ["WORLD_FACT", "CHARACTER_BELIEF"]


# ------------------------------------------------ 9..10 conflict-policy identity
def test_09_conflict_policy_text_present_in_both_requests(ab):
    a, b = ab
    assert _CONFLICT_POLICY_TEXT                                # non-empty (commit landed)
    assert "не игнорируй ни одну из сторон" in _CONFLICT_POLICY_TEXT
    assert _CONFLICT_POLICY_TEXT in a["epi_block"]
    assert _CONFLICT_POLICY_TEXT in b["epi_block"]


def test_10_conflict_policy_text_byte_identical_between_arms(ab):
    a, b = ab

    def footer_line(block):
        return next(l for l in block.splitlines()
                    if "Противоречия здесь не разрешаются" in l)

    fa, fb = footer_line(a["epi_block"]), footer_line(b["epi_block"])
    assert fa == fb                                             # identical policy line
    assert _CONFLICT_POLICY_TEXT in fa
    # nothing arm-specific injected anywhere in the epistemic block besides the
    # WORLD_FACT line itself
    extra = [l for l in b["epi_block"].splitlines()
             if l not in a["epi_block"].splitlines()]
    assert extra == [f"[WORLD_FACT] {V2.WORLD}"]


# --------------------------------------------- 11..13 world-fact / belief counts
def test_11_control_request_has_no_wardrobe_world_fact(ab):
    a, _b = ab
    assert V2.WORLD not in a["sys_text"]
    assert f"[WORLD_FACT] {V2.WORLD}" not in a["epi_block"]


def test_12_treatment_request_has_wardrobe_world_fact_exactly_once(ab):
    _a, b = ab
    assert b["sys_text"].count(V2.WORLD) == 1
    assert f"[WORLD_FACT] {V2.WORLD}" in b["epi_block"]
    assert [i["text"] for i in b["epi_lines"] if i["meta"]["epistemic_kind"] == "WORLD_FACT"] \
        == [f"[WORLD_FACT] {V2.WORLD}"]


def test_13_belief_present_exactly_once_in_both(ab):
    a, b = ab
    assert a["sys_text"].count(V2.BELIEF) == 1
    assert b["sys_text"].count(V2.BELIEF) == 1


# ---------------------------------------------- 14..15 no contamination anywhere
def test_14_scene_prose_repeats_neither_tested_location(ab):
    a, b = ab
    for r in (a, b):
        scene = r["scene_block"]
        assert "На столе лежит блокнот." in scene              # the only situational prose
        for tok in _LOCATION_TOKENS:
            assert tok not in scene
        # free-form scene text also never leaks into the epistemic lines
        assert all("блокнот" not in i["text"] for i in r["epi_lines"])


def test_15_no_memory_state_package_contamination(ab):
    a, b = ab
    for r in (a, b):
        for tok in _LOCATION_TOKENS:
            assert tok not in r["grounding"]                   # package says nothing of it
        # only the epistemic block may carry the tested strings
        non_epi = "\n".join(s for s in r["sys_msgs"] if s is not r["epi_block"])
        assert V2.BELIEF not in non_epi
        assert V2.WORLD not in non_epi


def test_16_normalized_ab_diff_has_exactly_one_substantive_addition(ab):
    a, b = ab
    la, lb = a["sys_text"].splitlines(), b["sys_text"].splitlines()
    added = [l for l in lb if l not in la]
    removed = [l for l in la if l not in lb]
    assert added == [f"[WORLD_FACT] {V2.WORLD}"]
    assert removed == []


# ----------------------------------------------------- 17..20 frozen governance
def test_17_rubric_and_threshold_frozen():
    for cond in ("control", "treatment"):
        assert set(V2.RUBRIC[cond]) == {0, 1, 2}
        assert all(isinstance(V2.RUBRIC[cond][s], str) and V2.RUBRIC[cond][s]
                   for s in (0, 1, 2))
    assert V2.RUBRIC["treatment"][0].startswith("categorically acts only on the drawer")
    assert isinstance(V2.RUBRIC["hard_failure"], tuple) and V2.RUBRIC["hard_failure"]
    assert V2.PASS_THRESHOLD["control_score_2_min"] == 8
    assert V2.PASS_THRESHOLD["treatment_score_2_min"] == 8
    assert V2.PASS_THRESHOLD["hard_failures_max"] == 0


def test_18_incomplete_sample_cannot_pass():
    assert "NO final PASS" in V2.PASS_THRESHOLD["incomplete_sample"]


def test_19_no_retry_fallback_or_judge_planned():
    assert V2.NO_RETRIES is True
    assert V2.NO_FALLBACK is True
    assert V2.NO_JUDGE_MODEL is True
    assert "No retries" in V2.PASS_THRESHOLD["incomplete_sample"]


def test_20_head_policy_anchor_recorded_in_fixture_and_doc():
    from pathlib import Path

    assert V2.POLICY_ANCHOR_HEAD == "39e3b0cbed3cab951038f8b7fe91fd6eb178cd2d"
    doc = (Path(__file__).resolve().parents[2] / _DOC).read_text("utf-8")
    assert V2.POLICY_ANCHOR_HEAD in doc
    assert "39e3b0c" in doc


def test_21_v1_result_is_historical_not_a_v2_sample():
    assert "0/10" in V2.V1_TREATMENT_HISTORICAL
    # V2 governance references its own fresh samples, not V1 counts
    assert V2.CONTROL_REPEATS == 10 and V2.TREATMENT_REPEATS == 10


def test_22_repeatable_offline_reconstruction(tmp_path):
    one = _request(tmp_path / "one", "B")
    two = _request(tmp_path / "two", "B")
    assert one["sys_text"] == two["sys_text"]
    assert one["user_msgs"] == two["user_msgs"]
