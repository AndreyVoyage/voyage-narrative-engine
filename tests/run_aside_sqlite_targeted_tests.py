"""Standalone targeted SQLite tests for Ren'Py embedded Python runtime.

Run:
  C:/DEV/Narrative/renpy-8.5.3-sdk/lib/py3-windows-x86_64/python.exe
    tests/run_aside_sqlite_targeted_tests.py

This script does NOT import unittest — it uses manual record/assert patterns
compatible with the Ren'Py embedded Python (which lacks unittest/pytest).

Authorized write-set path:
  tests/run_aside_sqlite_targeted_tests.py
"""

import sys
import os
import hashlib
import json
import tempfile
import shutil
import traceback
from datetime import datetime, timezone, timedelta

# =============================================================================
# Configuration
# =============================================================================

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PYTHON_PACKAGES = os.path.join(REPO_ROOT, "novel", "game", "python-packages")
SQLITE3_DIR = os.path.join(PYTHON_PACKAGES, "sqlite3")
NATIVE_PATH = os.path.join(PYTHON_PACKAGES,
    "_sqlite3.cp312-mingw_x86_64_ucrt_llvm.pyd")

# Insert repo-local path FIRST
if PYTHON_PACKAGES not in sys.path:
    sys.path.insert(0, PYTHON_PACKAGES)

# Pinned values
PINNED_NATIVE_SHA256 = (
    "d6f829149200b18dfcfb5a3bc96c80e00005deed2536743a24f4b428957bbe4d"
)
PINNED_NATIVE_SIZE = 1523200

PINNED_PURE_PYTHON_HASHES = {
    "__init__.py": "f7cc982617b68e147540ef352d38310fe4d25c2c9c2542b67d0590c871df09a8",
    "dbapi2.py": "7c5c8d98df1f2c50c4062a3be2c0f0499190c179fa4fc281507a1ef763a98f28",
    "dump.py": "bbd9b9d14affcb013f8bd996e30e2cfd1b214d40a37916b9a67fce5b11820eff",
}

PINNED_SOURCE_HASHES = {
    "sqlite": "ea170e73e447703e8359308ca2e4366a3ae0c4304a8665896f068c736781c651",
    "cpython": "0c4db8f00ab490bfb5a4b0d0e763319d017226b5521f97e851412342ff04d459",
    "toolchain": "f4f3ad8616c4183ce7b0d72df634400945b41ea9816145fc2430df6003455db7",
    "import_lib": "125add086832756cbdb72625c97f692cea52b678ba4cb93983ac1ed7784e26e6",
}

SDK_PATH = r"C:\DEV\Narrative\renpy-8.5.3-sdk"
SDK_PYTHON_PACKAGES = os.path.join(SDK_PATH, "lib", "py3-windows-x86_64")
LEGACY_JSON_DIR = os.path.join(REPO_ROOT, "services", "aside_memory_json")

EXPECTED_NATIVE_FILENAME = "_sqlite3.cp312-mingw_x86_64_ucrt_llvm.pyd"
EXPECTED_SQLITE_VERSION = "3.45.3"

# =============================================================================
# Results accumulator
# =============================================================================

results = {
    "test_time": datetime.now(timezone(timedelta(hours=3))).strftime("%Y-%m-%d %H:%M UTC+3"),
    "python_executable": sys.executable,
    "python_version": sys.version,
    "sys_path": sys.path[:5],
    "tests": {},
}

pass_count = 0
fail_count = 0


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def record(test_name, passed, detail="", error=""):
    global pass_count, fail_count
    results["tests"][test_name] = {
        "passed": bool(passed),
        "detail": str(detail),
        "error": str(error),
    }
    if passed:
        pass_count += 1
        print(f"[PASS] {test_name}")
    else:
        fail_count += 1
        print(f"[FAIL] {test_name}")
    if detail:
        print(f"       {detail}")
    if error:
        print(f"       ERROR: {error}")


def assert_true(condition, test_name, detail=""):
    if condition:
        record(test_name, True, detail)
    else:
        record(test_name, False, detail, f"Expected True, got {condition}")
    return bool(condition)


def assert_equal(actual, expected, test_name, detail=""):
    if actual == expected:
        record(test_name, True, detail or f"{actual}")
        return True
    else:
        record(test_name, False, detail or f"Expected={expected} Actual={actual}",
               f"Mismatch: expected {expected}, got {actual}")
        return False


def assert_in(needle, haystack, test_name, detail=""):
    if needle in haystack:
        record(test_name, True, detail)
        return True
    else:
        record(test_name, False, detail, f"'{needle}' not found")
        return False


def assert_not_in(needle, haystack, test_name, detail=""):
    if needle not in haystack:
        record(test_name, True, detail)
        return True
    else:
        record(test_name, False, detail, f"'{needle}' unexpectedly found")
        return False


def assert_file_exists(path, test_name):
    exists = os.path.isfile(path)
    if exists:
        record(test_name, True, path)
    else:
        record(test_name, False, path, "File missing")
    return exists


def assert_dir_exists(path, test_name):
    exists = os.path.isdir(path)
    if exists:
        record(test_name, True, path)
    else:
        record(test_name, False, path, "Directory missing")
    return exists


# =============================================================================
# TEST SUITE
# =============================================================================

print("=" * 70)
print("ASIDE V2 SLICE 2 SQLITE CORRECTION — TARGETED TESTS")
print(f"Python:  {sys.version}")
print(f"Repo:    {REPO_ROOT}")
print("=" * 70)
print()

# ---- SECTION 1: File Existence ----

print("--- File Existence ---")

assert_file_exists(
    os.path.join(SQLITE3_DIR, "__init__.py"),
    "01_sqlite3___init___exists")
assert_file_exists(
    os.path.join(SQLITE3_DIR, "dbapi2.py"),
    "02_sqlite3_dbapi2_exists")
assert_file_exists(
    os.path.join(SQLITE3_DIR, "dump.py"),
    "03_sqlite3_dump_exists")
assert_file_exists(
    NATIVE_PATH,
    "04_native_binary_exists")
assert_file_exists(
    os.path.join(PYTHON_PACKAGES, "NOTICE.txt"),
    "05_NOTICE_txt_exists")
assert_file_exists(
    os.path.join(PYTHON_PACKAGES, "PROVENANCE.md"),
    "06_PROVENANCE_md_exists")
assert_file_exists(
    os.path.join(REPO_ROOT, "THIRD_PARTY_NOTICES.md"),
    "07_THIRD_PARTY_NOTICES_md_exists")
assert_file_exists(
    os.path.join(REPO_ROOT, "build", "scripts", "build_sqlite3.py"),
    "08_build_script_exists")
assert_file_exists(
    os.path.join(REPO_ROOT, "build", "provenance", "source_manifest.json"),
    "09_source_manifest_exists")
assert_file_exists(
    os.path.join(REPO_ROOT, "build", "provenance", "source_hashes.txt"),
    "10_source_hashes_exists")
assert_file_exists(
    os.path.join(REPO_ROOT, "build", "provenance", "toolchain_lock.json"),
    "11_toolchain_lock_exists")

# ---- SECTION 2: Binary Identity ----

print("\n--- Binary Identity ---")

actual_name = os.path.basename(NATIVE_PATH)
assert_equal(
    actual_name, EXPECTED_NATIVE_FILENAME,
    "12_native_filename_abi_suffix",
    f"Filename: {actual_name}")

actual_sha256 = sha256_file(NATIVE_PATH)
assert_equal(
    actual_sha256, PINNED_NATIVE_SHA256,
    "13_native_sha256_match",
    f"SHA256: {actual_sha256}")

actual_size = os.path.getsize(NATIVE_PATH)
assert_equal(
    actual_size, PINNED_NATIVE_SIZE,
    "14_native_size_match",
    f"Size: {actual_size}")

# ---- SECTION 3: Pure-Python Hashes ----

print("\n--- Pure-Python Hashes ---")

for fname, expected_hash in PINNED_PURE_PYTHON_HASHES.items():
    path = os.path.join(SQLITE3_DIR, fname)
    actual = sha256_file(path)
    assert_equal(
        actual, expected_hash,
        f"15_hash_{fname.replace('.py','')}",
        f"SHA256: {actual}")

# ---- SECTION 4: Import Tests ----

print("\n--- Import Tests ---")

try:
    import _sqlite3
    record("16_import__sqlite3", True,
           f"Loaded from: {_sqlite3.__file__}")
    assert_in(
        PYTHON_PACKAGES, _sqlite3.__file__,
        "17__sqlite3_origin_local",
        f"Origin: {_sqlite3.__file__}")
except Exception as e:
    record("16_import__sqlite3", False, "", str(e))
    record("17__sqlite3_origin_local", False, "Skipped — import failed")

try:
    import sqlite3
    record("18_import_sqlite3", True,
           f"Loaded from: {sqlite3.__file__}")
    assert_equal(
        sqlite3.sqlite_version, EXPECTED_SQLITE_VERSION,
        "19_sqlite_version",
        f"Version: {sqlite3.sqlite_version}")
    assert_in(
        PYTHON_PACKAGES, sqlite3.__file__,
        "20_sqlite3_origin_local",
        f"Origin: {sqlite3.__file__}")
except Exception as e:
    record("18_import_sqlite3", False, "", str(e))
    record("19_sqlite_version", False, "Skipped — import failed")
    record("20_sqlite3_origin_local", False, "Skipped — import failed")

# ---- SECTION 5: Threadsafety ----

print("\n--- Threadsafety ---")
try:
    import sqlite3
    assert_equal(
        sqlite3.threadsafety, 3,
        "21_threadsafety",
        f"threadsafety={sqlite3.threadsafety} (DB-API 2.0 level 3 = SQLITE_THREADSAFE=1 serialized)")
except Exception as e:
    record("21_threadsafety", False, "", str(e))

# ---- SECTION 6: Capability Tests ----

print("\n--- Capability Tests ---")

try:
    import sqlite3
    # FTS5
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE VIRTUAL TABLE probe_fts5 USING fts5(x)")
    conn.close()
    record("22_FTS5_create_table", True, "Virtual table created")
except Exception as e:
    record("22_FTS5_create_table", False, "", str(e))

try:
    import sqlite3
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE VIRTUAL TABLE probe_fts5 USING fts5(content)")
    conn.execute("INSERT INTO probe_fts5(rowid, content) VALUES(1, 'hello world')")
    rows = conn.execute(
        "SELECT rowid FROM probe_fts5 WHERE probe_fts5 MATCH 'hello'"
    ).fetchall()
    assert_equal(len(rows), 1, "23_FTS5_insert_and_match",
                 f"Found {len(rows)} rows")
    conn.close()
except Exception as e:
    record("23_FTS5_insert_and_match", False, "", str(e))

try:
    import sqlite3
    tmp_dir = tempfile.mkdtemp(prefix="sqlite_test_")
    try:
        db_path = os.path.join(tmp_dir, "test_wal.db")
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        row = conn.execute("PRAGMA journal_mode").fetchone()
        assert_equal(row[0], "wal", "24_WAL_mode_activation",
                     f"Journal mode: {row[0]}")
        conn.close()
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
except Exception as e:
    record("24_WAL_mode_activation", False, "", str(e))

try:
    import sqlite3
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys=ON")
    row = conn.execute("PRAGMA foreign_keys").fetchone()
    assert_equal(row[0], 1, "25_foreign_keys_on",
                 f"foreign_keys={row[0]}")
    conn.close()
except Exception as e:
    record("25_foreign_keys_on", False, "", str(e))

try:
    import sqlite3
    src = sqlite3.connect(":memory:")
    src.execute("CREATE TABLE t(x)")
    src.execute("INSERT INTO t VALUES(42)")
    src.commit()
    dst = sqlite3.connect(":memory:")
    src.backup(dst)
    row = dst.execute("SELECT x FROM t").fetchone()
    assert_equal(row[0], 42, "26_backup", "Backup completed")
    src.close()
    dst.close()
except Exception as e:
    record("26_backup", False, "", str(e))

try:
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
        assert_equal(row[0], 42, "27_persistence",
                     f"Value: {row[0]}")
        conn2.close()
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
except Exception as e:
    record("27_persistence", False, "", str(e))

try:
    import sqlite3
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE t(x)")
    conn.execute("BEGIN")
    conn.execute("INSERT INTO t VALUES(1)")
    conn.execute("COMMIT")
    assert_equal(
        conn.execute("SELECT x FROM t").fetchone()[0], 1,
        "28_transaction_commit")
    conn.close()
except Exception as e:
    record("28_transaction_commit", False, "", str(e))

try:
    import sqlite3
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE t(x)")
    conn.execute("BEGIN")
    conn.execute("INSERT INTO t VALUES(1)")
    conn.execute("ROLLBACK")
    rows = conn.execute("SELECT x FROM t").fetchall()
    assert_equal(len(rows), 0, "29_transaction_rollback")
    conn.close()
except Exception as e:
    record("29_transaction_rollback", False, "", str(e))

# ---- SECTION 7: Security ----

print("\n--- Security ---")

try:
    import sqlite3
    conn = sqlite3.connect(":memory:")
    has_enable = hasattr(conn, "enable_load_extension")
    has_load = hasattr(conn, "load_extension")
    ok = not has_enable and not has_load
    record("30_load_extension_forbidden", ok,
           f"enable_load_extension={has_enable}, load_extension={has_load}")
    conn.close()
except Exception as e:
    record("30_load_extension_forbidden", False, "", str(e))

# ---- SECTION 8: Preservation Checks ----

print("\n--- Preservation Checks ---")

# No SQLite3 DLL
dll_path = os.path.join(PYTHON_PACKAGES, "sqlite3.dll")
assert_true(
    not os.path.isfile(dll_path),
    "31_no_sqlite3_dll",
    f"Check: {dll_path}")

# SDK not modified
sdk_sqlite3_init = os.path.join(SDK_PYTHON_PACKAGES, "sqlite3", "__init__.py")
assert_true(
    not os.path.isfile(sdk_sqlite3_init),
    "32_SDK_not_modified_sqlite3",
    f"Check: {sdk_sqlite3_init}")

sdk_pyd_files = []
if os.path.isdir(SDK_PYTHON_PACKAGES):
    for f in os.listdir(SDK_PYTHON_PACKAGES):
        if f.startswith("_sqlite3") and f.endswith(".pyd"):
            sdk_pyd_files.append(f)
assert_equal(
    len(sdk_pyd_files), 0,
    "33_SDK_not_modified_pyd",
    f"SDK PYD files: {sdk_pyd_files}")

# Legacy JSON preserved
legacy_exists = os.path.isdir(LEGACY_JSON_DIR)
if legacy_exists:
    found_any = False
    for root, _, files in os.walk(LEGACY_JSON_DIR):
        for fn in files:
            if fn.endswith(".json") or fn.endswith(".py"):
                found_any = True
                break
        if found_any:
            break
    record("34_legacy_json_preserved", found_any,
           f"Directory: {LEGACY_JSON_DIR}, Found files: {found_any}")
else:
    record("34_legacy_json_preserved", True,
           f"Directory: {LEGACY_JSON_DIR} (does not exist in this worktree)")

# ---- SECTION 9: Source Lock / Provenance Agreement ----

print("\n--- Source Lock / Provenance Agreement ---")

try:
    manifest_path = os.path.join(
        REPO_ROOT, "build", "provenance", "source_manifest.json")
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    assert_equal(
        manifest["sqlite"]["archive_sha256"],
        PINNED_SOURCE_HASHES["sqlite"],
        "35_manifest_sqlite_hash")

    assert_equal(
        manifest["cpython"]["archive_sha256"],
        PINNED_SOURCE_HASHES["cpython"],
        "36_manifest_cpython_hash")

    assert_equal(
        manifest["toolchain"]["archive_sha256"],
        PINNED_SOURCE_HASHES["toolchain"],
        "37_manifest_toolchain_hash")
except Exception as e:
    record("35_manifest_sqlite_hash", False, "", str(e))
    record("36_manifest_cpython_hash", False, "", str(e))
    record("37_manifest_toolchain_hash", False, "", str(e))

# Source hashes.txt coverage
try:
    hashes_path = os.path.join(
        REPO_ROOT, "build", "provenance", "source_hashes.txt")
    with open(hashes_path, "r", encoding="utf-8") as f:
        hashes_content = f.read()
    all_found = True
    for label, expected in PINNED_SOURCE_HASHES.items():
        if expected not in hashes_content:
            all_found = False
            break
    record("38_source_hashes_coverage", all_found)
except Exception as e:
    record("38_source_hashes_coverage", False, "", str(e))

# PROVENANCE.md contains native SHA-256
try:
    prov_path = os.path.join(PYTHON_PACKAGES, "PROVENANCE.md")
    with open(prov_path, "r", encoding="utf-8") as f:
        prov_content = f.read()
    assert_in(
        PINNED_NATIVE_SHA256, prov_content,
        "39_provenance_md_native_hash")
except Exception as e:
    record("39_provenance_md_native_hash", False, "", str(e))

# ---- SECTION 10: No Runtime Download Path ----

print("\n--- No Runtime Download ---")

try:
    aside_path = os.path.join(REPO_ROOT, "novel", "game", "aside.rpy")
    with open(aside_path, "r", encoding="utf-8") as f:
        aside_content = f.read().lower()
    suspicious = ["urllib.request", "requests.get", "pip install sqlite3",
                  "sqlite3.dll"]
    ok = True
    for pattern in suspicious:
        if pattern in aside_content:
            ok = False
            break
    record("40_no_runtime_download", ok)
except Exception as e:
    record("40_no_runtime_download", False, "", str(e))

# ---- SECTION 11: Compile Options (PRAGMA compile_options) ----

print("\n--- Compile Options ---")

try:
    import sqlite3
    conn = sqlite3.connect(":memory:")
    options = [r[0] for r in conn.execute("PRAGMA compile_options").fetchall()]
    assert_in("ENABLE_FTS5", options, "41_compile_FTS5")
    assert_in("THREADSAFE=1", options, "42_compile_THREADSAFE")
    assert_in("OMIT_LOAD_EXTENSION", options, "43_compile_OMIT_LOAD")
    assert_true(
        len(options) >= 35,
        "44_compile_options_count",
        f"Count: {len(options)}")
    conn.close()
except Exception as e:
    record("41_compile_FTS5", False, "", str(e))
    record("42_compile_THREADSAFE", False, "", str(e))
    record("43_compile_OMIT_LOAD", False, "", str(e))
    record("44_compile_options_count", False, "", str(e))

# ---- SECTION 12: Native Binary Re-Verification ----

print("\n--- Final Binary Verification ---")

final_sha256 = sha256_file(NATIVE_PATH)
assert_equal(
    final_sha256, PINNED_NATIVE_SHA256,
    "45_final_binary_sha256",
    f"SHA256: {final_sha256}")

# =============================================================================
# Summary
# =============================================================================

total = pass_count + fail_count
print("\n" + "=" * 70)
print(f"RESULTS: {pass_count}/{total} PASSED, {fail_count} FAILED")
print(f"Python:  {sys.executable}")
print(f"Repo:    {REPO_ROOT}")
print("=" * 70)

results["pass_count"] = pass_count
results["fail_count"] = fail_count
results["total"] = total
results["all_passed"] = fail_count == 0

# Write JSON results
results_path = os.path.join(os.path.dirname(__file__), "targeted_test_results.json")
with open(results_path, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
print(f"\nResults saved: {results_path}")

if fail_count > 0:
    print("\n*** SOME TESTS FAILED ***")
    sys.exit(1)
else:
    print("\n*** ALL TESTS PASSED ***")
    sys.exit(0)