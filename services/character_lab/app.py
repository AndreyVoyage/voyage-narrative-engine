#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Character Lab V1 application service (Slice 2).

Composes the Slice 1 RuntimeService + TurnCapture into the smallest UI-facing
API. It does NOT reimplement Character Runtime and does NOT import any
acceptance-mutating API. The provider callable/factory is injected by the server
(or tests) so this module stays provider- and network-free.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from services.character_runtime import load_accepted_character
from services.crp_authoring import compute_package_hash

from .runtime_policy import BetaV1CurrentPolicy
from .runtime_service import RuntimeService
from .source_loader import DEFAULT_ACCEPTANCE_ROOT, build_repo_source_loader
from .turn_capture import TurnCapture, verify_segment_delivered

CHARACTER_LAB_DATA_ROOT_ENV = "CHARACTER_LAB_DATA_ROOT"

_VARIANT_CATALOG = (
    {"id": "KIRA_BETA_V1_CURRENT", "display_name": "Beta v1 — Current", "implemented": True},
    {"id": "KIRA_GROUNDED_V2", "display_name": "Grounded v2", "implemented": False, "status": "planned"},
    {"id": "EXPERIMENTAL", "display_name": "Experimental", "implemented": False, "status": "planned"},
)


def resolve_data_root() -> Path:
    """Character Lab user-data root (outside the repo, overridable by env)."""
    env = os.environ.get(CHARACTER_LAB_DATA_ROOT_ENV)
    if env:
        return Path(env)
    return Path.home() / ".voyage-narrative-engine" / "character_lab"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _enum_value(value) -> str:
    return getattr(value, "value", str(value))


def _serialize_claim(claim) -> dict:
    return {
        "claim_id": claim.claim_id,
        "role_id": claim.role_id,
        "claim": claim.claim,
        "claim_type": _enum_value(claim.claim_type),
        "status": _enum_value(claim.status),
        "confidence": _enum_value(claim.confidence),
        "rationale_summary": claim.rationale_summary,
        "source_evidence_ids": list(claim.source_evidence_ids),
        "target_module_or_layer": claim.target_module_or_layer,
    }


def _serialize_group(mapping) -> list:
    result = []
    for key, claims in mapping.items():
        result.append({"section": key, "claims": [_serialize_claim(c) for c in claims]})
    return result


def _serialize_contradiction(contradiction) -> dict:
    return {
        "contradiction_id": contradiction.contradiction_id,
        "claim_ids": list(contradiction.claim_ids),
        "description": contradiction.description,
        "severity": _enum_value(contradiction.severity),
        "resolution_status": _enum_value(contradiction.resolution_status),
        "requires_human": contradiction.requires_human,
    }


def _extract_response_text(data) -> Optional[str]:
    if not isinstance(data, dict):
        return None
    choices = data.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        message = choices[0].get("message")
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            return message["content"]
    return None


def _extract_accepted_source_hash_from_manifest(manifest) -> Optional[str]:
    if not isinstance(manifest, dict):
        return None
    for item in manifest.get("items", []):
        if item.get("kind") == "system.package_identity":
            h = (item.get("meta") or {}).get("accepted_source_hash")
            if h:
                return h
    return None


class CharacterLabApp:
    """UI-facing application service composing the Slice 1 runtime foundation."""

    def __init__(
        self,
        *,
        acceptance_root=None,
        data_root=None,
        provider_factory=None,
        provider_info=None,
        provider_availability="NOT CHECKED",
    ) -> None:
        self._acceptance_root = Path(acceptance_root) if acceptance_root else DEFAULT_ACCEPTANCE_ROOT
        self._data_root = Path(data_root) if data_root else resolve_data_root()
        self._source_loader = build_repo_source_loader(acceptance_root=self._acceptance_root)
        self._runtime = RuntimeService(
            acceptance_root=self._acceptance_root, source_loader=self._source_loader
        )
        self._capture = TurnCapture(self._data_root)
        self._memory_root = self._data_root / "memory"
        self._policy = BetaV1CurrentPolicy()
        self._provider_factory = provider_factory
        self._provider_info = dict(provider_info or {})
        self._provider_availability = provider_availability
        self._sessions: dict = {}
        self._selected_session_id: Optional[str] = None
        self._turn_index: dict = {}

    @property
    def data_root(self) -> Path:
        return self._data_root

    # ------------------------------------------------------------------ health
    def health(self) -> dict:
        source_available = (self._acceptance_root / "kira" / "source_candidate.json").exists()
        try:
            load_accepted_character(
                "kira", acceptance_root=self._acceptance_root, source_loader=self._source_loader
            )
            loadable = True
        except Exception:
            loadable = False
        return {
            "status": "ready",
            "character_source_available": source_available,
            "accepted_package_loadable": loadable,
            "provider_availability": self._provider_availability,
        }

    # ---------------------------------------------------------------- catalog
    def catalog(self) -> dict:
        return {
            "characters": [{"id": "kira", "display_name": "KIRA", "supported": True}],
            "variants": list(_VARIANT_CATALOG),
        }

    # ------------------------------------------------------------ loaded state
    def loaded_state(self) -> dict:
        state = self._runtime.resolve(
            "kira",
            policy=self._policy,
            provider_id=self._provider_info.get("provider_id", "unknown"),
            model=self._provider_info.get("model", "unknown"),
            session_id=self._selected_session_id,
        )
        return {
            "character_id": state.character_id,
            "acceptance_id": state.acceptance_id,
            "acceptance_decision": state.acceptance_decision,
            "accepted_source_hash": state.accepted_source_hash,
            "runtime_loaded_package_hash": state.runtime_loaded_package_hash,
            "hash_match": state.hash_match,
            "package_id": state.package_id,
            "package_version": state.package_version,
            "package_status": state.package_status,
            "variant_id": state.variant_id,
            "variant_version": state.variant_version,
            "session_id": self._selected_session_id,
            "provider_id": state.provider_id,
            "model": state.model,
            "provider_availability": self._provider_availability,
            "context_capture": "ACTIVE" if self._provider_factory is not None else "INACTIVE",
            "data_root": str(self._data_root),
            "workspace_label": "Clean Test / isolated Character Lab data",
            "package_write_access": "LOCKED",
        }

    # --------------------------------------------------------------- sessions
    def new_session(self) -> dict:
        sid = f"session-{uuid.uuid4().hex}"
        self._sessions[sid] = {"history": [], "created_at": _now_iso()}
        self._selected_session_id = sid
        return {"session_id": sid, "created_at": self._sessions[sid]["created_at"], "selected": True}

    def list_sessions(self) -> list:
        result = []
        for sid, sess in self._sessions.items():
            preview = sess["history"][0]["content"][:120] if sess["history"] else None
            result.append({
                "session_id": sid,
                "created_at": sess["created_at"],
                "message_count": len(sess["history"]),
                "preview": preview,
                "selected": sid == self._selected_session_id,
            })
        return result

    def select_session(self, session_id: str) -> dict:
        if session_id not in self._sessions:
            raise KeyError(f"unknown session {session_id!r}")
        self._selected_session_id = session_id
        return {"session_id": session_id, "selected": True}

    # ------------------------------------------------------------------- chat
    def chat(self, message: str, session_id: Optional[str] = None) -> dict:
        message = (message or "").strip()
        if not message:
            return {"ok": False, "error": "empty_message", "message": "Сообщение пустое."}
        if self._provider_availability != "CONFIGURED" or self._provider_factory is None:
            return {
                "ok": False,
                "error": "provider_unavailable",
                "message": "Provider unavailable — configure the required backend environment before sending messages.",
            }
        sid = session_id or self._selected_session_id
        if sid is None or sid not in self._sessions:
            sid = self.new_session()["session_id"]
        history = [dict(m) for m in self._sessions[sid]["history"]]
        result = self._runtime.turn(
            "kira",
            policy=self._policy,
            history=history,
            user_message=message,
            provider=self._provider_factory(None),
            provider_factory=self._provider_factory,
            memory_root=self._memory_root,
            session_id=sid,
            provider_info=self._provider_info,
            capture=self._capture,
        )
        self._sessions[sid]["history"].append({"role": "user", "content": message})
        self._sessions[sid]["history"].append({"role": "assistant", "content": result.response})
        self._turn_index[result.turn_id] = {
            "session_id": sid,
            "character_id": "kira",
            "accepted_source_hash": result.accepted_source_hash,
            "variant_id": result.variant_id,
            "response": result.response,
            "persisted_event_ids": list(result.persisted_event_ids),
            "package_hash_after": result.package_hash_after,
            "package_hash_unchanged": result.package_hash_unchanged,
            "created_at": _now_iso(),
        }
        return {
            "ok": True,
            "turn_id": result.turn_id,
            "session_id": sid,
            "response": result.response,
            "request_hash": result.request_hash,
        }

    # ------------------------------------------------------ character inspector
    def character_inspector(self) -> dict:
        accepted = load_accepted_character(
            "kira", acceptance_root=self._acceptance_root, source_loader=self._source_loader
        )
        package = accepted.package
        group_specs = (
            ("identity_biography", "Identity / Biography", package.identity_biography_candidate),
            ("psychology", "Psychology", package.psychology_candidate),
            ("behavior", "Behavior", package.behavior_candidate),
            ("relationships", "Relationships", package.relationships_candidate),
            ("boundaries", "Boundaries", package.boundaries_candidate),
            ("intimacy", "Intimacy", package.intimacy_candidate),
            ("voice", "Voice", package.voice_candidate),
        )
        return {
            "character_id": "kira",
            "accepted_source_hash": accepted.source_candidate_hash,
            "package_id": package.package_id,
            "package_version": package.package_version,
            "package_status": package.status.value,
            "claim_count": len(package.claims),
            "contradiction_count": len(package.contradictions),
            "unknown_count": len(package.unknowns),
            "groups": [
                {
                    "id": gid,
                    "display_name": display,
                    "sections": _serialize_group(mapping),
                    "observability": self._group_observability(mapping),
                }
                for gid, display, mapping in group_specs
            ],
            "contradictions": [_serialize_contradiction(c) for c in package.contradictions],
            "unknowns": [_serialize_claim(u) for u in package.unknowns],
        }

    def _group_observability(self, mapping) -> dict:
        has_data = len(mapping) > 0
        return {
            "stored": has_data,
            "loaded": has_data,
            "selected": False,
            "delivered": False,
            "note": "Beta v1 does not select/deliver claim content into the provider request.",
        }

    # ------------------------------------------------------------------ turns
    def list_turns(self) -> list:
        turns_dir = self._data_root / "turns"
        result = []
        if turns_dir.exists():
            for d in sorted(turns_dir.iterdir()):
                if not d.is_dir():
                    continue
                turn_id = d.name
                request_hash = self._capture.read_request_hash(turn_id)
                response_text = _extract_response_text(self._capture.read_response(turn_id))
                meta = self._turn_index.get(turn_id, {})
                result.append({
                    "turn_id": turn_id,
                    "session_id": meta.get("session_id"),
                    "request_hash": request_hash,
                    "response_preview": (response_text or "")[:160] if response_text else None,
                    "has_error": (d / "error.json").exists(),
                    "created_at": meta.get("created_at"),
                })
        return result

    def turn_detail(self, turn_id: str) -> dict:
        directory = self._capture.turn_dir(turn_id)
        if not directory.exists():
            raise KeyError(f"unknown turn {turn_id!r}")
        request_bytes = None
        request_path = directory / "request.json"
        if request_path.exists():
            request_bytes = request_path.read_bytes()
        request_hash = self._capture.read_request_hash(turn_id)
        manifest = self._capture.read_manifest(turn_id)
        response = self._capture.read_response(turn_id)
        error = None
        error_path = directory / "error.json"
        if error_path.exists():
            try:
                error = json.loads(error_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                error = None
        request_text = request_bytes.decode("utf-8") if request_bytes else None
        items = []
        if isinstance(manifest, dict):
            for item in manifest.get("items", []):
                delivered = False
                if request_text is not None:
                    delivered = verify_segment_delivered(
                        segment_text=item.get("text", ""), request_body_text=request_text
                    )
                items.append({**item, "selected": True, "delivered": delivered})
        meta = self._turn_index.get(turn_id, {})
        accepted_source_hash = meta.get("accepted_source_hash") or _extract_accepted_source_hash_from_manifest(manifest)
        return {
            "turn_id": turn_id,
            "character_id": meta.get("character_id"),
            "variant_id": (manifest or {}).get("variant_id"),
            "variant_version": (manifest or {}).get("variant_version"),
            "session_id": meta.get("session_id"),
            "accepted_source_hash": accepted_source_hash,
            "request": {
                "request_hash": request_hash,
                "bytes_sha256": request_hash,
                "raw": request_text,
            },
            "manifest": {
                "assembly_hash": (manifest or {}).get("assembly_hash"),
                "request_hash": request_hash,
                "items": items,
                "provider": (manifest or {}).get("provider"),
            },
            "provider": (manifest or {}).get("provider"),
            "response": response,
            "response_metadata": self._response_metadata(response),
            "error": error,
            "persistence": {"event_ids": meta.get("persisted_event_ids", [])},
            "package": {
                "accepted_source_hash": accepted_source_hash,
                "hash_after": meta.get("package_hash_after"),
                "unchanged": meta.get("package_hash_unchanged"),
            },
        }

    @staticmethod
    def _response_metadata(data) -> dict:
        if not isinstance(data, dict):
            return {}
        meta = {}
        if "id" in data:
            meta["response_id"] = data["id"]
        if "model" in data:
            meta["provider_reported_model"] = data["model"]
        if "usage" in data:
            meta["usage"] = data["usage"]
        choices = data.get("choices")
        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            fr = choices[0].get("finish_reason")
            if fr is not None:
                meta["finish_reason"] = fr
        return meta
