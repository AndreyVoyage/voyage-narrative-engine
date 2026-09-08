#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Local Character Lab adapter for the Character Core contract (v1 proof).

Dependency direction (OD-CHAR-PLATFORM-01(A)):

    Character Lab adapter (this module)
            v
    Character Core contract (services.character_core.contract)
            v
    existing Character Lab / runtime services (CharacterLabApp)

NOT the reverse -- ``services.character_core`` never imports this module or
anything under ``services.character_lab``.

This module does not reimplement any runtime/observability logic. It only
translates between the existing ``CharacterLabApp`` (constructed by the
caller, exactly as the server/tests already do -- fake or real provider
factory, acceptance root, data root) and the stable Character Core DTOs /
Protocols. No new behavior, no new persistence, no provider/network calls of
its own.

V1 scope: :data:`SessionPurpose.TESTING` only, using the existing Clean Test
workspace model. AUTHORING / GAME_RUNTIME / COMPANION are recognized by the
contract but explicitly NOT implemented here -- ``create_session`` raises
:class:`SessionPurposeNotImplementedError` for them rather than silently
mapping them to TESTING.
"""

from __future__ import annotations

from typing import Optional, Sequence, Tuple
from dataclasses import asdict

from services.character_runtime.state import RuntimeStateBackend
from services.character_runtime.evolution_store import EvolutionCandidateStore

from services.character_core.contract import (
    CapabilitySet,
    ChatTurnResult,
    CharacterPackageRef,
    CharacterSession,
    CharacterSummary,
    CharacterVariantSummary,
    ConsolidatedMemoryRecordSummary,
    ContextManifestSummary,
    KNOWN_CAPABILITIES,
    ManifestItemSummary,
    MemoryEventInspection,
    MemoryEventList,
    MemoryEventSummary,
    MemoryPromotionCandidateSummary,
    MemoryRelationSummary,
    MemorySummary,
    RequestCaptureSummary,
    RuntimeStateEntrySummary,
    RuntimeStateSummary,
    SceneSummary,
    SessionPurpose,
    SessionPurposeNotImplementedError,
    TurnDebugBundle,
    TurnSummary,
    WorkspaceSummary,
)

from services.character_runtime import RuntimeMemoryBackend
from services.character_runtime.consolidated_memory import (
    ConsolidatedMemoryBackend,
    ConsolidatedMemoryError,
    ELIGIBLE_SOURCE_EVENT_TYPES,
    PROVENANCE_USER_STATED,
)
from services.character_runtime.state import NUMERIC_DOMAINS, SOURCE_OPERATOR_CONFIRMED

from .app import CharacterLabApp
from .workspace import WorkspaceError

__all__ = [
    "CharacterLabServiceAdapter",
    "CharacterLabDebugAdapter",
    "RuntimeStateMutationError",
    "MemoryOperationError",
]

#: The only character this adapter currently exposes. Not a Core-level
#: constraint -- just what the underlying CharacterLabApp presently loads.
_CHARACTER_ID = "kira"


class RuntimeStateMutationError(RuntimeError):
    """A Runtime State mutation was rejected by the backend's canonical
    validation (invalid domain/key/value, out-of-range result, ADJUST on a
    missing/removed key, etc.).

    Carries the backend's deterministic ``code`` (e.g. ``invalid_key``,
    ``invalid_domain``, ``invalid_value``, ``state_rejected``) and a short,
    deliberately-written ``message``. Never a traceback or internal detail.

    Subclasses ``RuntimeError`` (NOT ``ValueError``) so the transport can map
    it to a specific, deterministic client error instead of the generic
    ``ValueError`` variant path.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class MemoryOperationError(RuntimeError):
    """A Consolidated Memory operation was rejected by the authoritative
    backend (``ConsolidatedMemoryBackend``).

    Carries a deterministic ``code`` (``ineligible_event``, ``unknown_event``,
    ``already_decided``, ``duplicate_record``, ``self_relation``,
    ``duplicate_relation``, ``unknown_record``, ``invalid_relation_kind``,
    ``invalid_memory_kind``, ``invalid_decision``, ``unknown_candidate``,
    ``cross_workspace``) plus the backend's own safe, deliberately-written
    ``message``. Never a traceback or SQLite internal.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


# Deterministic mapping from the backend's stable, deliberately-written error
# text (services/character_runtime/consolidated_memory.py) to a client-facing
# code. Order matters: first matching substring wins.
_MEMORY_ERROR_RULES = (
    ("ineligible:", "ineligible_event"),
    ("not found in this workspace", "unknown_event"),
    ("already decided", "already_decided"),
    ("duplicate:", "duplicate_record"),
    ("cannot relate to itself", "self_relation"),
    ("duplicate relation", "duplicate_relation"),
    ("does not exist", "unknown_record"),
    ("relation kind must be", "invalid_relation_kind"),
    ("different subject/workspace", "cross_workspace"),
    ("memory_kind must be", "invalid_memory_kind"),
    ("decision must be", "invalid_decision"),
    ("unknown candidate", "unknown_candidate"),
)


def _memory_error(exc: ConsolidatedMemoryError) -> MemoryOperationError:
    text = str(exc)
    for needle, code in _MEMORY_ERROR_RULES:
        if needle in text:
            return MemoryOperationError(code, text)
    return MemoryOperationError("memory_operation_rejected", text)


def assess_promotion_eligibility(event) -> "tuple[bool, Optional[str]]":
    """Service-side promotion eligibility view for ONE raw runtime event.

    Reuses the backend's own vocabulary constants
    (``ELIGIBLE_SOURCE_EVENT_TYPES`` / ``PROVENANCE_USER_STATED``) instead of
    redefining them. This is an INSPECTION projection only: the backend's
    ``propose()`` remains the sole authoritative gate at mutation time.
    """
    if event.event_type not in ELIGIBLE_SOURCE_EVENT_TYPES:
        return False, "not_a_user_message"
    if event.provenance != PROVENANCE_USER_STATED:
        return False, "not_user_stated"
    if not str(event.meaning).strip():
        return False, "empty_content"
    return True, None


def _state_int(value) -> "Optional[int]":
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _package_ref_from_loaded_state(loaded: dict) -> CharacterPackageRef:
    return CharacterPackageRef(
        character_id=loaded["character_id"],
        package_id=loaded["package_id"],
        package_version=loaded["package_version"],
        source_hash=loaded["accepted_source_hash"],
        acceptance_decision=loaded["acceptance_decision"],
        candidate_status=loaded["package_status"],
    )


def _workspace_summary_from_loaded_state(loaded: dict) -> WorkspaceSummary:
    return WorkspaceSummary(
        workspace_id=loaded["workspace_id"],
        workspace_kind=loaded["workspace_kind"],
        display_name=loaded["workspace_display_name"],
        selected=True,
    )


class CharacterLabServiceAdapter:
    """``CharacterService`` implemented directly over an existing
    ``CharacterLabApp`` instance (the "direct/local adapter" transport).

    ``CharacterLabApp`` is single-current-workspace/session stateful (exactly
    like the Character Lab UI: one selected workspace, one selected session at
    a time). This adapter keeps a small session_id -> workspace_id registry
    for the sessions IT created, so every per-session/per-workspace method can
    make the underlying app's "current" pointer correct before delegating --
    without inventing new storage semantics or duplicating
    ``WorkspaceManager``/``CharacterLabApp`` behavior.
    """

    def __init__(self, app: CharacterLabApp) -> None:
        self._app = app
        self._session_workspace: dict = {}

    # ------------------------------------------------------------- catalog

    def list_characters(self) -> Tuple[CharacterSummary, ...]:
        catalog = self._app.catalog()
        out = []
        for c in catalog["characters"]:
            ref = (
                _package_ref_from_loaded_state(self._app.loaded_state())
                if c["id"] == _CHARACTER_ID
                else None
            )
            out.append(
                CharacterSummary(
                    character_id=c["id"],
                    display_name=c["display_name"],
                    supported=c["supported"],
                    package_ref=ref,
                )
            )
        return tuple(out)

    def get_character(self, character_id: str) -> CharacterSummary:
        for summary in self.list_characters():
            if summary.character_id == character_id:
                return summary
        raise KeyError(f"unknown character {character_id!r}")

    def list_variants(self, character_id: str) -> Tuple[CharacterVariantSummary, ...]:
        self._require_known_character(character_id)
        catalog = self._app.catalog()
        return tuple(
            CharacterVariantSummary(
                variant_id=v["id"],
                display_name=v["display_name"],
                implemented=v["implemented"],
                status=v.get("status"),
                selected=v.get("selected", False),
            )
            for v in catalog["variants"]
        )

    def capabilities(self, character_id: str) -> CapabilitySet:
        self._require_known_character(character_id)
        health = self._app.health()
        caps = [
            "chat", "memory", "runtime_state", "relationship_state",
            "psychology_state", "scene", "turn_debugger",
        ]
        if health.get("provider_availability") == "CONFIGURED":
            caps.append("provider_configured")
        # every emitted capability name must be part of the known vocabulary
        assert all(c in KNOWN_CAPABILITIES for c in caps)
        return CapabilitySet(capabilities=tuple(caps))

    def _require_known_character(self, character_id: str) -> None:
        if character_id != _CHARACTER_ID:
            raise KeyError(f"unknown character {character_id!r}")

    # ----------------------------------------------------------- workspaces

    def list_workspaces(self) -> Tuple[WorkspaceSummary, ...]:
        data = self._app.list_workspaces()
        return tuple(
            WorkspaceSummary(
                workspace_id=w["workspace_id"], workspace_kind=w["workspace_kind"],
                display_name=w["display_name"], selected=w["selected"],
            )
            for w in data["workspaces"]
        )

    def get_workspace(self, workspace_id: str) -> WorkspaceSummary:
        for workspace in self.list_workspaces():
            if workspace.workspace_id == workspace_id:
                return workspace
        raise KeyError(f"unknown workspace {workspace_id!r}")

    def create_test_workspace(self) -> WorkspaceSummary:
        """Create a fresh, isolated CLEAN_TEST workspace. This is the ONLY
        way a new workspace comes into existence through this contract --
        :meth:`create_session` never creates one silently."""
        self._app.new_clean_test()
        return _workspace_summary_from_loaded_state(self._app.loaded_state())

    def _ensure_current_workspace(self, workspace_id: str) -> dict:
        loaded = self._app.loaded_state()
        if loaded.get("workspace_id") != workspace_id:
            self._app.select_workspace(workspace_id)  # raises KeyError if unknown
            loaded = self._app.loaded_state()
        return loaded

    # ------------------------------------------------------------ sessions

    def create_session(
        self,
        character_id: str,
        variant_id: str,
        purpose: SessionPurpose,
        workspace_id: str,
    ) -> CharacterSession:
        self._require_known_character(character_id)
        if purpose is not SessionPurpose.TESTING:
            raise SessionPurposeNotImplementedError(purpose)
        # workspace_id must already exist (from list_workspaces() /
        # create_test_workspace()); resolving it first means a bad id fails
        # before anything else is touched.
        self._ensure_current_workspace(workspace_id)
        selection = self._app.select_variant(variant_id)
        if not selection.get("ok"):
            raise ValueError(f"variant unavailable: {selection.get('message')}")
        # a NEW session in the ALREADY-EXISTING workspace -- multiple sessions
        # may share one workspace (e.g. for cross-session memory testing).
        created = self._app.new_session()
        self._session_workspace[created["session_id"]] = workspace_id
        loaded = self._app.loaded_state()
        return CharacterSession(
            session_id=created["session_id"],
            character_id=character_id,
            variant_id=loaded["variant_id"],
            purpose=purpose,
            workspace=_workspace_summary_from_loaded_state(loaded),
        )

    def _select(self, session_id: str) -> dict:
        """Make the underlying app's current workspace+session match
        ``session_id`` (a session this adapter created), then return the
        resulting ``loaded_state()``. Raises ``KeyError`` for any other id."""
        workspace_id = self._session_workspace.get(session_id)
        if workspace_id is None:
            raise KeyError(f"unknown session {session_id!r}")
        loaded = self._ensure_current_workspace(workspace_id)
        if loaded.get("session_id") != session_id:
            self._app.select_session(session_id)  # raises KeyError if truly gone
            loaded = self._app.loaded_state()
        return loaded

    def get_session(self, session_id: str) -> CharacterSession:
        loaded = self._select(session_id)
        return CharacterSession(
            session_id=session_id,
            character_id=loaded["character_id"],
            variant_id=loaded["variant_id"],
            purpose=SessionPurpose.TESTING,
            workspace=_workspace_summary_from_loaded_state(loaded),
        )

    # ----------------------------------------------------------------- chat

    def send_message(self, session_id: str, text: str) -> ChatTurnResult:
        self._select(session_id)
        result = self._app.chat(text, session_id)
        if not result.get("ok"):
            raise RuntimeError(result.get("message") or result.get("error") or "chat failed")
        loaded = self._app.loaded_state()
        return ChatTurnResult(
            turn_id=result["turn_id"],
            session_id=result["session_id"],
            character_id=loaded["character_id"],
            variant_id=loaded["variant_id"],
            response=result["response"],
            request_hash=result.get("request_hash"),
            scene_present=result.get("scene_present", False),
        )

    # --------------------------------------------------------------- memory
    # Memory is workspace-scoped (existing Character Lab semantics exactly):
    # every session in a workspace shares its memory, which is how
    # cross-session memory testing works.

    def get_memory(self, workspace_id: str) -> MemorySummary:
        self._ensure_current_workspace(workspace_id)
        data = self._app.memory()
        events = tuple(
            MemoryEventSummary(
                seq=e["seq"], event_id=e["event_id"], session_id=e["session_id"],
                event_type=e["event_type"], provenance=e["provenance"], meaning=e["meaning"],
            )
            for e in data["events"]
        )
        return MemorySummary(
            workspace_id=data["workspace_id"], causal_order=data["causal_order"],
            event_count=data["event_count"], events=events,
        )

    # -------------------------------------------------- consolidated memory
    # Operator-driven promotion over the accepted backends. The adapter opens
    # RuntimeMemoryBackend / ConsolidatedMemoryBackend against the EXPLICIT
    # workspace's own memory root and never reimplements backend validation.

    def _workspace_memory_root(self, workspace_id: str):
        """Resolve the explicit workspace's memory root (or KeyError)."""
        try:
            workspace = self._app._workspace_manager.get(workspace_id)
        except WorkspaceError as exc:
            raise KeyError(f"unknown workspace {workspace_id!r}") from exc
        return workspace.memory_root

    def list_memory_events(self, workspace_id: str) -> MemoryEventList:
        root = self._workspace_memory_root(workspace_id)
        backend = RuntimeMemoryBackend(root, _CHARACTER_ID)
        try:
            events = backend.load_events_causal(_CHARACTER_ID)
        finally:
            backend.close()
        inspected = []
        for e in events:
            eligible, reason = assess_promotion_eligibility(e)
            inspected.append(MemoryEventInspection(
                event_id=e.event_id, seq=e.seq, event_type=e.event_type,
                provenance=e.provenance or "LEGACY_UNCLASSIFIED", meaning=e.meaning,
                subject_id=e.subject_id, session_id=e.session_id,
                eligible_for_promotion=eligible, ineligibility_reason=reason,
            ))
        return MemoryEventList(
            workspace_id=workspace_id, causal_order="seq", events=tuple(inspected),
        )

    @staticmethod
    def _candidate_statuses(cons: ConsolidatedMemoryBackend) -> dict:
        statuses = {}
        for d in cons.load_decisions():
            statuses[d.candidate_id] = (
                "APPROVED" if d.decision == "APPROVE" else "REJECTED"
            )
        return statuses

    @staticmethod
    def _candidate_summary(candidate, status: str) -> MemoryPromotionCandidateSummary:
        return MemoryPromotionCandidateSummary(
            candidate_id=candidate.candidate_id,
            source_event_id=candidate.source_event_id,
            memory_kind=candidate.memory_kind,
            epistemic_kind=candidate.epistemic_kind,
            meaning=candidate.meaning,
            provenance=candidate.provenance,
            seq=candidate.seq,
            decision_status=status,
        )

    def list_memory_promotion_candidates(
        self, workspace_id: str
    ) -> Tuple[MemoryPromotionCandidateSummary, ...]:
        cons = ConsolidatedMemoryBackend(
            self._workspace_memory_root(workspace_id), _CHARACTER_ID
        )
        try:
            statuses = self._candidate_statuses(cons)
            candidates = cons.load_candidates()
        finally:
            cons.close()
        return tuple(
            self._candidate_summary(c, statuses.get(c.candidate_id, "PENDING"))
            for c in candidates
        )

    def propose_memory_promotion(
        self,
        workspace_id: str,
        source_event_id: str,
        memory_kind: str,
    ) -> MemoryPromotionCandidateSummary:
        root = self._workspace_memory_root(workspace_id)
        mem = RuntimeMemoryBackend(root, _CHARACTER_ID)
        cons = ConsolidatedMemoryBackend(root, _CHARACTER_ID)
        try:
            candidate = cons.propose(
                memory_backend=mem,
                source_event_id=source_event_id,
                memory_kind=memory_kind,
            )
        except ConsolidatedMemoryError as exc:
            raise _memory_error(exc) from exc
        finally:
            cons.close()
            mem.close()
        return self._candidate_summary(candidate, "PENDING")

    def decide_memory_promotion(
        self,
        workspace_id: str,
        candidate_id: str,
        decision: str,
    ) -> MemoryPromotionCandidateSummary:
        cons = ConsolidatedMemoryBackend(
            self._workspace_memory_root(workspace_id), _CHARACTER_ID
        )
        try:
            try:
                cons.decide(candidate_id=candidate_id, decision=decision)
            except ConsolidatedMemoryError as exc:
                raise _memory_error(exc) from exc
            statuses = self._candidate_statuses(cons)
            candidate = next(
                (c for c in cons.load_candidates() if c.candidate_id == candidate_id),
                None,
            )
        finally:
            cons.close()
        if candidate is None:  # pragma: no cover - decide() already validated
            raise MemoryOperationError("unknown_candidate", f"unknown candidate {candidate_id!r}")
        return self._candidate_summary(candidate, statuses[candidate_id])

    def list_consolidated_memory(
        self, workspace_id: str
    ) -> Tuple[ConsolidatedMemoryRecordSummary, ...]:
        cons = ConsolidatedMemoryBackend(
            self._workspace_memory_root(workspace_id), _CHARACTER_ID
        )
        try:
            records = cons.load_all_records()
            conflicts = cons.active_conflict_record_ids()
            relations = cons.load_relations()
        finally:
            cons.close()
        conflict_partners = {}
        for rel in relations:
            if rel.kind != "CONFLICTS_WITH":
                continue
            if rel.from_record_id in conflicts and rel.to_record_id in conflicts:
                conflict_partners.setdefault(rel.from_record_id, set()).add(rel.to_record_id)
                conflict_partners.setdefault(rel.to_record_id, set()).add(rel.from_record_id)
        return tuple(
            ConsolidatedMemoryRecordSummary(
                record_id=r.record_id,
                memory_kind=r.memory_kind,
                epistemic_kind=r.epistemic_kind,
                meaning=r.meaning,
                source_event_id=r.source_event_id,
                basis_event_ids=tuple(r.basis_event_ids),
                provenance=r.provenance,
                status=r.status,
                superseded_by_record_id=r.superseded_by_record_id,
                conflict_record_ids=tuple(sorted(conflict_partners.get(r.record_id, ()))),
                seq=r.seq,
            )
            for r in records
        )

    def create_consolidated_memory_relation(
        self,
        workspace_id: str,
        from_record_id: str,
        to_record_id: str,
        relation_type: str,
    ) -> MemoryRelationSummary:
        cons = ConsolidatedMemoryBackend(
            self._workspace_memory_root(workspace_id), _CHARACTER_ID
        )
        try:
            try:
                relation = cons.declare_relation(
                    from_record_id=from_record_id,
                    to_record_id=to_record_id,
                    kind=relation_type,
                )
            except ConsolidatedMemoryError as exc:
                raise _memory_error(exc) from exc
        finally:
            cons.close()
        return MemoryRelationSummary(
            relation_id=relation.relation_id,
            kind=relation.kind,
            from_record_id=relation.from_record_id,
            to_record_id=relation.to_record_id,
        )

    # ---------------------------------------------------------- runtime state
    # Runtime State is workspace-scoped (existing Character Lab semantics
    # exactly), same as memory.

    # Lab-local extension; does not change the Character Core protocol.
    def _evolution_backend(self, workspace_id):
        try:
            workspace = self._app._workspace_manager.get(workspace_id)
        except WorkspaceError as exc:
            raise KeyError(f"unknown workspace {workspace_id!r}") from exc
        return RuntimeStateBackend(workspace.state_root, _CHARACTER_ID)

    @staticmethod
    def _evolution_summary(row):
        candidate, decision, event_id = row
        return {**asdict(candidate),
                "decision": asdict(decision) if decision else None,
                "state_event_id": event_id}

    def list_evolution_candidates(self, workspace_id, *, status=None):
        backend = self._evolution_backend(workspace_id)
        try:
            return tuple(self._evolution_summary(row) for row in
                         EvolutionCandidateStore(backend).list_candidates(status=status))
        finally:
            backend.close()

    def create_evolution_candidate(self, workspace_id, **fields):
        backend = self._evolution_backend(workspace_id)
        try:
            candidate = EvolutionCandidateStore(backend).create_candidate(**fields)
            return self._evolution_summary((candidate, None, None))
        finally:
            backend.close()

    def decide_evolution_candidate(self, workspace_id, candidate_id, **fields):
        backend = self._evolution_backend(workspace_id)
        try:
            return self._evolution_summary(
                EvolutionCandidateStore(backend).decide_candidate(candidate_id, **fields))
        finally:
            backend.close()

    def get_runtime_state(self, workspace_id: str) -> RuntimeStateSummary:
        self._ensure_current_workspace(workspace_id)
        data = self._app.runtime_state()
        current = tuple(
            RuntimeStateEntrySummary(
                domain=e["domain"], key=e["key"], value=e["value"],
                value_int=e.get("value_int"), source_kind=e["source_kind"],
                source_ref=e.get("source_ref"), seq=e.get("seq"),
            )
            for e in data["current"]
        )
        return RuntimeStateSummary(
            workspace_id=data["workspace_id"],
            domains_active=tuple(data["domains_active"]),
            current=current, current_count=data["current_count"],
        )

    def _entry_from_event(self, event: dict) -> RuntimeStateEntrySummary:
        domain = event["domain"]
        value = event.get("value", "")
        numeric = domain in NUMERIC_DOMAINS
        return RuntimeStateEntrySummary(
            domain=domain,
            key=event["key"],
            value=value,
            value_int=_state_int(value) if numeric else None,
            source_kind=event.get("source_kind", SOURCE_OPERATOR_CONFIRMED),
            source_ref=event.get("source_ref"),
            seq=event.get("seq"),
        )

    def set_runtime_state(
        self,
        workspace_id: str,
        domain: str,
        key: str,
        value: str,
        source_ref: Optional[str] = None,
    ) -> RuntimeStateEntrySummary:
        self._ensure_current_workspace(workspace_id)
        result = self._app.runtime_state_set({
            "domain": domain, "key": key, "value": value, "source_ref": source_ref,
        })
        if not result.get("ok"):
            raise RuntimeStateMutationError(
                result.get("error", "state_rejected"),
                result.get("message", "state rejected"),
            )
        return self._entry_from_event(result["event"])

    def adjust_runtime_state(
        self,
        workspace_id: str,
        domain: str,
        key: str,
        delta: int,
        source_ref: Optional[str] = None,
    ) -> RuntimeStateEntrySummary:
        self._ensure_current_workspace(workspace_id)
        result = self._app.runtime_state_adjust({
            "domain": domain, "key": key, "delta": delta, "source_ref": source_ref,
        })
        if not result.get("ok"):
            raise RuntimeStateMutationError(
                result.get("error", "state_rejected"),
                result.get("message", "state rejected"),
            )
        return self._entry_from_event(result["event"])

    def remove_runtime_state(
        self,
        workspace_id: str,
        domain: str,
        key: str,
        source_ref: Optional[str] = None,
    ) -> RuntimeStateEntrySummary:
        self._ensure_current_workspace(workspace_id)
        result = self._app.runtime_state_remove({
            "domain": domain, "key": key, "source_ref": source_ref,
        })
        if not result.get("ok"):
            raise RuntimeStateMutationError(
                result.get("error", "state_rejected"),
                result.get("message", "state rejected"),
            )
        return self._entry_from_event(result["event"])

    # -------------------------------------------------------------- scene
    # Scene remains session-scoped (existing Character Lab semantics exactly).

    def get_scene(self, session_id: str) -> SceneSummary:
        loaded = self._select(session_id)
        data = self._app.get_scene()
        scene = data.get("scene") or {}
        return SceneSummary(
            session_id=data.get("session_id"), workspace_id=loaded.get("workspace_id"),
            active=data["active"], title=scene.get("title"), location=scene.get("location"),
            scene_hash=data.get("scene_hash"),
        )

    def set_scene(
        self,
        session_id: str,
        *,
        title: str = "",
        location: str = "",
        participants: Sequence[str] = (),
        prior_events: Sequence[str] = (),
        current_situation: str = "",
    ) -> SceneSummary:
        loaded = self._select(session_id)
        result = self._app.set_scene({
            "title": title, "location": location,
            "participants": list(participants), "prior_events": list(prior_events),
            "current_situation": current_situation,
        })
        if not result.get("ok"):
            raise ValueError(result.get("message") or "scene rejected")
        scene = result.get("scene") or {}
        return SceneSummary(
            session_id=result.get("session_id"), workspace_id=loaded.get("workspace_id"),
            active=True, title=scene.get("title"), location=scene.get("location"),
            scene_hash=result.get("scene_hash"),
        )

    def clear_scene(self, session_id: str) -> SceneSummary:
        loaded = self._select(session_id)
        result = self._app.clear_scene()
        return SceneSummary(
            session_id=result.get("session_id"), workspace_id=loaded.get("workspace_id"),
            active=False,
        )


class CharacterLabDebugAdapter:
    """``CharacterDebugService`` implemented directly over the same
    ``CharacterLabApp`` instance. Kept as a SEPARATE class/object from
    :class:`CharacterLabServiceAdapter` -- developer observability is never
    part of the normal consumer chat interface."""

    def __init__(self, app: CharacterLabApp) -> None:
        self._app = app

    def list_turns(self, session_id: Optional[str] = None) -> Tuple[TurnSummary, ...]:
        turns = self._app.list_turns()
        return tuple(
            TurnSummary(
                turn_id=t["turn_id"], session_id=t.get("session_id"), variant_id=None,
                request_hash=t.get("request_hash"), response_preview=t.get("response_preview"),
                scene_present=t.get("scene_present", False), has_error=t.get("has_error", False),
                created_at=t.get("created_at"),
            )
            for t in turns
            if session_id is None or t.get("session_id") == session_id
        )

    def _manifest_summary(self, detail: dict) -> ContextManifestSummary:
        manifest = detail["manifest"]
        items = tuple(
            ManifestItemSummary(
                kind=i["kind"], text=i["text"],
                selected=i.get("selected", True), delivered=i.get("delivered", False),
            )
            for i in manifest.get("items", [])
        )
        return ContextManifestSummary(
            turn_id=detail["turn_id"], variant_id=detail.get("variant_id"),
            assembly_hash=manifest.get("assembly_hash"), items=items,
        )

    def _request_summary(self, detail: dict) -> RequestCaptureSummary:
        request = detail["request"]
        return RequestCaptureSummary(
            turn_id=detail["turn_id"], request_hash=request.get("request_hash"),
            raw_request_json=request.get("raw"),
        )

    def get_turn_debug(self, turn_id: str) -> TurnDebugBundle:
        detail = self._app.turn_detail(turn_id)
        turn = TurnSummary(
            turn_id=detail["turn_id"], session_id=detail.get("session_id"),
            variant_id=detail.get("variant_id"),
            request_hash=detail["request"].get("request_hash"),
            response_preview=None,
            scene_present=(detail.get("scene") or {}).get("present", False),
            has_error=detail.get("error") is not None,
            created_at=None,
        )
        return TurnDebugBundle(
            turn=turn, manifest=self._manifest_summary(detail),
            request=self._request_summary(detail),
        )

    def get_request_capture(self, turn_id: str) -> RequestCaptureSummary:
        return self._request_summary(self._app.turn_detail(turn_id))

    def get_context_manifest(self, turn_id: str) -> ContextManifestSummary:
        return self._manifest_summary(self._app.turn_detail(turn_id))
