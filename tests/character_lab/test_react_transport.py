#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""React Character Lab desktop integration v1 -- transport tests.

Offline, fake provider only. No live provider call, no network beyond
127.0.0.1. Proves the full path:

    HTTP request -> ReactTransport -> CharacterLabServiceAdapter
    -> CharacterLabApp / RuntimeService -> fake provider -> HTTP response

without changing CharacterService, CharacterLabServiceAdapter, or
RuntimeService semantics in any way.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest

import character_lab_react_server as server_mod
from services.character_lab.react_transport import ReactTransport, ReactTransportError
from services.character_lab.service_adapter import CharacterLabServiceAdapter

_REPO_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_HASH = "e26f83dafa26e61af82f29b654b592300c8f3f7bd295d07bd4d2b6527ae3eebd"


def _transport(tmp_path, response="[KIRA] тестовый фейковый ответ") -> ReactTransport:
    app = server_mod.build_app(
        acceptance_root=_REPO_ROOT / "accepted",
        data_root=tmp_path / "data",
        response=response,
    )
    return ReactTransport(CharacterLabServiceAdapter(app))


def _new_session(transport, variant_id="KIRA_BETA_V1_CURRENT", purpose="TESTING"):
    ws = transport.create_test_workspace()
    session = transport.create_session({
        "characterId": "kira", "variantId": variant_id,
        "purpose": purpose, "workspaceId": ws["workspaceId"],
    })
    return ws, session


class TestTransportDirect:
    """Direct ReactTransport calls -- no HTTP/sockets involved."""

    def test_list_characters_exposes_kira(self, tmp_path):
        transport = _transport(tmp_path)
        data = transport.list_characters()
        ids = {c["characterId"] for c in data["characters"]}
        assert "kira" in ids
        kira = next(c for c in data["characters"] if c["characterId"] == "kira")
        assert kira["packageRef"]["sourceHash"] == EXPECTED_HASH
        assert kira["packageRef"]["acceptanceDecision"] == "HUMAN_APPROVED"

    def test_variants_expose_beta_grounded_and_experimental_unavailable(self, tmp_path):
        transport = _transport(tmp_path)
        data = transport.list_variants("kira")
        variants = {v["variantId"]: v for v in data["variants"]}
        assert variants["KIRA_BETA_V1_CURRENT"]["implemented"] is True
        assert variants["KIRA_GROUNDED_V2"]["implemented"] is True
        assert variants["EXPERIMENTAL"]["implemented"] is False

    def test_workspaces_list_correctly(self, tmp_path):
        transport = _transport(tmp_path)
        data = transport.list_workspaces()
        kinds = {w["workspaceKind"] for w in data["workspaces"]}
        assert "NORMAL" in kinds and "CLEAN_TEST" in kinds

    def test_clean_test_can_be_created(self, tmp_path):
        transport = _transport(tmp_path)
        before = {w["workspaceId"] for w in transport.list_workspaces()["workspaces"]}
        ws = transport.create_test_workspace()
        assert ws["workspaceKind"] == "CLEAN_TEST"
        after = {w["workspaceId"] for w in transport.list_workspaces()["workspaces"]}
        assert ws["workspaceId"] in after - before

    def test_testing_session_requires_explicit_workspace_id(self, tmp_path):
        transport = _transport(tmp_path)
        with pytest.raises(ReactTransportError) as exc_info:
            transport.create_session({
                "characterId": "kira", "variantId": "KIRA_BETA_V1_CURRENT",
                "purpose": "TESTING",
                # workspaceId omitted entirely
            })
        assert exc_info.value.code == "invalid_request"

        with pytest.raises(ReactTransportError) as exc_info2:
            transport.create_session({
                "characterId": "kira", "variantId": "KIRA_BETA_V1_CURRENT",
                "purpose": "TESTING", "workspaceId": "test-doesnotexist000000000000",
            })
        assert exc_info2.value.code == "unknown_workspace"
        assert exc_info2.value.status == 404

    def test_session_creation_never_silently_creates_a_workspace(self, tmp_path):
        transport = _transport(tmp_path)
        ws = transport.create_test_workspace()
        before = {w["workspaceId"] for w in transport.list_workspaces()["workspaces"]}
        transport.create_session({
            "characterId": "kira", "variantId": "KIRA_BETA_V1_CURRENT",
            "purpose": "TESTING", "workspaceId": ws["workspaceId"],
        })
        after = {w["workspaceId"] for w in transport.list_workspaces()["workspaces"]}
        assert before == after

    def test_message_reaches_adapter_and_fake_reply_returns(self, tmp_path):
        transport = _transport(tmp_path, response="[KIRA] уникальный фейковый ответ 42")
        _, session = _new_session(transport)
        result = transport.send_message({"sessionId": session["sessionId"], "text": "Привет"})
        assert result["response"] == "[KIRA] уникальный фейковый ответ 42"
        assert result["turnId"]

    def test_identity_preserved_across_character_session_variant(self, tmp_path):
        transport = _transport(tmp_path)
        ws, session = _new_session(transport, variant_id="KIRA_GROUNDED_V2")
        assert session["characterId"] == "kira"
        assert session["variantId"] == "KIRA_GROUNDED_V2"
        assert session["workspace"]["workspaceId"] == ws["workspaceId"]
        turn = transport.send_message({"sessionId": session["sessionId"], "text": "Привет"})
        assert turn["sessionId"] == session["sessionId"]
        assert turn["characterId"] == "kira"
        assert turn["variantId"] == "KIRA_GROUNDED_V2"
        fetched = transport.get_session(session["sessionId"])
        assert fetched == session

    def test_experimental_creates_no_session(self, tmp_path):
        transport = _transport(tmp_path)
        ws = transport.create_test_workspace()
        with pytest.raises(ReactTransportError) as exc_info:
            transport.create_session({
                "characterId": "kira", "variantId": "EXPERIMENTAL",
                "purpose": "TESTING", "workspaceId": ws["workspaceId"],
            })
        assert exc_info.value.code == "unavailable_variant"

    def test_unsupported_purpose_rejected(self, tmp_path):
        transport = _transport(tmp_path)
        ws = transport.create_test_workspace()
        with pytest.raises(ReactTransportError) as exc_info:
            transport.create_session({
                "characterId": "kira", "variantId": "KIRA_BETA_V1_CURRENT",
                "purpose": "AUTHORING", "workspaceId": ws["workspaceId"],
            })
        assert exc_info.value.code == "unsupported_purpose"
        assert exc_info.value.status == 501

    def test_unknown_character_rejected(self, tmp_path):
        transport = _transport(tmp_path)
        with pytest.raises(ReactTransportError) as exc_info:
            transport.get_character("nika")
        assert exc_info.value.code == "unknown_character"

    def test_unknown_session_rejected(self, tmp_path):
        transport = _transport(tmp_path)
        with pytest.raises(ReactTransportError) as exc_info:
            transport.get_session("session-doesnotexist")
        assert exc_info.value.code == "unknown_session"

    def test_invalid_request_body_rejected(self, tmp_path):
        transport = _transport(tmp_path)
        with pytest.raises(ReactTransportError) as exc_info:
            transport.send_message({"sessionId": "x"})  # missing 'text'
        assert exc_info.value.code == "invalid_request"
        assert exc_info.value.status == 400

    def test_invalid_purpose_string_rejected(self, tmp_path):
        transport = _transport(tmp_path)
        ws = transport.create_test_workspace()
        with pytest.raises(ReactTransportError) as exc_info:
            transport.create_session({
                "characterId": "kira", "variantId": "KIRA_BETA_V1_CURRENT",
                "purpose": "NOT_A_REAL_PURPOSE", "workspaceId": ws["workspaceId"],
            })
        assert exc_info.value.code == "invalid_request"

    def test_internal_error_never_leaks_traceback(self, tmp_path, monkeypatch):
        transport = _transport(tmp_path)

        def boom(*a, **k):
            raise RuntimeError("simulated internal failure with a secret detail")

        monkeypatch.setattr(transport._adapter, "list_characters", boom)
        with pytest.raises(ReactTransportError) as exc_info:
            transport.list_characters()
        assert exc_info.value.code == "internal_error"
        assert exc_info.value.status == 500
        payload = json.dumps(exc_info.value.to_json())
        assert "Traceback" not in payload
        assert "simulated internal failure" not in payload
        assert exc_info.value.message == "internal server failure"


# --------------------------------------------------------------------------
# Real HTTP, real loopback socket, still fake provider only.
# --------------------------------------------------------------------------

def _http_get(url):
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


def _http_post(url, body=None):
    data = json.dumps(body or {}).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST", headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


@pytest.fixture
def server(tmp_path):
    app = server_mod.build_app(acceptance_root=_REPO_ROOT / "accepted", data_root=tmp_path / "data")
    adapter = CharacterLabServiceAdapter(app)
    transport = ReactTransport(adapter)
    srv = server_mod.ReactCharacterLabServer(transport, port=0)
    srv.start()
    yield srv
    srv.shutdown()


class TestServerBindingAndHealth:
    def test_binds_localhost_only(self, server):
        assert server.host == "127.0.0.1"
        assert server_mod.BIND_HOST == "127.0.0.1"

    def test_rejects_non_loopback_bind(self, tmp_path):
        transport = _transport(tmp_path)
        with pytest.raises(ValueError):
            server_mod.ReactCharacterLabServer(transport, bind="0.0.0.0", port=0)

    def test_health(self, server):
        status, body = _http_get(server.base_url + "/health")
        assert status == 200 and body["status"] == "ready" and body["provider"] == "fake"


class TestEndToEndSmoke:
    """The exact required path: Clean Test workspace -> KIRA Beta TESTING
    session -> send 'Привет' -> deterministic fake reply, all over a real
    loopback HTTP socket. No browser automation; this direct HTTP smoke is
    the required end-to-end proof."""

    def test_full_desktop_flow_over_real_http(self, server):
        status, ws = _http_post(server.base_url + "/api/workspaces")
        assert status == 200 and ws["workspaceKind"] == "CLEAN_TEST"

        status, session = _http_post(server.base_url + "/api/sessions", {
            "characterId": "kira", "variantId": "KIRA_BETA_V1_CURRENT",
            "purpose": "TESTING", "workspaceId": ws["workspaceId"],
        })
        assert status == 200
        assert session["variantId"] == "KIRA_BETA_V1_CURRENT"
        assert session["workspace"]["workspaceId"] == ws["workspaceId"]

        status, turn = _http_post(server.base_url + "/api/chat", {
            "sessionId": session["sessionId"], "text": "Привет",
        })
        assert status == 200
        assert turn["response"] == server_mod.DEFAULT_FAKE_REPLY
        assert turn["sessionId"] == session["sessionId"]
        assert turn["turnId"]

        status, fetched = _http_get(server.base_url + "/api/sessions/" + session["sessionId"])
        assert status == 200 and fetched == session

    def test_characters_and_variants_over_http(self, server):
        status, data = _http_get(server.base_url + "/api/characters")
        assert status == 200
        assert any(c["characterId"] == "kira" for c in data["characters"])

        status, data = _http_get(server.base_url + "/api/characters/kira/variants")
        assert status == 200
        variants = {v["variantId"]: v for v in data["variants"]}
        assert variants["EXPERIMENTAL"]["implemented"] is False

    def test_unknown_workspace_over_http_returns_deterministic_error(self, server):
        status, body = _http_post(server.base_url + "/api/sessions", {
            "characterId": "kira", "variantId": "KIRA_BETA_V1_CURRENT",
            "purpose": "TESTING", "workspaceId": "test-doesnotexist000000000000",
        })
        assert status == 404
        assert body["error"]["code"] == "unknown_workspace"
        assert "Traceback" not in json.dumps(body)

    def test_invalid_json_body_handled_without_crash(self, server):
        req = urllib.request.Request(
            server.base_url + "/api/sessions", data=b"not json at all",
            method="POST", headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                status, body = r.status, json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            status, body = e.code, json.loads(e.read().decode("utf-8"))
        assert status == 400
        assert body["error"]["code"] == "invalid_request"

    def test_not_found_route(self, server):
        status, body = _http_get(server.base_url + "/api/does-not-exist")
        assert status == 404

    def test_shutdown_endpoint(self, tmp_path):
        transport = _transport(tmp_path)
        srv = server_mod.ReactCharacterLabServer(transport, port=0)
        srv.start()
        status, body = _http_post(srv.base_url + "/shutdown")
        assert status == 200
        srv.shutdown()


class TestMemoryStateTransportDirect:
    def test_get_memory_returns_workspace_scoped_causal(self, tmp_path):
        transport = _transport(tmp_path)
        ws, session = _new_session(transport)
        transport.send_message({"sessionId": session["sessionId"], "text": "Привет"})
        data = transport.get_memory(ws["workspaceId"])
        assert data["workspaceId"] == ws["workspaceId"]
        assert data["causalOrder"] == "seq"
        assert data["eventCount"] >= 2
        seqs = [e["seq"] for e in data["events"] if e["seq"] is not None]
        assert seqs == sorted(seqs)

    def test_get_runtime_state_returns_domains(self, tmp_path):
        transport = _transport(tmp_path)
        ws, _ = _new_session(transport)
        data = transport.get_runtime_state(ws["workspaceId"])
        assert set(data["domainsActive"]) == {"FACT", "RELATIONSHIP", "PSYCHOLOGY"}
        assert data["currentCount"] == 0

    def test_set_adjust_remove_through_transport(self, tmp_path):
        transport = _transport(tmp_path)
        ws, _ = _new_session(transport)
        entry = transport.set_runtime_state({
            "workspaceId": ws["workspaceId"], "domain": "RELATIONSHIP",
            "key": "andrey.trust", "value": "30",
        })
        assert entry["valueInt"] == 30
        adjusted = transport.adjust_runtime_state({
            "workspaceId": ws["workspaceId"], "domain": "RELATIONSHIP",
            "key": "andrey.trust", "delta": 10,
        })
        assert adjusted["valueInt"] == 40
        removed = transport.remove_runtime_state({
            "workspaceId": ws["workspaceId"], "domain": "RELATIONSHIP", "key": "andrey.trust",
        })
        assert removed["value"] == "" and removed["valueInt"] is None

    def test_invalid_domain_rejected(self, tmp_path):
        transport = _transport(tmp_path)
        ws, _ = _new_session(transport)
        with pytest.raises(ReactTransportError) as exc_info:
            transport.set_runtime_state({
                "workspaceId": ws["workspaceId"], "domain": "BOGUS", "key": "k", "value": "v",
            })
        assert exc_info.value.code == "invalid_domain"
        assert exc_info.value.status == 400

    def test_invalid_delta_rejected(self, tmp_path):
        transport = _transport(tmp_path)
        ws, _ = _new_session(transport)
        with pytest.raises(ReactTransportError) as exc_info:
            transport.adjust_runtime_state({
                "workspaceId": ws["workspaceId"], "domain": "RELATIONSHIP",
                "key": "andrey.trust", "delta": "not-an-int",
            })
        assert exc_info.value.code == "invalid_delta"
        assert exc_info.value.status == 400

    def test_missing_value_rejected(self, tmp_path):
        transport = _transport(tmp_path)
        ws, _ = _new_session(transport)
        with pytest.raises(ReactTransportError) as exc_info:
            transport.set_runtime_state({
                "workspaceId": ws["workspaceId"], "domain": "FACT", "key": "k",
            })
        assert exc_info.value.code == "invalid_value"

    def test_adjust_after_remove_conflict(self, tmp_path):
        transport = _transport(tmp_path)
        ws, _ = _new_session(transport)
        transport.set_runtime_state({
            "workspaceId": ws["workspaceId"], "domain": "PSYCHOLOGY", "key": "stress", "value": "40",
        })
        transport.remove_runtime_state({
            "workspaceId": ws["workspaceId"], "domain": "PSYCHOLOGY", "key": "stress",
        })
        with pytest.raises(ReactTransportError) as exc_info:
            transport.adjust_runtime_state({
                "workspaceId": ws["workspaceId"], "domain": "PSYCHOLOGY", "key": "stress", "delta": 1,
            })
        assert exc_info.value.status == 409
        assert "Traceback" not in json.dumps(exc_info.value.to_json())


class TestMemoryStateHttp:
    def test_memory_and_state_over_http(self, server):
        status, ws = _http_post(server.base_url + "/api/workspaces")
        assert status == 200
        wid = ws["workspaceId"]
        status, memory = _http_get(server.base_url + f"/api/workspaces/{wid}/memory")
        assert status == 200 and memory["workspaceId"] == wid
        status, state = _http_get(server.base_url + f"/api/workspaces/{wid}/runtime-state")
        assert status == 200 and state["workspaceId"] == wid

    def test_state_mutations_over_http(self, server):
        status, ws = _http_post(server.base_url + "/api/workspaces")
        wid = ws["workspaceId"]
        status, entry = _http_post(server.base_url + "/api/runtime-state/set", {
            "workspaceId": wid, "domain": "PSYCHOLOGY", "key": "stress", "value": "40",
        })
        assert status == 200 and entry["valueInt"] == 40
        status, adjusted = _http_post(server.base_url + "/api/runtime-state/adjust", {
            "workspaceId": wid, "domain": "PSYCHOLOGY", "key": "stress", "delta": -15,
        })
        assert status == 200 and adjusted["valueInt"] == 25

    def test_invalid_domain_over_http_has_no_traceback(self, server):
        status, ws = _http_post(server.base_url + "/api/workspaces")
        wid = ws["workspaceId"]
        status, body = _http_post(server.base_url + "/api/runtime-state/set", {
            "workspaceId": wid, "domain": "BOGUS", "key": "k", "value": "v",
        })
        assert status == 400
        assert body["error"]["code"] == "invalid_domain"
        assert "Traceback" not in json.dumps(body)
