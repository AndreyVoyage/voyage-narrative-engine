#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""JSON-dict <-> :class:`CompanionService` translation for the Companion client.

Mirrors the Character Lab ``ReactTransport`` pattern: no HTTP, no sockets, no
character/runtime logic of its own -- every method parses a plain JSON-safe
dict into a typed service call and serializes the typed result back. Fully
unit-testable without a server.

This transport exposes ONLY the five Companion operations. It never exposes any
Character Lab debug / operator / workspace / memory-editor / evolution surface.
"""

from __future__ import annotations

from typing import Any, Callable, Dict

from .service import (
    CompanionError,
    CompanionMessage,
    CompanionProviderError,
    CompanionService,
    CompanionSession,
)

__all__ = ["CompanionTransportError", "CompanionTransport"]

_STATUS_BY_CODE = {
    "unknown_character": 404,
    "unknown_session": 404,
    "empty_message": 400,
    "invalid_request": 400,
    "provider_failed": 502,
    "provider_unavailable": 503,
}


class CompanionTransportError(Exception):
    """Deterministic, JSON-safe transport error. No traceback ever reaches the
    client; ``message`` is always a short deliberately-written string."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message

    def to_json(self) -> dict:
        return {"error": {"code": self.code, "message": self.message}}


def _require_str(payload: dict, field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise CompanionTransportError(400, "invalid_request", f"'{field}' must be a non-empty string")
    return value


def _character_to_json(entry) -> dict:
    return {
        "characterId": entry.character_id,
        "displayName": entry.display_name,
        "packageId": entry.package_id,
        "packageVersion": entry.package_version,
        "sourceHash": entry.source_hash,
    }


def _session_to_json(s: CompanionSession) -> dict:
    return {
        "sessionId": s.session_id,
        "characterId": s.character_id,
        "purpose": s.purpose,
        "createdAt": s.created_at,
        "updatedAt": s.updated_at,
        "label": s.label,
    }


def _message_to_json(m: CompanionMessage) -> dict:
    return {"seq": m.seq, "role": m.role, "text": m.text, "createdAt": m.created_at}


def _run(fn: Callable[[], Dict[str, Any]]) -> Dict[str, Any]:
    try:
        return fn()
    except CompanionTransportError:
        raise
    except CompanionProviderError as exc:
        raise CompanionTransportError(502, "provider_failed", exc.message) from exc
    except CompanionError as exc:
        status = _STATUS_BY_CODE.get(exc.code, 400)
        raise CompanionTransportError(status, exc.code, exc.message) from exc
    except Exception as exc:  # noqa: BLE001 -- never leak a traceback
        raise CompanionTransportError(500, "internal_error", "internal server failure") from exc


class CompanionTransport:
    def __init__(self, service: CompanionService) -> None:
        self._service = service

    def list_characters(self) -> dict:
        return _run(lambda: {
            "characters": [_character_to_json(c) for c in self._service.list_characters()]
        })

    def list_sessions(self, character_id: str) -> dict:
        return _run(lambda: {
            "sessions": [_session_to_json(s) for s in self._service.list_sessions(character_id)]
        })

    def create_session(self, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise CompanionTransportError(400, "invalid_request", "request body must be a JSON object")
        character_id = _require_str(payload, "characterId")
        return _run(lambda: _session_to_json(self._service.create_session(character_id)))

    def get_messages(self, session_id: str) -> dict:
        return _run(lambda: {
            "sessionId": session_id,
            "messages": [_message_to_json(m) for m in self._service.get_messages(session_id)],
        })

    def send_message(self, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise CompanionTransportError(400, "invalid_request", "request body must be a JSON object")
        session_id = _require_str(payload, "sessionId")
        text = payload.get("text")
        if not isinstance(text, str) or not text.strip():
            raise CompanionTransportError(400, "empty_message", "'text' must be a non-empty string")

        def op():
            turn = self._service.send_message(session_id, text)
            return {
                "sessionId": turn.session_id,
                "response": turn.response,
                "messages": [_message_to_json(m) for m in turn.messages],
            }

        return _run(op)
