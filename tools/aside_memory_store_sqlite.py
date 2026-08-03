#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQLite + FTS5 backend for N6 Character Aside memory (Slice 2 / Stage 3).

Implements D-ASD-S2-DB-SCOPE (SINGLE_DB_PER_SAVEDIR_WITH_COMPOSITE_SCOPE):
  - One SQLite DB per savedir/memory root (<root>/vne_aside_memory.db).
  - Isolation key: (profile_id, character_id, world_id) — real columns, not JSON blob.
  - world_id != provenance; separate axes.
  - FTS5 via external content table, all queries scoped via JOIN.
  - WAL mode, busy_timeout=5000ms, per-operation connections.
  - No dependency on sqlite JSON1 extension.

Schema version: 1.0 (major.minor tracked in schema_version table).
"""

from __future__ import annotations

import datetime
import json
import sqlite3
from pathlib import Path
from typing import Any

# ── Constants ──────────────────────────────────────────────────────────────────

SCHEMA_VERSION_MAJOR = 1
SCHEMA_VERSION_MINOR = 0
DB_FILENAME = "vne_aside_memory.db"

PROVENANCE_CANON_WORLD = "CANON_WORLD"
PROVENANCE_ASIDE_WORLD = "ASIDE_WORLD"
PROVENANCE_USER_CLAIM = "USER_CLAIM"
_VALID_PROVENANCE = frozenset({PROVENANCE_CANON_WORLD, PROVENANCE_ASIDE_WORLD, PROVENANCE_USER_CLAIM})

DEFAULT_WORLD = "aside"
DEFAULT_PROFILE = "dev_slot"
RECENT_LIMIT = 20
SUMMARY_LIMIT = 4000
DEFAULT_SEARCH_LIMIT = 50
MAX_SEARCH_LIMIT = 200


class SqliteMemoryError(RuntimeError):
    """Clean, user-facing SQLite memory store error."""


# ── Connection management ──────────────────────────────────────────────────────


def get_db_path(root: Path) -> Path:
    """Resolve the SQLite DB path for a given memory root.

    DB lives at <root>/vne_aside_memory.db — NOT inside private_chats/,
    NOT in the Git repository, NOT under tools/ or tests/.
    """
    root_path = Path(root).expanduser().resolve()
    return root_path / DB_FILENAME


def get_connection(db_path: Path, read_only: bool = False) -> sqlite3.Connection:
    """Open a configured SQLite connection for Aside memory.

    Configures:
      - WAL journal mode
      - busy_timeout = 5000ms
      - check_same_thread = False (required for Ren'Py background worker)
      - Foreign keys enforced
    """
    uri = f"file:{db_path.as_posix()}?mode=ro" if read_only else str(db_path)
    try:
        if read_only:
            con = sqlite3.connect(uri, uri=True, check_same_thread=False)
        else:
            con = sqlite3.connect(str(db_path), check_same_thread=False)
    except (sqlite3.OperationalError, sqlite3.DatabaseError) as exc:
        raise SqliteMemoryError(f"Cannot open DB at {db_path}: {exc}") from None

    try:
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA busy_timeout=5000")
        con.execute("PRAGMA foreign_keys=ON")
    except (sqlite3.OperationalError, sqlite3.DatabaseError) as exc:
        con.close()
        raise SqliteMemoryError(f"Cannot configure DB at {db_path}: {exc}") from None
    return con


def check_integrity(db_path: Path) -> bool:
    """Run PRAGMA integrity_check and return True if OK."""
    try:
        con = get_connection(db_path)
        cur = con.execute("PRAGMA integrity_check")
        row = cur.fetchone()
        con.close()
        return row is not None and row[0] == "ok"
    except Exception:
        return False


# ── Schema management ──────────────────────────────────────────────────────────


def create_schema(con: sqlite3.Connection) -> None:
    """Create all tables, indexes, FTS virtual table, and triggers.

    Idempotent: uses IF NOT EXISTS for all DDL statements.
    Must be called in a transaction.
    """
    con.executescript("""
        -- Schema version tracking (single row)
        CREATE TABLE IF NOT EXISTS schema_version (
            major INTEGER NOT NULL,
            minor INTEGER NOT NULL,
            applied_at TEXT NOT NULL
        );

        -- Core sessions table with composite scope isolation key
        CREATE TABLE IF NOT EXISTS sessions (
            session_id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_id TEXT NOT NULL,
            character_id TEXT NOT NULL,
            world_id TEXT NOT NULL,
            scene_id TEXT NOT NULL,
            beat_id TEXT NOT NULL,
            progress_index INTEGER NOT NULL,
            session_summary TEXT DEFAULT '',
            provenance TEXT DEFAULT 'ASIDE_WORLD',
            created_at TEXT NOT NULL,
            migration_source TEXT,
            UNIQUE(profile_id, character_id, world_id, scene_id, beat_id, progress_index)
        );

        CREATE INDEX IF NOT EXISTS idx_sessions_scope
            ON sessions(profile_id, character_id, world_id);

        CREATE INDEX IF NOT EXISTS idx_sessions_progress
            ON sessions(profile_id, character_id, world_id, progress_index);

        -- Individual message parts within a session
        CREATE TABLE IF NOT EXISTS message_parts (
            part_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
            content TEXT NOT NULL,
            provenance TEXT NOT NULL
                CHECK(provenance IN ('USER_CLAIM', 'ASIDE_WORLD', 'CANON_WORLD')),
            part_order INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_message_parts_session
            ON message_parts(session_id);

        CREATE INDEX IF NOT EXISTS idx_message_parts_scope
            ON message_parts(session_id, provenance);

        -- Per-scope summary (one row per isolation key)
        CREATE TABLE IF NOT EXISTS summaries (
            summary_id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_id TEXT NOT NULL,
            character_id TEXT NOT NULL,
            world_id TEXT NOT NULL,
            summary_text TEXT DEFAULT '',
            session_count INTEGER DEFAULT 0,
            max_progress_index INTEGER,
            generated_at TEXT NOT NULL,
            UNIQUE(profile_id, character_id, world_id)
        );

        -- Canon snapshot data linked to a session
        CREATE TABLE IF NOT EXISTS canonical_snapshots (
            snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            snapshot_data TEXT NOT NULL,
            provenance TEXT DEFAULT 'CANON_WORLD',
            FOREIGN KEY(session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
        );

        -- Migration tracking (per-file fingerprint to enable idempotent re-run)
        CREATE TABLE IF NOT EXISTS migration_log (
            source_path TEXT PRIMARY KEY,
            imported_at TEXT NOT NULL,
            file_hash TEXT NOT NULL,
            session_rowid INTEGER
        );

        -- FTS5 virtual table on message_parts.content (external content table)
        CREATE VIRTUAL TABLE IF NOT EXISTS message_fts USING fts5(
            content,
            content_rowid='part_id',
            content='message_parts',
            tokenize='unicode61'
        );
    """)

    # Triggers for FTS5 sync (must be separate from CREATE VIRTUAL TABLE)
    con.executescript("""
        CREATE TRIGGER IF NOT EXISTS message_parts_ai AFTER INSERT ON message_parts BEGIN
            INSERT INTO message_fts(rowid, content) VALUES (new.part_id, new.content);
        END;

        CREATE TRIGGER IF NOT EXISTS message_parts_ad AFTER DELETE ON message_parts BEGIN
            INSERT INTO message_fts(message_fts, rowid, content) VALUES ('delete', old.part_id, old.content);
        END;

        CREATE TRIGGER IF NOT EXISTS message_parts_au AFTER UPDATE ON message_parts BEGIN
            INSERT INTO message_fts(message_fts, rowid, content) VALUES ('delete', old.part_id, old.content);
            INSERT INTO message_fts(rowid, content) VALUES (new.part_id, new.content);
        END;
    """)


def ensure_schema(db_path: Path) -> dict[str, Any]:
    """Ensure the SQLite DB exists with the correct schema version.

    Creates schema if DB is new. Verifies version matches target.
    Returns status dict.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        con = get_connection(db_path)
    except SqliteMemoryError as exc:
        return {"status": "error", "note": str(exc)}

    try:
        # Check if schema_version table exists
        cur = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
        )
        exists = cur.fetchone() is not None

        if not exists:
            # Fresh DB: create schema and insert version
            con.execute("BEGIN IMMEDIATE")
            create_schema(con)
            now = datetime.datetime.now().isoformat(timespec="seconds")
            con.execute(
                "INSERT INTO schema_version (major, minor, applied_at) VALUES (?, ?, ?)",
                (SCHEMA_VERSION_MAJOR, SCHEMA_VERSION_MINOR, now),
            )
            con.commit()
            return {
                "status": "schema_created",
                "version": f"{SCHEMA_VERSION_MAJOR}.{SCHEMA_VERSION_MINOR}",
            }

        # Existing DB: verify version
        cur = con.execute("SELECT major, minor FROM schema_version ORDER BY rowid LIMIT 1")
        row = cur.fetchone()
        if row is None:
            con.close()
            return {"status": "error", "note": "schema_version table exists but is empty"}

        major, minor = row
        if major != SCHEMA_VERSION_MAJOR or minor != SCHEMA_VERSION_MINOR:
            con.close()
            return {
                "status": "error",
                "note": (
                    f"Schema version mismatch: DB has {major}.{minor}, "
                    f"expected {SCHEMA_VERSION_MAJOR}.{SCHEMA_VERSION_MINOR}"
                ),
            }

        con.close()
        return {
            "status": "schema_ok",
            "version": f"{major}.{minor}",
        }
    except Exception as exc:
        try:
            con.rollback()
        except Exception:
            pass
        con.close()
        return {"status": "error", "note": str(exc)}


# ── Session CRUD (v2 API equivalent) ─────────────────────────────────────────


def append_session(
    con: sqlite3.Connection,
    *,
    profile_id: str,
    character_id: str,
    world_id: str,
    session: dict[str, Any],
) -> dict[str, Any]:
    """Append a session to the SQLite store within an active transaction.

    The caller must manage BEGIN/COMMIT/ROLLBACK.
    Con accepts an open connection with foreign keys enforced.
    """
    scene_id = _required_text(session, "scene_id")
    beat_id = _required_text(session, "beat_id")
    progress_index = _required_int(session, "progress_index")
    session_summary = str(session.get("summary", "")).strip()
    provenance = str(session.get("provenance", PROVENANCE_ASIDE_WORLD)).strip()
    if provenance not in _VALID_PROVENANCE:
        provenance = PROVENANCE_ASIDE_WORLD
    created_at = datetime.datetime.now().isoformat(timespec="seconds")

    # Insert or ignore (idempotent via UNIQUE constraint)
    con.execute(
        """
        INSERT OR IGNORE INTO sessions
            (profile_id, character_id, world_id, scene_id, beat_id,
             progress_index, session_summary, provenance, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            profile_id, character_id, world_id, scene_id, beat_id,
            progress_index, session_summary, provenance, created_at,
        ),
    )

    # Get the session_id (may be newly inserted or already existing)
    cur = con.execute(
        """
        SELECT session_id FROM sessions
        WHERE profile_id=? AND character_id=? AND world_id=?
          AND scene_id=? AND beat_id=? AND progress_index=?
        """,
        (profile_id, character_id, world_id, scene_id, beat_id, progress_index),
    )
    row = cur.fetchone()
    if row is None:
        raise SqliteMemoryError("Failed to insert or retrieve session row")
    session_rowid = row[0]

    # Check if we should insert message parts (only for new sessions with no parts)
    cur = con.execute(
        "SELECT COUNT(*) FROM message_parts WHERE session_id=?", (session_rowid,)
    )
    existing_parts = cur.fetchone()[0]

    if existing_parts == 0:
        part_order = 0

        # Player message part (USER_CLAIM)
        player = session.get("player")
        if isinstance(player, dict):
            player_text = str(player.get("text", player.get("data", "")))
            if player_text.strip():
                con.execute(
                    """
                    INSERT INTO message_parts
                        (session_id, role, content, provenance, part_order, created_at)
                    VALUES (?, 'user', ?, ?, ?, ?)
                    """,
                    (
                        session_rowid, player_text.strip(),
                        PROVENANCE_USER_CLAIM, part_order, created_at,
                    ),
                )
                part_order += 1
        elif "player" not in session and "reply" not in session:
            # Legacy session: map transcript entries
            for entry in session.get("transcript", []):
                if not isinstance(entry, dict):
                    continue
                role = entry.get("role", "")
                content = str(entry.get("content", "")).strip()
                if not content:
                    continue
                if role == "user":
                    entry_prov = PROVENANCE_USER_CLAIM
                elif role == "assistant":
                    entry_prov = PROVENANCE_ASIDE_WORLD
                else:
                    entry_prov = provenance
                con.execute(
                    """
                    INSERT INTO message_parts
                        (session_id, role, content, provenance, part_order, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (session_rowid, role, content, entry_prov, part_order, created_at),
                )
                part_order += 1

        # Reply message part (ASIDE_WORLD)
        reply = session.get("reply")
        if isinstance(reply, dict):
            reply_text = str(reply.get("text", reply.get("data", "")))
            if reply_text.strip():
                con.execute(
                    """
                    INSERT INTO message_parts
                        (session_id, role, content, provenance, part_order, created_at)
                    VALUES (?, 'assistant', ?, ?, ?, ?)
                    """,
                    (
                        session_rowid, reply_text.strip(),
                        PROVENANCE_ASIDE_WORLD, part_order, created_at,
                    ),
                )
                part_order += 1

        # Canon snapshot
        canon = session.get("canon_snapshot")
        if isinstance(canon, dict):
            canon_data = canon.get("data", canon.get("text", canon))
            if isinstance(canon_data, dict):
                canon_json = json.dumps(canon_data, ensure_ascii=False, sort_keys=True)
            else:
                canon_json = json.dumps({"data": str(canon_data)}, ensure_ascii=False)
            con.execute(
                """
                INSERT INTO canonical_snapshots (session_id, snapshot_data, provenance)
                VALUES (?, ?, ?)
                """,
                (session_rowid, canon_json, PROVENANCE_CANON_WORLD),
            )

    # Rebuild summary for this scope
    _rebuild_summary(con, profile_id, character_id, world_id)

    return {
        "status": "appended",
        "session_rowid": session_rowid,
        "profile_id": profile_id,
        "character_id": character_id,
        "world_id": world_id,
    }


def load_memory(
    con: sqlite3.Connection,
    *,
    profile_id: str,
    character_id: str,
    world_id: str,
    progress: int,
) -> dict[str, Any]:
    """Load aside memory with full isolation keys (past-only progress gate)."""
    # Fetch sessions within scope and progress gate
    cur = con.execute(
        """
        SELECT session_id, scene_id, beat_id, progress_index,
               session_summary, provenance, created_at, migration_source
        FROM sessions
        WHERE profile_id=? AND character_id=? AND world_id=?
          AND progress_index <= ?
        ORDER BY progress_index, scene_id, beat_id
        """,
        (profile_id, character_id, world_id, progress),
    )
    session_rows = cur.fetchall()

    sessions_meta = []
    recent_parts = []
    summary_parts = []

    for srow in session_rows:
        sid, scene_id, beat_id, pi, ssum, prov, cat, msrc = srow

        # Fetch message parts for this session
        cur = con.execute(
            """
            SELECT part_id, role, content, provenance, part_order
            FROM message_parts
            WHERE session_id=?
            ORDER BY part_order
            """,
            (sid,),
        )
        part_rows = cur.fetchall()

        player_dict = None
        reply_dict = None
        transcript = []

        for prow in part_rows:
            part_id, role, content, part_prov, part_order = prow
            entry = {"role": role, "content": content, "provenance": part_prov}
            transcript.append(entry)
            if role == "user":
                if player_dict is None:
                    player_dict = {"text": content, "provenance": part_prov}
                recent_parts.append(entry)
            elif role == "assistant":
                if reply_dict is None:
                    reply_dict = {"text": content, "provenance": part_prov}
                recent_parts.append(entry)

        # Fetch canon snapshot
        cur = con.execute(
            "SELECT snapshot_data FROM canonical_snapshots WHERE session_id=? LIMIT 1",
            (sid,),
        )
        cs_row = cur.fetchone()
        canon_snapshot = None
        if cs_row is not None:
            try:
                cs_data = json.loads(cs_row[0])
                canon_snapshot = {"data": cs_data, "provenance": PROVENANCE_CANON_WORLD}
            except json.JSONDecodeError:
                canon_snapshot = {"data": cs_row[0], "provenance": PROVENANCE_CANON_WORLD}

        meta = {
            "scene_id": scene_id,
            "beat_id": beat_id,
            "progress_index": pi,
            "session_id": f"{scene_id}_{beat_id}_{pi}",
            "player": player_dict or {"text": "", "provenance": PROVENANCE_USER_CLAIM},
            "reply": reply_dict or {"text": "", "provenance": PROVENANCE_ASIDE_WORLD},
            "canon_snapshot": canon_snapshot,
        }
        sessions_meta.append(meta)

        if ssum:
            summary_parts.append(f"[{pi} {scene_id}/{beat_id}] {ssum}")

    summary_text = _truncate("\n".join(summary_parts), SUMMARY_LIMIT)
    recent = recent_parts[-RECENT_LIMIT:] if recent_parts else []

    return {
        "summary": summary_text,
        "recent": recent,
        "sessions_meta": sessions_meta,
    }


def _rebuild_summary(
    con: sqlite3.Connection,
    profile_id: str,
    character_id: str,
    world_id: str,
) -> None:
    """Regenerate the summary row for a scope (call within a transaction)."""
    cur = con.execute(
        """
        SELECT COUNT(*), MAX(progress_index) FROM sessions
        WHERE profile_id=? AND character_id=? AND world_id=?
        """,
        (profile_id, character_id, world_id),
    )
    row = cur.fetchone()
    session_count = row[0] if row else 0
    max_pi = row[1] if row and row[1] is not None else None

    # Build summary text
    cur = con.execute(
        """
        SELECT progress_index, scene_id, beat_id, session_summary
        FROM sessions
        WHERE profile_id=? AND character_id=? AND world_id=?
        ORDER BY progress_index
        """,
        (profile_id, character_id, world_id),
    )
    parts = []
    for srow in cur.fetchall():
        pi, sc, bt, ssum = srow
        if ssum:
            parts.append(f"[{pi} {sc}/{bt}] {ssum}")
    summary_text = _truncate("\n".join(parts), SUMMARY_LIMIT)

    now = datetime.datetime.now().isoformat(timespec="seconds")
    con.execute(
        """
        INSERT INTO summaries
            (profile_id, character_id, world_id, summary_text,
             session_count, max_progress_index, generated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(profile_id, character_id, world_id) DO UPDATE SET
            summary_text=excluded.summary_text,
            session_count=excluded.session_count,
            max_progress_index=excluded.max_progress_index,
            generated_at=excluded.generated_at
        """,
        (profile_id, character_id, world_id, summary_text, session_count, max_pi, now),
    )


def summarize_memory(
    con: sqlite3.Connection,
    *,
    profile_id: str,
    character_id: str,
    world_id: str,
) -> dict[str, Any]:
    """Build and return the memory summary for a scope."""
    _rebuild_summary(con, profile_id, character_id, world_id)
    cur = con.execute(
        """
        SELECT summary_text, session_count, max_progress_index, generated_at
        FROM summaries
        WHERE profile_id=? AND character_id=? AND world_id=?
        """,
        (profile_id, character_id, world_id),
    )
    row = cur.fetchone()
    if row is None:
        return {
            "profile_id": profile_id,
            "character_id": character_id,
            "world": world_id,
            "session_count": 0,
            "max_progress_index": None,
            "summary": "",
            "sessions_meta": [],
        }

    # Fetch sessions_meta with player/reply/canon_snapshot (W-07 preserve existing contract)
    cur = con.execute(
        """
        SELECT s.session_id, s.scene_id, s.beat_id, s.progress_index,
               s.session_summary, s.provenance, s.created_at
        FROM sessions s
        WHERE s.profile_id=? AND s.character_id=? AND s.world_id=?
        ORDER BY s.progress_index
        """,
        (profile_id, character_id, world_id),
    )
    meta_list = []
    for srow in cur.fetchall():
        sid, sc, bt, pi, ssum, prov, cat = srow

        # Reconstruct player/reply from message_parts
        cur2 = con.execute(
            """
            SELECT role, content, provenance FROM message_parts
            WHERE session_id=?
            ORDER BY part_order
            """,
            (sid,),
        )
        player_dict = None
        reply_dict = None
        for prow in cur2.fetchall():
            role, content, part_prov = prow
            if role == "user" and player_dict is None:
                player_dict = {"text": content, "provenance": part_prov}
            elif role == "assistant" and reply_dict is None:
                reply_dict = {"text": content, "provenance": part_prov}

        # Fetch canon snapshot
        cur3 = con.execute(
            "SELECT snapshot_data FROM canonical_snapshots WHERE session_id=? LIMIT 1",
            (sid,),
        )
        cs_row = cur3.fetchone()
        canon_snapshot = None
        if cs_row is not None:
            try:
                cs_data = json.loads(cs_row[0])
                canon_snapshot = {"data": cs_data, "provenance": PROVENANCE_CANON_WORLD}
            except json.JSONDecodeError:
                canon_snapshot = {"data": cs_row[0], "provenance": PROVENANCE_CANON_WORLD}

        meta_entry = {
            "scene_id": sc,
            "beat_id": bt,
            "progress_index": pi,
            "session_id": f"{sc}_{bt}_{pi}",
            "summary": ssum,
        }
        if player_dict is not None:
            meta_entry["player"] = player_dict
        if reply_dict is not None:
            meta_entry["reply"] = reply_dict
        if canon_snapshot is not None:
            meta_entry["canon_snapshot"] = canon_snapshot
        meta_list.append(meta_entry)

    return {
        "profile_id": profile_id,
        "character_id": character_id,
        "world": world_id,
        "session_count": row[1],
        "max_progress_index": row[2],
        "summary": row[0],
        "sessions_meta": meta_list,
    }


def reset_window(
    con: sqlite3.Connection,
    *,
    profile_id: str,
    character_id: str,
    world_id: str,
) -> dict[str, Any]:
    """Clear only the transient UI window; no SQLite rows are deleted.

    This is a no-op at the storage layer. The caller clears its own UI history.
    """
    cur = con.execute(
        """
        SELECT COUNT(*) FROM sessions
        WHERE profile_id=? AND character_id=? AND world_id=?
        """,
        (profile_id, character_id, world_id),
    )
    row = cur.fetchone()
    session_count = row[0] if row else 0

    return {
        "status": "window_reset",
        "sessions_preserved": session_count,
        "note": "No session rows were deleted; only transient UI history should be cleared",
    }


def wipe_memory(
    con: sqlite3.Connection,
    *,
    profile_id: str,
    character_id: str,
    world_id: str,
    confirmed: bool = False,
) -> dict[str, Any]:
    """Remove all scoped aside memory from SQLite.

    Requires confirmed=True. Deletes sessions (cascading to message_parts
    via FK CASCADE and FTS triggers), canonical_snapshots, and summary
    in one transaction. External-content FTS5 is kept in sync by triggers;
    no manual FTS DELETE needed.
    """
    if not confirmed:
        return {
            "status": "wipe_requires_confirmation",
            "note": "set confirmed=True to permanently delete all aside memory",
        }

    # Delete in correct FK order.
    # message_fts is an external-content table backed by message_parts;
    # the AFTER DELETE trigger on message_parts handles FTS cleanup.
    # We must NOT manually DELETE from message_fts.

    # 1. Delete canonical_snapshots referencing sessions in this scope
    con.execute(
        """
        DELETE FROM canonical_snapshots WHERE session_id IN (
            SELECT session_id FROM sessions
            WHERE profile_id=? AND character_id=? AND world_id=?
        )
        """,
        (profile_id, character_id, world_id),
    )

    # 2. Delete sessions (FK CASCADE deletes message_parts, which
    #    triggers AFTER DELETE on message_parts → message_fts cleanup)
    con.execute(
        """
        DELETE FROM sessions
        WHERE profile_id=? AND character_id=? AND world_id=?
        """,
        (profile_id, character_id, world_id),
    )

    # 3. Delete summary
    con.execute(
        """
        DELETE FROM summaries
        WHERE profile_id=? AND character_id=? AND world_id=?
        """,
        (profile_id, character_id, world_id),
    )

    # 4. Compact FTS index (optional rebuild to clean any stale entries)
    con.execute("INSERT INTO message_fts(message_fts) VALUES ('rebuild')")

    return {
        "status": "wiped",
        "profile_id": profile_id,
        "character_id": character_id,
        "world_id": world_id,
    }


# ── FTS5 scoped search ────────────────────────────────────────────────────────


def search_memory(
    con: sqlite3.Connection,
    *,
    profile_id: str,
    character_id: str,
    world_id: str,
    query: str,
    limit: int = DEFAULT_SEARCH_LIMIT,
    provenance_filter: str | None = None,
) -> list[dict[str, Any]]:
    """Scoped FTS5 full-text search.

    Architectural boundary (D-ASD-S2-DB-SCOPE):
      - FTS5 MATCH returns rowid → JOIN to message_parts → JOIN to sessions
      - Scope filter (profile_id, character_id, world_id) is MANDATORY
      - Provenance filter is OPTIONAL and separate
      - LIMIT applied AFTER scope enforcement

    Returns list of dicts with session metadata, matched content, and provenance.
    """
    if not query or not query.strip():
        return []

    search_limit = max(1, min(limit, MAX_SEARCH_LIMIT))
    normalized_query = query.strip()

    # Build scoped FTS query following the architectural boundary:
    # FTS → JOIN message_parts → JOIN sessions → scope filter → LIMIT
    sql = """
        SELECT s.session_id, s.scene_id, s.beat_id, s.progress_index,
               s.session_summary, s.provenance as session_provenance,
               mp.part_id, mp.role, mp.content, mp.provenance as part_provenance,
               mp.part_order, mp.created_at
        FROM message_fts fts
        JOIN message_parts mp ON fts.rowid = mp.part_id
        JOIN sessions s ON mp.session_id = s.session_id
        WHERE message_fts MATCH ?
          AND s.profile_id = ?
          AND s.character_id = ?
          AND s.world_id = ?
    """
    params: list[Any] = [normalized_query, profile_id, character_id, world_id]

    if provenance_filter and provenance_filter in _VALID_PROVENANCE:
        sql += " AND mp.provenance = ?"
        params.append(provenance_filter)

    sql += " ORDER BY s.progress_index DESC, mp.part_order LIMIT ?"
    params.append(search_limit)

    cur = con.execute(sql, tuple(params))
    rows = cur.fetchall()

    results = []
    for row in rows:
        (
            sid, scene_id, beat_id, pi, ssum, sprov,
            part_id, role, content, part_prov, part_order, created_at,
        ) = row
        results.append({
            "session_id": sid,
            "scene_id": scene_id,
            "beat_id": beat_id,
            "progress_index": pi,
            "session_summary": ssum,
            "matched_content": content,
            "matched_role": role,
            "matched_provenance": part_prov,
            "part_id": part_id,
            "created_at": created_at,
        })

    return results


# ── Top-level API (matches aside_memory_store v2 signature) ───────────────────


def append_session_sqlite(
    *,
    root: Path,
    profile_id: str,
    character_id: str,
    world: str = DEFAULT_WORLD,
    session: dict[str, Any],
) -> dict[str, Any]:
    """Public API: append a session via SQLite."""
    world_id = _safe_world(world)
    db_path = get_db_path(root)
    con = get_connection(db_path)
    try:
        con.execute("BEGIN IMMEDIATE")
        result = append_session(
            con,
            profile_id=profile_id.strip(),
            character_id=character_id.strip(),
            world_id=world_id,
            session=session,
        )
        con.commit()
        return result
    except Exception:
        try:
            con.rollback()
        except Exception:
            pass
        raise
    finally:
        con.close()


def load_memory_sqlite(
    *,
    root: Path,
    profile_id: str,
    character_id: str,
    world: str = DEFAULT_WORLD,
    progress: int,
) -> dict[str, Any]:
    """Public API: load memory via SQLite."""
    world_id = _safe_world(world)
    db_path = get_db_path(root)
    con = get_connection(db_path)
    try:
        return load_memory(
            con,
            profile_id=profile_id.strip(),
            character_id=character_id.strip(),
            world_id=world_id,
            progress=progress,
        )
    finally:
        con.close()


def summarize_memory_sqlite(
    *,
    root: Path,
    profile_id: str,
    character_id: str,
    world: str = DEFAULT_WORLD,
) -> dict[str, Any]:
    """Public API: summarize memory via SQLite."""
    world_id = _safe_world(world)
    db_path = get_db_path(root)
    con = get_connection(db_path)
    try:
        return summarize_memory(
            con,
            profile_id=profile_id.strip(),
            character_id=character_id.strip(),
            world_id=world_id,
        )
    finally:
        con.close()


def reset_window_sqlite(
    *,
    root: Path,
    profile_id: str,
    character_id: str,
    world: str = DEFAULT_WORLD,
) -> dict[str, Any]:
    """Public API: reset window via SQLite (no-op on storage)."""
    world_id = _safe_world(world)
    db_path = get_db_path(root)
    con = get_connection(db_path)
    try:
        return reset_window(
            con,
            profile_id=profile_id.strip(),
            character_id=character_id.strip(),
            world_id=world_id,
        )
    finally:
        con.close()


def wipe_memory_sqlite(
    *,
    root: Path,
    profile_id: str,
    character_id: str,
    world: str = DEFAULT_WORLD,
    confirmed: bool = False,
) -> dict[str, Any]:
    """Public API: wipe memory via SQLite."""
    if not confirmed:
        return {
            "status": "wipe_requires_confirmation",
            "note": "set confirmed=True to permanently delete all aside memory",
        }
    world_id = _safe_world(world)
    db_path = get_db_path(root)
    con = get_connection(db_path)
    try:
        con.execute("BEGIN IMMEDIATE")
        result = wipe_memory(
            con,
            profile_id=profile_id.strip(),
            character_id=character_id.strip(),
            world_id=world_id,
            confirmed=True,
        )
        con.commit()
        return result
    except Exception:
        try:
            con.rollback()
        except Exception:
            pass
        raise
    finally:
        con.close()


def search_memory_sqlite(
    *,
    root: Path,
    profile_id: str,
    character_id: str,
    world: str = DEFAULT_WORLD,
    query: str,
    limit: int = DEFAULT_SEARCH_LIMIT,
    provenance_filter: str | None = None,
) -> list[dict[str, Any]]:
    """Public API: scoped FTS5 search."""
    world_id = _safe_world(world)
    db_path = get_db_path(root)
    con = get_connection(db_path)
    try:
        return search_memory(
            con,
            profile_id=profile_id.strip(),
            character_id=character_id.strip(),
            world_id=world_id,
            query=query,
            limit=limit,
            provenance_filter=provenance_filter,
        )
    finally:
        con.close()


def get_scope_stats(
    *,
    root: Path,
    profile_id: str,
    character_id: str,
    world: str = DEFAULT_WORLD,
) -> dict[str, Any]:
    """Return diagnostic stats for a scope (session count, part count, etc.)."""
    world_id = _safe_world(world)
    db_path = get_db_path(root)
    con = get_connection(db_path)
    try:
        cur = con.execute(
            """
            SELECT COUNT(*) FROM sessions
            WHERE profile_id=? AND character_id=? AND world_id=?
            """,
            (profile_id, character_id, world_id),
        )
        session_count = cur.fetchone()[0]

        cur = con.execute(
            """
            SELECT COUNT(*) FROM message_parts mp
            JOIN sessions s ON mp.session_id = s.session_id
            WHERE s.profile_id=? AND s.character_id=? AND s.world_id=?
            """,
            (profile_id, character_id, world_id),
        )
        part_count = cur.fetchone()[0]

        cur = con.execute(
            """
            SELECT mp.provenance, COUNT(*) FROM message_parts mp
            JOIN sessions s ON mp.session_id = s.session_id
            WHERE s.profile_id=? AND s.character_id=? AND s.world_id=?
            GROUP BY mp.provenance
            """,
            (profile_id, character_id, world_id),
        )
        provenance_counts = {row[0]: row[1] for row in cur.fetchall()}

        return {
            "profile_id": profile_id,
            "character_id": character_id,
            "world_id": world_id,
            "session_count": session_count,
            "message_part_count": part_count,
            "provenance_counts": provenance_counts,
        }
    finally:
        con.close()


# ── Internal helpers ──────────────────────────────────────────────────────────


def _safe_world(world: str) -> str:
    """Validate and canonicalize world identifier."""
    if not isinstance(world, str) or not world.strip():
        raise SqliteMemoryError("world must be a non-empty string")
    cleaned = world.strip().lower()
    if cleaned not in ("aside", "canon"):
        raise SqliteMemoryError(f"world must be 'aside' or 'canon', got: {world!r}")
    return cleaned


def _required_text(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SqliteMemoryError(f"session.{key} must be a non-empty string")
    return value.strip()


def _required_int(data: dict[str, Any], key: str) -> int:
    value = data.get(key)
    if not isinstance(value, int):
        raise SqliteMemoryError(f"session.{key} must be an integer")
    return value


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"