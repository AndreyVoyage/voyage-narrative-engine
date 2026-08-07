#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Slice 2 tests for tools/cis_pilot/memory_gate.py.

No LLM, no network. Covers: four-layer separation (WORLD_EVENT !=
PERCEPTION != INTERPRETATION != MEMORY as distinct types and content),
deterministic salience threshold (boundary at threshold-1/threshold/
threshold+1), provenance-identity dedup, conflict evidence (never averaged,
promotion blocked), in-memory-only episodic state semantics, and the two
worked ME-1/ME-2 four-layer traces built from the real frozen source
snapshot with approved spec §6 subjective content via deterministic stubs.
"""

from __future__ import annotations

import ast
import hashlib
import inspect
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.cis_pilot.contracts import ContractValidationError, P3State
from tools.cis_pilot.memory_gate import (
    CONFLICT_STATUS,
    DECISION_CONFLICTED,
    DECISION_DISCARD,
    DECISION_DUPLICATE,
    DECISION_KEEP,
    MEMORY_SALIENCE_THRESHOLD,
    CharacterInterpretation,
    CharacterMemory,
    CharacterPerception,
    EpisodicMemoryState,
    MemoryConflict,
    MemoryGateError,
    SalienceSignals,
    WorldEvent,
    evaluate_memory_candidate,
    propose_gist,
    propose_interpretation,
)
from tools.cis_pilot.source_loader import load_pilot_source_snapshot

CHARACTER_ID = "kira"

# Approved spec §6 subjective content (verbatim from the pilot specification).
ME1_PERCEPTION_NOTICED = (
    "физическая близость собеседника; он остаётся рядом; "
    "в этот момент он не требует объяснений."
)
ME1_INTERPRETATION_MEANING = (
    "воспринимает его поведение как принятие её уязвимости и безопасную близость."
)
ME1_INTERPRETATION_COLORING = "позитив, безопасная близость"
ME1_MEMORY_GIST = (
    "Я позволила себе расплакаться у него на груди; "
    "он остался рядом и не заставлял меня объясняться"
)
ME2_PERCEPTION_NOTICED = "видит уведомление о новом сообщении от Сергея."
ME2_INTERPRETATION_MEANING = (
    "сообщение воспринимается как возможное возвращение прежнего напряжения "
    "и неопределённости."
)
ME2_INTERPRETATION_COLORING = "тревога, настороженность"
ME2_MEMORY_GIST = "Сергей снова написал; это вернуло тревогу и настороженность"

_PROTECTED_SUBSET = (
    "personas/kira/psychology/VALUE_SYSTEM.json",
    "personas/kira/relationships/MATRIX.json",
    "scenarios/SCENARIO_008_HOME_EMBRACE.json",
    "scenarios/SCENARIO_017_SERGEY_WRITES_AGAIN.v2.json",
)


@pytest.fixture(scope="module")
def snapshot():
    return load_pilot_source_snapshot(_REPO_ROOT)


@pytest.fixture(scope="module")
def me1_event(snapshot) -> WorldEvent:
    return WorldEvent.from_memory_event_source(snapshot.me1, ("kira", "user"))


@pytest.fixture(scope="module")
def me2_event(snapshot) -> WorldEvent:
    return WorldEvent.from_memory_event_source(snapshot.me2, ("kira", "sergey", "yakov"))


def _perception(event: WorldEvent, noticed: str = "замеченный аспект события") -> CharacterPerception:
    return CharacterPerception(
        character_id=CHARACTER_ID, world_event_id=event.event_id, noticed=noticed
    )


def _interpretation(event: WorldEvent, meaning: str = "субъективный смысл события") -> CharacterInterpretation:
    return CharacterInterpretation(
        character_id=CHARACTER_ID,
        world_event_id=event.event_id,
        meaning=meaning,
        emotional_coloring="нейтрально-тёплая окраска",
    )


def _signals(**overrides) -> SalienceSignals:
    base = dict(
        emotion=False,
        repetition=False,
        threat=False,
        promise=False,
        intimacy=False,
        recency=False,
        p0_value_link=False,
    )
    base.update(overrides)
    return SalienceSignals(**base)


def _candidate(event: WorldEvent, signals: SalienceSignals, gist: str = "субъективный пересказ события") -> CharacterMemory:
    return CharacterMemory(
        character_id=CHARACTER_ID,
        world_event=event,
        retained_gist=gist,
        salience=signals.score(),
        possible_distortion=None,
        tags=("episodic",),
    )


def _hash_all(paths: tuple) -> dict:
    return {p: hashlib.sha256((_REPO_ROOT / p).read_bytes()).hexdigest() for p in paths}


def _imported_module_names(source_path: Path) -> set:
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


# ---------------------------------------------------------------------------
# Four-layer separation (items 1-6)
# ---------------------------------------------------------------------------


def test_four_layer_types_are_distinct_classes():
    assert len({WorldEvent, CharacterPerception, CharacterInterpretation, CharacterMemory}) == 4


def test_world_event_is_not_perception(me1_event):
    perception = _perception(me1_event)
    assert type(me1_event) is not type(perception)
    assert me1_event != perception


def test_perception_is_not_interpretation(me1_event):
    assert _perception(me1_event) != _interpretation(me1_event)


def test_interpretation_is_not_memory(me1_event):
    signals = _signals(emotion=True)
    assert _interpretation(me1_event) != _candidate(me1_event, signals)


def test_me1_objective_text_differs_from_memory_text(me1_event):
    assert me1_event.objective_text == "Кира падает ему на грудь. Плачет. Не объясняет."
    assert ME1_MEMORY_GIST != me1_event.objective_text
    assert snapshot_text_is_not_memory(me1_event, ME1_MEMORY_GIST)


def test_me2_objective_text_differs_from_memory_text(me2_event):
    assert me2_event.objective_text == "Телефон загорается новым сообщением от Сергея."
    assert ME2_MEMORY_GIST != me2_event.objective_text


def snapshot_text_is_not_memory(event: WorldEvent, gist: str) -> bool:
    return event.objective_text not in gist or gist != event.objective_text


def test_event_text_equals_memory_text_shortcut_fails_closed(me1_event):
    with pytest.raises(ContractValidationError):
        CharacterMemory(
            character_id=CHARACTER_ID,
            world_event=me1_event,
            retained_gist=me1_event.objective_text,  # forbidden shortcut
            salience=3,
            possible_distortion=None,
            tags=(),
        )


def test_interpretation_is_belief_never_fact(me1_event):
    with pytest.raises(ContractValidationError):
        CharacterInterpretation(
            character_id=CHARACTER_ID,
            world_event_id=me1_event.event_id,
            meaning="смысл",
            emotional_coloring="окраска",
            belief_tag="fact",
        )


# ---------------------------------------------------------------------------
# Salience (items 7-10)
# ---------------------------------------------------------------------------


def test_salience_has_exactly_seven_signals_and_additive_score():
    import dataclasses

    field_names = [f.name for f in dataclasses.fields(SalienceSignals)]
    assert field_names == [
        "emotion", "repetition", "threat", "promise", "intimacy", "recency", "p0_value_link",
    ]
    assert _signals().score() == 0
    assert _signals(emotion=True, threat=True, recency=True).score() == 3
    full = _signals(
        emotion=True, repetition=True, threat=True, promise=True,
        intimacy=True, recency=True, p0_value_link=True,
    )
    assert full.score() == 7


def test_threshold_minus_one_discards(me1_event):
    signals = _signals(emotion=True, threat=True)  # 2 = threshold - 1
    assert signals.score() == MEMORY_SALIENCE_THRESHOLD - 1
    state = EpisodicMemoryState()
    result = evaluate_memory_candidate(
        me1_event, _perception(me1_event), _interpretation(me1_event),
        _candidate(me1_event, signals), signals, state,
    )
    assert result.decision == DECISION_DISCARD
    assert result.state.memories == ()


def test_threshold_exactly_keeps(me1_event):
    signals = _signals(emotion=True, threat=True, recency=True)  # 3 = threshold
    assert signals.score() == MEMORY_SALIENCE_THRESHOLD
    result = evaluate_memory_candidate(
        me1_event, _perception(me1_event), _interpretation(me1_event),
        _candidate(me1_event, signals), signals, EpisodicMemoryState(),
    )
    assert result.decision == DECISION_KEEP
    assert len(result.state.memories) == 1


def test_threshold_plus_one_keeps(me1_event):
    signals = _signals(emotion=True, threat=True, recency=True, intimacy=True)  # 4
    assert signals.score() == MEMORY_SALIENCE_THRESHOLD + 1
    result = evaluate_memory_candidate(
        me1_event, _perception(me1_event), _interpretation(me1_event),
        _candidate(me1_event, signals), signals, EpisodicMemoryState(),
    )
    assert result.decision == DECISION_KEEP


# ---------------------------------------------------------------------------
# Dedup / state semantics (items 11-15)
# ---------------------------------------------------------------------------


def _kept_state(event: WorldEvent) -> EpisodicMemoryState:
    signals = _signals(emotion=True, threat=True, recency=True)
    result = evaluate_memory_candidate(
        event, _perception(event), _interpretation(event),
        _candidate(event, signals), signals, EpisodicMemoryState(),
    )
    assert result.decision == DECISION_KEEP
    return result.state


def test_duplicate_event_creates_no_second_memory(me1_event):
    state = _kept_state(me1_event)
    signals = _signals(emotion=True, threat=True, recency=True)
    result = evaluate_memory_candidate(
        me1_event, _perception(me1_event), _interpretation(me1_event),
        _candidate(me1_event, signals), signals, state,
    )
    assert result.decision == DECISION_DUPLICATE
    assert len(result.state.memories) == 1


def test_accepted_memory_enters_episodic_state(me1_event):
    state = _kept_state(me1_event)
    assert len(state.memories) == 1
    assert state.memories[0].world_event.event_id == me1_event.event_id


def test_rejected_memory_does_not_enter_state(me1_event):
    signals = _signals(emotion=True)  # score 1 < threshold
    state = EpisodicMemoryState()
    result = evaluate_memory_candidate(
        me1_event, _perception(me1_event), _interpretation(me1_event),
        _candidate(me1_event, signals), signals, state,
    )
    assert result.decision == DECISION_DISCARD
    assert result.state.memories == ()
    assert result.state.conflicts == ()


def test_input_state_is_never_mutated(me1_event):
    state = EpisodicMemoryState()
    keep_signals = _signals(emotion=True, threat=True, recency=True)
    discard_signals = _signals(emotion=True)
    discard_result = evaluate_memory_candidate(
        me1_event, _perception(me1_event), _interpretation(me1_event),
        _candidate(me1_event, discard_signals), discard_signals, state,
    )
    assert discard_result.state is state  # discard returns the same object
    keep_result = evaluate_memory_candidate(
        me1_event, _perception(me1_event), _interpretation(me1_event),
        _candidate(me1_event, keep_signals), keep_signals, state,
    )
    assert keep_result.state is not state
    assert state.memories == ()  # original untouched


def test_repeated_identical_input_is_deterministic(me1_event):
    signals = _signals(emotion=True, threat=True, recency=True)
    args = (
        me1_event, _perception(me1_event), _interpretation(me1_event),
        _candidate(me1_event, signals), signals, EpisodicMemoryState(),
    )
    first = evaluate_memory_candidate(*args)
    second = evaluate_memory_candidate(*args)
    assert first == second


# ---------------------------------------------------------------------------
# Conflict (items 16-18)
# ---------------------------------------------------------------------------


def test_conflict_is_marked_conflicted(me1_event):
    state = _kept_state(me1_event)
    signals = _signals(emotion=True, threat=True, recency=True)
    other_gist = "иной субъективный пересказ того же события"
    result = evaluate_memory_candidate(
        me1_event, _perception(me1_event), _interpretation(me1_event),
        _candidate(me1_event, signals, gist=other_gist), signals, state,
    )
    assert result.decision == DECISION_CONFLICTED
    assert len(result.state.conflicts) == 1
    assert result.state.conflicts[0].status == CONFLICT_STATUS


def test_conflicting_versions_are_not_averaged(me1_event):
    state = _kept_state(me1_event)
    original_gist = state.memories[0].retained_gist
    other_gist = "иной субъективный пересказ того же события"
    signals = _signals(emotion=True, threat=True, recency=True)
    result = evaluate_memory_candidate(
        me1_event, _perception(me1_event), _interpretation(me1_event),
        _candidate(me1_event, signals, gist=other_gist), signals, state,
    )
    conflict = result.state.conflicts[0]
    assert conflict.existing_gist == original_gist
    assert conflict.conflicting_gist == other_gist
    assert conflict.existing_gist != conflict.conflicting_gist
    # The kept memory still holds the original gist verbatim -- no merge.
    assert result.state.memories[0].retained_gist == original_gist


def test_conflict_blocks_automatic_promotion(me1_event):
    state = _kept_state(me1_event)
    other_gist = "иной субъективный пересказ того же события"
    signals = _signals(emotion=True, threat=True, recency=True)
    result = evaluate_memory_candidate(
        me1_event, _perception(me1_event), _interpretation(me1_event),
        _candidate(me1_event, signals, gist=other_gist), signals, state,
    )
    assert len(result.state.memories) == 1  # candidate NOT promoted
    assert all(m.retained_gist != other_gist for m in result.state.memories)


# ---------------------------------------------------------------------------
# Provenance / paths (items 19-20)
# ---------------------------------------------------------------------------


def test_accepted_memory_retains_full_provenance(me1_event):
    state = _kept_state(me1_event)
    memory = state.memories[0]
    assert memory.world_event.event_id == "SC_008"
    assert memory.world_event.scenario_repo_relative_path == (
        "scenarios/SCENARIO_008_HOME_EMBRACE.json"
    )
    assert memory.world_event.json_path == "choice_points[0].branches[0].action"
    assert len(memory.world_event.source_sha256) == 64
    provenance = memory.provenance
    assert "SC_008" in provenance
    assert "scenarios/SCENARIO_008_HOME_EMBRACE.json" in provenance
    assert memory.world_event.source_sha256 in provenance


def test_no_absolute_machine_paths_anywhere(me1_event, me2_event):
    for event in (me1_event, me2_event):
        path = event.scenario_repo_relative_path
        assert "\\" not in path
        assert ":" not in path
        assert not path.startswith("/")


# ---------------------------------------------------------------------------
# Boundaries: no P3 / no canon / no files / no provider (items 21-24)
# ---------------------------------------------------------------------------


def test_gate_has_no_p3_input_and_never_mutates_p3(me1_event):
    signature = inspect.signature(evaluate_memory_candidate)
    forbidden = {"p3", "p3_state", "trust", "attraction", "relationship"}
    assert forbidden.isdisjoint(signature.parameters.keys())
    p3 = P3State(trust=75, attraction=85)
    signals = _signals(emotion=True, threat=True, recency=True)
    evaluate_memory_candidate(
        me1_event, _perception(me1_event), _interpretation(me1_event),
        _candidate(me1_event, signals), signals, EpisodicMemoryState(),
    )
    assert (p3.trust, p3.attraction) == (75, 85)


def test_gate_does_not_write_canon(me1_event, me2_event):
    before = _hash_all(_PROTECTED_SUBSET)
    for event in (me1_event, me2_event):
        _kept_state(event)
    after = _hash_all(_PROTECTED_SUBSET)
    assert before == after
    result = subprocess.run(
        ["git", "-C", str(_REPO_ROOT), "status", "--porcelain=v1",
         "--untracked-files=all", "--", "personas", "scenarios"],
        capture_output=True, text=True, timeout=10, shell=False,
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_gate_creates_no_files_or_local_runs(me1_event):
    _kept_state(me1_event)
    assert not (_REPO_ROOT / "local_runs").exists()


def test_memory_gate_requires_no_network_or_provider():
    from tools.cis_pilot import memory_gate

    imported = _imported_module_names(Path(memory_gate.__file__))
    forbidden_fragments = (
        "openai", "anthropic", "deepseek", "kimi", "ollama",
        "requests", "httpx", "urllib", "socket", "llm_provider",
        "provider_boundary",
    )
    for name in imported:
        for fragment in forbidden_fragments:
            assert fragment not in name.lower(), f"forbidden import {name}"


# ---------------------------------------------------------------------------
# Fail-closed structural checks + proposal injection
# ---------------------------------------------------------------------------


def test_broken_layer_linkage_fails_closed(me1_event, me2_event):
    signals = _signals(emotion=True, threat=True, recency=True)
    wrong_perception = _perception(me2_event)  # linked to another event
    with pytest.raises(MemoryGateError):
        evaluate_memory_candidate(
            me1_event, wrong_perception, _interpretation(me1_event),
            _candidate(me1_event, signals), signals, EpisodicMemoryState(),
        )


def test_salience_mismatch_fails_closed(me1_event):
    signals = _signals(emotion=True, threat=True, recency=True)
    lying_candidate = CharacterMemory(
        character_id=CHARACTER_ID,
        world_event=me1_event,
        retained_gist="субъективный пересказ события",
        salience=7,  # does not match signals.score() == 3
        possible_distortion=None,
        tags=(),
    )
    with pytest.raises(MemoryGateError):
        evaluate_memory_candidate(
            me1_event, _perception(me1_event), _interpretation(me1_event),
            lying_candidate, signals, EpisodicMemoryState(),
        )


def test_interpretation_proposal_injection_with_deterministic_stub(me1_event):
    perception = _perception(me1_event, noticed=ME1_PERCEPTION_NOTICED)

    def _stub(event, perc):
        return CharacterInterpretation(
            character_id=perc.character_id,
            world_event_id=event.event_id,
            meaning=ME1_INTERPRETATION_MEANING,
            emotional_coloring=ME1_INTERPRETATION_COLORING,
        )

    interpretation = propose_interpretation(_stub, me1_event, perception)
    assert interpretation.meaning == ME1_INTERPRETATION_MEANING
    assert interpretation.belief_tag == "belief"


def test_proposal_returning_objective_text_fails_closed(me1_event):
    perception = _perception(me1_event)
    interpretation = _interpretation(me1_event)

    def _bad_gist(event, perc, interp):
        return event.objective_text  # forbidden shortcut

    with pytest.raises(MemoryGateError):
        propose_gist(_bad_gist, me1_event, perception, interpretation)


def test_proposal_wrong_type_fails_closed(me1_event):
    with pytest.raises(MemoryGateError):
        propose_interpretation(lambda e, p: "not-an-interpretation", me1_event, _perception(me1_event))


# ---------------------------------------------------------------------------
# Worked ME-1 / ME-2 four-layer traces (items 25-26)
# ---------------------------------------------------------------------------


def _worked_trace(event: WorldEvent, noticed: str, meaning: str, coloring: str, gist: str, signals: SalienceSignals):
    """Full four-layer trace with deterministic stub proposals, then gate."""
    perception = CharacterPerception(
        character_id=CHARACTER_ID, world_event_id=event.event_id, noticed=noticed
    )

    def _interpretation_stub(evt, perc):
        return CharacterInterpretation(
            character_id=perc.character_id,
            world_event_id=evt.event_id,
            meaning=meaning,
            emotional_coloring=coloring,
        )

    interpretation = propose_interpretation(_interpretation_stub, event, perception)

    def _gist_stub(evt, perc, interp):
        return gist

    retained_gist = propose_gist(_gist_stub, event, perception, interpretation)
    candidate = CharacterMemory(
        character_id=CHARACTER_ID,
        world_event=event,
        retained_gist=retained_gist,
        salience=signals.score(),
        possible_distortion=None,
        tags=("episodic", "pilot-fixture"),
    )
    result = evaluate_memory_candidate(
        event, perception, interpretation, candidate, signals, EpisodicMemoryState()
    )
    return perception, interpretation, candidate, result


def test_me1_worked_four_layer_trace(me1_event):
    signals = _signals(emotion=True, intimacy=True, recency=True, p0_value_link=True)
    perception, interpretation, candidate, result = _worked_trace(
        me1_event, ME1_PERCEPTION_NOTICED, ME1_INTERPRETATION_MEANING,
        ME1_INTERPRETATION_COLORING, ME1_MEMORY_GIST, signals,
    )
    assert result.decision == DECISION_KEEP
    memory = result.state.memories[0]
    # Four layers: distinct types, distinct content, fully linked.
    assert len({type(me1_event), type(perception), type(interpretation), type(memory)}) == 4
    assert perception.noticed == ME1_PERCEPTION_NOTICED
    assert interpretation.meaning == ME1_INTERPRETATION_MEANING
    assert memory.retained_gist == ME1_MEMORY_GIST
    assert memory.retained_gist != me1_event.objective_text
    assert (
        perception.world_event_id
        == interpretation.world_event_id
        == memory.world_event.event_id
        == me1_event.event_id
        == "SC_008"
    )
    assert memory.salience == 4


def test_me2_worked_four_layer_trace(me2_event):
    signals = _signals(emotion=True, threat=True, recency=True)
    perception, interpretation, candidate, result = _worked_trace(
        me2_event, ME2_PERCEPTION_NOTICED, ME2_INTERPRETATION_MEANING,
        ME2_INTERPRETATION_COLORING, ME2_MEMORY_GIST, signals,
    )
    assert result.decision == DECISION_KEEP
    memory = result.state.memories[0]
    assert perception.noticed == ME2_PERCEPTION_NOTICED
    assert interpretation.meaning == ME2_INTERPRETATION_MEANING
    assert memory.retained_gist == ME2_MEMORY_GIST
    assert memory.retained_gist != me2_event.objective_text
    assert memory.world_event.event_id == "SC_017"
    assert memory.salience == 3 == MEMORY_SALIENCE_THRESHOLD
    # Only the confirmed first sentence is the objective text (Slice 0 semantics).
    assert "Яков" not in me2_event.objective_text
