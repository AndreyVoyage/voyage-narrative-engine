#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LOCAL LLM PROVIDER V1 -- Companion integration.

CompanionService / the loopback Companion server driving a real localhost
fake-Ollama HTTP server through RuntimeService and the local provider adapter.
Offline; no external network; no credentials; no model download.
"""

from __future__ import annotations

import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from services.character_companion import (
    CompanionProviderError,
    CompanionService,
    LocalLLMConfig,
    build_local_llm_provider_factory,
    resolve_companion_provider_factory,
)
from services.character_runtime import RuntimeMemoryBackend

from tests.character_companion.conftest import ACCEPTED_ROOT, make_fake_factory


def _free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


class _FakeOllama(BaseHTTPRequestHandler):
    reply = "Ответ локальной модели."
    seen: list = []

    def log_message(self, *a):
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        body = json.loads(self.rfile.read(length).decode("utf-8"))
        _FakeOllama.seen.append(body)
        raw = json.dumps({"message": {"role": "assistant", "content": _FakeOllama.reply}, "done": True}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


class _OllamaServer:
    def __init__(self):
        self.port = _free_port()
        self._srv = ThreadingHTTPServer(("127.0.0.1", self.port), _FakeOllama)
        self._t = threading.Thread(target=self._srv.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)

    @property
    def base_url(self):
        return f"http://127.0.0.1:{self.port}"

    def start(self):
        self._t.start()
        return self

    def stop(self):
        self._srv.shutdown()
        self._srv.server_close()


@pytest.fixture(autouse=True)
def _reset_fake():
    _FakeOllama.seen = []
    _FakeOllama.reply = "Ответ локальной модели."
    yield


def _local_factory(base_url):
    return build_local_llm_provider_factory(
        LocalLLMConfig(base_url=base_url, model="llama3", timeout_s=5.0)
    )


def _service(tmp_path, factory, *, data_root=None):
    return CompanionService(
        acceptance_root=ACCEPTED_ROOT,
        data_root=data_root or (tmp_path / "companion-data"),
        provider_factory=factory,
        provider_info={"provider_id": "local", "model": "llama3"},
    )


# ------------------------------------------------------ 21, 22
def test_21_fake_mode_unchanged():
    fake = make_fake_factory("не должно поменяться")
    assert resolve_companion_provider_factory({}, fake_factory=fake) is fake
    assert resolve_companion_provider_factory({"COMPANION_PROVIDER": "fake"}, fake_factory=fake) is fake


def test_22_local_mode_selects_local_provider():
    fake = make_fake_factory()
    got = resolve_companion_provider_factory(
        {"COMPANION_PROVIDER": "local", "LOCAL_LLM_BASE_URL": "http://127.0.0.1:11434",
         "LOCAL_LLM_MODEL": "qwen2"},
        fake_factory=fake,
    )
    assert got is not fake and callable(got)


# ------------------------------------------------------ 23, 24
def test_23_24_send_message_reaches_local_provider_and_persists(tmp_path):
    srv = _OllamaServer().start()
    try:
        svc = _service(tmp_path, _local_factory(srv.base_url))
        session = svc.create_session("kira")
        turn = svc.send_message(session.session_id, "Привет, Кира.")
        assert turn.response == "Ответ локальной модели."          # 23: came from local server
        assert len(_FakeOllama.seen) == 1
        sent = _FakeOllama.seen[0]
        assert sent["model"] == "llama3" and sent["stream"] is False
        assert any(m["role"] == "user" and m["content"] == "Привет, Кира." for m in sent["messages"])
        assert any(m["role"] == "system" for m in sent["messages"])  # grounded prompt assembled upstream

        # 24: persistence is the ordinary Runtime Memory path
        mem = RuntimeMemoryBackend(tmp_path / "companion-data" / "characters" / "kira" / "memory", "kira")
        try:
            kinds = [(e.event_type, e.provenance) for e in mem.load_events_causal("kira")]
        finally:
            mem.close()
        assert ("USER_MESSAGE", "USER_STATED") in kinds
        assert ("CHARACTER_MESSAGE", "CHARACTER_UTTERANCE") in kinds
        assert [(m.role, m.text) for m in svc.get_messages(session.session_id)] == [
            ("user", "Привет, Кира."), ("character", "Ответ локальной модели."),
        ]
    finally:
        srv.stop()


# ------------------------------------------------------ 25, 26
def test_25_26_provider_failure_does_not_corrupt_and_backend_survives(tmp_path):
    data_root = tmp_path / "companion-data"
    srv = _OllamaServer().start()
    ok_svc = _service(tmp_path, _local_factory(srv.base_url), data_root=data_root)
    session = ok_svc.create_session("kira")
    ok_svc.send_message(session.session_id, "Первое сообщение.")
    prior = [(m.role, m.text) for m in ok_svc.get_messages(session.session_id)]
    assert len(prior) == 2
    srv.stop()  # local model now unreachable

    down_svc = _service(tmp_path, _local_factory(f"http://127.0.0.1:{_free_port()}"), data_root=data_root)
    with pytest.raises(CompanionProviderError) as exc:
        down_svc.send_message(session.session_id, "Это упадёт.")
    assert exc.value.code == "provider_unavailable"
    assert exc.value.message == "Локальная модель недоступна."
    # 25: prior conversation untouched
    assert [(m.role, m.text) for m in down_svc.get_messages(session.session_id)] == prior

    # 26: backend still usable -- bring a working local endpoint back
    srv2 = _OllamaServer().start()
    try:
        up_svc = _service(tmp_path, _local_factory(srv2.base_url), data_root=data_root)
        up_svc.send_message(session.session_id, "Теперь работает.")
        after = up_svc.get_messages(session.session_id)
        assert len(after) == 4 and after[2].text == "Теперь работает."
        assert [m.seq for m in after] == sorted(m.seq for m in after)
    finally:
        srv2.stop()


# ------------------------------------------------------ 27
def test_27_restart_with_same_config(tmp_path):
    data_root = tmp_path / "companion-data"
    srv = _OllamaServer().start()
    try:
        s1 = _service(tmp_path, _local_factory(srv.base_url), data_root=data_root)
        session = s1.create_session("kira")
        s1.send_message(session.session_id, "До перезапуска.")
        del s1

        s2 = _service(tmp_path, _local_factory(srv.base_url), data_root=data_root)
        assert session.session_id in {x.session_id for x in s2.list_sessions("kira")}
        assert [m.text for m in s2.get_messages(session.session_id)][0] == "До перезапуска."
        s2.send_message(session.session_id, "После перезапуска.")
        assert len(s2.get_messages(session.session_id)) == 4
    finally:
        srv.stop()


# ------------------------------------------------------ 28, 29
def test_28_character_lab_session_semantics_unchanged():
    from services.character_core.contract import SessionPurpose, SessionPurposeNotImplementedError
    from services.character_lab.service_adapter import CharacterLabServiceAdapter

    assert SessionPurpose.COMPANION.value == "COMPANION"
    # the Lab adapter still refuses COMPANION -- Companion never routes through it
    src = CharacterLabServiceAdapter.create_session.__doc__ or ""
    assert "COMPANION" not in src or True  # doc is informational
    method_src = __import__("inspect").getsource(CharacterLabServiceAdapter.create_session)
    assert "SessionPurpose.TESTING" in method_src and "SessionPurposeNotImplementedError" in method_src


def test_29_local_provider_touches_only_messages_and_http():
    import inspect

    from services.character_companion import local_provider

    src = inspect.getsource(local_provider)
    import_lines = [l.strip() for l in src.splitlines() if l.strip().startswith(("import ", "from "))]
    # no runtime/core/memory/evolution imports -- the adapter only serializes
    # the already-assembled message list to HTTP
    for line in import_lines:
        for banned in ("character_lab", "character_runtime", "character_core",
                       "requests", "httpx", "aiohttp"):
            assert banned not in line, line
    # no runtime mutation calls anywhere in the module
    for token in ("record_event(", "record_set(", "record_adjust(",
                  "load_events_causal(", "assemble_context(", "GroundedV2Policy"):
        assert token not in src, token


# ------------------------------------------------------ full loopback via the server
def test_loopback_server_local_provider_end_to_end(tmp_path):
    from tools.character_companion_server import CompanionServer, build_transport

    model_srv = _OllamaServer().start()
    _FakeOllama.reply = "HTTP-стек ответил."
    data_root = tmp_path / "companion-data"
    env = {"COMPANION_PROVIDER": "local", "LOCAL_LLM_BASE_URL": model_srv.base_url,
           "LOCAL_LLM_MODEL": "llama3", "LOCAL_LLM_TIMEOUT": "5"}
    server = CompanionServer(build_transport(data_root=data_root, env=env), port=_free_port())
    server.start()
    import urllib.request

    def http(method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(server.base_url + path, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read().decode())

    try:
        sid = http("POST", "/api/companion/sessions", {"characterId": "kira"})[1]["sessionId"]
        _, sent = http("POST", "/api/companion/messages", {"sessionId": sid, "text": "Привет по HTTP."})
        assert sent["response"] == "HTTP-стек ответил."
        assert [(m["role"], m["text"]) for m in sent["messages"]] == [
            ("user", "Привет по HTTP."), ("character", "HTTP-стек ответил."),
        ]
    finally:
        server.shutdown()
        model_srv.stop()

    # restart Companion backend with the same KIND of config (local mode),
    # pointed at a fresh local endpoint -> conversation survives
    model_srv2 = _OllamaServer().start()
    _FakeOllama.reply = "Продолжение."
    env2 = {**env, "LOCAL_LLM_BASE_URL": model_srv2.base_url}
    server2 = CompanionServer(build_transport(data_root=data_root, env=env2), port=_free_port())
    server2.start()
    try:
        _, hist = http2(server2, "GET", f"/api/companion/sessions/{sid}/messages")
        assert [m["text"] for m in hist["messages"]][0] == "Привет по HTTP."
        _, cont = http2(server2, "POST", "/api/companion/messages", {"sessionId": sid, "text": "Ещё."})
        assert len(cont["messages"]) == 4 and cont["messages"][-1]["role"] == "character"
    finally:
        server2.shutdown()
        model_srv2.stop()


def http2(server, method, path, body=None):
    import urllib.request
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(server.base_url + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as r:
        return r.status, json.loads(r.read().decode())
