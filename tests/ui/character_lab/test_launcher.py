"""Tracked launcher: static safety checks + offline CWD-independence verification."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

_LAUNCHER = Path(__file__).resolve().parents[3] / "START_CHARACTER_LAB.ps1"


def _text() -> str:
    return _LAUNCHER.read_text(encoding="utf-8")


def test_launcher_exists():
    assert _LAUNCHER.is_file()


def test_launcher_resolves_repo_root_from_script_location():
    assert "$PSScriptRoot" in _text()


def test_launcher_has_no_live_sibling_vcp_injection():
    text = _text()
    assert "voyage-character-platform\\src" not in text
    assert "voyage-character-platform/src" not in text


def test_launcher_references_pinned_site_packages():
    text = _text()
    assert "build\\output\\lab_vcp_env" in text
    assert "site-packages" in text
    assert "voyage_character_platform" in text


def test_launcher_launches_expected_module():
    assert "ui.character_lab" in _text()


def test_launcher_has_no_credential_literals():
    text = _text()
    for fragment in ("sk-", "Bearer ", "api_key=", "DEEPSEEK_API_KEY=", "OPENAI_API_KEY="):
        assert fragment not in text


def test_launcher_does_not_auto_install():
    text = _text().lower()
    assert "pip install" not in text
    assert "bootstrap_lab_vcp_env.py" in text  # referenced as manual instruction


def test_launcher_wraps_module_launch_in_repo_root_location():
    text = _text()
    assert "Push-Location $RepoRoot" in text
    assert "Pop-Location" in text
    push_idx = text.index("Push-Location $RepoRoot")
    pop_idx = text.index("Pop-Location")
    launch_idx = text.index("& py -m ui.character_lab")
    assert push_idx < launch_idx < pop_idx


def _find_powershell():
    return shutil.which("pwsh") or shutil.which("powershell")


def test_launcher_is_cwd_independent(tmp_path):
    pwsh = _find_powershell()
    if pwsh is None:
        pytest.skip("PowerShell not available")
    launcher = _LAUNCHER
    repo_root = launcher.parent.resolve()
    vcp_pkg = (
        repo_root
        / "build"
        / "output"
        / "lab_vcp_env"
        / "Lib"
        / "site-packages"
        / "voyage_character_platform"
    )
    if not vcp_pkg.is_dir():
        pytest.skip("pinned VCP runtime not present; cannot exercise launcher")

    shim_dir = tmp_path / "shim"
    shim_dir.mkdir()
    out_file = tmp_path / "shim_calls.txt"

    # Fake `py` records its working directory + args, then succeeds, so the
    # launcher's PySide6 check and the app launch both pass offline.
    (shim_dir / "py.cmd").write_text(
        "@echo off\r\n"
        f'echo CD=%CD% >> "{out_file}"\r\n'
        f'echo ARGS=%* >> "{out_file}"\r\n'
        "exit /b 0\r\n",
        encoding="ascii",
    )

    caller_cwd = tmp_path / "caller"
    caller_cwd.mkdir()

    env = os.environ.copy()
    env["PATH"] = str(shim_dir) + os.pathsep + env.get("PATH", "")

    subprocess.run(
        [
            pwsh,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(launcher),
        ],
        cwd=str(caller_cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    lines = out_file.read_text(encoding="utf-8", errors="replace").splitlines()
    launch_cwd = None
    for i, line in enumerate(lines):
        if line.startswith("ARGS=") and "ui.character_lab" in line:
            if i > 0 and lines[i - 1].startswith("CD="):
                launch_cwd = lines[i - 1][3:]
            break
    assert launch_cwd is not None, (
        f"launcher never invoked 'py -m ui.character_lab': {lines!r}"
    )
    assert Path(launch_cwd).resolve() == repo_root
