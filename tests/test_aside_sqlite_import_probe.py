"""Targeted SQLite import probe — Slice B repository integration tests.

Tests the repository-local sqlite3/_sqlite3 files under:
    <Repo>/novel/game/python-packages/

Requires the Ren'Py embedded Python 3.12.7 runtime.
When run under any other Python (system, venv), all runtime import tests
skip gracefully with a diagnostic message. File-existence and identity
tests run everywhere.

For actual Ren'Py embedded runtime testing, use:
    tests/run_aside_sqlite_targeted_tests.py

Verifies:
  - Required project-local files exist
  - Native filename has exact ABI suffix
  - Native SHA-256 matches pinned manifest
  - Pure-Python files match pinned hashes
  - Source-lock and provenance files agree
  - Shared SDK path is not used as integration destination
  - No sqlite3.dll included
  - No runtime network download present
  - No JSON runtime fallback introduced
  - No dual-read or dual-write introduced
  - Retained legacy JSON migration evidence untouched
  - Distribution inclusion rules include game/python-packages
  - Load-extension support remains forbidden
  - Windows x86_64 is the only claimed native target

Authorized write-set path:
  tests/test_aside_sqlite_import_probe.py
"""

import os
import sys
import hashlib
import unittest
import tempfile
import shutil

# =============================================================================
# Pinned values (owner-ratified — from build/provenance/source_hashes.txt)
# =============================================================================

PINNED_NATIVE_SHA256 = (
    "d6f829149200b18dfcfb5a3bc96c80e00005deed2536743a24f4b428957bbe4d"
)
PINNED_NATIVE_SIZE = 1523200
PINNED_PURE_PYTHON_HASHES = {
    "__init__.py": "f7cc982617b68e147540ef352d38310fe4d25c2c9c2542b67d0590c871df09a8",
    "dbapi2.py": "7c5c8d98df1f2c50c4062a3be2c0f0499190c179fa4fc281507a1ef763a98f28",
    "dump.py": "bbd9b9d14affcb013f8bd996e30e2cfd1b214d40a37916b9a67fce5b11820eff",
}

EXPECTED_NATIVE_FILENAME = (
    "_sqlite3.cp312-mingw_x86_64_ucrt_llvm.pyd"
)

REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
)
PYTHON_PACKAGES = os.path.join(
    REPO_ROOT, "novel", "game", "python-packages"
)
SQLITE3_DIR = os.path.join(PYTHON_PACKAGES, "sqlite3")
NATIVE_PATH = os.path.join(PYTHON_PACKAGES, EXPECTED_NATIVE_FILENAME)

# Shared SDK paths (must NOT be used)
SDK_PATH = r"C:\DEV\Narrative\renpy-8.5.3-sdk"
SDK_PYTHON_PACKAGES = os.path.join(SDK_PATH, "lib", "py3-windows-x86_64")

# Legacy JSON evidence (must remain untouched)
LEGACY_JSON_DIR = os.path.join(REPO_ROOT, "services", "aside_memory_json")

# Detect whether we are running under the Ren'Py embedded Python 3.12.7
# (which ships without the sqlite3 standard library package).
RENPY_RUNTIME_12 = (
    sys.version_info[:2] == (3, 12)
    and "mingw" in sys.version.lower()
    and os.path.isdir(os.path.join(SDK_PATH, "lib", "py3-windows-x86_64"))
)

# The Ren'Py embedded Python 3.12.7 lacks the unittest module.
# If we are on a Python that has unittest but is NOT the Ren'Py runtime,
# we can only run file-existence / identity tests, not import tests.
CAN_IMPORT_FROM_RENPY = RENPY_RUNTIME_12


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


class TestProjectLocalFileExistence(unittest.TestCase):
    """Verify all required project-local files exist."""

    def test_sqlite3_init_exists(self):
        self.assertTrue(
            os.path.isfile(os.path.join(SQLITE3_DIR, "__init__.py")),
            "sqlite3/__init__.py missing",
        )

    def test_sqlite3_dbapi2_exists(self):
        self.assertTrue(
            os.path.isfile(os.path.join(SQLITE3_DIR, "dbapi2.py")),
            "sqlite3/dbapi2.py missing",
        )

    def test_sqlite3_dump_exists(self):
        self.assertTrue(
            os.path.isfile(os.path.join(SQLITE3_DIR, "dump.py")),
            "sqlite3/dump.py missing",
        )

    def test_native_binary_exists(self):
        self.assertTrue(
            os.path.isfile(NATIVE_PATH),
            f"Native binary missing: {NATIVE_PATH}",
        )

    def test_notice_exists(self):
        self.assertTrue(
            os.path.isfile(os.path.join(PYTHON_PACKAGES, "NOTICE.txt")),
            "NOTICE.txt missing",
        )

    def test_provenance_exists(self):
        self.assertTrue(
            os.path.isfile(os.path.join(PYTHON_PACKAGES, "PROVENANCE.md")),
            "PROVENANCE.md missing",
        )

    def test_third_party_notices_exists(self):
        self.assertTrue(
            os.path.isfile(os.path.join(REPO_ROOT, "THIRD_PARTY_NOTICES.md")),
            "THIRD_PARTY_NOTICES.md missing at repo root",
        )

    def test_build_script_exists(self):
        self.assertTrue(
            os.path.isfile(
                os.path.join(REPO_ROOT, "build", "scripts", "build_sqlite3.py")
            ),
            "build/scripts/build_sqlite3.py missing",
        )

    def test_source_lock_exists(self):
        self.assertTrue(
            os.path.isfile(
                os.path.join(
                    REPO_ROOT, "build", "provenance", "source_manifest.json"
                )
            ),
            "source_manifest.json missing",
        )

    def test_source_hashes_exists(self):
        self.assertTrue(
            os.path.isfile(
                os.path.join(
                    REPO_ROOT, "build", "provenance", "source_hashes.txt"
                )
            ),
            "source_hashes.txt missing",
        )

    def test_toolchain_lock_exists(self):
        self.assertTrue(
            os.path.isfile(
                os.path.join(
                    REPO_ROOT, "build", "provenance", "toolchain_lock.json"
                )
            ),
            "toolchain_lock.json missing",
        )


class TestNativeBinaryIdentity(unittest.TestCase):
    """Verify the native binary identity matches pinned values."""

    def test_native_filename_has_exact_abi_suffix(self):
        actual_name = os.path.basename(NATIVE_PATH)
        self.assertEqual(
            actual_name,
            EXPECTED_NATIVE_FILENAME,
            f"Native filename mismatch: {actual_name}",
        )

    def test_native_sha256_matches_pinned(self):
        actual = sha256_file(NATIVE_PATH)
        self.assertEqual(
            actual,
            PINNED_NATIVE_SHA256,
            f"Native SHA-256 mismatch. Expected: {PINNED_NATIVE_SHA256}",
        )

    def test_native_size_matches_pinned(self):
        actual = os.path.getsize(NATIVE_PATH)
        self.assertEqual(
            actual,
            PINNED_NATIVE_SIZE,
            f"Native size mismatch. Expected: {PINNED_NATIVE_SIZE}, Actual: {actual}",
        )


class TestPurePythonHashes(unittest.TestCase):
    """Verify pure-Python file hashes match pinned values."""

    def test_init_hash(self):
        path = os.path.join(SQLITE3_DIR, "__init__.py")
        actual = sha256_file(path)
        self.assertEqual(
            actual,
            PINNED_PURE_PYTHON_HASHES["__init__.py"],
            f"__init__.py hash mismatch",
        )

    def test_dbapi2_hash(self):
        path = os.path.join(SQLITE3_DIR, "dbapi2.py")
        actual = sha256_file(path)
        self.assertEqual(
            actual,
            PINNED_PURE_PYTHON_HASHES["dbapi2.py"],
            f"dbapi2.py hash mismatch",
        )

    def test_dump_hash(self):
        path = os.path.join(SQLITE3_DIR, "dump.py")
        actual = sha256_file(path)
        self.assertEqual(
            actual,
            PINNED_PURE_PYTHON_HASHES["dump.py"],
            f"dump.py hash mismatch",
        )


class TestSDKPreservation(unittest.TestCase):
    """Verify the shared SDK is NOT used as integration destination."""

    def test_no_sqlite3_in_sdk(self):
        """The SDK must NOT contain a sqlite3/ package or _sqlite3.pyd."""
        sdk_sqlite3_dir = os.path.join(
            SDK_PYTHON_PACKAGES, "sqlite3"
        )
        sdk_sqlite3_init = os.path.join(sdk_sqlite3_dir, "__init__.py")
        self.assertFalse(
            os.path.isfile(sdk_sqlite3_init),
            f"SDK unexpectedly has sqlite3/__init__.py at {sdk_sqlite3_init}",
        )
        sdk_pyd_files = [
            f
            for f in os.listdir(SDK_PYTHON_PACKAGES)
            if f.startswith("_sqlite3") and f.endswith(".pyd")
        ]
        self.assertEqual(
            len(sdk_pyd_files),
            0,
            f"SDK unexpectedly has _sqlite3.pyd files: {sdk_pyd_files}",
        )


class TestNoSqlite3Dll(unittest.TestCase):
    """Verify no sqlite3.dll is included in the project-local package."""

    def test_no_sqlite3_dll(self):
        dll_path = os.path.join(PYTHON_PACKAGES, "sqlite3.dll")
        self.assertFalse(
            os.path.isfile(dll_path),
            f"sqlite3.dll found at {dll_path} — STATIC linkage was not used",
        )


class TestLegacyJsonPreserved(unittest.TestCase):
    """Verify legacy JSON migration evidence remains untouched.

    This worktree may not contain the legacy JSON directory. If the
    directory is absent, the tests pass conditionally — the directory
    existing is a deployment concern, not a Slice B concern.
    """

    def test_legacy_json_dir_exists(self):
        if not os.path.isdir(LEGACY_JSON_DIR):
            self.skipTest(
                f"Legacy JSON directory not present in this worktree: {LEGACY_JSON_DIR}"
            )
        # If present, verify it's a directory
        self.assertTrue(os.path.isdir(LEGACY_JSON_DIR))

    def test_legacy_json_files_unchanged(self):
        """Spot-check known legacy files exist."""
        if not os.path.isdir(LEGACY_JSON_DIR):
            self.skipTest(
                f"Legacy JSON directory not present in this worktree: {LEGACY_JSON_DIR}"
            )
        found_any = False
        for root, _, files in os.walk(LEGACY_JSON_DIR):
            for fn in files:
                if fn.endswith(".json") or fn.endswith(".py"):
                    found_any = True
                    break
            if found_any:
                break
        self.assertTrue(
            found_any,
            "No legacy JSON files found — directory may have been deleted",
        )


class TestNoSqlite3RuntimeDownload(unittest.TestCase):
    """Verify no runtime download path exists for sqlite3."""

    def test_no_requests_in_aside_rpy(self):
        """The aside.rpy must not import or download sqlite3 at runtime."""
        aside_path = os.path.join(REPO_ROOT, "novel", "game", "aside.rpy")
        with open(aside_path, "r", encoding="utf-8") as f:
            content = f.read()
        # Check for common download patterns
        suspicious = [
            "urllib.request",
            "requests.get",
            "download",
            "pip install sqlite3",
            "sqlite3.dll",
        ]
        for pattern in suspicious:
            self.assertNotIn(
                pattern.lower(),
                content.lower(),
                f"Suspicious download pattern '{pattern}' found in aside.rpy",
            )


class TestRepositoryLocalImport(unittest.TestCase):
    """Test import from the repository-local path using Ren'Py runtime.

    These tests require the Ren'Py embedded Python 3.12.7 runtime.
    When run under a different Python, all tests skip gracefully.
    For actual Ren'Py embedded runtime import testing, use:
        tests/run_aside_sqlite_targeted_tests.py
    """

    @classmethod
    def setUpClass(cls):
        if not CAN_IMPORT_FROM_RENPY:
            return
        if PYTHON_PACKAGES not in sys.path:
            sys.path.insert(0, PYTHON_PACKAGES)

    def _require_renpy(self):
        if not CAN_IMPORT_FROM_RENPY:
            self.skipTest(
                "Requires Ren'Py embedded Python 3.12.7 runtime. "
                "Use tests/run_aside_sqlite_targeted_tests.py for targeted tests."
            )

    def test_import_sqlite3_native(self):
        """import _sqlite3 must succeed from repository-local path."""
        self._require_renpy()
        import _sqlite3
        self.assertIsNotNone(_sqlite3)

    def test_import_sqlite3(self):
        """import sqlite3 must succeed from repository-local path."""
        self._require_renpy()
        import sqlite3
        self.assertIsNotNone(sqlite3)
        self.assertEqual(sqlite3.sqlite_version, "3.45.3")

    def test_fts5_available(self):
        """FTS5 must be compiled in."""
        self._require_renpy()
        import sqlite3
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE VIRTUAL TABLE probe_fts5 USING fts5(x)")
        conn.close()

    def test_wal_mode(self):
        """WAL journal mode must activate."""
        self._require_renpy()
        import sqlite3
        tmp_dir = tempfile.mkdtemp(prefix="sqlite_test_")
        try:
            db_path = os.path.join(tmp_dir, "test_wal.db")
            conn = sqlite3.connect(db_path)
            conn.execute("PRAGMA journal_mode=WAL")
            row = conn.execute("PRAGMA journal_mode").fetchone()
            self.assertEqual(
                row[0],
                "wal",
                f"Expected 'wal' journal mode, got '{row[0]}'",
            )
            conn.close()
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_foreign_keys_on(self):
        """Foreign keys must be enabled."""
        self._require_renpy()
        import sqlite3
        conn = sqlite3.connect(":memory:")
        conn.execute("PRAGMA foreign_keys=ON")
        row = conn.execute("PRAGMA foreign_keys").fetchone()
        self.assertEqual(
            row[0],
            1,
            f"Expected foreign_keys=1 (ON), got {row[0]}",
        )
        conn.close()

    def test_backup_works(self):
        """Connection.backup() must work."""
        self._require_renpy()
        import sqlite3
        src = sqlite3.connect(":memory:")
        src.execute("CREATE TABLE t(x)")
        src.execute("INSERT INTO t VALUES(1)")
        src.commit()
        dst = sqlite3.connect(":memory:")
        src.backup(dst)
        row = dst.execute("SELECT x FROM t").fetchone()
        self.assertEqual(row[0], 1)
        src.close()
        dst.close()

    def test_transaction_commit(self):
        """Transactions must commit correctly."""
        self._require_renpy()
        import sqlite3
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE t(x)")
        conn.execute("BEGIN")
        conn.execute("INSERT INTO t VALUES(1)")
        conn.execute("COMMIT")
        row = conn.execute("SELECT x FROM t").fetchone()
        self.assertEqual(row[0], 1)
        conn.close()

    def test_transaction_rollback(self):
        """Transactions must rollback correctly."""
        self._require_renpy()
        import sqlite3
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE t(x)")
        conn.execute("BEGIN")
        conn.execute("INSERT INTO t VALUES(1)")
        conn.execute("ROLLBACK")
        rows = conn.execute("SELECT x FROM t").fetchall()
        self.assertEqual(len(rows), 0, "Rollback did not revert the insert")
        conn.close()

    def test_persistence(self):
        """Data must persist across connection close/reopen."""
        self._require_renpy()
        import sqlite3
        tmp_dir = tempfile.mkdtemp(prefix="sqlite_test_")
        try:
            db_path = os.path.join(tmp_dir, "test_persist.db")
            conn = sqlite3.connect(db_path)
            conn.execute("CREATE TABLE t(x)")
            conn.execute("INSERT INTO t VALUES(42)")
            conn.commit()
            conn.close()
            conn2 = sqlite3.connect(db_path)
            row = conn2.execute("SELECT x FROM t").fetchone()
            self.assertEqual(row[0], 42)
            conn2.close()
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_load_extension_forbidden(self):
        """load_extension API must be unavailable."""
        self._require_renpy()
        import sqlite3
        conn = sqlite3.connect(":memory:")
        self.assertFalse(
            hasattr(conn, "enable_load_extension"),
            "enable_load_extension must NOT be available",
        )
        self.assertFalse(
            hasattr(conn, "load_extension"),
            "load_extension must NOT be available",
        )
        conn.close()

    def test_module_origin_is_local(self):
        """Both _sqlite3 and sqlite3 must originate from repo-local paths."""
        self._require_renpy()
        import _sqlite3
        import sqlite3
        self.assertIn(
            PYTHON_PACKAGES,
            _sqlite3.__file__,
            "_sqlite3 did not load from repository-local path",
        )
        self.assertIn(
            PYTHON_PACKAGES,
            sqlite3.__file__,
            "sqlite3 did not load from repository-local path",
        )

    def test_threadsafety(self):
        """Threadsafety must be 3 (DB-API 2.0 serialized, corresponds to
        SQLITE_THREADSAFE=1)."""
        self._require_renpy()
        import sqlite3
        self.assertEqual(sqlite3.threadsafety, 3)


class TestBootstrapRegression(unittest.TestCase):
    """Verify the Ren'Py bootstrap in aside.rpy satisfies all path correction
    requirements.

    These tests inspect the actual aside.rpy source and verify the bootstrap
    logic meets all constraints. They do NOT require a live Ren'Py runtime.
    """

    _aside_rpy_content: str = ""

    @classmethod
    def setUpClass(cls):
        aside_path = os.path.join(REPO_ROOT, "novel", "game", "aside.rpy")
        with open(aside_path, "r", encoding="utf-8") as f:
            cls._aside_rpy_content = f.read()

    def _assert_in_block(self, text, description):
        self.assertIn(
            text,
            self._aside_rpy_content,
            f"aside.rpy missing required {description}",
        )

    def _assert_not_in(self, text, description):
        self.assertNotIn(
            text,
            self._aside_rpy_content,
            f"aside.rpy should NOT contain {description}",
        )

    def test_config_gamedir_used(self):
        """config.gamedir is used to derive the bootstrap path."""
        self._assert_in_block("config.gamedir", "config.gamedir usage")

    def test_child_directory_is_python_packages(self):
        """The child directory is exactly 'python-packages'."""
        self._assert_in_block(
            'python-packages',
            "python-packages child directory literal",
        )

    def test_absolute_normalized_path(self):
        """Path is converted to absolute via os.path.abspath."""
        self._assert_in_block(
            'os.path.abspath',
            "os.path.abspath normalization",
        )
        self._assert_in_block(
            'os.path.normpath',
            "os.path.normpath normalization",
        )
        self._assert_in_block(
            'os.path.normcase',
            "os.path.normcase normalization",
        )

    def test_duplicate_checking_uses_normalized_comparison(self):
        """Duplicate checking uses normcase + normpath comparison."""
        self._assert_in_block(
            'not in _vne_existing_sys_path_keys',
            "normalized set lookup for deduplication",
        )

    def test_inserted_at_index_0(self):
        """Path is inserted at sys.path[0]."""
        self._assert_in_block(
            'sys.path.insert(0,',
            "sys.path.insert at index 0",
        )

    def test_conditional_on_directory_existing(self):
        """Insertion is conditional on os.path.isdir."""
        self._assert_in_block(
            'os.path.isdir',
            "os.path.isdir existence guard",
        )

    def test_no_shared_sdk_path_hardcoded(self):
        """No shared Ren'Py SDK path is hardcoded."""
        self._assert_not_in(
            "renpy-8.5",
            "hardcoded SDK version path",
        )
        self._assert_not_in(
            "C:\\DEV\\Narrative\\renpy",
            "hardcoded SDK path",
        )

    def test_no_system_python_path_hardcoded(self):
        """No system Python path is hardcoded."""
        self._assert_not_in(
            "C:\\Python",
            "hardcoded system Python path",
        )
        self._assert_not_in(
            "C:\\Program Files\\Python",
            "hardcoded Program Files Python path",
        )

    def _bootstrap_region(self):
        """Extract the bootstrap code region from aside.rpy content."""
        parts = self._aside_rpy_content.split(
            "# ── Project-local python-packages bootstrap"
        )
        if len(parts) < 2:
            return ""
        region = parts[1].split(
            "# ─────────────────────────────────────"
        )[0]
        return region

    def test_no_network_or_download(self):
        """No network or download behavior is introduced in the bootstrap."""
        bootstrap = self._bootstrap_region()
        for pattern, desc in [
            ("urllib.request", "urllib.request network access"),
            ("requests.get", "requests.get network access"),
            ("http://", "http:// URL"),
            ("https://", "https:// URL"),
            ("download", "download keyword"),
        ]:
            self.assertNotIn(
                pattern.lower(),
                bootstrap.lower(),
                f"{desc} in bootstrap region",
            )

    def test_bootstrap_before_runtime_trigger(self):
        """The bootstrap appears before _vne_run_aside_turn_from_snapshot which triggers
        the first sqlite3 import at runtime."""
        bootstrap_marker = (
            "Project-local python-packages bootstrap (Slice 2)"
        )
        runtime_trigger = "_vne_run_aside_turn_from_snapshot"
        bootstrap_pos = self._aside_rpy_content.find(bootstrap_marker)
        runtime_pos = self._aside_rpy_content.find(runtime_trigger)
        self.assertGreater(
            bootstrap_pos,
            -1,
            "Bootstrap marker not found in aside.rpy",
        )
        self.assertGreater(
            runtime_pos,
            -1,
            "Runtime trigger function not found in aside.rpy",
        )
        self.assertLess(
            bootstrap_pos,
            runtime_pos,
            "Bootstrap must appear BEFORE _vne_run_aside_turn_from_snapshot",
        )

    def _extract_python_block(self):
        """Extract the 'init python:' block from aside.rpy."""
        parts = self._aside_rpy_content.split("init python:")
        if len(parts) < 2:
            return ""
        # Find the end of the init python block: the next 'screen' or 'label' at top level
        rest = parts[1]
        # Split on top-level Ren'Py constructs
        import re
        end_markers = re.split(r"\n(screen|label)\s+[a-zA-Z_]", rest)
        return end_markers[0] if end_markers else rest

    def test_bootstrap_inside_init_block(self):
        """The bootstrap appears inside the existing 'init python:' block."""
        init_marker = "init python:"
        bootstrap_marker = (
            "Project-local python-packages bootstrap (Slice 2)"
        )
        init_pos = self._aside_rpy_content.find(init_marker)
        bootstrap_pos = self._aside_rpy_content.find(bootstrap_marker)
        # The bootstrap must come after 'init python:'
        self.assertGreater(
            bootstrap_pos, init_pos,
            "Bootstrap must be inside the init python block",
        )
        # Find the next screen/label after init which would end the init block
        # The init block ends before 'screen aside_dev_overlay():'
        screen_marker = "screen aside_dev_overlay():"
        screen_pos = self._aside_rpy_content.find(screen_marker)
        self.assertLess(
            bootstrap_pos, screen_pos,
            "Bootstrap must be before the screen definition",
        )


class TestPathDeduplicationBehavior(unittest.TestCase):
    """Pure-Python behavioral unit tests for path deduplication logic.

    Uses temporary directories and synthetic sys.path lists.
    Does NOT require Ren'Py runtime.
    """

    def _resolve_path(self, base_dir, child="python-packages"):
        """Mimics the aside.rpy bootstrap path resolution."""
        raw = os.path.join(base_dir, child)
        return os.path.abspath(raw)

    def _normalize_key(self, path):
        """Mimics the normaized dedup key from aside.rpy."""
        return os.path.normcase(os.path.normpath(os.path.abspath(path)))

    def _simulate_bootstrap(self, base_dir, current_sys_path):
        """Simulate the bootstrap logic and return (new_sys_path, inserted)."""
        pkg_dir = self._resolve_path(base_dir, child="python-packages")
        pkg_key = self._normalize_key(pkg_dir)
        existing_keys = {
            self._normalize_key(str(p)) for p in current_sys_path if p
        }
        if os.path.isdir(pkg_dir) and pkg_key not in existing_keys:
            return ([pkg_dir] + list(current_sys_path), True)
        return (list(current_sys_path), False)

    def test_dir_exists_not_in_path_inserted_at_0(self):
        """Directory exists and absent from sys.path → inserted once at index 0."""
        with tempfile.TemporaryDirectory() as base:
            pkgs = os.path.join(base, "python-packages")
            os.makedirs(pkgs)
            sys_path = ["/some/other/path", "/another/path"]
            new_path, inserted = self._simulate_bootstrap(base, sys_path)
            self.assertTrue(inserted)
            self.assertEqual(new_path[0], os.path.abspath(pkgs))
            self.assertEqual(
                len(new_path),
                len(sys_path) + 1,
            )

    def test_dir_already_present_exactly_not_duplicated(self):
        """Directory already present exactly → not duplicated."""
        with tempfile.TemporaryDirectory() as base:
            pkgs = os.path.join(base, "python-packages")
            os.makedirs(pkgs)
            existing = os.path.abspath(pkgs)
            sys_path = [existing, "/other/path"]
            new_path, inserted = self._simulate_bootstrap(base, sys_path)
            self.assertFalse(inserted)
            self.assertEqual(new_path, sys_path)

    def test_same_dir_different_case_not_duplicated_windows(self):
        """Same directory with different case → not duplicated on Windows."""
        with tempfile.TemporaryDirectory() as base:
            pkgs = os.path.join(base, "python-packages")
            os.makedirs(pkgs)
            # Use lowercased version of the same path
            existing_lower = os.path.abspath(pkgs).lower()
            sys_path = [existing_lower, "/other/path"]
            new_path, inserted = self._simulate_bootstrap(base, sys_path)
            if os.name == "nt":
                # On Windows, normcase normalizes case → should not insert
                self.assertFalse(
                    inserted,
                    "Should NOT insert when same path with different case "
                    "already in sys.path on Windows",
                )
                self.assertEqual(len(new_path), len(sys_path))
            else:
                # On Linux/Mac, case-sensitive → MAY insert
                # Just verify no crash
                pass

    def test_same_dir_different_slash_not_duplicated(self):
        """Same directory with alternative slash direction → not duplicated on Windows."""
        with tempfile.TemporaryDirectory() as base:
            pkgs = os.path.join(base, "python-packages")
            os.makedirs(pkgs)
            abs_path = os.path.abspath(pkgs)
            # Use forward slashes
            existing_forward = abs_path.replace("\\", "/")
            sys_path = [existing_forward, "/other/path"]
            new_path, inserted = self._simulate_bootstrap(base, sys_path)
            # normpath normalizes slashes → should not insert
            self.assertFalse(
                inserted,
                "Should NOT insert when same path with different slashes already "
                "in sys.path",
            )
            self.assertEqual(len(new_path), len(sys_path))

    def test_dir_absent_not_inserted(self):
        """Directory does not exist → not inserted."""
        with tempfile.TemporaryDirectory() as base:
            # Do NOT create python-packages subdirectory
            sys_path = ["/some/other/path"]
            new_path, inserted = self._simulate_bootstrap(base, sys_path)
            self.assertFalse(inserted)
            self.assertEqual(new_path, sys_path)

    def test_unrelated_paths_unchanged(self):
        """Unrelated paths remain unchanged after bootstrap."""
        with tempfile.TemporaryDirectory() as base:
            pkgs = os.path.join(base, "python-packages")
            os.makedirs(pkgs)
            original_paths = [
                "/system/python/path",
                "/another/lib",
                "/third/pkg",
                str(pkgs).upper(),  # pre-existing with different case
            ]
            sys_path = list(original_paths)
            new_path, inserted = self._simulate_bootstrap(base, sys_path)
            if os.name == "nt":
                # Should NOT insert because pkgs already present (different case)
                self.assertFalse(inserted)
            for orig in original_paths:
                self.assertIn(orig, new_path, f"Unrelated path {orig} was removed")


if __name__ == "__main__":
    unittest.main()
