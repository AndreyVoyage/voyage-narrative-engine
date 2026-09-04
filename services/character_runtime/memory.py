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

Slice 3 evolution (backward compatible):

- Two nullable columns are added -- ``seq`` (a stable monotonic causal write
  sequence) and ``provenance`` (an optional origin label). Old databases are
  upgraded in place with ``ALTER TABLE ADD COLUMN`` and a one-time deterministic
  ``seq = rowid`` backfill; no row is deleted, no ``event_id`` or ``meaning`` is
  rewritten, and no historical provenance is fabricated (legacy rows keep
  ``provenance IS NULL``, surfaced by readers as ``LEGACY_UNCLASSIFIED``).
- ``load_events`` is UNCHANGED: it still returns 6-field events ordered by
  ``created_at, event_id`` -- the legacy ordering ``KIRA_BETA_V1_CURRENT`` relies
  on (OD-CL-02). Causal/observability reads use ``load_events_causal`` which
  orders by ``seq``.
- ``seq`` is assigned from SQLite's own row identifier (``lastrowid`` on insert,
  ``rowid`` on backfill). Single INSERT + single UPDATE per event in one
  transaction: no ``MAX(seq)+1`` scan, safe under the single-process V1 usage.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS runtime_events ("
    " event_id TEXT PRIMARY KEY,"
    " subject_id TEXT NOT NULL,"
    " session_id TEXT NOT NULL,"
    " event_type TEXT NOT NULL,"
    " meaning TEXT NOT NULL,"
    " created_at TEXT NOT NULL,"
    " seq INTEGER,"
    " provenance TEXT"
    ")"
)

# Columns added by Slice 3. Old databases created before this slice will be
# missing them and are upgraded in place (never reset).
_EVOLVED_COLUMNS = (
    ("seq", "INTEGER"),
    ("provenance", "TEXT"),
)


class RuntimeMemoryError(RuntimeError):
    """Fail-closed error for the durable runtime-memory backend."""


@dataclass(frozen=True)
class RuntimeEvent:
    """One immutable runtime-memory event (never package seed).

    ``seq`` and ``provenance`` are observability-only metadata. They default to
    ``None`` so callers that only know the historical 6-field shape (the
    Character Runtime session facade, legacy tests) keep working unchanged.
    """

    event_id: str
    subject_id: str
    session_id: str
    event_type: str
    meaning: str
    created_at: str
    seq: Optional[int] = None
    provenance: Optional[str] = None

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
        if self.seq is not None and (
            isinstance(self.seq, bool) or not isinstance(self.seq, int)
        ):
            raise RuntimeMemoryError("seq must be an int or None")
        if self.provenance is not None and (
            not isinstance(self.provenance, str) or not self.provenance.strip()
        ):
            raise RuntimeMemoryError("provenance must be a non-empty string or None")


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
            self._migrate()
            self._conn.commit()
        except Exception as exc:
            self._conn.close()
            raise RuntimeMemoryError(f"failed to initialise runtime memory: {exc}") from exc

    @property
    def subject_id(self) -> str:
        return self._subject_id

    # ------------------------------------------------------------------ schema
    def _migrate(self) -> None:
        """Upgrade a pre-Slice-3 database in place. Idempotent, non-destructive.

        Adds any missing evolved column, then deterministically backfills
        ``seq = rowid`` for rows that predate the column. SQLite's ``rowid`` is
        assigned in insertion order for this append-only table, so the backfill
        preserves the original write order as strongly as SQLite allows. Running
        this again is a no-op (``WHERE seq IS NULL`` matches nothing).
        """
        existing = {
            row[1] for row in self._conn.execute("PRAGMA table_info(runtime_events)")
        }
        for column, decl in _EVOLVED_COLUMNS:
            if column not in existing:
                self._conn.execute(
                    f"ALTER TABLE runtime_events ADD COLUMN {column} {decl}"
                )
        self._conn.execute(
            "UPDATE runtime_events SET seq = rowid WHERE seq IS NULL"
        )

    # ------------------------------------------------------------------- write
    def record_event(
        self, event: RuntimeEvent, *, provenance: Optional[str] = None
    ) -> None:
        """Persist one runtime event (duplicate event_id fails closed).

        ``provenance`` may be supplied on the ``RuntimeEvent`` itself or via the
        keyword argument (the event value wins). It is never inferred here.
        ``seq`` is assigned from the row's own SQLite id immediately after
        insertion.
        """
        if not isinstance(event, RuntimeEvent):
            raise RuntimeMemoryError("event must be a RuntimeEvent")
        if event.subject_id != self._subject_id:
            raise RuntimeMemoryError(
                f"event.subject_id {event.subject_id!r} != backend subject {self._subject_id!r}"
            )
        if self._conn is None:
            raise RuntimeMemoryError("runtime memory backend is already closed")
        resolved_provenance = event.provenance if event.provenance is not None else provenance
        if resolved_provenance is not None and (
            not isinstance(resolved_provenance, str) or not resolved_provenance.strip()
        ):
            raise RuntimeMemoryError("provenance must be a non-empty string or None")
        try:
            cursor = self._conn.execute(
                "INSERT INTO runtime_events"
                " (event_id, subject_id, session_id, event_type, meaning, created_at, provenance)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    event.event_id,
                    event.subject_id,
                    event.session_id,
                    event.event_type,
                    event.meaning,
                    event.created_at,
                    resolved_provenance,
                ),
            )
            self._conn.execute(
                "UPDATE runtime_events SET seq = ? WHERE event_id = ?",
                (cursor.lastrowid, event.event_id),
            )
            self._conn.commit()
        except sqlite3.IntegrityError as exc:
            raise RuntimeMemoryError(
                f"duplicate runtime event_id {event.event_id!r}"
            ) from exc

    def set_provenance(self, event_id: str, provenance: str) -> bool:
        """Attach a provenance label to an existing event, once.

        Fail-closed honesty: an event that already carries a provenance label is
        never overwritten (``WHERE provenance IS NULL``). Returns ``True`` when a
        label was actually written.
        """
        if self._conn is None:
            raise RuntimeMemoryError("runtime memory backend is already closed")
        if not isinstance(event_id, str) or not event_id.strip():
            raise RuntimeMemoryError("event_id must be a non-empty string")
        if not isinstance(provenance, str) or not provenance.strip():
            raise RuntimeMemoryError("provenance must be a non-empty string")
        cursor = self._conn.execute(
            "UPDATE runtime_events SET provenance = ?"
            " WHERE event_id = ? AND subject_id = ? AND provenance IS NULL",
            (provenance, event_id, self._subject_id),
        )
        self._conn.commit()
        return cursor.rowcount > 0

    # -------------------------------------------------------------------- read
    def load_events(self, subject_id: str) -> Tuple[RuntimeEvent, ...]:
        """Return all persisted runtime events for ``subject_id``.

        LEGACY ORDER (OD-CL-02): ``ORDER BY created_at, event_id``. This is the
        exact ordering ``KIRA_BETA_V1_CURRENT`` provider-context assembly
        depends on and MUST NOT change. Returns 6-field events (``seq`` /
        ``provenance`` left as ``None``) so historical callers are unaffected.
        """
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

    def load_events_causal(self, subject_id: str) -> Tuple[RuntimeEvent, ...]:
        """Return all persisted runtime events ordered by causal ``seq``.

        This is the observability / Memory Inspector authority: order == write
        order. Events carry ``seq`` and ``provenance`` (``None`` provenance means
        a pre-Slice-3 row -- readers surface it as ``LEGACY_UNCLASSIFIED``).
        """
        if self._conn is None:
            raise RuntimeMemoryError("runtime memory backend is already closed")
        if subject_id != self._subject_id:
            raise RuntimeMemoryError(
                f"subject_id {subject_id!r} != backend subject {self._subject_id!r}"
            )
        rows = self._conn.execute(
            "SELECT event_id, subject_id, session_id, event_type, meaning, created_at,"
            " seq, provenance"
            " FROM runtime_events WHERE subject_id = ? ORDER BY seq, rowid",
            (subject_id,),
        ).fetchall()
        return tuple(
            RuntimeEvent(
                event_id=row[0],
                subject_id=row[1],
                session_id=row[2],
                event_type=row[3],
                meaning=row[4],
                created_at=row[5],
                seq=row[6],
                provenance=row[7],
            )
            for row in rows
        )

    def close(self) -> None:
        """Commit and close this instance's connection."""
        if self._conn is not None:
            self._conn.commit()
            self._conn.close()
            self._conn = None
