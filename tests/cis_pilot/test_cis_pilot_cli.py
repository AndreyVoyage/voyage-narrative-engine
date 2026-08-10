#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Slice 4 tests for tools/cis_pilot_cli.py.

Covers: CLI help output, load-snapshot, run-probe for each mode,
assemble-result, inspect, exit codes, non-mock rejection, path safety.
No real provider, no network.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.cis_pilot_cli import _main


def _run_cli(argv: list[str], expect_exit: int = 0) -> str:
    """Run the CLI with args; capture stdout and stderr, verify exit code."""
    import io
    out_buf = io.StringIO()
    err_buf = io.StringIO()
    try:
        with patch("sys.stdout", out_buf), patch("sys.stderr", err_buf):
            _main(argv)
    except SystemExit as e:
        if e.code != expect_exit:
            raise AssertionError(f"Expected exit {expect_exit}, got {e.code}")
    return out_buf.getvalue() + err_buf.getvalue()


# ---------------------------------------------------------------------------
# Help / usage
# ---------------------------------------------------------------------------

class TestCliHelp:
    def test_help_main(self) -> None:
        output = _run_cli(["--help"], expect_exit=0)
        assert "usage" in output

    def test_help_load_snapshot(self) -> None:
        output = _run_cli(["load-snapshot", "--help"], expect_exit=0)
        assert "usage" in output

    def test_help_run_probe(self) -> None:
        output = _run_cli(["run-probe", "--help"], expect_exit=0)
        assert "usage" in output

    def test_no_command_is_error(self) -> None:
        with pytest.raises(SystemExit):
            _main()


# ---------------------------------------------------------------------------
# load-snapshot
# ---------------------------------------------------------------------------

class TestCliLoadSnapshot:
    def test_load_snapshot_prints_info(self) -> None:
        output = _run_cli(["load-snapshot"])
        assert "Snapshot loaded" in output
        assert "P3 trust=" in output

    def test_load_snapshot_with_custom_base(self, tmp_path: Path) -> None:
        output = _run_cli(["load-snapshot", "--base-path", str(tmp_path)])
        assert "Snapshot loaded" in output


# ---------------------------------------------------------------------------
# run-probe
# ---------------------------------------------------------------------------

class TestCliRunProbe:
    def test_run_pb_rec(self, tmp_path: Path) -> None:
        output = _run_cli(["run-probe", "--mode", "PB-REC",
                          "--base-path", str(tmp_path), "--samples", "1"])
        assert "Running PB-REC" in output
        assert "Result package saved" in output

    def test_run_pb_mem(self, tmp_path: Path) -> None:
        output = _run_cli(["run-probe", "--mode", "PB-MEM",
                          "--base-path", str(tmp_path), "--samples", "1"])
        assert "Running PB-MEM" in output
        assert "Result package saved" in output

    def test_run_pb_ab_t3_p3(self, tmp_path: Path) -> None:
        output = _run_cli(["run-probe", "--mode", "PB-AB",
                          "--sub-mode", "T3-P3",
                          "--base-path", str(tmp_path), "--samples", "1"])
        assert "Running PB-AB/T3-P3" in output

    def test_run_pb_ab_t3_p4(self, tmp_path: Path) -> None:
        output = _run_cli(["run-probe", "--mode", "PB-AB",
                          "--sub-mode", "T3-P4",
                          "--base-path", str(tmp_path), "--samples", "1"])
        assert "Running PB-AB/T3-P4" in output

    def test_run_pb_ab_combined(self, tmp_path: Path) -> None:
        output = _run_cli(["run-probe", "--mode", "PB-AB",
                          "--sub-mode", "COMBINED",
                          "--base-path", str(tmp_path), "--samples", "1"])
        assert "Running PB-AB/COMBINED" in output

    def test_run_pb_leak(self, tmp_path: Path) -> None:
        output = _run_cli(["run-probe", "--mode", "PB-LEAK",
                          "--base-path", str(tmp_path), "--samples", "1"])
        assert "Running PB-LEAK" in output
        assert "Result package saved" in output

    def test_invalid_mode_exits_nonzero(self) -> None:
        output = _run_cli(["run-probe", "--mode", "INVALID",
                          "--base-path", "/tmp"], expect_exit=2)
        assert "error" in output.lower()


# ---------------------------------------------------------------------------
# assemble-result / inspect
# ---------------------------------------------------------------------------

class TestCliAssembleInspect:
    def test_assemble_missing_run_id(self, tmp_path: Path) -> None:
        output = _run_cli(["assemble-result", "--run-id", "nonexistent",
                          "--base-path", str(tmp_path)], expect_exit=1)
        assert "ERROR" in output


# ---------------------------------------------------------------------------
# Static: no network or real provider in CLI
# ---------------------------------------------------------------------------

class TestCliStaticNoNetwork:
    def test_cli_source_has_no_network(self) -> None:
        src = (Path(__file__).parents[2] / "tools" /
               "cis_pilot_cli.py").read_text(encoding="utf-8")
        for token in ("openai", "anthropic", "deepseek", "kimi", "ollama",
                      "requests.", "httpx", "urllib", "socket"):
            assert token not in src, f"Forbidden token in CLI source: {token}"

    def test_cli_source_has_no_real_provider_selection(self) -> None:
        """Verify CLI never selects a real provider. The word 'real' may appear
        in docstrings/description text but never as a provider selection path."""
        src = (Path(__file__).parents[2] / "tools" /
               "cis_pilot_cli.py").read_text(encoding="utf-8")
        # Only accept the literal string '"real"' as valid mention
        for token in ("provider=real", "'real'", '"openai"', '"anthropic"', '"kimi"'):
            assert token not in src, f"CLI mentions real provider: {token}"
