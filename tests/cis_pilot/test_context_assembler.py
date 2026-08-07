#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Slice 1 tests for tools/cis_pilot/context_assembler.py.

No LLM, no network. Loads the real, frozen Slice 0 pilot source snapshot
(read-only) to build realistic P0/P3/P4 fixtures, then exercises CIS-arm
assembly and rendering: layer isolation (only the touched field changes),
determinism, no-write guarantees, non-convergence with the baseline arm,
and the Slice 0 contract-naming normalization rules from this Slice 1
authorization's §5 (do not rename/duplicate the seven Slice 0 contracts;
do not prematurely create pilot-wide Slice 2+ names).
"""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.cis_pilot.contracts import (
    BaselineSourceSet,
    ContractValidationError,
    MemoryEventSource,
    P0Snapshot,
    P3State,
    P4State,
    PilotSourceSnapshot,
    SourceArtifact,
)
from tools.cis_pilot.context_assembler import (
    CisContextLayers,
    assemble_cis_context,
    render_cis_messages,
)
from tools.cis_pilot.source_loader import load_pilot_source_snapshot

_CRITICAL_SOURCES = (
    "personas/kira/psychology/VALUE_SYSTEM.json",
    "personas/kira/psychology/BASE.json",
    "personas/kira/psychology/ATTACHMENT.json",
    "personas/kira/psychology/DEFENSE_MECHANISMS.json",
    "personas/kira/psychology/IFS_PARTS.json",
    "personas/kira/psychology/ODSC.json",
    "personas/kira/relationships/MATRIX.json",
    "personas/kira/psychology/AFFECT_REGULATION.json",
)

SCENE_QUESTION = "Что ты сейчас чувствуешь?"


def _hash_all(paths: tuple) -> dict:
    return {p: hashlib.sha256((_REPO_ROOT / p).read_bytes()).hexdigest() for p in paths}


def _imported_module_names(source_path: Path) -> set:
    """Return every module name this file actually imports (``import x`` /
    ``from x import y`` / ``from .x import y``), parsed via ``ast`` -- never
    matched as a raw substring, so a docstring merely *mentioning* another
    module's filename does not count as an import."""
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


@pytest.fixture(scope="module")
def snapshot() -> PilotSourceSnapshot:
    return load_pilot_source_snapshot(_REPO_ROOT)


# ---------------------------------------------------------------------------
# CIS P0
# ---------------------------------------------------------------------------


def test_assembled_context_p0_is_the_loaded_snapshot_p0(snapshot):
    p4 = snapshot.p4_strategy_map["low_arousal_low_anxiety"]
    context = assemble_cis_context(snapshot.p0, snapshot.p3, p4, SCENE_QUESTION)
    assert context.p0 == snapshot.p0


def test_p0_snapshot_has_exactly_six_fields_no_attachment_style_dynamic():
    field_names = {f.name for f in dataclasses.fields(P0Snapshot)}
    assert field_names == {
        "value_system", "base", "attachment", "defense_mechanisms", "ifs_parts", "odsc",
    }
    assert "attachment_style_dynamic" not in field_names


# ---------------------------------------------------------------------------
# CIS P3 (spec PD-3 / T3-P3)
# ---------------------------------------------------------------------------


def test_p3_source_state_is_75_85(snapshot):
    assert snapshot.p3.trust == 75
    assert snapshot.p3.attraction == 85


def test_t3_p3_intervention_states_a_and_b():
    state_a = P3State(trust=75, attraction=85)
    state_b = P3State(trust=55, attraction=85)
    assert (state_a.trust, state_a.attraction) == (75, 85)
    assert (state_b.trust, state_b.attraction) == (55, 85)


def test_p3_has_no_session_count_attachment_style_or_resentment_field():
    field_names = {f.name for f in dataclasses.fields(P3State)}
    assert field_names == {"trust", "attraction"}


# ---------------------------------------------------------------------------
# CIS P4 (spec PD-4 / T3-P4)
# ---------------------------------------------------------------------------


def test_p4_strategy_map_has_four_source_backed_combinations(snapshot):
    assert len(snapshot.p4_strategy_map) == 4


def test_t3_p3_fixed_p4_is_low_low_exploration(snapshot):
    p4 = snapshot.p4_strategy_map["low_arousal_low_anxiety"]
    assert (p4.arousal, p4.anxiety, p4.strategy) == ("low", "low", "exploration")


def test_t3_p4_state_a_is_high_low_approach(snapshot):
    p4 = snapshot.p4_strategy_map["high_arousal_low_anxiety"]
    assert (p4.arousal, p4.anxiety, p4.strategy) == ("high", "low", "approach")


def test_t3_p4_state_b_is_high_high_avoidance(snapshot):
    p4 = snapshot.p4_strategy_map["high_arousal_high_anxiety"]
    assert (p4.arousal, p4.anxiety, p4.strategy) == ("high", "high", "avoidance")


# ---------------------------------------------------------------------------
# Structural layering
# ---------------------------------------------------------------------------


def test_memory_layer_is_always_none_in_slice1(snapshot):
    p4 = snapshot.p4_strategy_map["low_arousal_low_anxiety"]
    context = assemble_cis_context(snapshot.p0, snapshot.p3, p4, SCENE_QUESTION)
    assert context.memory_layer is None


def test_context_layers_rejects_non_none_memory_layer(snapshot):
    p4 = snapshot.p4_strategy_map["low_arousal_low_anxiety"]
    with pytest.raises(ContractValidationError):
        CisContextLayers(
            p0=snapshot.p0,
            p3=snapshot.p3,
            p4=p4,
            memory_layer="not-none",  # type: ignore[arg-type]
            scene_question=SCENE_QUESTION,
        )


def test_context_layers_rejects_empty_scene_question(snapshot):
    p4 = snapshot.p4_strategy_map["low_arousal_low_anxiety"]
    with pytest.raises(ContractValidationError):
        CisContextLayers(
            p0=snapshot.p0,
            p3=snapshot.p3,
            p4=p4,
            memory_layer=None,
            scene_question="   ",
        )


def test_rendered_messages_have_role_content_shape(snapshot):
    p4 = snapshot.p4_strategy_map["low_arousal_low_anxiety"]
    context = assemble_cis_context(snapshot.p0, snapshot.p3, p4, SCENE_QUESTION)
    messages = render_cis_messages(context)
    assert isinstance(messages, list)
    for message in messages:
        assert set(message.keys()) == {"role", "content"}


def test_rendered_messages_contain_distinct_p0_p3_p4_memory_blocks(snapshot):
    p4 = snapshot.p4_strategy_map["low_arousal_low_anxiety"]
    context = assemble_cis_context(snapshot.p0, snapshot.p3, p4, SCENE_QUESTION)
    system_content = render_cis_messages(context)[0]["content"]
    assert "P0 core psychological anchors" in system_content
    assert "P3 relationship state" in system_content
    assert "P4 transient regulation state" in system_content
    assert "Event/memory layer: absent" in system_content


def test_rendered_messages_user_content_is_scene_question(snapshot):
    p4 = snapshot.p4_strategy_map["low_arousal_low_anxiety"]
    context = assemble_cis_context(snapshot.p0, snapshot.p3, p4, SCENE_QUESTION)
    messages = render_cis_messages(context)
    assert messages[-1] == {"role": "user", "content": SCENE_QUESTION}


# ---------------------------------------------------------------------------
# Isolation (the core Slice 1 requirement)
# ---------------------------------------------------------------------------


def test_p3_only_change_leaves_p0_and_p4_object_fields_untouched(snapshot):
    p4_fixed = snapshot.p4_strategy_map["low_arousal_low_anxiety"]
    context_a = assemble_cis_context(
        snapshot.p0, P3State(trust=75, attraction=85), p4_fixed, SCENE_QUESTION
    )
    context_b = assemble_cis_context(
        snapshot.p0, P3State(trust=55, attraction=85), p4_fixed, SCENE_QUESTION
    )
    assert context_a.p0 == context_b.p0
    assert context_a.p4 == context_b.p4
    assert context_a.p3 != context_b.p3


def test_p3_only_change_isolates_to_the_p3_rendered_segment(snapshot):
    p4_fixed = snapshot.p4_strategy_map["low_arousal_low_anxiety"]
    context_a = assemble_cis_context(
        snapshot.p0, P3State(trust=75, attraction=85), p4_fixed, SCENE_QUESTION
    )
    context_b = assemble_cis_context(
        snapshot.p0, P3State(trust=55, attraction=85), p4_fixed, SCENE_QUESTION
    )
    segments_a = render_cis_messages(context_a)[0]["content"].split("\n\n")
    segments_b = render_cis_messages(context_b)[0]["content"].split("\n\n")
    assert len(segments_a) == len(segments_b) == 4
    p0_a, p3_a, p4_a, mem_a = segments_a
    p0_b, p3_b, p4_b, mem_b = segments_b
    assert p0_a == p0_b
    assert p4_a == p4_b
    assert mem_a == mem_b
    assert p3_a != p3_b


def test_p4_only_change_leaves_p0_and_p3_object_fields_untouched(snapshot):
    state_a = snapshot.p4_strategy_map["high_arousal_low_anxiety"]
    state_b = snapshot.p4_strategy_map["high_arousal_high_anxiety"]
    context_a = assemble_cis_context(snapshot.p0, snapshot.p3, state_a, SCENE_QUESTION)
    context_b = assemble_cis_context(snapshot.p0, snapshot.p3, state_b, SCENE_QUESTION)
    assert context_a.p0 == context_b.p0
    assert context_a.p3 == context_b.p3
    assert context_a.p4 != context_b.p4


def test_p4_only_change_isolates_to_the_p4_rendered_segment(snapshot):
    state_a = snapshot.p4_strategy_map["high_arousal_low_anxiety"]
    state_b = snapshot.p4_strategy_map["high_arousal_high_anxiety"]
    context_a = assemble_cis_context(snapshot.p0, snapshot.p3, state_a, SCENE_QUESTION)
    context_b = assemble_cis_context(snapshot.p0, snapshot.p3, state_b, SCENE_QUESTION)
    segments_a = render_cis_messages(context_a)[0]["content"].split("\n\n")
    segments_b = render_cis_messages(context_b)[0]["content"].split("\n\n")
    assert len(segments_a) == len(segments_b) == 4
    p0_a, p3_a, p4_a, mem_a = segments_a
    p0_b, p3_b, p4_b, mem_b = segments_b
    assert p0_a == p0_b
    assert p3_a == p3_b
    assert mem_a == mem_b
    assert p4_a != p4_b


def test_assembly_does_not_mutate_source_snapshot(snapshot):
    p4_fixed = snapshot.p4_strategy_map["low_arousal_low_anxiety"]
    original_p0 = snapshot.p0
    original_p3 = snapshot.p3
    assemble_cis_context(snapshot.p0, P3State(trust=55, attraction=85), p4_fixed, SCENE_QUESTION)
    assert snapshot.p0 == original_p0
    assert snapshot.p3 == original_p3


def test_repeated_assembly_with_identical_input_is_deterministic(snapshot):
    p4_fixed = snapshot.p4_strategy_map["low_arousal_low_anxiety"]
    context_1 = assemble_cis_context(snapshot.p0, snapshot.p3, p4_fixed, SCENE_QUESTION)
    context_2 = assemble_cis_context(snapshot.p0, snapshot.p3, p4_fixed, SCENE_QUESTION)
    assert render_cis_messages(context_1) == render_cis_messages(context_2)


# ---------------------------------------------------------------------------
# Non-convergence with the baseline arm (spec §16)
# ---------------------------------------------------------------------------


def test_context_assembler_does_not_import_baseline_adapter_or_aside_builder():
    import tools.cis_pilot.context_assembler as ca_module

    imported = _imported_module_names(Path(ca_module.__file__))
    assert not any("baseline_adapter" in name for name in imported)
    assert not any("aside_context_builder" in name for name in imported)


# ---------------------------------------------------------------------------
# No write
# ---------------------------------------------------------------------------


def test_no_write_source_hashes_unchanged_before_and_after(snapshot):
    before = _hash_all(_CRITICAL_SOURCES)
    p4_fixed = snapshot.p4_strategy_map["low_arousal_low_anxiety"]
    for trust in (75, 55):
        context = assemble_cis_context(
            snapshot.p0, P3State(trust=trust, attraction=85), p4_fixed, SCENE_QUESTION
        )
        render_cis_messages(context)
    after = _hash_all(_CRITICAL_SOURCES)
    assert before == after


def test_local_runs_not_created():
    assert not (_REPO_ROOT / "local_runs").exists()


# ---------------------------------------------------------------------------
# NAMING (this authorization's §5 QA-M2 normalization)
# ---------------------------------------------------------------------------


def test_seven_slice0_contracts_still_exist_under_original_names():
    names = {
        SourceArtifact.__name__,
        P0Snapshot.__name__,
        P3State.__name__,
        P4State.__name__,
        MemoryEventSource.__name__,
        BaselineSourceSet.__name__,
        PilotSourceSnapshot.__name__,
    }
    assert names == {
        "SourceArtifact",
        "P0Snapshot",
        "P3State",
        "P4State",
        "MemoryEventSource",
        "BaselineSourceSet",
        "PilotSourceSnapshot",
    }


def test_pilot_wide_slice2plus_names_not_created_in_slice1_files():
    forbidden = (
        "class WorldEvent",
        "class CharacterPerception",
        "class CharacterInterpretation",
        "class CharacterMemory",
        "class EvolutionProposal",
        "class AuditRecord",
        "class ProvenanceManifest",
    )
    for relative in (
        "tools/cis_pilot/baseline_adapter.py",
        "tools/cis_pilot/context_assembler.py",
    ):
        text = (_REPO_ROOT / relative).read_text(encoding="utf-8")
        for marker in forbidden:
            assert marker not in text, f"{marker} found in {relative}"
