#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Persistent isolated memory store for N6 Character Aside.

Writes only under:
  <root>/private_chats/<profile_id>/<character_id>/<world>/

The default root is the OS temp directory, not the repository. This tool does
not read .env files, does not call an LLM or network, and never writes canon
paths such as scenarios/, personas/, novel/, or RenPy v2_* state.

Slice 1 (aside-v2): profile_id + world + provenance + window-only Reset.
Slice 1 R2 correction: non-destructive Reset, mixed per-part provenance,
production v2 wiring defaults, sandbox removal.
Slice 2: SQLite+FTS5 internal adapter — activation on first load_memory_v2,
one-time migration, parity gate, SQLite sole read/write path post-activation.
First load reads JSON (pre-activation data), activates SQLite in background.
Subsequent loads read exclusively from SQLite.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any


DEFAULT_ROOT = Path(tempfile.gettempdir()) / "vne_private_chats"
RECENT_LIMIT = 20
SUMMARY_LIMIT = 4000
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")

# ── Provenance tags (Slice 1) ───────────────────────────────────────────────
PROVENANCE_CANON_WORLD = "CANON_WORLD"
PROVENANCE_ASIDE_WORLD = "ASIDE_WORLD"
PROVENANCE_USER_CLAIM = "USER_CLAIM"
_VALID_PROVENANCE = frozenset({PROVENANCE_CANON_WORLD, PROVENANCE_ASIDE_WORLD, PROVENANCE_USER_CLAIM})

# Valid world identifiers (Slice 1 R2: sandbox removed).
_VALID_WORLDS = frozenset({"aside", "canon"})

# Default world for existing v1 data (backward compatible).
DEFAULT_WORLD = "aside"
# Default profile for existing v1 data (backward compatible).
# Slice 1 R2: changed from "default_profile" to "dev_slot".
DEFAULT_PROFILE = "dev_slot"


class AsideMemoryError(RuntimeError):
    """Clean, user-facing memory store error."""


# ── Slice 2: SQLite activation infrastructure (internal adapter) ───────────

_activation_lock = threading.Lock()
# Keyed by (root_str, profile_id, character_id, world_id) for per-root isolation
_activated_scopes: set[tuple[str, str, str, str]] = set()


def _activation_key(root: Path, profile_id: str, character_id: str, world: str) -> tuple[str, str, str, str]:
    return (
        str(Path(root).expanduser().resolve()),
        profile_id.strip(),
        character_id.strip(),
        world.strip().lower(),
    )


def _is_sqlite_activated_for_root(
    root: Path,
    profile_id: str,
    character_id: str,
    world: str,
) -> bool:
    """Check if this specific root+scope has been activated for SQLite."""
    return _activation_key(root, profile_id, character_id, world) in _activated_scopes


def _ensure_sqlite_activated(
    root: Path,
    profile_id: str,
    character_id: str,
    world: str,
) -> None:
    """One-time activation: create schema, migrate JSON, parity gate.

    Idempotent, thread-safe. Must be called to mark a scope as SQLite-active.
    Raises AsideMemoryError on any failure — no silent fallback to JSON.
    """
    safe_profile = profile_id.strip()
    safe_character = character_id.strip()
    safe_world = world.strip().lower()
    scope_key = _activation_key(root, safe_profile, safe_character, safe_world)

    if scope_key in _activated_scopes:
        return

    with _activation_lock:
        if scope_key in _activated_scopes:
            return

        import aside_memory_store_sqlite as _sqlite_store
        import aside_memory_migration as _migration

        db_path = _sqlite_store.get_db_path(root)

        # 1. Ensure schema exists (creates DB if needed)
        schema_result = _sqlite_store.ensure_schema(db_path)
        if schema_result["status"] not in ("schema_created", "schema_ok"):
            raise AsideMemoryError(
                f"SQLite schema setup failed: {schema_result.get('note', 'unknown')}"
            )

        # 2. Discover if legacy JSON sessions exist
        json_base = (
            Path(root).expanduser().resolve()
            / "private_chats"
            / safe_profile
            / safe_character
            / safe_world
            / "sessions"
        )
        has_json = (
            json_base.exists()
            and any(json_base.glob("*.json"))
        )

        if has_json:
            # 3. Check if DB already has sessions for this scope
            try:
                con = _sqlite_store.get_connection(db_path)
                cur = con.execute(
                    "SELECT COUNT(*) FROM sessions "
                    "WHERE profile_id=? AND character_id=? AND world_id=?",
                    (safe_profile, safe_character, safe_world),
                )
                db_session_count = cur.fetchone()[0]
                con.close()
            except _sqlite_store.SqliteMemoryError as exc:
                raise AsideMemoryError(f"SQLite connection error: {exc}") from None

            if db_session_count == 0:
                # 4. Run Mode A migration
                mig_result = _migration.migrate_scope(
                    root=root,
                    profile_id=safe_profile,
                    character_id=safe_character,
                    world_id=safe_world,
                )
                if mig_result.get("status") not in (
                    "imported", "no_new_data", "no_sessions", "no_json_data",
                ):
                    raise AsideMemoryError(
                        f"Migration failed: {mig_result.get('status')} — "
                        f"{mig_result.get('note', '')}"
                    )

                # 5. Parity gate (only after fresh migration)
                parity = _migration._check_parity(
                    root, safe_profile, safe_character, safe_world
                )
                if not parity["parity_ok"]:
                    raise AsideMemoryError(
                        f"Parity gate FAILED after fresh migration: "
                        f"JSON sessions={parity['json_sessions']}, "
                        f"SQLite sessions={parity['sqlite_sessions']}, "
                        f"JSON parts={parity['json_parts']}, "
                        f"SQLite parts={parity['sqlite_parts']}, "
                        f"duplicates={parity['duplicate_rows']}"
                    )
            # If db_session_count > 0 and has JSON: already migrated or
            # externally seeded. Accept the DB state.

        # 6. Activation confirmed
        _activated_scopes.add(scope_key)


# ── Slice 2 v2 API (SQLite-backed after activation) ────────────────────────


def load_memory_v2(
    *,
    root: Path,
    profile_id: str,
    character_id: str,
    world: str = DEFAULT_WORLD,
    progress: int,
) -> dict[str, Any]:
    """Load aside memory with full isolation keys (past-only progress gate).

    Slice 2: activates SQLite on first call for a scope (migration + parity),
    then reads exclusively from SQLite. SQLite is the sole read path
    in all states — JSON is never an active production read path.
    """
    # Activate SQLite if this scope hasn't been activated yet
    if not _is_sqlite_activated_for_root(root, profile_id, character_id, world):
        _ensure_sqlite_activated(root, profile_id, character_id, world)

    # Read exclusively from SQLite in all cases
    import aside_memory_store_sqlite as _sqlite_store

    try:
        return _sqlite_store.load_memory_sqlite(
            root=root,
            profile_id=profile_id,
            character_id=character_id,
            world=world,
            progress=progress,
        )
    except _sqlite_store.SqliteMemoryError as exc:
        raise AsideMemoryError(str(exc)) from None


def append_session_v2(
    *,
    root: Path,
    profile_id: str,
    character_id: str,
    world: str = DEFAULT_WORLD,
    session: dict[str, Any],
) -> dict[str, Any]:
    """Append one aside session with full isolation keys.

    Slice 1 (aside-v2): replaces ``slot`` with ``profile_id + world``.
    Slice 1 R2: each session carries structured player/reply/canon_snapshot
    parts with independent provenance.
    Slice 2: SQLite is the sole write path. If the scope is not yet
    activated, activation runs first (migration + parity), then the
    session is written to SQLite. JSON files are NEVER written.
    """
    # Ensure activation before any write
    if not _is_sqlite_activated_for_root(root, profile_id, character_id, world):
        _ensure_sqlite_activated(root, profile_id, character_id, world)

    # W-06: validate provenance BEFORE SQLite transaction (reuse existing contract)
    normalized = _normalize_session_v2(session)

    import aside_memory_store_sqlite as _sqlite_store

    try:
        result = _sqlite_store.append_session_sqlite(
            root=root,
            profile_id=profile_id,
            character_id=character_id,
            world=world,
            session=normalized,
        )
    except _sqlite_store.SqliteMemoryError as exc:
        raise AsideMemoryError(str(exc)) from None

    return {
        "status": "appended",
        "session_file": "",
        "session_rowid": result.get("session_rowid"),
    }


def summarize_memory_v2(
    *,
    root: Path,
    profile_id: str,
    character_id: str,
    world: str = DEFAULT_WORLD,
) -> dict[str, Any]:
    """Deterministically rebuild memory summary (v2 isolation keys).

    Slice 2: if SQLite is active, builds from SQLite exclusively.
    Otherwise uses legacy JSON path.
    """
    if _is_sqlite_activated_for_root(root, profile_id, character_id, world):
        import aside_memory_store_sqlite as _sqlite_store

        try:
            return _sqlite_store.summarize_memory_sqlite(
                root=root,
                profile_id=profile_id,
                character_id=character_id,
                world=world,
            )
        except _sqlite_store.SqliteMemoryError as exc:
            raise AsideMemoryError(str(exc)) from None

    # Pre-activation: legacy JSON path
    base = _character_dir_v2(root, profile_id, character_id, world)
    base.mkdir(parents=True, exist_ok=True)
    sessions = _read_sessions(base)
    sessions.sort(key=_session_sort_key)
    summary = {
        "profile_id": profile_id,
        "character_id": character_id,
        "world": world,
        "session_count": len(sessions),
        "max_progress_index": max(
            (int(s["progress_index"]) for s in sessions), default=None
        ),
        "summary": _summary_from_sessions(sessions),
        "sessions_meta": [
            {
                "scene_id": s["scene_id"],
                "beat_id": s["beat_id"],
                "progress_index": s["progress_index"],
                "session_id": s.get("session_id"),
                "player": s.get("player"),
                "reply": s.get("reply"),
                "canon_snapshot": s.get("canon_snapshot"),
                "file": s.get("_file"),
            }
            for s in sessions
        ],
    }
    _write_json(base / "memory_summary.json", summary)
    return summary


def reset_window_v2(
    *,
    root: Path,
    profile_id: str,
    character_id: str,
    world: str = DEFAULT_WORLD,
) -> dict[str, Any]:
    """Clear only the transient UI window, preserving all long-term memory.

    Slice 1 R2 correction: storage no-op. No SQLite rows or JSON files deleted.
    Slice 2: uses SQLite to count sessions if active; otherwise JSON count.
    """
    if _is_sqlite_activated_for_root(root, profile_id, character_id, world):
        import aside_memory_store_sqlite as _sqlite_store

        try:
            return _sqlite_store.reset_window_sqlite(
                root=root,
                profile_id=profile_id,
                character_id=character_id,
                world=world,
            )
        except _sqlite_store.SqliteMemoryError as exc:
            raise AsideMemoryError(str(exc)) from None

    # Pre-activation: legacy JSON count
    base = _character_dir_v2(root, profile_id, character_id, world)
    sessions_dir = base / "sessions"
    session_count = 0
    if sessions_dir.exists():
        session_count = len(list(sessions_dir.glob("*.json")))

    return {
        "status": "window_reset",
        "sessions_preserved": session_count,
        "note": "No session files were deleted; only transient UI history should be cleared",
    }


def wipe_memory_v2(
    *,
    root: Path,
    profile_id: str,
    character_id: str,
    world: str = DEFAULT_WORLD,
    confirmed: bool = False,
) -> dict[str, Any]:
    """Remove all isolated aside memory for a profile/character/world.

    Slice 1: requires explicit ``confirmed=True``.
    Slice 2: uses SQLite scoped wipe if active; JSON files are NEVER deleted.
    """
    if not confirmed:
        return {
            "status": "wipe_requires_confirmation",
            "note": "set confirmed=True to permanently delete all aside memory",
        }

    if _is_sqlite_activated_for_root(root, profile_id, character_id, world):
        import aside_memory_store_sqlite as _sqlite_store

        try:
            return _sqlite_store.wipe_memory_sqlite(
                root=root,
                profile_id=profile_id,
                character_id=character_id,
                world=world,
                confirmed=True,
            )
        except _sqlite_store.SqliteMemoryError as exc:
            raise AsideMemoryError(str(exc)) from None

    # Pre-activation: legacy JSON wipe (filesystem)
    base = _character_dir_v2(root, profile_id, character_id, world)
    path_str = str(base)
    if base.exists():
        shutil.rmtree(base)
    return {"status": "wiped", "path": path_str}


# ── Internal v2 helpers (retained for migration and test compatibility) ──


def _normalize_session_v2(session: dict[str, Any]) -> dict[str, Any]:
    """Normalize a session dict with structured mixed-provenance support."""
    normalized = _normalize_session(session)

    if "player" in session and "reply" in session:
        player = _validate_provenance_part(session["player"], "player", PROVENANCE_USER_CLAIM)
        reply = _validate_provenance_part(session["reply"], "reply", PROVENANCE_ASIDE_WORLD)
        canon_snapshot = None
        if "canon_snapshot" in session and session["canon_snapshot"] is not None:
            cs = session["canon_snapshot"]
            if not isinstance(cs, dict):
                raise AsideMemoryError("session.canon_snapshot must be a JSON object")
            prov = cs.get("provenance")
            if prov is None:
                prov = PROVENANCE_CANON_WORLD
            if not isinstance(prov, str) or prov not in _VALID_PROVENANCE:
                raise AsideMemoryError(
                    f"session.canon_snapshot.provenance must be one of "
                    f"{sorted(_VALID_PROVENANCE)}, got: {prov!r}"
                )
            prov = prov.strip()
            if prov != PROVENANCE_CANON_WORLD:
                raise AsideMemoryError(
                    f"session.canon_snapshot.provenance must be {PROVENANCE_CANON_WORLD!r}, "
                    f"got: {prov!r}"
                )
            # Preserve original data structure (dict or string), not convert to str
            data_value = cs.get("data", cs.get("text", ""))
            canon_snapshot = {"data": data_value, "provenance": prov}
        normalized["player"] = player
        normalized["reply"] = reply
        normalized["canon_snapshot"] = canon_snapshot
        _tag_transcript_provenance(normalized)
        return normalized

    provenance = session.get("provenance")
    if provenance is None:
        provenance = PROVENANCE_ASIDE_WORLD
    if not isinstance(provenance, str) or provenance not in _VALID_PROVENANCE:
        raise AsideMemoryError(
            f"session.provenance must be one of {sorted(_VALID_PROVENANCE)}"
        )
    provenance = provenance.strip()

    normalized["player"] = {
        "text": "",
        "provenance": _map_legacy_role_provenance("user", provenance),
    }
    normalized["reply"] = {
        "text": "",
        "provenance": _map_legacy_role_provenance("assistant", provenance),
    }
    normalized["canon_snapshot"] = None
    _tag_transcript_provenance(normalized)
    return normalized


def _validate_provenance_part(
    part: dict[str, Any],
    part_name: str,
    expected_provenance: str,
) -> dict[str, Any]:
    if not isinstance(part, dict):
        raise AsideMemoryError(f"session.{part_name} must be a JSON object")
    prov = part.get("provenance")
    if prov is None:
        prov = expected_provenance
    if not isinstance(prov, str) or prov not in _VALID_PROVENANCE:
        raise AsideMemoryError(
            f"session.{part_name}.provenance must be one of "
            f"{sorted(_VALID_PROVENANCE)}, got: {prov!r}"
        )
    prov = prov.strip()
    if prov != expected_provenance:
        raise AsideMemoryError(
            f"session.{part_name}.provenance must be {expected_provenance!r}, "
            f"got: {prov!r}"
        )
    text = str(part.get("text", part.get("data", "")))
    return {"text": text, "provenance": prov}


def _map_legacy_role_provenance(role: str, session_provenance: str) -> str:
    if role == "user":
        return PROVENANCE_USER_CLAIM
    if role == "assistant":
        return PROVENANCE_ASIDE_WORLD
    return session_provenance


def _tag_transcript_provenance(normalized: dict[str, Any]) -> None:
    player_prov = (
        normalized.get("player", {}).get("provenance", PROVENANCE_USER_CLAIM)
        if isinstance(normalized.get("player"), dict)
        else PROVENANCE_USER_CLAIM
    )
    reply_prov = (
        normalized.get("reply", {}).get("provenance", PROVENANCE_ASIDE_WORLD)
        if isinstance(normalized.get("reply"), dict)
        else PROVENANCE_ASIDE_WORLD
    )
    for entry in normalized.get("transcript", []):
        if not isinstance(entry, dict):
            continue
        if "provenance" in entry:
            continue
        role = entry.get("role", "")
        if role == "user":
            entry["provenance"] = player_prov
        elif role == "assistant":
            entry["provenance"] = reply_prov
        else:
            entry["provenance"] = PROVENANCE_ASIDE_WORLD


def _character_dir_v2(
    root: Path, profile_id: str, character_id: str, world: str
) -> Path:
    safe_profile = _safe_id(profile_id, "profile_id")
    safe_character = _safe_id(character_id, "character_id")
    safe_world = _safe_world(world)
    root_path = Path(root).expanduser().resolve()
    base = (
        root_path / "private_chats" / safe_profile / safe_character / safe_world
    ).resolve()
    private_root = (root_path / "private_chats").resolve()
    if private_root != base and private_root not in base.parents:
        raise AsideMemoryError("resolved memory path escapes private_chats root")
    return base


def _safe_world(world: str) -> str:
    if not isinstance(world, str) or not world.strip():
        raise AsideMemoryError("world must be a non-empty string")
    cleaned = world.strip().lower()
    if cleaned not in _VALID_WORLDS:
        raise AsideMemoryError(
            f"world must be one of {sorted(_VALID_WORLDS)}, got: {world!r}"
        )
    return cleaned


def _next_session_filename_v2(sessions_dir: Path, session: dict[str, Any]) -> str:
    return _next_session_filename(sessions_dir, session)


# ── Legacy v1 API (backward compatible) ─────────────────────────────────────


def append_session(
    *,
    root: Path,
    slot: str,
    character: str,
    session: dict[str, Any],
) -> dict[str, Any]:
    """Append one aside session and update memory_summary.json."""
    base = _character_dir(root, slot, character)
    sessions_dir = base / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    normalized = _normalize_session(session)
    target = sessions_dir / _next_session_filename(sessions_dir, normalized)
    _write_json(target, normalized)
    summary = summarize_memory(root=root, slot=slot, character=character)
    return {"status": "appended", "session_file": str(target), "summary": summary}


def load_memory(
    *,
    root: Path,
    slot: str,
    character: str,
    progress: int,
) -> dict[str, Any]:
    """Load summary/recent/session metadata, excluding sessions from the future."""
    base = _character_dir(root, slot, character)
    sessions = [
        session
        for session in _read_sessions(base)
        if int(session.get("progress_index", -1)) <= progress
    ]
    sessions.sort(key=_session_sort_key)
    filtered_summary = _summary_from_sessions(sessions)
    recent = _recent_from_sessions(sessions)
    sessions_meta = [
        {
            "scene_id": session["scene_id"],
            "beat_id": session["beat_id"],
            "progress_index": session["progress_index"],
            "session_id": session.get("session_id"),
            "file": session.get("_file"),
        }
        for session in sessions
    ]
    return {"summary": filtered_summary, "recent": recent, "sessions_meta": sessions_meta}


def summarize_memory(*, root: Path, slot: str, character: str) -> dict[str, Any]:
    """Deterministically rebuild memory_summary.json from stored sessions."""
    base = _character_dir(root, slot, character)
    base.mkdir(parents=True, exist_ok=True)
    sessions = _read_sessions(base)
    sessions.sort(key=_session_sort_key)
    summary = {
        "character_id": character,
        "save_slot": slot,
        "session_count": len(sessions),
        "max_progress_index": max((int(s["progress_index"]) for s in sessions), default=None),
        "summary": _summary_from_sessions(sessions),
        "sessions_meta": [
            {
                "scene_id": s["scene_id"],
                "beat_id": s["beat_id"],
                "progress_index": s["progress_index"],
                "session_id": s.get("session_id"),
                "file": s.get("_file"),
            }
            for s in sessions
        ],
    }
    _write_json(base / "memory_summary.json", summary)
    return summary


def reset_memory(*, root: Path, slot: str, character: str) -> dict[str, Any]:
    """Remove isolated aside memory for a character."""
    base = _character_dir(root, slot, character)
    if base.exists():
        shutil.rmtree(base)
    return {"status": "reset", "path": str(base)}


def _normalize_session(session: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(session, dict):
        raise AsideMemoryError("session must be a JSON object")
    scene_id = _required_text(session, "scene_id")
    beat_id = _required_text(session, "beat_id")
    progress_index = session.get("progress_index")
    if not isinstance(progress_index, int):
        raise AsideMemoryError("session.progress_index must be an integer")
    transcript = session.get("transcript", [])
    if not isinstance(transcript, list):
        raise AsideMemoryError("session.transcript must be a list")
    clean_transcript = _clean_transcript(transcript)
    summary = session.get("summary", "")
    if summary is None:
        summary = ""
    if not isinstance(summary, str):
        raise AsideMemoryError("session.summary must be a string")
    session_id = session.get("session_id")
    if session_id is not None and not isinstance(session_id, str):
        raise AsideMemoryError("session.session_id must be a string")
    return {
        "scene_id": scene_id,
        "beat_id": beat_id,
        "progress_index": progress_index,
        "session_id": session_id or f"{scene_id}_{beat_id}_{progress_index}",
        "summary": summary.strip(),
        "transcript": clean_transcript,
    }


def _clean_transcript(value: list[Any]) -> list[dict[str, str]]:
    cleaned: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")
        if role in {"user", "assistant", "system"} and isinstance(content, str) and content.strip():
            cleaned.append({"role": role, "content": content.strip()})
    return cleaned


def _read_sessions(base: Path) -> list[dict[str, Any]]:
    sessions_dir = base / "sessions"
    if not sessions_dir.exists():
        return []
    sessions: list[dict[str, Any]] = []
    for path in sorted(sessions_dir.glob("*.json"), key=lambda p: p.name):
        data = _read_json(path)
        session = _normalize_session(data)
        if "player" not in data and "reply" not in data:
            legacy_provenance = (
                data.get("provenance", "").strip() or PROVENANCE_ASIDE_WORLD
            )
            session["player"] = {
                "text": "",
                "provenance": _map_legacy_role_provenance("user", legacy_provenance),
            }
            session["reply"] = {
                "text": "",
                "provenance": _map_legacy_role_provenance("assistant", legacy_provenance),
            }
            session["canon_snapshot"] = (
                {"text": str(data["canon_snapshot"]), "provenance": PROVENANCE_CANON_WORLD}
                if isinstance(data.get("canon_snapshot"), dict)
                else None
            )
            if isinstance(data.get("provenance"), str) and data["provenance"].strip():
                session["provenance"] = data["provenance"].strip()
            _tag_transcript_provenance(session)
        else:
            if "player" in data and isinstance(data["player"], dict):
                session["player"] = dict(data["player"])
            if "reply" in data and isinstance(data["reply"], dict):
                session["reply"] = dict(data["reply"])
            if "canon_snapshot" in data and isinstance(data["canon_snapshot"], dict):
                session["canon_snapshot"] = dict(data["canon_snapshot"])
            else:
                session["canon_snapshot"] = None
            if isinstance(data.get("provenance"), str) and data["provenance"].strip():
                session["provenance"] = data["provenance"].strip()
            _tag_transcript_provenance(session)
        session["_file"] = str(path)
        sessions.append(session)
    return sessions


def _summary_from_sessions(sessions: list[dict[str, Any]]) -> str:
    parts = []
    for session in sessions:
        summary = session.get("summary", "")
        if summary:
            parts.append(f"[{session['progress_index']} {session['scene_id']}/{session['beat_id']}] {summary}")
    text = "\n".join(parts)
    return _truncate(text, SUMMARY_LIMIT)


def _recent_from_sessions(sessions: list[dict[str, Any]]) -> list[dict[str, str]]:
    recent: list[dict[str, str]] = []
    for session in sessions:
        recent.extend(session.get("transcript", []))
    return recent[-RECENT_LIMIT:]


def _next_session_filename(sessions_dir: Path, session: dict[str, Any]) -> str:
    prefix = f"{_safe_filename_part(session['scene_id'])}_{_safe_filename_part(session['beat_id'])}"
    index = 1
    while True:
        name = f"{prefix}_{index:03d}.json"
        if not (sessions_dir / name).exists():
            return name
        index += 1


def _character_dir(root: Path, slot: str, character: str) -> Path:
    safe_slot = _safe_id(slot, "slot")
    safe_character = _safe_id(character, "character")
    root_path = Path(root).expanduser().resolve()
    base = (root_path / "private_chats" / safe_slot / safe_character).resolve()
    private_root = (root_path / "private_chats").resolve()
    if private_root != base and private_root not in base.parents:
        raise AsideMemoryError("resolved memory path escapes private_chats root")
    return base


def _safe_id(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AsideMemoryError(f"{name} must be a non-empty string")
    cleaned = value.strip()
    if not SAFE_ID_RE.match(cleaned) or ".." in cleaned:
        raise AsideMemoryError(f"{name} contains unsafe characters")
    return cleaned


def _safe_filename_part(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._") or "item"


def _session_sort_key(session: dict[str, Any]) -> tuple[int, str, str, str]:
    return (
        int(session.get("progress_index", -1)),
        str(session.get("scene_id", "")),
        str(session.get("beat_id", "")),
        str(session.get("_file", "")),
    )


def _required_text(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise AsideMemoryError(f"session.{key} must be a non-empty string")
    return value.strip()


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise AsideMemoryError(f"invalid JSON in {path}: {exc}") from None
    except OSError as exc:
        raise AsideMemoryError(f"cannot read {path}: {exc}") from None


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(_stable_json(data) + "\n", encoding="utf-8")
    tmp.replace(path)


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="N6 Character Aside memory store")
    parser.add_argument("command", choices=["append", "load", "summarize", "reset"])
    parser.add_argument("--root", default=str(DEFAULT_ROOT), help="isolated memory root")
    parser.add_argument("--slot", required=True, help="save slot id")
    parser.add_argument("--character", required=True, help="character id")
    parser.add_argument("--progress", type=int, help="current canon progress index for load")
    parser.add_argument("--session", help="session JSON file for append")
    return parser


def main(argv: list[str] | None = None) -> int:
    _configure_stdio()
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        root = Path(args.root)
        if args.command == "append":
            if not args.session:
                raise AsideMemoryError("--session is required for append")
            result = append_session(
                root=root, slot=args.slot, character=args.character,
                session=_read_json(Path(args.session)),
            )
        elif args.command == "load":
            if args.progress is None:
                raise AsideMemoryError("--progress is required for load")
            result = load_memory(
                root=root, slot=args.slot, character=args.character, progress=args.progress
            )
        elif args.command == "summarize":
            result = summarize_memory(root=root, slot=args.slot, character=args.character)
        elif args.command == "reset":
            result = reset_memory(root=root, slot=args.slot, character=args.character)
        else:
            raise AsideMemoryError(f"unknown command: {args.command}")
        print(_stable_json(result))
        return 0
    except AsideMemoryError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())