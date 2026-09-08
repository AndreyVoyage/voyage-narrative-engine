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
  which COMPANION sessions exist, per character, plus ADDITIVE optional metadata
  (title, scene, scene cover). Old registry rows lacking the new fields still
  load, with defaults.
- image-generation job metadata lives in its own small additive JSON file
  (``companion_image_jobs.json``); see :mod:`image_jobs`.
- each character's Companion conversations share one memory / state root under
  ``<data_root>/characters/<character_id>/`` -- fully isolated from Character
  Lab's CLEAN_TEST workspaces (a different data root entirely).

Scene: a session may carry editable scene fields (place / time / situation /
mood + free-form). On each turn a plain :class:`Scene` is built from those
fields and passed through the EXISTING ``RuntimeService`` scene parameter. It is
never converted into memory / WORLD_FACT / Runtime State / EvolutionCandidate.

No provider or network calls of its own.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from services.character_lab import GroundedV2Policy, RuntimeService
from services.character_lab.scene import new_scene
from services.character_lab.source_loader import build_repo_source_loader
from services.character_runtime import RuntimeMemoryBackend

from .catalog import CompanionCatalog, CompanionCharacterEntry, build_default_catalog
from .image_jobs import (
    KIND_CONTEXT,
    KIND_CUSTOM,
    CompanionImageError,
    ImageJob,
    ImageJobService,
    UnavailableImageGenerator,
)
from .local_provider import LocalLLMProviderError

PURPOSE_COMPANION = "COMPANION"

_ROLE_BY_EVENT_TYPE = {"USER_MESSAGE": "user", "CHARACTER_MESSAGE": "character"}
_HISTORY_ROLE = {"user": "user", "character": "assistant"}

_REGISTRY_FILENAME = "companion_sessions.json"
_SCENE_FIELDS = ("place", "time", "situation", "mood", "freeform")
_CONTEXT_EXCERPT_MAX = 8      # "Кадр по контексту" bounded recent context
_PREVIEW_MAX_CHARS = 120


class CompanionError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class CompanionProviderError(CompanionError):
    """The character response failed at the provider layer. Nothing was
    persisted; prior conversation history is unchanged."""


@dataclass(frozen=True)
class CompanionScene:
    place: str = ""
    time: str = ""
    situation: str = ""
    mood: str = ""
    freeform: str = ""

    @classmethod
    def from_row(cls, data: Optional[dict]) -> Optional["CompanionScene"]:
        if not isinstance(data, dict):
            return None
        picked = {k: str(data.get(k) or "").strip() for k in _SCENE_FIELDS}
        if not any(picked.values()):
            return None
        return cls(**picked)

    def to_row(self) -> dict:
        return {k: getattr(self, k) for k in _SCENE_FIELDS}

    def is_empty(self) -> bool:
        return not any(getattr(self, k) for k in _SCENE_FIELDS)


@dataclass(frozen=True)
class CompanionSession:
    session_id: str
    character_id: str
    purpose: str
    created_at: str
    updated_at: str
    label: str
    title: str = ""
    scene: Optional[CompanionScene] = None
    scene_cover_ref: Optional[str] = None
    last_message_preview: str = ""
    last_activity: str = ""


@dataclass(frozen=True)
class CompanionMessage:
    seq: Optional[int]
    role: str
    text: str
    created_at: str


@dataclass(frozen=True)
class CompanionTurn:
    session_id: str
    response: str
    messages: Tuple[CompanionMessage, ...]
    scene_present: bool = False


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _default_label(created_at: str) -> str:
    stamp = created_at.replace("T", " ")
    if "+" in stamp:
        stamp = stamp.split("+", 1)[0]
    return f"Диалог от {stamp}"


def _compose_situation(scene: CompanionScene) -> str:
    parts: List[str] = []
    if scene.freeform:
        parts.append(scene.freeform)
    if scene.time:
        parts.append(f"Время: {scene.time}.")
    if scene.situation:
        parts.append(f"Ситуация: {scene.situation}.")
    if scene.mood:
        parts.append(f"Настроение: {scene.mood}.")
    return " ".join(parts).strip()


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
        image_generator=None,
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
        self._images = ImageJobService(
            self._data_root, image_generator or UnavailableImageGenerator()
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
    def _next_activity_seq(self, registry: List[dict]) -> int:
        return max((int(r.get("activity_seq") or 0) for r in registry), default=0) + 1

    def list_sessions(self, character_id: str) -> Tuple[CompanionSession, ...]:
        self._require_character(character_id)
        registry = self._load_registry()
        rows = [r for r in registry if r.get("character_id") == character_id]
        # newest activity first -- a monotonic activity_seq is authoritative so
        # ordering is deterministic regardless of wall-clock granularity.
        rows.sort(
            key=lambda r: (int(r.get("activity_seq") or 0), r.get("updated_at") or "", r.get("session_id") or ""),
            reverse=True,
        )
        return tuple(self._enrich(r) for r in rows)

    def create_session(
        self,
        character_id: str,
        *,
        title: Optional[str] = None,
        scene: Optional[dict] = None,
    ) -> CompanionSession:
        self._require_character(character_id)
        now = _now_iso()
        row: dict = {
            "session_id": "cmp-" + uuid.uuid4().hex,
            "character_id": character_id,
            "purpose": PURPOSE_COMPANION,
            "created_at": now,
            "updated_at": now,
            "label": _default_label(now),
        }
        if isinstance(title, str) and title.strip():
            row["title"] = title.strip()
        parsed = CompanionScene.from_row(scene)
        if parsed is not None:
            row["scene"] = parsed.to_row()
        registry = self._load_registry()
        row["activity_seq"] = self._next_activity_seq(registry)
        registry.append(row)
        self._save_registry(registry)
        return self._enrich(row)

    def get_session(self, session_id: str) -> CompanionSession:
        return self._enrich(self._session_row(session_id))

    def _session_row(self, session_id: str) -> dict:
        for row in self._load_registry():
            if row.get("session_id") == session_id:
                return row
        raise CompanionError("unknown_session", f"unknown session {session_id!r}")

    def _enrich(self, row: dict) -> CompanionSession:
        created = row.get("created_at", "")
        updated = row.get("updated_at", created)
        preview = ""
        try:
            history = self._history(row["character_id"], row["session_id"])
            if history:
                preview = history[-1].text.strip().replace("\n", " ")
                if len(preview) > _PREVIEW_MAX_CHARS:
                    preview = preview[: _PREVIEW_MAX_CHARS - 1].rstrip() + "…"
        except CompanionError:
            pass
        return CompanionSession(
            session_id=row["session_id"],
            character_id=row["character_id"],
            purpose=row.get("purpose", PURPOSE_COMPANION),
            created_at=created,
            updated_at=updated,
            label=row.get("label") or _default_label(created),
            title=str(row.get("title") or "").strip(),
            scene=CompanionScene.from_row(row.get("scene")),
            scene_cover_ref=row.get("scene_cover_ref"),
            last_message_preview=preview,
            last_activity=updated,
        )

    def _mutate_row(self, session_id: str, changes: Dict) -> dict:
        registry = self._load_registry()
        target = None
        for r in registry:
            if r.get("session_id") == session_id:
                r.update(changes)
                target = r
        if target is None:
            raise CompanionError("unknown_session", f"unknown session {session_id!r}")
        self._save_registry(registry)
        return target

    def set_scene_cover(self, session_id: str, result_ref: str) -> CompanionSession:
        """Explicit user action. Does not auto-overwrite -- caller decides. The
        referenced image must be a READY job result for this session."""
        row = self._session_row(session_id)
        ready = self._images.ready_results(session_id)
        if result_ref not in ready:
            raise CompanionError("invalid_request", "cover must reference a READY generated image of this session")
        return self._enrich(self._mutate_row(session_id, {"scene_cover_ref": result_ref}))

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
                continue
            out.append(
                CompanionMessage(seq=e.seq, role=role, text=e.meaning, created_at=e.created_at)
            )
        return tuple(out)

    def _scene_for_turn(self, row: dict, entry: CompanionCharacterEntry):
        parsed = CompanionScene.from_row(row.get("scene"))
        if parsed is None or parsed.is_empty():
            return None
        return new_scene(
            title=str(row.get("title") or "").strip(),
            location=parsed.place,
            participants=[entry.display_name],
            prior_events=[],
            current_situation=_compose_situation(parsed),
            scene_id=f"companion-{row['session_id']}",
            created_at=row.get("created_at") or _now_iso(),
        )

    def send_message(self, session_id: str, text: str) -> CompanionTurn:
        if not isinstance(text, str) or not text.strip():
            raise CompanionError("empty_message", "message text must be a non-empty string")
        row = self._session_row(session_id)
        entry = self._require_character(row["character_id"])
        char_root = self._char_root(entry.character_id)
        scene = self._scene_for_turn(row, entry)

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
                scene=scene,
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
                r["activity_seq"] = self._next_activity_seq(registry)
        self._save_registry(registry)
        return CompanionTurn(
            session_id=session_id,
            response=result.response,
            messages=self._history(entry.character_id, session_id),
            scene_present=scene is not None,
        )

    # ------------------------------------------------------- image jobs
    def create_image_job(
        self,
        session_id: str,
        *,
        kind: str,
        prompt: Optional[str] = None,
    ) -> ImageJob:
        row = self._session_row(session_id)
        character_id = row["character_id"]
        context: Optional[dict] = None
        if kind == KIND_CONTEXT:
            context = self._context_frame_request(row)
        try:
            return self._images.create_job(
                session_id=session_id, character_id=character_id, kind=kind,
                prompt=prompt, context=context,
            )
        except CompanionImageError as exc:
            raise CompanionError(exc.code, exc.message) from exc

    def _context_frame_request(self, row: dict) -> dict:
        """Structured intent for a future visual pipeline. BOUNDED: only the
        scene + the last few messages -- never the whole conversation."""
        history = self._history(row["character_id"], row["session_id"])
        excerpt = [
            {"role": m.role, "text": m.text}
            for m in history[-_CONTEXT_EXCERPT_MAX:]
        ]
        scene = CompanionScene.from_row(row.get("scene"))
        return {
            "characterId": row["character_id"],
            "sessionId": row["session_id"],
            "scene": scene.to_row() if scene else None,
            "recentMessages": excerpt,
            "excerptLimit": _CONTEXT_EXCERPT_MAX,
        }

    def poll_image_jobs(self, session_id: str) -> Tuple[ImageJob, ...]:
        self._session_row(session_id)
        self._images.tick()
        return self._images.list_jobs(session_id=session_id)

    def get_image_job(self, job_id: str) -> ImageJob:
        # a point read -- never advances state; poll_image_jobs is the poller
        try:
            return self._images.get_job(job_id)
        except CompanionImageError as exc:
            raise CompanionError(exc.code, exc.message) from exc

    def delete_image_job(self, job_id: str) -> None:
        try:
            self._images.delete_job(job_id)
        except CompanionImageError as exc:
            raise CompanionError(exc.code, exc.message) from exc

    def image_path(self, result_ref: str) -> Path:
        return self._data_root / result_ref


def _find_local_provider_error(exc: BaseException) -> Optional[LocalLLMProviderError]:
    seen = set()
    cur: Optional[BaseException] = exc
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        if isinstance(cur, LocalLLMProviderError):
            return cur
        cur = cur.__cause__ or cur.__context__
    return None
