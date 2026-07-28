#!/usr/bin/env python3
"""Eval tests -- 36-probe validation."""

import json
from pathlib import Path
import tempfile
import pytest
from services.persona_authoring.eval import PacEvalProbe, PacEvalResult, PacEvalService, PROBE_COUNT, PROBES_PER_CATEGORY
from services.persona_authoring.storage import PacStorage
from services.persona_authoring.errors import PacError


def _make_probe(probe_id, category="A", character_id="kira"):
    return {
        "probe_id": probe_id,
        "probe_version": "1.0",
        "character_id": character_id,
        "category": category,
        "scene_context": "test scene",
        "point_in_time": "present",
        "prompt": "test prompt",
        "required_gateway_sources": ["core/IDENTITY.json"],
        "expected_character_signals": "stability",
        "forbidden_claims": "none",
        "fmdr_requirements": "thoughts+actions+speech",
        "human_rubric": "rubric",
        "judge_rubric": "judge rubric",
    }


def _make_probe_set(n=36):
    probes = []
    cats = ["A"] * 12 + ["B"] * 12 + ["C"] * 12
    for i in range(n):
        p = _make_probe(f"probe-{i:03d}", category=cats[i] if i < len(cats) else "A")
        probes.append(p)
    return probes


class TestEvalProbeLoading:
    def test_load_36_probes(self, tmp_storage_dir):
        storage = PacStorage(base_path=tmp_storage_dir / "pac")
        probe_dir = Path(tmp_storage_dir) / "probes"
        probe_dir.mkdir()
        probes_data = _make_probe_set(36)
        for i, p in enumerate(probes_data):
            (probe_dir / f"probe_{i:03d}.json").write_text(
                json.dumps(p, ensure_ascii=False), encoding="utf-8"
            )
        svc = PacEvalService(storage, probe_dir=probe_dir)
        loaded = svc.load_probes()
        assert len(loaded) == 36

    def test_probe_count_too_few(self, tmp_storage_dir):
        storage = PacStorage(base_path=tmp_storage_dir / "pac")
        probe_dir = Path(tmp_storage_dir) / "probes"
        probe_dir.mkdir()
        for i in range(20):
            p = _make_probe(f"probe-{i:03d}", "A")
            (probe_dir / f"x_{i}.json").write_text(json.dumps(p, ensure_ascii=False), encoding="utf-8")
        svc = PacEvalService(storage, probe_dir=probe_dir)
        with pytest.raises(PacError, match="expected exactly 36"):
            svc.load_probes()

    def test_duplicate_probe_ids_rejected(self, tmp_storage_dir):
        storage = PacStorage(base_path=tmp_storage_dir / "pac")
        probe_dir = Path(tmp_storage_dir) / "probes"
        probe_dir.mkdir()
        probes_data = _make_probe_set(36)
        probes_data[0]["probe_id"] = probes_data[1]["probe_id"]  # duplicate
        for i, p in enumerate(probes_data):
            (probe_dir / f"p_{i:03d}.json").write_text(json.dumps(p, ensure_ascii=False), encoding="utf-8")
        svc = PacEvalService(storage, probe_dir=probe_dir)
        with pytest.raises(PacError, match="duplicate"):
            svc.load_probes()

    def test_category_count_validation(self, tmp_storage_dir):
        storage = PacStorage(base_path=tmp_storage_dir / "pac")
        probe_dir = Path(tmp_storage_dir) / "probes"
        probe_dir.mkdir()
        # Create explicitly 13 A, 11 B, 12 C = invalid
        cats = ["A"] * 13 + ["B"] * 11 + ["C"] * 12
        probes_data = [
            _make_probe(f"probe-{i:03d}", category=cats[i])
            for i in range(36)
        ]
        for i, p in enumerate(probes_data):
            (probe_dir / f"p_{i:03d}.json").write_text(json.dumps(p, ensure_ascii=False), encoding="utf-8")
        svc = PacEvalService(storage, probe_dir=probe_dir)
        with pytest.raises(PacError, match="category"):
            svc.load_probes()


class TestEvalResult:
    def test_build_eval_result(self, tmp_storage_dir):
        storage = PacStorage(base_path=tmp_storage_dir / "pac")
        svc = PacEvalService(storage)
        probes = [
            PacEvalProbe(
                probe_id=f"p-{i:03d}", probe_version="1.0",
                character_id="kira", category="A",
                scene_context="t", point_in_time="now",
                prompt="test", required_gateway_sources=(),
                expected_character_signals="s", forbidden_claims="f",
                fmdr_requirements="f", human_rubric="h", judge_rubric="j",
            )
            for i in range(3)
        ]
        results = [
            {"probe_id": f"p-{i:03d}", "score": 0.8, "notes": "ok"}
            for i in range(3)
        ]
        r = svc.build_eval_result(
            run_id="test-run", probes=probes, per_probe_results=results,
            provider="mock", model="test", character_id="kira",
        )
        assert r.aggregate_score["min_per_turn"] == 0.8
        assert 0.79 < r.aggregate_score["average"] < 0.81

    def test_manual_calibration_supported(self, tmp_storage_dir):
        storage = PacStorage(base_path=tmp_storage_dir / "pac")
        svc = PacEvalService(storage)
        path = svc.save_calibration("run-1", {"notes": "human scored"})
        assert path.exists()