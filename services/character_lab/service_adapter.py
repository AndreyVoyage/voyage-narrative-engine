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

from services.character_core.contract import (
    CapabilitySet,
    ChatTurnResult,
    CharacterPackageRef,
    CharacterSession,
    CharacterSummary,
    CharacterVariantSummary,
    ContextManifestSummary,
    KNOWN_CAPABILITIES,
    ManifestItemSummary,
    MemoryEventSummary,
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

from .app import CharacterLabApp

__all__ = ["CharacterLabServiceAdapter", "CharacterLabDebugAdapter"]

#: The only character this adapter currently exposes. Not a Core-level
#: constraint -- just what the underlying CharacterLabApp presently loads.
_CHARACTER_ID = "kira"


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

    # ---------------------------------------------------------- runtime state
    # Runtime State is workspace-scoped (existing Character Lab semantics
    # exactly), same as memory.

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
