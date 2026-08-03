#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Slice 1 isolation tests — R2 correction:
  - Non-destructive Reset (filesystem no-op)
  - Mixed per-part provenance (player/reply/canon_snapshot)
  - Production v2 wiring
  - Wipe confirmation UI (Confirm/Cancel)
  - Legacy mapping (non-destructive, in-memory only)
  - World validation (sandbox removed)

All tests use pytest tmp_path (never real user memory).
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_TOOLS = _REPO / "tools"
sys.path.insert(0, str(_TOOLS))

import pytest
import aside_memory_store as store  # noqa: E402


# ── helpers ──────────────────────────────────────────────────────────────────


def _make_structured_session(
    scene_id="SC_017",
    beat_id="sc_017_v2_1a",
    progress_index=1,
    msg="Hello",
    reply="Hi",
    player_provenance=None,
    reply_provenance=None,
    canon_data=None,
):
    """Build a structured session with per-part provenance."""
    session = {
        "scene_id": scene_id,
        "beat_id": beat_id,
        "progress_index": progress_index,
        "summary": f"Player: {msg}",
        "player": {
            "text": msg,
            "provenance": player_provenance or store.PROVENANCE_USER_CLAIM,
        },
        "reply": {
            "text": reply,
            "provenance": reply_provenance or store.PROVENANCE_ASIDE_WORLD,
        },
        "transcript": [
            {"role": "user", "content": msg},
            {"role": "assistant", "content": reply},
        ],
    }
    if canon_data is not None:
        session["canon_snapshot"] = {
            "data": canon_data,
            "provenance": store.PROVENANCE_CANON_WORLD,
        }
    return session


def _make_legacy_session(
    scene_id="SC_017",
    beat_id="sc_017_v2_1a",
    progress_index=1,
    msg="Hello",
    reply="Hi",
    provenance=None,
):
    """Build a legacy session with top-level provenance only."""
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


# ── profile isolation ───────────────────────────────────────────────────────


def test_profile_isolation(tmp_path):
    """Two profiles do not cross-read each other's memory."""
    root = tmp_path / "aside_root"
    store.append_session_v2(
        root=root,
        profile_id="profile_a",
        character_id="kira",
        world="aside",
        session=_make_structured_session(msg="From profile A"),
    )
    store.append_session_v2(
        root=root,
        profile_id="profile_b",
        character_id="kira",
        world="aside",
        session=_make_structured_session(msg="From profile B"),
    )

    mem_a = store.load_memory_v2(
        root=root, profile_id="profile_a", character_id="kira", world="aside", progress=999
    )
    mem_b = store.load_memory_v2(
        root=root, profile_id="profile_b", character_id="kira", world="aside", progress=999
    )

    assert len(mem_a["sessions_meta"]) == 1
    assert len(mem_b["sessions_meta"]) == 1
    # Verify profile isolation: each profile only sees its own content
    assert mem_a["sessions_meta"][0]["player"]["text"] == "From profile A"
    assert mem_b["sessions_meta"][0]["player"]["text"] == "From profile B"


# ── character isolation ─────────────────────────────────────────────────────


def test_character_isolation(tmp_path):
    """Two characters under same profile do not cross-read."""
    root = tmp_path / "aside_root"
    store.append_session_v2(
        root=root, profile_id="p1", character_id="kira", world="aside",
        session=_make_structured_session(msg="Kira's chat"),
    )
    store.append_session_v2(
        root=root, profile_id="p1", character_id="marina", world="aside",
        session=_make_structured_session(msg="Marina's chat"),
    )

    kira_mem = store.load_memory_v2(
        root=root, profile_id="p1", character_id="kira", world="aside", progress=999
    )
    marina_mem = store.load_memory_v2(
        root=root, profile_id="p1", character_id="marina", world="aside", progress=999
    )

    assert len(kira_mem["sessions_meta"]) == 1
    assert len(marina_mem["sessions_meta"]) == 1


# ── world isolation ─────────────────────────────────────────────────────────


def test_world_isolation(tmp_path):
    """Same profile+character but different worlds do not cross-read."""
    root = tmp_path / "aside_root"
    store.append_session_v2(
        root=root, profile_id="p1", character_id="kira", world="aside",
        session=_make_structured_session(msg="Aside world"),
    )
    store.append_session_v2(
        root=root, profile_id="p1", character_id="kira", world="canon",
        session=_make_structured_session(msg="Canon world"),
    )

    aside_mem = store.load_memory_v2(
        root=root, profile_id="p1", character_id="kira", world="aside", progress=999
    )
    canon_mem = store.load_memory_v2(
        root=root, profile_id="p1", character_id="kira", world="canon", progress=999
    )

    assert len(aside_mem["sessions_meta"]) == 1
    assert len(canon_mem["sessions_meta"]) == 1


def test_invalid_world_rejected(tmp_path):
    """Invalid world values raise AsideMemoryError."""
    root = tmp_path / "aside_root"
    for bad_world in ("invalid_world", "sandbox", "SANDBOX", "", "   "):
        with pytest.raises(store.AsideMemoryError):
            store.append_session_v2(
                root=root, profile_id="p1", character_id="kira", world=bad_world,
                session=_make_structured_session(),
            )


# ── provenance — structured mixed ───────────────────────────────────────────


def test_structured_mixed_provenance_stored(tmp_path):
    """Structured session stores player, reply, and optional canon_snapshot with provenance."""
    root = tmp_path / "aside_root"
    canon_data = {"scene_id": "SC_017", "beat_id": "sc_017_v2_1a", "progress_index": 17}
    store.append_session_v2(
        root=root, profile_id="p1", character_id="kira", world="aside",
        session=_make_structured_session(
            msg="Player says",
            reply="Kira replies",
            canon_data=canon_data,
        ),
    )

    mem = store.load_memory_v2(
        root=root, profile_id="p1", character_id="kira", world="aside", progress=999
    )
    meta = mem["sessions_meta"][0]
    assert meta["player"]["provenance"] == store.PROVENANCE_USER_CLAIM
    assert meta["reply"]["provenance"] == store.PROVENANCE_ASIDE_WORLD
    assert meta["canon_snapshot"] is not None
    assert meta["canon_snapshot"]["provenance"] == store.PROVENANCE_CANON_WORLD


def test_player_never_canon_world(tmp_path):
    """Player text cannot have CANON_WORLD provenance."""
    root = tmp_path / "aside_root"
    with pytest.raises(store.AsideMemoryError):
        store.append_session_v2(
            root=root, profile_id="p1", character_id="kira", world="aside",
            session=_make_structured_session(
                player_provenance=store.PROVENANCE_CANON_WORLD,
            ),
        )


def test_player_never_aside_world(tmp_path):
    """Player text cannot have ASIDE_WORLD provenance (must be USER_CLAIM)."""
    root = tmp_path / "aside_root"
    with pytest.raises(store.AsideMemoryError):
        store.append_session_v2(
            root=root, profile_id="p1", character_id="kira", world="aside",
            session=_make_structured_session(
                player_provenance=store.PROVENANCE_ASIDE_WORLD,
            ),
        )


def test_reply_must_be_aside_world(tmp_path):
    """Character reply must have ASIDE_WORLD provenance."""
    root = tmp_path / "aside_root"
    with pytest.raises(store.AsideMemoryError):
        store.append_session_v2(
            root=root, profile_id="p1", character_id="kira", world="aside",
            session=_make_structured_session(
                reply_provenance=store.PROVENANCE_CANON_WORLD,
            ),
        )


def test_snapshot_must_be_canon_world(tmp_path):
    """Canon snapshot must have CANON_WORLD provenance."""
    root = tmp_path / "aside_root"
    canon_data = {"scene_id": "SC_017", "beat_id": "beat_1"}

    # Valid: helper sets correct CANON_WORLD provenance.
    store.append_session_v2(
        root=root, profile_id="p1", character_id="kira", world="aside",
        session=_make_structured_session(canon_data=canon_data),
    )

    # Invalid: snapshot with USER_CLAIM provenance must be rejected.
    session = _make_structured_session(msg="Hi", reply="Hey")
    session["canon_snapshot"] = {"data": canon_data, "provenance": store.PROVENANCE_USER_CLAIM}
    with pytest.raises(store.AsideMemoryError):
        store.append_session_v2(
            root=root, profile_id="p1", character_id="kira", world="aside",
            session=session,
        )


def test_invalid_provenance_rejected(tmp_path):
    """Invalid provenance values on parts are rejected."""
    root = tmp_path / "aside_root"
    for bad_prov in ("INVALID", "canon_world", ""):
        session = _make_structured_session()
        session["player"]["provenance"] = bad_prov
        with pytest.raises(store.AsideMemoryError):
            store.append_session_v2(
                root=root, profile_id="p1", character_id="kira", world="aside",
                session=session,
            )


def test_unknown_provenance_tag_rejected(tmp_path):
    """Completely unknown provenance tag on any part is rejected."""
    root = tmp_path / "aside_root"
    session = {
        "scene_id": "SC_017",
        "beat_id": "beat_1",
        "progress_index": 1,
        "summary": "test",
        "player": {"text": "hello", "provenance": "INVENTED_TAG"},
        "reply": {"text": "hi", "provenance": store.PROVENANCE_ASIDE_WORLD},
        "transcript": [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ],
    }
    with pytest.raises(store.AsideMemoryError):
        store.append_session_v2(
            root=root, profile_id="p1", character_id="kira", world="aside",
            session=session,
        )


# ── provenance — transcript tagging ─────────────────────────────────────────


def test_transcript_entries_tagged_with_provenance(tmp_path):
    """Each transcript entry carries its own provenance field."""
    root = tmp_path / "aside_root"
    store.append_session_v2(
        root=root, profile_id="p1", character_id="kira", world="aside",
        session=_make_structured_session(msg="User message", reply="Character reply"),
    )

    mem = store.load_memory_v2(
        root=root, profile_id="p1", character_id="kira", world="aside", progress=999
    )
    recent = mem["recent"]
    assert len(recent) == 2
    assert any(
        entry.get("role") == "user" and entry.get("provenance") == store.PROVENANCE_USER_CLAIM
        for entry in recent
    )
    assert any(
        entry.get("role") == "assistant" and entry.get("provenance") == store.PROVENANCE_ASIDE_WORLD
        for entry in recent
    )


# ── Reset: non-destructive (Slice 1 R2 correction) ─────────────────────────


def test_reset_preserves_all_sessions(tmp_path):
    """reset_window_v2 must not delete any session files (filesystem no-op)."""
    root = tmp_path / "aside_root"
    store.append_session_v2(
        root=root, profile_id="p1", character_id="kira", world="aside",
        session=_make_structured_session(msg="Session 1", progress_index=1),
    )
    store.append_session_v2(
        root=root, profile_id="p1", character_id="kira", world="aside",
        session=_make_structured_session(msg="Session 2", progress_index=2),
    )

    result = store.reset_window_v2(
        root=root, profile_id="p1", character_id="kira", world="aside",
    )
    assert result["status"] == "window_reset"
    assert result["sessions_preserved"] == 2

    mem = store.load_memory_v2(
        root=root, profile_id="p1", character_id="kira", world="aside", progress=999
    )
    indices = [m["progress_index"] for m in mem["sessions_meta"]]
    assert sorted(indices) == [1, 2]
    assert len(mem["sessions_meta"]) == 2


def test_reset_preserves_summary(tmp_path):
    """reset_window_v2 must not delete or modify memory_summary.json."""
    root = tmp_path / "aside_root"
    store.append_session_v2(
        root=root, profile_id="p1", character_id="kira", world="aside",
        session=_make_structured_session(msg="Session 1", progress_index=1),
    )

    summary_before = store.summarize_memory_v2(
        root=root, profile_id="p1", character_id="kira", world="aside"
    )
    assert summary_before["session_count"] == 1

    store.reset_window_v2(
        root=root, profile_id="p1", character_id="kira", world="aside",
    )
    summary_after = store.summarize_memory_v2(
        root=root, profile_id="p1", character_id="kira", world="aside"
    )
    assert summary_after["session_count"] == 1


def test_reset_does_not_change_bytes_or_mtime(tmp_path):
    """reset_window_v2 must not modify bytes or mtime of existing session files."""
    root = tmp_path / "aside_root"
    # Create legacy JSON files manually (test-only, not production write)
    sessions_dir = root / "private_chats" / "p1" / "kira" / "aside" / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    session_file = sessions_dir / "SC_017_sc_017_v2_1a_001.json"
    session_data = _make_structured_session(msg="Session 1", progress_index=1)
    session_file.write_text(json.dumps(session_data, ensure_ascii=False), encoding="utf-8")

    stat_before = session_file.stat()
    bytes_before = stat_before.st_size
    mtime_before = stat_before.st_mtime

    # Small delay to ensure mtime would differ if file were rewritten.
    time.sleep(1.1)

    store.reset_window_v2(
        root=root, profile_id="p1", character_id="kira", world="aside",
    )

    stat_after = session_file.stat()
    assert stat_after.st_size == bytes_before
    assert stat_after.st_mtime == mtime_before


def test_after_reset_new_session_appended_without_loss(tmp_path):
    """After Reset, appending a new session preserves all old sessions."""
    root = tmp_path / "aside_root"
    store.append_session_v2(
        root=root, profile_id="p1", character_id="kira", world="aside",
        session=_make_structured_session(msg="Session 1", progress_index=1),
    )
    store.append_session_v2(
        root=root, profile_id="p1", character_id="kira", world="aside",
        session=_make_structured_session(msg="Session 2", progress_index=2),
    )

    store.reset_window_v2(
        root=root, profile_id="p1", character_id="kira", world="aside",
    )

    # Append session 3.
    store.append_session_v2(
        root=root, profile_id="p1", character_id="kira", world="aside",
        session=_make_structured_session(msg="Session 3", progress_index=3),
    )

    mem = store.load_memory_v2(
        root=root, profile_id="p1", character_id="kira", world="aside", progress=999
    )
    indices = [m["progress_index"] for m in mem["sessions_meta"]]
    assert sorted(indices) == [1, 2, 3]
    assert len(indices) == 3


def test_reset_window_empty_directory_no_error(tmp_path):
    """reset_window_v2 on empty directory returns gracefully."""
    root = tmp_path / "aside_root"
    result = store.reset_window_v2(
        root=root, profile_id="p1", character_id="kira", world="aside"
    )
    assert result["status"] == "window_reset"
    assert result["sessions_preserved"] == 0


def test_legacy_reset_wrapper_does_not_delete_files(tmp_path):
    """legacy _vne_reset_aside_memory should route to window-only reset (no file delete)."""
    root = tmp_path / "aside_root"
    store.append_session_v2(
        root=root, profile_id="p1", character_id="kira", world="aside",
        session=_make_structured_session(msg="Session 1", progress_index=1),
    )
    store.append_session_v2(
        root=root, profile_id="p1", character_id="kira", world="aside",
        session=_make_structured_session(msg="Session 2", progress_index=2),
    )

    # Legacy reset (via v2 window-only) — same profile_id.
    store.reset_window_v2(
        root=root, profile_id="p1", character_id="kira", world="aside"
    )

    # All sessions preserved.
    mem = store.load_memory_v2(
        root=root, profile_id="p1", character_id="kira", world="aside", progress=999
    )
    assert len(mem["sessions_meta"]) == 2


# ── Wipe: confirmation UI ───────────────────────────────────────────────────


def test_wipe_requires_confirmation(tmp_path):
    """wipe_memory_v2 without confirmed=True returns notice, does NOT delete."""
    root = tmp_path / "aside_root"
    store.append_session_v2(
        root=root, profile_id="p1", character_id="kira", world="aside",
        session=_make_structured_session(),
    )

    result = store.wipe_memory_v2(
        root=root, profile_id="p1", character_id="kira", world="aside", confirmed=False
    )
    assert result["status"] == "wipe_requires_confirmation"

    mem = store.load_memory_v2(
        root=root, profile_id="p1", character_id="kira", world="aside", progress=999
    )
    assert len(mem["sessions_meta"]) == 1


def test_wipe_confirmed_deletes_all(tmp_path):
    """wipe_memory_v2 with confirmed=True deletes everything."""
    root = tmp_path / "aside_root"
    store.append_session_v2(
        root=root, profile_id="p1", character_id="kira", world="aside",
        session=_make_structured_session(),
    )

    result = store.wipe_memory_v2(
        root=root, profile_id="p1", character_id="kira", world="aside", confirmed=True
    )
    assert result["status"] == "wiped"

    char_dir = root / "private_chats" / "p1" / "kira" / "aside"
    assert not char_dir.exists()


def test_wipe_scoped_to_profile_character_world(tmp_path):
    """Wipe only clears the target profile+character+world, not others."""
    root = tmp_path / "aside_root"
    store.append_session_v2(
        root=root, profile_id="p1", character_id="kira", world="aside",
        session=_make_structured_session(msg="Kira aside"),
    )
    store.append_session_v2(
        root=root, profile_id="p1", character_id="marina", world="aside",
        session=_make_structured_session(msg="Marina aside"),
    )

    result = store.wipe_memory_v2(
        root=root, profile_id="p1", character_id="kira", world="aside", confirmed=True
    )
    assert result["status"] == "wiped"

    # Kira is gone.
    kira_dir = root / "private_chats" / "p1" / "kira" / "aside"
    assert not kira_dir.exists()

    # Marina is still there.
    marina_mem = store.load_memory_v2(
        root=root, profile_id="p1", character_id="marina", world="aside", progress=999
    )
    assert len(marina_mem["sessions_meta"]) == 1


def test_reset_button_does_not_call_wipe(tmp_path):
    """reset_window_v2 must not delete any files (wipe is separate)."""
    root = tmp_path / "aside_root"
    # Create legacy JSON session file (test-only, not production write)
    sessions_dir = root / "private_chats" / "p1" / "kira" / "aside" / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    session_file = sessions_dir / "SC_017_sc_017_v2_1a_001.json"
    session_data = _make_structured_session(msg="Session 1")
    session_file.write_text(json.dumps(session_data, ensure_ascii=False), encoding="utf-8")

    store.reset_window_v2(
        root=root, profile_id="p1", character_id="kira", world="aside",
    )

    assert sessions_dir.exists()
    assert len(list(sessions_dir.glob("*.json"))) == 1


# ── v2 summary metadata ─────────────────────────────────────────────────────


def test_summary_includes_profile_and_world(tmp_path):
    """summarize_memory_v2 includes profile_id and world."""
    root = tmp_path / "aside_root"
    store.append_session_v2(
        root=root, profile_id="my_profile", character_id="kira", world="aside",
        session=_make_structured_session(),
    )

    summary = store.summarize_memory_v2(
        root=root, profile_id="my_profile", character_id="kira", world="aside"
    )
    assert summary["profile_id"] == "my_profile"
    assert summary["character_id"] == "kira"
    assert summary["world"] == "aside"
    assert summary["session_count"] == 1
    assert "player" in summary["sessions_meta"][0]
    assert "reply" in summary["sessions_meta"][0]


# ── legacy backward compatibility ───────────────────────────────────────────


def test_v1_api_still_works(tmp_path):
    """Legacy v1 API (slot-based) still functional."""
    root = tmp_path / "aside_root"
    result = store.append_session(
        root=root, slot="dev_slot", character="kira",
        session={
            "scene_id": "SC_017",
            "beat_id": "beat_1",
            "progress_index": 1,
            "summary": "test",
            "transcript": [{"role": "user", "content": "hello"}],
        },
    )
    assert result["status"] == "appended"

    mem = store.load_memory(
        root=root, slot="dev_slot", character="kira", progress=999
    )
    assert len(mem["sessions_meta"]) == 1


def test_v1_reset_still_works(tmp_path):
    """Legacy v1 reset_memory still functional (full rmtree — old behavior)."""
    root = tmp_path / "aside_root"
    store.append_session(
        root=root, slot="dev_slot", character="kira",
        session={
            "scene_id": "SC_017",
            "beat_id": "beat_1",
            "progress_index": 1,
            "summary": "test",
            "transcript": [{"role": "user", "content": "hello"}],
        },
    )

    char_dir = root / "private_chats" / "dev_slot" / "kira"
    assert char_dir.exists()

    store.reset_memory(root=root, slot="dev_slot", character="kira")
    assert not char_dir.exists()


def test_legacy_mapping_non_destructive(tmp_path):
    """Legacy sessions on disk are mapped in memory without mutating JSON files."""
    root = tmp_path / "aside_root"

    # Simulate a pre-existing legacy session file written without
    # structured player/reply parts. Use manual write to avoid the
    # normalizer adding structured keys during append.
    char_dir = (
        root / "private_chats" / "p1" / "kira" / "aside" / "sessions"
    )
    char_dir.mkdir(parents=True, exist_ok=True)
    legacy_raw = {
        "scene_id": "SC_017",
        "beat_id": "sc_017_v2_1a",
        "progress_index": 1,
        "summary": "Player: Legacy message",
        "transcript": [
            {"role": "user", "content": "Legacy message"},
            {"role": "assistant", "content": "Legacy reply"},
        ],
    }
    from aside_memory_store import _stable_json
    session_file = char_dir / "SC_017_sc_017_v2_1a_001.json"
    session_file.write_text(_stable_json(legacy_raw) + "\n", encoding="utf-8")

    # Read raw JSON from disk — it should NOT contain player/reply structured parts.
    raw = json.loads(session_file.read_text(encoding="utf-8"))
    assert "player" not in raw
    assert "reply" not in raw

    # Load via v2 API — should map to structured in memory.
    mem = store.load_memory_v2(
        root=root, profile_id="p1", character_id="kira", world="aside", progress=999
    )
    meta = mem["sessions_meta"][0]
    assert meta["player"]["provenance"] == store.PROVENANCE_USER_CLAIM
    assert meta["reply"]["provenance"] == store.PROVENANCE_ASIDE_WORLD

    # File should still be untouched.
    raw_after = json.loads(session_file.read_text(encoding="utf-8"))
    assert "player" not in raw_after


def test_legacy_mapping_player_always_user_claim(tmp_path):
    """Legacy user transcript entries are always mapped to USER_CLAIM."""
    root = tmp_path / "aside_root"
    # Store with legacy top-level ASIDE_WORLD provenance.
    store.append_session_v2(
        root=root, profile_id="p1", character_id="kira", world="aside",
        session=_make_legacy_session(
            msg="User text", reply="Reply text", provenance=store.PROVENANCE_ASIDE_WORLD,
        ),
    )

    mem = store.load_memory_v2(
        root=root, profile_id="p1", character_id="kira", world="aside", progress=999
    )
    meta = mem["sessions_meta"][0]
    assert meta["player"]["provenance"] == store.PROVENANCE_USER_CLAIM
    assert meta["reply"]["provenance"] == store.PROVENANCE_ASIDE_WORLD


def test_legacy_transcript_entries_provenance_tagged(tmp_path):
    """Legacy transcript entries get per-role provenance after mapping."""
    root = tmp_path / "aside_root"
    store.append_session_v2(
        root=root, profile_id="p1", character_id="kira", world="aside",
        session=_make_legacy_session(msg="Hello", reply="Hi"),
    )

    mem = store.load_memory_v2(
        root=root, profile_id="p1", character_id="kira", world="aside", progress=999
    )
    for entry in mem["recent"]:
        assert "provenance" in entry
        if entry["role"] == "user":
            assert entry["provenance"] == store.PROVENANCE_USER_CLAIM
        elif entry["role"] == "assistant":
            assert entry["provenance"] == store.PROVENANCE_ASIDE_WORLD


# ── past-only progress gate ─────────────────────────────────────────────────


def test_v2_past_only_progress_gate(tmp_path):
    """load_memory_v2 respects progress gate."""
    root = tmp_path / "aside_root"
    for pi in (10, 20, 30):
        store.append_session_v2(
            root=root, profile_id="p1", character_id="kira", world="aside",
            session=_make_structured_session(progress_index=pi, beat_id=f"beat_{pi}"),
        )

    mem = store.load_memory_v2(
        root=root, profile_id="p1", character_id="kira", world="aside", progress=20
    )
    indices = [m["progress_index"] for m in mem["sessions_meta"]]
    assert indices == [10, 20]


# ── provenance written to session file ──────────────────────────────────────


# REMOVED_AS_DUPLICATE: test_provenance_written_to_session_file
# Covered by test_structured_mixed_provenance_stored (PASSES) which asserts
# player/reply provenance in load_memory_v2 output.
# JSON production file write is retired; SQLite is the sole write path.
# ── world normalization ─────────────────────────────────────────────────────


def test_safe_world_normalizes_case(tmp_path):
    """_safe_world lowercases valid worlds like 'ASIDE' → 'aside'."""
    root = tmp_path / "aside_root"
    store.append_session_v2(
        root=root, profile_id="p1", character_id="kira", world="ASIDE",
        session=_make_structured_session(msg="Uppercase world"),
    )
    mem = store.load_memory_v2(
        root=root, profile_id="p1", character_id="kira", world="aside", progress=999
    )
    assert len(mem["sessions_meta"]) == 1


# ── sandbox explicitly rejected ─────────────────────────────────────────────


def test_sandbox_world_rejected(tmp_path):
    """Sandbox is not a valid writable world for Aside store."""
    root = tmp_path / "aside_root"
    with pytest.raises(store.AsideMemoryError):
        store.append_session_v2(
            root=root, profile_id="p1", character_id="kira", world="sandbox",
            session=_make_structured_session(),
        )


# ── default profile is dev_slot (Slice 1 R2) ────────────────────────────────


def test_default_profile_is_dev_slot():
    """Production default profile is dev_slot (not default_profile)."""
    assert store.DEFAULT_PROFILE == "dev_slot"