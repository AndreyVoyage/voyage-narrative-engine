#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Slice 0 contract tests for tools/cis_pilot/source_loader.py.

These tests load the real, frozen ``personas/kira`` and ``scenarios/``
source (read-only) and confirm it matches the values fixed by
``CIS_KIRA_PILOT_SPECIFICATION_v0.1_2026-08-05.md`` and the Slice 0
authorization. No network, no LLM, no ``local_runs/`` output, and no
mutation of any source file -- verified explicitly below via
git-status-before/after and hash-before/after checks.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.cis_pilot.contracts import ALLOWED_P4_STATES, SourceArtifact
from tools.cis_pilot.source_loader import (
    CHARACTER_ID,
    FROZEN_SOURCE_BASELINE_SHA,
    ME1_EVENT_ID,
    ME1_EXPECTED_LITERAL_TEXT,
    ME1_JSON_PATH,
    ME1_NORMALIZED_TEXT,
    ME2_EVENT_ID,
    ME2_EXPECTED_FIRST_SENTENCE,
    ME2_JSON_PATH,
    PROTECTED_SOURCE_RELATIVE_PATHS,
    load_pilot_source_snapshot,
)

# The exact set of read-only source files Slice 0 touches. Hashed before
# and after the full loader run to prove the loader never mutates them.
_CRITICAL_SOURCES = (
    "personas/kira/psychology/VALUE_SYSTEM.json",
    "personas/kira/psychology/BASE.json",
    "personas/kira/psychology/ATTACHMENT.json",
    "personas/kira/psychology/DEFENSE_MECHANISMS.json",
    "personas/kira/psychology/IFS_PARTS.json",
    "personas/kira/psychology/ODSC.json",
    "personas/kira/psychology/ATTACHMENT_STYLE_DYNAMIC.json",
    "personas/kira/relationships/MATRIX.json",
    "personas/kira/psychology/AFFECT_REGULATION.json",
    "personas/kira/core/IDENTITY.json",
    "personas/kira/speech/SPEECH_MATRIX.json",
    "scenarios/SCENARIO_008_HOME_EMBRACE.json",
    "scenarios/SCENARIO_017_SERGEY_WRITES_AGAIN.v2.json",
    "tools/aside_context_builder.py",
)


def _hash_all(paths: tuple) -> dict:
    return {p: hashlib.sha256((_REPO_ROOT / p).read_bytes()).hexdigest() for p in paths}


def _git_status_for_paths(paths: list) -> str:
    result = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all", "--", *paths],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=10,
        shell=False,
    )
    assert result.returncode == 0, f"git status failed: {result.stderr}"
    return result.stdout


@pytest.fixture(scope="module")
def snapshot():
    """Load the real Slice 0 pilot source snapshot once per test module."""
    return load_pilot_source_snapshot(_REPO_ROOT)


# ---------------------------------------------------------------------------
# No-mutation guarantees (checked once, independently of `snapshot` fixture
# so a failure here is never masked by fixture caching)
# ---------------------------------------------------------------------------


def test_loader_does_not_modify_tracked_sources_git_status():
    before = _git_status_for_paths(["personas/kira", "scenarios"])
    assert before == "", f"worktree not clean before loader run: {before!r}"
    load_pilot_source_snapshot(_REPO_ROOT)
    after = _git_status_for_paths(["personas/kira", "scenarios"])
    assert after == "", f"loader modified tracked sources: {after!r}"


def test_loader_source_hashes_unchanged_before_and_after():
    before = _hash_all(_CRITICAL_SOURCES)
    load_pilot_source_snapshot(_REPO_ROOT)
    after = _hash_all(_CRITICAL_SOURCES)
    assert before == after


def test_loader_creates_no_local_runs_directory():
    load_pilot_source_snapshot(_REPO_ROOT)
    assert not (_REPO_ROOT / "local_runs" / "cis_pilot").exists()
    assert not (_REPO_ROOT / "local_runs").exists()


def test_loader_creates_no_new_untracked_files_anywhere():
    before = _git_status_for_paths(["."])
    load_pilot_source_snapshot(_REPO_ROOT)
    after = _git_status_for_paths(["."])
    assert before == after


# ---------------------------------------------------------------------------
# P0
# ---------------------------------------------------------------------------


def test_p0_all_six_modules_loaded(snapshot):
    for artifact in (
        snapshot.p0.value_system,
        snapshot.p0.base,
        snapshot.p0.attachment,
        snapshot.p0.defense_mechanisms,
        snapshot.p0.ifs_parts,
        snapshot.p0.odsc,
    ):
        assert isinstance(artifact, SourceArtifact)
        assert len(artifact.sha256) == 64


def test_p0_value_system_path_and_hash(snapshot):
    artifact = snapshot.p0.value_system
    assert artifact.repo_relative_path == "personas/kira/psychology/VALUE_SYSTEM.json"
    expected = hashlib.sha256(
        (_REPO_ROOT / "personas/kira/psychology/VALUE_SYSTEM.json").read_bytes()
    ).hexdigest()
    assert artifact.sha256 == expected


def test_p0_base_path_and_hash(snapshot):
    artifact = snapshot.p0.base
    assert artifact.repo_relative_path == "personas/kira/psychology/BASE.json"
    expected = hashlib.sha256((_REPO_ROOT / "personas/kira/psychology/BASE.json").read_bytes()).hexdigest()
    assert artifact.sha256 == expected


def test_p0_load_fails_closed_when_core_values_missing(tmp_path, monkeypatch):
    # Structural drift check: VALUE_SYSTEM.json without 'core_values' must
    # fail closed, not silently produce a snapshot missing the key.
    import json

    from services.persona_gateway import PersonaCatalog
    from tools.cis_pilot import source_loader

    persona_root = tmp_path / "personas" / "kira"
    for module_id in source_loader.P0_MODULE_IDS.values():
        target = persona_root / module_id
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({"module_id": "X"}), encoding="utf-8")
    index = {
        "id": "kira",
        "name": "Кира",
        "modules": {mid: {} for mid in source_loader.P0_MODULE_IDS.values()},
    }
    (persona_root / "INDEX.json").write_text(json.dumps(index), encoding="utf-8")

    catalog = PersonaCatalog(entries={"kira": persona_root})
    with pytest.raises(source_loader.SourceLoaderError):
        source_loader._load_p0_snapshot(catalog)


def test_attachment_style_dynamic_excluded_from_p0(snapshot):
    field_names = {f.name for f in __import__("dataclasses").fields(snapshot.p0)}
    assert "attachment_style_dynamic" not in field_names


def test_attachment_style_dynamic_still_confirmed_to_exist():
    from services.persona_gateway import PersonaCatalog
    from tools.cis_pilot import source_loader

    catalog = PersonaCatalog(entries={CHARACTER_ID: _REPO_ROOT / "personas" / "kira"})
    # Must not raise -- confirms existence/structure without ever exposing
    # it through PilotSourceSnapshot.
    source_loader._confirm_attachment_style_dynamic_excluded(catalog)


# ---------------------------------------------------------------------------
# P3
# ---------------------------------------------------------------------------


def test_p3_trust_and_attraction(snapshot):
    assert snapshot.p3.trust == 75
    assert snapshot.p3.attraction == 85


def test_p3_state_has_no_forbidden_fields(snapshot):
    field_names = {f.name for f in __import__("dataclasses").fields(snapshot.p3)}
    assert field_names == {"trust", "attraction"}


# ---------------------------------------------------------------------------
# P4
# ---------------------------------------------------------------------------


def test_p4_all_four_strategy_states_present(snapshot):
    assert set(snapshot.p4_strategy_map.keys()) == {
        "high_arousal_low_anxiety",
        "high_arousal_high_anxiety",
        "low_arousal_high_anxiety",
        "low_arousal_low_anxiety",
    }


def test_p4_strategy_mapping_matches_spec(snapshot):
    expected = {
        "high_arousal_low_anxiety": ("high", "low", "approach"),
        "high_arousal_high_anxiety": ("high", "high", "avoidance"),
        "low_arousal_high_anxiety": ("low", "high", "seeking_reassurance"),
        "low_arousal_low_anxiety": ("low", "low", "exploration"),
    }
    for key, (arousal, anxiety, strategy) in expected.items():
        state = snapshot.p4_strategy_map[key]
        assert state.arousal == arousal
        assert state.anxiety == anxiety
        assert state.strategy == strategy
        assert ALLOWED_P4_STATES[(arousal, anxiety)] == strategy


# ---------------------------------------------------------------------------
# ME-1 / ME-2
# ---------------------------------------------------------------------------


def test_me1_exact_json_path_and_event_id(snapshot):
    assert snapshot.me1.event_id == ME1_EVENT_ID == "SC_008"
    assert snapshot.me1.json_path == ME1_JSON_PATH == "choice_points[0].branches[0].action"
    assert snapshot.me1.scenario_repo_relative_path == "scenarios/SCENARIO_008_HOME_EMBRACE.json"


def test_me1_literal_text_matches_spec(snapshot):
    assert snapshot.me1.literal_text == ME1_EXPECTED_LITERAL_TEXT
    assert snapshot.me1.literal_text == "Падает ему на грудь. Плачет. Не объясняет."


def test_me1_normalized_fixture_matches_spec(snapshot):
    assert snapshot.me1.normalized_text == ME1_NORMALIZED_TEXT
    assert snapshot.me1.normalized_text == "Кира падает ему на грудь. Плачет. Не объясняет."
    # Normalization only prepends an explicit subject and lower-cases the
    # verb's leading letter; the rest of the sentence is unchanged, and
    # literal_text (stored separately) is untouched by normalization.
    assert snapshot.me1.literal_text == "Падает ему на грудь. Плачет. Не объясняет."
    assert snapshot.me1.normalized_text != snapshot.me1.literal_text
    assert snapshot.me1.normalized_text.endswith("падает ему на грудь. Плачет. Не объясняет.")


def test_me2_exact_json_path_and_event_id(snapshot):
    assert snapshot.me2.event_id == ME2_EVENT_ID == "SC_017"
    assert snapshot.me2.json_path == ME2_JSON_PATH == "entry_beats[0].narration"
    assert snapshot.me2.scenario_repo_relative_path == "scenarios/SCENARIO_017_SERGEY_WRITES_AGAIN.v2.json"


def test_me2_literal_text_is_confirmed_first_sentence_only(snapshot):
    assert snapshot.me2.literal_text == ME2_EXPECTED_FIRST_SENTENCE
    assert snapshot.me2.literal_text == "Телефон загорается новым сообщением от Сергея."
    # The real source narration has a second sentence -- fixture must not
    # include it.
    assert "Яков" not in snapshot.me2.literal_text


def test_me1_and_me2_source_hashes_present(snapshot):
    assert len(snapshot.me1.sha256) == 64
    assert len(snapshot.me2.sha256) == 64


# ---------------------------------------------------------------------------
# Baseline (PD-10)
# ---------------------------------------------------------------------------


def test_baseline_four_source_files_present(snapshot):
    assert snapshot.baseline.identity.repo_relative_path == "personas/kira/core/IDENTITY.json"
    assert snapshot.baseline.base.repo_relative_path == "personas/kira/psychology/BASE.json"
    assert snapshot.baseline.speech_matrix.repo_relative_path == "personas/kira/speech/SPEECH_MATRIX.json"
    assert snapshot.baseline.matrix.repo_relative_path == "personas/kira/relationships/MATRIX.json"


def test_baseline_builder_source_artifact(snapshot):
    artifact = snapshot.baseline.builder_source
    assert artifact.repo_relative_path == "tools/aside_context_builder.py"
    expected = hashlib.sha256((_REPO_ROOT / "tools" / "aside_context_builder.py").read_bytes()).hexdigest()
    assert artifact.sha256 == expected


def test_baseline_git_sha_matches_frozen_source_baseline(snapshot):
    # baseline_git_sha records the PD-10 freeze anchor commit, not whatever
    # HEAD happens to be at load time (see repo-HEAD-provenance section
    # below for that distinction).
    assert snapshot.baseline.baseline_git_sha == FROZEN_SOURCE_BASELINE_SHA


# ---------------------------------------------------------------------------
# Repo HEAD provenance (HEAD is captured, never used as a load-blocking gate)
# ---------------------------------------------------------------------------


def test_repo_head_matches_independent_git_rev_parse(snapshot):
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=10,
        shell=False,
    )
    assert result.returncode == 0
    assert snapshot.repo_head_sha == result.stdout.strip()


def test_head_advancement_past_frozen_baseline_does_not_block_loading(snapshot):
    # This is the exact regression case this correction fixes: a routine,
    # authorized commit (Slice 0's own commit, then Slice 1's uncommitted
    # work) has advanced HEAD past FROZEN_SOURCE_BASELINE_SHA. The loader
    # must still succeed (the `snapshot` fixture above already proves this
    # by not raising) and must still report the real current HEAD as
    # provenance, distinct from the frozen baseline anchor.
    assert snapshot.repo_head_sha != FROZEN_SOURCE_BASELINE_SHA


# ---------------------------------------------------------------------------
# Frozen source baseline invariant (protected source CONTENT, not HEAD)
# ---------------------------------------------------------------------------


def test_protected_source_paths_match_independently_maintained_critical_sources():
    # Cross-check: the production protected-source list (derived from the
    # loader's own module-id constants) must cover exactly the same 14
    # sources this test file independently hard-codes and hashes.
    assert set(PROTECTED_SOURCE_RELATIVE_PATHS) == set(_CRITICAL_SOURCES)
    assert len(PROTECTED_SOURCE_RELATIVE_PATHS) == 14


def test_verify_frozen_source_invariant_passes_for_the_real_unmodified_repo():
    from tools.cis_pilot import source_loader

    source_loader._verify_frozen_source_invariant(_REPO_ROOT)  # must not raise


def test_frozen_blob_git_sha_matches_working_tree_blob_sha_for_real_repo():
    # The real file has not drifted from the frozen baseline commit, so
    # Git's own blob ids match -- even though this repo has
    # core.autocrlf=true, which means the raw checked-out working-tree
    # bytes (CRLF) legitimately differ from the raw committed blob bytes
    # (LF). Comparing Git's own blob ids (both sides computed by Git,
    # respecting the same normalization) is what makes this comparison
    # correct across that platform-normalization difference.
    from tools.cis_pilot import source_loader

    relative_path = "personas/kira/psychology/VALUE_SYSTEM.json"
    frozen_sha = source_loader._frozen_blob_git_sha(
        _REPO_ROOT, FROZEN_SOURCE_BASELINE_SHA, relative_path
    )
    working_sha = source_loader._working_tree_blob_git_sha(_REPO_ROOT, relative_path)
    assert len(frozen_sha) == 40
    assert len(working_sha) == 40
    assert frozen_sha == working_sha


def test_frozen_blob_git_sha_missing_path_fails_closed():
    from tools.cis_pilot import source_loader

    with pytest.raises(source_loader.SourceLoaderError):
        source_loader._frozen_blob_git_sha(
            _REPO_ROOT, FROZEN_SOURCE_BASELINE_SHA, "personas/kira/DOES_NOT_EXIST_AT_ALL.json"
        )


def test_frozen_blob_git_sha_unknown_commit_fails_closed():
    from tools.cis_pilot import source_loader

    with pytest.raises(source_loader.SourceLoaderError):
        source_loader._frozen_blob_git_sha(
            _REPO_ROOT, "0" * 40, "personas/kira/psychology/VALUE_SYSTEM.json"
        )


def test_frozen_blob_git_sha_subprocess_error_fails_closed(monkeypatch):
    from tools.cis_pilot import source_loader

    def _raise(*args, **kwargs):
        raise OSError("git executable not found")

    monkeypatch.setattr(source_loader.subprocess, "run", _raise)
    with pytest.raises(source_loader.SourceLoaderError):
        source_loader._frozen_blob_git_sha(
            _REPO_ROOT, FROZEN_SOURCE_BASELINE_SHA, "personas/kira/psychology/VALUE_SYSTEM.json"
        )


def test_working_tree_blob_git_sha_missing_file_fails_closed():
    from tools.cis_pilot import source_loader

    with pytest.raises(source_loader.SourceLoaderError):
        source_loader._working_tree_blob_git_sha(_REPO_ROOT, "personas/kira/DOES_NOT_EXIST_AT_ALL.json")


def test_working_tree_blob_git_sha_subprocess_error_fails_closed(monkeypatch):
    from tools.cis_pilot import source_loader

    def _raise(*args, **kwargs):
        raise OSError("git executable not found")

    monkeypatch.setattr(source_loader.subprocess, "run", _raise)
    with pytest.raises(source_loader.SourceLoaderError):
        source_loader._working_tree_blob_git_sha(
            _REPO_ROOT, "personas/kira/psychology/VALUE_SYSTEM.json"
        )


def test_missing_protected_source_fails_closed(tmp_path, monkeypatch):
    # tmp_path only -- never the real repo (per instruction: do not mutate
    # real personas/kira source for this test).
    from tools.cis_pilot import source_loader

    fake_relative_path = "personas/kira/psychology/DOES_NOT_EXIST.json"
    monkeypatch.setattr(source_loader, "PROTECTED_SOURCE_RELATIVE_PATHS", (fake_relative_path,))
    with pytest.raises(source_loader.SourceLoaderError):
        source_loader._verify_frozen_source_invariant(tmp_path)


def test_protected_source_content_drift_fails_closed(tmp_path, monkeypatch):
    # tmp_path + monkeypatch only -- never the real repo. Simulates a
    # protected source whose current Git blob id differs from its frozen
    # blob id (i.e. genuine content drift, not a line-ending artifact).
    from tools.cis_pilot import source_loader

    fake_relative_path = "personas/kira/psychology/VALUE_SYSTEM.json"
    current_file = tmp_path / fake_relative_path
    current_file.parent.mkdir(parents=True, exist_ok=True)
    current_file.write_bytes(b'{"drifted": true}')

    monkeypatch.setattr(source_loader, "PROTECTED_SOURCE_RELATIVE_PATHS", (fake_relative_path,))
    monkeypatch.setattr(
        source_loader, "_working_tree_blob_git_sha", lambda repo_root, relative_path: "a" * 40
    )
    monkeypatch.setattr(
        source_loader,
        "_frozen_blob_git_sha",
        lambda repo_root, frozen_sha, relative_path: "b" * 40,
    )

    with pytest.raises(source_loader.SourceLoaderError):
        source_loader._verify_frozen_source_invariant(tmp_path)


def test_protected_source_identical_content_passes(tmp_path, monkeypatch):
    # The mirror-image positive case for the drift test above: identical
    # current/frozen Git blob ids must not raise.
    from tools.cis_pilot import source_loader

    fake_relative_path = "personas/kira/psychology/VALUE_SYSTEM.json"
    current_file = tmp_path / fake_relative_path
    current_file.parent.mkdir(parents=True, exist_ok=True)
    current_file.write_bytes(b'{"same": true}')

    monkeypatch.setattr(source_loader, "PROTECTED_SOURCE_RELATIVE_PATHS", (fake_relative_path,))
    same_sha = "c" * 40
    monkeypatch.setattr(
        source_loader, "_working_tree_blob_git_sha", lambda repo_root, relative_path: same_sha
    )
    monkeypatch.setattr(
        source_loader,
        "_frozen_blob_git_sha",
        lambda repo_root, frozen_sha, relative_path: same_sha,
    )

    source_loader._verify_frozen_source_invariant(tmp_path)  # must not raise
