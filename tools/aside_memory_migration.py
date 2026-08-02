#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mode A migration: one-time idempotent import of existing JSON aside sessions
into SQLite + FTS5 (Slice 2 / Stage 3).

Implements D-ASD-S2-MIGRATION:
  - MODE_A_ONE_TIME_IDEMPOTENT_IMPORT_JSON_RETAINED_READ_ONLY
  - JSON files are NEVER deleted, overwritten, or renamed.
  - After successful migration + parity gate, SQLite becomes sole active
    read-path. JSON remains cold rollback/recovery evidence.
  - Dual-read and dual-write are FORBIDDEN.
  - Stable uniqueness boundary: (profile_id, character_id, world_id, session_id)
    where session_id = scene + beat + progress.
  - Uses Slice 1 R2 provenance mapping: player->USER_CLAIM, reply->ASIDE_WORLD,
    snapshot->CANON_WORLD.
  - Compat defaults: profile_id=dev_slot, world_id=aside for legacy records.
  - Transaction-safe and idempotent: re-run does not create duplicates.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_TOOLS = _REPO / "tools"
sys.path.insert(0, str(_TOOLS))

from aside_memory_store import (  # noqa: E402
    PROVENANCE_ASIDE_WORLD,
    PROVENANCE_CANON_WORLD,
    PROVENANCE_USER_CLAIM,
    _read_sessions,
)
import aside_memory_store_sqlite as sqlite_store  # noqa: E402


class MigrationError(RuntimeError):
    """Raised when migration fails in a way that should block SQLite activation."""


# ── Session identity (deterministic) ───────────────────────────────────────────


def _deterministic_session_id(session: dict[str, Any]) -> str:
    """Build a deterministic session_id from scene + beat + progress.

    Matches the Slice 1 convention: f"{scene_id}_{beat_id}_{progress_index}".
    """
    scene_id = session.get("scene_id", "")
    beat_id = session.get("beat_id", "")
    progress_index = session.get("progress_index", -1)
    return f"{scene_id}_{beat_id}_{progress_index}"


def _file_hash(path: Path) -> str:
    """SHA-256 hash of a file for migration dedup tracking."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ── Parity helpers ────────────────────────────────────────────────────────────


def _count_json_sessions(
    root: Path,
    profile_id: str,
    character_id: str,
    world_id: str,
) -> dict[str, Any]:
    """Count all sessions and message parts in the existing JSON store."""
    base = (
        root / "private_chats" / profile_id / character_id / world_id
    )
    sessions_dir = base / "sessions"
    if not sessions_dir.exists():
        return {"session_count": 0, "part_count": 0, "provenance_counts": {}}

    sessions = _read_sessions(base)

    session_count = len(sessions)
    part_count = 0
    provenance_counts: dict[str, int] = {
        PROVENANCE_USER_CLAIM: 0,
        PROVENANCE_ASIDE_WORLD: 0,
        PROVENANCE_CANON_WORLD: 0,
    }

    for session in sessions:
        player = session.get("player")
        if isinstance(player, dict) and player.get("text", "").strip():
            part_count += 1
            provenance_counts[PROVENANCE_USER_CLAIM] = (
                provenance_counts.get(PROVENANCE_USER_CLAIM, 0) + 1
            )

        reply = session.get("reply")
        if isinstance(reply, dict) and reply.get("text", "").strip():
            part_count += 1
            provenance_counts[PROVENANCE_ASIDE_WORLD] = (
                provenance_counts.get(PROVENANCE_ASIDE_WORLD, 0) + 1
            )

        canon = session.get("canon_snapshot")
        if isinstance(canon, dict) and canon.get("data") is not None:
            part_count += 1
            provenance_counts[PROVENANCE_CANON_WORLD] = (
                provenance_counts.get(PROVENANCE_CANON_WORLD, 0) + 1
            )

        # Also count raw transcript entries for legacy sessions
        if "player" not in session and "reply" not in session:
            for entry in session.get("transcript", []):
                if isinstance(entry, dict):
                    role = str(entry.get("role", ""))
                    content = str(entry.get("content", "")).strip()
                    if content:
                        part_count += 1
                        if role == "user":
                            provenance_counts[PROVENANCE_USER_CLAIM] = (
                                provenance_counts.get(PROVENANCE_USER_CLAIM, 0) + 1
                            )
                        elif role == "assistant":
                            provenance_counts[PROVENANCE_ASIDE_WORLD] = (
                                provenance_counts.get(PROVENANCE_ASIDE_WORLD, 0) + 1
                            )

    return {
        "session_count": session_count,
        "part_count": part_count,
        "provenance_counts": provenance_counts,
    }


def _check_parity(
    root: Path,
    profile_id: str,
    character_id: str,
    world_id: str,
) -> dict[str, Any]:
    """Compare JSON and SQLite counts for a scope. Returns parity report."""
    json_stats = _count_json_sessions(root, profile_id, character_id, world_id)
    db_path = sqlite_store.get_db_path(root)

    con = sqlite_store.get_connection(db_path)
    try:
        cur = con.execute(
            """
            SELECT COUNT(*) FROM sessions
            WHERE profile_id=? AND character_id=? AND world_id=?
            """,
            (profile_id, character_id, world_id),
        )
        sql_session_count = cur.fetchone()[0]

        cur = con.execute(
            """
            SELECT COUNT(*) FROM message_parts mp
            JOIN sessions s ON mp.session_id = s.session_id
            WHERE s.profile_id=? AND s.character_id=? AND s.world_id=?
            """,
            (profile_id, character_id, world_id),
        )
        sql_part_count = cur.fetchone()[0]

        cur = con.execute(
            """
            SELECT mp.provenance, COUNT(*) FROM message_parts mp
            JOIN sessions s ON mp.session_id = s.session_id
            WHERE s.profile_id=? AND s.character_id=? AND s.world_id=?
            GROUP BY mp.provenance
            """,
            (profile_id, character_id, world_id),
        )
        sql_prov_counts = {row[0]: row[1] for row in cur.fetchall()}

        # Check for duplicate rows (UNIQUE constraint violation would prevent,
        # but verify explicitly)
        cur = con.execute(
            """
            SELECT scene_id, beat_id, progress_index, COUNT(*)
            FROM sessions
            WHERE profile_id=? AND character_id=? AND world_id=?
            GROUP BY scene_id, beat_id, progress_index
            HAVING COUNT(*) > 1
            """,
            (profile_id, character_id, world_id),
        )
        duplicates = cur.fetchall()
    finally:
        con.close()

    parity_ok = (
        json_stats["session_count"] == sql_session_count
        and json_stats["part_count"] <= sql_part_count
        and len(duplicates) == 0
    )

    return {
        "profile_id": profile_id,
        "character_id": character_id,
        "world_id": world_id,
        "json_sessions": json_stats["session_count"],
        "sqlite_sessions": sql_session_count,
        "json_parts": json_stats["part_count"],
        "sqlite_parts": sql_part_count,
        "json_provenance": json_stats["provenance_counts"],
        "sqlite_provenance": sql_prov_counts,
        "duplicate_rows": len(duplicates),
        "parity_ok": parity_ok,
    }


# ── Migration ─────────────────────────────────────────────────────────────────


def migrate_scope(
    *,
    root: Path,
    profile_id: str,
    character_id: str,
    world_id: str,
) -> dict[str, Any]:
    """Import all JSON sessions for one scope into SQLite.

    Mode A: reads JSON files, imports into SQLite with idempotent INSERT OR IGNORE.
    JSON files are never modified. Uses stable session_id determinism.

    Returns migration result dict. Raises MigrationError on critical failure.
    """
    base = (
        root / "private_chats" / profile_id / character_id / world_id
    )
    sessions_dir = base / "sessions"
    if not sessions_dir.exists():
        return {
            "status": "no_json_data",
            "note": f"No sessions directory at {sessions_dir}",
            "imported": 0,
            "skipped": 0,
        }

    # Read sessions, gracefully skipping corrupt files
    sessions: list[dict[str, Any]] = []
    try:
        sessions = _read_sessions(base)
    except Exception:
        # _read_sessions may fail on corrupt files. Fall back to per-file reading.
        sessions_dir = base / "sessions"
        if sessions_dir.exists():
            for json_file in sorted(sessions_dir.glob("*.json")):
                try:
                    data = json.loads(json_file.read_text(encoding="utf-8-sig"))
                    if isinstance(data, dict):
                        sessions.append(data)
                except Exception:
                    pass  # skip corrupt files

    if not sessions:
        return {
            "status": "no_sessions",
            "note": "No valid session files found",
            "imported": 0,
            "skipped": 0,
        }

    db_path = sqlite_store.get_db_path(root)
    con = sqlite_store.get_connection(db_path)

    try:
        con.execute("BEGIN IMMEDIATE")

        imported = 0
        skipped = 0
        failed = 0
        failures: list[str] = []

        for session in sessions:
            session_file = session.get("_file", "")
            session_id = _deterministic_session_id(session)

            # Check if already imported (idempotency guard via migration_log)
            if session_file:
                cur = con.execute(
                    "SELECT COUNT(*) FROM migration_log WHERE source_path=?",
                    (session_file,),
                )
                if cur.fetchone()[0] > 0:
                    skipped += 1
                    continue

            try:
                result = sqlite_store.append_session(
                    con,
                    profile_id=profile_id,
                    character_id=character_id,
                    world_id=world_id,
                    session=session,
                )

                # Log the import for future idempotency
                if session_file:
                    fhash = _file_hash(Path(session_file))
                    now = __import__("datetime").datetime.now().isoformat(
                        timespec="seconds"
                    )
                    con.execute(
                        """
                        INSERT OR IGNORE INTO migration_log
                            (source_path, imported_at, file_hash, session_rowid)
                        VALUES (?, ?, ?, ?)
                        """,
                        (session_file, now, fhash, result.get("session_rowid")),
                    )

                imported += 1
            except Exception as exc:
                failed += 1
                failures.append(f"{session_file}: {exc}")

        con.commit()

        return {
            "status": "imported" if imported > 0 else "no_new_data",
            "imported": imported,
            "skipped": skipped,
            "failed": failed,
            "failures": failures[:20],  # cap failure list
        }

    except Exception:
        try:
            con.rollback()
        except Exception:
            pass
        raise
    finally:
        con.close()


def migrate_all(
    *,
    root: Path,
    discover_scopes: bool = True,
) -> dict[str, Any]:
    """Discover all existing JSON scopes and migrate them.

    If discover_scopes=True, scans <root>/private_chats/ for existing
    profile/character/world directories.
    """
    db_path = sqlite_store.get_db_path(root)

    # Ensure schema exists
    schema_result = sqlite_store.ensure_schema(db_path)
    if schema_result["status"] not in ("schema_created", "schema_ok"):
        raise MigrationError(
            f"Schema setup failed: {schema_result.get('note', 'unknown error')}"
        )

    private_dir = root / "private_chats"
    if not private_dir.exists():
        return {"status": "no_data", "note": "No private_chats directory", "scopes": []}

    scope_results = []

    for profile_dir in sorted(private_dir.iterdir()):
        if not profile_dir.is_dir():
            continue
        profile_id = profile_dir.name

        for char_dir in sorted(profile_dir.iterdir()):
            if not char_dir.is_dir():
                continue
            character_id = char_dir.name

            for world_dir in sorted(char_dir.iterdir()):
                if not world_dir.is_dir():
                    continue
                world_id = world_dir.name

                sessions_dir = world_dir / "sessions"
                if not sessions_dir.exists():
                    continue

                try:
                    result = migrate_scope(
                        root=root,
                        profile_id=profile_id,
                        character_id=character_id,
                        world_id=world_id,
                    )
                    scope_results.append({
                        "profile_id": profile_id,
                        "character_id": character_id,
                        "world_id": world_id,
                        **result,
                    })
                except Exception as exc:
                    scope_results.append({
                        "profile_id": profile_id,
                        "character_id": character_id,
                        "world_id": world_id,
                        "status": "error",
                        "note": str(exc),
                    })

    return {
        "status": "completed",
        "scopes_migrated": len([s for s in scope_results if s.get("imported", 0) > 0]),
        "scopes": scope_results,
    }


def parity_gate_all(
    *,
    root: Path,
) -> dict[str, Any]:
    """Run parity check for all scopes with both JSON and SQLite data.

    Returns a dict with per-scope parity reports. If any scope fails parity,
    the overall status is 'parity_failed'.
    """
    private_dir = root / "private_chats"
    if not private_dir.exists():
        return {"status": "no_data", "scopes": []}

    db_path = sqlite_store.get_db_path(root)
    if not db_path.exists():
        return {"status": "no_db", "note": "SQLite DB does not exist"}

    scope_checks = []
    all_ok = True

    for profile_dir in sorted(private_dir.iterdir()):
        if not profile_dir.is_dir():
            continue
        profile_id = profile_dir.name

        for char_dir in sorted(profile_dir.iterdir()):
            if not char_dir.is_dir():
                continue
            character_id = char_dir.name

            for world_dir in sorted(char_dir.iterdir()):
                if not world_dir.is_dir():
                    continue
                world_id = world_dir.name

                sessions_dir = world_dir / "sessions"
                if not sessions_dir.exists():
                    continue

                check = _check_parity(root, profile_id, character_id, world_id)
                scope_checks.append(check)
                if not check["parity_ok"]:
                    all_ok = False

    return {
        "status": "parity_ok" if all_ok else "parity_failed",
        "scopes_checked": len(scope_checks),
        "scopes": scope_checks,
    }


# ── CLI ───────────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for migration and parity operations."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Aside v2 JSON -> SQLite migration (Slice 2)"
    )
    parser.add_argument(
        "--root",
        type=str,
        required=True,
        help="Memory root directory (e.g. RenPy savedir/vne_aside_memory)",
    )
    parser.add_argument(
        "command",
        choices=["migrate", "parity", "full"],
        help="Operation: migrate (import JSON->SQLite), parity (check), "
        "full (migrate + parity)",
    )
    parser.add_argument(
        "--profile-id", type=str, help="Specific profile_id to migrate"
    )
    parser.add_argument(
        "--character-id", type=str, help="Specific character_id to migrate"
    )
    parser.add_argument(
        "--world-id", type=str, help="Specific world_id to migrate"
    )

    args = parser.parse_args(argv)
    root = Path(args.root).expanduser().resolve()

    def _print_json(obj: Any) -> None:
        print(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True))

    try:
        if args.command == "migrate":
            if args.profile_id and args.character_id and args.world_id:
                result = migrate_scope(
                    root=root,
                    profile_id=args.profile_id,
                    character_id=args.character_id,
                    world_id=args.world_id,
                )
            else:
                result = migrate_all(root=root)
            _print_json(result)

        elif args.command == "parity":
            result = parity_gate_all(root=root)
            _print_json(result)

        elif args.command == "full":
            # Migrate first
            print("=== Migration ===")
            mig_result = migrate_all(root=root)
            _print_json(mig_result)

            # Then parity
            print("\n=== Parity Gate ===")
            parity_result = parity_gate_all(root=root)
            _print_json(parity_result)

            if parity_result["status"] == "parity_failed":
                print("\nMIGRATION_PARITY_FAILED: SQLite activation blocked.")
                return 1

            print("\nParity gate PASSED. SQLite is the active read-path.")

        return 0

    except MigrationError as exc:
        print(f"MIGRATION_ERROR: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"UNEXPECTED_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())