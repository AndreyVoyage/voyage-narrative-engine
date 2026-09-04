#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PART R -- workspace model (offline, fake provider).

CLEAN_TEST default, NORMAL explicit, separate memory roots, no cross-workspace
contamination, no arbitrary frontend paths, same Accepted KIRA + variant.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.character_lab import CharacterLabApp
from services.character_lab.workspace import WorkspaceError, WorkspaceManager

_REPO_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_HASH = "e26f83dafa26e61af82f29b654b592300c8f3f7bd295d07bd4d2b6527ae3eebd"


def _fake_provider_factory(response="[KIRA] ответ"):
    def factory(recorder):
        def provider(messages):
            body = json.dumps({"model": "fake", "messages": messages}, ensure_ascii=False).encode("utf-8")
            if recorder:
                recorder({"event": "request", "payload": {"model": "fake", "messages": messages}, "body": body})
                recorder({"event": "response", "data": {"choices": [{"message": {"content": response}, "finish_reason": "stop"}]}})
            return response
        return provider
    return factory


def _make_app(tmp_path):
    return CharacterLabApp(
        acceptance_root=_REPO_ROOT / "accepted",
        data_root=tmp_path / "data",
        provider_factory=_fake_provider_factory(),
        provider_info={"provider_id": "deepseek", "model": "deepseek-v4-pro"},
        provider_availability="CONFIGURED",
    )


class TestDefaultsAndCreation:
    def test_1_default_workspace_is_clean_test(self, tmp_path):
        app = _make_app(tmp_path)
        ws = app.list_workspaces()
        current = [w for w in ws["workspaces"] if w["selected"]]
        assert len(current) == 1
        assert current[0]["workspace_kind"] == "CLEAN_TEST"
        assert app.loaded_state()["workspace_kind"] == "CLEAN_TEST"

    def test_2_new_clean_test_has_empty_memory(self, tmp_path):
        app = _make_app(tmp_path)
        app.chat("Привет.")
        r = app.new_clean_test()
        assert r["workspace_kind"] == "CLEAN_TEST"
        assert app.memory()["event_count"] == 0

    def test_6_new_clean_test_does_not_inherit_prior_test_memory(self, tmp_path):
        app = _make_app(tmp_path)
        app.chat("Сообщение в первом тесте.")
        assert app.memory()["event_count"] == 2
        app.new_clean_test()
        assert app.memory()["event_count"] == 0
        rows = app.memory()["events"]
        assert rows == []


class TestIsolation:
    def test_3_4_5_normal_and_clean_paths_differ_and_no_contamination(self, tmp_path):
        app = _make_app(tmp_path)
        # message in the default Clean Test
        app.chat("Только для Clean Test.")
        clean_ws_id = app.loaded_state()["workspace_id"]

        app.select_workspace("normal")
        assert app.loaded_state()["workspace_kind"] == "NORMAL"
        # NORMAL starts empty and does not see the clean-test message
        normal_mem = app.memory()
        assert all("Только для Clean Test." != e["meaning"] for e in normal_mem["events"])
        app.chat("Только для NORMAL.")

        # back to the clean test: it does not see the NORMAL message
        app.select_workspace(clean_ws_id)
        clean_mem = app.memory()
        assert any(e["meaning"] == "Только для Clean Test." for e in clean_mem["events"])
        assert all(e["meaning"] != "Только для NORMAL." for e in clean_mem["events"])

        # DB files are physically distinct
        normal_db = tmp_path / "data" / "workspaces" / "normal" / "runtime_memory.sqlite3"
        test_db = tmp_path / "data" / "workspaces" / "tests" / clean_ws_id / "runtime_memory.sqlite3"
        assert normal_db.exists() and test_db.exists()
        assert normal_db != test_db

    def test_7_and_8_accepted_hash_and_variant_same_across_workspaces(self, tmp_path):
        app = _make_app(tmp_path)
        s_clean = app.loaded_state()
        app.select_workspace("normal")
        s_normal = app.loaded_state()
        assert s_clean["accepted_source_hash"] == EXPECTED_HASH
        assert s_normal["accepted_source_hash"] == EXPECTED_HASH
        assert s_clean["variant_id"] == s_normal["variant_id"] == "KIRA_BETA_V1_CURRENT"


class TestBackendResolutionAndSafety:
    def test_9_switch_is_backend_resolved(self, tmp_path):
        app = _make_app(tmp_path)
        r = app.select_workspace("normal")
        assert r["workspace_id"] == "normal"
        assert r["workspace_kind"] == "NORMAL"
        assert r["notice"]["code"] == "LONG_LIVED_MEMORY"
        r2 = app.select_workspace(app.list_workspaces()["workspaces"][0]["workspace_id"]
                                  if app.list_workspaces()["workspaces"][0]["workspace_kind"] == "CLEAN_TEST"
                                  else app.new_clean_test()["workspace_id"])
        assert "notice" in r2

    def test_10_arbitrary_frontend_path_rejected(self, tmp_path):
        app = _make_app(tmp_path)
        for bad in ("../escape", "..\\escape", "/etc/passwd", "normal/../tests", "test-!!!", "", "   "):
            with pytest.raises(KeyError):
                app.select_workspace(bad)

    def test_manager_rejects_traversal_and_protects_normal(self, tmp_path):
        mgr = WorkspaceManager(tmp_path / "data")
        with pytest.raises(WorkspaceError):
            mgr.get("../x")
        with pytest.raises(WorkspaceError):
            mgr.reset_clean_test("normal")

    def test_reset_clean_test_only_touches_that_workspace(self, tmp_path):
        mgr = WorkspaceManager(tmp_path / "data")
        ws = mgr.new_clean_test()
        (ws.root / "marker.txt").write_text("x", encoding="utf-8")
        mgr.normal().root.mkdir(parents=True, exist_ok=True)
        (mgr.normal().root / "keep.txt").write_text("y", encoding="utf-8")
        mgr.reset_clean_test(ws.workspace_id)
        assert not (ws.root / "marker.txt").exists()
        assert (mgr.normal().root / "keep.txt").exists()
