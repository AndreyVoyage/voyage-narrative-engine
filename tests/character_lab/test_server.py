#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Character Lab HTTP server tests (loopback only, offline fake provider)."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

import character_lab_server as server_mod
from services.character_lab import CharacterLabApp

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


def build_app(tmp_path, availability="CONFIGURED"):
    return CharacterLabApp(
        acceptance_root=_REPO_ROOT / "accepted",
        data_root=tmp_path / "data",
        provider_factory=make_fake_provider_factory() if availability == "CONFIGURED" else None,
        provider_info={"provider_id": "deepseek", "model": "deepseek-v4-pro", "credential_env": "DEEPSEEK_API_KEY"},
        provider_availability=availability,
    )


def http_get(url):
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


def http_post(url, body=None):
    data = json.dumps(body or {}).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST", headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


def http_delete(url):
    req = urllib.request.Request(url, method="DELETE")
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


@pytest.fixture
def server(tmp_path):
    app = build_app(tmp_path)
    srv = server_mod.CharacterLabServer(app)
    srv.start()
    yield srv
    srv.shutdown()


class TestServerBasics:
    def test_binds_localhost_only(self, server):
        assert server.host == "127.0.0.1"
        assert server_mod.BIND_HOST == "127.0.0.1"

    def test_health_without_provider(self, tmp_path):
        app = build_app(tmp_path, availability="NOT CONFIGURED")
        srv = server_mod.CharacterLabServer(app)
        srv.start()
        try:
            status, body = http_get(srv.base_url + "/health")
            assert status == 200
            assert body["status"] == "ready"
            assert body["accepted_package_loadable"] is True
            assert body["provider_availability"] == "NOT CONFIGURED"
        finally:
            srv.shutdown()

    def test_catalog(self, server):
        status, body = http_get(server.base_url + "/api/catalog")
        assert status == 200
        assert any(c["id"] == "kira" for c in body["characters"])
        assert any(v["id"] == "KIRA_BETA_V1_CURRENT" and v["implemented"] for v in body["variants"])

    def test_state(self, server):
        status, body = http_get(server.base_url + "/api/state")
        assert status == 200
        assert body["accepted_source_hash"] == EXPECTED_HASH
        assert body["package_status"] == "DRAFT"
        assert body["acceptance_decision"] == "HUMAN_APPROVED"

    def test_static_files_served(self, server):
        for path in ("/", "/app.css", "/app.js"):
            with urllib.request.urlopen(server.base_url + path, timeout=5) as r:
                assert r.status == 200
                assert r.read()


class TestServerApi:
    def test_new_session(self, server):
        status, body = http_post(server.base_url + "/api/session/new")
        assert status == 200
        assert body["session_id"].startswith("session-")

    def test_chat_returns_turn_id(self, server):
        status, body = http_post(server.base_url + "/api/chat", {"message": "Привет."})
        assert status == 200
        assert body["ok"] is True
        assert body["turn_id"]
        assert body["response"] == "[KIRA] тест"

    def test_turn_list_and_detail(self, server):
        _, chat = http_post(server.base_url + "/api/chat", {"message": "Привет."})
        status, turns = http_get(server.base_url + "/api/turns")
        assert status == 200
        assert any(t["turn_id"] == chat["turn_id"] for t in turns)
        status, detail = http_get(server.base_url + "/api/turn/" + chat["turn_id"])
        assert status == 200
        assert detail["request"]["request_hash"]

    def test_character_inspector(self, server):
        status, body = http_get(server.base_url + "/api/character")
        assert status == 200
        assert body["accepted_source_hash"] == EXPECTED_HASH
        assert len(body["groups"]) == 7

    def test_chat_unavailable_without_provider(self, tmp_path):
        app = build_app(tmp_path, availability="NOT CONFIGURED")
        srv = server_mod.CharacterLabServer(app)
        srv.start()
        try:
            status, body = http_post(srv.base_url + "/api/chat", {"message": "Привет."})
            assert status == 409
            assert body["ok"] is False
            assert body["error"] == "provider_unavailable"
        finally:
            srv.shutdown()

    def test_no_credential_in_api_output(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "SECRET_SENTINEL_VALUE")
        app = build_app(tmp_path, availability="NOT CONFIGURED")
        srv = server_mod.CharacterLabServer(app)
        srv.start()
        try:
            for path in ("/health", "/api/catalog", "/api/state", "/api/character"):
                status, body = http_get(srv.base_url + path)
                assert "SECRET_SENTINEL_VALUE" not in json.dumps(body, ensure_ascii=False)
        finally:
            srv.shutdown()

    def test_unknown_route_404(self, server):
        status, _ = http_get(server.base_url + "/api/not-a-real-endpoint")
        assert status == 404


class TestSlice3Routes:
    def test_workspaces_default_clean_test(self, server):
        status, body = http_get(server.base_url + "/api/workspaces")
        assert status == 200
        current = [w for w in body["workspaces"] if w["selected"]]
        assert len(current) == 1 and current[0]["workspace_kind"] == "CLEAN_TEST"

    def test_workspace_select_normal_warns(self, server):
        status, body = http_post(server.base_url + "/api/workspace/select", {"workspace_id": "normal"})
        assert status == 200
        assert body["workspace_kind"] == "NORMAL"
        assert body["notice"]["code"] == "LONG_LIVED_MEMORY"

    def test_workspace_select_unknown_404(self, server):
        status, _ = http_post(server.base_url + "/api/workspace/select", {"workspace_id": "../evil"})
        assert status == 404

    def test_new_clean_test_route(self, server):
        status, body = http_post(server.base_url + "/api/workspace/new-test")
        assert status == 200
        assert body["workspace_kind"] == "CLEAN_TEST"
        assert body["session_id"].startswith("session-")

    def test_memory_route_causal_order(self, server):
        http_post(server.base_url + "/api/chat", {"message": "Привет."})
        status, body = http_get(server.base_url + "/api/memory")
        assert status == 200
        assert body["causal_order"] == "seq"
        assert [e["event_type"] for e in body["events"]] == ["USER_MESSAGE", "CHARACTER_MESSAGE"]
        assert [e["provenance"] for e in body["events"]] == ["USER_STATED", "CHARACTER_UTTERANCE"]

    def test_scene_get_set_clear_routes(self, server):
        status, body = http_get(server.base_url + "/api/scene")
        assert status == 200 and body["active"] is False
        status, body = http_post(server.base_url + "/api/scene", {
            "title": "T", "location": "L", "participants": ["A", "B"],
            "prior_events": ["e1"], "current_situation": "now",
        })
        assert status == 200 and body["ok"] is True
        status, body = http_get(server.base_url + "/api/scene")
        assert body["active"] is True and body["scene"]["title"] == "T"
        status, body = http_delete(server.base_url + "/api/scene")
        assert status == 200 and body["active"] is False

    def test_scene_delivered_in_turn_via_server(self, server):
        http_post(server.base_url + "/api/scene", {
            "title": "Сцена", "location": "парк", "participants": ["Кира"],
            "prior_events": [], "current_situation": "Уникальная ситуация в парке.",
        })
        _, chat = http_post(server.base_url + "/api/chat", {"message": "Привет."})
        status, detail = http_get(server.base_url + "/api/turn/" + chat["turn_id"])
        assert status == 200
        scene_items = [i for i in detail["manifest"]["items"] if i["kind"] == "system.scene"]
        assert scene_items and scene_items[0]["delivered"] is True

    def test_no_credential_in_slice3_output(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "SECRET_SENTINEL_VALUE")
        app = build_app(tmp_path, availability="NOT CONFIGURED")
        srv = server_mod.CharacterLabServer(app)
        srv.start()
        try:
            for path in ("/api/workspaces", "/api/memory", "/api/scene"):
                status, body = http_get(srv.base_url + path)
                assert "SECRET_SENTINEL_VALUE" not in json.dumps(body, ensure_ascii=False)
        finally:
            srv.shutdown()

    def test_shutdown_endpoint(self, tmp_path):
        app = build_app(tmp_path)
        srv = server_mod.CharacterLabServer(app)
        srv.start()
        status, body = http_post(srv.base_url + "/shutdown")
        assert status == 200
        deadline = time.time() + 5
        stopped = False
        while time.time() < deadline:
            try:
                urllib.request.urlopen(srv.base_url + "/health", timeout=0.5)
                time.sleep(0.1)
            except Exception:
                stopped = True
                break
        assert stopped
        srv.shutdown()
