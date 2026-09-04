#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Character Lab application-service tests (offline, fake provider)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.character_lab import (
    CHARACTER_LAB_DATA_ROOT_ENV,
    CharacterLabApp,
    resolve_data_root,
)
from services.character_lab.turn_capture import compute_request_hash
from services.crp_authoring import compute_package_hash

_REPO_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_HASH = "e26f83dafa26e61af82f29b654b592300c8f3f7bd295d07bd4d2b6527ae3eebd"


def make_fake_provider_factory(response="[KIRA] тест"):
    def factory(recorder):
        def provider(messages):
            body = json.dumps({"model": "fake", "messages": messages}, ensure_ascii=False).encode("utf-8")
            if recorder:
                recorder({"event": "request", "payload": {"model": "fake", "messages": messages}, "body": body})
            if recorder:
                recorder({"event": "response", "data": {
                    "id": "cmpl-fake",
                    "model": "fake",
                    "choices": [{"message": {"content": response}, "finish_reason": "stop"}],
                }})
            return response
        return provider
    return factory


def make_app(tmp_path, *, availability="CONFIGURED", provider_factory=None, data_root=None):
    return CharacterLabApp(
        acceptance_root=_REPO_ROOT / "accepted",
        data_root=data_root or (tmp_path / "data"),
        provider_factory=provider_factory if provider_factory is not None else make_fake_provider_factory(),
        provider_info={"provider_id": "deepseek", "model": "deepseek-v4-pro", "credential_env": "DEEPSEEK_API_KEY"},
        provider_availability=availability,
    )


class TestCatalogAndState:
    def test_catalog_exposes_kira_and_variants(self, tmp_path):
        app = make_app(tmp_path)
        catalog = app.catalog()
        chars = {c["id"] for c in catalog["characters"]}
        assert "kira" in chars
        variants = {v["id"]: v for v in catalog["variants"]}
        assert variants["KIRA_BETA_V1_CURRENT"]["implemented"] is True
        assert variants["KIRA_GROUNDED_V2"]["implemented"] is False
        assert variants["EXPERIMENTAL"]["implemented"] is False

    def test_planned_variants_not_activatable(self, tmp_path):
        app = make_app(tmp_path)
        variants = app.catalog()["variants"]
        planned = [v for v in variants if v["id"] != "KIRA_BETA_V1_CURRENT"]
        assert planned and all(v["implemented"] is False for v in planned)

    def test_state_returns_real_acceptance_hash(self, tmp_path):
        app = make_app(tmp_path)
        state = app.loaded_state()
        assert state["character_id"] == "kira"
        assert state["acceptance_decision"] == "HUMAN_APPROVED"
        assert state["accepted_source_hash"] == EXPECTED_HASH
        assert state["runtime_loaded_package_hash"] == EXPECTED_HASH
        assert state["hash_match"] is True

    def test_draft_status_and_acceptance_shown_separately(self, tmp_path):
        app = make_app(tmp_path)
        state = app.loaded_state()
        assert state["package_status"] == "DRAFT"
        assert state["acceptance_decision"] == "HUMAN_APPROVED"
        assert state["package_status"] != state["acceptance_decision"]


class TestSessions:
    def test_new_session(self, tmp_path):
        app = make_app(tmp_path)
        r = app.new_session()
        assert r["session_id"].startswith("session-")

    def test_selected_session_is_backend_state(self, tmp_path):
        app = make_app(tmp_path)
        s1 = app.new_session()["session_id"]
        s2 = app.new_session()["session_id"]
        app.select_session(s1)
        sessions = app.list_sessions()
        by_id = {s["session_id"]: s for s in sessions}
        assert by_id[s1]["selected"] is True
        assert by_id[s2]["selected"] is False


class TestChat:
    def test_chat_completes_through_runtime_service(self, tmp_path):
        app = make_app(tmp_path)
        r = app.chat("Привет.")
        assert r["ok"] is True
        assert r["response"] == "[KIRA] тест"
        assert r["turn_id"]

    def test_chat_creates_turn_capture_artifacts(self, tmp_path):
        app = make_app(tmp_path)
        r = app.chat("Привет.")
        turn_dir = app.turn_capture_dir(r["turn_id"])
        # Slice 3: artifacts live under the current (Clean Test) workspace root.
        assert "workspaces" in turn_dir.parts
        assert (turn_dir / "request.json").exists()
        assert (turn_dir / "manifest.json").exists()
        assert (turn_dir / "response.json").exists()

    def test_turn_list_exposes_captured_turn(self, tmp_path):
        app = make_app(tmp_path)
        r = app.chat("Привет.")
        turns = app.list_turns()
        ids = [t["turn_id"] for t in turns]
        assert r["turn_id"] in ids

    def test_turn_detail_request_hash_matches_exact_artifact(self, tmp_path):
        app = make_app(tmp_path)
        r = app.chat("Привет.")
        detail = app.turn_detail(r["turn_id"])
        request_bytes = (app.turn_capture_dir(r["turn_id"]) / "request.json").read_bytes()
        assert detail["request"]["request_hash"] == compute_request_hash(request_bytes)

    def test_turn_detail_selected_delivered_from_manifest(self, tmp_path):
        app = make_app(tmp_path)
        r = app.chat("Уникальный вопрос.")
        detail = app.turn_detail(r["turn_id"])
        items = {i["kind"]: i for i in detail["manifest"]["items"]}
        assert items["user.current"]["selected"] is True
        assert items["user.current"]["delivered"] is True
        assert items["system.role_instruction"]["delivered"] is True

    def test_chat_unavailable_without_provider(self, tmp_path):
        app = make_app(tmp_path, availability="NOT CONFIGURED", provider_factory=None)
        r = app.chat("Привет.")
        assert r["ok"] is False
        assert r["error"] == "provider_unavailable"

    def test_empty_message_rejected(self, tmp_path):
        app = make_app(tmp_path)
        r = app.chat("   ")
        assert r["ok"] is False
        assert r["error"] == "empty_message"


class TestCharacterInspector:
    def test_inspector_serializes_loaded_package(self, tmp_path):
        app = make_app(tmp_path, availability="NOT CONFIGURED", provider_factory=None)
        data = app.character_inspector()
        assert data["accepted_source_hash"] == EXPECTED_HASH
        assert len(data["groups"]) == 7
        assert data["package_status"] == "DRAFT"

    def test_inspection_works_without_provider(self, tmp_path):
        app = make_app(tmp_path, availability="NOT CONFIGURED", provider_factory=None)
        data = app.character_inspector()
        assert data["character_id"] == "kira"


class TestSafety:
    def test_no_credential_value_in_api_output(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "SECRET_SENTINEL_VALUE")
        app = make_app(tmp_path, availability="NOT CONFIGURED", provider_factory=None)
        blobs = [
            json.dumps(app.health(), ensure_ascii=False),
            json.dumps(app.catalog(), ensure_ascii=False),
            json.dumps(app.loaded_state(), ensure_ascii=False),
            json.dumps(app.character_inspector(), ensure_ascii=False),
            json.dumps(app.list_workspaces(), ensure_ascii=False),
            json.dumps(app.memory(), ensure_ascii=False),
            json.dumps(app.get_scene(), ensure_ascii=False),
        ]
        for blob in blobs:
            assert "SECRET_SENTINEL_VALUE" not in blob

    def test_no_package_mutation(self, tmp_path):
        app = make_app(tmp_path)
        app.chat("Привет.")
        after = app.loaded_state()["runtime_loaded_package_hash"]
        assert after == EXPECTED_HASH

    def test_default_data_root_outside_repo(self):
        root = resolve_data_root()
        assert str(_REPO_ROOT) not in [str(p) for p in root.parents]
        assert str(root).startswith(str(Path.home()))

    def test_isolated_from_kira_cli_memory(self):
        from kira_chat_cli import DEFAULT_MEMORY_ROOT  # noqa: E402
        char_lab_root = resolve_data_root()
        assert char_lab_root != DEFAULT_MEMORY_ROOT
        assert "character_lab" in str(char_lab_root)

    def test_env_override_data_root(self, tmp_path, monkeypatch):
        monkeypatch.setenv(CHARACTER_LAB_DATA_ROOT_ENV, str(tmp_path / "override"))
        assert resolve_data_root() == Path(tmp_path / "override")
