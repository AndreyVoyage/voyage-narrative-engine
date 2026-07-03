#!/usr/bin/env python3
"""Unit tests for the N5H mock live/dev JSON loader tool."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
LOADER = REPO_ROOT / "tools" / "live_dev_json_loader.py"
WORKFLOW = REPO_ROOT / "tools" / "rn_workflow.py"
SCENE = REPO_ROOT / "scenarios" / "SCENARIO_017_SERGEY_WRITES_AGAIN.v2.json"


def run_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


class TestLiveDevJsonLoader(unittest.TestCase):
    def _combined(self, result: subprocess.CompletedProcess[str]) -> str:
        return result.stdout + result.stderr

    def test_inspect_sc017_succeeds(self) -> None:
        result = run_command([str(LOADER), "inspect", "SC_017"])
        output = self._combined(result)
        self.assertEqual(result.returncode, 0, output)
        self.assertIn("PASS live-dev-inspect", output)
        self.assertIn("SC_017", output)
        self.assertIn("beat_id", output)
        self.assertIn("safe_editable_fields", output)
        self.assertIn("forbidden_fields", output)
        self.assertIn("completed_scenes -> v2_completed_scenes", output)
        self.assertIn("write-back: NOT IMPLEMENTED", output)
        self.assertIn("hot-reload: NOT IMPLEMENTED", output)
        self.assertIn("RenPy runtime loader: NOT IMPLEMENTED", output)
        self.assertIn("release path affected: NO", output)

    def test_inspect_direct_path_succeeds(self) -> None:
        result = run_command([str(LOADER), "inspect", str(SCENE)])
        output = self._combined(result)
        self.assertEqual(result.returncode, 0, output)
        self.assertIn("PASS live-dev-inspect", output)
        self.assertIn("SC_017", output)

    def test_workflow_wrapper_inspect_succeeds(self) -> None:
        result = run_command([str(WORKFLOW), "live-dev-inspect", "SC_017"])
        output = self._combined(result)
        self.assertEqual(result.returncode, 0, output)
        self.assertIn("PASS live-dev-inspect", output)

    def test_inspect_missing_scene_fails_cleanly(self) -> None:
        result = run_command([str(LOADER), "inspect", "SC_999"])
        output = self._combined(result)
        self.assertNotEqual(result.returncode, 0, output)
        self.assertIn("FAIL", output)
        self.assertNotIn("Traceback", output)

    def test_inspect_non_v2_path_fails_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "not_v2.json"
            path.write_text('{"not": "v2"}', encoding="utf-8")
            result = run_command([str(LOADER), "inspect", str(path)])
            output = self._combined(result)
            self.assertNotEqual(result.returncode, 0, output)
            self.assertIn("FAIL", output)
            self.assertNotIn("Traceback", output)

    def test_inspect_invalid_json_fails_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "invalid.v2.json"
            path.write_text("this is not json", encoding="utf-8")
            result = run_command([str(LOADER), "inspect", str(path)])
            output = self._combined(result)
            self.assertNotEqual(result.returncode, 0, output)
            self.assertIn("FAIL", output)
            self.assertNotIn("Traceback", output)

    def test_reload_check_text_only_is_safe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "base.v2.json"
            candidate = Path(tmp) / "candidate.v2.json"
            data = json.loads(SCENE.read_text(encoding="utf-8"))
            base.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

            data["entry_beats"][0]["narration"] = "Modified narration text for reload test."
            candidate.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

            result = run_command(
                [str(LOADER), "reload-check", "--base", str(base), "--candidate", str(candidate)]
            )
            output = self._combined(result)
            self.assertEqual(result.returncode, 0, output)
            self.assertIn("PASS reload-check", output)
            self.assertIn("SAFE_TEXT_ONLY", output)

    def test_reload_check_structural_change_is_unsafe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "base.v2.json"
            candidate = Path(tmp) / "candidate.v2.json"
            data = json.loads(SCENE.read_text(encoding="utf-8"))
            base.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

            data["entry_beats"][0]["beat_id"] = "e1-modified"
            candidate.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

            result = run_command(
                [str(LOADER), "reload-check", "--base", str(base), "--candidate", str(candidate)]
            )
            output = self._combined(result)
            self.assertEqual(result.returncode, 0, output)
            self.assertIn("PASS reload-check", output)
            self.assertIn("UNSAFE_STRUCTURAL", output)

    def test_workflow_wrapper_reload_check_works(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "base.v2.json"
            candidate = Path(tmp) / "candidate.v2.json"
            data = json.loads(SCENE.read_text(encoding="utf-8"))
            base.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

            data["entry_beats"][0]["speech"] = None
            data["entry_beats"][0]["narration"] = "Workflow wrapper reload check text."
            candidate.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

            result = run_command(
                [
                    str(WORKFLOW),
                    "live-dev-reload-check",
                    "--base",
                    str(base),
                    "--candidate",
                    str(candidate),
                ]
            )
            output = self._combined(result)
            self.assertEqual(result.returncode, 0, output)
            self.assertIn("SAFE_TEXT_ONLY", output)


if __name__ == "__main__":
    unittest.main()
