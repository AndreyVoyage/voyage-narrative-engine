"""Build voyage-character-platform 0.1.0 wheel -- OFFLINE, PINNED, ISOLATED

Character Lab pinned VCP dependency build (LAB VCP DEPENDENCY BUILD).

Transforms the exact committed VCP Shared Core source at
ccade9e0ef943f63fec703b7ed5b436d7520324a into a locally generated,
installable wheel with machine-readable provenance.

Adapted from the proven Studio pattern
(STUDIO_J1A_IMMUTABLE_VCP_DEPENDENCY_BOOTSTRAP_V1). This script is intentionally
narrow and is NOT a dependency manager.

Guarantees:
  - Source comes ONLY from committed Git objects (``git archive <commit>``).
    The VCP working tree (including uncommitted work) is never read, never
    placed on PYTHONPATH, never built from and never editable-installed.
    Every materialized file is re-verified against its committed blob hash.
  - Backend artifacts (setuptools / wheel) are local files verified by
    pinned SHA-256. Nothing is downloaded: pip always runs with --no-index.
  - All generated material stays beneath build/output/ (gitignored).
  - The base Python interpreter is never modified; everything is installed
    into an isolated venv beneath build/output/.
  - Refuses to proceed on any mismatch (fail closed).
  - Never commits, stages, pushes or merges.

Required inputs (must be provided locally -- not fetched by this script):
  - VCP Git repository containing commit
    ccade9e0ef943f63fec703b7ed5b436d7520324a (default: sibling directory
    ../voyage-character-platform of the Lab repository root)
  - setuptools-84.0.0-py3-none-any.whl
    SHA-256: 51a52592b3b99e102b609654876bd65f19f999935166d1352678931132b0c670
  - wheel-0.48.0-py3-none-any.whl
    SHA-256: 3217dcc807155e45db462d7ef2431f5ddda0d7273b700d05a67b271ceb1287ab

USAGE:
  py build/scripts/build_vcp_shared_core.py ^
    [--vcp-repo PATH_TO_voyage-character-platform] ^
    [--backend-dir DIR] ^
    [--verify-reproducibility]

Generated layout (all gitignored):
  build/output/vcp_build_backend/      verified backend wheels (inputs)
  build/output/vcp_shared_core/        generated VCP wheel + work dirs
  build/output/vcp_shared_core_env/    isolated Python environment

Tracked output:
  build/provenance/vcp_shared_core_provenance.json
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path, PurePosixPath

# =============================================================================
# Pinned inputs (owner-ratified -- do not modify without re-ratification)
# =============================================================================

VCP_SOURCE_REPOSITORY = "voyage-character-platform"
VCP_SOURCE_COMMIT = "ccade9e0ef943f63fec703b7ed5b436d7520324a"

DEPENDENCY_NAME = "voyage-character-platform"
DEPENDENCY_VERSION = "0.1.0"
EXPECTED_WHEEL_FILENAME = "voyage_character_platform-0.1.0-py3-none-any.whl"
IMPORT_PACKAGE = "voyage_character_platform"

# Lab current project environment is Python 3.14 (discovered: 3.14.6).
PYTHON_MAJOR_MINOR = (3, 14)

BUILD_BACKEND = "setuptools.build_meta"
SETUPTOOLS_VERSION = "84.0.0"
WHEEL_VERSION = "0.48.0"

BACKEND_ARTIFACTS = {
    "setuptools": {
        "filename": "setuptools-84.0.0-py3-none-any.whl",
        "sha256": "51A52592B3B99E102B609654876BD65F19F999935166D1352678931132B0C670",
    },
    "wheel": {
        "filename": "wheel-0.48.0-py3-none-any.whl",
        "sha256": "3217DCC807155E45DB462D7EF2431F5DDDA0D7273B700D05A67B271CEB1287AB",
    },
}

BUILD_MODE = "pip-wheel-no-build-isolation-no-deps-no-index"

PROVENANCE_SCHEMA_VERSION = "vcp_shared_core_provenance/1.0"
BUILD_RECIPE_SCHEMA = "vcp-shared-core-build-recipe/1.0"

# Git config forced for `git archive` so the materialized bytes equal the
# committed blobs regardless of the local machine's core.autocrlf setting.
GIT_ARCHIVE_CONFIG = ["-c", "core.autocrlf=false", "-c", "core.eol=lf"]

# pip options applied to every pip invocation (offline, no resolution).
PIP_OFFLINE_ARGS = ["--no-index", "--no-deps", "--disable-pip-version-check"]

# Environment variables removed from every subprocess so nothing outside the
# pinned inputs can leak into the build or the smoke (no PYTHONPATH, no
# alternate package index, no user pip configuration).
SCRUBBED_ENV_VARS = (
    "PYTHONPATH",
    "PYTHONHOME",
    "PYTHONSTARTUP",
    "PIP_INDEX_URL",
    "PIP_EXTRA_INDEX_URL",
    "PIP_FIND_LINKS",
    "PIP_TRUSTED_HOST",
    "PIP_REQUIRE_VIRTUALENV",
    "PIP_USER",
    "PIP_TARGET",
    "PIP_PREFIX",
    "PIP_EDITABLE",
    "PIP_CONSTRAINT",
    "PIP_REQUIREMENT",
    "VIRTUAL_ENV",
)

# Output layout, relative to build/output/.
BACKEND_DIRNAME = "vcp_build_backend"
SHARED_CORE_DIRNAME = "vcp_shared_core"
ENV_DIRNAME = "vcp_shared_core_env"

PROVENANCE_RELPATH = ("build", "provenance", "vcp_shared_core_provenance.json")

# Committed source paths required in the materialized tree.
REQUIRED_SOURCE_PATHS = (
    "pyproject.toml",
    "src/voyage_character_platform/__init__.py",
    "src/voyage_character_platform/package_v1.py",
)


class BootstrapError(RuntimeError):
    """Fail-closed error: any mismatch aborts the bootstrap."""


# =============================================================================
# Canonical build recipe
# =============================================================================


def build_recipe():
    """Return the canonical, machine-independent logical build recipe.

    Contains no absolute paths, usernames, hostnames or timestamps, so its
    digest is stable across machines and can be recomputed independently.
    """
    return {
        "schema": BUILD_RECIPE_SCHEMA,
        "source_repository": VCP_SOURCE_REPOSITORY,
        "source_commit": VCP_SOURCE_COMMIT,
        "source_materialization": "git-archive-tar-autocrlf-false-eol-lf",
        "python_major_minor": "%d.%d" % PYTHON_MAJOR_MINOR,
        "backend": BUILD_BACKEND,
        "setuptools_version": SETUPTOOLS_VERSION,
        "setuptools_sha256": BACKEND_ARTIFACTS["setuptools"]["sha256"].lower(),
        "wheel_version": WHEEL_VERSION,
        "wheel_sha256": BACKEND_ARTIFACTS["wheel"]["sha256"].lower(),
        "build_mode": BUILD_MODE,
        "source_date_epoch": "commit-committer-time",
    }


def canonical_recipe_bytes(recipe=None):
    """Canonical serialization: sorted keys, no whitespace, ASCII, UTF-8."""
    if recipe is None:
        recipe = build_recipe()
    return json.dumps(
        recipe, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")


def build_command_digest(recipe=None):
    """SHA-256 (lowercase hex) of the canonical build recipe."""
    return hashlib.sha256(canonical_recipe_bytes(recipe)).hexdigest()


# =============================================================================
# Generic helpers
# =============================================================================


def sha256_file(path):
    """Return lowercase hex SHA-256 of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def git_blob_sha1(data):
    """Return the Git blob object id (SHA-1) for raw bytes."""
    h = hashlib.sha1()
    h.update(b"blob %d\0" % len(data))
    h.update(data)
    return h.hexdigest()


def output_root(repo_root):
    return Path(repo_root) / "build" / "output"


def output_layout(repo_root):
    """Return every generated location. All are beneath build/output/."""
    root = output_root(repo_root)
    shared = root / SHARED_CORE_DIRNAME
    return {
        "output_root": root,
        "backend_dir": root / BACKEND_DIRNAME,
        "shared_core_dir": shared,
        "work_dir": shared / "work",
        "wheel_path": shared / EXPECTED_WHEEL_FILENAME,
        "env_dir": root / ENV_DIRNAME,
    }


def ensure_under_output(repo_root, path):
    """Refuse any generated path that escapes build/output/."""
    root = output_root(repo_root).resolve()
    resolved = Path(path).resolve()
    if resolved != root and root not in resolved.parents:
        raise BootstrapError(f"Generated path escapes build/output/: {resolved}")
    return resolved


def reset_generated_dir(repo_root, path):
    """Remove and recreate a generated directory beneath build/output/."""
    target = ensure_under_output(repo_root, path)
    if target == output_root(repo_root).resolve():
        raise BootstrapError("Refusing to reset build/output/ itself")
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    return target


def subprocess_env(base_env=None, source_date_epoch=None, temp_dir=None):
    """Return a scrubbed, offline environment for build subprocesses.

    ``temp_dir`` (beneath build/output/) keeps pip's ephemeral build
    directories out of the system temp location.
    """
    env = dict(os.environ if base_env is None else base_env)
    for name in SCRUBBED_ENV_VARS:
        env.pop(name, None)
    env["PIP_NO_INDEX"] = "1"
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    env["PIP_NO_CACHE_DIR"] = "1"
    env["PIP_NO_INPUT"] = "1"
    env["PIP_CONFIG_FILE"] = os.devnull
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONUTF8"] = "1"
    if source_date_epoch is not None:
        env["SOURCE_DATE_EPOCH"] = str(source_date_epoch)
    if temp_dir is not None:
        for name in ("TMP", "TEMP", "TMPDIR"):
            env[name] = str(temp_dir)
    return env


def run_cmd(cmd, desc, env=None, cwd=None, stdout=None):
    """Run a command; fail closed on non-zero exit. Return stdout text."""
    print(f"[{desc}]")
    print(f"  CMD: {' '.join(str(c) for c in cmd)}")
    result = subprocess.run(
        [str(c) for c in cmd],
        env=env,
        cwd=cwd,
        stdout=stdout if stdout is not None else subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    out = ""
    if stdout is None and result.stdout:
        out = result.stdout.decode("utf-8", errors="replace")
        print(out.rstrip())
    if result.stderr:
        print(result.stderr.decode("utf-8", errors="replace").rstrip(), file=sys.stderr)
    if result.returncode != 0:
        raise BootstrapError(f"{desc} failed with exit code {result.returncode}")
    return out


# =============================================================================
# Repository root
# =============================================================================


def lab_repo_root():
    """Lab root derived from this file: build/scripts/<this> -> root."""
    return Path(__file__).resolve().parents[2]


def validate_repo_root(repo_root):
    top = run_cmd(
        ["git", "-C", repo_root, "rev-parse", "--show-toplevel"],
        "LAB REPOSITORY ROOT",
    ).strip()
    if Path(top).resolve() != Path(repo_root).resolve():
        raise BootstrapError(f"Lab root mismatch: git={top} script={repo_root}")
    # build/output/ must be gitignored so generated artifacts never get tracked.
    probe = f"build/output/{SHARED_CORE_DIRNAME}/probe"
    result = subprocess.run(
        ["git", "-C", str(repo_root), "check-ignore", "-q", probe]
    )
    if result.returncode != 0:
        raise BootstrapError("build/output/ is not gitignored -- refusing to proceed")
    print(f"Lab repository root verified: {repo_root}\n")


# =============================================================================
# Local inputs and backend artifacts
# =============================================================================


def verify_backend_artifacts(backend_dir):
    """Verify exact backend filenames and pinned SHA-256. Return paths."""
    backend_dir = Path(backend_dir)
    if not backend_dir.is_dir():
        raise BootstrapError(f"Backend directory not found: {backend_dir}")
    paths = {}
    for key, spec in BACKEND_ARTIFACTS.items():
        path = backend_dir / spec["filename"]
        if not path.is_file() or path.is_symlink():
            raise BootstrapError(f"Backend artifact missing or not a regular file: {path}")
        actual = sha256_file(path)
        expected = spec["sha256"].lower()
        if actual != expected:
            raise BootstrapError(
                f"{spec['filename']} SHA-256 MISMATCH\n"
                f"  Expected: {expected}\n"
                f"  Got:      {actual}"
            )
        print(f"{spec['filename']} SHA-256 verified: {actual}")
        paths[key] = path
    print()
    return paths


# =============================================================================
# Exact VCP source materialization
# =============================================================================


def verify_vcp_commit(vcp_repo):
    kind = run_cmd(
        ["git", "-C", vcp_repo, "cat-file", "-t", VCP_SOURCE_COMMIT],
        "VCP COMMIT EXISTS",
    ).strip()
    if kind != "commit":
        raise BootstrapError(f"{VCP_SOURCE_COMMIT} is not a commit (got {kind!r})")
    epoch = run_cmd(
        ["git", "-C", vcp_repo, "log", "-1", "--format=%ct", VCP_SOURCE_COMMIT],
        "VCP COMMIT TIME (SOURCE_DATE_EPOCH)",
    ).strip()
    return int(epoch)


def committed_blobs(vcp_repo):
    """Return {path: blob_sha1} for every file in the pinned commit tree."""
    out = run_cmd(
        ["git", "-C", vcp_repo, "ls-tree", "-r", "-z", "--full-tree", VCP_SOURCE_COMMIT],
        "VCP COMMITTED TREE",
    )
    blobs = {}
    for entry in out.split("\0"):
        if not entry:
            continue
        meta, path = entry.split("\t", 1)
        mode, kind, oid = meta.split()
        if kind != "blob" or mode not in ("100644", "100755"):
            raise BootstrapError(f"Unsupported tree entry {mode} {kind} {path}")
        blobs[path] = oid
    return blobs


def git_archive_command(vcp_repo):
    """The exact git archive invocation: committed tree of the pinned commit."""
    return ["git", "-C", str(vcp_repo)] + GIT_ARCHIVE_CONFIG + [
        "archive",
        "--format=tar",
        VCP_SOURCE_COMMIT,
    ]


def safe_extract_tar(tar_path, dest):
    """Extract a tar archive refusing links, devices and path escapes."""
    dest = Path(dest).resolve()
    with tarfile.open(tar_path, "r:") as tf:
        commit_comment = tf.pax_headers.get("comment")
        for member in tf.getmembers():
            name = PurePosixPath(member.name)
            if name.is_absolute() or ".." in name.parts:
                raise BootstrapError(f"Unsafe archive member path: {member.name}")
            if not (member.isfile() or member.isdir()):
                raise BootstrapError(f"Unsupported archive member type: {member.name}")
            target = (dest / member.name).resolve()
            if target != dest and dest not in target.parents:
                raise BootstrapError(f"Archive member escapes destination: {member.name}")
        tf.extractall(dest, filter="data")
    return commit_comment


def materialize_source(repo_root, vcp_repo, work_dir, blobs):
    """git archive the pinned commit and verify every byte against Git."""
    work_dir = reset_generated_dir(repo_root, work_dir)
    tar_path = ensure_under_output(repo_root, work_dir / "source.tar")
    src_dir = ensure_under_output(repo_root, work_dir / "src")
    src_dir.mkdir()
    with open(tar_path, "wb") as f:
        run_cmd(git_archive_command(vcp_repo), "GIT ARCHIVE PINNED COMMIT", stdout=f)
    comment = safe_extract_tar(tar_path, src_dir)
    if comment != VCP_SOURCE_COMMIT:
        raise BootstrapError(f"Archive commit id mismatch: {comment!r}")

    extracted = {
        p.relative_to(src_dir).as_posix(): p for p in src_dir.rglob("*") if p.is_file()
    }
    if set(extracted) != set(blobs):
        raise BootstrapError(
            "Materialized file set differs from committed tree:\n"
            f"  extra:   {sorted(set(extracted) - set(blobs))}\n"
            f"  missing: {sorted(set(blobs) - set(extracted))}"
        )
    for rel, path in sorted(extracted.items()):
        if git_blob_sha1(path.read_bytes()) != blobs[rel]:
            raise BootstrapError(f"Materialized bytes differ from committed blob: {rel}")
    for rel in REQUIRED_SOURCE_PATHS:
        if rel not in extracted:
            raise BootstrapError(f"Required source path missing: {rel}")
    pyproject = (src_dir / "pyproject.toml").read_text(encoding="utf-8")
    for needle in (
        f'name = "{DEPENDENCY_NAME}"',
        f'version = "{DEPENDENCY_VERSION}"',
        f'build-backend = "{BUILD_BACKEND}"',
    ):
        if needle not in pyproject:
            raise BootstrapError(f"pyproject.toml missing expected metadata: {needle}")
    print(
        f"Materialized {len(extracted)} files from {VCP_SOURCE_COMMIT}; "
        "all match committed blobs.\n"
    )
    return src_dir


# =============================================================================
# Isolated build environment
# =============================================================================


def env_python(env_dir):
    if os.name == "nt":
        return Path(env_dir) / "Scripts" / "python.exe"
    return Path(env_dir) / "bin" / "python"


def create_isolated_env(repo_root, env_dir, backend_paths, temp_dir):
    """Fresh venv beneath build/output/, bootstrapped from local wheels only."""
    env_dir = ensure_under_output(repo_root, env_dir)
    if env_dir.exists():
        shutil.rmtree(env_dir)
    env = subprocess_env(temp_dir=temp_dir)
    run_cmd([sys.executable, "-m", "venv", env_dir], "CREATE ISOLATED ENV", env=env)
    py = env_python(env_dir)
    run_cmd(
        [py, "-I", "-m", "pip", "install"]
        + PIP_OFFLINE_ARGS
        + [backend_paths["setuptools"], backend_paths["wheel"]],
        "INSTALL LOCAL BUILD BACKEND",
        env=env,
    )
    script = (
        "import importlib.metadata as m, sys;"
        "print(sys.version.split()[0]);"
        "print(m.version('setuptools'));"
        "print(m.version('wheel'))"
    )
    out = run_cmd([py, "-I", "-c", script], "ISOLATED ENV VERSIONS", env=env)
    py_version, st_version, wh_version = out.split()
    if tuple(int(x) for x in py_version.split(".")[:2]) != PYTHON_MAJOR_MINOR:
        raise BootstrapError(f"Isolated env Python {py_version} is not 3.14")
    if st_version != SETUPTOOLS_VERSION or wh_version != WHEEL_VERSION:
        raise BootstrapError(
            f"Backend version mismatch: setuptools={st_version} wheel={wh_version}"
        )
    return py, py_version


# =============================================================================
# Build the VCP wheel
# =============================================================================


def build_wheel(repo_root, py, src_dir, dist_dir, source_date_epoch):
    dist_dir = reset_generated_dir(repo_root, dist_dir)
    temp_dir = reset_generated_dir(repo_root, dist_dir.parent / "tmp")
    run_cmd(
        [py, "-I", "-m", "pip", "wheel"]
        + PIP_OFFLINE_ARGS
        + ["--no-build-isolation", "--wheel-dir", dist_dir, src_dir],
        "BUILD VCP WHEEL",
        env=subprocess_env(source_date_epoch=source_date_epoch, temp_dir=temp_dir),
    )
    wheels = sorted(dist_dir.glob("*.whl"))
    if [w.name for w in wheels] != [EXPECTED_WHEEL_FILENAME]:
        raise BootstrapError(f"Unexpected build output: {[w.name for w in wheels]}")
    return wheels[0]


def validate_wheel_contents(wheel_path, blobs):
    """Wheel identity and module set must match the committed source."""
    with zipfile.ZipFile(wheel_path) as zf:
        names = zf.namelist()
        dist_info = f"voyage_character_platform-{DEPENDENCY_VERSION}.dist-info"
        metadata = zf.read(f"{dist_info}/METADATA").decode("utf-8")
        wheel_meta = zf.read(f"{dist_info}/WHEEL").decode("utf-8")
    headers = dict(
        line.split(": ", 1) for line in metadata.splitlines() if ": " in line
    )
    if headers.get("Name") != DEPENDENCY_NAME or headers.get("Version") != DEPENDENCY_VERSION:
        raise BootstrapError(
            f"Wheel metadata mismatch: {headers.get('Name')} {headers.get('Version')}"
        )
    if "Root-Is-Purelib: true" not in wheel_meta:
        raise BootstrapError("Wheel is not pure Python")
    committed_modules = {
        p[len("src/"):] for p in blobs
        if p.startswith(f"src/{IMPORT_PACKAGE}/") and p.endswith(".py")
    }
    wheel_modules = {n for n in names if n.startswith(f"{IMPORT_PACKAGE}/")}
    if wheel_modules != committed_modules:
        raise BootstrapError(
            "Wheel modules differ from committed source:\n"
            f"  extra:   {sorted(wheel_modules - committed_modules)}\n"
            f"  missing: {sorted(committed_modules - wheel_modules)}"
        )
    print(f"Wheel contents verified: {len(wheel_modules)} committed modules.\n")


# =============================================================================
# Install into isolated env and smoke
# =============================================================================

SMOKE_SCRIPT = """
import importlib.metadata as md
import json
import pathlib
import sys

import voyage_character_platform as vcp
from voyage_character_platform import package_v1

dist = md.distribution("voyage-character-platform")
assert dist.metadata["Name"] == "voyage-character-platform", dist.metadata["Name"]
assert dist.version == "0.1.0", dist.version
assert callable(vcp.verify_package_v1)
assert callable(package_v1.verify_package_v1)
assert vcp.verify_package_v1 is package_v1.verify_package_v1
assert vcp.verify_package_v1.__module__ == "voyage_character_platform.package_v1"
assert "verify_package_v1" in vcp.__all__
prefix = pathlib.Path(sys.prefix).resolve()
module_file = pathlib.Path(vcp.__file__).resolve()
assert prefix in module_file.parents, module_file
assert "site-packages" in module_file.parts, module_file
direct_url = json.loads(dist.read_text("direct_url.json") or "{}")
assert not direct_url.get("dir_info", {}).get("editable", False), direct_url
assert "archive_info" in direct_url, direct_url
print("SMOKE import voyage_character_platform: PASS")
print("SMOKE distribution: %s %s" % (dist.metadata["Name"], dist.version))
print("SMOKE public verify_package_v1: PASS")
print("SMOKE module verify_package_v1: PASS")
print("SMOKE module location: <env>/" + module_file.relative_to(prefix).as_posix())
"""


def install_and_smoke(py, wheel_path, temp_dir):
    env = subprocess_env(temp_dir=temp_dir)
    run_cmd(
        [py, "-I", "-m", "pip", "install"]
        + PIP_OFFLINE_ARGS
        + ["--force-reinstall", wheel_path],
        "INSTALL VCP WHEEL INTO ISOLATED ENV",
        env=env,
    )
    run_cmd([py, "-I", "-c", SMOKE_SCRIPT], "IMPORT / PUBLIC-SYMBOL SMOKE", env=env)


# =============================================================================
# Provenance
# =============================================================================


def provenance_record(wheel_filename, wheel_sha256, python_version):
    return {
        "schema_version": PROVENANCE_SCHEMA_VERSION,
        "dependency_name": DEPENDENCY_NAME,
        "dependency_version": DEPENDENCY_VERSION,
        "source_repository": VCP_SOURCE_REPOSITORY,
        "source_commit": VCP_SOURCE_COMMIT,
        "wheel_filename": wheel_filename,
        "wheel_sha256": wheel_sha256,
        "python_version": python_version,
        "build_backend": BUILD_BACKEND,
        "build_backend_version": SETUPTOOLS_VERSION,
        "wheel_builder_version": WHEEL_VERSION,
        "backend_artifacts": {
            key: {"filename": spec["filename"], "sha256": spec["sha256"]}
            for key, spec in BACKEND_ARTIFACTS.items()
        },
        "build_recipe": build_recipe(),
        "build_command_digest": build_command_digest(),
    }


def provenance_bytes(record):
    """Deterministic UTF-8 JSON, 2-space indent, LF, trailing newline."""
    return (json.dumps(record, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def write_provenance(repo_root, record):
    path = Path(repo_root).joinpath(*PROVENANCE_RELPATH)
    path.write_bytes(provenance_bytes(record))
    print(f"Provenance written: {path.relative_to(repo_root).as_posix()}")
    return path


# =============================================================================
# Orchestration
# =============================================================================


def build_once(repo_root, py, vcp_repo, work_dir, blobs, source_date_epoch):
    src_dir = materialize_source(repo_root, vcp_repo, work_dir, blobs)
    wheel = build_wheel(repo_root, py, src_dir, work_dir / "dist", source_date_epoch)
    validate_wheel_contents(wheel, blobs)
    digest = sha256_file(wheel)
    print(f"Built {wheel.name} SHA-256: {digest}\n")
    return wheel, digest


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Offline pinned build of voyage-character-platform 0.1.0"
    )
    repo_root = lab_repo_root()
    parser.add_argument(
        "--vcp-repo",
        default=str(repo_root.parent / VCP_SOURCE_REPOSITORY),
        help="VCP Git repository (only its object database is read)",
    )
    parser.add_argument(
        "--backend-dir",
        default=None,
        help="Directory with the pinned backend wheels "
        "(default: build/output/vcp_build_backend/)",
    )
    parser.add_argument(
        "--verify-reproducibility",
        action="store_true",
        help="Build twice from separate clean materializations and compare SHA-256",
    )
    args = parser.parse_args(argv)

    if sys.version_info[:2] != PYTHON_MAJOR_MINOR:
        raise BootstrapError(f"Python 3.14 required, running {sys.version.split()[0]}")

    layout = output_layout(repo_root)
    backend_dir = Path(args.backend_dir) if args.backend_dir else layout["backend_dir"]

    print("=" * 70)
    print(f"BUILD {DEPENDENCY_NAME} {DEPENDENCY_VERSION}")
    print(f"Source commit:   {VCP_SOURCE_COMMIT}")
    print(f"Recipe digest:   {build_command_digest()}")
    print("Network:         DISABLED (--no-index)")
    print("=" * 70)
    print()

    validate_repo_root(repo_root)
    backend_paths = verify_backend_artifacts(backend_dir)
    source_date_epoch = verify_vcp_commit(args.vcp_repo)
    blobs = committed_blobs(args.vcp_repo)

    shared_dir = reset_generated_dir(repo_root, layout["shared_core_dir"])
    temp_dir = reset_generated_dir(repo_root, shared_dir / "tmp")
    py, python_version = create_isolated_env(
        repo_root, layout["env_dir"], backend_paths, temp_dir
    )

    wheel, digest = build_once(
        repo_root, py, args.vcp_repo, shared_dir / "work" / "build_1", blobs, source_date_epoch
    )
    reproducible = "NOT_PROVEN"
    if args.verify_reproducibility:
        _, digest_2 = build_once(
            repo_root, py, args.vcp_repo, shared_dir / "work" / "build_2", blobs, source_date_epoch
        )
        reproducible = "YES" if digest_2 == digest else "NO"
        print(f"Second build SHA-256: {digest_2}")

    final_wheel = ensure_under_output(repo_root, layout["wheel_path"])
    shutil.copyfile(wheel, final_wheel)
    if sha256_file(final_wheel) != digest:
        raise BootstrapError("Copied wheel hash mismatch")

    install_and_smoke(py, final_wheel, temp_dir)
    write_provenance(repo_root, provenance_record(final_wheel.name, digest, python_version))

    print()
    print(f"WHEEL:              {final_wheel.relative_to(repo_root).as_posix()}")
    print(f"WHEEL_SHA256:       {digest}")
    print(f"REPRODUCIBLE_WHEEL: {reproducible}")
    print("\nDONE.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BootstrapError as exc:
        sys.exit(f"BOOTSTRAP FAILED (fail closed): {exc}")
