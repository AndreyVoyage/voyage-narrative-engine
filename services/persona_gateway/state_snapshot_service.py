#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
StateSnapshotService -- read-only facade over saved aside/session memory
(N7 Persona Data Gateway, P1a-S1 partial runtime).

Scope, per N7_P1A_CONTRACT_CORRECTION_READONLY_PREFLIGHT_2026-07-17.md
Phase 5: this service reads exclusively saved aside/session data via
``tools.aside_memory_store.load_memory``. It never reads the live Ren'Py
``v2_*`` canon (which in any case only exists in game-process memory, not
on disk in general form) and never loads ``state/STATE_TEMPLATE_v2.json``
as if it were live state.

Deliberate deviation from the task's literal instruction to additionally
import ``summarize_memory``: inspection of ``tools/aside_memory_store.py``
(Phase 3 of this task) shows that despite its name, ``summarize_memory``
is NOT read-only -- it calls ``base.mkdir(parents=True, exist_ok=True)``
and unconditionally writes ``memory_summary.json`` to disk as a side
effect. Calling it here would violate the P1a "no filesystem writes"
invariant. This module therefore imports and calls only ``load_memory``,
which is verified to perform no filesystem mutation (it only resolves
paths and reads existing session files, returning ``[]`` when the
``sessions`` directory does not exist).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, Optional

from tools.aside_memory_store import load_memory

from .errors import PersonaGatewayError, SnapshotUnavailableError
from .models import MessageEntry, SessionMeta, StateSnapshot

LoadMemoryFn = Callable[..., Dict[str, Any]]


def _assert_plain_data(value: Any) -> None:
    """Recursively assert that ``value`` is built only from detached plain
    data types. Raises ``PersonaGatewayError`` on any other object type
    (custom classes, sets, file handles, etc.) surfaced by the underlying
    read function."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return
    if isinstance(value, dict):
        for key, val in value.items():
            if not isinstance(key, str):
                raise PersonaGatewayError(
                    f"unsupported non-string key in saved state: {type(key).__name__}"
                )
            _assert_plain_data(val)
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _assert_plain_data(item)
        return
    raise PersonaGatewayError(
        f"unsupported data type encountered in saved aside state: {type(value).__name__}"
    )


class StateSnapshotService:
    """Thin, read-only wrapper over saved aside/session memory.

    ``load_memory_fn`` is injectable for testability; it defaults to the
    real ``tools.aside_memory_store.load_memory``.
    """

    def __init__(
        self,
        root: Path,
        slot: str,
        *,
        load_memory_fn: LoadMemoryFn = load_memory,
    ) -> None:
        self._root = root
        self._slot = slot
        self._load_memory_fn = load_memory_fn

    def get_state_snapshot(self, character_id: str, progress: int) -> StateSnapshot:
        raw = self._load_memory_fn(
            root=self._root,
            slot=self._slot,
            character=character_id,
            progress=progress,
        )

        if not isinstance(raw, dict):
            raise PersonaGatewayError("saved state payload must be a JSON object")

        _assert_plain_data(raw)

        summary = raw.get("summary") or ""
        recent = raw.get("recent") or []
        sessions_meta = raw.get("sessions_meta") or []

        if not summary and not recent and not sessions_meta:
            raise SnapshotUnavailableError(
                f"no saved aside session state for character_id={character_id!r}"
            )

        recent_entries = tuple(
            MessageEntry(role=entry.get("role", ""), content=entry.get("content", ""))
            for entry in recent
            if isinstance(entry, dict)
        )

        session_metas = tuple(
            SessionMeta(
                session_id=meta.get("session_id"),
                scene_id=meta.get("scene_id", ""),
                beat_id=meta.get("beat_id", ""),
                progress_index=int(meta.get("progress_index", -1)),
            )
            for meta in sessions_meta
            if isinstance(meta, dict)
        )

        max_progress: Optional[int] = (
            max((sm.progress_index for sm in session_metas), default=None)
        )

        return StateSnapshot(
            character_id=character_id,
            summary=str(summary),
            recent=recent_entries,
            session_count=len(session_metas),
            max_progress_index=max_progress,
            sessions=session_metas,
        )
