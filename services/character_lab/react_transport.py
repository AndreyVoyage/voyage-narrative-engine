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

Minimal API surface (deliberately): characters, workspaces, sessions, chat,
memory (raw events + operator-driven consolidated memory), Runtime State.
Scene / Debug are NOT exposed here yet.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from services.character_core.contract import (
    CONSOLIDATED_RELATION_KINDS,
    MEMORY_KINDS,
    PROMOTION_DECISIONS,
    CapabilitySet,
    ChatTurnResult,
    CharacterSession,
    CharacterSummary,
    CharacterVariantSummary,
    ConsolidatedMemoryRecordSummary,
    MemoryEventInspection,
    MemoryEventList,
    MemoryEventSummary,
    MemoryPromotionCandidateSummary,
    MemoryRelationSummary,
    MemorySummary,
    RuntimeStateEntrySummary,
    RuntimeStateSummary,
    SessionPurpose,
    SessionPurposeNotImplementedError,
    WorkspaceSummary,
)

from .service_adapter import (
    CharacterLabServiceAdapter,
    MemoryOperationError,
    RuntimeStateMutationError,
)

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


def _require_value_field(payload: dict) -> str:
    value = payload.get("value")
    if isinstance(value, bool):
        raise ReactTransportError(400, "invalid_value", "'value' must not be a boolean")
    if isinstance(value, (str, int)):
        text = str(value).strip()
        if text:
            return text
    raise ReactTransportError(400, "invalid_value", "'value' must be a non-empty value")


def _require_int_field(payload: dict, field: str) -> int:
    value = payload.get(field)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ReactTransportError(400, "invalid_delta", f"'{field}' must be an integer")
    return value


_RUNTIME_STATE_DOMAINS = ("FACT", "RELATIONSHIP", "PSYCHOLOGY")


def _require_domain(payload: dict) -> str:
    domain = _require_str_field(payload, "domain")
    if domain not in _RUNTIME_STATE_DOMAINS:
        raise ReactTransportError(
            400, "invalid_domain",
            f"'domain' must be one of {list(_RUNTIME_STATE_DOMAINS)}",
        )
    return domain


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


def _state_entry_to_json(e: RuntimeStateEntrySummary) -> dict:
    return {
        "domain": e.domain,
        "key": e.key,
        "value": e.value,
        "valueInt": e.value_int,
        "sourceKind": e.source_kind,
        "sourceRef": e.source_ref,
        "seq": e.seq,
    }


def _runtime_state_to_json(s: RuntimeStateSummary) -> dict:
    return {
        "workspaceId": s.workspace_id,
        "domainsActive": list(s.domains_active),
        "current": [_state_entry_to_json(e) for e in s.current],
        "currentCount": s.current_count,
    }


def _memory_to_json(m: MemorySummary) -> dict:
    return {
        "workspaceId": m.workspace_id,
        "causalOrder": m.causal_order,
        "eventCount": m.event_count,
        "events": [
            {
                "seq": e.seq,
                "eventId": e.event_id,
                "sessionId": e.session_id,
                "eventType": e.event_type,
                "provenance": e.provenance,
                "meaning": e.meaning,
            }
            for e in m.events
        ],
    }


def _memory_event_inspection_to_json(e: MemoryEventInspection) -> dict:
    return {
        "eventId": e.event_id,
        "seq": e.seq,
        "eventType": e.event_type,
        "provenance": e.provenance,
        "meaning": e.meaning,
        "subjectId": e.subject_id,
        "sessionId": e.session_id,
        "eligibleForPromotion": e.eligible_for_promotion,
        "ineligibilityReason": e.ineligibility_reason,
    }


def _memory_event_list_to_json(lst: MemoryEventList) -> dict:
    return {
        "workspaceId": lst.workspace_id,
        "causalOrder": lst.causal_order,
        "events": [_memory_event_inspection_to_json(e) for e in lst.events],
    }


def _candidate_to_json(c: MemoryPromotionCandidateSummary) -> dict:
    return {
        "candidateId": c.candidate_id,
        "sourceEventId": c.source_event_id,
        "memoryKind": c.memory_kind,
        "epistemicKind": c.epistemic_kind,
        "meaning": c.meaning,
        "provenance": c.provenance,
        "seq": c.seq,
        "decisionStatus": c.decision_status,
    }


def _record_to_json(r: ConsolidatedMemoryRecordSummary) -> dict:
    return {
        "recordId": r.record_id,
        "memoryKind": r.memory_kind,
        "epistemicKind": r.epistemic_kind,
        "meaning": r.meaning,
        "sourceEventId": r.source_event_id,
        "basisEventIds": list(r.basis_event_ids),
        "provenance": r.provenance,
        "status": r.status,
        "supersededByRecordId": r.superseded_by_record_id,
        "conflictRecordIds": list(r.conflict_record_ids),
        "seq": r.seq,
    }


def _relation_to_json(r: MemoryRelationSummary) -> dict:
    return {
        "relationId": r.relation_id,
        "kind": r.kind,
        "fromRecordId": r.from_record_id,
        "toRecordId": r.to_record_id,
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
    except RuntimeStateMutationError as exc:
        # Canonical backend rejection of a Runtime State mutation. Invalid
        # input (domain/key/value) is a client error (400); anything the
        # backend rejects because of current state (out-of-range result, ADJUST
        # on a missing/removed key) is a conflict (409).
        status = 400 if exc.code in ("invalid_domain", "invalid_key", "invalid_value") else 409
        raise ReactTransportError(status, exc.code, exc.message) from exc
    except MemoryOperationError as exc:
        # Canonical Consolidated Memory backend rejection. The backend's own
        # deliberately-written message is preserved verbatim; the deterministic
        # code lets the client branch without parsing prose. Bad references /
        # rule violations are conflicts (409); malformed input codes are 400.
        status = 400 if exc.code in ("invalid_memory_kind", "invalid_decision", "invalid_relation_kind") else 409
        raise ReactTransportError(status, exc.code, exc.message) from exc
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

    # --------------------------------------------------------------- memory

    def get_memory(self, workspace_id: str) -> dict:
        def op():
            return _memory_to_json(self._adapter.get_memory(workspace_id))
        return _run("workspace", op)

    # -------------------------------------------------- consolidated memory

    def list_memory_events(self, workspace_id: str) -> dict:
        def op():
            return _memory_event_list_to_json(self._adapter.list_memory_events(workspace_id))
        return _run("workspace", op)

    def list_memory_promotion_candidates(self, workspace_id: str) -> dict:
        def op():
            return {
                "candidates": [
                    _candidate_to_json(c)
                    for c in self._adapter.list_memory_promotion_candidates(workspace_id)
                ]
            }
        return _run("workspace", op)

    def propose_memory_promotion(self, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise _invalid_request("request body must be a JSON object")
        workspace_id = _require_str_field(payload, "workspaceId")
        source_event_id = _require_str_field(payload, "sourceEventId")
        memory_kind = _require_str_field(payload, "memoryKind")
        if memory_kind not in MEMORY_KINDS:
            raise ReactTransportError(
                400, "invalid_memory_kind",
                f"'memoryKind' must be one of {list(MEMORY_KINDS)}",
            )

        def op():
            return _candidate_to_json(
                self._adapter.propose_memory_promotion(
                    workspace_id, source_event_id, memory_kind
                )
            )
        return _run("workspace", op)

    def decide_memory_promotion(self, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise _invalid_request("request body must be a JSON object")
        workspace_id = _require_str_field(payload, "workspaceId")
        candidate_id = _require_str_field(payload, "candidateId")
        decision = _require_str_field(payload, "decision")
        if decision not in PROMOTION_DECISIONS:
            raise ReactTransportError(
                400, "invalid_decision",
                f"'decision' must be one of {list(PROMOTION_DECISIONS)}",
            )

        def op():
            return _candidate_to_json(
                self._adapter.decide_memory_promotion(workspace_id, candidate_id, decision)
            )
        return _run("workspace", op)

    def list_consolidated_memory(self, workspace_id: str) -> dict:
        def op():
            return {
                "records": [
                    _record_to_json(r)
                    for r in self._adapter.list_consolidated_memory(workspace_id)
                ]
            }
        return _run("workspace", op)

    def create_consolidated_memory_relation(self, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise _invalid_request("request body must be a JSON object")
        workspace_id = _require_str_field(payload, "workspaceId")
        from_record_id = _require_str_field(payload, "fromRecordId")
        to_record_id = _require_str_field(payload, "toRecordId")
        relation_type = _require_str_field(payload, "relationType")
        if relation_type not in CONSOLIDATED_RELATION_KINDS:
            raise ReactTransportError(
                400, "invalid_relation_kind",
                f"'relationType' must be one of {list(CONSOLIDATED_RELATION_KINDS)}",
            )

        def op():
            return _relation_to_json(
                self._adapter.create_consolidated_memory_relation(
                    workspace_id, from_record_id, to_record_id, relation_type
                )
            )
        return _run("workspace", op)

    # ---------------------------------------------------------- runtime state

    def get_runtime_state(self, workspace_id: str) -> dict:
        def op():
            return _runtime_state_to_json(self._adapter.get_runtime_state(workspace_id))
        return _run("workspace", op)

    def set_runtime_state(self, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise _invalid_request("request body must be a JSON object")
        workspace_id = _require_str_field(payload, "workspaceId")
        domain = _require_domain(payload)
        key = _require_str_field(payload, "key")
        value = _require_value_field(payload)
        source_ref = payload.get("sourceRef")

        def op():
            return _state_entry_to_json(
                self._adapter.set_runtime_state(workspace_id, domain, key, value, source_ref)
            )
        return _run("workspace", op)

    def adjust_runtime_state(self, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise _invalid_request("request body must be a JSON object")
        workspace_id = _require_str_field(payload, "workspaceId")
        domain = _require_domain(payload)
        key = _require_str_field(payload, "key")
        delta = _require_int_field(payload, "delta")
        source_ref = payload.get("sourceRef")

        def op():
            return _state_entry_to_json(
                self._adapter.adjust_runtime_state(workspace_id, domain, key, delta, source_ref)
            )
        return _run("workspace", op)

    def remove_runtime_state(self, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise _invalid_request("request body must be a JSON object")
        workspace_id = _require_str_field(payload, "workspaceId")
        domain = _require_domain(payload)
        key = _require_str_field(payload, "key")
        source_ref = payload.get("sourceRef")

        def op():
            return _state_entry_to_json(
                self._adapter.remove_runtime_state(workspace_id, domain, key, source_ref)
            )
        return _run("workspace", op)
