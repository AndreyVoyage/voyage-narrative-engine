#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CHARACTER COMPANION APP MVP V1 -- transport roundtrip.

Dict-level ``CompanionTransport`` roundtrip plus one real loopback HTTP
roundtrip through ``tools/character_companion_server.py``. Offline fake
provider only; no external network.
"""

from __future__ import annotations

import json
import socket
import urllib.request
from pathlib import Path

import pytest

from services.character_companion import CompanionService, CompanionTransport
from services.character_companion.transport import CompanionTransportError

from tests.character_companion.conftest import (
    ACCEPTED_ROOT,
    FAKE_PROVIDER_INFO,
    make_fake_factory,
)


def _transport(tmp_path, *, data_root=None, factory=None) -> CompanionTransport:
    service = CompanionService(
        acceptance_root=ACCEPTED_ROOT,
        data_root=data_root or (tmp_path / "companion-data"),
        provider_factory=factory or make_fake_factory("Ответ фейкового провайдера."),
        provider_info=FAKE_PROVIDER_INFO,
    )
    return CompanionTransport(service)


# --------------------------------------------------- dict-level roundtrip (21..26)
def test_21_to_26_full_dict_roundtrip(tmp_path):
    t = _transport(tmp_path)

    chars = t.list_characters()                                        # 21
    assert [c["characterId"] for c in chars["characters"]] == ["kira"]
    assert chars["characters"][0]["packageId"]

    created = t.create_session({"characterId": "kira"})                # 22
    sid = created["sessionId"]
    assert created["purpose"] == "COMPANION" and created["label"]

    sessions = t.list_sessions("kira")                                 # 23
    assert [s["sessionId"] for s in sessions["sessions"]] == [sid]

    empty = t.get_messages(sid)                                        # 24
    assert empty == {"sessionId": sid, "messages": []}

    sent = t.send_message({"sessionId": sid, "text": "Привет, Кира."})  # 25
    assert sent["response"] == "Ответ фейкового провайдера."
    assert [(m["role"], m["text"]) for m in sent["messages"]] == [
        ("user", "Привет, Кира."), ("character", "Ответ фейкового провайдера."),
    ]

    hist = t.get_messages(sid)                                        # 26
    assert [m["role"] for m in hist["messages"]] == ["user", "character"]
    assert all(isinstance(m["seq"], int) for m in hist["messages"])


def test_27_28_29_restart_then_continue(tmp_path):
    data_root = tmp_path / "companion-data"
    t1 = _transport(tmp_path, data_root=data_root)
    sid = t1.create_session({"characterId": "kira"})["sessionId"]
    t1.send_message({"sessionId": sid, "text": "Первое."})
    t1.send_message({"sessionId": sid, "text": "Второе."})
    before = t1.get_messages(sid)["messages"]
    assert len(before) == 4
    del t1

    t2 = _transport(tmp_path, data_root=data_root)                     # 27 restart
    assert sid in {s["sessionId"] for s in t2.list_sessions("kira")["sessions"]}
    assert t2.get_messages(sid)["messages"] == before                 # 28 still accessible

    t2.send_message({"sessionId": sid, "text": "Третье."})            # 29 subsequent turn
    after = t2.get_messages(sid)["messages"]
    assert len(after) == 6 and after[4]["text"] == "Третье."
    assert [m["seq"] for m in after] == sorted(m["seq"] for m in after)


def test_transport_error_mapping(tmp_path):
    t = _transport(tmp_path)
    with pytest.raises(CompanionTransportError) as e1:
        t.list_sessions("ghost")
    assert (e1.value.status, e1.value.code) == (404, "unknown_character")

    sid = t.create_session({"characterId": "kira"})["sessionId"]
    with pytest.raises(CompanionTransportError) as e2:
        t.send_message({"sessionId": sid, "text": "   "})
    assert (e2.value.status, e2.value.code) == (400, "empty_message")

    with pytest.raises(CompanionTransportError) as e3:
        t.get_messages("cmp-nope")
    assert (e3.value.status, e3.value.code) == (404, "unknown_session")


# --------------------------------------------------- real loopback HTTP roundtrip
def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _http(base, method, path, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        base + path, data=data, method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=5) as resp:  # noqa: S310 -- loopback only
        return resp.status, json.loads(resp.read().decode("utf-8"))


def test_loopback_http_smoke(tmp_path):
    from tools.character_companion_server import CompanionServer, build_transport

    data_root = tmp_path / "companion-data"
    server = CompanionServer(build_transport(data_root=data_root, response="Ответ по HTTP."),
                             port=_free_port())
    server.start()
    try:
        base = server.base_url
        status, health = _http(base, "GET", "/health")
        assert status == 200 and health["client"] == "companion"

        _, chars = _http(base, "GET", "/api/companion/characters")
        assert [c["characterId"] for c in chars["characters"]] == ["kira"]

        _, created = _http(base, "POST", "/api/companion/sessions", {"characterId": "kira"})
        sid = created["sessionId"]

        _, sessions = _http(base, "GET", f"/api/companion/characters/{sid and 'kira'}/sessions")
        assert sid in {s["sessionId"] for s in sessions["sessions"]}

        _, empty = _http(base, "GET", f"/api/companion/sessions/{sid}/messages")
        assert empty["messages"] == []

        _, sent = _http(base, "POST", "/api/companion/messages",
                        {"sessionId": sid, "text": "Привет по сети."})
        assert sent["response"] == "Ответ по HTTP."

        _, hist = _http(base, "GET", f"/api/companion/sessions/{sid}/messages")
        assert [(m["role"], m["text"]) for m in hist["messages"]] == [
            ("user", "Привет по сети."), ("character", "Ответ по HTTP."),
        ]
    finally:
        server.shutdown()


def test_loopback_http_survives_server_restart(tmp_path):
    from tools.character_companion_server import CompanionServer, build_transport

    data_root = tmp_path / "companion-data"
    port = _free_port()

    s1 = CompanionServer(build_transport(data_root=data_root), port=port)
    s1.start()
    try:
        _, created = _http(s1.base_url, "POST", "/api/companion/sessions", {"characterId": "kira"})
        sid = created["sessionId"]
        _http(s1.base_url, "POST", "/api/companion/messages", {"sessionId": sid, "text": "До перезапуска."})
    finally:
        s1.shutdown()

    s2 = CompanionServer(build_transport(data_root=data_root), port=port)
    s2.start()
    try:
        _, hist = _http(s2.base_url, "GET", f"/api/companion/sessions/{sid}/messages")
        assert [m["text"] for m in hist["messages"]][0] == "До перезапуска."
        _, sent = _http(s2.base_url, "POST", "/api/companion/messages",
                        {"sessionId": sid, "text": "После перезапуска."})
        assert sent["messages"][-1]["role"] == "character"
        assert len(sent["messages"]) == 4
    finally:
        s2.shutdown()


# --------------------------------------------------- S8B pinned-session transport
def _pinned_transport(tmp_path):
    """A CompanionTransport backed by one synthetic installed Package V1."""
    from services.character_companion.character_import import (
        CharacterPackageManagementService,
    )
    from tests.character_companion.test_session_character_pinning import (
        _resolve_ids,
        _synthetic_catalog,
        make_crp_package,
    )

    data_root = tmp_path / "companion-data"
    data_root.mkdir(parents=True, exist_ok=True)
    (tmp_path / "acceptance").mkdir(parents=True, exist_ok=True)

    src = make_crp_package(
        tmp_path, dirname="pkg", character_id="alice", release_id="v1"
    )
    package_hash, runtime_hash = _resolve_ids(src, "alice", "v1")
    CharacterPackageManagementService(data_root).import_package(src)

    service = CompanionService(
        acceptance_root=tmp_path / "acceptance",
        data_root=data_root,
        provider_factory=make_fake_factory(),
        provider_info=FAKE_PROVIDER_INFO,
        catalog=_synthetic_catalog("alice"),
    )
    transport = CompanionTransport(service)
    payload = {
        "characterId": "alice",
        "releaseId": "v1",
        "packageHash": package_hash,
        "runtimeDefinitionHash": runtime_hash,
    }
    return transport, payload


def test_pinned_session_serializes_exact_pin(tmp_path):
    transport, payload = _pinned_transport(tmp_path)
    created = transport.create_pinned_session(payload)
    assert created["characterPinStatus"] == "PINNED_V1"
    assert created["characterPinV1"] == {
        "characterId": "alice",
        "releaseId": "v1",
        "packageHash": payload["packageHash"],
        "runtimeDefinitionHash": payload["runtimeDefinitionHash"],
    }

    sessions = transport.list_sessions("alice")
    assert sessions["sessions"][0]["characterPinStatus"] == "PINNED_V1"
    assert sessions["sessions"][0]["characterPinV1"]["releaseId"] == "v1"


def test_pinned_and_legacy_status_are_explicit(tmp_path):
    transport, payload = _pinned_transport(tmp_path)
    pinned = transport.create_pinned_session(payload)
    assert pinned["characterPinStatus"] == "PINNED_V1"

    legacy = _transport(tmp_path)
    legacy_session = legacy.create_session({"characterId": "kira"})
    assert legacy_session["characterPinStatus"] == "LEGACY_UNPINNED"
    assert legacy_session["characterPinV1"] is None


def test_malformed_pin_maps_to_stable_error(tmp_path):
    transport, payload = _pinned_transport(tmp_path)
    payload = dict(payload)
    payload["packageHash"] = "not-a-sha256"
    with pytest.raises(CompanionTransportError) as exc:
        transport.create_pinned_session(payload)
    assert (exc.value.status, exc.value.code) == (400, "invalid_pin")


def test_pinned_execution_boundary_maps_errors(tmp_path):
    transport, payload = _pinned_transport(tmp_path)
    session = transport.create_pinned_session(payload)

    # S8C1: pinned send_message runs the runtime and is no longer mapped to
    # the generic pinned_execution_blocked error.
    sent = transport.send_message({"sessionId": session["sessionId"], "text": "Hi"})
    assert sent["sessionId"] == session["sessionId"]
    assert sent["response"]

    # Genuinely still-blocked pinned operations keep their stable 409 error.
    with pytest.raises(CompanionTransportError) as exc:
        transport.create_image_job(
            {"sessionId": session["sessionId"], "kind": "context"}
        )
    assert (exc.value.status, exc.value.code) == (409, "pinned_execution_blocked")
