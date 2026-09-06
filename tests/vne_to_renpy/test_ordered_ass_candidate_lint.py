#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Focused tests for the OrderedASS candidate lint helper (temp-copy)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.vne_to_renpy import (  # noqa: E402
    ORDERED_ASS_CANDIDATE_FILENAME,
    CandidateLintResult,
    OrderedCandidateLintError,
    OrderedProjectCandidate,
    lint_ordered_ass_candidate,
)


def _candidate(source: str = "# fake source\n") -> OrderedProjectCandidate:
    return OrderedProjectCandidate(
        source=source,
        source_sha256="0" * 64,
        scene_ids=("SC_900",),
        ass_ids=("ass_900",),
        reading_mode="classic_vn",
        candidate_filename=ORDERED_ASS_CANDIDATE_FILENAME,
    )


def _make_source_project(tmp_path: Path) -> Path:
    novel = tmp_path / "novel"
    game = novel / "game"
    game.mkdir(parents=True)
    (game / "script.rpy").write_text("label start:\n    return\n", encoding="utf-8")
    (game / "scenes_v2_generated.rpy").write_text(
        "label sc_017_v2_start:\n    return\n", encoding="utf-8"
    )
    (game / "definitions.rpy").write_text("define e = Character('E')\n", encoding="utf-8")
    img_dir = game / "images" / "story"
    img_dir.mkdir(parents=True)
    (img_dir / "asset.png").write_bytes(b"fake-image")
    return novel


@pytest.fixture
def sdk_command(monkeypatch):
    def fake(sdk):
        return (Path("python.exe"), Path("renpy.py"))

    monkeypatch.setattr(
        "tools.vne_to_renpy.ordered_ass_candidate_lint.find_renpy_command", fake
    )
    return fake


@pytest.fixture
def run_record(monkeypatch):
    records = {"commands": [], "envs": [], "returncode": 0, "temp_files": []}

    def fake(cmd, **kwargs):
        records["commands"].append(cmd)
        records["envs"].append(kwargs.get("env", {}))
        temp_novel = Path(cmd[2])
        files = {
            p.relative_to(temp_novel).as_posix()
            for p in temp_novel.rglob("*")
            if p.is_file()
        }
        records["temp_files"].append(files)
        return subprocess.CompletedProcess(
            cmd, records["returncode"], stdout="ok", stderr=""
        )

    monkeypatch.setattr(subprocess, "run", fake)
    return records


@pytest.fixture
def copytree_record(monkeypatch):
    real = shutil.copytree
    records: list[Path] = []

    def wrapped(src, dst, *args, **kwargs):
        # record only the top-level copy (the first call); recursive copies skip
        if not records:
            records.append(Path(dst))
        return real(src, dst, *args, **kwargs)

    monkeypatch.setattr(shutil, "copytree", wrapped)
    return records


# ---------------------------------------------------------------------------
# Path / input validation
# ---------------------------------------------------------------------------

def test_source_novel_path_must_be_absolute(tmp_path, sdk_command):
    with pytest.raises(OrderedCandidateLintError):
        lint_ordered_ass_candidate(
            _candidate(),
            source_novel_path=Path("relative/novel"),
            sdk_path=Path("/abs/sdk"),
        )


def test_sdk_path_must_be_absolute(tmp_path, sdk_command):
    source = _make_source_project(tmp_path)
    with pytest.raises(OrderedCandidateLintError):
        lint_ordered_ass_candidate(
            _candidate(),
            source_novel_path=source,
            sdk_path=Path("relative/sdk"),
        )


def test_missing_source_project_rejected(tmp_path, sdk_command):
    with pytest.raises(OrderedCandidateLintError):
        lint_ordered_ass_candidate(
            _candidate(),
            source_novel_path=tmp_path / "does_not_exist",
            sdk_path=tmp_path,
        )


def test_missing_sdk_rejected(tmp_path, sdk_command):
    source = _make_source_project(tmp_path)
    with pytest.raises(OrderedCandidateLintError):
        lint_ordered_ass_candidate(
            _candidate(),
            source_novel_path=source,
            sdk_path=tmp_path / "no_sdk",
        )


def test_reserved_candidate_exists_in_source_rejected(tmp_path, sdk_command):
    source = _make_source_project(tmp_path)
    (source / "game" / ORDERED_ASS_CANDIDATE_FILENAME).write_text("x", encoding="utf-8")
    with pytest.raises(OrderedCandidateLintError):
        lint_ordered_ass_candidate(
            _candidate(),
            source_novel_path=source,
            sdk_path=tmp_path,
        )


# ---------------------------------------------------------------------------
# Temp construction / injection
# ---------------------------------------------------------------------------

def test_success_returns_passed_result(tmp_path, sdk_command, run_record, copytree_record):
    source = _make_source_project(tmp_path)
    result = lint_ordered_ass_candidate(
        _candidate("# candidate\n"),
        source_novel_path=source,
        sdk_path=tmp_path,
    )
    assert isinstance(result, CandidateLintResult)
    assert result.passed is True
    assert result.temp_cleaned is True
    assert result.returncode == 0
    assert result.candidate_filename == ORDERED_ASS_CANDIDATE_FILENAME
    assert result.stdout == "ok"


def test_candidate_written_only_inside_temp(tmp_path, sdk_command, run_record, copytree_record):
    source = _make_source_project(tmp_path)
    lint_ordered_ass_candidate(
        _candidate("# candidate\n"),
        source_novel_path=source,
        sdk_path=tmp_path,
    )
    temp_files = run_record["temp_files"][0]
    assert "game/{}".format(ORDERED_ASS_CANDIDATE_FILENAME) in temp_files
    assert not (source / "game" / ORDERED_ASS_CANDIDATE_FILENAME).exists()


def test_existing_v2_and_images_retained_in_temp(tmp_path, sdk_command, run_record, copytree_record):
    source = _make_source_project(tmp_path)
    lint_ordered_ass_candidate(
        _candidate("# candidate\n"),
        source_novel_path=source,
        sdk_path=tmp_path,
    )
    temp_files = run_record["temp_files"][0]
    assert "game/scenes_v2_generated.rpy" in temp_files
    assert "game/images/story/asset.png" in temp_files


def test_sdk_command_uses_temp_novel_path(tmp_path, sdk_command, run_record, copytree_record):
    source = _make_source_project(tmp_path)
    lint_ordered_ass_candidate(
        _candidate("# candidate\n"),
        source_novel_path=source,
        sdk_path=tmp_path,
    )
    cmd = run_record["commands"][0]
    assert cmd[-2:] == ["lint", "--error-code"]
    assert copytree_record[0] == Path(cmd[2])


def test_dummy_sdl_and_temp_save_env(tmp_path, sdk_command, run_record, copytree_record):
    source = _make_source_project(tmp_path)
    lint_ordered_ass_candidate(
        _candidate("# candidate\n"),
        source_novel_path=source,
        sdk_path=tmp_path,
    )
    env = run_record["envs"][0]
    assert env["SDL_VIDEODRIVER"] == "dummy"
    assert env["SDL_AUDIODRIVER"] == "dummy"
    assert "RENPY_PATH_TO_SAVES" in env


def test_temp_cleanup_after_pass(tmp_path, sdk_command, run_record, copytree_record):
    source = _make_source_project(tmp_path)
    lint_ordered_ass_candidate(
        _candidate("# candidate\n"),
        source_novel_path=source,
        sdk_path=tmp_path,
    )
    temp_novel = copytree_record[0]
    assert not temp_novel.exists()
    assert not temp_novel.parent.exists()


def test_source_project_unchanged(tmp_path, sdk_command, run_record, copytree_record):
    source = _make_source_project(tmp_path)
    before = {p.relative_to(source): p.read_bytes() for p in source.rglob("*") if p.is_file()}
    lint_ordered_ass_candidate(
        _candidate("# candidate\n"),
        source_novel_path=source,
        sdk_path=tmp_path,
    )
    after = {p.relative_to(source): p.read_bytes() for p in source.rglob("*") if p.is_file()}
    assert before == after


# ---------------------------------------------------------------------------
# Failure / cleanup paths
# ---------------------------------------------------------------------------

def test_nonzero_lint_raises_with_failed_result(tmp_path, sdk_command, run_record, copytree_record):
    run_record["returncode"] = 1
    source = _make_source_project(tmp_path)
    with pytest.raises(OrderedCandidateLintError) as excinfo:
        lint_ordered_ass_candidate(
            _candidate("# candidate\n"),
            source_novel_path=source,
            sdk_path=tmp_path,
        )
    assert excinfo.value.result is not None
    assert excinfo.value.result.passed is False
    assert excinfo.value.result.returncode == 1
    assert excinfo.value.result.temp_cleaned is True
    # temp cleaned even on failure
    temp_novel = copytree_record[0]
    assert not temp_novel.exists()


def test_subprocess_start_failure_surfaced(tmp_path, sdk_command, monkeypatch):
    def fake_run(cmd, **kwargs):
        raise OSError("cannot start")

    monkeypatch.setattr(subprocess, "run", fake_run)
    source = _make_source_project(tmp_path)
    with pytest.raises(OrderedCandidateLintError):
        lint_ordered_ass_candidate(
            _candidate("# candidate\n"),
            source_novel_path=source,
            sdk_path=tmp_path,
        )


def test_timeout_surfaced(tmp_path, sdk_command, monkeypatch):
    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, 1)

    monkeypatch.setattr(subprocess, "run", fake_run)
    source = _make_source_project(tmp_path)
    with pytest.raises(OrderedCandidateLintError):
        lint_ordered_ass_candidate(
            _candidate("# candidate\n"),
            source_novel_path=source,
            sdk_path=tmp_path,
            timeout_seconds=1,
        )


def test_copy_failure_surfaced(tmp_path, sdk_command, monkeypatch):
    def fake_copytree(src, dst, **kwargs):
        raise OSError("copy failed")

    monkeypatch.setattr(shutil, "copytree", fake_copytree)
    source = _make_source_project(tmp_path)
    with pytest.raises(OrderedCandidateLintError):
        lint_ordered_ass_candidate(
            _candidate("# candidate\n"),
            source_novel_path=source,
            sdk_path=tmp_path,
        )


def test_sdk_command_missing_surfaced(tmp_path, monkeypatch):
    def fake_find(sdk):
        return None

    monkeypatch.setattr(
        "tools.vne_to_renpy.ordered_ass_candidate_lint.find_renpy_command", fake_find
    )
    source = _make_source_project(tmp_path)
    with pytest.raises(OrderedCandidateLintError):
        lint_ordered_ass_candidate(
            _candidate("# candidate\n"),
            source_novel_path=source,
            sdk_path=tmp_path,
        )


# ---------------------------------------------------------------------------
# Actual local Ren'Py SDK proof (authorized single run; test-harness env only)
# ---------------------------------------------------------------------------

def test_actual_sdk_integration():
    sdk_raw = os.environ.get("VNE_TEST_RENPY_SDK_PATH")
    if not sdk_raw:
        pytest.skip("VNE_TEST_RENPY_SDK_PATH not set")
    sdk_path = Path(sdk_raw)

    from services.ass import build_ordered_ass
    from services.scene_body import (
        AUTHORING_SCHEMA_VERSION,
        ChoiceEntry,
        ChoiceOption,
        ChoiceTarget,
        Participant,
        SceneBody,
        TextEntry,
        VisualChangeEvent,
    )
    from tools.vne_to_renpy import build_ordered_project_candidate

    registry_path = _REPO_ROOT / "scenarios" / "visual_assets" / "ASSET_REGISTRY.json"
    source_novel = _REPO_ROOT / "novel"

    def _scene(scene_id, ass_id, entries):
        body = SceneBody(
            authoring_schema_version=AUTHORING_SCHEMA_VERSION,
            scene_id=scene_id,
            location_id="yoga_hall",
            participants=(Participant(character_id="KIRA", role="protagonist", present=True),),
            content_rating="PG",
            entries=entries,
        )
        return build_ordered_ass(
            body, ass_id=ass_id, version=1, source_ref="x.json", source_hash="0" * 64
        )

    scene_a = _scene(
        "SC_900", "ass_900",
        (
            TextEntry(entry_id="e1", presentation="NARRATIVE", text="Kira enters the yoga hall."),
            ChoiceEntry(
                entry_id="c1",
                prompt="Continue?",
                options=(
                    ChoiceOption(
                        option_id="o1", display_text="Continue",
                        target=ChoiceTarget(target_kind="SCENE", target_id="SC_901"),
                    ),
                ),
            ),
            VisualChangeEvent(
                entry_id="v1", operation="SET",
                asset_id="kira_yoga_hall_pilot_image_01",
            ),
        ),
    )
    scene_b = _scene(
        "SC_901", "ass_901",
        (
            TextEntry(entry_id="e1", presentation="NARRATIVE", text="Kira continues."),
            VisualChangeEvent(entry_id="v1", operation="CLEAR", asset_id=None),
        ),
    )

    candidate = build_ordered_project_candidate(
        (scene_a, scene_b),
        reading_mode="classic_vn",
        character_symbols={},
        registry_path=registry_path,
        repo_root=_REPO_ROOT,
    )

    # source project must be unchanged by the candidate build (pure)
    assert not (source_novel / "game" / ORDERED_ASS_CANDIDATE_FILENAME).exists()

    result = lint_ordered_ass_candidate(
        candidate,
        source_novel_path=source_novel,
        sdk_path=sdk_path,
    )
    assert result.passed is True
    assert result.returncode == 0
    assert result.temp_cleaned is True
    assert not (source_novel / "game" / ORDERED_ASS_CANDIDATE_FILENAME).exists()
