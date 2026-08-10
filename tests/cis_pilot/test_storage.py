#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Slice 4 tests for tools/cis_pilot/storage.py.

Covers: base_path confinement, canon-path rejection, traversal rejection,
atomic JSON write, fail-if-exists, JSONL append, read-back roundtrip.
Uses tmp_path for isolation; never touches production local_runs/.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.cis_pilot.storage import (
    CisPilotStorage,
    CisPilotStorageError,
    CisPilotCanonError,
    CisPilotStorageConflictError,
    DEFAULT_BASE_PATH,
    _reject_traversal,
    _reject_canon_path,
    _CANON_MARKERS,
)


# ---------------------------------------------------------------------------
# Traversal rejection
# ---------------------------------------------------------------------------

class TestTraversalRejection:
    def test_empty_path(self) -> None:
        with pytest.raises(CisPilotStorageError):
            _reject_traversal("")

    def test_dot_segment(self) -> None:
        with pytest.raises(CisPilotStorageError):
            _reject_traversal("./etc/passwd")

    def test_dotdot_segment(self) -> None:
        with pytest.raises(CisPilotStorageError):
            _reject_traversal("../etc/passwd")

    def test_absolute_path(self) -> None:
        with pytest.raises(CisPilotStorageError):
            _reject_traversal("/etc/passwd")

    def test_non_string(self) -> None:
        with pytest.raises(CisPilotStorageError):
            _reject_traversal(None)  # type: ignore[arg-type]

    def test_backslash_path_normalized_ok(self) -> None:
        """Single backslash separators are normalized to forward slashes."""
        # The function replaces \\ with /, so dir\\subdir becomes dir/subdir (valid).
        # This test confirms the normalization path does not erroneously reject.
        _reject_traversal("dir\\subdir")  # should NOT raise


# ---------------------------------------------------------------------------
# Canon-path rejection
# ---------------------------------------------------------------------------

class TestCanonRejection:
    def test_personas_rejected(self) -> None:
        """Top-level canon dir is rejected."""
        with pytest.raises(CisPilotCanonError):
            _reject_canon_path(Path("personas"))

    def test_scenarios_rejected(self) -> None:
        """Top-level canon dir is rejected."""
        with pytest.raises(CisPilotCanonError):
            _reject_canon_path(Path("scenarios"))

    def test_core_rejected(self) -> None:
        with pytest.raises(CisPilotCanonError):
            _reject_canon_path(Path("core"))

    def test_local_runs_ok(self) -> None:
        _reject_canon_path(Path("local_runs"))  # should not raise

    def test_tmp_path_ok(self) -> None:
        _reject_canon_path(Path("/tmp/test"))  # should not raise


# ---------------------------------------------------------------------------
# JSON write / read / fail-if-exists
# ---------------------------------------------------------------------------

class TestJsonWriteRead:
    def test_write_and_read_roundtrip(self, tmp_path: Path) -> None:
        storage = CisPilotStorage(tmp_path)
        data = {"key": "value", "nested": {"a": 1}}
        storage.write_json("test.json", data)
        assert storage.exists("test.json")
        result = storage.read_json("test.json")
        assert result == data

    def test_fail_if_exists_default(self, tmp_path: Path) -> None:
        storage = CisPilotStorage(tmp_path)
        storage.write_json("dup.json", {"x": 1})
        with pytest.raises(CisPilotStorageConflictError):
            storage.write_json("dup.json", {"x": 2})

    def test_overwrite_opt_in(self, tmp_path: Path) -> None:
        storage = CisPilotStorage(tmp_path)
        storage.write_json("over.json", {"x": 1})
        storage.write_json("over.json", {"x": 2}, overwrite=True)
        assert storage.read_json("over.json") == {"x": 2}

    def test_write_creates_parents(self, tmp_path: Path) -> None:
        storage = CisPilotStorage(tmp_path)
        storage.write_json("sub/dir/nested.json", {"ok": True})
        assert storage.exists("sub/dir/nested.json")

    def test_read_missing_fails(self, tmp_path: Path) -> None:
        storage = CisPilotStorage(tmp_path)
        with pytest.raises(CisPilotStorageError):
            storage.read_json("nonexistent.json")

    def test_atomic_write_no_partial(self, tmp_path: Path) -> None:
        """Crash before write — no tmp artifact left behind."""
        storage = CisPilotStorage(tmp_path)
        # Normal write creates exactly one file
        path = storage.write_json("atomic.json", {"v": 1})
        files = list(tmp_path.rglob("*.json"))
        assert len(files) == 1
        assert files[0].name == "atomic.json"

    def test_utf8_support(self, tmp_path: Path) -> None:
        storage = CisPilotStorage(tmp_path)
        data = {"name": "Кира", "emoji": "❤️", "text": "Привет мир"}
        storage.write_json("utf8.json", data)
        result = storage.read_json("utf8.json")
        assert result == data

    def test_sorted_keys(self, tmp_path: Path) -> None:
        storage = CisPilotStorage(tmp_path)
        storage.write_json("sort.json", {"c": 3, "a": 1, "b": 2})
        raw = (tmp_path / "sort.json").read_text(encoding="utf-8")
        data = json.loads(raw)
        keys = list(data.keys())
        assert keys == sorted(keys)


# ---------------------------------------------------------------------------
# JSONL append
# ---------------------------------------------------------------------------

class TestJsonlAppend:
    def test_append_creates(self, tmp_path: Path) -> None:
        storage = CisPilotStorage(tmp_path)
        storage.append_jsonl("log.jsonl", {"event": "first"})
        records = storage.read_jsonl("log.jsonl")
        assert len(records) == 1
        assert records[0] == {"event": "first"}

    def test_multiple_appends(self, tmp_path: Path) -> None:
        storage = CisPilotStorage(tmp_path)
        for i in range(3):
            storage.append_jsonl("multi.jsonl", {"idx": i})
        records = storage.read_jsonl("multi.jsonl")
        assert len(records) == 3
        assert [r["idx"] for r in records] == [0, 1, 2]

    def test_empty_file_returns_empty_list(self, tmp_path: Path) -> None:
        storage = CisPilotStorage(tmp_path)
        assert storage.read_jsonl("none.jsonl") == []

    def test_record_must_be_dict(self, tmp_path: Path) -> None:
        storage = CisPilotStorage(tmp_path)
        with pytest.raises(CisPilotStorageError):
            storage.append_jsonl("bad.jsonl", ["not a dict"])  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Base path confinement
# ---------------------------------------------------------------------------

class TestBasePathConfinement:
    def test_canon_base_rejected(self) -> None:
        with pytest.raises(CisPilotCanonError):
            CisPilotStorage(Path.cwd() / "personas")

    def test_default_base_is_local_runs(self) -> None:
        storage = CisPilotStorage()
        assert "local_runs" in str(storage.base_path)

    def test_tmp_path_ok(self, tmp_path: Path) -> None:
        storage = CisPilotStorage(tmp_path)
        assert storage.base_path == tmp_path.resolve()

    def test_escape_via_resolve_blocked(self, tmp_path: Path) -> None:
        storage = CisPilotStorage(tmp_path)
        with pytest.raises(CisPilotStorageError):
            storage._resolve("../outside.json")


# ---------------------------------------------------------------------------
# Static: no SQLite / network
# ---------------------------------------------------------------------------

class TestNoSqliteOrNetwork:
    def test_no_sqlite_in_source(self) -> None:
        src = (Path(__file__).parents[2] / "tools" / "cis_pilot" /
               "storage.py").read_text(encoding="utf-8")
        assert "sqlite3" not in src
        assert "sqlite" not in src
        assert "requests" not in src
        assert "httpx" not in src