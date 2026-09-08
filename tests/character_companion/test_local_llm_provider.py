#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LOCAL LLM PROVIDER V1 -- adapter contract.

Real localhost HTTP is exercised through a stdlib fake Ollama-shaped server;
message-shaping / loopback-policy checks use an injected ``http_post``. No
external network, no credentials, no model download.
"""

from __future__ import annotations

import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from services.character_companion.local_provider import (
    DEFAULT_LOCAL_MODEL,
    LocalLLMConfig,
    LocalLLMProviderError,
    assert_loopback_url,
    build_local_llm_provider_factory,
    resolve_companion_provider_factory,
)

MESSAGES = [
    {"role": "system", "content": "СИСТЕМА: грунд-промпт уже собран рантаймом."},
    {"role": "user", "content": "Первое сообщение пользователя."},
    {"role": "assistant", "content": "Прошлый ответ персонажа."},
    {"role": "user", "content": "Второе сообщение пользователя."},
]


def _capturing_post(reply="ответ локальной модели", *, box):
    def http_post(url, payload, timeout_s):
        box.update(url=url, payload=payload, timeout_s=timeout_s)
        return {"message": {"role": "assistant", "content": reply}, "done": True}
    return http_post


# ------------------------------------------------------ 1..4 request shaping
def test_01_provider_accepts_existing_provider_request_list():
    box = {}
    factory = build_local_llm_provider_factory(
        LocalLLMConfig(model="qwen2"), http_post=_capturing_post(box=box)
    )
    out = factory(None)(MESSAGES)
    assert out == "ответ локальной модели"
    assert box["payload"]["messages"] is MESSAGES               # passed through, not rebuilt


def test_02_message_order_preserved():
    box = {}
    build_local_llm_provider_factory(LocalLLMConfig(), http_post=_capturing_post(box=box))(None)(MESSAGES)
    assert [m["role"] for m in box["payload"]["messages"]] == ["system", "user", "assistant", "user"]
    assert box["payload"]["messages"] == MESSAGES
    assert box["payload"]["stream"] is False


def test_03_model_identifier_comes_from_config():
    box = {}
    build_local_llm_provider_factory(
        LocalLLMConfig(model="my-local-model:latest"), http_post=_capturing_post(box=box)
    )(None)(MESSAGES)
    assert box["payload"]["model"] == "my-local-model:latest"
    # env-driven default is configurable, not hardcoded architecture
    assert LocalLLMConfig.from_env({}).model == DEFAULT_LOCAL_MODEL
    assert LocalLLMConfig.from_env({"LOCAL_LLM_MODEL": "llama3.1"}).model == "llama3.1"


def test_04_configured_base_url_is_used():
    box = {}
    build_local_llm_provider_factory(
        LocalLLMConfig(base_url="http://127.0.0.1:9999"), http_post=_capturing_post(box=box)
    )(None)(MESSAGES)
    assert box["url"] == "http://127.0.0.1:9999/api/chat"


# ------------------------------------------------------ 5..9 loopback policy
@pytest.mark.parametrize("url", [
    "http://localhost:11434",
    "http://127.0.0.1:11434",
    "http://[::1]:11434",
    "https://localhost:1234",
])
def test_05_06_07_loopback_hosts_accepted(url):
    assert assert_loopback_url(url) == url
    build_local_llm_provider_factory(LocalLLMConfig(base_url=url), http_post=_capturing_post(box={}))


@pytest.mark.parametrize("url", [
    "http://example.com:11434",
    "http://api.openai.com/v1",
    "http://8.8.8.8:11434",
    "http://192.168.1.50:11434",
    "http://ollama.internal:11434",
])
def test_08_09_remote_endpoints_rejected(url):
    with pytest.raises(LocalLLMProviderError) as exc:
        assert_loopback_url(url)
    assert exc.value.code == "provider_failed"
    with pytest.raises(LocalLLMProviderError):
        LocalLLMConfig(base_url=url)                       # config construction fails closed
    with pytest.raises(LocalLLMProviderError):
        LocalLLMConfig.from_env({"LOCAL_LLM_BASE_URL": url})


def test_10_no_api_key_required(monkeypatch):
    for var in ("DEEPSEEK_API_KEY", "OPENAI_API_KEY", "LOCAL_LLM_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    box = {}
    build_local_llm_provider_factory(LocalLLMConfig(), http_post=_capturing_post(box=box))(None)(MESSAGES)
    assert "api_key" not in box["payload"] and "Authorization" not in json.dumps(box["payload"])


# ------------------------------------------------------ 11..17 real HTTP fail-closed
class _FakeOllama(BaseHTTPRequestHandler):
    mode = "ok"

    def log_message(self, *a):  # silence
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        _ = self.rfile.read(length)
        if _FakeOllama.mode == "timeout":
            time.sleep(1.5)
        bodies = {
            "ok": (200, json.dumps({"message": {"role": "assistant", "content": "Привет из локали."}, "done": True})),
            "malformed": (200, "{not json"),
            "missing": (200, json.dumps({"done": True})),
            "blank": (200, json.dumps({"message": {"role": "assistant", "content": "   "}})),
            "http500": (500, json.dumps({"error": "boom"})),
            "timeout": (200, json.dumps({"message": {"content": "late"}})),
        }
        status, payload = bodies.get(_FakeOllama.mode, bodies["ok"])
        raw = payload.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def _free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


@pytest.fixture
def fake_ollama():
    port = _free_port()
    srv = ThreadingHTTPServer(("127.0.0.1", port), _FakeOllama)
    t = threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    t.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        _FakeOllama.mode = "ok"
        srv.shutdown()
        srv.server_close()


def _provider(base_url, *, timeout_s=5.0):
    return build_local_llm_provider_factory(
        LocalLLMConfig(base_url=base_url, model="llama3", timeout_s=timeout_s)
    )(None)


def test_11_successful_local_response_maps_to_plain_text(fake_ollama):
    _FakeOllama.mode = "ok"
    assert _provider(fake_ollama)(MESSAGES) == "Привет из локали."


def test_12_malformed_json_rejected(fake_ollama):
    _FakeOllama.mode = "malformed"
    with pytest.raises(LocalLLMProviderError) as exc:
        _provider(fake_ollama)(MESSAGES)
    assert exc.value.code == "provider_failed" and "invalid JSON" in exc.value.message


def test_13_missing_content_rejected(fake_ollama):
    _FakeOllama.mode = "missing"
    with pytest.raises(LocalLLMProviderError) as exc:
        _provider(fake_ollama)(MESSAGES)
    assert "no message content" in exc.value.message


def test_14_blank_content_rejected(fake_ollama):
    _FakeOllama.mode = "blank"
    with pytest.raises(LocalLLMProviderError) as exc:
        _provider(fake_ollama)(MESSAGES)
    assert "blank message content" in exc.value.message


def test_15_http_non_2xx_mapped_to_bounded_error(fake_ollama):
    _FakeOllama.mode = "http500"
    with pytest.raises(LocalLLMProviderError) as exc:
        _provider(fake_ollama)(MESSAGES)
    assert exc.value.code == "provider_failed" and "HTTP 500" in exc.value.message


def test_16_connection_refused_maps_to_provider_unavailable():
    dead = f"http://127.0.0.1:{_free_port()}"       # nothing listening
    with pytest.raises(LocalLLMProviderError) as exc:
        _provider(dead)(MESSAGES)
    assert exc.value.code == "provider_unavailable"


def test_17_timeout_maps_to_provider_unavailable(fake_ollama):
    _FakeOllama.mode = "timeout"
    with pytest.raises(LocalLLMProviderError) as exc:
        _provider(fake_ollama, timeout_s=0.3)(MESSAGES)
    assert exc.value.code == "provider_unavailable"


# ------------------------------------------------------ 18..20 no retry / fallback / rebuild
def test_18_no_retry_single_attempt(fake_ollama):
    calls = {"n": 0}
    orig = _FakeOllama.do_POST

    def counting(self):
        calls["n"] += 1
        return orig(self)

    _FakeOllama.mode = "http500"
    _FakeOllama.do_POST = counting
    try:
        with pytest.raises(LocalLLMProviderError):
            _provider(fake_ollama)(MESSAGES)
    finally:
        _FakeOllama.do_POST = orig
    assert calls["n"] == 1


def test_19_no_cloud_fallback():
    # 'local' mode never returns the fake factory, and a failing local call
    # never silently produces a cloud/fake answer.
    sentinel = lambda recorder: (lambda m: "FAKE-SHOULD-NOT-BE-USED")
    local_factory = resolve_companion_provider_factory(
        {"COMPANION_PROVIDER": "local", "LOCAL_LLM_BASE_URL": f"http://127.0.0.1:{_free_port()}"},
        fake_factory=sentinel,
    )
    assert local_factory is not sentinel
    with pytest.raises(LocalLLMProviderError) as exc:
        local_factory(None)(MESSAGES)
    assert exc.value.code == "provider_unavailable"
    # unknown mode is a hard error, never a fallback
    with pytest.raises(LocalLLMProviderError):
        resolve_companion_provider_factory({"COMPANION_PROVIDER": "deepseek"}, fake_factory=sentinel)


def test_20_no_prompt_reconstruction(fake_ollama):
    _FakeOllama.mode = "ok"
    captured = {}
    orig = _FakeOllama.do_POST

    def capture(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        captured["body"] = json.loads(self.rfile.read(length).decode("utf-8"))
        # re-serve a canned ok
        raw = json.dumps({"message": {"content": "ok"}}).encode()
        self.send_response(200); self.send_header("Content-Length", str(len(raw))); self.end_headers()
        self.wfile.write(raw)

    _FakeOllama.do_POST = capture
    try:
        _provider(fake_ollama)(MESSAGES)
    finally:
        _FakeOllama.do_POST = orig
    # exactly the messages we passed -- no injected system prompt, no grounding,
    # no memory/epistemic/scene layers added by the provider
    assert captured["body"]["messages"] == MESSAGES
    assert set(captured["body"]) == {"model", "messages", "stream"}


def test_fake_mode_resolves_to_the_supplied_fake_factory():
    marker = lambda recorder: (lambda m: "FAKE")
    assert resolve_companion_provider_factory({}, fake_factory=marker) is marker
    assert resolve_companion_provider_factory({"COMPANION_PROVIDER": "FAKE"}, fake_factory=marker) is marker
