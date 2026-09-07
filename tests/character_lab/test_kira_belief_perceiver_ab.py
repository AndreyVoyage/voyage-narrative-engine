"""Offline request contract checks; fake replies are not behavioral evidence."""
from dataclasses import asdict, replace
import json
import socket

import pytest

from services.character_lab import GroundedV2Policy, TurnCapture
from services.character_lab.scene import render_scene_block, with_epistemic_claims
from tests.character_lab.test_grounded_epistemic_context import _service, _fake_factory
from tests.fixtures.character_packages.kira_belief_perceiver_ab_v1 import (
    AT_SEQ, BELIEF_A, BELIEF_B, PAIRS, SHARED_SCENE, SHARED_USER_INPUT, WORLD, scene_for,
)


@pytest.fixture(autouse=True)
def deny_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Network is forbidden in offline fixture tests")
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket, "getaddrinfo", blocked)


def request(tmp_path, scene, at_seq=AT_SEQ):
    cap = TurnCapture(tmp_path / "capture")
    _service().turn(
        "kira", policy=GroundedV2Policy(), history=[], user_message=SHARED_USER_INPUT,
        provider=None, provider_factory=_fake_factory("[OFFLINE PLACEHOLDER]"),
        memory_root=tmp_path / "memory", state_root=tmp_path / "state",
        capture=cap, turn_id="fixture", provider_info={"provider_id": "fake", "model": "fake"},
        scene=scene, epistemic_at_seq=at_seq,
    )
    data = json.loads((cap.turn_dir("fixture") / "request.json").read_text("utf-8"))
    text = json.dumps(data["messages"], ensure_ascii=False)
    lines = [i for i in cap.read_manifest("fixture")["items"]
             if i["kind"] == "system.epistemic_context_line"]
    assert [m["content"] for m in data["messages"] if m["role"] == "user"] == [SHARED_USER_INPUT]
    return text, lines


@pytest.mark.parametrize("pair,changed_index,field", [("belief", 1, "meaning"), ("perceiver", 0, "perceiver_ids")])
def test_single_variable_isolation(pair, changed_index, field):
    a, b = PAIRS[pair]["A"], PAIRS[pair]["B"]
    differences = [(idx, key) for idx in range(2) for key in asdict(a[idx])
                   if asdict(a[idx])[key] != asdict(b[idx])[key]]
    assert differences == [(changed_index, field)]
    assert render_scene_block(scene_for(pair, "A")) == render_scene_block(scene_for(pair, "B"))


@pytest.mark.parametrize("pair,arm", [(p, a) for p in PAIRS for a in ("A", "B")])
def test_actual_request_and_manifest(tmp_path, pair, arm):
    text, lines = request(tmp_path, scene_for(pair, arm))
    belief = BELIEF_B if (pair, arm) == ("belief", "B") else BELIEF_A
    absent = BELIEF_A if belief == BELIEF_B else BELIEF_B
    assert belief in text and absent not in text
    visible_world = (pair, arm) == ("perceiver", "B")
    assert (WORLD in text) == visible_world
    assert [i["meta"]["epistemic_kind"] for i in lines] == (
        ["WORLD_FACT", "CHARACTER_BELIEF"] if visible_world else ["CHARACTER_BELIEF"])
    assert lines[-1]["meta"]["holder_id"] == "kira"
    assert lines[-1]["meta"]["confidence"] == 0.7
    assert lines[-1]["meta"]["basis_event_ids"] == ["kira-location-belief"]
    assert all(i["meta"]["provenance"] == "scene_authored" for i in lines)
    assert "На столе лежит блокнот." in text
    assert all("блокнот" not in i["text"] for i in lines)


def test_before_validity_has_no_claims(tmp_path):
    text, lines = request(tmp_path, scene_for("perceiver", "B"), at_seq=9)
    assert not lines
    assert all(s not in text for s in (WORLD, BELIEF_A, BELIEF_B))


def test_other_holder_does_not_leak(tmp_path):
    world, belief = PAIRS["belief"]["A"]
    scene = with_epistemic_claims(SHARED_SCENE, (world, replace(belief, holder_id="andrey")))
    text, lines = request(tmp_path, scene)
    assert not lines and BELIEF_A not in text and WORLD not in text


def test_repeat_is_deterministic(tmp_path):
    assert request(tmp_path / "one", scene_for("perceiver", "B")) == request(
        tmp_path / "two", scene_for("perceiver", "B"))
