#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CompanionService -- the minimal end-user chat surface for accepted characters.

Companion is a SEPARATE client from Character Lab. It never imports the Lab
adapter or Lab UI; it composes the same lower layers the Lab already uses:

    CompanionService
        v
    RuntimeService.turn(...)           (unchanged)  -- accepted package + policy
    RuntimeMemoryBackend               (unchanged)  -- the ONE durable event log
        v
    Character Runtime / Core

Persistence:
- conversation turns are the EXISTING Runtime Memory event log (USER_MESSAGE /
  CHARACTER_MESSAGE). No second chat database.
- a small durable JSON session registry (``companion_sessions.json``) records
  which COMPANION sessions exist, per character, with a neutral deterministic
  label. This is a session index, not chat history.
- each character's Companion conversations share one memory / state root under
  ``<data_root>/characters/<character_id>/`` -- fully isolated from Character
  Lab's CLEAN_TEST workspaces (a different data root entirely).

No provider or network calls of its own: the caller injects a provider factory
(the local server injects the deterministic fake one). Provider failure raises
without persisting anything, so prior history is always intact.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from services.character_lab import GroundedV2Policy, RuntimeService
from services.character_lab.source_loader import build_repo_source_loader
from services.character_runtime import RuntimeMemoryBackend

from .catalog import CompanionCatalog, CompanionCharacterEntry, build_default_catalog
from .local_provider import LocalLLMProviderError

PURPOSE_COMPANION = "COMPANION"

# durable runtime event types that map to a displayable conversational turn
_ROLE_BY_EVENT_TYPE = {"USER_MESSAGE": "user", "CHARACTER_MESSAGE": "character"}
# and the provider-history role for each
_HISTORY_ROLE = {"user": "user", "character": "assistant"}

_REGISTRY_FILENAME = "companion_sessions.json"


class CompanionError(RuntimeError):
    """Deterministic, client-safe Companion failure. ``code`` is a small fixed
    vocabulary; ``message`` is a short deliberately-written string."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class CompanionProviderError(CompanionError):
    """The character response failed at the provider layer. Nothing was
    persisted; prior conversation history is unchanged."""


@dataclass(frozen=True)
class CompanionSession:
    session_id: str
    character_id: str
    purpose: str
    created_at: str
    updated_at: str
    label: str


@dataclass(frozen=True)
class CompanionMessage:
    seq: Optional[int]
    role: str          # "user" | "character"
    text: str
    created_at: str


@dataclass(frozen=True)
class CompanionTurn:
    session_id: str
    response: str
    messages: Tuple[CompanionMessage, ...]


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _default_label(created_at: str) -> str:
    # neutral, deterministic -- no LLM, no provider call
    stamp = created_at.replace("T", " ")
    if "+" in stamp:
        stamp = stamp.split("+", 1)[0]
    return f"Диалог от {stamp}"


class CompanionService:
    def __init__(
        self,
        *,
        acceptance_root,
        data_root,
        provider_factory,
        provider_info: dict,
        source_loader=None,
        catalog: Optional[CompanionCatalog] = None,
    ) -> None:
        self._acceptance_root = Path(acceptance_root)
        self._data_root = Path(data_root)
        self._data_root.mkdir(parents=True, exist_ok=True)
        self._source_loader = source_loader or build_repo_source_loader(
            acceptance_root=self._acceptance_root
        )
        if provider_factory is None:
            raise CompanionError("provider_unavailable", "a provider factory is required")
        self._provider_factory = provider_factory
        self._provider_info = dict(provider_info or {})
        self._runtime = RuntimeService(
            acceptance_root=self._acceptance_root, source_loader=self._source_loader
        )
        self._catalog = catalog or build_default_catalog(
            self._acceptance_root, self._source_loader
        )

    # ------------------------------------------------------------- catalog
    def list_characters(self) -> Tuple[CompanionCharacterEntry, ...]:
        return self._catalog.available()

    def _require_character(self, character_id: str) -> CompanionCharacterEntry:
        entry = self._catalog.get(character_id)
        if entry is None or not entry.available:
            raise CompanionError("unknown_character", f"unknown character {character_id!r}")
        return entry

    # --------------------------------------------------------- registry io
    def _registry_path(self) -> Path:
        return self._data_root / _REGISTRY_FILENAME

    def _load_registry(self) -> List[dict]:
        path = self._registry_path()
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        return [r for r in data if isinstance(r, dict)] if isinstance(data, list) else []

    def _save_registry(self, rows: Sequence[dict]) -> None:
        path = self._registry_path()
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(list(rows), ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)

    def _char_root(self, character_id: str) -> Path:
        root = self._data_root / "characters" / character_id
        (root / "memory").mkdir(parents=True, exist_ok=True)
        (root / "state").mkdir(parents=True, exist_ok=True)
        return root

    # ------------------------------------------------------------- sessions
    def list_sessions(self, character_id: str) -> Tuple[CompanionSession, ...]:
        self._require_character(character_id)
        rows = [r for r in self._load_registry() if r.get("character_id") == character_id]
        rows.sort(key=lambda r: (r.get("created_at", ""), r.get("session_id", "")))
        return tuple(_session_from_row(r) for r in rows)

    def create_session(self, character_id: str) -> CompanionSession:
        self._require_character(character_id)
        now = _now_iso()
        row = {
            "session_id": "cmp-" + uuid.uuid4().hex,
            "character_id": character_id,
            "purpose": PURPOSE_COMPANION,
            "created_at": now,
            "updated_at": now,
            "label": _default_label(now),
        }
        registry = self._load_registry()
        registry.append(row)
        self._save_registry(registry)
        return _session_from_row(row)

    def _session_row(self, session_id: str) -> dict:
        for row in self._load_registry():
            if row.get("session_id") == session_id:
                return row
        raise CompanionError("unknown_session", f"unknown session {session_id!r}")

    # ------------------------------------------------------------- messages
    def get_messages(self, session_id: str) -> Tuple[CompanionMessage, ...]:
        row = self._session_row(session_id)
        return self._history(row["character_id"], session_id)

    def _history(self, character_id: str, session_id: str) -> Tuple[CompanionMessage, ...]:
        entry = self._require_character(character_id)
        backend = RuntimeMemoryBackend(self._char_root(character_id) / "memory", entry.subject_id)
        try:
            events = backend.load_events_causal(entry.subject_id)
        finally:
            backend.close()
        out: List[CompanionMessage] = []
        for e in events:
            if e.session_id != session_id:
                continue
            role = _ROLE_BY_EVENT_TYPE.get(e.event_type)
            if role is None:
                # never surface system / grounding / epistemic / state / manifest
                continue
            out.append(
                CompanionMessage(seq=e.seq, role=role, text=e.meaning, created_at=e.created_at)
            )
        return tuple(out)

    def send_message(self, session_id: str, text: str) -> CompanionTurn:
        if not isinstance(text, str) or not text.strip():
            raise CompanionError("empty_message", "message text must be a non-empty string")
        row = self._session_row(session_id)
        entry = self._require_character(row["character_id"])
        char_root = self._char_root(entry.character_id)

        history = [
            {"role": _HISTORY_ROLE[m.role], "content": m.text}
            for m in self._history(entry.character_id, session_id)
        ]
        try:
            result = self._runtime.turn(
                entry.subject_id,
                policy=GroundedV2Policy(),
                history=history,
                user_message=text.strip(),
                provider=self._provider_factory(None),
                provider_factory=self._provider_factory,
                memory_root=char_root / "memory",
                state_root=char_root / "state",
                session_id=session_id,
                provider_info=self._provider_info,
            )
        except CompanionError:
            raise
        except Exception as exc:  # noqa: BLE001 -- fail-closed, do not leak internals
            local = _find_local_provider_error(exc)
            if local is not None and local.code == "provider_unavailable":
                raise CompanionProviderError(
                    "provider_unavailable", "Локальная модель недоступна."
                ) from exc
            raise CompanionProviderError(
                "provider_failed", "the character response could not be generated"
            ) from exc

        registry = self._load_registry()
        for r in registry:
            if r.get("session_id") == session_id:
                r["updated_at"] = _now_iso()
        self._save_registry(registry)

        return CompanionTurn(
            session_id=session_id,
            response=result.response,
            messages=self._history(entry.character_id, session_id),
        )


def _find_local_provider_error(exc: BaseException) -> Optional[LocalLLMProviderError]:
    """Walk the exception cause chain for a LocalLLMProviderError so its
    deterministic ``code`` can be preserved for the client."""
    seen = set()
    cur: Optional[BaseException] = exc
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        if isinstance(cur, LocalLLMProviderError):
            return cur
        cur = cur.__cause__ or cur.__context__
    return None


def _session_from_row(row: dict) -> CompanionSession:
    return CompanionSession(
        session_id=row["session_id"],
        character_id=row["character_id"],
        purpose=row.get("purpose", PURPOSE_COMPANION),
        created_at=row.get("created_at", ""),
        updated_at=row.get("updated_at", row.get("created_at", "")),
        label=row.get("label") or _default_label(row.get("created_at", "")),
    )
