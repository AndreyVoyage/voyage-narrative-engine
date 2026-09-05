#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""React Character Lab desktop integration v1 -- HTTP/JSON transport layer.

This is an APPLICATION transport adapter for the React Character Lab client
only. It does NOT modify, extend, or redefine ``CharacterService`` /
``CharacterDebugService`` (``services/character_core/contract.py``), and it is
NOT documented anywhere as the canonical Character Core platform transport --
per OD-CHAR-PLATFORM-01(A), a transport is deliberately not chosen at the
Core level. Future clients may use IPC, a direct/local adapter, or another
transport entirely.

Dependency direction:

    tools/character_lab_react_server.py (HTTP framing: sockets, headers, JSON
    bytes on the wire)
            v
    ReactTransport (this module -- JSON dict <-> CharacterLabServiceAdapter)
            v
    CharacterLabServiceAdapter (services/character_lab/service_adapter.py,
    UNCHANGED)
            v
    CharacterLabApp / RuntimeService (UNCHANGED)

``ReactTransport`` contains NO duplicated character/runtime logic -- every
method is a thin translation: parse a plain JSON-safe ``dict`` into the
adapter's typed call, and serialize the adapter's typed DTO result back into a
plain JSON-safe ``dict``. It never touches sockets/HTTP itself, so it is fully
unit-testable without starting a server (see
``tests/character_lab/test_react_transport.py``).

Minimal API surface v1 (deliberately -- see the task boundary): characters,
workspaces, sessions, chat. Memory / Runtime State / Scene / Debug are NOT
exposed here yet.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from services.character_core.contract import (
    CapabilitySet,
    ChatTurnResult,
    CharacterSession,
    CharacterSummary,
    CharacterVariantSummary,
    SessionPurpose,
    SessionPurposeNotImplementedError,
    WorkspaceSummary,
)

from .service_adapter import CharacterLabServiceAdapter

__all__ = ["ReactTransportError", "ReactTransport"]


class ReactTransportError(Exception):
    """A deterministic, JSON-safe transport error.

    ``status`` is an HTTP status code (meaningful only to the HTTP framing
    layer -- this class itself has no HTTP dependency). ``code`` is one of a
    small fixed vocabulary the React client can branch on without parsing
    prose. The original Python exception (if any) is never serialized to the
    client -- no traceback, no internal message leakage beyond ``message``,
    which this module always sets to a short, deliberately-written string.
    """

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message

    def to_json(self) -> dict:
        return {"error": {"code": self.code, "message": self.message}}


def _invalid_request(message: str) -> ReactTransportError:
    return ReactTransportError(400, "invalid_request", message)


def _require_str_field(payload: dict, field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise _invalid_request(f"'{field}' must be a non-empty string")
    return value


# ------------------------------------------------------------- serialization

def _package_ref_to_json(ref) -> Optional[dict]:
    if ref is None:
        return None
    return {
        "characterId": ref.character_id,
        "packageId": ref.package_id,
        "packageVersion": ref.package_version,
        "sourceHash": ref.source_hash,
        "acceptanceDecision": ref.acceptance_decision,
        "candidateStatus": ref.candidate_status,
    }


def _character_to_json(c: CharacterSummary) -> dict:
    return {
        "characterId": c.character_id,
        "displayName": c.display_name,
        "supported": c.supported,
        "packageRef": _package_ref_to_json(c.package_ref),
    }


def _variant_to_json(v: CharacterVariantSummary) -> dict:
    return {
        "variantId": v.variant_id,
        "displayName": v.display_name,
        "implemented": v.implemented,
        "status": v.status,
        "selected": v.selected,
    }


def _capabilities_to_json(caps: CapabilitySet) -> dict:
    return {"capabilities": list(caps.capabilities)}


def _workspace_to_json(w: WorkspaceSummary) -> dict:
    return {
        "workspaceId": w.workspace_id,
        "workspaceKind": w.workspace_kind,
        "displayName": w.display_name,
        "selected": w.selected,
    }


def _session_to_json(s: CharacterSession) -> dict:
    return {
        "sessionId": s.session_id,
        "characterId": s.character_id,
        "variantId": s.variant_id,
        "purpose": s.purpose.value,
        "workspace": _workspace_to_json(s.workspace),
        "createdAt": s.created_at,
    }


def _chat_result_to_json(r: ChatTurnResult) -> dict:
    return {
        "turnId": r.turn_id,
        "sessionId": r.session_id,
        "characterId": r.character_id,
        "variantId": r.variant_id,
        "response": r.response,
        "requestHash": r.request_hash,
        "scenePresent": r.scene_present,
    }


def _parse_session_purpose(raw: Any) -> SessionPurpose:
    if not isinstance(raw, str) or not raw:
        raise _invalid_request("'purpose' must be a non-empty string")
    try:
        return SessionPurpose(raw)
    except ValueError:
        recognized = ", ".join(p.value for p in SessionPurpose)
        raise _invalid_request(
            f"'purpose' {raw!r} is not a recognized SessionPurpose "
            f"(recognized: {recognized})"
        ) from None


def _run(operation: str, fn: Callable[[], Dict[str, Any]]) -> Dict[str, Any]:
    """Execute one adapter call, translating its failure mode into a
    deterministic :class:`ReactTransportError` for this ``operation``.

    ``operation`` selects which kind of id a bare ``KeyError`` refers to --
    the adapter itself only ever raises a generic ``KeyError`` regardless of
    whether the missing thing was a character, workspace, or session, so the
    caller (which already knows what it asked for) supplies that context.
    """
    try:
        return fn()
    except SessionPurposeNotImplementedError as exc:
        raise ReactTransportError(
            501, "unsupported_purpose",
            f"SessionPurpose.{exc.purpose.value} is recognized but not "
            "implemented by this desktop integration",
        ) from exc
    except KeyError as exc:
        # The adapter raises a bare KeyError for every "unknown id" case
        # (character/workspace/session) -- e.g. create_session() alone can
        # fail on EITHER an unknown character_id or an unknown workspace_id.
        # Its message text ("unknown character '...'" / "unknown workspace
        # '...'" / "unknown session '...'") is a stable, deterministic string
        # from services/character_lab/{app,service_adapter}.py, so it -- not
        # just the call site -- decides the specific error code.
        text = str(exc).strip("'\"")
        if "unknown character" in text:
            code = "unknown_character"
        elif "unknown workspace" in text:
            code = "unknown_workspace"
        elif "unknown session" in text:
            code = "unknown_session"
        else:
            code = {
                "character": "unknown_character",
                "workspace": "unknown_workspace",
                "session": "unknown_session",
            }[operation]
        raise ReactTransportError(404, code, text) from exc
    except ValueError as exc:
        message = str(exc)
        if "disabled" in message.lower():
            raise ReactTransportError(409, "unavailable_variant", message) from exc
        raise ReactTransportError(404, "unknown_variant", message) from exc
    except ReactTransportError:
        raise
    except Exception as exc:  # noqa: BLE001 -- fail-closed, never leak a traceback
        # Concise server-side diagnostic only; the client never sees this.
        print(f"[react_transport] internal error in {operation}: {exc!r}")
        raise ReactTransportError(
            500, "internal_error", "internal server failure"
        ) from exc


class ReactTransport:
    """JSON-dict <-> ``CharacterLabServiceAdapter`` translation. No HTTP, no
    sockets, no runtime/character logic of its own -- see the module
    docstring for the full dependency direction."""

    def __init__(self, adapter: CharacterLabServiceAdapter) -> None:
        self._adapter = adapter

    # ------------------------------------------------------------- catalog

    def list_characters(self) -> dict:
        def op():
            return {"characters": [_character_to_json(c) for c in self._adapter.list_characters()]}
        return _run("character", op)

    def get_character(self, character_id: str) -> dict:
        def op():
            return _character_to_json(self._adapter.get_character(character_id))
        return _run("character", op)

    def list_variants(self, character_id: str) -> dict:
        def op():
            return {"variants": [_variant_to_json(v) for v in self._adapter.list_variants(character_id)]}
        return _run("character", op)

    def capabilities(self, character_id: str) -> dict:
        def op():
            return _capabilities_to_json(self._adapter.capabilities(character_id))
        return _run("character", op)

    # ----------------------------------------------------------- workspaces

    def list_workspaces(self) -> dict:
        def op():
            return {"workspaces": [_workspace_to_json(w) for w in self._adapter.list_workspaces()]}
        return _run("workspace", op)

    def create_test_workspace(self) -> dict:
        def op():
            return _workspace_to_json(self._adapter.create_test_workspace())
        return _run("workspace", op)

    def get_workspace(self, workspace_id: str) -> dict:
        def op():
            return _workspace_to_json(self._adapter.get_workspace(workspace_id))
        return _run("workspace", op)

    # ------------------------------------------------------------ sessions

    def create_session(self, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise _invalid_request("request body must be a JSON object")
        character_id = _require_str_field(payload, "characterId")
        variant_id = _require_str_field(payload, "variantId")
        workspace_id = _require_str_field(payload, "workspaceId")
        purpose = _parse_session_purpose(payload.get("purpose"))

        def op():
            return _session_to_json(
                self._adapter.create_session(character_id, variant_id, purpose, workspace_id)
            )
        return _run("workspace", op)

    def get_session(self, session_id: str) -> dict:
        def op():
            return _session_to_json(self._adapter.get_session(session_id))
        return _run("session", op)

    # ----------------------------------------------------------------- chat

    def send_message(self, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise _invalid_request("request body must be a JSON object")
        session_id = _require_str_field(payload, "sessionId")
        text = payload.get("text")
        if not isinstance(text, str) or not text.strip():
            raise _invalid_request("'text' must be a non-empty string")

        def op():
            return _chat_result_to_json(self._adapter.send_message(session_id, text))
        return _run("session", op)
