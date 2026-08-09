#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CIS Kira Pilot -- Slice 3 deterministic EVOLUTION_PROPOSAL_GATE.

Implements the owner-approved evolution proposal boundary (spec §10 /
plan §5, §9, §14 Slice 3 / TD-12 / CIS-Q11) as a pure, deterministic
eligibility gate:

    accumulated pilot evidence (S2 episodic memory + S3 relationship
    transitions) + injected P0-compatibility signal
        ->  eligibility check  ->  EvolutionProposal (PROPOSED, never applied)

Mandatory invariants:

* PROPOSAL-ONLY (plan §14 Slice 3 acceptance, CIS-Q11): the output is ALWAYS
  a proposal. There is NO code path in this module -- or anywhere in Slice 3
  -- that applies a proposal to P0/P1/P2/P5, writes ``personas/**``, or
  promotes anything to canon. Canon promotion is human-only.
* NOT-AGAINST-P0 (TD-12, Concept §12 Q13): a trajectory assessed as
  P0-incompatible is never eligible. The compatibility assessment is an
  INJECTED structured signal (analytical step, signal not truth); this module
  never reads psychology files and never renders P0 content.
* THRESHOLD (TD-12): ``EVOLUTION_PROPOSAL_THRESHOLD = 3`` applies the CIS
  Concept §12 Q13 advisory default ("параметр, начать с 3 + не против P0");
  TD-12 records OWNER_DECISION_REQUIRED: NO. It is a documented, auditable,
  non-configurable module-level constant, not a hidden literal.
* DETERMINISTIC: same inputs -> same eligibility and same proposal content.
  No randomness, no timestamps, no uuids, no provider, no network, no file
  I/O, no persistence (file output under ``local_runs/cis_pilot/`` is Slice 4
  territory and is not created here).

Slice-local contracts (``P0CompatibilitySignal``, ``EvolutionProposal``,
``EvolutionGateResult``) are intentionally defined in this module rather than
``contracts.py``, following the accepted Slice 1 (``CisContextLayers``) and
Slice 2 (``WorldEvent``/``CharacterMemory``) precedents: they are
Slice-3-scoped and ``contracts.py`` is outside this slice's write-set. The
plan §5 name ``EvolutionProposal`` is preserved exactly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from .contracts import ContractValidationError
from .memory_gate import EpisodicMemoryState
from .relationship_gate import RelationshipTransitionState

# ---------------------------------------------------------------------------
# TD-12 evolution accumulation threshold (Concept §12 Q13 advisory default)
# ---------------------------------------------------------------------------
#
# TD-12 (plan §15): a fixed small integer matching the CIS Concept document's
# own recommendation "параметр, начать с 3 + не против P0" -- applying the
# source document's stated advisory default is not inventing a new number.
# TD-12 explicitly records OWNER_DECISION_REQUIRED: NO.
#
# The pilot's single-session, single-relationship scope means this threshold
# will rarely trigger a real proposal in practice; it exists so that IF
# accumulated pilot evidence ever reaches it, the output is an auditable,
# unapplied proposal -- never a mutation.
EVOLUTION_PROPOSAL_THRESHOLD = 3

# Proposal status marker. The ONLY status a proposal can ever carry: there is
# no "applied"/"approved"/"promoted" status anywhere in Slice 3.
PROPOSAL_STATUS_PROPOSED = "PROPOSED"

# The psychological layers an evolution proposal may CONCERN (as a proposal
# target only -- never as a mutation target). P3 is pilot-mutable through the
# relationship gate and P4 is transient; neither is an evolution target.
ALLOWED_EVOLUTION_TARGET_LAYERS = ("P0", "P1", "P2", "P5")


class EvolutionGateError(RuntimeError):
    """Fail-closed error for structurally invalid gate input (wrong-type
    argument, invalid target layer, empty summary). Never silently
    substitutes a value."""


# ---------------------------------------------------------------------------
# Injected P0-compatibility signal (analytical step lives outside the gate)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class P0CompatibilitySignal:
    """Structured result of the not-against-P0 assessment (TD-12).

    In the full architecture this assessment is an LLM-analytical step
    (signal, not truth -- CIS-Q11); in Slice 3 it is injected by the caller
    and tests use deterministic values. This module never reads P0 files and
    never derives the signal itself. ``basis`` is a short audit note stating
    how the assessment was produced (e.g. "deterministic test stub").
    """

    compatible: bool
    basis: str

    def __post_init__(self) -> None:
        if not isinstance(self.compatible, bool):
            raise ContractValidationError("compatible must be a plain bool")
        _require_non_empty_str(self.basis, "basis")


# ---------------------------------------------------------------------------
# EvolutionProposal (proposal-only contract -- no applying methods by design)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EvolutionProposal:
    """An audit-ready, UNAPPLIED evolution proposal (plan §5).

    Data only. Deliberately has no ``apply``/``commit``/``promote``/
    ``write_canon``/``update_persona`` method and no persistence hook:
    constructing or holding a proposal changes nothing. ``p0_compatible``
    must be True -- a P0-incompatible trajectory is structurally incapable of
    producing a proposal (the gate never builds one, and this contract
    refuses one). ``status`` is always ``PROPOSED``; ``evidence_refs`` carries
    the provenance strings of every supporting evidence item so the proposal
    is fully auditable back to source.
    """

    target_layer: str
    summary: str
    evidence_refs: Tuple[str, ...]
    accumulated_evidence_count: int
    p0_compatible: bool
    status: str = PROPOSAL_STATUS_PROPOSED

    def __post_init__(self) -> None:
        if self.target_layer not in ALLOWED_EVOLUTION_TARGET_LAYERS:
            raise ContractValidationError(
                f"target_layer must be one of {ALLOWED_EVOLUTION_TARGET_LAYERS}, "
                f"got {self.target_layer!r}"
            )
        _require_non_empty_str(self.summary, "summary")
        if not isinstance(self.evidence_refs, tuple) or not self.evidence_refs:
            raise ContractValidationError("evidence_refs must be a non-empty tuple")
        for ref in self.evidence_refs:
            _require_non_empty_str(ref, "evidence_ref")
        if isinstance(self.accumulated_evidence_count, bool) or not isinstance(
            self.accumulated_evidence_count, int
        ):
            raise ContractValidationError("accumulated_evidence_count must be a plain int")
        if self.accumulated_evidence_count < EVOLUTION_PROPOSAL_THRESHOLD:
            raise ContractValidationError(
                f"accumulated_evidence_count ({self.accumulated_evidence_count}) below "
                f"threshold {EVOLUTION_PROPOSAL_THRESHOLD}; such a proposal must not exist"
            )
        if len(self.evidence_refs) != self.accumulated_evidence_count:
            raise ContractValidationError(
                f"evidence_refs count ({len(self.evidence_refs)}) != "
                f"accumulated_evidence_count ({self.accumulated_evidence_count})"
            )
        if self.p0_compatible is not True:
            raise ContractValidationError(
                "a P0-incompatible trajectory can never yield an EvolutionProposal "
                "(not-against-P0, TD-12)"
            )
        if self.status != PROPOSAL_STATUS_PROPOSED:
            raise ContractValidationError(f"status must be {PROPOSAL_STATUS_PROPOSED!r}")


@dataclass(frozen=True)
class EvolutionGateResult:
    """Deterministic eligibility outcome. ``proposal`` is present only when
    ``eligible`` is True. Inputs are never mutated; nothing is persisted."""

    eligible: bool
    proposal: Optional[EvolutionProposal]
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.eligible, bool):
            raise ContractValidationError("eligible must be a plain bool")
        if self.eligible and not isinstance(self.proposal, EvolutionProposal):
            raise ContractValidationError("an eligible result must carry an EvolutionProposal")
        if not self.eligible and self.proposal is not None:
            raise ContractValidationError("a non-eligible result must not carry a proposal")
        _require_non_empty_str(self.reason, "reason")


# ---------------------------------------------------------------------------
# Deterministic EVOLUTION_PROPOSAL_GATE
# ---------------------------------------------------------------------------


def evaluate_evolution_eligibility(
    memory_state: EpisodicMemoryState,
    relationship_state: RelationshipTransitionState,
    p0_compatibility: P0CompatibilitySignal,
    target_layer: str,
    proposal_summary: str,
) -> EvolutionGateResult:
    """Deterministic eligibility check for one evolution proposal.

    Qualifying evidence (plan §5: "accumulated pilot-scope changes from
    ``memory_gate.py``/``relationship_gate.py`` outputs across a session"):

    * every ACCEPTED ``CharacterMemory`` in the S2 episodic state (its
      provenance string is the audit ref), and
    * every S3 relationship transition record with a non-zero applied trust
      delta (neutral/duplicate/conflicted evidence does not qualify).

    Order of checks (all fail-closed or deterministic):

    1. Type checks on all five arguments; ``target_layer`` must be one of
       ``ALLOWED_EVOLUTION_TARGET_LAYERS``; ``proposal_summary`` must be a
       non-empty string.
    2. Accumulation threshold (TD-12): fewer than
       ``EVOLUTION_PROPOSAL_THRESHOLD`` qualifying evidence items -> not
       eligible, no proposal.
    3. Not-against-P0 (TD-12 / Concept §12 Q13): a P0-incompatible signal ->
       not eligible, no proposal.
    4. Otherwise eligible: build the ``EvolutionProposal`` (status PROPOSED,
       evidence refs in deterministic order: memories first, then
       relationship records, insertion order).

    The proposal is NEVER applied by anyone: this function only constructs
    the value object. No network, no provider, no file I/O, no canon write,
    no P0/P1/P2/P5 mutation.
    """
    if not isinstance(memory_state, EpisodicMemoryState):
        raise EvolutionGateError("memory_state must be an EpisodicMemoryState instance")
    if not isinstance(relationship_state, RelationshipTransitionState):
        raise EvolutionGateError(
            "relationship_state must be a RelationshipTransitionState instance"
        )
    if not isinstance(p0_compatibility, P0CompatibilitySignal):
        raise EvolutionGateError(
            "p0_compatibility must be a P0CompatibilitySignal instance"
        )
    if target_layer not in ALLOWED_EVOLUTION_TARGET_LAYERS:
        raise EvolutionGateError(
            f"target_layer must be one of {ALLOWED_EVOLUTION_TARGET_LAYERS}, "
            f"got {target_layer!r}"
        )
    if not isinstance(proposal_summary, str) or not proposal_summary.strip():
        raise EvolutionGateError("proposal_summary must be a non-empty string")

    evidence_refs = _qualifying_evidence_refs(memory_state, relationship_state)
    count = len(evidence_refs)

    if count < EVOLUTION_PROPOSAL_THRESHOLD:
        return EvolutionGateResult(
            eligible=False,
            proposal=None,
            reason=(
                f"accumulated qualifying evidence {count} < threshold "
                f"{EVOLUTION_PROPOSAL_THRESHOLD}; no proposal created"
            ),
        )
    if not p0_compatibility.compatible:
        return EvolutionGateResult(
            eligible=False,
            proposal=None,
            reason=(
                "trajectory assessed as AGAINST P0 "
                f"({p0_compatibility.basis}); proposal eligibility blocked "
                "(not-against-P0, TD-12)"
            ),
        )

    proposal = EvolutionProposal(
        target_layer=target_layer,
        summary=proposal_summary,
        evidence_refs=evidence_refs,
        accumulated_evidence_count=count,
        p0_compatible=True,
    )
    return EvolutionGateResult(
        eligible=True,
        proposal=proposal,
        reason=(
            f"accumulated qualifying evidence {count} >= threshold "
            f"{EVOLUTION_PROPOSAL_THRESHOLD} and trajectory is P0-compatible; "
            "proposal created with status PROPOSED -- never auto-applied, "
            "canon promotion is human-only (CIS-Q11)"
        ),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _qualifying_evidence_refs(
    memory_state: EpisodicMemoryState,
    relationship_state: RelationshipTransitionState,
) -> Tuple[str, ...]:
    """Deterministic provenance refs of qualifying pilot evidence.

    Accepted memories contribute their full provenance string; applied
    relationship transitions contribute a stable structural descriptor.
    Zero-delta records (neutral / fully capped) and conflict evidence never
    qualify. Order is deterministic: memories first, then relationship
    records, each in insertion order.
    """
    refs = [memory.provenance for memory in memory_state.memories]
    for record in relationship_state.records:
        if record.applied_delta != 0:
            refs.append(
                f"relationship:{record.character_id}:{record.world_event_id}:"
                f"{record.evidence_type}:delta{record.applied_delta:+d}"
            )
    return tuple(refs)


def _require_non_empty_str(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ContractValidationError(f"{field_name} must be a non-empty string")
