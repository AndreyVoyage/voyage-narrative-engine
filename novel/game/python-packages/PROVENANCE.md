# PROVENANCE.md — SQLite Correction Build Provenance

> ASIDE V2 SLICE 2 SQLITE CORRECTION SLICE B
> Repository: `vne-aside-v2-slice2-sqlite-correction`
> Branch: `feature/aside-v2-slice2-sqlite-correction`
> HEAD: `afa64d3af14ad78366dc34cad68af3fb91f2423c`

---

## 1. Component Identity

| Field | Value |
|-------|-------|
| Component | `_sqlite3.cp312-mingw_x86_64_ucrt_llvm.pyd` |
| Type | Native Python extension (.pyd) |
| Target runtime | Ren'Py 8.5.3 embedded CPython 3.12.7 |
| Platform | Windows x86_64 |
| SQLite linkage | STATIC |
| Package | `novel/game/python-packages/` |

---

## 2. Source Provenance

### 2.1 SQLite 3.45.3

| Field | Value |
|-------|-------|
| Version | 3.45.3 |
| Release date | 2024-04-15 |
| Official URL | https://sqlite.org/download.html |
| Amalgamation URL | https://www.sqlite.org/2024/sqlite-amalgamation-3450300.zip |
| Archive name | `sqlite-amalgamation-3450300.zip` |
| Archive size | 2,730,988 bytes (2.60 MB) |
| SHA-256 | `ea170e73e447703e8359308ca2e4366a3ae0c4304a8665896f068c736781c651` |
| License | Public Domain |

### 2.2 CPython 3.12.7

| Field | Value |
|-------|-------|
| Version | 3.12.7 |
| Official URL | https://github.com/python/cpython/tree/v3.12.7 |
| Source archive | `cpython-3.12.7-source-fresh.tar.gz` |
| SHA-256 | `0c4db8f00ab490bfb5a4b0d0e763319d017226b5521f97e851412342ff04d459` |
| License | PSF License Version 2 |

Pure-Python files (`sqlite3/__init__.py`, `dbapi2.py`, `dump.py`) are byte-for-byte copies from CPython 3.12.7 `Lib/sqlite3/`.

CPython `_sqlite3` wrapper sources (`Modules/_sqlite/*.c`) were used to compile the native extension.

### 2.3 Ren'Py 8.5.3

| Field | Value |
|-------|-------|
| Version | 8.5.3.26051504 |
| Python version | 3.12.7 (heads/mingw-v3.12.7-dirty) |
| Compiler identifier | GCC UCRT Clang 19.1.6 |
| ABI tag | mingw_x86_64_ucrt_llvm |
| License | MIT License |

Import library `libpython3.12.a` was generated from `lib/python3.12.dll` via gendef + llvm-dlltool.

---

## 3. Toolchain

| Field | Value |
|-------|-------|
| Toolchain | llvm-mingw 20241217 |
| Archive URL | https://github.com/mstorsjo/llvm-mingw/releases/tag/20241217 |
| Archive SHA-256 | `f4f3ad8616c4183ce7b0d72df634400945b41ea9816145fc2430df6003455db7` |
| C Compiler | `x86_64-w64-mingw32-clang.exe` |
| Compiler version | Clang 19.1.6 |
| Compiler target | `x86_64-w64-windows-gnu` |
| Linker | LLD 19.1.6 (`ld.lld.exe`) |

---

## 4. Build Configuration

### 4.1 SQLite Core Compile Definitions

```
-DSQLITE_ENABLE_FTS5
-DSQLITE_THREADSAFE=1
-DSQLITE_OMIT_LOAD_EXTENSION
-DSQLITE_DEFAULT_WAL_SYNCHRONOUS=1
-DSQLITE_DQS=0
```

### 4.2 CPython Wrapper Compile Definitions

`PY_SQLITE_ENABLE_LOAD_EXTENSION` is **NOT defined** (load-extension FORBIDDEN).

### 4.3 Build Environment

```
-D_WIN64
-DNDEBUG
```

### 4.4 Compile Sources

**SQLite core:**
- `sqlite3.c` (SQLite 3.45.3 amalgamation)

**_sqlite3 wrapper (CPython 3.12.7 `Modules/_sqlite/`):**
- `blob.c`, `connection.c`, `cursor.c`, `microprotocols.c`, `module.c`, `prepare_protocol.c`, `row.c`, `statement.c`, `util.c`

### 4.5 Link

```
x86_64-w64-mingw32-clang.exe -shared -O2
  -o _sqlite3.cp312-mingw_x86_64_ucrt_llvm.pyd
  sqlite3.o blob.o connection.o cursor.o microprotocols.o module.o
  prepare_protocol.o row.o statement.o util.o
  -L<link_inputs> -lpython3.12 -lkernel32
```

---

## 5. Binary Identity

### 5.1 Native Output

| Field | Value |
|-------|-------|
| Filename | `_sqlite3.cp312-mingw_x86_64_ucrt_llvm.pyd` |
| Size | 1,523,200 bytes |
| SHA-256 | `d6f829149200b18dfcfb5a3bc96c80e00005deed2536743a24f4b428957bbe4d` |
| ABI suffix | `.cp312-mingw_x86_64_ucrt_llvm.pyd` |

### 5.2 PE Audit

```
Machine:        IMAGE_FILE_MACHINE_AMD64 (x86_64)
Export:         PyInit__sqlite3 (ordinal 1)
Characteristics: IMAGE_FILE_DLL | IMAGE_FILE_EXECUTABLE_IMAGE | IMAGE_FILE_LARGE_ADDRESS_AWARE
DLL Characteristics: DYNAMIC_BASE | HIGH_ENTROPY_VA | NX_COMPAT
```

### 5.3 DLL Dependencies

```
libpython3.12.dll        (Ren'Py 8.5.3 embedded runtime)
KERNEL32.dll             (Windows system)
api-ms-win-crt-*.dll     (UCRT)
```

**No `sqlite3.dll` dependency** — SQLite is statically linked.

### 5.4 Pure-Python Pair Hashes

| File | SHA-256 |
|------|---------|
| `sqlite3/__init__.py` | `f7cc982617b68e147540ef352d38310fe4d25c2c9c2542b67d0590c871df09a8` |
| `sqlite3/dbapi2.py` | `7c5c8d98df1f2c50c4062a3be2c0f0499190c179fa4fc281507a1ef763a98f28` |
| `sqlite3/dump.py` | `bbd9b9d14affcb013f8bd996e30e2cfd1b214d40a37916b9a67fce5b11820eff` |

---

## 6. Runtime Policy

| PRAGMA | Where set | Status |
|--------|-----------|--------|
| `journal_mode=WAL` | `tools/aside_memory_store_sqlite.py` | REQUIRED RUNTIME |
| `foreign_keys=ON` | `tools/aside_memory_store_sqlite.py` | REQUIRED RUNTIME |

---

## 7. Build Authority

| Decision | Ratified value |
|----------|---------------|
| RSP-1 Packaging topology | `PROJECT_DISTRIBUTION_LOCAL` |
| RSP-2 Source acquisition | `PIN_ALL_SOURCES_WITH_SHA256` |
| RSP-3 Toolchain | `LLVM_MINGW_20241217_UCRT_X86_64_CLANG_19_1_6` |
| RSP-4 SQLite linkage | `STATIC` |
| RSP-5 SQLite version | `SQLITE_3_45_3` |
| RSP-6 Compile configuration | See Section 4 |
| RSP-7 Binary in Git | `TRACK_BINARY_IN_GIT` |
| RSP-8 Git LFS | `SKIP_LFS` |
| RSP-9 License placement | `BOTH_NOTICE_TXT_AND_THIRD_PARTY_NOTICES_MD` |
| RSP-10 Provenance format | `MARKDOWN_PRIMARY_JSON_SECONDARY` |
| RSP-11 Clean Windows QA | `REQUIRED_CLEAN_WINDOWS_VM_QA_GATE` |
| RSP-12 Platform scope | `WINDOWS_X86_64_ONLY` |
| RSP-13 Update policy | `ON_CVE_ADVISORY_OR_CPYTHON_UPGRADE` |
| RSP-14 SDK modification | `CATEGORICALLY_FORBIDDEN` |
| RSP-15 Implementation gate | `AUTHORIZE_AFTER_OWNER_RATIFIES_ALL_RSP` |

Owner ratification: `C:\DEV\Narrative\LOCAL_STORAGE\handoffs\ASIDE_V2_SLICE2_SQLITE_OWNER_RATIFICATION_2026-08-06.md`

---

## 8. Slice A Build

| Field | Value |
|-------|-------|
| Build root | `C:\DEV\Narrative\LOCAL_STORAGE\renpy_sqlite_build\ASIDE_V2_SLICE2_SQLITE_BUILD_SLICE_A_2026-08-06` |
| Build script | `build_sqlite3.py` |
| Build timestamp | 2026-08-06 |
| Direct runtime tests | 26/26 PASSED |
| Negative test | PASSED |
| Restoration test | PASSED |
| Slice A report | `C:\DEV\Narrative\LOCAL_STORAGE\handoffs\ASIDE_V2_SLICE2_SQLITE_CORRECTION_SLICE_A_BUILD_REPORT_2026-08-06.md` |

---

*Created: 2026-08-06*
*Slice: B — Repository Integration*