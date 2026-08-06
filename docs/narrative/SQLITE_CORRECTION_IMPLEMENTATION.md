# SQLite Correction Implementation — Slice B Repository Integration

**ASIDE V2 SLICE 2 SQLITE CORRECTION**  
**Slice B — Repository Integration**  
**Date: 2026-08-06**

---

## 1. Summary

This document describes the repository integration phase (Slice B) of the
SQLite correction for the Voyage Narrative Engine Character Aside module.

The correction adds a project-local `sqlite3` package and statically-linked
`_sqlite3` native extension to `novel/game/python-packages/`, enabling the
Ren'Py 8.5.3 runtime to use SQLite for the Character Aside memory store.

---

## 2. Decision Trail

| RSP | Decision | Owner Choice | Source |
|-----|----------|-------------|--------|
| RSP-1 | `PROJECT_DISTRIBUTION_LOCAL` | Ratified | `ASIDE_V2_SLICE2_SQLITE_OWNER_RATIFICATION_2026-08-06.md` |
| RSP-2 | `PIN_ALL_SOURCES_WITH_SHA256` | Ratified | Same |
| RSP-3 | `LLVM_MINGW_20241217_UCRT_X86_64_CLANG_19_1_6` | Ratified | Same |
| RSP-4 | `STATIC` SQLite linkage | Ratified | Same |
| RSP-5 | SQLite 3.45.3 | Ratified | Same |
| RSP-6 | Corrected compile config (R2) | Ratified | Same |
| RSP-7 | `TRACK_BINARY_IN_GIT` | Ratified | Same |
| RSP-8 | `SKIP_LFS` | Ratified | Same |
| RSP-9 | `BOTH_NOTICE_TXT_AND_THIRD_PARTY_NOTICES_MD` | Ratified | Same |
| RSP-10 | `MARKDOWN_PRIMARY_JSON_SECONDARY` | Ratified | Same |
| RSP-11 | `REQUIRED_CLEAN_WINDOWS_VM_QA_GATE` | Ratified | Same |
| RSP-12 | `WINDOWS_X86_64_ONLY` | Ratified | Same |
| RSP-13 | `ON_CVE_ADVISORY_OR_CPYTHON_UPGRADE` | Ratified | Same |
| RSP-14 | `CATEGORICALLY_FORBIDDEN` SDK modification | Ratified | Same |
| RSP-15 | `AUTHORIZE_AFTER_OWNER_RATIFIES_ALL_RSP` | Ratified | Same |

**Corrected decision packet:** `ASIDE_V2_SLICE2_SQLITE_OWNER_DECISION_PACKET_CORRECTION_R2_2026-08-06.md`

---

## 3. Write-Set

### 3.1 Runtime Components

| # | Path | Type | Classification |
|---|------|------|---------------|
| 1 | `novel/game/python-packages/sqlite3/__init__.py` | PURE-PYTHON | REQUIRED, SOURCE |
| 2 | `novel/game/python-packages/sqlite3/dbapi2.py` | PURE-PYTHON | REQUIRED, SOURCE |
| 3 | `novel/game/python-packages/sqlite3/dump.py` | PURE-PYTHON | REQUIRED, SOURCE |
| 4 | `novel/game/python-packages/_sqlite3.cp312-mingw_x86_64_ucrt_llvm.pyd` | NATIVE BINARY | REQUIRED, BINARY |

### 3.2 Licenses and Provenance

| # | Path | Type |
|---|------|------|
| 5 | `novel/game/python-packages/NOTICE.txt` | LICENSE |
| 6 | `novel/game/python-packages/PROVENANCE.md` | DOCUMENTATION |
| 7 | `THIRD_PARTY_NOTICES.md` (repo root) | LICENSE |

### 3.3 Build Support

| # | Path | Type |
|---|------|------|
| 8 | `build/scripts/build_sqlite3.py` | BUILD SCRIPT |
| 9 | `build/provenance/source_manifest.json` | PROVENANCE |
| 10 | `build/provenance/source_hashes.txt` | PROVENANCE |
| 11 | `build/provenance/toolchain_lock.json` | PROVENANCE |

### 3.4 Tests

| # | Path | Type |
|---|------|------|
| 15 | `tests/test_aside_sqlite_import_probe.py` | TEST |
| 16 | `tests/test_aside_sqlite_feature_probe.py` | TEST |

### 3.5 Documentation

| # | Path | Type |
|---|------|------|
| 17 | `docs/narrative/SQLITE_CORRECTION_IMPLEMENTATION.md` | DOCUMENTATION |

### 3.6 Configuration (Optional)

| # | Path | Type |
|---|------|------|
| 18 | `.gitignore` (append `build/output/`) | CONFIG |

---

## 4. Compile Configuration (Corrected R2)

### SQLite Core

```
-DSQLITE_ENABLE_FTS5
-DSQLITE_THREADSAFE=1
-DSQLITE_OMIT_LOAD_EXTENSION
-DSQLITE_DEFAULT_WAL_SYNCHRONOUS=1
-DSQLITE_DQS=0
```

### CPython Wrapper

`PY_SQLITE_ENABLE_LOAD_EXTENSION` is **NOT defined** (load-extension FORBIDDEN).

### Runtime PRAGMAs

```
PRAGMA journal_mode=WAL
PRAGMA foreign_keys=ON
```

Applied by `tools/aside_memory_store_sqlite.py` at connection open time.

---

## 5. Binary Identity

| Field | Value |
|-------|-------|
| Filename | `_sqlite3.cp312-mingw_x86_64_ucrt_llvm.pyd` |
| Size | 1,523,200 bytes |
| SHA-256 | `d6f829149200b18dfcfb5a3bc96c80e00005deed2536743a24f4b428957bbe4d` |
| SQLite version | 3.45.3 |
| CPython version | 3.12.7 |
| SQLite linkage | STATIC |
| Load extensions | FORBIDDEN |
| Target platform | Windows x86_64 |
| DLL dependencies | `libpython3.12.dll`, `KERNEL32.dll`, UCRT |
| `sqlite3.dll` dependency | NONE |

---

## 6. Slice A Build (External)

| Field | Value |
|-------|-------|
| Build root | `C:\DEV\Narrative\LOCAL_STORAGE\renpy_sqlite_build\ASIDE_V2_SLICE2_SQLITE_BUILD_SLICE_A_2026-08-06` |
| Direct runtime tests | 26/26 PASSED |
| Negative test | PASSED |
| Restoration test | PASSED |
| SDK preservation | NO substantive changes |
| Build report | `ASIDE_V2_SLICE2_SQLITE_CORRECTION_SLICE_A_BUILD_REPORT_2026-08-06.md` |

---

## 7. Slice B Verification

Slice B verification consists of:
1. **Targeted import probe** — tests/test_aside_sqlite_import_probe.py
2. **Targeted feature probe** — tests/test_aside_sqlite_feature_probe.py
3. **Regression suite** — existing test_aside_memory_* tests, PAC tests, full suite
4. **Exact diff audit** — git status/diff validation
5. **Binary SHA-256** — post-test repository binary verification

---

## 8. Rollback Procedure

To remove the SQLite correction:

1. Delete `novel/game/python-packages/sqlite3/` directory
2. Delete `novel/game/python-packages/_sqlite3.*.pyd`
3. Delete `novel/game/python-packages/NOTICE.txt`
4. Delete `novel/game/python-packages/PROVENANCE.md`
5. Remove SQLite/CPython entries from `THIRD_PARTY_NOTICES.md`
6. Delete `build/scripts/build_sqlite3.py`
7. Delete `build/provenance/` directory
8. Delete `tests/test_aside_sqlite_import_probe.py`
9. Delete `tests/test_aside_sqlite_feature_probe.py`
10. Delete `docs/narrative/SQLITE_CORRECTION_IMPLEMENTATION.md`
11. Revert `.gitignore` changes

After rollback, `import sqlite3` will return to `ModuleNotFoundError` status.

---

## 9. Standing Restrictions

| Restriction | Status |
|-------------|--------|
| No shared Ren'Py SDK modification | BINDING |
| No system-Python binary copying | BINDING |
| No sidecar implementation | BINDING |
| No JSON active runtime fallback | BINDING |
| No JSON dual-read/write | BINDING |
| Legacy JSON retained as read-only evidence | BINDING |
| SQLite-only active backend | BINDING |
| In-process storage (IN_PROCESS_RENPY) | BINDING |

---

## 10. Authorized Next Actions

1. **Slice C** — Independent QA (separate worktree, independent agent)
2. **Slice D** — Live Character Aside QA (mock LLM, full turn lifecycle)

No commit, push, merge, or branch deletion is authorized without
explicit separate approval.

---

*Created: 2026-08-06 — ASIDE V2 SLICE 2 SQLITE CORRECTION SLICE B*