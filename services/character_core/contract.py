#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Character Core Release Boundary v1 -- transport-neutral service contract.

Per OD-CHAR-PLATFORM-01(A): Character Core is architecturally independent from
any particular UI or transport. This module defines the stable, serializable
boundary that any future client (Character Lab, Narrative Editor embedded
Core, a future Character App) talks to -- as plain Python types and a
structural :class:`typing.Protocol`, never HTTP verbs, URLs, status codes,
JSON envelopes, or browser concepts.

Standard library only. This module MUST NOT import ``services.character_lab``
or ``services.character_runtime`` -- concrete implementations live on the
OTHER side of this contract (see ``services.character_lab.service_adapter``
for the first proof-of-contract local adapter). No provider, no network, no
filesystem paths, no SQLite handles are exposed through these types.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Protocol, Sequence, Tuple, runtime_checkable

__all__ = [
    "SessionPurpose",
    "SessionPurposeNotImplementedError",
    "KNOWN_CAPABILITIES",
    "CapabilitySet",
    "CharacterPackageRef",
    "CharacterVariantSummary",
    "CharacterSummary",
    "WorkspaceSummary",
    "CharacterSession",
    "ChatTurnResult",
    "RuntimeStateEntrySummary",
    "RuntimeStateSummary",
    "MemoryEventSummary",
    "MemorySummary",
    "MEMORY_KIND_EPISODIC",
    "MEMORY_KIND_SEMANTIC",
    "MEMORY_KINDS",
    "PROMOTION_DECISION_APPROVE",
    "PROMOTION_DECISION_REJECT",
    "PROMOTION_DECISIONS",
    "CANDIDATE_STATUS_PENDING",
    "CANDIDATE_STATUS_APPROVED",
    "CANDIDATE_STATUS_REJECTED",
    "CONSOLIDATED_RELATION_SUPERSEDES",
    "CONSOLIDATED_RELATION_CONFLICTS_WITH",
    "CONSOLIDATED_RELATION_KINDS",
    "CONSOLIDATED_RECORD_STATUS_ACTIVE",
    "CONSOLIDATED_RECORD_STATUS_SUPERSEDED",
    "EPISTEMIC_USER_REPORT",
    "MemoryEventInspection",
    "MemoryEventList",
    "MemoryPromotionCandidateSummary",
    "ConsolidatedMemoryRecordSummary",
    "MemoryRelationSummary",
    "SceneSummary",
    "TurnSummary",
    "ManifestItemSummary",
    "ContextManifestSummary",
    "RequestCaptureSummary",
    "TurnDebugBundle",
    "CharacterService",
    "CharacterDebugService",
]


# --------------------------------------------------------------------------
# Session purpose
# --------------------------------------------------------------------------


class SessionPurpose(Enum):
    """Recognized architectural purposes a Character Core session may serve.

    Recognizing a purpose here is NOT the same as a concrete adapter
    implementing its behavioral policy today. Character Core Contract v1
    requires only :data:`SessionPurpose.TESTING` to have a working local
    adapter (see ``services.character_lab.service_adapter``). The others are
    reserved, forward-looking vocabulary -- their semantics are explicitly
    deferred, not invented here.
    """

    TESTING = "TESTING"
    AUTHORING = "AUTHORING"
    GAME_RUNTIME = "GAME_RUNTIME"
    COMPANION = "COMPANION"


class SessionPurposeNotImplementedError(NotImplementedError):
    """Raised when a recognized :class:`SessionPurpose` has no implementation
    in the adapter that was asked to create a session for it.

    A deterministic, explicit failure -- never a silent fallback to TESTING.
    """

    def __init__(self, purpose: SessionPurpose) -> None:
        self.purpose = purpose
        super().__init__(
            f"SessionPurpose.{purpose.name} is a recognized architectural "
            "purpose but is not implemented by this adapter"
        )


# --------------------------------------------------------------------------
# Capabilities
# --------------------------------------------------------------------------

#: The full vocabulary of capability names a backend MAY resolve as present.
#: A concrete adapter returns only the subset it actually backs, so a client
#: can render supported functionality without hard-coding character/backend
#: assumptions (e.g. ``if character == "kira"``).
KNOWN_CAPABILITIES: Tuple[str, ...] = (
    "chat",
    "memory",
    "runtime_state",
    "relationship_state",
    "psychology_state",
    "scene",
    "turn_debugger",
    "provider_configured",
)


@dataclass(frozen=True)
class CapabilitySet:
    """Backend-resolved capabilities for one character, as opaque flags."""

    capabilities: Tuple[str, ...] = ()

    def has(self, name: str) -> bool:
        return name in self.capabilities


# --------------------------------------------------------------------------
# Character / package / variant / workspace DTOs
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class CharacterPackageRef:
    """Identifies an Accepted Character Package independently from Core.

    Per OD-CHAR-CORE-RELEASE-01(A): Character Core and Character Package have
    independent versions. This is a REFERENCE only -- identity + acceptance
    status -- never the package's claims/content.
    """

    character_id: str
    package_id: str
    package_version: int
    source_hash: str
    acceptance_decision: str
    candidate_status: str


@dataclass(frozen=True)
class CharacterVariantSummary:
    """One selectable runtime policy (Variant) for a character."""

    variant_id: str
    display_name: str
    implemented: bool
    status: Optional[str] = None
    selected: bool = False


@dataclass(frozen=True)
class CharacterSummary:
    """One character as the contract exposes it to a client."""

    character_id: str
    display_name: str
    supported: bool
    package_ref: Optional[CharacterPackageRef] = None


@dataclass(frozen=True)
class WorkspaceSummary:
    """Minimal, path-free workspace identity: no filesystem path, no SQLite
    filename, no turn-capture directory -- only ``workspace_id`` (an opaque
    token), ``workspace_kind`` (``CLEAN_TEST`` / ``NORMAL``), and a display
    name. V1 scope: TESTING sessions only, using the existing Character Lab
    Clean Test / Normal workspace model -- a workspace may host MULTIPLE
    sessions (see :meth:`CharacterService.create_session`). Future
    AUTHORING / GAME_RUNTIME / COMPANION storage semantics are deferred and
    NOT generalized here.
    """

    workspace_id: str
    workspace_kind: str
    display_name: str
    selected: bool = False


@dataclass(frozen=True)
class CharacterSession:
    """A live session bound to one character + variant + purpose, hosted in
    exactly one explicit workspace (never silently created)."""

    session_id: str
    character_id: str
    variant_id: str
    purpose: SessionPurpose
    workspace: WorkspaceSummary
    created_at: Optional[str] = None


@dataclass(frozen=True)
class ChatTurnResult:
    """Result of one chat turn through :meth:`CharacterService.send_message`."""

    turn_id: str
    session_id: str
    character_id: str
    variant_id: str
    response: str
    request_hash: Optional[str] = None
    scene_present: bool = False


# --------------------------------------------------------------------------
# Runtime State / Memory / Scene DTOs
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class RuntimeStateEntrySummary:
    """One current Runtime State fact (FACT / RELATIONSHIP / PSYCHOLOGY)."""

    domain: str
    key: str
    value: str
    value_int: Optional[int]
    source_kind: str
    source_ref: Optional[str]
    seq: Optional[int]


@dataclass(frozen=True)
class RuntimeStateSummary:
    """Current Runtime State for one workspace (explicitly operator-confirmed
    only -- see ``services.character_runtime.state``; never automatically
    promoted from memory, model output, or Scene)."""

    workspace_id: str
    domains_active: Tuple[str, ...]
    current: Tuple[RuntimeStateEntrySummary, ...] = ()
    current_count: int = 0


@dataclass(frozen=True)
class MemoryEventSummary:
    """One causal runtime-memory event, with its honest provenance label."""

    seq: Optional[int]
    event_id: str
    session_id: str
    event_type: str
    provenance: str
    meaning: str


@dataclass(frozen=True)
class MemorySummary:
    """Causal-order runtime memory for one workspace."""

    workspace_id: str
    causal_order: str
    event_count: int
    events: Tuple[MemoryEventSummary, ...] = ()


# --------------------------------------------------------------------------
# Consolidated Memory (operator-driven promotion) vocabulary + DTOs
# --------------------------------------------------------------------------

# Plain-string vocabulary mirroring the Consolidated Memory V1 backend's
# values (``services.character_runtime.consolidated_memory``), so clients can
# render/branch on them without importing backend modules. The BACKEND remains
# the sole authority on validation -- these constants never weaken its checks.

MEMORY_KIND_EPISODIC = "EPISODIC"
MEMORY_KIND_SEMANTIC = "SEMANTIC"
#: The only two memory kinds in V1.
MEMORY_KINDS: Tuple[str, ...] = (MEMORY_KIND_EPISODIC, MEMORY_KIND_SEMANTIC)

PROMOTION_DECISION_APPROVE = "APPROVE"
PROMOTION_DECISION_REJECT = "REJECT"
#: Operator decisions over a promotion candidate.
PROMOTION_DECISIONS: Tuple[str, ...] = (
    PROMOTION_DECISION_APPROVE,
    PROMOTION_DECISION_REJECT,
)

CANDIDATE_STATUS_PENDING = "PENDING"
CANDIDATE_STATUS_APPROVED = "APPROVED"
CANDIDATE_STATUS_REJECTED = "REJECTED"

CONSOLIDATED_RELATION_SUPERSEDES = "SUPERSEDES"
CONSOLIDATED_RELATION_CONFLICTS_WITH = "CONFLICTS_WITH"
#: The only two operator-declarable relations between approved records.
CONSOLIDATED_RELATION_KINDS: Tuple[str, ...] = (
    CONSOLIDATED_RELATION_SUPERSEDES,
    CONSOLIDATED_RELATION_CONFLICTS_WITH,
)

CONSOLIDATED_RECORD_STATUS_ACTIVE = "ACTIVE"
CONSOLIDATED_RECORD_STATUS_SUPERSEDED = "SUPERSEDED"

#: V1 only ever promotes user reports. ``USER_REPORT`` == "the user stated
#: this" -- never an independently confirmed world fact.
EPISTEMIC_USER_REPORT = "USER_REPORT"


@dataclass(frozen=True)
class MemoryEventInspection:
    """One raw runtime-memory event WITH its promotion eligibility.

    ``eligible_for_promotion`` / ``ineligibility_reason`` are computed by the
    SERVICE side (adapter) reusing the backend's own vocabulary constants; the
    backend's ``propose()`` remains the sole authoritative gate at mutation
    time. A client must never re-derive eligibility itself.
    """

    event_id: str
    seq: Optional[int]
    event_type: str
    provenance: str
    meaning: str
    subject_id: str
    session_id: str
    eligible_for_promotion: bool
    ineligibility_reason: Optional[str] = None


@dataclass(frozen=True)
class MemoryEventList:
    """Raw workspace memory events annotated for operator inspection."""

    workspace_id: str
    causal_order: str
    events: Tuple[MemoryEventInspection, ...] = ()


@dataclass(frozen=True)
class MemoryPromotionCandidateSummary:
    """One promotion candidate with its derived decision status."""

    candidate_id: str
    source_event_id: str
    memory_kind: str
    epistemic_kind: str
    meaning: str
    provenance: str
    seq: Optional[int]
    decision_status: str  # PENDING / APPROVED / REJECTED


@dataclass(frozen=True)
class ConsolidatedMemoryRecordSummary:
    """One approved consolidated record, with derived status + conflicts."""

    record_id: str
    memory_kind: str
    epistemic_kind: str
    meaning: str
    source_event_id: str
    basis_event_ids: Tuple[str, ...]
    provenance: str
    status: str  # ACTIVE / SUPERSEDED (derived, never stored mutable)
    superseded_by_record_id: Optional[str] = None
    conflict_record_ids: Tuple[str, ...] = ()
    seq: Optional[int] = None


@dataclass(frozen=True)
class MemoryRelationSummary:
    """One operator-declared relation between two approved records."""

    relation_id: str
    kind: str  # SUPERSEDES / CONFLICTS_WITH
    from_record_id: str
    to_record_id: str


@dataclass(frozen=True)
class SceneSummary:
    """Session-scoped situational Scene setup (never Accepted Package data,
    never durable memory)."""

    session_id: Optional[str]
    workspace_id: Optional[str]
    active: bool
    title: Optional[str] = None
    location: Optional[str] = None
    scene_hash: Optional[str] = None


# --------------------------------------------------------------------------
# Debug / observability DTOs
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class TurnSummary:
    """One captured turn, listing-level detail only."""

    turn_id: str
    session_id: Optional[str]
    variant_id: Optional[str]
    request_hash: Optional[str]
    response_preview: Optional[str]
    scene_present: bool
    has_error: bool
    created_at: Optional[str]


@dataclass(frozen=True)
class ManifestItemSummary:
    """One assembly-manifest item: request text mapped back to its source,
    with SELECTED (always true for a captured item) / DELIVERED proven only
    from the exact captured provider request bytes."""

    kind: str
    text: str
    selected: bool
    delivered: bool


@dataclass(frozen=True)
class ContextManifestSummary:
    """The deterministic assembly manifest for one turn."""

    turn_id: str
    variant_id: Optional[str]
    assembly_hash: Optional[str]
    items: Tuple[ManifestItemSummary, ...] = ()


@dataclass(frozen=True)
class RequestCaptureSummary:
    """The exact captured transport request for one turn (source of truth
    for DELIVERED) -- never provider reasoning/chain-of-thought, which this
    contract does not expose at all."""

    turn_id: str
    request_hash: Optional[str]
    raw_request_json: Optional[str] = None


@dataclass(frozen=True)
class TurnDebugBundle:
    """One turn's full developer-observability bundle."""

    turn: TurnSummary
    manifest: ContextManifestSummary
    request: RequestCaptureSummary


# --------------------------------------------------------------------------
# Service contracts
# --------------------------------------------------------------------------


@runtime_checkable
class CharacterService(Protocol):
    """Transport-neutral consumer-facing Character Core contract.

    Every future client (Character Lab, Narrative Editor embedded Core, a
    future Character App) is a client of THIS logical contract, regardless of
    transport (direct/local adapter, IPC, localhost HTTP, remote HTTP, a
    test/mock adapter). No transport is selected as canonical here.

    Workspace ownership is explicit, not global mutable state: a workspace is
    resolved (:meth:`list_workspaces` / :meth:`get_workspace`) or newly
    created (:meth:`create_test_workspace`) BEFORE a session is created in it,
    and ``workspace_id`` is then passed explicitly to :meth:`create_session`
    -- it must already exist; a session is never given a silently-created
    workspace. One workspace may host multiple sessions (e.g. for
    cross-session memory testing).

    Scope, matching the existing Character Lab semantics exactly:

    - Memory is workspace-scoped (:meth:`get_memory`);
    - Runtime State is workspace-scoped (:meth:`get_runtime_state`);
    - Scene is session-scoped (:meth:`get_scene` / :meth:`set_scene` /
      :meth:`clear_scene`).
    """

    def list_characters(self) -> Tuple[CharacterSummary, ...]: ...

    def get_character(self, character_id: str) -> CharacterSummary: ...

    def list_variants(self, character_id: str) -> Tuple[CharacterVariantSummary, ...]: ...

    def capabilities(self, character_id: str) -> CapabilitySet: ...

    def list_workspaces(self) -> Tuple[WorkspaceSummary, ...]: ...

    def get_workspace(self, workspace_id: str) -> WorkspaceSummary: ...

    def create_test_workspace(self) -> WorkspaceSummary: ...

    def create_session(
        self,
        character_id: str,
        variant_id: str,
        purpose: SessionPurpose,
        workspace_id: str,
    ) -> CharacterSession: ...

    def get_session(self, session_id: str) -> CharacterSession: ...

    def send_message(self, session_id: str, text: str) -> ChatTurnResult: ...

    def get_memory(self, workspace_id: str) -> MemorySummary: ...

    # -------------------------------------------------- consolidated memory
    # Operator-driven, human-approved Consolidated Memory (V1). The service
    # side validates against the authoritative backend; a client only ever
    # selects an event / a candidate / two records and confirms an action.

    def list_memory_events(self, workspace_id: str) -> MemoryEventList: ...

    def list_memory_promotion_candidates(
        self, workspace_id: str
    ) -> Tuple[MemoryPromotionCandidateSummary, ...]: ...

    def propose_memory_promotion(
        self,
        workspace_id: str,
        source_event_id: str,
        memory_kind: str,
    ) -> MemoryPromotionCandidateSummary: ...

    def decide_memory_promotion(
        self,
        workspace_id: str,
        candidate_id: str,
        decision: str,
    ) -> MemoryPromotionCandidateSummary: ...

    def list_consolidated_memory(
        self, workspace_id: str
    ) -> Tuple[ConsolidatedMemoryRecordSummary, ...]: ...

    def create_consolidated_memory_relation(
        self,
        workspace_id: str,
        from_record_id: str,
        to_record_id: str,
        relation_type: str,
    ) -> MemoryRelationSummary: ...

    def get_runtime_state(self, workspace_id: str) -> RuntimeStateSummary: ...

    def set_runtime_state(
        self,
        workspace_id: str,
        domain: str,
        key: str,
        value: str,
        source_ref: Optional[str] = None,
    ) -> RuntimeStateEntrySummary: ...

    def adjust_runtime_state(
        self,
        workspace_id: str,
        domain: str,
        key: str,
        delta: int,
        source_ref: Optional[str] = None,
    ) -> RuntimeStateEntrySummary: ...

    def remove_runtime_state(
        self,
        workspace_id: str,
        domain: str,
        key: str,
        source_ref: Optional[str] = None,
    ) -> RuntimeStateEntrySummary: ...

    def get_scene(self, session_id: str) -> SceneSummary: ...

    def set_scene(
        self,
        session_id: str,
        *,
        title: str = "",
        location: str = "",
        participants: Sequence[str] = (),
        prior_events: Sequence[str] = (),
        current_situation: str = "",
    ) -> SceneSummary: ...

    def clear_scene(self, session_id: str) -> SceneSummary: ...


@runtime_checkable
class CharacterDebugService(Protocol):
    """Developer-observability contract -- explicitly SEPARATE from
    :class:`CharacterService`. A normal chat client never needs this; it is
    for a Turn Debugger / Character Inspector style consumer only. Never
    exposes hidden reasoning -- only the deterministic assembly manifest and
    the exact captured transport request (the same evidence
    ``services.character_lab.turn_capture`` already produces)."""

    def list_turns(self, session_id: str) -> Tuple[TurnSummary, ...]: ...

    def get_turn_debug(self, turn_id: str) -> TurnDebugBundle: ...

    def get_request_capture(self, turn_id: str) -> RequestCaptureSummary: ...

    def get_context_manifest(self, turn_id: str) -> ContextManifestSummary: ...
