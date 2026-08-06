#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Slice 0 unit tests for tools/cis_pilot/provenance.py.

No network, no LLM. All test fixtures live under pytest's ``tmp_path`` --
never inside the real repository.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.cis_pilot.provenance import (
    ProvenanceError,
    build_source_artifact,
    get_head_sha,
    sha256_file,
    to_repo_relative_posix,
)


# ---------------------------------------------------------------------------
# sha256_file
# ---------------------------------------------------------------------------


def test_sha256_file_matches_hashlib(tmp_path: Path):
    target = tmp_path / "sample.txt"
    target.write_bytes(b"hello world")
    assert sha256_file(target) == hashlib.sha256(b"hello world").hexdigest()


def test_sha256_file_is_stable_across_calls(tmp_path: Path):
    target = tmp_path / "sample.txt"
    target.write_bytes(b"stable content")
    assert sha256_file(target) == sha256_file(target)


def test_sha256_file_changes_when_bytes_change(tmp_path: Path):
    target = tmp_path / "sample.txt"
    target.write_bytes(b"version one")
    digest_one = sha256_file(target)
    target.write_bytes(b"version two")
    digest_two = sha256_file(target)
    assert digest_one != digest_two


def test_sha256_file_does_not_modify_source(tmp_path: Path):
    target = tmp_path / "sample.txt"
    original = b"do not touch me"
    target.write_bytes(original)
    before_mtime = target.stat().st_mtime_ns
    sha256_file(target)
    assert target.read_bytes() == original
    assert target.stat().st_mtime_ns == before_mtime


def test_sha256_file_rejects_missing_file(tmp_path: Path):
    with pytest.raises(ProvenanceError):
        sha256_file(tmp_path / "does_not_exist.txt")


def test_sha256_file_rejects_directory(tmp_path: Path):
    directory = tmp_path / "a_directory"
    directory.mkdir()
    with pytest.raises(ProvenanceError):
        sha256_file(directory)


# ---------------------------------------------------------------------------
# to_repo_relative_posix
# ---------------------------------------------------------------------------


def test_to_repo_relative_posix_normalizes_nested_path(tmp_path: Path):
    repo_root = tmp_path / "repo"
    nested = repo_root / "a" / "b" / "c.json"
    nested.parent.mkdir(parents=True)
    nested.write_text("{}", encoding="utf-8")
    result = to_repo_relative_posix(nested, repo_root)
    assert result == "a/b/c.json"
    assert "\\" not in result


def test_to_repo_relative_posix_rejects_external_absolute_path(tmp_path: Path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    outside = tmp_path / "outside" / "secret.txt"
    outside.parent.mkdir(parents=True)
    outside.write_text("secret", encoding="utf-8")
    with pytest.raises(ProvenanceError):
        to_repo_relative_posix(outside, repo_root)


def test_to_repo_relative_posix_rejects_traversal_escape(tmp_path: Path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (tmp_path / "sibling.txt").write_text("x", encoding="utf-8")
    with pytest.raises(ProvenanceError):
        to_repo_relative_posix(repo_root / ".." / "sibling.txt", repo_root)


def test_to_repo_relative_posix_rejects_symlinked_directory_component(tmp_path: Path):
    repo_root = tmp_path / "repo"
    real_dir = tmp_path / "real_target"
    real_dir.mkdir(parents=True)
    (real_dir / "file.json").write_text("{}", encoding="utf-8")
    repo_root.mkdir()
    link = repo_root / "linked"
    try:
        link.symlink_to(real_dir, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation not permitted in this environment")
    with pytest.raises(ProvenanceError):
        to_repo_relative_posix(link / "file.json", repo_root)


def test_to_repo_relative_posix_rejects_nonexistent_repo_root(tmp_path: Path):
    with pytest.raises(ProvenanceError):
        to_repo_relative_posix(tmp_path / "missing_repo" / "x.json", tmp_path / "missing_repo")


# ---------------------------------------------------------------------------
# get_head_sha
# ---------------------------------------------------------------------------


def test_get_head_sha_on_non_git_directory_raises(tmp_path: Path):
    not_a_repo = tmp_path / "not_a_repo"
    not_a_repo.mkdir()
    with pytest.raises(ProvenanceError):
        get_head_sha(not_a_repo, timeout_s=5.0)


def test_get_head_sha_on_real_repo_returns_valid_sha():
    sha = get_head_sha(_REPO_ROOT)
    assert len(sha) == 40
    assert all(c in "0123456789abcdef" for c in sha)


def test_get_head_sha_is_stable_across_calls():
    assert get_head_sha(_REPO_ROOT) == get_head_sha(_REPO_ROOT)


# ---------------------------------------------------------------------------
# build_source_artifact
# ---------------------------------------------------------------------------


def test_build_source_artifact_contains_matching_sha256(tmp_path: Path):
    repo_root = tmp_path / "repo"
    target = repo_root / "tools" / "example.py"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"# example\n")
    artifact = build_source_artifact(repo_root, "tools/example.py", kind="builder_source")
    assert artifact.sha256 == hashlib.sha256(b"# example\n").hexdigest()
    assert artifact.repo_relative_path == "tools/example.py"
    assert artifact.kind == "builder_source"


def test_build_source_artifact_carries_optional_fields(tmp_path: Path):
    repo_root = tmp_path / "repo"
    target = repo_root / "scenarios" / "SCENARIO_TEST.json"
    target.parent.mkdir(parents=True)
    target.write_text("{}", encoding="utf-8")
    artifact = build_source_artifact(
        repo_root,
        "scenarios/SCENARIO_TEST.json",
        kind="memory_fixture",
        json_path="entry_beats[0].narration",
        module_id=None,
    )
    assert artifact.json_path == "entry_beats[0].narration"
    assert artifact.module_id is None


def test_build_source_artifact_does_not_modify_source(tmp_path: Path):
    repo_root = tmp_path / "repo"
    target = repo_root / "tools" / "example.py"
    target.parent.mkdir(parents=True)
    original = b"# untouched\n"
    target.write_bytes(original)
    build_source_artifact(repo_root, "tools/example.py", kind="builder_source")
    assert target.read_bytes() == original


def test_build_source_artifact_rejects_traversal(tmp_path: Path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (tmp_path / "outside.py").write_bytes(b"x")
    with pytest.raises(ProvenanceError):
        build_source_artifact(repo_root, "../outside.py", kind="builder_source")


def test_build_source_artifact_rejects_missing_file(tmp_path: Path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    with pytest.raises(ProvenanceError):
        build_source_artifact(repo_root, "tools/missing.py", kind="builder_source")
