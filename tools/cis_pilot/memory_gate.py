#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CIS Kira Pilot -- Slice 2 deterministic MEMORY_GATE and four-layer memory
representation.

Implements the owner-approved memory pipeline (CIS-Q6 / spec §6-§8 /
plan §14 Slice 2) as four DISTINCT, non-collapsible layers:

    WORLD_EVENT -> CHARACTER_PERCEPTION -> CHARACTER_INTERPRETATION
    -> CHARACTER_MEMORY  ->  deterministic MEMORY_GATE -> pilot episodic state

Mandatory invariant (CIS-Q6, OWNER_DECIDED): an objective event is never its
subjective memory. ``memory.retained_gist == world_event.objective_text`` is
structurally forbidden and fails closed -- it is never used as a shortcut.

The gate itself is fully deterministic (spec §8, CIS-Q11): a flat, unweighted
additive salience score over the seven approved signals (TD-10), a single
documented threshold constant, and provenance-identity dedup. Any LLM
gist/interpretation proposal lives OUTSIDE the gate behind an injected
callable (dependency injection); this module imports no provider, performs no
network or file I/O, and never writes canon. Slice 2 memory is EPISODIC ONLY
and IN-MEMORY ONLY: file persistence is deferred to Slice 4
(``local_runs/cis_pilot/``), relationship memory is Slice 3, and working scene
memory has no owning slice. P3 is never read or mutated here.

Slice-local contracts (``WorldEvent``, ``CharacterPerception``,
``CharacterInterpretation``, ``CharacterMemory``) are intentionally defined in
this module rather than ``contracts.py``, following the accepted Slice 1
precedent (``CisContextLayers``): they are Slice-2-scoped and
``contracts.py`` is outside this slice's write-set. Field shapes follow the
conceptual fields of spec §7 exactly; nothing beyond them is invented.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Tuple

from .contracts import ContractValidationError, MemoryEventSource

# ---------------------------------------------------------------------------
# TD-10 salience threshold (documented implementation default)
# ---------------------------------------------------------------------------
#
# TD-10 (plan §15) mandates a flat, unweighted additive score over the seven
# spec-named salience signals with "a documented, single threshold constant",
# and explicitly records OWNER_DECISION_REQUIRED: NO -- the numeric value is
# delegated to the implementation layer as an auditable constant.
#
# Derivation of the value 3 (not an arbitrary pick):
#   * The score range is 0..7 (seven boolean signals, unweighted sum).
#   * Both approved fixtures are spec-designed to be salient (killer Test 2
#     requires their use): ME-1 scores 4 (emotion + intimacy + recency +
#     P0-value link), ME-2 scores exactly 3 (emotion + threat + recency) from
#     their approved spec §6 content. Any threshold <= 3 keeps both.
#   * A null/trivial event (0-2 signals) must be discardable so the gate is
#     load-bearing, not a pass-through: threshold >= 3 guarantees a
#     no-signal event (score 0) and a weak event (score 1-2) are discarded.
#   * 3 is therefore the minimal value that (a) keeps both owner-approved
#     salient fixtures and (b) gives the gate real discard behavior, with
#     usable boundary tests at 2 / 3 / 4.
#
# This constant is module-level, integer, used by every gate decision, and is
# NOT configurable via env/provider/CLI. Changing it later is a threshold
# adjustment, not a new mechanic (TD-10).
MEMORY_SALIENCE_THRESHOLD = 3

# Gate decision outcomes (plain string constants -- no enum dependency).
DECISION_KEEP = "keep"
DECISION_DISCARD = "discard"
DECISION_DUPLICATE = "duplicate"
DECISION_CONFLICTED = "conflicted"

# CONFLICTED status marker (Concept §7: keep both versions, never average,
# block automatic promotion, human review for any later promotion).
CONFLICT_STATUS = "CONFLICTED"


class MemoryGateError(RuntimeError):
    """Fail-closed error for structurally invalid gate input (broken layer
    linkage, forbidden event==memory shortcut, salience inconsistency, or a
    wrong-type argument). Never silently substitutes a value."""


# ---------------------------------------------------------------------------
# Layer 0 -- WORLD_EVENT (objective, immutable)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WorldEvent:
    """Objective external fact (spec §7: event_id, world/save_ref,
    objective_text, participants, order/time). One per world; immutable;
    never becomes canon automatically. Built from the Slice 0
    ``MemoryEventSource`` fixture -- this module never reads scenario files.

    ``objective_text`` is the approved objective text: the Slice 0
    ``normalized_text`` when present (ME-1: subject-restored objective form
    fixed by spec §6), otherwise the exact ``literal_text`` (ME-2: confirmed
    first sentence only -- the second scenario sentence is not included).
    """

    event_id: str
    objective_text: str
    participants: Tuple[str, ...]
    scenario_repo_relative_path: str
    json_path: str
    source_sha256: str

    def __post_init__(self) -> None:
        _require_non_empty_str(self.event_id, "event_id")
        _require_non_empty_str(self.objective_text, "objective_text")
        _require_non_empty_str(self.scenario_repo_relative_path, "scenario_repo_relative_path")
        _require_non_empty_str(self.json_path, "json_path")
        _require_non_empty_str(self.source_sha256, "source_sha256")
        if "\\" in self.scenario_repo_relative_path or ":" in self.scenario_repo_relative_path:
            raise ContractValidationError(
                "scenario_repo_relative_path must be repo-relative POSIX, never an "
                f"absolute machine path: {self.scenario_repo_relative_path!r}"
            )
        if not isinstance(self.participants, tuple) or not self.participants:
            raise ContractValidationError("participants must be a non-empty tuple")
        for participant in self.participants:
            _require_non_empty_str(participant, "participant")

    @classmethod
    def from_memory_event_source(
        cls, source: MemoryEventSource, participants: Tuple[str, ...]
    ) -> "WorldEvent":
        """Build the objective layer from a Slice 0 ``MemoryEventSource``
        fixture. Structured input only -- no file reads."""
        if not isinstance(source, MemoryEventSource):
            raise ContractValidationError("source must be a MemoryEventSource instance")
        objective_text = (
            source.normalized_text if source.normalized_text is not None else source.literal_text
        )
        return cls(
            event_id=source.event_id,
            objective_text=objective_text,
            participants=participants,
            scenario_repo_relative_path=source.scenario_repo_relative_path,
            json_path=source.json_path,
            source_sha256=source.sha256,
        )


# ---------------------------------------------------------------------------
# Layer 1 -- CHARACTER_PERCEPTION (subjective noticing)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CharacterPerception:
    """What the character noticed (spec §7: character_id, world_event_ref,
    noticed, missed). Subjective; never equal to the WorldEvent; never
    becomes memory by itself. ``world_event_id`` keeps the provenance link
    to the objective layer."""

    character_id: str
    world_event_id: str
    noticed: str
    missed: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_non_empty_str(self.character_id, "character_id")
        _require_non_empty_str(self.world_event_id, "world_event_id")
        _require_non_empty_str(self.noticed, "noticed")
        if not isinstance(self.missed, tuple):
            raise ContractValidationError("missed must be a tuple (possibly empty)")


# ---------------------------------------------------------------------------
# Layer 2 -- CHARACTER_INTERPRETATION (belief / meaning)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CharacterInterpretation:
    """The meaning the character assigned (spec §7: character_id, meaning,
    emotional_coloring, belief_tag). Always tagged ``belief`` -- never
    ``fact``. Distinct from event, perception, and memory."""

    character_id: str
    world_event_id: str
    meaning: str
    emotional_coloring: str
    belief_tag: str = "belief"

    def __post_init__(self) -> None:
        _require_non_empty_str(self.character_id, "character_id")
        _require_non_empty_str(self.world_event_id, "world_event_id")
        _require_non_empty_str(self.meaning, "meaning")
        _require_non_empty_str(self.emotional_coloring, "emotional_coloring")
        if self.belief_tag != "belief":
            raise ContractValidationError(
                f"belief_tag must be 'belief', never 'fact': {self.belief_tag!r}"
            )


# ---------------------------------------------------------------------------
# Layer 3 -- CHARACTER_MEMORY (candidate subjective episodic memory)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CharacterMemory:
    """What and how the character remembers (spec §7: character_id, salience,
    retained_gist, possible_distortion, tags, provenance). A CANDIDATE until
    the deterministic gate accepts it. Embeds its ``world_event`` for
    provenance (repo-relative scenario path, JSON path, source SHA-256) --
    never an absolute machine path. Pilot episodic scope only: no
    relationship/P3 fields, no canon."""

    character_id: str
    world_event: WorldEvent
    retained_gist: str
    salience: int
    possible_distortion: Optional[str]
    tags: Tuple[str, ...]

    def __post_init__(self) -> None:
        _require_non_empty_str(self.character_id, "character_id")
        if not isinstance(self.world_event, WorldEvent):
            raise ContractValidationError("world_event must be a WorldEvent instance")
        _require_non_empty_str(self.retained_gist, "retained_gist")
        if isinstance(self.salience, bool) or not isinstance(self.salience, int):
            raise ContractValidationError("salience must be a plain int")
        if not 0 <= self.salience <= 7:
            raise ContractValidationError(
                f"salience must be within 0..7 (seven unweighted boolean signals), "
                f"got {self.salience}"
            )
        if self.possible_distortion is not None and not isinstance(self.possible_distortion, str):
            raise ContractValidationError("possible_distortion must be a string or None")
        if not isinstance(self.tags, tuple):
            raise ContractValidationError("tags must be a tuple (possibly empty)")
        # CIS-Q6 invariant, enforced at construction: the subjective memory
        # is never the objective event text.
        if self.retained_gist == self.world_event.objective_text:
            raise ContractValidationError(
                "retained_gist must not equal the WorldEvent objective_text "
                "(objective event != subjective memory)"
            )

    @property
    def provenance(self) -> str:
        """Human-readable provenance string (repo-relative only)."""
        return (
            f"derived from {self.world_event.event_id} @ "
            f"{self.world_event.scenario_repo_relative_path}#{self.world_event.json_path} "
            f"sha256:{self.world_event.source_sha256}"
        )


# ---------------------------------------------------------------------------
# Salience signals (TD-10: exactly seven, flat additive, unweighted)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SalienceSignals:
    """The seven approved salience signals (spec §8 / Concept §6):
    emotion, repetition, threat, promise, intimacy, recency, P0-value link.
    Boolean presence only -- no weights, no LLM score, no probabilistic
    score. ``score()`` is the flat deterministic sum."""

    emotion: bool
    repetition: bool
    threat: bool
    promise: bool
    intimacy: bool
    recency: bool
    p0_value_link: bool

    def __post_init__(self) -> None:
        for name in (
            "emotion",
            "repetition",
            "threat",
            "promise",
            "intimacy",
            "recency",
            "p0_value_link",
        ):
            if not isinstance(getattr(self, name), bool):
                raise ContractValidationError(f"{name} must be a bool")

    def score(self) -> int:
        return sum(
            (
                self.emotion,
                self.repetition,
                self.threat,
                self.promise,
                self.intimacy,
                self.recency,
                self.p0_value_link,
            )
        )


# ---------------------------------------------------------------------------
# Pilot episodic state (IN-MEMORY ONLY, immutable)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MemoryConflict:
    """Conflict evidence (Concept §7): both versions retained, status
    CONFLICTED, never averaged, never auto-resolved. Recording a conflict is
    not a canon write and not a promotion; any later promotion is a human
    decision outside Slice 2."""

    character_id: str
    world_event_id: str
    existing_gist: str
    conflicting_gist: str
    status: str = CONFLICT_STATUS

    def __post_init__(self) -> None:
        _require_non_empty_str(self.character_id, "character_id")
        _require_non_empty_str(self.world_event_id, "world_event_id")
        _require_non_empty_str(self.existing_gist, "existing_gist")
        _require_non_empty_str(self.conflicting_gist, "conflicting_gist")
        if self.status != CONFLICT_STATUS:
            raise ContractValidationError(f"status must be {CONFLICT_STATUS!r}")


@dataclass(frozen=True)
class EpisodicMemoryState:
    """The pilot-scope episodic memory: an immutable tuple of accepted
    ``CharacterMemory`` records plus conflict evidence. IN-MEMORY ONLY --
    no files, no SQLite, no pickle, no canon, no globals. The gate returns a
    NEW state instead of mutating (pure functional behavior)."""

    memories: Tuple[CharacterMemory, ...] = ()
    conflicts: Tuple[MemoryConflict, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.memories, tuple) or not isinstance(self.conflicts, tuple):
            raise ContractValidationError("memories and conflicts must be tuples")
        for memory in self.memories:
            if not isinstance(memory, CharacterMemory):
                raise ContractValidationError("memories must contain CharacterMemory instances")
        for conflict in self.conflicts:
            if not isinstance(conflict, MemoryConflict):
                raise ContractValidationError("conflicts must contain MemoryConflict instances")


@dataclass(frozen=True)
class MemoryGateResult:
    """Deterministic gate outcome: the decision plus the NEW episodic state
    (the input state is never mutated). ``reason`` is a stable, documented
    explanation string for auditability."""

    decision: str
    state: EpisodicMemoryState
    reason: str

    def __post_init__(self) -> None:
        if self.decision not in (
            DECISION_KEEP,
            DECISION_DISCARD,
            DECISION_DUPLICATE,
            DECISION_CONFLICTED,
        ):
            raise ContractValidationError(f"unknown gate decision: {self.decision!r}")
        if not isinstance(self.state, EpisodicMemoryState):
            raise ContractValidationError("state must be an EpisodicMemoryState instance")
        _require_non_empty_str(self.reason, "reason")


# ---------------------------------------------------------------------------
# Proposal injection (LLM-analytical step lives outside the gate)
# ---------------------------------------------------------------------------
#
# In the full architecture, interpretation/gist proposals are LLM-analytical
# steps (signal, not truth -- CIS-Q11). In Slice 2 they are injected
# callables; tests use deterministic stubs, and the approved spec §6 fixture
# content supplies the real pilot values. This module imports no provider
# and never will: provider binding is deferred (Slice 4/6).

InterpretationProposalFn = Callable[[WorldEvent, CharacterPerception], CharacterInterpretation]
GistProposalFn = Callable[[WorldEvent, CharacterPerception, CharacterInterpretation], str]


def propose_interpretation(
    proposal_fn: InterpretationProposalFn,
    world_event: WorldEvent,
    perception: CharacterPerception,
) -> CharacterInterpretation:
    """Call the injected interpretation proposal and validate its output
    against the layer contract (fail closed on wrong type or broken
    linkage). Deterministic given a deterministic ``proposal_fn``."""
    interpretation = proposal_fn(world_event, perception)
    if not isinstance(interpretation, CharacterInterpretation):
        raise MemoryGateError(
            f"interpretation proposal must return CharacterInterpretation, "
            f"got {type(interpretation).__name__}"
        )
    if interpretation.world_event_id != world_event.event_id:
        raise MemoryGateError(
            f"interpretation proposal broke event linkage: {interpretation.world_event_id!r} "
            f"!= {world_event.event_id!r}"
        )
    if interpretation.character_id != perception.character_id:
        raise MemoryGateError("interpretation proposal changed character_id")
    return interpretation


def propose_gist(
    gist_fn: GistProposalFn,
    world_event: WorldEvent,
    perception: CharacterPerception,
    interpretation: CharacterInterpretation,
) -> str:
    """Call the injected gist proposal and validate: non-empty string, never
    equal to the objective event text (CIS-Q6 shortcut forbidden)."""
    gist = gist_fn(world_event, perception, interpretation)
    if not isinstance(gist, str) or not gist.strip():
        raise MemoryGateError(f"gist proposal must return a non-empty string, got {gist!r}")
    if gist == world_event.objective_text:
        raise MemoryGateError(
            "gist proposal returned the objective event text -- the "
            "event_text == memory_text shortcut is forbidden (CIS-Q6)"
        )
    return gist


# ---------------------------------------------------------------------------
# Deterministic MEMORY_GATE
# ---------------------------------------------------------------------------


def evaluate_memory_candidate(
    world_event: WorldEvent,
    perception: CharacterPerception,
    interpretation: CharacterInterpretation,
    candidate: CharacterMemory,
    signals: SalienceSignals,
    state: EpisodicMemoryState,
) -> MemoryGateResult:
    """Deterministic keep / discard / duplicate / conflicted decision.

    Order of checks (all fail-closed or deterministic):

    1. Four-layer linkage: every layer must reference the same
       ``world_event.event_id`` and the same ``character_id``.
    2. CIS-Q6 invariant: ``candidate.retained_gist`` must not equal the
       objective event text (already enforced at construction; re-checked
       here so the gate itself is never bypassable).
    3. Salience consistency: ``candidate.salience`` must equal
       ``signals.score()`` (single source of truth for the score).
    4. Dedup by provenance identity (``character_id`` + ``event_id`` --
       approved source-event identity, never fuzzy string similarity):
       same gist again -> DECISION_DUPLICATE (no second record);
       different gist for the same event -> DECISION_CONFLICTED, both
       versions kept as conflict evidence, candidate NOT promoted
       (Concept §7: never average, never auto-pick, human-only promotion).
    5. Threshold: ``score >= MEMORY_SALIENCE_THRESHOLD`` -> keep (append to
       the new state); otherwise discard (state returned unchanged).

    No network, no provider, no file I/O, no canon write, no P3 access.
    """
    for name, value, expected_type in (
        ("world_event", world_event, WorldEvent),
        ("perception", perception, CharacterPerception),
        ("interpretation", interpretation, CharacterInterpretation),
        ("candidate", candidate, CharacterMemory),
        ("signals", signals, SalienceSignals),
        ("state", state, EpisodicMemoryState),
    ):
        if not isinstance(value, expected_type):
            raise MemoryGateError(f"{name} must be a {expected_type.__name__} instance")

    # 1. Four-layer linkage.
    if perception.world_event_id != world_event.event_id:
        raise MemoryGateError("perception is not linked to this world_event")
    if interpretation.world_event_id != world_event.event_id:
        raise MemoryGateError("interpretation is not linked to this world_event")
    if candidate.world_event.event_id != world_event.event_id:
        raise MemoryGateError("candidate is not linked to this world_event")
    if not (
        perception.character_id == interpretation.character_id == candidate.character_id
    ):
        raise MemoryGateError("character_id mismatch across layers")

    # 2. CIS-Q6 invariant (defense in depth -- construction already enforces).
    if candidate.retained_gist == world_event.objective_text:
        raise MemoryGateError(
            "candidate memory equals the objective event text (forbidden shortcut)"
        )

    # 3. Salience consistency.
    score = signals.score()
    if candidate.salience != score:
        raise MemoryGateError(
            f"candidate.salience ({candidate.salience}) != signals.score() ({score}); "
            "the gate score is the single source of truth"
        )

    # 4. Dedup / conflict by provenance identity.
    for existing in state.memories:
        if (
            existing.character_id == candidate.character_id
            and existing.world_event.event_id == world_event.event_id
        ):
            if existing.retained_gist == candidate.retained_gist:
                return MemoryGateResult(
                    decision=DECISION_DUPLICATE,
                    state=state,
                    reason=(
                        f"event {world_event.event_id!r} already recorded with the same "
                        "gist; no second episodic record created"
                    ),
                )
            conflict = MemoryConflict(
                character_id=candidate.character_id,
                world_event_id=world_event.event_id,
                existing_gist=existing.retained_gist,
                conflicting_gist=candidate.retained_gist,
            )
            return MemoryGateResult(
                decision=DECISION_CONFLICTED,
                state=EpisodicMemoryState(
                    memories=state.memories, conflicts=state.conflicts + (conflict,)
                ),
                reason=(
                    f"conflicting memory for event {world_event.event_id!r}: both versions "
                    "kept as CONFLICTED evidence, automatic promotion blocked (human review)"
                ),
            )

    # 5. Threshold keep/discard.
    if score >= MEMORY_SALIENCE_THRESHOLD:
        return MemoryGateResult(
            decision=DECISION_KEEP,
            state=EpisodicMemoryState(
                memories=state.memories + (candidate,), conflicts=state.conflicts
            ),
            reason=(
                f"salience {score} >= threshold {MEMORY_SALIENCE_THRESHOLD}; "
                "candidate accepted into pilot episodic state"
            ),
        )
    return MemoryGateResult(
        decision=DECISION_DISCARD,
        state=state,
        reason=(
            f"salience {score} < threshold {MEMORY_SALIENCE_THRESHOLD}; "
            "candidate discarded, no placeholder memory created"
        ),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_non_empty_str(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ContractValidationError(f"{field_name} must be a non-empty string")
