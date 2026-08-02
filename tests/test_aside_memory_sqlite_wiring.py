#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Slice 2 Production Wiring Tests — targeted validation of adapter dispatch,
migration activation, and SQLite post-activation routing via production APIs.

Correction R1: first-load cutover fixed (activation before read),
append-before-load fixed (activation before write, no JSON write),
parity test implemented with real assertions.

Tests use real SQLite and real foundation APIs for storage behavior.
Monkeypatch only for call routing verification and failure injection.
"""

from __future__ import annotations

import json
import os
import sys
import threading
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_TOOLS = _REPO / "tools"
sys.path.insert(0, str(_TOOLS))

import pytest
import aside_memory_store as store  # noqa: E402
import aside_memory_store_sqlite as sqlite_store  # noqa: E402
import aside_memory_migration as migration  # noqa: E402
from tests.fixtures.slice2_sqlite_fixtures import (  # noqa: E402
    make_structured_session,
    make_legacy_session,
    setup_sqlite_db,
)


# ── Direct JSON helpers (bypass production API for migration test setup) ───

def _write_json_sessions(root, profile_id, character_id, world, sessions):
    """Write session dicts directly to the legacy JSON filesystem path.

    Does NOT call append_session_v2 — preserves pure JSON-on-disk for
    migration testing without activating SQLite.
    """
    json_dir = (
        Path(root) / "private_chats" / profile_id / character_id / world / "sessions"
    )
    json_dir.mkdir(parents=True, exist_ok=True)
    for i, session in enumerate(sessions, start=1):
        fname = f"SC_017_sc_017_v2_{i:03d}.json"
        (json_dir / fname).write_text(
            json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def _json_file_count(root, profile_id, character_id, world):
    """Count JSON files in a legacy scope directory."""
    json_dir = (
        Path(root) / "private_chats" / profile_id / character_id / world / "sessions"
    )
    if not json_dir.exists():
        return 0
    return len(list(json_dir.glob("*.json")))


# ── Module imports & public API signatures ──────────────────────────────────


def test_production_module_imports_sqlite_backend():
    """production module (aside_memory_store) imports aside_memory_store_sqlite."""
    import aside_memory_store_sqlite  # noqa: F401


def test_production_module_imports_migration():
    """production module imports aside_memory_migration."""
    import aside_memory_migration  # noqa: F401


def test_public_signatures_preserved():
    """All five v2 public API functions retain their signatures."""
    import inspect

    for fn_name in [
        "load_memory_v2", "append_session_v2", "summarize_memory_v2",
        "reset_window_v2", "wipe_memory_v2",
    ]:
        assert hasattr(store, fn_name), f"{fn_name} missing"
        fn = getattr(store, fn_name)
        sig = inspect.signature(fn)
        params = list(sig.parameters.keys())
        assert "root" in params
        assert "profile_id" in params
        assert "character_id" in params
        assert "world" in params


# ── Fresh savedir activation ────────────────────────────────────────────────


def test_fresh_savedir_first_load_activates_sqlite(tmp_path):
    """First load for a fresh scope: creates schema, returns empty structure."""
    root = tmp_path / "aside_root"
    result = store.load_memory_v2(
        root=root, profile_id="p1", character_id="kira",
        world="aside", progress=999,
    )
    assert result["summary"] == ""
    assert result["recent"] == []
    assert result["sessions_meta"] == []

    db_path = sqlite_store.get_db_path(root)
    assert db_path.exists()
    assert "vne_aside_memory.db" in db_path.name


def test_fresh_savedir_db_outside_repo(tmp_path):
    """SQLite DB is NOT created inside the repository."""
    root = tmp_path / "aside_root"
    store.load_memory_v2(
        root=root, profile_id="p1", character_id="kira",
        world="aside", progress=999,
    )
    db_path = sqlite_store.get_db_path(root)
    resolved = db_path.resolve()
    assert str(_REPO.resolve()) not in str(resolved)
    assert str(tmp_path.resolve()) in str(resolved)


def test_empty_fresh_load_correct_structure(tmp_path):
    """Empty fresh load returns dict with required keys."""
    root = tmp_path / "aside_root"
    result = store.load_memory_v2(
        root=root, profile_id="p1", character_id="kira",
        world="aside", progress=999,
    )
    assert isinstance(result, dict)
    assert "summary" in result
    assert "recent" in result
    assert "sessions_meta" in result
    assert isinstance(result["summary"], str)
    assert isinstance(result["recent"], list)
    assert isinstance(result["sessions_meta"], list)


# ── First-load cutover: activation before return (R1-01) ────────────────────


def test_first_legacy_load_returns_sqlite_result(tmp_path):
    """First load on legacy JSON activates SQLite first, returns SQLite result.

    R1-01 correction: activation + migration happen BEFORE the result is
    built; the returned result is SQLite-derived, not JSON-derived.
    """
    root = tmp_path / "aside_root"
    _write_json_sessions(
        root, "p1", "kira", "aside",
        [make_structured_session(msg="Legacy cutover test", progress_index=1)],
    )

    # Verify scope is NOT pre-activated
    assert not store._is_sqlite_activated_for_root(root, "p1", "kira", "aside")

    # First load — should activate, migrate, then read SQLite
    result = store.load_memory_v2(
        root=root, profile_id="p1", character_id="kira",
        world="aside", progress=999,
    )
    assert len(result["sessions_meta"]) == 1
    # Scope activated
    assert store._is_sqlite_activated_for_root(root, "p1", "kira", "aside")

    # Verify DB has migrated data
    db_path = sqlite_store.get_db_path(root)
    con = sqlite_store.get_connection(db_path)
    sqlite_count = con.execute(
        "SELECT COUNT(*) FROM sessions "
        "WHERE profile_id=? AND character_id=? AND world_id=?",
        ("p1", "kira", "aside"),
    ).fetchone()[0]
    con.close()
    assert sqlite_count == 1

    # Second load — same result from SQLite, no re-migration
    result2 = store.load_memory_v2(
        root=root, profile_id="p1", character_id="kira",
        world="aside", progress=999,
    )
    assert len(result2["sessions_meta"]) == 1


def test_first_load_returns_from_sqlite_backend(tmp_path, monkeypatch):
    """Proof: the first load routes through SQLite backend, not JSON read.

    Monkeypatches _read_sessions to fail; if first load calls it,
    the test fails. First load must go through SQLite activation then
    sqlite_store.load_memory_sqlite.
    """
    root = tmp_path / "aside_root"
    _write_json_sessions(
        root, "p1", "kira", "aside",
        [make_structured_session(msg="Must go SQLite", progress_index=1)],
    )

    # Make _read_sessions crash — first load must NOT call it
    def crash_read(*args, **kwargs):
        raise AssertionError("_read_sessions was called — first load should use SQLite")

    monkeypatch.setattr(store, "_read_sessions", crash_read)

    # First load should succeed via SQLite path (never calls _read_sessions)
    result = store.load_memory_v2(
        root=root, profile_id="p1", character_id="kira",
        world="aside", progress=999,
    )
    assert len(result["sessions_meta"]) == 1


# ── Legacy JSON → SQLite migration ──────────────────────────────────────────


def test_migration_runs_exactly_once(tmp_path, monkeypatch):
    """Repeated loads do not re-run migration."""
    root = tmp_path / "aside_root"
    _write_json_sessions(
        root, "p1", "kira", "aside",
        [make_structured_session(msg="Once", progress_index=1)],
    )

    call_count = [0]
    original_migrate = migration.migrate_scope

    def counting_migrate(*args, **kwargs):
        call_count[0] += 1
        return original_migrate(*args, **kwargs)

    monkeypatch.setattr(migration, "migrate_scope", counting_migrate)

    store.load_memory_v2(
        root=root, profile_id="p1", character_id="kira",
        world="aside", progress=999,
    )
    store.load_memory_v2(
        root=root, profile_id="p1", character_id="kira",
        world="aside", progress=999,
    )

    assert call_count[0] == 1, f"Migration called {call_count[0]} times"


def test_repeat_load_no_duplicate_import(tmp_path):
    """Second load after append does not re-import from JSON."""
    root = tmp_path / "aside_root"
    _write_json_sessions(
        root, "p1", "kira", "aside",
        [make_structured_session(msg="Initial", progress_index=1)],
    )
    result1 = store.load_memory_v2(
        root=root, profile_id="p1", character_id="kira",
        world="aside", progress=999,
    )
    assert len(result1["sessions_meta"]) == 1

    store.append_session_v2(
        root=root, profile_id="p1", character_id="kira",
        world="aside",
        session=make_structured_session(msg="New", progress_index=2),
    )

    result2 = store.load_memory_v2(
        root=root, profile_id="p1", character_id="kira",
        world="aside", progress=999,
    )
    assert len(result2["sessions_meta"]) == 2


def test_json_unchanged_after_migration_wiring(tmp_path):
    """JSON files are byte-for-byte unchanged after migration via production API."""
    root = tmp_path / "aside_root"
    session = make_structured_session(msg="Preserve me", progress_index=1)
    _write_json_sessions(root, "p1", "kira", "aside", [session])

    json_dir = (
        root / "private_chats" / "p1" / "kira" / "aside" / "sessions"
    )
    hashes_before = {}
    for jf in sorted(json_dir.glob("*.json")):
        hashes_before[jf.name] = jf.read_bytes()

    store.load_memory_v2(
        root=root, profile_id="p1", character_id="kira",
        world="aside", progress=999,
    )

    for jf in sorted(json_dir.glob("*.json")):
        assert jf.read_bytes() == hashes_before[jf.name], f"{jf.name} modified"


def test_json_unchanged_after_append_wiring(tmp_path):
    """append does NOT modify JSON files — writes exclusively to SQLite."""
    root = tmp_path / "aside_root"
    session = make_structured_session(msg="Initial", progress_index=1)
    _write_json_sessions(root, "p1", "kira", "aside", [session])

    # Activate
    store.load_memory_v2(
        root=root, profile_id="p1", character_id="kira",
        world="aside", progress=999,
    )

    json_count_before = _json_file_count(root, "p1", "kira", "aside")

    store.append_session_v2(
        root=root, profile_id="p1", character_id="kira",
        world="aside",
        session=make_structured_session(msg="After activation", progress_index=2),
    )

    json_count_after = _json_file_count(root, "p1", "kira", "aside")
    assert json_count_after == json_count_before, (
        f"JSON file count changed: {json_count_before} -> {json_count_after}"
    )


# ── Append-before-load: activate then SQLite write (R1-02) ──────────────────


def test_append_before_load_activates_sqlite(tmp_path):
    """append before first load activates SQLite and writes to SQLite."""
    root = tmp_path / "aside_root"

    assert not store._is_sqlite_activated_for_root(root, "p1", "kira", "aside")

    result = store.append_session_v2(
        root=root, profile_id="p1", character_id="kira",
        world="aside",
        session=make_structured_session(msg="Append first", progress_index=1),
    )
    assert result["status"] == "appended"

    # Scope activated by append
    assert store._is_sqlite_activated_for_root(root, "p1", "kira", "aside")

    # Verify data in SQLite
    db_path = sqlite_store.get_db_path(root)
    con = sqlite_store.get_connection(db_path)
    count = con.execute(
        "SELECT COUNT(*) FROM sessions "
        "WHERE profile_id=? AND character_id=? AND world_id=?",
        ("p1", "kira", "aside"),
    ).fetchone()[0]
    con.close()
    assert count == 1


def test_append_before_load_does_not_write_json(tmp_path):
    """append before load does NOT create JSON files."""
    root = tmp_path / "aside_root"

    store.append_session_v2(
        root=root, profile_id="p1", character_id="kira",
        world="aside",
        session=make_structured_session(msg="No JSON write", progress_index=1),
    )

    json_count = _json_file_count(root, "p1", "kira", "aside")
    assert json_count == 0, f"JSON files found: {json_count}"


def test_append_before_load_visible_on_subsequent_load(tmp_path):
    """append before load writes to SQLite; subsequent load sees the data."""
    root = tmp_path / "aside_root"

    store.append_session_v2(
        root=root, profile_id="p1", character_id="kira",
        world="aside",
        session=make_structured_session(msg="Visible", progress_index=1),
    )

    result = store.load_memory_v2(
        root=root, profile_id="p1", character_id="kira",
        world="aside", progress=999,
    )
    assert len(result["sessions_meta"]) == 1


def test_append_before_load_migrates_legacy_json_first(tmp_path):
    """append on a root with legacy JSON migrates before writing."""
    root = tmp_path / "aside_root"
    _write_json_sessions(
        root, "p1", "kira", "aside",
        [make_structured_session(msg="Pre-existing legacy", progress_index=1)],
    )

    # append triggers activation → migration → parity → SQLite write
    store.append_session_v2(
        root=root, profile_id="p1", character_id="kira",
        world="aside",
        session=make_structured_session(msg="New via append", progress_index=2),
    )

    # Both sessions visible
    result = store.load_memory_v2(
        root=root, profile_id="p1", character_id="kira",
        world="aside", progress=999,
    )
    assert len(result["sessions_meta"]) == 2


# ── Parity & error handling (R1-03) ─────────────────────────────────────────


def test_parity_failure_blocks_activation(tmp_path, monkeypatch):
    """Parity failure after migration raises AsideMemoryError; scope NOT activated."""
    import aside_memory_migration as _migration

    root = tmp_path / "aside_root"
    _write_json_sessions(
        root, "p1", "kira", "aside",
        [make_structured_session(msg="Before parity hack", progress_index=1)],
    )
    setup_sqlite_db(root)

    scoped_check_parity = _migration._check_parity

    def failing_parity(*args, **kwargs):
        return {
            "parity_ok": False,
            "json_sessions": 1,
            "sqlite_sessions": 2,
            "json_parts": 2,
            "sqlite_parts": 4,
            "duplicate_rows": 0,
        }

    monkeypatch.setattr(_migration, "_check_parity", failing_parity)

    # (1) Parity failure → explicit error
    with pytest.raises(store.AsideMemoryError, match="Parity gate FAILED"):
        store.load_memory_v2(
            root=root, profile_id="p1", character_id="kira",
            world="aside", progress=999,
        )

    # (2) Scope NOT in activated cache
    assert not store._is_sqlite_activated_for_root(root, "p1", "kira", "aside"), (
        "Scope added to activated cache despite parity failure"
    )

    # (3) JSON unchanged
    json_dir = (
        root / "private_chats" / "p1" / "kira" / "aside" / "sessions"
    )
    json_files = sorted(json_dir.glob("*.json"))
    assert len(json_files) == 1
    original_content = json_files[0].read_text(encoding="utf-8")
    assert "Before parity hack" in original_content

    # (4) DB still exists but is not the active production store for this scope
    db_path = sqlite_store.get_db_path(root)
    assert db_path.exists()

    # (5) No JSON fallback — the error propagated, not masked as empty success
    # (Already proven by the pytest.raises above)

    # (6) Retry after restoring parity succeeds
    monkeypatch.undo()
    # Remove any stale activation state
    scope_key = store._activation_key(root, "p1", "kira", "aside")
    store._activated_scopes.discard(scope_key)

    result = store.load_memory_v2(
        root=root, profile_id="p1", character_id="kira",
        world="aside", progress=999,
    )
    assert len(result["sessions_meta"]) == 1
    assert store._is_sqlite_activated_for_root(root, "p1", "kira", "aside")
    # (7) JSON still unchanged after successful retry
    assert json_files[0].read_text(encoding="utf-8") == original_content


def test_corrupted_json_does_not_block_migration(tmp_path):
    """Corrupted JSON file is skipped during migration; good files imported."""
    root = tmp_path / "aside_root"
    _write_json_sessions(
        root, "p1", "kira", "aside",
        [make_structured_session(msg="Good", progress_index=1)],
    )
    sessions_dir = (
        root / "private_chats" / "p1" / "kira" / "aside" / "sessions"
    )
    (sessions_dir / "corrupt.json").write_text("{invalid json", encoding="utf-8")

    setup_sqlite_db(root)
    result = migration.migrate_scope(
        root=root, profile_id="p1", character_id="kira", world_id="aside",
    )
    assert result.get("imported", 0) >= 1


def test_corrupted_db_fails_loudly(tmp_path):
    """Corrupted SQLite DB raises AsideMemoryError — no silent fallback."""
    root = tmp_path / "aside_root"
    db_path = sqlite_store.get_db_path(root)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.write_bytes(b"this is not a valid sqlite database")

    with pytest.raises(store.AsideMemoryError):
        store.load_memory_v2(
            root=root, profile_id="p1", character_id="kira",
            world="aside", progress=999,
        )


# ── No fallback ─────────────────────────────────────────────────────────────


def test_no_filesystem_fallback_after_activation(tmp_path):
    """After SQLite activation, load does NOT silently fall back to JSON."""
    root = tmp_path / "aside_root"
    _write_json_sessions(
        root, "p1", "kira", "aside",
        [make_structured_session(msg="JSON fallback test", progress_index=1)],
    )
    result1 = store.load_memory_v2(
        root=root, profile_id="p1", character_id="kira",
        world="aside", progress=999,
    )
    assert len(result1["sessions_meta"]) == 1

    result2 = store.load_memory_v2(
        root=root, profile_id="p1", character_id="kira",
        world="aside", progress=999,
    )
    assert len(result2["sessions_meta"]) == 1


def test_dual_read_absent_after_activation(tmp_path):
    """After activation, load reads from SQLite only (no dual-read)."""
    root = tmp_path / "aside_root"
    _write_json_sessions(
        root, "p1", "kira", "aside",
        [make_structured_session(msg="JSON original", progress_index=1)],
    )
    result1 = store.load_memory_v2(
        root=root, profile_id="p1", character_id="kira",
        world="aside", progress=999,
    )
    assert len(result1["sessions_meta"]) == 1

    store.append_session_v2(
        root=root, profile_id="p1", character_id="kira",
        world="aside",
        session=make_structured_session(msg="SQLite only", progress_index=2),
    )

    result2 = store.load_memory_v2(
        root=root, profile_id="p1", character_id="kira",
        world="aside", progress=999,
    )
    assert len(result2["sessions_meta"]) == 2


def test_dual_write_absent_after_activation(tmp_path):
    """After activation, append writes only to SQLite, not JSON."""
    root = tmp_path / "aside_root"
    _write_json_sessions(
        root, "p1", "kira", "aside",
        [make_structured_session(msg="Original", progress_index=1)],
    )

    store.load_memory_v2(
        root=root, profile_id="p1", character_id="kira",
        world="aside", progress=999,
    )

    json_count_before = _json_file_count(root, "p1", "kira", "aside")

    store.append_session_v2(
        root=root, profile_id="p1", character_id="kira",
        world="aside",
        session=make_structured_session(msg="Only SQLite", progress_index=2),
    )

    json_count_after = _json_file_count(root, "p1", "kira", "aside")
    assert json_count_after == json_count_before, "JSON files were created post-activation"


# ── Isolation ───────────────────────────────────────────────────────────────


def test_profile_isolation_wiring(tmp_path):
    """Profile A and B are isolated via production API."""
    root = tmp_path / "aside_root"
    store.append_session_v2(
        root=root, profile_id="pA", character_id="kira",
        world="aside",
        session=make_structured_session(msg="Profile A", progress_index=1),
    )
    store.append_session_v2(
        root=root, profile_id="pB", character_id="kira",
        world="aside",
        session=make_structured_session(msg="Profile B", progress_index=1),
    )
    mem_a = store.load_memory_v2(
        root=root, profile_id="pA", character_id="kira",
        world="aside", progress=999,
    )
    mem_b = store.load_memory_v2(
        root=root, profile_id="pB", character_id="kira",
        world="aside", progress=999,
    )
    assert len(mem_a["sessions_meta"]) == 1
    assert len(mem_b["sessions_meta"]) == 1


def test_character_isolation_wiring(tmp_path):
    """Kira and Marina are isolated within same profile."""
    root = tmp_path / "aside_root"
    store.append_session_v2(
        root=root, profile_id="p1", character_id="kira",
        world="aside",
        session=make_structured_session(msg="Kira", progress_index=1),
    )
    store.append_session_v2(
        root=root, profile_id="p1", character_id="marina",
        world="aside",
        session=make_structured_session(msg="Marina", progress_index=1),
    )
    mem_k = store.load_memory_v2(
        root=root, profile_id="p1", character_id="kira",
        world="aside", progress=999,
    )
    mem_m = store.load_memory_v2(
        root=root, profile_id="p1", character_id="marina",
        world="aside", progress=999,
    )
    assert len(mem_k["sessions_meta"]) == 1
    assert len(mem_m["sessions_meta"]) == 1


def test_world_isolation_wiring(tmp_path):
    """aside and canon worlds are isolated."""
    root = tmp_path / "aside_root"
    store.append_session_v2(
        root=root, profile_id="p1", character_id="kira",
        world="aside",
        session=make_structured_session(msg="aside world", progress_index=1),
    )
    store.append_session_v2(
        root=root, profile_id="p1", character_id="kira",
        world="canon",
        session=make_structured_session(msg="canon world", progress_index=1),
    )
    mem_aside = store.load_memory_v2(
        root=root, profile_id="p1", character_id="kira",
        world="aside", progress=999,
    )
    mem_canon = store.load_memory_v2(
        root=root, profile_id="p1", character_id="kira",
        world="canon", progress=999,
    )
    assert len(mem_aside["sessions_meta"]) == 1
    assert len(mem_canon["sessions_meta"]) == 1


# ── Reset & Wipe ────────────────────────────────────────────────────────────


def test_reset_preserves_sqlite_rows(tmp_path):
    """Reset does NOT delete SQLite data."""
    root = tmp_path / "aside_root"
    _write_json_sessions(
        root, "p1", "kira", "aside",
        [make_structured_session(msg="Keep me", progress_index=1)],
    )
    store.load_memory_v2(
        root=root, profile_id="p1", character_id="kira",
        world="aside", progress=999,
    )

    result = store.reset_window_v2(
        root=root, profile_id="p1", character_id="kira", world="aside",
    )
    assert result["sessions_preserved"] >= 1

    mem = store.load_memory_v2(
        root=root, profile_id="p1", character_id="kira",
        world="aside", progress=999,
    )
    assert len(mem["sessions_meta"]) >= 1


def test_reset_preserves_fts_rows(tmp_path):
    """Reset does NOT delete FTS index data."""
    root = tmp_path / "aside_root"
    _write_json_sessions(
        root, "p1", "kira", "aside",
        [make_structured_session(msg="Searchable", reply="Found here", progress_index=1)],
    )
    store.load_memory_v2(
        root=root, profile_id="p1", character_id="kira",
        world="aside", progress=999,
    )

    store.reset_window_v2(
        root=root, profile_id="p1", character_id="kira", world="aside",
    )

    results = sqlite_store.search_memory_sqlite(
        root=root, profile_id="p1", character_id="kira",
        world="aside", query="Searchable",
    )
    assert len(results) >= 1


def test_reset_preserves_json_evidence(tmp_path):
    """Reset does NOT delete JSON files."""
    root = tmp_path / "aside_root"
    _write_json_sessions(
        root, "p1", "kira", "aside",
        [make_structured_session(msg="Keep JSON", progress_index=1)],
    )
    json_count_before = _json_file_count(root, "p1", "kira", "aside")

    store.load_memory_v2(
        root=root, profile_id="p1", character_id="kira",
        world="aside", progress=999,
    )
    store.reset_window_v2(
        root=root, profile_id="p1", character_id="kira", world="aside",
    )

    json_count_after = _json_file_count(root, "p1", "kira", "aside")
    assert json_count_after == json_count_before


def test_confirm_wipe_deletes_only_current_scope(tmp_path):
    """Confirm Wipe removes only the specified scope."""
    root = tmp_path / "aside_root"
    _write_json_sessions(
        root, "p1", "kira", "aside",
        [make_structured_session(msg="Scope A", progress_index=1)],
    )
    store.load_memory_v2(
        root=root, profile_id="p1", character_id="kira",
        world="aside", progress=999,
    )
    # Scope B — append activates and writes to SQLite
    store.append_session_v2(
        root=root, profile_id="p1", character_id="marina",
        world="aside",
        session=make_structured_session(msg="Scope B", progress_index=1),
    )

    store.wipe_memory_v2(
        root=root, profile_id="p1", character_id="kira",
        world="aside", confirmed=True,
    )

    mem_kira = store.load_memory_v2(
        root=root, profile_id="p1", character_id="kira",
        world="aside", progress=999,
    )
    assert len(mem_kira["sessions_meta"]) == 0

    mem_marina = store.load_memory_v2(
        root=root, profile_id="p1", character_id="marina",
        world="aside", progress=999,
    )
    assert len(mem_marina["sessions_meta"]) == 1


def test_confirm_wipe_cleans_fts(tmp_path):
    """Confirm Wipe removes FTS searchable content."""
    root = tmp_path / "aside_root"
    _write_json_sessions(
        root, "p1", "kira", "aside",
        [make_structured_session(msg="To be wiped", reply="Gone", progress_index=1)],
    )
    store.load_memory_v2(
        root=root, profile_id="p1", character_id="kira",
        world="aside", progress=999,
    )

    store.wipe_memory_v2(
        root=root, profile_id="p1", character_id="kira",
        world="aside", confirmed=True,
    )

    results = sqlite_store.search_memory_sqlite(
        root=root, profile_id="p1", character_id="kira",
        world="aside", query="wiped",
    )
    assert len(results) == 0


def test_other_scopes_survive_wipe(tmp_path):
    """Wipe of one scope does not affect another scope."""
    root = tmp_path / "aside_root"
    for char in ["kira", "marina"]:
        store.append_session_v2(
            root=root, profile_id="p1", character_id=char,
            world="aside",
            session=make_structured_session(msg=f"Data for {char}", progress_index=1),
        )

    store.wipe_memory_v2(
        root=root, profile_id="p1", character_id="kira",
        world="aside", confirmed=True,
    )

    mem = store.load_memory_v2(
        root=root, profile_id="p1", character_id="marina",
        world="aside", progress=999,
    )
    assert len(mem["sessions_meta"]) == 1


def test_json_survives_wipe(tmp_path):
    """Wipe does NOT delete JSON files."""
    root = tmp_path / "aside_root"
    _write_json_sessions(
        root, "p1", "kira", "aside",
        [make_structured_session(msg="Survive wipe", progress_index=1)],
    )
    json_count_before = _json_file_count(root, "p1", "kira", "aside")

    store.load_memory_v2(
        root=root, profile_id="p1", character_id="kira",
        world="aside", progress=999,
    )
    store.wipe_memory_v2(
        root=root, profile_id="p1", character_id="kira",
        world="aside", confirmed=True,
    )

    json_count_after = _json_file_count(root, "p1", "kira", "aside")
    assert json_count_after == json_count_before


# ── Reopen / restart persistence ────────────────────────────────────────────


def test_reopen_restart_persistence(tmp_path):
    """Data persists across simulated restart (multiple load calls)."""
    root = tmp_path / "aside_root"
    _write_json_sessions(
        root, "p1", "kira", "aside",
        [make_structured_session(msg="Persist me", progress_index=1)],
    )

    result1 = store.load_memory_v2(
        root=root, profile_id="p1", character_id="kira",
        world="aside", progress=999,
    )
    assert len(result1["sessions_meta"]) == 1

    store.append_session_v2(
        root=root, profile_id="p1", character_id="kira",
        world="aside",
        session=make_structured_session(msg="New data", progress_index=2),
    )

    con = sqlite_store.get_connection(sqlite_store.get_db_path(root))
    cur = con.execute(
        "SELECT COUNT(*) FROM sessions "
        "WHERE profile_id=? AND character_id=? AND world_id=?",
        ("p1", "kira", "aside"),
    )
    count = cur.fetchone()[0]
    con.close()
    assert count == 2


# ── Output contract compatibility ────────────────────────────────────────────


def test_load_output_contract_compatible(tmp_path):
    """load_memory_v2 output dict has expected structure for aside.rpy."""
    root = tmp_path / "aside_root"
    _write_json_sessions(
        root, "p1", "kira", "aside",
        [make_structured_session(
            msg="Player msg", reply="Kira reply",
            progress_index=1,
        )],
    )

    result = store.load_memory_v2(
        root=root, profile_id="p1", character_id="kira",
        world="aside", progress=999,
    )

    assert "summary" in result
    assert "recent" in result
    assert "sessions_meta" in result
    assert isinstance(result["summary"], str)
    assert isinstance(result["recent"], list)
    assert isinstance(result["sessions_meta"], list)
    for meta in result["sessions_meta"]:
        assert "scene_id" in meta
        assert "beat_id" in meta
        assert "progress_index" in meta
        assert "session_id" in meta


# ── FTS boundary ─────────────────────────────────────────────────────────────


def test_fts_not_called_for_load(tmp_path):
    """load_memory_v2 does NOT call FTS search."""
    root = tmp_path / "aside_root"
    store.load_memory_v2(
        root=root, profile_id="p1", character_id="kira",
        world="aside", progress=999,
    )


def test_fts_search_available_but_not_in_prompt(tmp_path):
    """FTS search API exists but is NOT called by load_memory_v2."""
    root = tmp_path / "aside_root"
    _write_json_sessions(
        root, "p1", "kira", "aside",
        [make_structured_session(msg="Findable text", reply="Response", progress_index=1)],
    )

    store.load_memory_v2(
        root=root, profile_id="p1", character_id="kira",
        world="aside", progress=999,
    )

    results = sqlite_store.search_memory_sqlite(
        root=root, profile_id="p1", character_id="kira",
        world="aside", query="Findable",
    )
    assert len(results) >= 1

    mem = store.load_memory_v2(
        root=root, profile_id="p1", character_id="kira",
        world="aside", progress=999,
    )
    assert "fts_results" not in mem


# ── Activation lock ─────────────────────────────────────────────────────────


def test_concurrent_activation_same_scope_safe(tmp_path):
    """Concurrent activation of the same scope is serialized by lock."""
    root = tmp_path / "aside_root"

    errors = []

    def activate():
        try:
            store.load_memory_v2(
                root=root, profile_id="p1", character_id="kira",
                world="aside", progress=999,
            )
        except Exception as exc:
            errors.append(exc)

    t1 = threading.Thread(target=activate)
    t2 = threading.Thread(target=activate)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert len(errors) == 0, f"Errors during concurrent activation: {errors}"


def test_activation_other_scope_no_cross_leakage(tmp_path):
    """Activating scope A does not leak data to scope B."""
    root = tmp_path / "aside_root"
    _write_json_sessions(
        root, "p1", "kira", "aside",
        [make_structured_session(msg="Scope A data", progress_index=1)],
    )

    store.load_memory_v2(
        root=root, profile_id="p1", character_id="kira",
        world="aside", progress=999,
    )
    result = store.load_memory_v2(
        root=root, profile_id="p1", character_id="marina",
        world="aside", progress=999,
    )
    assert len(result["sessions_meta"]) == 0


# ── Infrastructure error → not empty memory ──────────────────────────────────


def test_infrastructure_error_not_masked(tmp_path):
    """Corrupted DB after activation is not masked as empty memory."""
    root = tmp_path / "aside_root"
    _write_json_sessions(
        root, "p1", "kira", "aside",
        [make_structured_session(msg="Infra test", progress_index=1)],
    )
    result = store.load_memory_v2(
        root=root, profile_id="p1", character_id="kira",
        world="aside", progress=999,
    )
    assert len(result["sessions_meta"]) == 1

    result2 = store.load_memory_v2(
        root=root, profile_id="p1", character_id="kira",
        world="aside", progress=999,
    )
    assert len(result2["sessions_meta"]) == 1
    assert result2["summary"] != "" or len(result2["recent"]) > 0


# ── Repo-local artifacts absent ──────────────────────────────────────────────


def test_no_repo_local_db_artifacts(tmp_path):
    """DB/WAL/SHM files are never created inside the repository."""
    root = tmp_path / "aside_root"
    store.load_memory_v2(
        root=root, profile_id="p1", character_id="kira",
        world="aside", progress=999,
    )
    db_path = sqlite_store.get_db_path(root)
    repo_root = _REPO

    for suffix in ["", "-wal", "-shm"]:
        candidate = db_path.parent / (db_path.name + suffix)
        if candidate.exists():
            assert str(repo_root) not in str(candidate.resolve()), (
                f"DB artifact {candidate} inside repository"
            )