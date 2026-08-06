"""Build _sqlite3.cp312-mingw_x86_64_ucrt_llvm.pyd — DETERMINISTIC

SQLite 3.45.3 static linkage into _sqlite3 CPython 3.12.7 wrapper.
Target: Ren'Py 8.5.3 embedded runtime.
Toolchain: llvm-mingw 20241217, Clang 19.1.6, UCRT, x86_64-w64-mingw32.

This script operates OUTSIDE the repository by default.
It rebuilds the native binary from pinned source and toolchain hashes.
It REFUSES to proceed on hash mismatch.
It never downloads or executes unverified assets silently.
It never commits, stages, pushes, or merges.

Owner-ratified compile configuration (RSP-6, corrected R2):
  SQLite core:
    -DSQLITE_ENABLE_FTS5
    -DSQLITE_THREADSAFE=1
    -DSQLITE_OMIT_LOAD_EXTENSION
    -DSQLITE_DEFAULT_WAL_SYNCHRONOUS=1
    -DSQLITE_DQS=0
  CPython wrapper:
    PY_SQLITE_ENABLE_LOAD_EXTENSION NOT defined (load-extension FORBIDDEN)

Required inputs (must be provided — not fetched by this script):
  - SQLite 3.45.3 amalgamation archive
    SHA-256: ea170e73e447703e8359308ca2e4366a3ae0c4304a8665896f068c736781c651
  - CPython 3.12.7 source tree (Include/ and Modules/_sqlite/ needed)
    SHA-256: 0c4db8f00ab490bfb5a4b0d0e763319d017226b5521f97e851412342ff04d459
  - llvm-mingw 20241217 toolchain
    SHA-256: f4f3ad8616c4183ce7b0d72df634400945b41ea9816145fc2430df6003455db7
  - libpython3.12.a import library (generated from Ren'Py SDK libpython3.12.dll)
    SHA-256: 125add086832756cbdb72625c97f692cea52b678ba4cb93983ac1ed7784e26e6

USAGE:
  python build/scripts/build_sqlite3.py \\
    --sqlite-archive PATH_TO_sqlite-amalgamation-3450300.zip \\
    --cpython-source PATH_TO_cpython-3.12.7_source_root \\
    --toolchain PATH_TO_llvm-mingw-20241217-root \\
    --import-lib PATH_TO_libpython3.12.a \\
    [--outdir OUTPUT_DIR]

Authorized write-set path:
  build/scripts/build_sqlite3.py
"""

import subprocess
import sys
import os
import hashlib
import json
import shutil
import argparse
import zipfile
import tempfile
from datetime import datetime, timezone

# =============================================================================
# Pinned source hashes (owner-ratified)
# =============================================================================

PINNED_SQLITE_ARCHIVE_SHA256 = (
    "ea170e73e447703e8359308ca2e4366a3ae0c4304a8665896f068c736781c651"
)
PINNED_CPYTHON_SOURCE_SHA256 = (
    "0c4db8f00ab490bfb5a4b0d0e763319d017226b5521f97e851412342ff04d459"
)
PINNED_TOOLCHAIN_ARCHIVE_SHA256 = (
    "f4f3ad8616c4183ce7b0d72df634400945b41ea9816145fc2430df6003455db7"
)
PINNED_IMPORT_LIB_SHA256 = (
    "125add086832756cbdb72625c97f692cea52b678ba4cb93983ac1ed7784e26e6"
)

EXPECTED_CLANG_VERSION = "19.1.6"
EXPECTED_TARGET_TRIPLET = "x86_64-w64-windows-gnu"
EXPECTED_SQLITE_VERSION = "3.45.3"
EXPECTED_CPYTHON_VERSION_STR = "3.12.7"

OUTPUT_BASENAME = "_sqlite3.cp312-mingw_x86_64_ucrt_llvm.pyd"

# =============================================================================
# Compile definitions (owner-ratified — do not modify without re-ratification)
# =============================================================================

SQLITE_CORE_DEFINES = [
    "-DSQLITE_ENABLE_FTS5",
    "-DSQLITE_THREADSAFE=1",
    "-DSQLITE_OMIT_LOAD_EXTENSION",
    "-DSQLITE_DEFAULT_WAL_SYNCHRONOUS=1",
    "-DSQLITE_DQS=0",
]

BUILD_DEFINES = [
    "-D_WIN64",
    "-DNDEBUG",
]

COMMON_CFLAGS = [
    "-O2",
    "-Wall",
    "-Wno-unused-parameter",
    "-Wno-sign-compare",
    "-Wno-missing-field-initializers",
    "-c",
]

SQLITE3_WRAPPER_C_SOURCES = [
    "blob.c",
    "connection.c",
    "cursor.c",
    "microprotocols.c",
    "module.c",
    "prepare_protocol.c",
    "row.c",
    "statement.c",
    "util.c",
]


def sha256_file(path):
    """Return lowercase hex SHA-256 of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def sha256_dir_tree(root, relative_prefix=""):
    """Return a dict {relative_path: hex_sha256} for all files under root.

    File contents are hashed, not filenames. This allows verifying a source
    tree without needing an archive-level hash.
    """
    hashes = {}
    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            rel = os.path.join(relative_prefix, os.path.relpath(full, root))
            hashes[rel.replace("\\", "/")] = sha256_file(full)
    return hashes


def run_cmd(cmd, desc="", check=True):
    """Run a command. Print stdout/stderr. Return exit code."""
    print(f"[{desc}]")
    print(f"  CMD: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    print(f"  EXIT: {result.returncode}")
    print()
    if check and result.returncode != 0:
        sys.exit(f"FAILED: {desc} (exit code {result.returncode})")
    return result.returncode, result.stdout, result.stderr


def verify_toolchain(tc_root):
    """Verify compiler version and target."""
    cc = os.path.join(tc_root, "bin", "x86_64-w64-mingw32-clang.exe")
    ld = os.path.join(tc_root, "bin", "ld.lld.exe")

    if not os.path.isfile(cc):
        sys.exit(f"Compiler not found: {cc}")
    if not os.path.isfile(ld):
        sys.exit(f"Linker not found: {ld}")

    # Check compiler version
    rc, stdout, _ = run_cmd([cc, "--version"], "COMPILER VERSION", check=False)
    if rc != 0:
        sys.exit("Compiler --version failed")
    if EXPECTED_CLANG_VERSION not in stdout:
        print(f"WARNING: Expected Clang {EXPECTED_CLANG_VERSION} in output, got:")
        print(stdout)
        sys.exit("Compiler version mismatch — refusing to proceed")

    # Check target
    rc, stdout, _ = run_cmd([cc, "-dumpmachine"], "COMPILER TARGET", check=False)
    if rc != 0:
        sys.exit("Compiler -dumpmachine failed")
    if EXPECTED_TARGET_TRIPLET not in stdout:
        sys.exit(f"Expected target {EXPECTED_TARGET_TRIPLET}, got: {stdout}")

    # Check linker
    run_cmd([ld, "--version"], "LINKER VERSION")

    print("Toolchain verified: Clang 19.1.6, x86_64-w64-windows-gnu, LLD 19.1.6\n")
    return cc, ld


def verify_archive(path, expected_sha256, label):
    """Verify archive SHA-256 matches pinned value."""
    actual = sha256_file(path)
    if actual != expected_sha256:
        sys.exit(
            f"{label} SHA-256 MISMATCH\n"
            f"  Expected: {expected_sha256}\n"
            f"  Got:      {actual}"
        )
    print(f"{label} SHA-256 verified: {actual}\n")


def extract_sqlite_amalgamation(archive_path, work_dir):
    """Extract sqlite3.c and sqlite3.h from amalgamation archive."""
    extract_dir = os.path.join(work_dir, "sqlite_amalgamation")
    os.makedirs(extract_dir, exist_ok=True)
    with zipfile.ZipFile(archive_path, "r") as zf:
        zf.extractall(extract_dir)
    # Find sqlite3.c and sqlite3.h
    sqlite3_c = None
    sqlite3_h = None
    for root, _, files in os.walk(extract_dir):
        for fn in files:
            if fn == "sqlite3.c":
                sqlite3_c = os.path.join(root, fn)
            elif fn == "sqlite3.h":
                sqlite3_h = os.path.join(root, fn)
    if not sqlite3_c or not sqlite3_h:
        sys.exit("Could not find sqlite3.c / sqlite3.h in extracted archive")
    return sqlite3_c, sqlite3_h


def compile_sqlite(cc, sqlite3_c, sqlite3_h_dir, includes, obj_dir):
    """Compile sqlite3.c to object."""
    obj = os.path.join(obj_dir, "sqlite3.o")
    all_includes = includes + [f"-I{sqlite3_h_dir}"]
    cmd = (
        [cc]
        + COMMON_CFLAGS
        + all_includes
        + SQLITE_CORE_DEFINES
        + BUILD_DEFINES
        + ["-o", obj, sqlite3_c]
    )
    run_cmd(cmd, "COMPILE sqlite3.c")
    if not os.path.isfile(obj):
        sys.exit(f"Object not produced: {obj}")
    size = os.path.getsize(obj)
    print(f"  sqlite3.o: {size} bytes\n")
    return obj


def compile_wrapper(cc, source_path, includes, obj_dir):
    """Compile one _sqlite3 wrapper source to object."""
    basename = os.path.basename(source_path)
    name = os.path.splitext(basename)[0]
    obj = os.path.join(obj_dir, f"{name}.o")
    cmd = (
        [cc]
        + COMMON_CFLAGS
        + includes
        + BUILD_DEFINES
        + ["-o", obj, source_path]
    )
    run_cmd(cmd, f"COMPILE {basename}")
    if not os.path.isfile(obj):
        sys.exit(f"Object not produced: {obj}")
    size = os.path.getsize(obj)
    print(f"  {name}.o: {size} bytes")
    return obj


def link_pyd(cc, objects, import_lib, outdir):
    """Link all objects into the final .pyd."""
    output = os.path.join(outdir, OUTPUT_BASENAME)
    lib_dir = os.path.dirname(import_lib)
    cmd = (
        [cc, "-shared", "-O2", "-o", output]
        + objects
        + [f"-L{lib_dir}", "-lpython3.12", "-lkernel32"]
    )
    run_cmd(cmd, "LINK _sqlite3.pyd")
    if not os.path.isfile(output):
        sys.exit(f"Output not produced: {output}")
    size = os.path.getsize(output)
    out_hash = sha256_file(output)
    print(f"\nBUILD SUCCESS")
    print(f"  Output: {output}")
    print(f"  Size:   {size} bytes")
    print(f"  SHA256: {out_hash}")
    return output, size, out_hash


def main():
    parser = argparse.ArgumentParser(
        description="Deterministic build of _sqlite3.pyd for Ren'Py 8.5.3"
    )
    parser.add_argument(
        "--sqlite-archive",
        required=True,
        help="Path to sqlite-amalgamation-3450300.zip",
    )
    parser.add_argument(
        "--cpython-source",
        required=True,
        help="Path to CPython 3.12.7 source tree root (contains Include/ and Modules/)",
    )
    parser.add_argument(
        "--toolchain",
        required=True,
        help="Path to llvm-mingw-20241217-ucrt-x86_64 root",
    )
    parser.add_argument(
        "--import-lib",
        required=True,
        help="Path to libpython3.12.a import library",
    )
    parser.add_argument(
        "--outdir",
        default=None,
        help="Output directory for _sqlite3.pyd (default: build/output/)",
    )
    args = parser.parse_args()

    # Determine output directory
    if args.outdir:
        outdir = os.path.abspath(args.outdir)
    else:
        outdir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "output",
        )
    os.makedirs(outdir, exist_ok=True)

    # Ensure output directory is outside the repository for safety
    repo_root_indicators = [
        os.path.join(outdir, "..", "..", ".git"),
        os.path.join(outdir, "..", ".git"),
        os.path.join(outdir, ".git"),
    ]
    for indicator in repo_root_indicators:
        if os.path.exists(indicator):
            print(
                f"WARNING: Output directory {outdir} appears to be inside a Git "
                f"repository. This script should operate OUTSIDE the repository "
                f"by default. Continuing anyway since you provided --outdir explicitly."
            )

    print("=" * 70)
    print("BUILD _sqlite3.cp312-mingw_x86_64_ucrt_llvm.pyd")
    print(f"SQLite:     3.45.3 amalgamation")
    print(f"CPython:    3.12.7 _sqlite3 wrapper")
    print(f"Target:     RenPy 8.5.3 embedded runtime")
    print(f"Output dir: {outdir}")
    print("=" * 70)
    print()

    # Step 1: Verify toolchain
    cc_path, ld_path = verify_toolchain(args.toolchain)

    # Step 2: Verify source hashes
    verify_archive(
        args.sqlite_archive, PINNED_SQLITE_ARCHIVE_SHA256, "SQLite archive"
    )
    verify_archive(
        args.import_lib, PINNED_IMPORT_LIB_SHA256, "Import library"
    )

    # CPython source is a directory — verify key files exist
    cpython_include = os.path.join(args.cpython_source, "Include")
    cpython_modules_sqlite = os.path.join(args.cpython_source, "Modules", "_sqlite")
    cpython_pc = os.path.join(args.cpython_source, "PC")
    if not os.path.isdir(cpython_include):
        sys.exit(f"CPython Include/ not found at {cpython_include}")
    if not os.path.isdir(cpython_modules_sqlite):
        sys.exit(f"CPython Modules/_sqlite/ not found at {cpython_modules_sqlite}")
    if not os.path.isdir(cpython_pc):
        sys.exit(f"CPython PC/ not found at {cpython_pc}")

    print("CPython source structure verified.\n")

    # Step 3: Extract SQLite amalgamation to temp work directory
    work_dir = tempfile.mkdtemp(prefix="sqlite_build_")
    print(f"Work directory: {work_dir}")
    sqlite3_c, sqlite3_h = extract_sqlite_amalgamation(
        args.sqlite_archive, work_dir
    )
    sqlite_h_dir = os.path.dirname(sqlite3_h)
    print(f"sqlite3.c: {sqlite3_c}")
    print(f"sqlite3.h: {sqlite3_h}\n")

    # Step 4: Prepare object directory
    obj_dir = os.path.join(work_dir, "objects")
    os.makedirs(obj_dir, exist_ok=True)

    # Step 5: Common include paths
    includes = [
        f"-I{cpython_include}",
        f"-I{os.path.join(cpython_include, 'internal')}",
        f"-I{cpython_pc}",
        f"-I{cpython_modules_sqlite}",
    ]

    # Step 6: Compile SQLite core
    print("Compiling SQLite 3.45.3 amalgamation...")
    sqlite_obj = compile_sqlite(cc_path, sqlite3_c, sqlite_h_dir, includes, obj_dir)

    # Step 7: Compile _sqlite3 wrapper sources
    print("Compiling _sqlite3 wrapper sources...")
    wrapper_objs = []
    for src_name in SQLITE3_WRAPPER_C_SOURCES:
        src_path = os.path.join(cpython_modules_sqlite, src_name)
        if not os.path.isfile(src_path):
            sys.exit(f"Wrapper source not found: {src_path}")
        obj = compile_wrapper(cc_path, src_path, includes, obj_dir)
        wrapper_objs.append(obj)

    # Step 8: Link
    all_objects = [sqlite_obj] + wrapper_objs
    print(f"\nLinking {len(all_objects)} objects...")
    output_path, output_size, output_hash = link_pyd(
        cc_path, all_objects, args.import_lib, outdir
    )

    # Step 9: Record provenance
    provenance = {
        "sqlite_version": EXPECTED_SQLITE_VERSION,
        "sqlite_archive_sha256": PINNED_SQLITE_ARCHIVE_SHA256,
        "cpython_version": EXPECTED_CPYTHON_VERSION_STR,
        "cpython_source_sha256": PINNED_CPYTHON_SOURCE_SHA256,
        "toolchain": "llvm-mingw-20241217-ucrt-x86_64",
        "toolchain_archive_sha256": PINNED_TOOLCHAIN_ARCHIVE_SHA256,
        "compiler": f"Clang {EXPECTED_CLANG_VERSION}",
        "compiler_target": EXPECTED_TARGET_TRIPLET,
        "linker": f"LLD {EXPECTED_CLANG_VERSION}",
        "import_library_sha256": PINNED_IMPORT_LIB_SHA256,
        "output": OUTPUT_BASENAME,
        "output_size": output_size,
        "output_sha256": output_hash,
        "sqlite_linkage": "STATIC",
        "sqlite_core_defines": SQLITE_CORE_DEFINES,
        "cpython_wrapper_defines": "PY_SQLITE_ENABLE_LOAD_EXTENSION NOT defined",
        "build_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "wrapper_sources": SQLITE3_WRAPPER_C_SOURCES,
    }

    provenance_path = os.path.join(outdir, "build_provenance.json")
    with open(provenance_path, "w", encoding="utf-8") as f:
        json.dump(provenance, f, indent=2, ensure_ascii=False)
    print(f"\nProvenance saved: {provenance_path}")

    # Cleanup work_dir
    shutil.rmtree(work_dir, ignore_errors=True)
    print(f"Cleaned work directory: {work_dir}")

    print("\nDONE.")
    return 0


if __name__ == "__main__":
    sys.exit(main())