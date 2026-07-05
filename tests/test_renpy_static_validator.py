#!/usr/bin/env python3
"""Tests for renpy_static_validator freshness checks."""

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "tools"
sys.path.insert(0, str(TOOLS_DIR))

import renpy_static_validator as validator


def _sha256(text: bytes) -> str:
    return hashlib.sha256(text).hexdigest()


class TestGeneratedSourceFreshness(unittest.TestCase):
    def _make_repo(self):
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        scenarios = root / "scenarios"
        scenarios.mkdir()
        generated = root / "scenes_v2_generated.rpy"
        self.addCleanup(tmp.cleanup)
        return root, scenarios, generated

    def _header(self, source_path: str, sha: str) -> str:
        return (
            "# AUTO-GENERATED\n"
            f"# source: {source_path}\n"
            f"# source SHA256: {sha}\n"
            "# do not edit\n"
            "label sc_017_v2_start:\n"
            "    return\n"
        )

    def test_matching_hash_passes(self):
        root, scenarios, generated = self._make_repo()
        source = scenarios / "SCENARIO_017.json"
        source.write_bytes(b'{"id":"SC_017"}')
        sha = _sha256(source.read_bytes())
        generated.write_text(
            self._header("scenarios/SCENARIO_017.json", sha), encoding="utf-8"
        )
        result = validator.ValidatorResult()
        validator.check_generated_source_freshness(result, generated, root)
        self.assertTrue(result.ok(), result.errors)

    def test_mismatching_hash_fails(self):
        root, scenarios, generated = self._make_repo()
        source = scenarios / "SCENARIO_017.json"
        source.write_bytes(b'{"id":"SC_017"}')
        generated.write_text(
            self._header("scenarios/SCENARIO_017.json", "0" * 64),
            encoding="utf-8",
        )
        result = validator.ValidatorResult()
        validator.check_generated_source_freshness(result, generated, root)
        self.assertFalse(result.ok())
        self.assertTrue(
            any(
                "stale" in e.lower() or "mismatch" in e.lower()
                for e in result.errors
            )
        )

    def test_missing_source_path_fails(self):
        root, scenarios, generated = self._make_repo()
        source = scenarios / "SCENARIO_017.json"
        source.write_bytes(b'{"id":"SC_017"}')
        sha = _sha256(source.read_bytes())
        header = (
            "# AUTO-GENERATED\n"
            f"# source SHA256: {sha}\n"
            "# do not edit\n"
        )
        generated.write_text(header, encoding="utf-8")
        result = validator.ValidatorResult()
        validator.check_generated_source_freshness(result, generated, root)
        self.assertFalse(result.ok())
        self.assertTrue(any("source path" in e.lower() for e in result.errors))

    def test_missing_sha256_fails(self):
        root, scenarios, generated = self._make_repo()
        source = scenarios / "SCENARIO_017.json"
        source.write_bytes(b'{"id":"SC_017"}')
        header = (
            "# AUTO-GENERATED\n"
            "# source: scenarios/SCENARIO_017.json\n"
            "# do not edit\n"
        )
        generated.write_text(header, encoding="utf-8")
        result = validator.ValidatorResult()
        validator.check_generated_source_freshness(result, generated, root)
        self.assertFalse(result.ok())
        self.assertTrue(any("sha256" in e.lower() for e in result.errors))

    def test_missing_source_file_fails(self):
        root, _scenarios, generated = self._make_repo()
        # Source file intentionally not created.
        generated.write_text(
            self._header("scenarios/SCENARIO_017.json", "0" * 64),
            encoding="utf-8",
        )
        result = validator.ValidatorResult()
        validator.check_generated_source_freshness(result, generated, root)
        self.assertFalse(result.ok())
        self.assertTrue(any("not found" in e.lower() for e in result.errors))

    def test_relative_path_resolves_from_repo_root(self):
        root, scenarios, generated = self._make_repo()
        source = scenarios / "SCENARIO_017.json"
        source.write_bytes(b'{"id":"SC_017"}')
        sha = _sha256(source.read_bytes())
        generated.write_text(
            self._header("scenarios/SCENARIO_017.json", sha), encoding="utf-8"
        )
        result = validator.ValidatorResult()
        validator.check_generated_source_freshness(result, generated, root)
        self.assertTrue(result.ok(), result.errors)

    def test_expected_failures_do_not_raise(self):
        root, scenarios, generated = self._make_repo()
        source = scenarios / "SCENARIO_017.json"
        source.write_bytes(b'{"id":"SC_017"}')
        generated.write_text(
            self._header("scenarios/SCENARIO_017.json", "0" * 64),
            encoding="utf-8",
        )
        result = validator.ValidatorResult()
        try:
            validator.check_generated_source_freshness(result, generated, root)
        except Exception as exc:
            self.fail(f"expected failure raised an exception: {exc}")
        self.assertFalse(result.ok())


if __name__ == "__main__":
    unittest.main()
