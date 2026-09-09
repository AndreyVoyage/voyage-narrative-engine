#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""JSON-dict <-> :class:`CompanionService` translation for the Companion client.

Mirrors the Character Lab ``ReactTransport`` pattern: no HTTP, no sockets, no
character/runtime logic of its own. Fully unit-testable without a server.

Exposes ONLY end-user Companion operations: catalog, multi-chat sessions
(with additive scene metadata), conversation, deterministic random scenario,
and the async image-job boundary. NEVER any Character Lab debug / operator /
workspace / memory-editor / evolution surface.
"""

from __future__ import annotations

from typing import Any, Callable, Dict

from .image_jobs import KIND_CONTEXT, KIND_CUSTOM
from .scenarios import SCENE_FIELDS, random_field, random_scenario
from .service import (
    CompanionError,
    CompanionMessage,
    CompanionProviderError,
    CompanionScene,
    CompanionService,
    CompanionSession,
)

__all__ = ["CompanionTransportError", "CompanionTransport"]

_STATUS_BY_CODE = {
    "unknown_character": 404,
    "unknown_session": 404,
    "unknown_job": 404,
    "unknown_provider": 404,
    "empty_message": 400,
    "invalid_request": 400,
    "invalid_secret": 400,
    "invalid_num_ctx": 400,
    "unknown_role": 400,
    "unsupported_role": 400,
    "unknown_model": 400,
    "unsupported_model_role": 400,
    "provider_failed": 502,
    "provider_unavailable": 503,
    "missing_credential": 409,
    "no_credential_needed": 409,
    "provider_config": 409,
    "provider_not_configured": 409,
    "settings_unavailable": 409,
    "secret_in_settings": 500,
    "vault_unavailable": 503,
}


class CompanionTransportError(Exception):
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


def _scene_to_json(scene) -> Dict[str, str] | None:
    if scene is None:
        return None
    return {
        "place": scene.place, "time": scene.time,
        "situation": scene.situation, "mood": scene.mood, "freeform": scene.freeform,
    }


def _session_to_json(s: CompanionSession) -> dict:
    return {
        "sessionId": s.session_id,
        "characterId": s.character_id,
        "purpose": s.purpose,
        "createdAt": s.created_at,
        "updatedAt": s.updated_at,
        "label": s.label,
        "title": s.title,
        "scene": _scene_to_json(s.scene),
        "sceneCoverRef": s.scene_cover_ref,
        "lastMessagePreview": s.last_message_preview,
        "lastActivity": s.last_activity,
    }


def _message_to_json(m: CompanionMessage) -> dict:
    return {"seq": m.seq, "role": m.role, "text": m.text, "createdAt": m.created_at}


def _job_to_json(j) -> dict:
    return {
        "jobId": j.job_id,
        "sessionId": j.session_id,
        "characterId": j.character_id,
        "kind": j.kind,
        "state": j.state,
        "createdAt": j.created_at,
        "updatedAt": j.updated_at,
        "prompt": j.prompt,
        "resultRef": j.result_ref,
        "error": j.error,
    }


def _run(fn: Callable[[], Dict[str, Any]]) -> Dict[str, Any]:
    try:
        return fn()
    except CompanionTransportError:
        raise
    except CompanionProviderError as exc:
        raise CompanionTransportError(_STATUS_BY_CODE.get(exc.code, 502), exc.code, exc.message) from exc
    except CompanionError as exc:
        raise CompanionTransportError(_STATUS_BY_CODE.get(exc.code, 400), exc.code, exc.message) from exc
    except Exception as exc:  # noqa: BLE001 -- never leak a traceback
        raise CompanionTransportError(500, "internal_error", "internal server failure") from exc


class CompanionTransport:
    def __init__(self, service: CompanionService) -> None:
        self._service = service

    # ---------------------------------------------------------- catalog
    def list_characters(self) -> dict:
        return _run(lambda: {
            "characters": [_character_to_json(c) for c in self._service.list_characters()]
        })

    # ---------------------------------------------------------- sessions
    def list_sessions(self, character_id: str) -> dict:
        return _run(lambda: {
            "sessions": [_session_to_json(s) for s in self._service.list_sessions(character_id)]
        })

    def get_session(self, session_id: str) -> dict:
        return _run(lambda: _session_to_json(self._service.get_session(session_id)))

    def create_session(self, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise CompanionTransportError(400, "invalid_request", "request body must be a JSON object")
        character_id = _require_str(payload, "characterId")
        title = payload.get("title")
        scene = payload.get("scene")
        if title is not None and not isinstance(title, str):
            raise CompanionTransportError(400, "invalid_request", "'title' must be a string")
        if scene is not None and not isinstance(scene, dict):
            raise CompanionTransportError(400, "invalid_request", "'scene' must be an object")
        return _run(lambda: _session_to_json(
            self._service.create_session(character_id, title=title, scene=scene)
        ))

    def set_scene_cover(self, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise CompanionTransportError(400, "invalid_request", "request body must be a JSON object")
        session_id = _require_str(payload, "sessionId")
        result_ref = _require_str(payload, "resultRef")
        return _run(lambda: _session_to_json(self._service.set_scene_cover(session_id, result_ref)))

    # ---------------------------------------------------------- chat
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
                "scenePresent": turn.scene_present,
                "messages": [_message_to_json(m) for m in turn.messages],
            }

        return _run(op)

    # ---------------------------------------------------------- scenario
    def random_scenario(self, payload: dict) -> dict:
        payload = payload if isinstance(payload, dict) else {}
        field = payload.get("field")
        seed = payload.get("seed")
        if seed is not None and not isinstance(seed, int):
            raise CompanionTransportError(400, "invalid_request", "'seed' must be an integer or null")

        def op():
            if isinstance(field, str) and field:
                if field not in SCENE_FIELDS:
                    raise CompanionError("invalid_request", f"unknown scenario field {field!r}")
                return {"field": field, "value": random_field(field, seed=seed)}
            return {"scenario": random_scenario(seed=seed)}

        return _run(op)

    # ---------------------------------------------------------- image jobs
    def create_image_job(self, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise CompanionTransportError(400, "invalid_request", "request body must be a JSON object")
        session_id = _require_str(payload, "sessionId")
        kind = _require_str(payload, "kind")
        if kind not in (KIND_CUSTOM, KIND_CONTEXT):
            raise CompanionTransportError(400, "invalid_request", f"'kind' must be one of {KIND_CUSTOM!r}/{KIND_CONTEXT!r}")
        prompt = payload.get("prompt")
        if prompt is not None and not isinstance(prompt, str):
            raise CompanionTransportError(400, "invalid_request", "'prompt' must be a string or null")
        return _run(lambda: _job_to_json(
            self._service.create_image_job(session_id, kind=kind, prompt=prompt)
        ))

    def list_image_jobs(self, session_id: str) -> dict:
        return _run(lambda: {
            "sessionId": session_id,
            "jobs": [_job_to_json(j) for j in self._service.poll_image_jobs(session_id)],
        })

    def get_image_job(self, job_id: str) -> dict:
        return _run(lambda: _job_to_json(self._service.get_image_job(job_id)))

    def delete_image_job(self, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise CompanionTransportError(400, "invalid_request", "request body must be a JSON object")
        job_id = _require_str(payload, "jobId")
        return _run(lambda: (self._service.delete_image_job(job_id), {"deleted": job_id})[1])

    # ---------------------------------------------------- provider settings
    def get_settings(self) -> dict:
        return _run(self._service.settings_view)

    def set_role(self, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise CompanionTransportError(400, "invalid_request", "request body must be a JSON object")
        role = _require_str(payload, "role")
        provider_id = _require_str(payload, "providerId")
        model_id = payload.get("modelId")
        if model_id is not None and not isinstance(model_id, str):
            raise CompanionTransportError(400, "invalid_request", "'modelId' must be a string or null")
        return _run(lambda: self._service.set_role(role, provider_id, model_id or ""))

    def set_local_settings(self, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise CompanionTransportError(400, "invalid_request", "request body must be a JSON object")
        out = None
        if "numCtx" in payload:
            n = payload.get("numCtx")
            if n is not None and (isinstance(n, bool) or not isinstance(n, int)):
                raise CompanionTransportError(400, "invalid_num_ctx", "'numCtx' must be an integer or null")
            out = _run(lambda: self._service.set_local_num_ctx(n))
        if "baseUrl" in payload:
            url = payload.get("baseUrl")
            if url is not None and not isinstance(url, str):
                raise CompanionTransportError(400, "invalid_request", "'baseUrl' must be a string or null")
            out = _run(lambda: self._service.set_provider_base_url("local", url))
        if out is None:
            return _run(self._service.settings_view)
        return out

    def store_credential(self, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise CompanionTransportError(400, "invalid_request", "request body must be a JSON object")
        provider_id = _require_str(payload, "providerId")
        secret = payload.get("secret")
        if not isinstance(secret, str) or not secret.strip():
            raise CompanionTransportError(400, "invalid_secret", "'secret' must be a non-empty string")
        # NOTE: the secret is handed straight to the vault; it is never echoed,
        # logged, or included in the response (settings_view has no secret).
        return _run(lambda: self._service.store_credential(provider_id, secret))

    def delete_credential(self, provider_id: str) -> dict:
        return _run(lambda: self._service.delete_credential(provider_id))

    def test_provider(self, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise CompanionTransportError(400, "invalid_request", "request body must be a JSON object")
        provider_id = _require_str(payload, "providerId")
        model_id = payload.get("modelId")
        return _run(lambda: self._service.test_connection(provider_id, model_id or ""))

    def resolve_role(self, role: str) -> dict:
        role = (role or "").strip()
        if not role:
            raise CompanionTransportError(400, "invalid_request", "'role' must be a non-empty string")
        return _run(lambda: self._service.resolve_media_role(role))

    def get_release_info(self) -> dict:
        return _run(self._service.release_info)
