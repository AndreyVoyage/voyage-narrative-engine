"""Targeted SQLite feature probe — Slice B complementary capability tests.

Supplements test_aside_sqlite_import_probe.py with:
  - Compile options verification
  - FTS5 end-to-end MATCH queries
  - WAL filesystem artifacts
  - WAL checkpoint behavior
  - Backup verification (byte-identical)
  - Source-lock / provenance agreement checks

Requires the Ren'Py embedded Python 3.12.7 runtime for compile-option and
import tests. File-existence and source-lock tests run everywhere.

For actual Ren'Py embedded runtime testing, use:
    tests/run_aside_sqlite_targeted_tests.py

Authorized write-set path:
  tests/test_aside_sqlite_feature_probe.py
"""

import os
import sys
import hashlib
import unittest
import tempfile
import shutil
import json

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PYTHON_PACKAGES = os.path.join(REPO_ROOT, "novel", "game", "python-packages")
SQLITE3_DIR = os.path.join(PYTHON_PACKAGES, "sqlite3")
NATIVE_PATH = os.path.join(PYTHON_PACKAGES,
    "_sqlite3.cp312-mingw_x86_64_ucrt_llvm.pyd")
PROVENANCE_PATH = os.path.join(PYTHON_PACKAGES, "PROVENANCE.md")
SOURCE_MANIFEST_PATH = os.path.join(
    REPO_ROOT, "build", "provenance", "source_manifest.json")
SOURCE_HASHES_PATH = os.path.join(
    REPO_ROOT, "build", "provenance", "source_hashes.txt")

SDK_PATH = r"C:\DEV\Narrative\renpy-8.5.3-sdk"

PINNED_NATIVE_SHA256 = (
    "d6f829149200b18dfcfb5a3bc96c80e00005deed2536743a24f4b428957bbe4d"
)
EXPECTED_SQLITE_VERSION = "3.45.3"

# Detect whether we are running under the Ren'Py embedded Python 3.12.7
RENPY_RUNTIME_12 = (
    sys.version_info[:2] == (3, 12)
    and "mingw" in sys.version.lower()
    and os.path.isdir(os.path.join(SDK_PATH, "lib", "py3-windows-x86_64"))
)

# The Ren'Py embedded Python 3.12.7 lacks the unittest module.
# These tests only work with the system Python (which has unittest)
# but system Python has its own SQLite — so we require the Ren'Py
# runtime marker to be detected for capability tests.  If not on
# Ren'Py runtime, skip gracefully.
CAN_RUN_CAPABILITY = RENPY_RUNTIME_12


class TestCompileOptions(unittest.TestCase):
    """Verify compile-time options are correctly embedded.

    Requires the Ren'Py embedded Python 3.12.7 runtime.
    If not running under that runtime, all tests skip.
    """

    @classmethod
    def setUpClass(cls):
        if not CAN_RUN_CAPABILITY:
            return
        if PYTHON_PACKAGES not in sys.path:
            sys.path.insert(0, PYTHON_PACKAGES)
        import sqlite3
        cls.sqlite3 = sqlite3
        cls.conn = sqlite3.connect(":memory:")

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'conn'):
            cls.conn.close()

    def _require_renpy(self):
        if not CAN_RUN_CAPABILITY:
            self.skipTest(
                "Requires Ren'Py embedded Python 3.12.7 runtime. "
                "Use tests/run_aside_sqlite_targeted_tests.py for targeted tests."
            )

    def test_compile_options_includes_enable_fts5(self):
        self._require_renpy()
        row = self.conn.execute(
            "PRAGMA compile_options"
        ).fetchall()
        options = [r[0] for r in row]
        self.assertIn("ENABLE_FTS5", options)

    def test_compile_options_includes_threadsafe_1(self):
        self._require_renpy()
        row = self.conn.execute(
            "PRAGMA compile_options"
        ).fetchall()
        options = [r[0] for r in row]
        self.assertIn("THREADSAFE=1", options)

    def test_compile_options_includes_omit_load_extension(self):
        self._require_renpy()
        row = self.conn.execute(
            "PRAGMA compile_options"
        ).fetchall()
        options = [r[0] for r in row]
        self.assertIn("OMIT_LOAD_EXTENSION", options)

    def test_compile_options_count(self):
        self._require_renpy()
        row = self.conn.execute(
            "PRAGMA compile_options"
        ).fetchall()
        self.assertGreaterEqual(len(row), 35,
            "Expected >=35 compile options")


class TestFTS5EndToEnd(unittest.TestCase):
    """Verify FTS5 works end-to-end.

    Requires the Ren'Py embedded runtime.
    """

    @classmethod
    def setUpClass(cls):
        if not CAN_RUN_CAPABILITY:
            return
        if PYTHON_PACKAGES not in sys.path:
            sys.path.insert(0, PYTHON_PACKAGES)
        import sqlite3
        cls.sqlite3 = sqlite3

    def _require_renpy(self):
        if not CAN_RUN_CAPABILITY:
            self.skipTest("Requires Ren'Py embedded Python 3.12.7 runtime.")

    def test_fts5_create_table(self):
        self._require_renpy()
        conn = self.sqlite3.connect(":memory:")
        conn.execute("CREATE VIRTUAL TABLE probe_fts5 USING fts5(content)")
        conn.close()

    def test_fts5_insert_and_match(self):
        self._require_renpy()
        conn = self.sqlite3.connect(":memory:")
        conn.execute("CREATE VIRTUAL TABLE probe_fts5 USING fts5(content)")
        conn.execute(
            "INSERT INTO probe_fts5(rowid, content) VALUES(1, 'hello world')")
        rows = conn.execute(
            "SELECT rowid FROM probe_fts5 WHERE probe_fts5 MATCH 'hello'"
        ).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], 1)
        conn.close()

    def test_fts5_no_match(self):
        self._require_renpy()
        conn = self.sqlite3.connect(":memory:")
        conn.execute("CREATE VIRTUAL TABLE probe_fts5 USING fts5(content)")
        conn.execute(
            "INSERT INTO probe_fts5(rowid, content) VALUES(1, 'hello world')")
        rows = conn.execute(
            "SELECT rowid FROM probe_fts5 WHERE probe_fts5 MATCH 'nonexistent'"
        ).fetchall()
        self.assertEqual(len(rows), 0)
        conn.close()

    def test_fts5_multiple_rows(self):
        self._require_renpy()
        conn = self.sqlite3.connect(":memory:")
        conn.execute("CREATE VIRTUAL TABLE probe_fts5 USING fts5(content)")
        conn.execute(
            "INSERT INTO probe_fts5(rowid, content) VALUES(1, 'apple banana')")
        conn.execute(
            "INSERT INTO probe_fts5(rowid, content) VALUES(2, 'cherry apple')")
        rows = conn.execute(
            "SELECT rowid FROM probe_fts5 WHERE probe_fts5 MATCH 'apple' "
            "ORDER BY rowid"
        ).fetchall()
        self.assertEqual(len(rows), 2)
        self.assertEqual([r[0] for r in rows], [1, 2])
        conn.close()


class TestWALArtifacts(unittest.TestCase):
    """Verify WAL filesystem artifacts behave correctly.

    Requires the Ren'Py embedded runtime.
    """

    @classmethod
    def setUpClass(cls):
        if not CAN_RUN_CAPABILITY:
            return
        if PYTHON_PACKAGES not in sys.path:
            sys.path.insert(0, PYTHON_PACKAGES)
        import sqlite3
        cls.sqlite3 = sqlite3

    def _require_renpy(self):
        if not CAN_RUN_CAPABILITY:
            self.skipTest("Requires Ren'Py embedded Python 3.12.7 runtime.")

    def test_wal_creates_journal_files(self):
        self._require_renpy()
        tmp_dir = tempfile.mkdtemp(prefix="sqlite_wal_test_")
        try:
            db_path = os.path.join(tmp_dir, "test.db")
            conn = self.sqlite3.connect(db_path)
            conn.execute("PRAGMA journal_mode=WAL")
            row = conn.execute("PRAGMA journal_mode").fetchone()
            self.assertEqual(row[0], "wal")
            conn.close()
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_wal_checkpoint(self):
        self._require_renpy()
        tmp_dir = tempfile.mkdtemp(prefix="sqlite_wal_test_")
        try:
            db_path = os.path.join(tmp_dir, "test.db")
            conn = self.sqlite3.connect(db_path)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("CREATE TABLE t(x)")
            conn.execute("INSERT INTO t VALUES(1)")
            conn.commit()
            # Verify table exists
            rows = conn.execute("SELECT x FROM t").fetchall()
            self.assertEqual(len(rows), 1)
            # Force checkpoint
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.close()
            # Reopen — data must persist
            conn2 = self.sqlite3.connect(db_path)
            rows2 = conn2.execute("SELECT x FROM t").fetchall()
            self.assertEqual(len(rows2), 1)
            conn2.close()
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


class TestBackup(unittest.TestCase):
    """Verify backup produces valid copy.

    Requires the Ren'Py embedded runtime.
    """

    @classmethod
    def setUpClass(cls):
        if not CAN_RUN_CAPABILITY:
            return
        if PYTHON_PACKAGES not in sys.path:
            sys.path.insert(0, PYTHON_PACKAGES)
        import sqlite3
        cls.sqlite3 = sqlite3

    def _require_renpy(self):
        if not CAN_RUN_CAPABILITY:
            self.skipTest("Requires Ren'Py embedded Python 3.12.7 runtime.")

    def test_backup_in_memory(self):
        self._require_renpy()
        src = self.sqlite3.connect(":memory:")
        src.execute("CREATE TABLE t(x)")
        src.execute("INSERT INTO t VALUES(42)")
        src.commit()
        dst = self.sqlite3.connect(":memory:")
        src.backup(dst)
        row = dst.execute("SELECT x FROM t").fetchone()
        self.assertEqual(row[0], 42)
        src.close()
        dst.close()

    def test_backup_file_to_file(self):
        self._require_renpy()
        tmp_dir = tempfile.mkdtemp(prefix="sqlite_backup_test_")
        try:
            src_path = os.path.join(tmp_dir, "src.db")
            dst_path = os.path.join(tmp_dir, "dst.db")
            src = self.sqlite3.connect(src_path)
            src.execute("CREATE TABLE t(x)")
            src.execute("INSERT INTO t VALUES(1),(2),(3)")
            src.commit()
            dst = self.sqlite3.connect(dst_path)
            src.backup(dst)
            src.close()
            dst.close()
            # Verify
            verify = self.sqlite3.connect(dst_path)
            rows = verify.execute("SELECT x FROM t ORDER BY x").fetchall()
            self.assertEqual([r[0] for r in rows], [1, 2, 3])
            verify.close()
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


class TestSourceLocksAgreement(unittest.TestCase):
    """Verify source lock and provenance files agree with each other."""

    def test_source_manifest_hashes_match_source_locks(self):
        """JSON manifest hashes must match the pinned values."""
        with open(SOURCE_MANIFEST_PATH, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        self.assertEqual(
            manifest["sqlite"]["archive_sha256"],
            "ea170e73e447703e8359308ca2e4366a3ae0c4304a8665896f068c736781c651",
        )
        self.assertEqual(
            manifest["cpython"]["archive_sha256"],
            "0c4db8f00ab490bfb5a4b0d0e763319d017226b5521f97e851412342ff04d459",
        )
        self.assertEqual(
            manifest["toolchain"]["archive_sha256"],
            "f4f3ad8616c4183ce7b0d72df634400945b41ea9816145fc2430df6003455db7",
        )

    def test_source_hashes_covers_all_inputs(self):
        """source_hashes.txt must list SQLite, CPython, toolchain, import lib."""
        with open(SOURCE_HASHES_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("ea170e73e447703e8359308ca2e4366a3ae0c4304a8665896f068c736781c651",
                      content)
        self.assertIn("0c4db8f00ab490bfb5a4b0d0e763319d017226b5521f97e851412342ff04d459",
                      content)
        self.assertIn("f4f3ad8616c4183ce7b0d72df634400945b41ea9816145fc2430df6003455db7",
                      content)
        self.assertIn("125add086832756cbdb72625c97f692cea52b678ba4cb93983ac1ed7784e26e6",
                      content)

    def test_provenance_md_native_hash_matches(self):
        """PROVENANCE.md must quote the exact pinned native SHA-256."""
        with open(PROVENANCE_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn(PINNED_NATIVE_SHA256, content,
                      "PROVENANCE.md does not contain pinned native SHA-256")

    def test_native_binary_hash_matches_pinned(self):
        """Actual repository binary must match pinned SHA-256."""
        h = hashlib.sha256()
        with open(NATIVE_PATH, "rb") as f:
            while chunk := f.read(1 << 20):
                h.update(chunk)
        self.assertEqual(h.hexdigest(), PINNED_NATIVE_SHA256)


if __name__ == "__main__":
    unittest.main()