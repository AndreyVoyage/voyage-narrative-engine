#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Minimal durable runtime-memory backend for accepted character packages.

Runtime memory is SEPARATE from the Accepted Character Package (package seed).
It stores only events learned after the character begins living, and must never
be written into the package (which is immutable). Backend: stdlib SQLite, one
connection per instance, so ``close()`` -> new instance -> ``load_events`` proves
durability across backend re-instantiation.

Provider-free, network-free. Writes only under the caller-supplied ``root``
(tests and the smoke runner use temporary storage, never production saves).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS runtime_events ("
    " event_id TEXT PRIMARY KEY,"
    " subject_id TEXT NOT NULL,"
    " session_id TEXT NOT NULL,"
    " event_type TEXT NOT NULL,"
    " meaning TEXT NOT NULL,"
    " created_at TEXT NOT NULL"
    ")"
)


class RuntimeMemoryError(RuntimeError):
    """Fail-closed error for the durable runtime-memory backend."""


@dataclass(frozen=True)
class RuntimeEvent:
    """One immutable runtime-memory event (never package seed)."""

    event_id: str
    subject_id: str
    session_id: str
    event_type: str
    meaning: str
    created_at: str

    def __post_init__(self) -> None:
        for field_name, value in (
            ("event_id", self.event_id),
            ("subject_id", self.subject_id),
            ("session_id", self.session_id),
            ("event_type", self.event_type),
            ("meaning", self.meaning),
            ("created_at", self.created_at),
        ):
            if not isinstance(value, str) or not value.strip():
                raise RuntimeMemoryError(f"{field_name} must be a non-empty string")


class RuntimeMemoryBackend:
    """Durable, per-root SQLite store for runtime events.

    Each instance opens its own connection. ``close()`` commits and closes it; a
    new instance against the same ``root`` re-opens the same file and recovers
    previously committed events.
    """

    def __init__(self, root: Path, subject_id: str) -> None:
        if not isinstance(subject_id, str) or not subject_id.strip():
            raise RuntimeMemoryError("subject_id must be a non-empty string")
        root = Path(root)
        root.mkdir(parents=True, exist_ok=True)
        self._subject_id = subject_id
        self._db_path = root / "runtime_memory.sqlite3"
        self._conn = sqlite3.connect(str(self._db_path))
        try:
            self._conn.execute(_SCHEMA)
            self._conn.commit()
        except Exception as exc:
            self._conn.close()
            raise RuntimeMemoryError(f"failed to initialise runtime memory: {exc}") from exc

    @property
    def subject_id(self) -> str:
        return self._subject_id

    def record_event(self, event: RuntimeEvent) -> None:
        """Persist one runtime event (duplicate event_id fails closed)."""
        if not isinstance(event, RuntimeEvent):
            raise RuntimeMemoryError("event must be a RuntimeEvent")
        if event.subject_id != self._subject_id:
            raise RuntimeMemoryError(
                f"event.subject_id {event.subject_id!r} != backend subject {self._subject_id!r}"
            )
        if self._conn is None:
            raise RuntimeMemoryError("runtime memory backend is already closed")
        try:
            self._conn.execute(
                "INSERT INTO runtime_events"
                " (event_id, subject_id, session_id, event_type, meaning, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    event.event_id,
                    event.subject_id,
                    event.session_id,
                    event.event_type,
                    event.meaning,
                    event.created_at,
                ),
            )
            self._conn.commit()
        except sqlite3.IntegrityError as exc:
            raise RuntimeMemoryError(
                f"duplicate runtime event_id {event.event_id!r}"
            ) from exc

    def load_events(self, subject_id: str) -> Tuple[RuntimeEvent, ...]:
        """Return all persisted runtime events for ``subject_id`` (ordered)."""
        if self._conn is None:
            raise RuntimeMemoryError("runtime memory backend is already closed")
        if subject_id != self._subject_id:
            raise RuntimeMemoryError(
                f"subject_id {subject_id!r} != backend subject {self._subject_id!r}"
            )
        rows = self._conn.execute(
            "SELECT event_id, subject_id, session_id, event_type, meaning, created_at"
            " FROM runtime_events WHERE subject_id = ? ORDER BY created_at, event_id",
            (subject_id,),
        ).fetchall()
        return tuple(RuntimeEvent(*row) for row in rows)

    def close(self) -> None:
        """Commit and close this instance's connection."""
        if self._conn is not None:
            self._conn.commit()
            self._conn.close()
            self._conn = None
