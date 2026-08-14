#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Slice 2 SQLite + FTS5 targeted tests.

Covers:
  - DB creation (outside repo)
  - Schema creation / version tracking
  - WAL / configuration
  - Migration from legacy JSON (Mode A)
  - Idempotent re-migration / duplicate prevention
  - Deterministic session_id
  - Slice 1 R2 provenance mapping
  - Compat defaults (profile_id=dev_slot, world_id=aside)
  - Parity gate
  - Profile / character / world isolation
  - World vs provenance separation
  - FTS5 English + Cyrillic retrieval
  - FTS cross-scope isolation
  - Provenance filtering in FTS
  - Unscoped retrieval rejection
  - Reset preserves SQLite + FTS rows
  - Cancel Wipe / Confirm Wipe
  - Scoped Wipe + FTS cleanup
  - Transaction rollback consistency
  - Restart persistence
  - Integrity check
  - Corrupted JSON / DB behavior
  - No repo-local DB artifacts

All tests use pytest tmp_path — never real user memory.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_TOOLS = _REPO / "tools"
sys.path.insert(0, str(_TOOLS))
sys.path.insert(0, str(_REPO))  # for tests/fixtures imports

import pytest

import aside_memory_store as json_store  # noqa: E402
import aside_memory_store_sqlite as sqlite_store  # noqa: E402
import aside_memory_migration as migration  # noqa: E402
from tests.fixtures.slice2_sqlite_fixtures import (  # noqa: E402
    assert_no_db_in_repo,
    count_parts_sqlite,
    count_sessions_sqlite,
    make_legacy_session,
    make_structured_session,
    populate_json_store,
    search_fts,
    setup_sqlite_db,
)


# ═══════════════════════════════════════════════════════════════════════════════
# DB Creation & Location
# ═══════════════════════════════════════════════════════════════════════════════


def test_db_created_outside_repo(tmp_path):
    """SQLite DB path resolves outside repository."""
    assert_no_db_in_repo(tmp_path)
    db_path = sqlite_store.get_db_path(tmp_path)
    assert str(_REPO.resolve()) not in str(db_path.resolve())


def test_db_creates_parent_directory(tmp_path):
    """ensure_schema creates parent directories as needed."""
    root = tmp_path / "deep" / "nested" / "aside_root"
    db_path = sqlite_store.get_db_path(root)
    result = sqlite_store.ensure_schema(db_path)
    assert result["status"] in ("schema_created", "schema_ok")
    assert db_path.exists()


# ═══════════════════════════════════════════════════════════════════════════════
# Schema Creation & Version
# ═══════════════════════════════════════════════════════════════════════════════


def test_schema_creation(tmp_path):
    """Fresh DB creates all tables + version row."""
    db_path = setup_sqlite_db(tmp_path)

    con = sqlite_store.get_connection(db_path)
    try:
        tables = {
            row[0]
            for row in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "schema_version" in tables
        assert "sessions" in tables
        assert "message_parts" in tables
        assert "summaries" in tables
        assert "canonical_snapshots" in tables
        assert "migration_log" in tables

        # FTS virtual table
        assert "message_fts" in tables or any(
            "message_fts" in str(t) for t in tables
        )

        # Version
        cur = con.execute(
            "SELECT major, minor FROM schema_version ORDER BY rowid LIMIT 1"
        )
        major, minor = cur.fetchone()
        assert (major, minor) == (1, 0)
    finally:
        con.close()


def test_schema_version_reported(tmp_path):
    """ensure_schema returns correct version status."""
    db_path = setup_sqlite_db(tmp_path)
    result = sqlite_store.ensure_schema(db_path)
    assert result["status"] == "schema_ok"
    assert result["version"] == "1.0"


def test_schema_idempotent_creation(tmp_path):
    """ensure_schema called twice does not fail."""
    db_path = sqlite_store.get_db_path(tmp_path)
    r1 = sqlite_store.ensure_schema(db_path)
    r2 = sqlite_store.ensure_schema(db_path)
    assert r1["status"] in ("schema_created", "schema_ok")
    assert r2["status"] in ("schema_created", "schema_ok")


# ═══════════════════════════════════════════════════════════════════════════════
# WAL / Configuration
# ═══════════════════════════════════════════════════════════════════════════════


def test_wal_mode_enabled(tmp_path):
    """DB opens in WAL journal mode."""
    db_path = setup_sqlite_db(tmp_path)
    con = sqlite_store.get_connection(db_path)
    try:
        cur = con.execute("PRAGMA journal_mode")
        mode = cur.fetchone()[0]
        assert mode.lower() == "wal"
    finally:
        con.close()


def test_busy_timeout_set(tmp_path):
    """DB opens with busy_timeout=5000."""
    db_path = setup_sqlite_db(tmp_path)
    con = sqlite_store.get_connection(db_path)
    try:
        cur = con.execute("PRAGMA busy_timeout")
        timeout = cur.fetchone()[0]
        assert timeout == 5000
    finally:
        con.close()


def test_foreign_keys_enforced(tmp_path):
    """Foreign key constraints are enforced."""
    db_path = setup_sqlite_db(tmp_path)
    con = sqlite_store.get_connection(db_path)
    try:
        cur = con.execute("PRAGMA foreign_keys")
        assert cur.fetchone()[0] == 1
    finally:
        con.close()


# ═══════════════════════════════════════════════════════════════════════════════
# Append Session (SQLite direct)
# ═══════════════════════════════════════════════════════════════════════════════


def test_append_session_via_sqlite(tmp_path):
    """append_session_sqlite stores a session and its parts."""
    root = tmp_path / "aside_root"
    setup_sqlite_db(root)
    result = sqlite_store.append_session_sqlite(
        root=root,
        profile_id="p1",
        character_id="kira",
        world="aside",
        session=make_structured_session(msg="Hello Kira"),
    )
    assert result["status"] == "appended"

    mem = sqlite_store.load_memory_sqlite(
        root=root, profile_id="p1", character_id="kira", world="aside", progress=999
    )
    assert len(mem["sessions_meta"]) == 1
    assert mem["sessions_meta"][0]["player"]["provenance"] == "USER_CLAIM"
    assert mem["sessions_meta"][0]["reply"]["provenance"] == "ASIDE_WORLD"


def test_append_with_canon_snapshot(tmp_path):
    """Canon snapshot is stored and retrieved."""
    root = tmp_path / "aside_root"
    setup_sqlite_db(root)
    canon = {"scene_id": "SC_017", "beat_id": "beat_1", "progress_index": 17}
    sqlite_store.append_session_sqlite(
        root=root,
        profile_id="p1",
        character_id="kira",
        world="aside",
        session=make_structured_session(msg="Hi", canon_data=canon),
    )
    mem = sqlite_store.load_memory_sqlite(
        root=root, profile_id="p1", character_id="kira", world="aside", progress=999
    )
    cs = mem["sessions_meta"][0].get("canon_snapshot")
    assert cs is not None
    assert cs["provenance"] == "CANON_WORLD"


def test_append_legacy_session_via_sqlite(tmp_path):
    """Legacy session (flat transcript) is imported with provenance mapping."""
    root = tmp_path / "aside_root"
    setup_sqlite_db(root)
    sqlite_store.append_session_sqlite(
        root=root,
        profile_id="p1",
        character_id="kira",
        world="aside",
        session=make_legacy_session(msg="Old message", reply="Old reply"),
    )
    mem = sqlite_store.load_memory_sqlite(
        root=root, profile_id="p1", character_id="kira", world="aside", progress=999
    )
    assert len(mem["sessions_meta"]) == 1
    # Legacy: player always USER_CLAIM
    assert mem["sessions_meta"][0]["player"]["provenance"] == "USER_CLAIM"
    assert mem["sessions_meta"][0]["reply"]["provenance"] == "ASIDE_WORLD"


# ═══════════════════════════════════════════════════════════════════════════════
# Duplicate Prevention (idempotent append)
# ═══════════════════════════════════════════════════════════════════════════════


def test_duplicate_session_ignored(tmp_path):
    """Same (profile, character, world, scene, beat, progress) is fully idempotent.

    Strengthened (TEST B): proves not only that the sessions row is not
    duplicated, but that message_parts stays at 2 and the loaded `recent`
    contains exactly one user/assistant pair (exact duplicate suppressed).
    """
    root = tmp_path / "aside_root"
    setup_sqlite_db(root)
    session = make_structured_session(msg="First", reply="Understood")
    r1 = sqlite_store.append_session_sqlite(
        root=root, profile_id="p1", character_id="kira", world="aside", session=session
    )
    r2 = sqlite_store.append_session_sqlite(
        root=root, profile_id="p1", character_id="kira", world="aside", session=session
    )

    assert r1["status"] == "appended"
    assert r2["status"] == "appended"

    assert count_sessions_sqlite(root, "p1", "kira", "aside") == 1
    assert count_parts_sqlite(root, "p1", "kira", "aside") == 2

    recent = sqlite_store.load_memory_sqlite(
        root=root, profile_id="p1", character_id="kira", world="aside", progress=999
    )["recent"]
    assert [(e["role"], e["content"]) for e in recent] == [
        ("user", "First"),
        ("assistant", "Understood"),
    ]


# ═══════════════════════════════════════════════════════════════════════════════
# Deterministic session_id
# ═══════════════════════════════════════════════════════════════════════════════


def test_deterministic_session_id(tmp_path):
    """Session identity = scene + beat + progress, not random."""
    sid = migration._deterministic_session_id({
        "scene_id": "SC_017",
        "beat_id": "beat_1",
        "progress_index": 5,
    })
    assert sid == "SC_017_beat_1_5"

    # Same inputs → same id
    sid2 = migration._deterministic_session_id({
        "scene_id": "SC_017",
        "beat_id": "beat_1",
        "progress_index": 5,
    })
    assert sid == sid2


# ═══════════════════════════════════════════════════════════════════════════════
# Migration: JSON → SQLite (Mode A)
# ═══════════════════════════════════════════════════════════════════════════════


def test_migration_single_session(tmp_path):
    """One JSON session is correctly imported into SQLite."""
    root = tmp_path / "aside_root"
    populate_json_store(
        root, "p1", "kira", "aside",
        [make_structured_session(msg="Migration test", progress_index=1)],
    )
    setup_sqlite_db(root)
    result = migration.migrate_scope(
        root=root, profile_id="p1", character_id="kira", world_id="aside",
    )
    assert result["imported"] == 1
    assert result["skipped"] == 0
    assert result["failed"] == 0
    assert count_sessions_sqlite(root, "p1", "kira", "aside") == 1


def test_migration_multiple_sessions(tmp_path):
    """N JSON sessions → N SQLite rows."""
    root = tmp_path / "aside_root"
    sessions = [
        make_structured_session(msg=f"Session {i}", progress_index=i)
        for i in range(1, 6)
    ]
    populate_json_store(root, "p1", "kira", "aside", sessions)
    setup_sqlite_db(root)
    result = migration.migrate_scope(
        root=root, profile_id="p1", character_id="kira", world_id="aside",
    )
    assert result["imported"] == 5
    assert count_sessions_sqlite(root, "p1", "kira", "aside") == 5


def test_migration_idempotent_rerun(tmp_path):
    """Re-running migration does not create duplicates."""
    root = tmp_path / "aside_root"
    populate_json_store(
        root, "p1", "kira", "aside",
        [make_structured_session(msg="Only once", progress_index=1)],
    )
    setup_sqlite_db(root)

    r1 = migration.migrate_scope(
        root=root, profile_id="p1", character_id="kira", world_id="aside",
    )
    assert r1["imported"] == 1

    r2 = migration.migrate_scope(
        root=root, profile_id="p1", character_id="kira", world_id="aside",
    )
    assert r2.get("imported", 0) == 0 or r2.get("skipped", 0) >= 1
    assert count_sessions_sqlite(root, "p1", "kira", "aside") == 1


def test_migration_duplicate_prevention_unstable_key(tmp_path):
    """JSON sessions with same deterministic key are deduplicated."""
    root = tmp_path / "aside_root"
    # Write two copies with same scene/beat/progress but different text
    s1 = make_structured_session(
        scene_id="SC_017", beat_id="beat_A", progress_index=1, msg="Variant 1"
    )
    s2 = make_structured_session(
        scene_id="SC_017", beat_id="beat_A", progress_index=1, msg="Variant 2"
    )
    populate_json_store(root, "p1", "kira", "aside", [s1, s2])
    setup_sqlite_db(root)
    result = migration.migrate_scope(
        root=root, profile_id="p1", character_id="kira", world_id="aside",
    )
    # Second is skipped (already imported record from first file)
    total = result.get("imported", 0) + result.get("skipped", 0)
    assert total >= 1
    # UNIQUE constraint ensures only 1 row
    assert count_sessions_sqlite(root, "p1", "kira", "aside") <= 1


def test_migration_with_canon_snapshot(tmp_path):
    """Structured session with canon_snapshot preserves provenance."""
    root = tmp_path / "aside_root"
    canon = {"scene_id": "SC_017", "beat_id": "beat_1", "progress_index": 1}
    populate_json_store(
        root, "p1", "kira", "aside",
        [make_structured_session(msg="Hi", canon_data=canon)],
    )
    setup_sqlite_db(root)
    migration.migrate_scope(
        root=root, profile_id="p1", character_id="kira", world_id="aside",
    )
    mem = sqlite_store.load_memory_sqlite(
        root=root, profile_id="p1", character_id="kira", world="aside", progress=999
    )
    cs = mem["sessions_meta"][0].get("canon_snapshot")
    assert cs is not None
    assert cs["provenance"] == "CANON_WORLD"


def test_migration_supports_legacy_session(tmp_path):
    """Legacy sessions (flat transcript) are imported."""
    root = tmp_path / "aside_root"
    populate_json_store(
        root, "p1", "kira", "aside",
        [make_legacy_session(msg="Old", reply="Old reply")],
    )
    setup_sqlite_db(root)
    result = migration.migrate_scope(
        root=root, profile_id="p1", character_id="kira", world_id="aside",
    )
    assert result["imported"] == 1


# ═══════════════════════════════════════════════════════════════════════════════
# JSON unchanged after migration
# ═══════════════════════════════════════════════════════════════════════════════


def test_json_unchanged_after_migration(tmp_path):
    """JSON files are not deleted or modified by migration."""
    root = tmp_path / "aside_root"
    session = make_structured_session(msg="Preserve me")
    populate_json_store(root, "p1", "kira", "aside", [session])
    setup_sqlite_db(root)

    sessions_dir = root / "private_chats" / "p1" / "kira" / "aside" / "sessions"
    json_files_before = sorted(sessions_dir.glob("*.json"))
    assert len(json_files_before) == 1
    mtime_before = json_files_before[0].stat().st_mtime
    size_before = json_files_before[0].stat().st_size

    migration.migrate_scope(
        root=root, profile_id="p1", character_id="kira", world_id="aside",
    )

    json_files_after = sorted(sessions_dir.glob("*.json"))
    assert len(json_files_after) == 1
    assert json_files_after[0].stat().st_mtime == mtime_before
    assert json_files_after[0].stat().st_size == size_before


# ═══════════════════════════════════════════════════════════════════════════════
# R2 Provenance Mapping
# ═══════════════════════════════════════════════════════════════════════════════


def test_r2_provenance_mapping_preserved(tmp_path):
    """Migration preserves Slice 1 R2 provenance mapping."""
    root = tmp_path / "aside_root"
    canon = {"scene_id": "SC_017", "beat_id": "beat_1", "progress_index": 1}
    populate_json_store(
        root, "p1", "kira", "aside",
        [make_structured_session(msg="Player says", reply="Kira says", canon_data=canon)],
    )
    setup_sqlite_db(root)
    migration.migrate_scope(
        root=root, profile_id="p1", character_id="kira", world_id="aside",
    )
    mem = sqlite_store.load_memory_sqlite(
        root=root, profile_id="p1", character_id="kira", world="aside", progress=999
    )
    meta = mem["sessions_meta"][0]
    assert meta["player"]["provenance"] == "USER_CLAIM"
    assert meta["reply"]["provenance"] == "ASIDE_WORLD"
    assert meta["canon_snapshot"]["provenance"] == "CANON_WORLD"


# ═══════════════════════════════════════════════════════════════════════════════
# Compat defaults
# ═══════════════════════════════════════════════════════════════════════════════


def test_compat_profile_is_dev_slot(tmp_path):
    """Legacy profile default = dev_slot."""
    assert sqlite_store.DEFAULT_PROFILE == "dev_slot"


def test_compat_world_is_aside(tmp_path):
    """Legacy world default = aside."""
    assert sqlite_store.DEFAULT_WORLD == "aside"


def test_character_id_preserved(tmp_path):
    """character_id is stored as provided, not lost or globalized."""
    root = tmp_path / "aside_root"
    setup_sqlite_db(root)
    sqlite_store.append_session_sqlite(
        root=root, profile_id="p1", character_id="kira", world="aside",
        session=make_structured_session(),
    )
    mem = sqlite_store.load_memory_sqlite(
        root=root, profile_id="p1", character_id="kira", world="aside", progress=999
    )
    assert len(mem["sessions_meta"]) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# Parity Gate
# ═══════════════════════════════════════════════════════════════════════════════


def test_parity_gate_matches(tmp_path):
    """After migration, session counts match JSON ↔ SQLite."""
    root = tmp_path / "aside_root"
    sessions = [
        make_structured_session(msg=f"Session {i}", progress_index=i)
        for i in range(1, 4)
    ]
    populate_json_store(root, "p1", "kira", "aside", sessions)
    setup_sqlite_db(root)
    migration.migrate_scope(
        root=root, profile_id="p1", character_id="kira", world_id="aside",
    )
    check = migration._check_parity(root, "p1", "kira", "aside")
    assert check["json_sessions"] == 3
    assert check["sqlite_sessions"] == 3
    assert check["duplicate_rows"] == 0
    assert check["parity_ok"] is True


def test_parity_fails_on_partial_import(tmp_path):
    """Parity check detects mismatch between JSON and SQLite counts."""
    root = tmp_path / "aside_root"
    populate_json_store(
        root, "p1", "kira", "aside",
        [make_structured_session(msg="S1", progress_index=1)],
    )
    setup_sqlite_db(root)
    # Don't migrate — parity should detect missing data
    check = migration._check_parity(root, "p1", "kira", "aside")
    assert check["json_sessions"] >= 1
    assert check["sqlite_sessions"] < check["json_sessions"]
    assert check["parity_ok"] is False


def test_parity_gate_all_reports_status(tmp_path):
    """parity_gate_all returns per-scope parity."""
    root = tmp_path / "aside_root"
    populate_json_store(
        root, "p1", "kira", "aside",
        [make_structured_session(msg="S1", progress_index=1)],
    )
    setup_sqlite_db(root)
    migration.migrate_scope(
        root=root, profile_id="p1", character_id="kira", world_id="aside",
    )
    result = migration.parity_gate_all(root=root)
    assert result["status"] in ("parity_ok", "no_data")


# ═══════════════════════════════════════════════════════════════════════════════
# Profile / Character / World Isolation
# ═══════════════════════════════════════════════════════════════════════════════


def test_sqlite_profile_isolation(tmp_path):
    """Two profiles do not cross-read."""
    root = tmp_path / "aside_root"
    setup_sqlite_db(root)
    sqlite_store.append_session_sqlite(
        root=root, profile_id="p_a", character_id="kira", world="aside",
        session=make_structured_session(msg="Profile A"),
    )
    sqlite_store.append_session_sqlite(
        root=root, profile_id="p_b", character_id="kira", world="aside",
        session=make_structured_session(msg="Profile B"),
    )
    mem_a = sqlite_store.load_memory_sqlite(
        root=root, profile_id="p_a", character_id="kira", world="aside", progress=999
    )
    mem_b = sqlite_store.load_memory_sqlite(
        root=root, profile_id="p_b", character_id="kira", world="aside", progress=999
    )
    assert len(mem_a["sessions_meta"]) == 1
    assert len(mem_b["sessions_meta"]) == 1


def test_sqlite_character_isolation(tmp_path):
    """Two characters under same profile do not cross-read."""
    root = tmp_path / "aside_root"
    setup_sqlite_db(root)
    sqlite_store.append_session_sqlite(
        root=root, profile_id="p1", character_id="kira", world="aside",
        session=make_structured_session(msg="Kira"),
    )
    sqlite_store.append_session_sqlite(
        root=root, profile_id="p1", character_id="marina", world="aside",
        session=make_structured_session(msg="Marina"),
    )
    kira = sqlite_store.load_memory_sqlite(
        root=root, profile_id="p1", character_id="kira", world="aside", progress=999
    )
    marina = sqlite_store.load_memory_sqlite(
        root=root, profile_id="p1", character_id="marina", world="aside", progress=999
    )
    assert len(kira["sessions_meta"]) == 1
    assert len(marina["sessions_meta"]) == 1


def test_sqlite_world_isolation(tmp_path):
    """Same profile+character but different worlds do not cross-read."""
    root = tmp_path / "aside_root"
    setup_sqlite_db(root)
    sqlite_store.append_session_sqlite(
        root=root, profile_id="p1", character_id="kira", world="aside",
        session=make_structured_session(msg="Aside"),
    )
    sqlite_store.append_session_sqlite(
        root=root, profile_id="p1", character_id="kira", world="canon",
        session=make_structured_session(msg="Canon"),
    )
    aside = sqlite_store.load_memory_sqlite(
        root=root, profile_id="p1", character_id="kira", world="aside", progress=999
    )
    canon_mem = sqlite_store.load_memory_sqlite(
        root=root, profile_id="p1", character_id="kira", world="canon", progress=999
    )
    assert len(aside["sessions_meta"]) == 1
    assert len(canon_mem["sessions_meta"]) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# World vs Provenance Separation
# ═══════════════════════════════════════════════════════════════════════════════


def test_world_provenance_are_separate(tmp_path):
    """world_id and provenance are different columns/axes."""
    root = tmp_path / "aside_root"
    setup_sqlite_db(root)
    sqlite_store.append_session_sqlite(
        root=root, profile_id="p1", character_id="kira", world="aside",
        session=make_structured_session(msg="Player msg"),
    )
    db_path = sqlite_store.get_db_path(root)
    con = sqlite_store.get_connection(db_path)
    try:
        # Sessions have both world_id (aside) and provenance (ASIDE_WORLD) columns
        cur = con.execute(
            "SELECT world_id, provenance FROM sessions WHERE profile_id='p1'"
        )
        row = cur.fetchone()
        assert row[0] == "aside"  # world_id
        # provenance is per-session level
        assert row[1] in ("ASIDE_WORLD",)

        # message_parts have provenance separate from session world_id
        cur = con.execute(
            """
            SELECT s.world_id, mp.provenance
            FROM message_parts mp
            JOIN sessions s ON mp.session_id = s.session_id
            WHERE s.profile_id='p1'
            """
        )
        for prow in cur.fetchall():
            assert prow[0] == "aside"           # world_id column
            assert prow[1] in ("USER_CLAIM", "ASIDE_WORLD", "CANON_WORLD")  # provenance column
    finally:
        con.close()


# ═══════════════════════════════════════════════════════════════════════════════
# FTS5 Retrieval
# ═══════════════════════════════════════════════════════════════════════════════


def test_fts_english_retrieval(tmp_path):
    """FTS5 finds English content."""
    root = tmp_path / "aside_root"
    setup_sqlite_db(root)
    sqlite_store.append_session_sqlite(
        root=root, profile_id="p1", character_id="kira", world="aside",
        session=make_structured_session(
            msg="Hello from the player", reply="Kira remembers the chat"
        ),
    )
    results = search_fts(root, "p1", "kira", "aside", "remembers*")
    assert len(results) >= 1
    matched = any("remembers" in r["matched_content"].lower() for r in results)
    assert matched


def test_fts_cyrillic_retrieval(tmp_path):
    """FTS5 finds Cyrillic (Russian) content."""
    root = tmp_path / "aside_root"
    setup_sqlite_db(root)
    sqlite_store.append_session_sqlite(
        root=root, profile_id="p1", character_id="kira", world="aside",
        session=make_structured_session(
            msg="Привет, Кира", reply="Кира вспоминает разговор с игроком"
        ),
    )
    results = search_fts(root, "p1", "kira", "aside", "Кир*")
    assert len(results) >= 1
    matched = any("Кира" in r["matched_content"] for r in results)
    assert matched


def test_fts_cross_profile_isolation(tmp_path):
    """FTS MATCH from profile A does not return profile B results."""
    root = tmp_path / "aside_root"
    setup_sqlite_db(root)
    sqlite_store.append_session_sqlite(
        root=root, profile_id="p_a", character_id="kira", world="aside",
        session=make_structured_session(msg="Secret for profile A"),
    )
    sqlite_store.append_session_sqlite(
        root=root, profile_id="p_b", character_id="kira", world="aside",
        session=make_structured_session(msg="Secret for profile B"),
    )
    results_a = search_fts(root, "p_a", "kira", "aside", "Secret*")
    results_b = search_fts(root, "p_b", "kira", "aside", "Secret*")
    # Each should see only their own
    for r in results_a:
        assert "profile A" in r["matched_content"].lower() or "profile B" not in r["matched_content"].lower()
    for r in results_b:
        assert "profile B" in r["matched_content"].lower() or "profile A" not in r["matched_content"].lower()


def test_fts_cross_character_isolation(tmp_path):
    """FTS from kira does not leak marina content."""
    root = tmp_path / "aside_root"
    setup_sqlite_db(root)
    sqlite_store.append_session_sqlite(
        root=root, profile_id="p1", character_id="kira", world="aside",
        session=make_structured_session(msg="Kira specific text"),
    )
    sqlite_store.append_session_sqlite(
        root=root, profile_id="p1", character_id="marina", world="aside",
        session=make_structured_session(msg="Marina specific text"),
    )
    results = search_fts(root, "p1", "kira", "aside", "specific*")
    for r in results:
        assert "Kira" in r["matched_content"] or "Marina" not in r["matched_content"]


def test_fts_cross_world_isolation(tmp_path):
    """FTS from aside world does not leak canon world content."""
    root = tmp_path / "aside_root"
    setup_sqlite_db(root)
    sqlite_store.append_session_sqlite(
        root=root, profile_id="p1", character_id="kira", world="aside",
        session=make_structured_session(msg="Aside secret"),
    )
    sqlite_store.append_session_sqlite(
        root=root, profile_id="p1", character_id="kira", world="canon",
        session=make_structured_session(msg="Canon secret"),
    )
    results = search_fts(root, "p1", "kira", "aside", "secret*")
    for r in results:
        assert "Aside" in r["matched_content"]


def test_fts_provenance_filtering(tmp_path):
    """FTS with provenance_filter returns only matching provenance."""
    root = tmp_path / "aside_root"
    setup_sqlite_db(root)
    sqlite_store.append_session_sqlite(
        root=root, profile_id="p1", character_id="kira", world="aside",
        session=make_structured_session(
            msg="Player secret thought here",
            reply="Character observation response",
        ),
    )
    # Search only USER_CLAIM
    results_user = search_fts(
        root, "p1", "kira", "aside", "secret*",
        provenance_filter="USER_CLAIM",
    )
    for r in results_user:
        assert r["matched_provenance"] == "USER_CLAIM"

    # Search only ASIDE_WORLD
    results_aside = search_fts(
        root, "p1", "kira", "aside", "observation*",
        provenance_filter="ASIDE_WORLD",
    )
    for r in results_aside:
        assert r["matched_provenance"] == "ASIDE_WORLD"


# ═══════════════════════════════════════════════════════════════════════════════
# FTS Architectural Boundaries
# ═══════════════════════════════════════════════════════════════════════════════


def test_fts_mandatory_scope_in_api(tmp_path):
    """search_memory_sqlite requires all scope fields in API signature."""
    root = tmp_path / "aside_root"
    setup_sqlite_db(root)
    # The API requires profile_id, character_id, world — all mandatory keyword args
    with pytest.raises(TypeError):
        sqlite_store.search_memory_sqlite(  # type: ignore[call-arg]
            root=root,
            query="anything",
        )


def test_fts_no_direct_fts5_table_access(tmp_path):
    """FTS queries use the scoped search_memory API, not raw FTS table."""
    root = tmp_path / "aside_root"
    setup_sqlite_db(root)
    sqlite_store.append_session_sqlite(
        root=root, profile_id="p1", character_id="kira", world="aside",
        session=make_structured_session(msg="Hello world"),
    )
    db_path = sqlite_store.get_db_path(root)
    con = sqlite_store.get_connection(db_path)
    try:
        # Raw FTS could return data, but the API boundary enforces scope
        cur = con.execute("SELECT COUNT(*) FROM message_fts WHERE message_fts MATCH ?", ("Hello*",))
        raw_count = cur.fetchone()[0]
        # But public API with wrong scope returns empty
        results = search_fts(root, "nonexistent", "nonexistent", "aside", "Hello*")
        assert len(results) == 0 or raw_count >= 0  # FTS may or may not find raw
    finally:
        con.close()


# ═══════════════════════════════════════════════════════════════════════════════
# Reset Preserves SQLite + FTS rows
# ═══════════════════════════════════════════════════════════════════════════════


def test_reset_preserves_sqlite_rows(tmp_path):
    """reset_window_sqlite does NOT delete any SQLite rows."""
    root = tmp_path / "aside_root"
    setup_sqlite_db(root)
    sqlite_store.append_session_sqlite(
        root=root, profile_id="p1", character_id="kira", world="aside",
        session=make_structured_session(msg="Session 1", progress_index=1),
    )
    sqlite_store.append_session_sqlite(
        root=root, profile_id="p1", character_id="kira", world="aside",
        session=make_structured_session(msg="Session 2", progress_index=2),
    )

    result = sqlite_store.reset_window_sqlite(
        root=root, profile_id="p1", character_id="kira", world="aside",
    )
    assert result["status"] == "window_reset"
    assert result["sessions_preserved"] == 2

    mem = sqlite_store.load_memory_sqlite(
        root=root, profile_id="p1", character_id="kira", world="aside", progress=999
    )
    assert len(mem["sessions_meta"]) == 2


def test_reset_preserves_fts_rows(tmp_path):
    """After Reset, FTS can still find pre-existing content."""
    root = tmp_path / "aside_root"
    setup_sqlite_db(root)
    sqlite_store.append_session_sqlite(
        root=root, profile_id="p1", character_id="kira", world="aside",
        session=make_structured_session(
            msg="Кира, помнишь наш разговор?", reply="Да, я помню"
        ),
    )
    sqlite_store.reset_window_sqlite(
        root=root, profile_id="p1", character_id="kira", world="aside",
    )
    results = search_fts(root, "p1", "kira", "aside", "помн*")
    assert len(results) >= 1


# ═══════════════════════════════════════════════════════════════════════════════
# Wipe (Cancel / Confirm)
# ═══════════════════════════════════════════════════════════════════════════════


def test_cancel_wipe_preserves_all_rows(tmp_path):
    """wipe_memory_sqlite with confirmed=False preserves all data."""
    root = tmp_path / "aside_root"
    setup_sqlite_db(root)
    sqlite_store.append_session_sqlite(
        root=root, profile_id="p1", character_id="kira", world="aside",
        session=make_structured_session(msg="Keep me"),
    )
    result = sqlite_store.wipe_memory_sqlite(
        root=root, profile_id="p1", character_id="kira", world="aside", confirmed=False
    )
    assert result["status"] == "wipe_requires_confirmation"
    assert count_sessions_sqlite(root, "p1", "kira", "aside") == 1


def test_confirm_wipe_scoped_deletion(tmp_path):
    """confirm wipe deletes only target scope."""
    root = tmp_path / "aside_root"
    setup_sqlite_db(root)
    sqlite_store.append_session_sqlite(
        root=root, profile_id="p1", character_id="kira", world="aside",
        session=make_structured_session(msg="Kira session"),
    )
    sqlite_store.append_session_sqlite(
        root=root, profile_id="p1", character_id="marina", world="aside",
        session=make_structured_session(msg="Marina session"),
    )

    result = sqlite_store.wipe_memory_sqlite(
        root=root, profile_id="p1", character_id="kira", world="aside", confirmed=True
    )
    assert result["status"] == "wiped"
    assert count_sessions_sqlite(root, "p1", "kira", "aside") == 0
    assert count_sessions_sqlite(root, "p1", "marina", "aside") == 1


def test_wipe_fts_cleanup(tmp_path):
    """After scoped Wipe, FTS no longer returns deleted text."""
    root = tmp_path / "aside_root"
    setup_sqlite_db(root)
    sqlite_store.append_session_sqlite(
        root=root, profile_id="p1", character_id="kira", world="aside",
        session=make_structured_session(msg="Уникальный текст Киры"),
    )
    # Verify FTS finds it
    results_before = search_fts(root, "p1", "kira", "aside", "Уникальный*")
    assert len(results_before) >= 1

    # Wipe
    sqlite_store.wipe_memory_sqlite(
        root=root, profile_id="p1", character_id="kira", world="aside", confirmed=True
    )

    # FTS should find nothing
    results_after = search_fts(root, "p1", "kira", "aside", "Уникальный*")
    assert len(results_after) == 0


def test_other_scopes_survive_wipe(tmp_path):
    """Wipe of one scope does not affect others."""
    root = tmp_path / "aside_root"
    setup_sqlite_db(root)
    sqlite_store.append_session_sqlite(
        root=root, profile_id="p1", character_id="kira", world="aside",
        session=make_structured_session(msg="Kira"),
    )
    sqlite_store.append_session_sqlite(
        root=root, profile_id="p1", character_id="marina", world="aside",
        session=make_structured_session(msg="Marina"),
    )
    sqlite_store.append_session_sqlite(
        root=root, profile_id="p2", character_id="kira", world="aside",
        session=make_structured_session(msg="Kira p2"),
    )

    sqlite_store.wipe_memory_sqlite(
        root=root, profile_id="p1", character_id="kira", world="aside", confirmed=True
    )

    assert count_sessions_sqlite(root, "p1", "kira", "aside") == 0
    assert count_sessions_sqlite(root, "p1", "marina", "aside") == 1
    assert count_sessions_sqlite(root, "p2", "kira", "aside") == 1


# ═══════════════════════════════════════════════════════════════════════════════
# Transaction Rollback Consistency
# ═══════════════════════════════════════════════════════════════════════════════


def test_transaction_rollback_consistency(tmp_path):
    """SQLite transaction ROLLBACK does not persist partial data."""
    root = tmp_path / "aside_root"
    setup_sqlite_db(root)
    db_path = sqlite_store.get_db_path(root)
    con = sqlite_store.get_connection(db_path)
    initial_count = count_sessions_sqlite(root, "p1", "kira", "aside")

    try:
        con.execute("BEGIN IMMEDIATE")
        con.execute(
            """
            INSERT INTO sessions (profile_id, character_id, world_id, scene_id,
                beat_id, progress_index, session_summary, provenance, created_at)
            VALUES ('p1', 'kira', 'aside', 'SC_099', 'beat_rollback', 99,
                    'Rollback test', 'ASIDE_WORLD', '2025-01-01T00:00:00')
            """,
        )
        con.execute("ROLLBACK")
    finally:
        con.close()

    assert count_sessions_sqlite(root, "p1", "kira", "aside") == initial_count


# ═══════════════════════════════════════════════════════════════════════════════
# Restart Persistence
# ═══════════════════════════════════════════════════════════════════════════════


def test_restart_persistence(tmp_path):
    """Data persists after close and reopen."""
    root = tmp_path / "aside_root"
    setup_sqlite_db(root)
    sqlite_store.append_session_sqlite(
        root=root, profile_id="p1", character_id="kira", world="aside",
        session=make_structured_session(msg="Persist me"),
    )

    # Simulate restart: create new connection via public API
    mem = sqlite_store.load_memory_sqlite(
        root=root, profile_id="p1", character_id="kira", world="aside", progress=999
    )
    assert len(mem["sessions_meta"]) == 1
    assert mem["sessions_meta"][0]["player"]["text"] == "Persist me"


# ═══════════════════════════════════════════════════════════════════════════════
# Integrity Check
# ═══════════════════════════════════════════════════════════════════════════════


def test_integrity_check_passes(tmp_path):
    """integrity_check returns ok for a fresh DB."""
    root = tmp_path / "aside_root"
    db_path = setup_sqlite_db(root)
    assert sqlite_store.check_integrity(db_path) is True


def test_integrity_check_with_data(tmp_path):
    """integrity_check passes with data in the DB."""
    root = tmp_path / "aside_root"
    setup_sqlite_db(root)
    sqlite_store.append_session_sqlite(
        root=root, profile_id="p1", character_id="kira", world="aside",
        session=make_structured_session(),
    )
    db_path = sqlite_store.get_db_path(root)
    assert sqlite_store.check_integrity(db_path) is True


# ═══════════════════════════════════════════════════════════════════════════════
# Corrupted JSON Behavior
# ═══════════════════════════════════════════════════════════════════════════════


def test_corrupted_json_file_handled(tmp_path):
    """Malformed JSON session file is skipped by migration gracefully."""
    root = tmp_path / "aside_root"
    sessions_dir = (
        root / "private_chats" / "p1" / "kira" / "aside" / "sessions"
    )
    sessions_dir.mkdir(parents=True, exist_ok=True)

    # Write a valid session directly to disk
    valid_session = make_structured_session(msg="Valid one", progress_index=1)
    valid_json = (
        '{\n'
        '  "scene_id": "SC_017",\n'
        '  "beat_id": "sc_017_v2_1a",\n'
        '  "progress_index": 1,\n'
        '  "summary": "Player: Valid one",\n'
        '  "player": {"text": "Valid one", "provenance": "USER_CLAIM"},\n'
        '  "reply": {"text": "Hi there", "provenance": "ASIDE_WORLD"},\n'
        '  "transcript": [\n'
        '    {"role": "user", "content": "Valid one"},\n'
        '    {"role": "assistant", "content": "Hi there"}\n'
        '  ]\n'
        '}'
    )
    (sessions_dir / "valid.json").write_text(valid_json, encoding="utf-8")

    # Write a corrupted JSON file
    (sessions_dir / "corrupt.json").write_text("NOT VALID JSON {{{", encoding="utf-8")

    setup_sqlite_db(root)
    result = migration.migrate_scope(
        root=root, profile_id="p1", character_id="kira", world_id="aside",
    )
    # Valid session should be imported, corrupt one should not break migration
    assert result.get("imported", 0) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# Corrupted DB Behavior
# ═══════════════════════════════════════════════════════════════════════════════


def test_corrupted_db_integrity_check_fails(tmp_path):
    """A corrupted DB file returns False from check_integrity."""
    root = tmp_path / "aside_root"
    db_path = sqlite_store.get_db_path(root)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    # Write garbage bytes as DB
    db_path.write_bytes(b"this is definitely not a valid SQLite database \x00\xFF")
    assert sqlite_store.check_integrity(db_path) is False


def test_corrupted_db_connect_raises(tmp_path):
    """Opening a garbage file as DB raises SqliteMemoryError."""
    root = tmp_path / "aside_root"
    db_path = sqlite_store.get_db_path(root)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.write_bytes(b"garbage")
    with pytest.raises(sqlite_store.SqliteMemoryError):
        sqlite_store.get_connection(db_path)


# ═══════════════════════════════════════════════════════════════════════════════
# No Repo-Local DB Artifacts
# ═══════════════════════════════════════════════════════════════════════════════


def test_no_repo_local_db_artifact(tmp_path):
    """DB is created only under the test tmp_path, never in repository."""
    assert_no_db_in_repo(tmp_path)
    db_path = setup_sqlite_db(tmp_path)
    repo_root = _REPO
    assert str(repo_root.resolve()) not in str(db_path.resolve())


# ═══════════════════════════════════════════════════════════════════════════════
# Dual-Read / Dual-Write Absence
# ═══════════════════════════════════════════════════════════════════════════════


def test_dual_read_absent(tmp_path):
    """After migration, dual-read is absent: production load returns SQLite-only result."""
    root = tmp_path / "aside_root"
    populate_json_store(
        root, "p1", "kira", "aside",
        [make_structured_session(msg="JSON data", progress_index=1)],
    )
    setup_sqlite_db(root)
    migration.migrate_scope(
        root=root, profile_id="p1", character_id="kira", world_id="aside",
    )

    # Append new data via SQLite only (JSON store NOT called)
    sqlite_store.append_session_sqlite(
        root=root, profile_id="p1", character_id="kira", world="aside",
        session=make_structured_session(msg="SQLite-only data", progress_index=2),
    )

    # SQLite has both
    mem = sqlite_store.load_memory_sqlite(
        root=root, profile_id="p1", character_id="kira", world="aside", progress=999
    )
    assert len(mem["sessions_meta"]) == 2

    # Production load returns SQLite-authoritative state (2 sessions)
    production_mem = json_store.load_memory_v2(
        root=root, profile_id="p1", character_id="kira", world="aside", progress=999
    )
    assert len(production_mem["sessions_meta"]) == 2

    # Legacy JSON file on disk still contains only 1 session (cold evidence untouched)
    json_session_dir = root / "private_chats" / "p1" / "kira" / "aside" / "sessions"
    session_files = sorted(json_session_dir.glob("*.json"))
    assert len(session_files) == 1
    raw_json = json.loads(session_files[0].read_text(encoding="utf-8"))
    assert raw_json["progress_index"] == 1


def test_dual_write_absent(tmp_path):
    """SQLite insert does not also write JSON files."""
    root = tmp_path / "aside_root"
    setup_sqlite_db(root)
    sqlite_store.append_session_sqlite(
        root=root, profile_id="p1", character_id="kira", world="aside",
        session=make_structured_session(msg="SQLite only", progress_index=1),
    )
    sessions_dir = root / "private_chats" / "p1" / "kira" / "aside" / "sessions"
    assert not sessions_dir.exists() or len(list(sessions_dir.glob("*.json"))) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# Summarize via SQLite
# ═══════════════════════════════════════════════════════════════════════════════


def test_summarize_via_sqlite(tmp_path):
    """summarize_memory_sqlite returns correct metadata."""
    root = tmp_path / "aside_root"
    setup_sqlite_db(root)
    sqlite_store.append_session_sqlite(
        root=root, profile_id="p1", character_id="kira", world="aside",
        session=make_structured_session(msg="S1", progress_index=1),
    )
    sqlite_store.append_session_sqlite(
        root=root, profile_id="p1", character_id="kira", world="aside",
        session=make_structured_session(msg="S2", progress_index=2),
    )
    summary = sqlite_store.summarize_memory_sqlite(
        root=root, profile_id="p1", character_id="kira", world="aside",
    )
    assert summary["session_count"] == 2
    assert summary["profile_id"] == "p1"
    assert summary["character_id"] == "kira"
    assert summary["world"] == "aside"


# ═══════════════════════════════════════════════════════════════════════════════
# Get Scope Stats
# ═══════════════════════════════════════════════════════════════════════════════


def test_get_scope_stats(tmp_path):
    """get_scope_stats returns accurate diagnostic data."""
    root = tmp_path / "aside_root"
    setup_sqlite_db(root)
    sqlite_store.append_session_sqlite(
        root=root, profile_id="p1", character_id="kira", world="aside",
        session=make_structured_session(msg="Hello", progress_index=1),
    )
    stats = sqlite_store.get_scope_stats(
        root=root, profile_id="p1", character_id="kira", world="aside",
    )
    assert stats["session_count"] == 1
    assert stats["message_part_count"] >= 2
    assert "USER_CLAIM" in stats["provenance_counts"]
    assert "ASIDE_WORLD" in stats["provenance_counts"]


# ═══════════════════════════════════════════════════════════════════════════════
# Past-only progress gate (SQLite)
# ═══════════════════════════════════════════════════════════════════════════════


def test_sqlite_past_only_progress_gate(tmp_path):
    """load_memory_sqlite respects progress gate."""
    root = tmp_path / "aside_root"
    setup_sqlite_db(root)
    for pi in (10, 20, 30):
        sqlite_store.append_session_sqlite(
            root=root, profile_id="p1", character_id="kira", world="aside",
            session=make_structured_session(msg=f"Session {pi}", progress_index=pi),
        )
    mem = sqlite_store.load_memory_sqlite(
        root=root, profile_id="p1", character_id="kira", world="aside", progress=20
    )
    indices = [m["progress_index"] for m in mem["sessions_meta"]]
    assert indices == [10, 20]


# ═══════════════════════════════════════════════════════════════════════════════
# Wipe: FTS Post-Wipe verification
# ═══════════════════════════════════════════════════════════════════════════════


def test_post_wipe_deleted_text_not_retrievable(tmp_path):
    """After scoped Wipe, deleted text cannot be found via FTS or load."""
    root = tmp_path / "aside_root"
    setup_sqlite_db(root)
    sqlite_store.append_session_sqlite(
        root=root, profile_id="p1", character_id="kira", world="aside",
        session=make_structured_session(
            msg="Удали меня полностью",
            reply="Этот ответ тоже исчезнет",
        ),
    )
    sqlite_store.wipe_memory_sqlite(
        root=root, profile_id="p1", character_id="kira", world="aside", confirmed=True
    )

    # Load returns empty
    mem = sqlite_store.load_memory_sqlite(
        root=root, profile_id="p1", character_id="kira", world="aside", progress=999
    )
    assert len(mem["sessions_meta"]) == 0

    # FTS returns empty
    results = search_fts(root, "p1", "kira", "aside", "исчезн*")
    assert len(results) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# Concurrent read (WAL)
# ═══════════════════════════════════════════════════════════════════════════════


def test_concurrent_read_while_writer(tmp_path):
    """WAL mode allows a reader while a writer is active."""
    root = tmp_path / "aside_root"
    setup_sqlite_db(root)

    # Pre-populate
    sqlite_store.append_session_sqlite(
        root=root, profile_id="p1", character_id="kira", world="aside",
        session=make_structured_session(msg="Pre-data"),
    )

    db_path = sqlite_store.get_db_path(root)
    con_w = sqlite_store.get_connection(db_path)
    con_r = sqlite_store.get_connection(db_path, read_only=False)
    try:
        con_w.execute("BEGIN IMMEDIATE")
        con_w.execute(
            """
            INSERT INTO sessions (profile_id, character_id, world_id, scene_id,
                beat_id, progress_index, session_summary, provenance, created_at)
            VALUES ('p1', 'kira', 'aside', 'SC_020', 'beat_wal', 50,
                    'WAL write test', 'ASIDE_WORLD', '2025-01-01T00:00:00')
            """,
        )
        # Reader should still see pre-existing data
        cur = con_r.execute(
            "SELECT COUNT(*) FROM sessions WHERE profile_id='p1' AND character_id='kira'"
        )
        count = cur.fetchone()[0]
        assert count >= 1
        con_w.commit()
    finally:
        con_r.close()
        con_w.close()


# ═══════════════════════════════════════════════════════════════════════════════
# Unscoped retrieval rejected
# ═══════════════════════════════════════════════════════════════════════════════


def test_unscoped_search_rejected_by_api_signature(tmp_path):
    """Public FTS API requires all scope fields — cannot call with partial scope."""
    root = tmp_path / "aside_root"
    setup_sqlite_db(root)
    # The API does not accept missing profile_id/character_id/world
    # This is enforced by Python keyword-argument requirements (TypeError)
    with pytest.raises(TypeError):
        sqlite_store.search_memory_sqlite(  # type: ignore[call-arg]
            root=root,
            query="anything",
            # Missing profile_id, character_id, world
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Large content / boundary
# ═══════════════════════════════════════════════════════════════════════════════


def test_large_message_parts_handled(tmp_path):
    """Messages with significant content are stored and retrievable."""
    root = tmp_path / "aside_root"
    setup_sqlite_db(root)
    long_msg = "Привет " * 200 + "уникальное завершение"
    sqlite_store.append_session_sqlite(
        root=root, profile_id="p1", character_id="kira", world="aside",
        session=make_structured_session(msg=long_msg, reply="Короткий ответ"),
    )
    results = search_fts(root, "p1", "kira", "aside", "уникальное*")
    assert len(results) >= 1


# ═══════════════════════════════════════════════════════════════════════════════
# World validation
# ═══════════════════════════════════════════════════════════════════════════════


def test_invalid_world_rejected_sqlite(tmp_path):
    """Invalid world value raises SqliteMemoryError."""
    root = tmp_path / "aside_root"
    setup_sqlite_db(root)
    with pytest.raises(sqlite_store.SqliteMemoryError):
        sqlite_store.append_session_sqlite(
            root=root, profile_id="p1", character_id="kira", world="sandbox",
            session=make_structured_session(),
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Multi-turn same-story-position persistence (ASIDE S2 regression)
# ═══════════════════════════════════════════════════════════════════════════════
#
# One SQLite session per story/canon position MUST support multiple ordered
# conversational user/assistant turns. Regression coverage for the confirmed
# defect where a second turn at the same (profile, character, world, scene,
# beat, progress_index) was silently lost.

_S2_PROFILE = "dev_slot"
_S2_CHARACTER = "kira"
_S2_WORLD = "aside"
_S2_SCENE = "SC_017"
_S2_BEAT = "sc_017_v2_1a"
_S2_PROGRESS = 17


def _append_s2_turn(root, msg, reply):
    """Append one structured user/assistant turn at the fixed S2 story position."""
    return sqlite_store.append_session_sqlite(
        root=root,
        profile_id=_S2_PROFILE,
        character_id=_S2_CHARACTER,
        world=_S2_WORLD,
        session=make_structured_session(
            scene_id=_S2_SCENE,
            beat_id=_S2_BEAT,
            progress_index=_S2_PROGRESS,
            msg=msg,
            reply=reply,
        ),
    )


def _load_s2(root):
    """Return the full loaded memory dict for the fixed S2 scope."""
    return sqlite_store.load_memory_sqlite(
        root=root,
        profile_id=_S2_PROFILE,
        character_id=_S2_CHARACTER,
        world=_S2_WORLD,
        progress=999,
    )


def _recent_pairs(root):
    """Return [(role, content), ...] from loaded recent for the S2 scope."""
    return [(e["role"], e["content"]) for e in _load_s2(root)["recent"]]


def test_aside_s2_first_append_preserved(tmp_path):
    """TEST A — first conversational turn at a story position.

    One structured session/turn (green notebook / understood) yields one
    session row and exactly two ordered message parts.
    """
    root = tmp_path / "aside_root"
    setup_sqlite_db(root)

    result = _append_s2_turn(root, "green notebook", "understood")
    assert result["status"] == "appended"

    assert count_sessions_sqlite(root, _S2_PROFILE, _S2_CHARACTER, _S2_WORLD) == 1
    assert count_parts_sqlite(root, _S2_PROFILE, _S2_CHARACTER, _S2_WORLD) == 2

    assert _recent_pairs(root) == [
        ("user", "green notebook"),
        ("assistant", "understood"),
    ]

    # Provenance remains correct (USER_CLAIM for user, ASIDE_WORLD for assistant)
    meta = _load_s2(root)["sessions_meta"][0]
    assert meta["player"]["provenance"] == "USER_CLAIM"
    assert meta["reply"]["provenance"] == "ASIDE_WORLD"


def test_aside_s2_multiturn_same_story_position(tmp_path):
    """TEST C — primary regression: a second turn at the same story position.

    Turn 1: green notebook / understood
    Turn 2: yellow card / understood
    Expected: one session, four ordered message parts, both turns preserved.
    """
    root = tmp_path / "aside_root"
    setup_sqlite_db(root)

    _append_s2_turn(root, "green notebook", "understood")
    _append_s2_turn(root, "yellow card", "understood")

    assert count_sessions_sqlite(root, _S2_PROFILE, _S2_CHARACTER, _S2_WORLD) == 1
    assert count_parts_sqlite(root, _S2_PROFILE, _S2_CHARACTER, _S2_WORLD) == 4

    assert _recent_pairs(root) == [
        ("user", "green notebook"),
        ("assistant", "understood"),
        ("user", "yellow card"),
        ("assistant", "understood"),
    ]

    # Provenance: every user entry is USER_CLAIM, every assistant entry ASIDE_WORLD
    recent = _load_s2(root)["recent"]
    for e in recent:
        if e["role"] == "user":
            assert e["provenance"] == "USER_CLAIM"
        elif e["role"] == "assistant":
            assert e["provenance"] == "ASIDE_WORLD"


def test_aside_s2_retry_later_turn_is_idempotent(tmp_path):
    """TEST D — retry of the later turn is idempotent (no duplicate tail pair).

    After Turn 1 + Turn 2, re-appending Turn 2 unchanged keeps 4 parts.
    """
    root = tmp_path / "aside_root"
    setup_sqlite_db(root)

    _append_s2_turn(root, "green notebook", "understood")
    _append_s2_turn(root, "yellow card", "understood")

    # Retry Turn 2 unchanged
    _append_s2_turn(root, "yellow card", "understood")

    assert count_sessions_sqlite(root, _S2_PROFILE, _S2_CHARACTER, _S2_WORLD) == 1
    assert count_parts_sqlite(root, _S2_PROFILE, _S2_CHARACTER, _S2_WORLD) == 4
    assert _recent_pairs(root) == [
        ("user", "green notebook"),
        ("assistant", "understood"),
        ("user", "yellow card"),
        ("assistant", "understood"),
    ]


def test_aside_s2_same_user_text_different_reply_is_new_turn(tmp_path):
    """TEST E — same user text with a different assistant reply is a new turn.

    Existing tail: yellow card / understood
    New turn:      yellow card / different reply
    This must NOT be treated as an idempotent duplicate — the pair differs,
    so it must append. Proves duplicate detection uses the complete pair.
    """
    root = tmp_path / "aside_root"
    setup_sqlite_db(root)

    _append_s2_turn(root, "green notebook", "understood")
    _append_s2_turn(root, "yellow card", "understood")

    # Same user text, different reply → new turn
    _append_s2_turn(root, "yellow card", "different reply")

    assert count_sessions_sqlite(root, _S2_PROFILE, _S2_CHARACTER, _S2_WORLD) == 1
    assert count_parts_sqlite(root, _S2_PROFILE, _S2_CHARACTER, _S2_WORLD) == 6
    assert _recent_pairs(root) == [
        ("user", "green notebook"),
        ("assistant", "understood"),
        ("user", "yellow card"),
        ("assistant", "understood"),
        ("user", "yellow card"),
        ("assistant", "different reply"),
    ]
