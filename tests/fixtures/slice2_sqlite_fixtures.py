#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Shared test fixtures and utilities for Slice 2 SQLite+FTS5 tests.

All tests use pytest tmp_path — no real user memory, no repo-local DB artifacts.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_TOOLS = _REPO / "tools"
sys.path.insert(0, str(_TOOLS))

import aside_memory_store as json_store  # noqa: E402
import aside_memory_store_sqlite as sqlite_store  # noqa: E402


# ── Structured session builders ────────────────────────────────────────────────


def make_structured_session(
    scene_id="SC_017",
    beat_id="sc_017_v2_1a",
    progress_index=1,
    msg="Hello",
    reply="Hi there",
    canon_data=None,
):
    """Build a structured session matching Slice 1/2 conventions."""
    session = {
        "scene_id": scene_id,
        "beat_id": beat_id,
        "progress_index": progress_index,
        "summary": f"Player: {msg}",
        "player": {
            "text": msg,
            "provenance": json_store.PROVENANCE_USER_CLAIM,
        },
        "reply": {
            "text": reply,
            "provenance": json_store.PROVENANCE_ASIDE_WORLD,
        },
        "transcript": [
            {"role": "user", "content": msg},
            {"role": "assistant", "content": reply},
        ],
    }
    if canon_data is not None:
        session["canon_snapshot"] = {
            "data": canon_data,
            "provenance": json_store.PROVENANCE_CANON_WORLD,
        }
    return session


def make_legacy_session(
    scene_id="SC_017",
    beat_id="sc_017_v2_1a",
    progress_index=1,
    msg="Legacy message",
    reply="Legacy reply",
    provenance=None,
):
    """Build a legacy session (flat, no structured player/reply)."""
    session = {
        "scene_id": scene_id,
        "beat_id": beat_id,
        "progress_index": progress_index,
        "summary": f"Player: {msg}",
        "transcript": [
            {"role": "user", "content": msg},
            {"role": "assistant", "content": reply},
        ],
    }
    if provenance is not None:
        session["provenance"] = provenance
    return session


# ── JSON store helpers (for pre-populating test data) ──────────────────────────


def populate_json_store(root: Path, profile_id, character_id, world, sessions):
    """Write sessions to the JSON filesystem store for migration testing."""
    for session in sessions:
        json_store.append_session_v2(
            root=root,
            profile_id=profile_id,
            character_id=character_id,
            world=world,
            session=session,
        )


# ── SQLite store setup ─────────────────────────────────────────────────────────


def setup_sqlite_db(root: Path) -> Path:
    """Create and return the path to an initialized SQLite Aside DB."""
    db_path = sqlite_store.get_db_path(root)
    result = sqlite_store.ensure_schema(db_path)
    assert result["status"] in (
        "schema_created",
        "schema_ok",
    ), f"Schema setup failed: {result}"
    return db_path


def assert_no_db_in_repo(root: Path):
    """Verify that DB files are not created inside the repository."""
    repo_root = _REPO
    root_resolved = root.resolve()
    assert str(root_resolved) != str(repo_root.resolve()), (
        f"Test root {root_resolved} is inside repo {repo_root}"
    )


# ── Parity helpers ─────────────────────────────────────────────────────────────


def count_sessions_sqlite(root: Path, profile_id, character_id, world_id) -> int:
    """Count sessions in SQLite for a scope."""
    db_path = sqlite_store.get_db_path(root)
    con = sqlite_store.get_connection(db_path)
    try:
        cur = con.execute(
            "SELECT COUNT(*) FROM sessions WHERE profile_id=? AND character_id=? AND world_id=?",
            (profile_id, character_id, world_id),
        )
        return cur.fetchone()[0]
    finally:
        con.close()


def count_parts_sqlite(root: Path, profile_id, character_id, world_id) -> int:
    """Count message parts in SQLite for a scope."""
    db_path = sqlite_store.get_db_path(root)
    con = sqlite_store.get_connection(db_path)
    try:
        cur = con.execute(
            """
            SELECT COUNT(*) FROM message_parts mp
            JOIN sessions s ON mp.session_id = s.session_id
            WHERE s.profile_id=? AND s.character_id=? AND s.world_id=?
            """,
            (profile_id, character_id, world_id),
        )
        return cur.fetchone()[0]
    finally:
        con.close()


def search_fts(root: Path, profile_id, character_id, world_id, query, **kwargs):
    """Convenience wrapper for scoped FTS search."""
    return sqlite_store.search_memory_sqlite(
        root=root,
        profile_id=profile_id,
        character_id=character_id,
        world=world_id,
        query=query,
        **kwargs,
    )