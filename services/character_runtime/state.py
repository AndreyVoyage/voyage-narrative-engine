#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Durable Runtime State backend -- explicitly confirmed current runtime facts.

Runtime State is a SEPARATE persistent layer from runtime memory. It is not the
Accepted Character Package, not conversational memory, not model output, not a
Scene, and never the product of automatic inference/extraction. Only an explicit
deterministic operator action (``record_set`` / ``record_adjust`` /
``record_remove``) may create or change it.

Domains: ``FACT`` (arbitrary text), plus the numeric domains ``RELATIONSHIP``
and ``PSYCHOLOGY`` whose ``value`` is a canonical decimal integer in
[-100, 100]. Numeric domains additionally support ``record_adjust`` (an integer
delta that appends a fresh ``SET``; out-of-range transitions are rejected, never
clamped). Absence of a numeric key means UNKNOWN / NOT INITIALIZED -- a delta on
an uninitialized key fails deterministically.

Storage: an append-only state-event ledger in its OWN per-workspace SQLite file
``<root>/runtime_state.sqlite3`` -- the existing ``runtime_memory.sqlite3`` is
never touched or migrated. Current state is DERIVED deterministically from the
ledger (last event per ``domain+key`` wins; ``SET`` present, ``REMOVE`` absent),
so history is fully auditable with no destructive writes.

``seq`` is assigned from SQLite's own row id (single INSERT + single UPDATE in
one transaction), giving a monotonic causal write order under the single-process
V1 usage -- the same technique ``runtime_memory`` uses.

Standard library only. No provider, no network, no canon access. Writes only
under the caller-supplied ``root``.
"""

from __future__ import annotations

import re
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

# ---- V1 application-validated vocabularies (strings only -- adding a domain
#      never changes the runtime_state.sqlite3 schema) -----------------------

DOMAIN_FACT = "FACT"
DOMAIN_RELATIONSHIP = "RELATIONSHIP"
DOMAIN_PSYCHOLOGY = "PSYCHOLOGY"
#: Domains an operator action may write.
ACTIVE_DOMAINS: Tuple[str, ...] = (DOMAIN_FACT, DOMAIN_RELATIONSHIP, DOMAIN_PSYCHOLOGY)
#: Domains whose ``value`` is a canonical decimal integer in [-100, 100] and
#: which additionally support the ADJUST/delta transition.
NUMERIC_DOMAINS: Tuple[str, ...] = (DOMAIN_RELATIONSHIP, DOMAIN_PSYCHOLOGY)

NUMERIC_STATE_MIN = -100
NUMERIC_STATE_MAX = 100

# RELATIONSHIP key: <other_subject_id>.<dimension> ; PSYCHOLOGY key: <dimension>.
_RELATIONSHIP_KEY_RE = re.compile(r"^[a-z0-9_]+\.[a-z0-9_]+$")
_PSYCHOLOGY_KEY_RE = re.compile(r"^[a-z0-9_]+$")

ACTION_SET = "SET"
ACTION_REMOVE = "REMOVE"
ACTIONS: Tuple[str, ...] = (ACTION_SET, ACTION_REMOVE)


def _coerce_state_int(value) -> int:
    """Parse a canonical integer state value; reject %/words/floats/bools."""
    if isinstance(value, bool):
        raise RuntimeStateError("numeric state value must be an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and re.fullmatch(r"-?\d+", value.strip()):
        return int(value.strip())
    raise RuntimeStateError(
        f"numeric state value must be a canonical integer, got {value!r}"
    )


def _validate_numeric_key(domain: str, key: str) -> str:
    key = (key or "").strip()
    if domain == DOMAIN_RELATIONSHIP and not _RELATIONSHIP_KEY_RE.match(key):
        raise RuntimeStateError(
            f"RELATIONSHIP key must match <other_subject_id>.<dimension> "
            f"([a-z0-9_]+.[a-z0-9_]+), got {key!r}"
        )
    if domain == DOMAIN_PSYCHOLOGY and not _PSYCHOLOGY_KEY_RE.match(key):
        raise RuntimeStateError(
            f"PSYCHOLOGY key must match <dimension> ([a-z0-9_]+), got {key!r}"
        )
    return key

#: The only active source kind in V1. A state fact is only ever created by an
#: explicit operator confirmation -- never promoted automatically from memory,
#: a provider response, a Scene, or a model hypothesis.
SOURCE_OPERATOR_CONFIRMED = "OPERATOR_CONFIRMED"
ACTIVE_SOURCE_KINDS: Tuple[str, ...] = (SOURCE_OPERATOR_CONFIRMED,)

_STATE_DB_FILENAME = "runtime_state.sqlite3"

_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS runtime_state_events ("
    " event_id TEXT PRIMARY KEY,"
    " subject_id TEXT NOT NULL,"
    " domain TEXT NOT NULL,"
    " key TEXT NOT NULL,"
    " action TEXT NOT NULL,"
    " value TEXT,"
    " source_kind TEXT NOT NULL,"
    " source_ref TEXT,"
    " created_at TEXT NOT NULL,"
    " seq INTEGER"
    ")"
)


class RuntimeStateError(RuntimeError):
    """Fail-closed error for the durable Runtime State backend."""


@dataclass(frozen=True)
class RuntimeStateEvent:
    """One immutable append-only Runtime State ledger event."""

    event_id: str
    subject_id: str
    domain: str
    key: str
    action: str
    value: Optional[str]
    source_kind: str
    source_ref: Optional[str]
    created_at: str
    seq: Optional[int] = None

    def __post_init__(self) -> None:
        for name, val in (
            ("event_id", self.event_id),
            ("subject_id", self.subject_id),
            ("domain", self.domain),
            ("key", self.key),
            ("action", self.action),
            ("source_kind", self.source_kind),
            ("created_at", self.created_at),
        ):
            if not isinstance(val, str) or not val.strip():
                raise RuntimeStateError(f"{name} must be a non-empty string")
        if self.action not in ACTIONS:
            raise RuntimeStateError(f"action must be one of {ACTIONS}")
        if self.action == ACTION_SET and (
            not isinstance(self.value, str) or self.value == ""
        ):
            raise RuntimeStateError("value must be a non-empty string for a SET event")
        if self.action == ACTION_REMOVE and self.value not in (None, ""):
            raise RuntimeStateError("value must be empty for a REMOVE event")
        if self.source_ref is not None and not isinstance(self.source_ref, str):
            raise RuntimeStateError("source_ref must be a string or None")
        if self.seq is not None and (
            isinstance(self.seq, bool) or not isinstance(self.seq, int)
        ):
            raise RuntimeStateError("seq must be an int or None")


@dataclass(frozen=True)
class CurrentStateEntry:
    """One currently-established runtime fact, derived from the ledger."""

    domain: str
    key: str
    value: str
    source_kind: str
    source_ref: Optional[str]
    seq: int
    event_id: str
    created_at: str


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class RuntimeStateBackend:
    """Append-only, per-root SQLite ledger for Runtime State events."""

    def __init__(self, root: Path, subject_id: str) -> None:
        if not isinstance(subject_id, str) or not subject_id.strip():
            raise RuntimeStateError("subject_id must be a non-empty string")
        root = Path(root)
        root.mkdir(parents=True, exist_ok=True)
        self._subject_id = subject_id
        self._db_path = root / _STATE_DB_FILENAME
        self._conn = sqlite3.connect(str(self._db_path))
        try:
            self._conn.execute(_SCHEMA)
            self._conn.commit()
        except Exception as exc:  # pragma: no cover - defensive
            self._conn.close()
            raise RuntimeStateError(
                f"failed to initialise runtime state: {exc}"
            ) from exc

    @property
    def subject_id(self) -> str:
        return self._subject_id

    @property
    def db_path(self) -> Path:
        return self._db_path

    # ------------------------------------------------------------------- write
    def _append(
        self,
        *,
        domain: str,
        key: str,
        action: str,
        value: Optional[str],
        source_kind: str,
        source_ref: Optional[str],
        event_id: Optional[str],
        created_at: Optional[str],
    ) -> RuntimeStateEvent:
        if self._conn is None:
            raise RuntimeStateError("runtime state backend is already closed")
        domain = (domain or "").strip()
        if domain not in ACTIVE_DOMAINS:
            raise RuntimeStateError(
                f"domain {domain!r} is not active in V1 (active: {ACTIVE_DOMAINS})"
            )
        if not isinstance(key, str) or not key.strip():
            raise RuntimeStateError("key must be a non-empty string")
        key = key.strip()
        if domain in NUMERIC_DOMAINS:
            key = _validate_numeric_key(domain, key)
            if action == ACTION_SET:
                n = _coerce_state_int(value)
                if not (NUMERIC_STATE_MIN <= n <= NUMERIC_STATE_MAX):
                    raise RuntimeStateError(
                        f"numeric state value {n} out of range "
                        f"[{NUMERIC_STATE_MIN}, {NUMERIC_STATE_MAX}]"
                    )
                value = str(n)
        if source_kind not in ACTIVE_SOURCE_KINDS:
            raise RuntimeStateError(
                f"source_kind {source_kind!r} is not active in V1 "
                f"(active: {ACTIVE_SOURCE_KINDS})"
            )
        if source_ref is not None:
            if not isinstance(source_ref, str):
                raise RuntimeStateError("source_ref must be a string or None")
            source_ref = source_ref.strip() or None

        event = RuntimeStateEvent(
            event_id=event_id or f"state-{uuid.uuid4().hex}",
            subject_id=self._subject_id,
            domain=domain,
            key=key,
            action=action,
            value=value if action == ACTION_SET else None,
            source_kind=source_kind,
            source_ref=source_ref,
            created_at=created_at or _now_iso(),
        )
        try:
            cursor = self._conn.execute(
                "INSERT INTO runtime_state_events"
                " (event_id, subject_id, domain, key, action, value,"
                "  source_kind, source_ref, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    event.event_id,
                    event.subject_id,
                    event.domain,
                    event.key,
                    event.action,
                    event.value,
                    event.source_kind,
                    event.source_ref,
                    event.created_at,
                ),
            )
            self._conn.execute(
                "UPDATE runtime_state_events SET seq = ? WHERE event_id = ?",
                (cursor.lastrowid, event.event_id),
            )
            self._conn.commit()
        except sqlite3.IntegrityError as exc:
            raise RuntimeStateError(
                f"duplicate runtime state event_id {event.event_id!r}"
            ) from exc
        return RuntimeStateEvent(
            event_id=event.event_id,
            subject_id=event.subject_id,
            domain=event.domain,
            key=event.key,
            action=event.action,
            value=event.value,
            source_kind=event.source_kind,
            source_ref=event.source_ref,
            created_at=event.created_at,
            seq=cursor.lastrowid,
        )

    def record_set(
        self,
        *,
        key: str,
        value: str,
        domain: str = DOMAIN_FACT,
        source_kind: str = SOURCE_OPERATOR_CONFIRMED,
        source_ref: Optional[str] = None,
        event_id: Optional[str] = None,
        created_at: Optional[str] = None,
    ) -> RuntimeStateEvent:
        """Append a ``SET`` event that establishes/replaces ``domain+key``."""
        if not isinstance(value, str) or not value.strip():
            raise RuntimeStateError("value must be a non-empty string")
        return self._append(
            domain=domain,
            key=key,
            action=ACTION_SET,
            value=value.strip(),
            source_kind=source_kind,
            source_ref=source_ref,
            event_id=event_id,
            created_at=created_at,
        )

    def record_remove(
        self,
        *,
        key: str,
        domain: str = DOMAIN_FACT,
        source_kind: str = SOURCE_OPERATOR_CONFIRMED,
        source_ref: Optional[str] = None,
        event_id: Optional[str] = None,
        created_at: Optional[str] = None,
    ) -> RuntimeStateEvent:
        """Append a ``REMOVE`` event; the fact leaves current state, history stays."""
        return self._append(
            domain=domain,
            key=key,
            action=ACTION_REMOVE,
            value=None,
            source_kind=source_kind,
            source_ref=source_ref,
            event_id=event_id,
            created_at=created_at,
        )

    def current_numeric(self, domain: str, key: str) -> Optional[int]:
        """Current integer value for a numeric ``domain+key``; ``None`` if not
        initialized (absent, or last event was REMOVE)."""
        key = (key or "").strip()
        for entry in self.load_current_state(self._subject_id):
            if entry.domain == domain and entry.key == key:
                return _coerce_state_int(entry.value)
        return None

    def record_adjust(
        self,
        *,
        key: str,
        delta,
        domain: str,
        source_kind: str = SOURCE_OPERATOR_CONFIRMED,
        source_ref: Optional[str] = None,
        event_id: Optional[str] = None,
        created_at: Optional[str] = None,
    ) -> RuntimeStateEvent:
        """Apply an integer delta to an already-initialized numeric value.

        Appends a NEW ``SET`` event ``value = current + delta`` (the earlier
        event is never overwritten, so history proves e.g. ``20 -> 30``).

        Deterministic failures, leaving state unchanged:
        - ``domain`` is not numeric (FACT rejects ADJUST);
        - ``delta`` is not an integer;
        - the key is not initialized (operator must SET an absolute value first);
        - ``current + delta`` falls outside [-100, 100] (rejected, never clamped).
        """
        if domain not in NUMERIC_DOMAINS:
            raise RuntimeStateError(
                f"ADJUST is only valid for numeric domains {NUMERIC_DOMAINS}"
            )
        step = _coerce_state_int(delta)
        key = _validate_numeric_key(domain, (key or "").strip())
        current = self.current_numeric(domain, key)
        if current is None:
            raise RuntimeStateError(
                f"{domain} key {key!r} is not initialized; SET an absolute "
                f"value first"
            )
        new_value = current + step
        if not (NUMERIC_STATE_MIN <= new_value <= NUMERIC_STATE_MAX):
            raise RuntimeStateError(
                f"adjusted value {new_value} out of range "
                f"[{NUMERIC_STATE_MIN}, {NUMERIC_STATE_MAX}]; state unchanged"
            )
        return self._append(
            domain=domain,
            key=key,
            action=ACTION_SET,
            value=str(new_value),
            source_kind=source_kind,
            source_ref=source_ref,
            event_id=event_id,
            created_at=created_at,
        )

    # -------------------------------------------------------------------- read
    def load_events(self, subject_id: str) -> Tuple[RuntimeStateEvent, ...]:
        """Return the full append-only ledger, ordered by causal ``seq``."""
        if self._conn is None:
            raise RuntimeStateError("runtime state backend is already closed")
        if subject_id != self._subject_id:
            raise RuntimeStateError(
                f"subject_id {subject_id!r} != backend subject {self._subject_id!r}"
            )
        rows = self._conn.execute(
            "SELECT event_id, subject_id, domain, key, action, value,"
            " source_kind, source_ref, created_at, seq"
            " FROM runtime_state_events WHERE subject_id = ? ORDER BY seq, rowid",
            (subject_id,),
        ).fetchall()
        return tuple(
            RuntimeStateEvent(
                event_id=r[0],
                subject_id=r[1],
                domain=r[2],
                key=r[3],
                action=r[4],
                value=r[5],
                source_kind=r[6],
                source_ref=r[7],
                created_at=r[8],
                seq=r[9],
            )
            for r in rows
        )

    def load_current_state(self, subject_id: str) -> Tuple[CurrentStateEntry, ...]:
        """Deterministically derive current state from the ledger.

        Order by ``seq``; the last event for a ``domain+key`` wins. ``SET`` ->
        the fact currently exists with that value; ``REMOVE`` -> the fact is
        currently absent. Returns entries sorted by ``(domain, key)``.
        """
        events = self.load_events(subject_id)
        latest: dict = {}
        for e in events:
            latest[(e.domain, e.key)] = e
        current = [
            CurrentStateEntry(
                domain=e.domain,
                key=e.key,
                value=e.value or "",
                source_kind=e.source_kind,
                source_ref=e.source_ref,
                seq=e.seq if e.seq is not None else 0,
                event_id=e.event_id,
                created_at=e.created_at,
            )
            for e in latest.values()
            if e.action == ACTION_SET
        ]
        current.sort(key=lambda c: (c.domain, c.key))
        return tuple(current)

    def close(self) -> None:
        """Commit and close this instance's connection."""
        if self._conn is not None:
            self._conn.commit()
            self._conn.close()
            self._conn = None
