#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Slice 3 runtime-memory evolution tests (offline, stdlib only).

Covers PART A / PART D / PART P:

- backward-compatible in-place migration of a pre-Slice-3 database;
- no row loss / no id or meaning rewrite / no fabricated provenance;
- deterministic causal ``seq`` assignment preserving insertion order;
- ``load_events`` keeps its legacy ``created_at, event_id`` ordering (OD-CL-02);
- ``load_events_causal`` orders by ``seq``;
- migration + reopen are idempotent.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from services.character_runtime.memory import (
    RuntimeEvent,
    RuntimeMemoryBackend,
    RuntimeMemoryError,
)

_OLD_SCHEMA = (
    "CREATE TABLE runtime_events ("
    " event_id TEXT PRIMARY KEY,"
    " subject_id TEXT NOT NULL,"
    " session_id TEXT NOT NULL,"
    " event_type TEXT NOT NULL,"
    " meaning TEXT NOT NULL,"
    " created_at TEXT NOT NULL"
    ")"
)

# Rows inserted in a deliberately non-sorted created_at order so that legacy
# ordering (created_at, event_id) and causal ordering (insertion order) differ.
_LEGACY_ROWS = [
    ("evt-a", "kira", "s-old", "USER_MESSAGE", "первое сообщение", "2026-08-01T00:00:05+00:00"),
    ("evt-b", "kira", "s-old", "CHARACTER_MESSAGE", "первый ответ", "2026-08-01T00:00:05+00:00"),
    ("evt-c", "kira", "s-old", "USER_MESSAGE", "второе сообщение", "2026-08-01T00:00:01+00:00"),
]


def _make_old_db(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    db_path = root / "runtime_memory.sqlite3"
    conn = sqlite3.connect(str(db_path))
    conn.execute(_OLD_SCHEMA)
    conn.executemany(
        "INSERT INTO runtime_events"
        " (event_id, subject_id, session_id, event_type, meaning, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        _LEGACY_ROWS,
    )
    conn.commit()
    conn.close()
    return db_path


def _columns(db_path: Path) -> set:
    conn = sqlite3.connect(str(db_path))
    try:
        return {row[1] for row in conn.execute("PRAGMA table_info(runtime_events)")}
    finally:
        conn.close()


class TestOldSchemaMigration:
    def test_1_old_db_opens(self, tmp_path):
        _make_old_db(tmp_path)
        backend = RuntimeMemoryBackend(tmp_path, "kira")
        backend.close()

    def test_2_no_rows_lost(self, tmp_path):
        _make_old_db(tmp_path)
        backend = RuntimeMemoryBackend(tmp_path, "kira")
        try:
            assert len(backend.load_events("kira")) == len(_LEGACY_ROWS)
            assert len(backend.load_events_causal("kira")) == len(_LEGACY_ROWS)
        finally:
            backend.close()

    def test_3_and_4_event_ids_and_meanings_unchanged(self, tmp_path):
        _make_old_db(tmp_path)
        backend = RuntimeMemoryBackend(tmp_path, "kira")
        try:
            by_id = {e.event_id: e for e in backend.load_events_causal("kira")}
        finally:
            backend.close()
        for event_id, _s, _sess, _t, meaning, _c in _LEGACY_ROWS:
            assert event_id in by_id
            assert by_id[event_id].meaning == meaning

    def test_5_legacy_rows_have_no_fabricated_provenance(self, tmp_path):
        _make_old_db(tmp_path)
        backend = RuntimeMemoryBackend(tmp_path, "kira")
        try:
            for event in backend.load_events_causal("kira"):
                assert event.provenance is None
        finally:
            backend.close()

    def test_6_deterministic_seq_preserves_insertion_order(self, tmp_path):
        _make_old_db(tmp_path)
        backend = RuntimeMemoryBackend(tmp_path, "kira")
        try:
            causal = backend.load_events_causal("kira")
        finally:
            backend.close()
        assert [e.event_id for e in causal] == ["evt-a", "evt-b", "evt-c"]
        seqs = [e.seq for e in causal]
        assert seqs == sorted(seqs)
        assert all(isinstance(s, int) for s in seqs)

    def test_7_causal_read_uses_seq_not_timestamp(self, tmp_path):
        _make_old_db(tmp_path)
        backend = RuntimeMemoryBackend(tmp_path, "kira")
        try:
            causal = [e.event_id for e in backend.load_events_causal("kira")]
            legacy = [e.event_id for e in backend.load_events("kira")]
        finally:
            backend.close()
        # legacy: created_at then event_id -> evt-c (00:00:01) first
        assert legacy == ["evt-c", "evt-a", "evt-b"]
        # causal: write order -> evt-a, evt-b, evt-c
        assert causal == ["evt-a", "evt-b", "evt-c"]
        assert causal != legacy

    def test_8_legacy_read_still_legacy_order_after_migration(self, tmp_path):
        _make_old_db(tmp_path)
        backend = RuntimeMemoryBackend(tmp_path, "kira")
        try:
            legacy = [e.event_id for e in backend.load_events("kira")]
            # load_events must not expose seq/provenance
            for e in backend.load_events("kira"):
                assert e.seq is None
                assert e.provenance is None
        finally:
            backend.close()
        assert legacy == ["evt-c", "evt-a", "evt-b"]

    def test_9_and_10_migration_idempotent_on_reopen(self, tmp_path):
        _make_old_db(tmp_path)
        b1 = RuntimeMemoryBackend(tmp_path, "kira")
        try:
            first = [(e.event_id, e.seq, e.provenance) for e in b1.load_events_causal("kira")]
        finally:
            b1.close()
        b2 = RuntimeMemoryBackend(tmp_path, "kira")
        try:
            second = [(e.event_id, e.seq, e.provenance) for e in b2.load_events_causal("kira")]
        finally:
            b2.close()
        assert first == second
        assert "seq" in _columns(tmp_path / "runtime_memory.sqlite3")
        assert "provenance" in _columns(tmp_path / "runtime_memory.sqlite3")


class TestProvenanceAndSeqOnNewRows:
    def test_record_event_assigns_monotonic_seq(self, tmp_path):
        backend = RuntimeMemoryBackend(tmp_path, "kira")
        try:
            for i in range(3):
                backend.record_event(RuntimeEvent(
                    event_id=f"e{i}", subject_id="kira", session_id="s1",
                    event_type="USER_MESSAGE", meaning=f"m{i}",
                    created_at="2026-08-29T00:00:00+00:00",
                ))
            causal = backend.load_events_causal("kira")
        finally:
            backend.close()
        seqs = [e.seq for e in causal]
        assert seqs == sorted(seqs) and len(set(seqs)) == 3
        assert [e.event_id for e in causal] == ["e0", "e1", "e2"]

    def test_set_provenance_writes_once_and_never_overwrites(self, tmp_path):
        backend = RuntimeMemoryBackend(tmp_path, "kira")
        try:
            backend.record_event(RuntimeEvent(
                event_id="e0", subject_id="kira", session_id="s1",
                event_type="USER_MESSAGE", meaning="m",
                created_at="2026-08-29T00:00:00+00:00",
            ))
            assert backend.set_provenance("e0", "USER_STATED") is True
            assert backend.set_provenance("e0", "CHARACTER_UTTERANCE") is False
            event = backend.load_events_causal("kira")[0]
            assert event.provenance == "USER_STATED"
        finally:
            backend.close()

    def test_record_event_accepts_plain_six_field_event(self, tmp_path):
        """The Character Runtime session facade still passes 6-field events."""
        backend = RuntimeMemoryBackend(tmp_path, "kira")
        try:
            backend.record_event(RuntimeEvent(
                "evt-x", "kira", "s1", "USER_MESSAGE", "hi",
                "2026-08-29T00:00:00+00:00",
            ))
            events = backend.load_events("kira")
            assert events[0].event_id == "evt-x"
        finally:
            backend.close()

    def test_record_event_provenance_kwarg(self, tmp_path):
        backend = RuntimeMemoryBackend(tmp_path, "kira")
        try:
            backend.record_event(
                RuntimeEvent(
                    "evt-x", "kira", "s1", "SCENE_EVENT", "hi",
                    "2026-08-29T00:00:00+00:00",
                ),
                provenance="SCENE_SETUP",
            )
            assert backend.load_events_causal("kira")[0].provenance == "SCENE_SETUP"
        finally:
            backend.close()

    def test_bad_provenance_rejected(self, tmp_path):
        backend = RuntimeMemoryBackend(tmp_path, "kira")
        try:
            with pytest.raises(RuntimeMemoryError):
                backend.record_event(
                    RuntimeEvent(
                        "evt-x", "kira", "s1", "USER_MESSAGE", "hi",
                        "2026-08-29T00:00:00+00:00",
                    ),
                    provenance="   ",
                )
        finally:
            backend.close()
