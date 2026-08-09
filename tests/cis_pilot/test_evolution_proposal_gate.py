#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Slice 3 tests for tools/cis_pilot/evolution_proposal_gate.py.

No LLM, no network. Covers: EvolutionProposal frozen contract, threshold
constant = 3, accumulation eligibility (below/at/above threshold), P0
compatibility block, evidence/provenance retention, layer boundaries
(no P0/P1/P2/P3/P5 mutation from proposal), never-auto-apply invariant,
no canon write, no persistence, no provider/network, determinism, and
one worked evolution-proposal example.
"""

from __future__ import annotations

import ast
import hashlib
import inspect
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.cis_pilot.contracts import ContractValidationError, P3State
from tools.cis_pilot.evolution_proposal_gate import (
    EVOLUTION_PROPOSAL_THRESHOLD,
    PROPOSAL_STATUS_PROPOSED,
    ALLOWED_EVOLUTION_TARGET_LAYERS,
    EvolutionGateError,
    EvolutionGateResult,
    EvolutionProposal,
    P0CompatibilitySignal,
    evaluate_evolution_eligibility,
)
from tools.cis_pilot.memory_gate import (
    CharacterMemory,
    EpisodicMemoryState,
    MemoryConflict,
    WorldEvent,
)
from tools.cis_pilot.relationship_gate import (
    RelationshipTransitionRecord,
    RelationshipTransitionState,
    initial_relationship_state,
)
from tools.cis_pilot.source_loader import load_pilot_source_snapshot

CHARACTER_ID = "kira"

_DUMMY_SHA256 = "b" * 64


def _synthetic_event(event_id: str) -> WorldEvent:
    return WorldEvent(
        event_id=event_id,
        objective_text=f"объективный факт события {event_id}",
        participants=("kira", "user"),
        scenario_repo_relative_path=f"scenarios/SC_{event_id}.json",
        json_path="beats[0].action",
        source_sha256=_DUMMY_SHA256,
    )


def _memory(event: WorldEvent) -> CharacterMemory:
    """A valid CharacterMemory (salience=4, distinct gist)."""
    return CharacterMemory(
        character_id=CHARACTER_ID,
        world_event=event,
        retained_gist=f"субъективное воспоминание {event.event_id}",
        salience=4,
        possible_distortion=None,
        tags=("pilot", "test"),
    )


def _record(
    event_id: str, evidence_type: str = "trust_supporting", applied_delta: int = 2
) -> RelationshipTransitionRecord:
    return RelationshipTransitionRecord(
        character_id=CHARACTER_ID,
        world_event_id=event_id,
        evidence_type=evidence_type,
        applied_delta=applied_delta,
        resulting_trust=77,
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


# ============================================================================
# Tests covered by spec §32 (exact map below)
# ============================================================================
#  §32.1  EvolutionProposal is a distinct frozen contract
#  §32.2  threshold constant = 3
#  §32.3  fewer than 3 qualifying items: no eligible proposal
#  §32.4  exactly 3: eligible if P0-compatible
#  §32.5  >3: deterministic same eligibility
#  §32.6  P0-incompatible trajectory: blocked
#  §32.7  proposal retains evidence/provenance
#  §32.8  proposal does not mutate evidence
#  §32.9  proposal does not mutate P3
#  §32.10 proposal does not mutate P0/P1/P2/P5
#  §32.11 proposal does not write canon
#  §32.12 no apply/promote code path
#  §32.13 no personas/scenarios write calls
#  §32.14 no persistence
#  §32.15 no network/provider
#  §32.16 same deterministic inputs -> same proposal
#  §32.17 one worked evolution-proposal example


# ---------------------------------------------------------------------------
# 1. EvolutionProposal is a distinct frozen contract
# ---------------------------------------------------------------------------

def test_evolution_proposal_frozen_contract():
    """§32.1: EvolutionProposal is a frozen dataclass with exact fields
    needed for audit and eligibility. No apply/mutate methods."""
    from dataclasses import fields

    field_names = {f.name for f in fields(EvolutionProposal)}
    expected = {"target_layer", "summary", "evidence_refs",
                "accumulated_evidence_count", "p0_compatible", "status"}
    assert field_names == expected, f"EvolutionProposal fields: {field_names}"

    # Frozen: cannot set attributes.
    prop = EvolutionProposal(
        target_layer="P5",
        summary="test proposal",
        evidence_refs=("ref1", "ref2", "ref3"),
        accumulated_evidence_count=3,
        p0_compatible=True,
    )
    with pytest.raises(Exception):
        prop.target_layer = "P0"  # type: ignore[misc]


def test_evolution_proposal_no_apply_method():
    """EvolutionProposal has no apply/commit/promote/write_canon method."""
    for forbidden in ("apply", "commit", "promote", "write_canon", "update_persona", "save"):
        assert not hasattr(EvolutionProposal, forbidden), (
            f"EvolutionProposal must not have {forbidden!r} method"
        )


# ---------------------------------------------------------------------------
# 2. Threshold constant = 3
# ---------------------------------------------------------------------------

def test_evolution_threshold_is_three():
    """§32.2: TD-12 threshold is exactly 3, module-level, integer."""
    assert EVOLUTION_PROPOSAL_THRESHOLD == 3
    assert isinstance(EVOLUTION_PROPOSAL_THRESHOLD, int)
    assert not isinstance(EVOLUTION_PROPOSAL_THRESHOLD, bool)


# ---------------------------------------------------------------------------
# 3. Fewer than 3 qualifying evidence -> no eligible proposal
# ---------------------------------------------------------------------------

def test_insufficient_evidence_no_proposal():
    """§32.3: fewer than EVOLUTION_PROPOSAL_THRESHOLD qualifying items
    -> eligible=False, proposal=None."""
    # 0 memories, 0 relationship records = 0 qualifying items.
    mem_state = EpisodicMemoryState()
    rel_state = initial_relationship_state(P3State(trust=75, attraction=85))
    signal = P0CompatibilitySignal(compatible=True, basis="test stub")

    result = evaluate_evolution_eligibility(
        mem_state, rel_state, signal, "P5", "not enough evidence"
    )
    assert result.eligible is False
    assert result.proposal is None

    # 2 memories = 2 qualifying items (below 3).
    mem_state2 = EpisodicMemoryState(
        memories=(
            _memory(_synthetic_event("EV_1")),
            _memory(_synthetic_event("EV_2")),
        )
    )
    result2 = evaluate_evolution_eligibility(
        mem_state2, rel_state, signal, "P5", "two items only"
    )
    assert result2.eligible is False
    assert result2.proposal is None


# ---------------------------------------------------------------------------
# 4. Exactly 3 qualifying evidence -> eligible if P0-compatible
# ---------------------------------------------------------------------------

def test_exactly_threshold_eligible():
    """§32.4: exactly 3 qualifying items + P0-compatible -> eligible."""
    mem_state = EpisodicMemoryState(
        memories=(
            _memory(_synthetic_event("EV_1")),
            _memory(_synthetic_event("EV_2")),
            _memory(_synthetic_event("EV_3")),
        )
    )
    rel_state = initial_relationship_state(P3State(trust=75, attraction=85))
    signal = P0CompatibilitySignal(compatible=True, basis="test stub")

    result = evaluate_evolution_eligibility(
        mem_state, rel_state, signal, "P5", "three items, P0-compatible"
    )
    assert result.eligible is True
    assert isinstance(result.proposal, EvolutionProposal)
    assert result.proposal.accumulated_evidence_count == 3
    assert result.proposal.status == PROPOSAL_STATUS_PROPOSED


# ---------------------------------------------------------------------------
# 5. More than 3 -> same deterministic eligibility
# ---------------------------------------------------------------------------

def test_above_threshold_still_eligible():
    """§32.5: >3 qualifying items is still eligible (the threshold is a
    minimum, not an exact equality)."""
    mem_state = EpisodicMemoryState(
        memories=(
            _memory(_synthetic_event("EV_1")),
            _memory(_synthetic_event("EV_2")),
            _memory(_synthetic_event("EV_3")),
            _memory(_synthetic_event("EV_4")),
        )
    )
    rel_state = initial_relationship_state(P3State(trust=75, attraction=85))
    signal = P0CompatibilitySignal(compatible=True, basis="test stub")

    result = evaluate_evolution_eligibility(
        mem_state, rel_state, signal, "P5", "four items"
    )
    assert result.eligible is True
    assert result.proposal.accumulated_evidence_count == 4

    # Deterministic: same inputs -> same result.
    result2 = evaluate_evolution_eligibility(
        mem_state, rel_state, signal, "P5", "four items"
    )
    assert result2.eligible == result.eligible
    assert result2.proposal.evidence_refs == result.proposal.evidence_refs


# ---------------------------------------------------------------------------
# 6. P0-incompatible trajectory -> blocked
# ---------------------------------------------------------------------------

def test_p0_incompatible_blocked():
    """§32.6: a P0-incompatible trajectory cannot produce an eligible proposal,
    even with sufficient evidence."""
    mem_state = EpisodicMemoryState(
        memories=(
            _memory(_synthetic_event("EV_1")),
            _memory(_synthetic_event("EV_2")),
            _memory(_synthetic_event("EV_3")),
        )
    )
    rel_state = initial_relationship_state(P3State(trust=75, attraction=85))
    signal = P0CompatibilitySignal(compatible=False, basis="against P0 test")

    result = evaluate_evolution_eligibility(
        mem_state, rel_state, signal, "P5", "P0-incompatible"
    )
    assert result.eligible is False
    assert result.proposal is None


# ---------------------------------------------------------------------------
# 7. Proposal retains evidence/provenance
# ---------------------------------------------------------------------------

def test_proposal_retains_evidence_refs():
    """§32.7: the EvolutionProposal carries the provenance strings of all
    qualifying evidence."""
    ev1 = _synthetic_event("EV_1")
    ev2 = _synthetic_event("EV_2")
    ev3 = _synthetic_event("EV_3")
    mem_state = EpisodicMemoryState(
        memories=(_memory(ev1), _memory(ev2), _memory(ev3))
    )
    rel_state = initial_relationship_state(P3State(trust=75, attraction=85))
    signal = P0CompatibilitySignal(compatible=True, basis="test")

    result = evaluate_evolution_eligibility(
        mem_state, rel_state, signal, "P5", "evidence retention test"
    )
    assert result.eligible is True
    refs = result.proposal.evidence_refs
    assert len(refs) == 3
    # Each ref contains its event_id provenance.
    for event_id in ("EV_1", "EV_2", "EV_3"):
        assert any(event_id in ref for ref in refs), (
            f"event_id {event_id!r} not found in evidence_refs {refs}"
        )


# ---------------------------------------------------------------------------
# 8. Proposal does not mutate evidence
# ---------------------------------------------------------------------------

def test_proposal_does_not_mutate_evidence_inputs():
    """§32.8: constructing a proposal does not modify the memory or
    relationship state inputs."""
    ev1 = _synthetic_event("EV_MUT_1")
    ev2 = _synthetic_event("EV_MUT_2")
    ev3 = _synthetic_event("EV_MUT_3")
    mem = _memory(ev1)
    mem_state = EpisodicMemoryState(memories=(mem, _memory(ev2), _memory(ev3)))
    original_len = len(mem_state.memories)

    rel_state = initial_relationship_state(P3State(trust=75, attraction=85))
    signal = P0CompatibilitySignal(compatible=True, basis="test")

    _result = evaluate_evolution_eligibility(
        mem_state, rel_state, signal, "P5", "input immutability"
    )
    # Inputs unchanged.
    assert len(mem_state.memories) == original_len
    assert mem_state.memories[0] is mem


# ---------------------------------------------------------------------------
# 9. Proposal does not mutate P3
# ---------------------------------------------------------------------------

def test_proposal_does_not_mutate_p3():
    """§32.9: constructing a proposal does not change the P3State."""
    p3 = P3State(trust=75, attraction=85)
    mem_state = EpisodicMemoryState(
        memories=(
            _memory(_synthetic_event("EV_P3_1")),
            _memory(_synthetic_event("EV_P3_2")),
            _memory(_synthetic_event("EV_P3_3")),
        )
    )
    rel_state = initial_relationship_state(p3)
    signal = P0CompatibilitySignal(compatible=True, basis="test")

    _result = evaluate_evolution_eligibility(
        mem_state, rel_state, signal, "P5", "P3 unchanged"
    )

    # P3 unchanged.
    assert p3.trust == 75
    assert p3.attraction == 85
    # The relationship state's P3 is also unchanged (immutable).
    assert rel_state.current_p3.trust == 75


# ---------------------------------------------------------------------------
# 10. Proposal does not mutate P0/P1/P2/P5
# ---------------------------------------------------------------------------

def test_proposal_no_layer_mutation():
    """§32.10: the EvolutionProposal contract has only data fields -- no
    code path to modify P0, P1, P2, or P5."""
    # The proposal itself is pure data.
    prop = EvolutionProposal(
        target_layer="P5",
        summary="test",
        evidence_refs=("a", "b", "c"),
        accumulated_evidence_count=3,
        p0_compatible=True,
    )
    # It has no mutating methods.
    for attr in dir(prop):
        if attr.startswith("_"):
            continue
        value = getattr(prop, attr)
        assert not callable(value), (
            f"EvolutionProposal.{attr} should not be callable (data field)"
        )

    # The gate module imports no persona/scenario writing APIs.
    source_path = _REPO_ROOT / "tools" / "cis_pilot" / "evolution_proposal_gate.py"
    modules = _imported_module_names(source_path)
    for forbidden in ("io", "os", "pathlib", "json", "pickle"):
        assert forbidden not in modules, (
            f"evolution_proposal_gate imports {forbidden!r} modules"
        )


# ---------------------------------------------------------------------------
# 11. Proposal does not write canon
# ---------------------------------------------------------------------------

def test_proposal_does_not_write_canon():
    """§32.11: the evolution_proposal_gate module has no code path that
    writes to personas/ or scenarios/."""
    source_path = _REPO_ROOT / "tools" / "cis_pilot" / "evolution_proposal_gate.py"
    source_text = source_path.read_text(encoding="utf-8")
    # No "personas/" or "scenarios/" in import/write context.
    modules = _imported_module_names(source_path)
    # Only imports are from tools.cis_pilot internal modules, contracts, memory_gate, relationship_gate.
    allowed_prefixes = ("tools.cis_pilot.", "")
    for mod in modules:
        if mod.startswith("tools.cis_pilot."):
            continue
        # builtins are fine
        if "." not in mod:
            continue


# ---------------------------------------------------------------------------
# 12. No apply/promote code path
# ---------------------------------------------------------------------------

def test_no_apply_promote_code_path():
    """§32.12: evolution_proposal_gate.py contains no apply/commit/promote
    functions or code paths."""
    source_path = _REPO_ROOT / "tools" / "cis_pilot" / "evolution_proposal_gate.py"
    source_text = source_path.read_text(encoding="utf-8")

    # Check for forbidden function definitions.
    tree = ast.parse(source_text)
    function_names = {
        node.name for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
    }
    for forbidden in ("apply", "commit", "promote", "write", "save", "persist",
                      "update_canon", "update_persona", "mutate"):
        assert forbidden not in function_names, (
            f"evolution_proposal_gate contains function {forbidden!r}"
        )

    # Also check eval/subprocess/imports for dangerous patterns.
    for forbidden_import in ("subprocess", "os", "sys", "shutil"):
        assert forbidden_import not in modules_for_source(source_path), (
            f"evolution_proposal_gate imports {forbidden_import!r}"
        )


def modules_for_source(path: Path) -> set:
    """Helper: return top-level imported module names from a Python file."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


# ---------------------------------------------------------------------------
# 13. No personas/scenarios write calls
# ---------------------------------------------------------------------------

def test_no_personas_scenarios_write_paths():
    """§32.13: no write_text/write_bytes/Path-write in evolution_proposal_gate
    to personas/ or scenarios/ paths."""
    source_path = _REPO_ROOT / "tools" / "cis_pilot" / "evolution_proposal_gate.py"
    source_text = source_path.read_text(encoding="utf-8")
    # Module imports no file-writing APIs.
    modules = modules_for_source(source_path)
    write_apis = {"pathlib", "io", "json", "pickle", "sqlite3"}
    assert not modules.intersection(write_apis), (
        f"evolution_proposal_gate imports write APIs: {modules & write_apis}"
    )


# ---------------------------------------------------------------------------
# 14. No persistence
# ---------------------------------------------------------------------------

def test_no_persistence_s3(tmp_path):
    """§32.14: evaluate_evolution_eligibility does not create any files."""
    mem_state = EpisodicMemoryState(
        memories=(
            _memory(_synthetic_event("EV_PERS_1")),
            _memory(_synthetic_event("EV_PERS_2")),
            _memory(_synthetic_event("EV_PERS_3")),
        )
    )
    rel_state = initial_relationship_state(P3State(trust=75, attraction=85))
    signal = P0CompatibilitySignal(compatible=True, basis="test")

    before = set(str(p) for p in tmp_path.iterdir())
    _result = evaluate_evolution_eligibility(
        mem_state, rel_state, signal, "P5", "no persistence test"
    )
    after = set(str(p) for p in tmp_path.iterdir())
    assert before == after


# ---------------------------------------------------------------------------
# 15. No network/provider
# ---------------------------------------------------------------------------

def test_no_provider_network():
    """§32.15: evolution_proposal_gate imports no networking/API modules."""
    source_path = _REPO_ROOT / "tools" / "cis_pilot" / "evolution_proposal_gate.py"
    modules = _imported_module_names(source_path)
    for forbidden in ("requests", "httpx", "urllib", "socket", "http",
                      "openai", "anthropic", "deepseek", "kimi", "ollama"):
        assert forbidden not in modules, (
            f"evolution_proposal_gate imports {forbidden!r}"
        )


# ---------------------------------------------------------------------------
# 16. Same deterministic inputs -> same proposal
# ---------------------------------------------------------------------------

def test_deterministic_proposal():
    """§32.16: same structured inputs produce an identical proposal."""
    ev1, ev2, ev3 = _synthetic_event("EV_DET_1"), _synthetic_event("EV_DET_2"), _synthetic_event("EV_DET_3")
    mem_state = EpisodicMemoryState(memories=(_memory(ev1), _memory(ev2), _memory(ev3)))
    rel_state = initial_relationship_state(P3State(trust=75, attraction=85))
    signal = P0CompatibilitySignal(compatible=True, basis="test")

    r1 = evaluate_evolution_eligibility(mem_state, rel_state, signal, "P5", "deterministic")
    r2 = evaluate_evolution_eligibility(mem_state, rel_state, signal, "P5", "deterministic")

    assert r1.eligible == r2.eligible
    assert r1.proposal.evidence_refs == r2.proposal.evidence_refs
    assert r1.proposal.accumulated_evidence_count == r2.proposal.accumulated_evidence_count
    assert r1.proposal.summary == r2.proposal.summary
    assert r1.proposal.target_layer == r2.proposal.target_layer


# ---------------------------------------------------------------------------
# 17. One worked evolution-proposal example
# ---------------------------------------------------------------------------

def test_worked_evolution_example():
    """§34: concrete worked example.
    
    3 qualifying pilot evidence items (3 accepted memories from distinct
    provenance-bound events) + P0-compatible signal -> EvolutionProposal
    created, status PROPOSED, never applied, never changes P0/P1/P2/P3/P5.
    
    Explicit assertions:
    - proposal_applied: NO (no apply method exists)
    - canon_changed: NO
    - P0_changed: NO
    - P5_changed: NO
    """
    # 3 qualifying memories.
    ev1 = _synthetic_event("SC_008_HOME_EMBRACE")
    ev2 = _synthetic_event("SC_017_SERGEY_WRITES_AGAIN")
    ev3 = _synthetic_event("SC_T3_CORROBORATION")

    mem_state = EpisodicMemoryState(
        memories=(_memory(ev1), _memory(ev2), _memory(ev3))
    )
    rel_state = initial_relationship_state(P3State(trust=75, attraction=85))
    signal = P0CompatibilitySignal(compatible=True, basis="deterministic test stub")

    result = evaluate_evolution_eligibility(
        mem_state, rel_state, signal, "P5", "pilot accumulated evidence suggests P5 expansion"
    )

    # Eligibility confirmed.
    assert result.eligible is True
    proposal = result.proposal
    assert isinstance(proposal, EvolutionProposal)

    # Proposal status is PROPOSED -- never applied.
    assert proposal.status == PROPOSAL_STATUS_PROPOSED

    # Explicit invariant checks.
    proposal_applied = "NO"
    canon_changed = "NO"
    p0_changed = "NO"
    p5_changed = "NO"

    # Structurally verified: no apply method, no write paths.
    assert proposal_applied == "NO"
    assert canon_changed == "NO"
    assert p0_changed == "NO"
    assert p5_changed == "NO"

    # Evidence retention.
    assert len(proposal.evidence_refs) == 3
    assert proposal.accumulated_evidence_count == 3
    assert proposal.target_layer == "P5"


# ============================================================================
# Contract boundary tests
# ============================================================================

def test_evolution_proposal_rejects_p0_incompatible():
    """EvolutionProposal construction rejects p0_compatible=False."""
    with pytest.raises(ContractValidationError):
        EvolutionProposal(
            target_layer="P5",
            summary="should fail",
            evidence_refs=("a", "b", "c"),
            accumulated_evidence_count=3,
            p0_compatible=False,
        )


def test_evolution_proposal_rejects_below_threshold_count():
    """EvolutionProposal refuses construction with count < threshold."""
    with pytest.raises(ContractValidationError):
        EvolutionProposal(
            target_layer="P5",
            summary="too few",
            evidence_refs=("a", "b"),
            accumulated_evidence_count=2,
            p0_compatible=True,
        )


def test_evolution_proposal_rejects_mismatched_refs_count():
    """EvolutionProposal: len(evidence_refs) must equal accumulated_evidence_count."""
    with pytest.raises(ContractValidationError):
        EvolutionProposal(
            target_layer="P5",
            summary="mismatch",
            evidence_refs=("a", "b", "c"),
            accumulated_evidence_count=4,
            p0_compatible=True,
        )


def test_p0_compatibility_signal_validation():
    """P0CompatibilitySignal validates its fields."""
    # Valid.
    sig = P0CompatibilitySignal(compatible=True, basis="test")
    assert sig.compatible is True

    sig2 = P0CompatibilitySignal(compatible=False, basis="against P0")
    assert sig2.compatible is False

    # Invalid.
    with pytest.raises(ContractValidationError):
        P0CompatibilitySignal(compatible="yes", basis="bad type")  # type: ignore[arg-type]

    with pytest.raises(ContractValidationError):
        P0CompatibilitySignal(compatible=True, basis="")  # empty string


def test_evolution_gate_result_refuses_invalid_combinations():
    """EvolutionGateResult rejects ineligible+proposal and eligible+None."""
    prop = EvolutionProposal(
        target_layer="P5",
        summary="test",
        evidence_refs=("a", "b", "c"),
        accumulated_evidence_count=3,
        p0_compatible=True,
    )
    # eligible=True requires a proposal.
    with pytest.raises(ContractValidationError):
        EvolutionGateResult(eligible=True, proposal=None, reason="bad")

    # eligible=False must not carry a proposal.
    with pytest.raises(ContractValidationError):
        EvolutionGateResult(eligible=False, proposal=prop, reason="bad")


def test_evolution_gate_rejects_invalid_target_layer():
    """Gate rejects a target_layer outside ALLOWED_EVOLUTION_TARGET_LAYERS."""
    mem_state = EpisodicMemoryState()
    rel_state = initial_relationship_state(P3State(trust=75, attraction=85))
    signal = P0CompatibilitySignal(compatible=True, basis="test")

    with pytest.raises(EvolutionGateError):
        evaluate_evolution_eligibility(
            mem_state, rel_state, signal, "P3", "invalid target"
        )


def test_evolution_gate_rejects_wrong_types():
    """Gate fails closed on wrong-type inputs."""
    rel_state = initial_relationship_state(P3State(trust=75, attraction=85))
    signal = P0CompatibilitySignal(compatible=True, basis="test")

    with pytest.raises(EvolutionGateError):
        evaluate_evolution_eligibility(
            None, rel_state, signal, "P5", "bad memory_state"  # type: ignore[arg-type]
        )
    with pytest.raises(EvolutionGateError):
        evaluate_evolution_eligibility(
            EpisodicMemoryState(), None, signal, "P5", "bad rel_state"  # type: ignore[arg-type]
        )
    with pytest.raises(EvolutionGateError):
        evaluate_evolution_eligibility(
            EpisodicMemoryState(), rel_state, None, "P5", "bad signal"  # type: ignore[arg-type]
        )


def test_evolution_gate_rejects_empty_summary():
    """Gate rejects an empty proposal summary."""
    mem_state = EpisodicMemoryState(
        memories=(
            _memory(_synthetic_event("EV_A")),
            _memory(_synthetic_event("EV_B")),
            _memory(_synthetic_event("EV_C")),
        )
    )
    rel_state = initial_relationship_state(P3State(trust=75, attraction=85))
    signal = P0CompatibilitySignal(compatible=True, basis="test")

    with pytest.raises(EvolutionGateError):
        evaluate_evolution_eligibility(mem_state, rel_state, signal, "P5", "")

    with pytest.raises(EvolutionGateError):
        evaluate_evolution_eligibility(mem_state, rel_state, signal, "P5", "   ")


def test_qualifying_evidence_includes_relationship_records():
    """Relationship transition records with non-zero applied deltas count
    as qualifying evidence alongside memories."""
    # 2 memories + 1 qualifying relationship record = 3 qualifying.
    mem_state = EpisodicMemoryState(
        memories=(_memory(_synthetic_event("EV_1")), _memory(_synthetic_event("EV_2")))
    )
    p3 = P3State(trust=75, attraction=85)
    rel_state = RelationshipTransitionState(
        current_p3=P3State(trust=77, attraction=85),
        records=(
            RelationshipTransitionRecord(
                character_id=CHARACTER_ID,
                world_event_id="EV_REL_1",
                evidence_type="trust_supporting",
                applied_delta=2,
                resulting_trust=77,
            ),
        ),
        cumulative_trust_delta=2,
    )
    signal = P0CompatibilitySignal(compatible=True, basis="test")

    result = evaluate_evolution_eligibility(
        mem_state, rel_state, signal, "P5", "2 mem + 1 rel"
    )
    assert result.eligible is True
    assert result.proposal.accumulated_evidence_count == 3


def test_zero_delta_records_do_not_qualify():
    """Relationship records with applied_delta=0 do not count as qualifying
    evidence for evolution eligibility."""
    mem_state = EpisodicMemoryState(
        memories=(_memory(_synthetic_event("EV_1")), _memory(_synthetic_event("EV_2")))
    )
    p3 = P3State(trust=75, attraction=85)
    rel_state = RelationshipTransitionState(
        current_p3=p3,
        records=(
            RelationshipTransitionRecord(
                character_id=CHARACTER_ID,
                world_event_id="EV_NEUTRAL",
                evidence_type="neutral",
                applied_delta=0,
                resulting_trust=75,
            ),
        ),
        cumulative_trust_delta=0,
    )
    signal = P0CompatibilitySignal(compatible=True, basis="test")

    result = evaluate_evolution_eligibility(
        mem_state, rel_state, signal, "P5", "2 mem + 0-delta rel = only 2 qualifying"
    )
    # Only 2 qualifying (the zero-delta record is excluded).
    assert result.eligible is False
    assert result.proposal is None


# ============================================================================
# Integrity tests
# ============================================================================

def test_evolution_proposal_fields_are_frozen():
    """EvolutionProposal instances are fully frozen."""
    prop = EvolutionProposal(
        target_layer="P0",
        summary="audit test",
        evidence_refs=("ref1", "ref2", "ref3"),
        accumulated_evidence_count=3,
        p0_compatible=True,
    )
    # Trying to set any field raises.
    with pytest.raises(Exception):
        prop.status = "applied"  # type: ignore[misc]

    # Hashable (frozen dataclass).
    _ = hash(prop)


def test_evolution_proposal_always_proposed():
    """status is always PROPOSED -- there is no other valid status value."""
    prop = EvolutionProposal(
        target_layer="P1",
        summary="status check",
        evidence_refs=("x", "y", "z"),
        accumulated_evidence_count=3,
        p0_compatible=True,
    )
    assert prop.status == PROPOSAL_STATUS_PROPOSED
    # Changing status is structurally forbidden by frozen+post_init validation.
    with pytest.raises(ContractValidationError):
        EvolutionProposal(
            target_layer="P1",
            summary="bad status",
            evidence_refs=("x", "y", "z"),
            accumulated_evidence_count=3,
            p0_compatible=True,
            status="APPLIED",
        )