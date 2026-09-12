#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Anthropic-native DIALOGUE provider adapter -- offline contract tests.

No live provider, no external network, no real credential. Request shaping and
translation use an injected ``http_post`` (no socket); HTTP error mapping uses a
stdlib fake server on 127.0.0.1 loopback only (same pattern as
``test_local_llm_provider.py``). One-attempt and secret-safety invariants are
asserted throughout.
"""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from services.character_companion.anthropic_provider import (
    ANTHROPIC_VERSION,
    DEFAULT_MAX_TOKENS,
    AnthropicProviderConfig,
    AnthropicProviderError,
    build_anthropic_provider_factory,
)
from services.character_companion.credentials import InMemoryCredentialVault
from services.character_companion.provider_registry import (
    CAP_CLOUD,
    CAP_DIALOGUE,
    KIND_CLOUD,
    ROLE_DIALOGUE,
    TRANSPORT_ANTHROPIC_NATIVE,
    TRANSPORT_FAKE,
    TRANSPORT_OLLAMA_NATIVE,
    TRANSPORT_OPENAI_COMPAT,
    ProviderRegistryError,
    get_provider,
    require_model_supported,
)
from services.character_companion.provider_resolution import (
    CompanionConfigError,
    _factory_for,
    resolve_dialogue_provider_factory,
)
from services.character_companion.settings import CompanionSettings, RoleAssignment

KEY = "sk-ant-test-secret-123456"
TEST_SECRET = "TEST_SECRET_DO_NOT_LEAK_12345"

MESSAGES = [
    {"role": "system", "content": "СИСТЕМА: грунд-промпт уже собран рантаймом."},
    {"role": "user", "content": "Первое сообщение пользователя."},
    {"role": "assistant", "content": "Прошлый ответ персонажа."},
    {"role": "user", "content": "Второе сообщение пользователя."},
]


class FakeHttp:
    """Injected transport seam. Captures every call; never opens a socket."""

    def __init__(self, response=None, raises=None):
        self.calls = []
        self._response = response if response is not None else {"content": [{"type": "text", "text": "ok"}]}
        self._raises = raises

    def __call__(self, url, payload, headers, timeout_s):
        self.calls.append({"url": url, "payload": payload, "headers": dict(headers), "timeout_s": timeout_s})
        if self._raises is not None:
            raise self._raises
        return self._response


def _factory(http, model="claude-sonnet-5", api_key=KEY, base_url="https://api.anthropic.com"):
    cfg = AnthropicProviderConfig(provider_id="anthropic", model=model, base_url=base_url)
    return build_anthropic_provider_factory(cfg, api_key=api_key, http_post=http)


def _vault_with_key():
    vault = InMemoryCredentialVault()
    vault.store("anthropic", KEY)
    return vault


def _sentinel_factory():
    return lambda recorder: (lambda m: "FAKE-SHOULD-NOT-BE-USED")


def _resolve(provider_id="anthropic", model_id="claude-sonnet-5", *, vault=None, http_cloud=None):
    settings = CompanionSettings(roles={ROLE_DIALOGUE: RoleAssignment(provider_id, model_id)})
    vault = vault if vault is not None else _vault_with_key()
    return _factory_for(
        settings, vault, provider_id, model_id,
        fake_factory=_sentinel_factory(),
        http_post_cloud=http_cloud,
    )


class _FakeAnthropic(BaseHTTPRequestHandler):
    mode = "ok"
    calls = 0

    def log_message(self, *args):  # silence request logging
        pass

    def do_POST(self):
        type(self).calls += 1
        length = int(self.headers.get("Content-Length", 0) or 0)
        self.rfile.read(length)
        self._serve(type(self).mode)

    def _serve(self, mode):
        if mode == "ok":
            self._json(200, {"content": [{"type": "text", "text": "ответ модели"}]})
        elif mode == "auth":
            self._json(401, {"type": "error", "error": {"type": "authentication_error", "message": "bad key"}})
        elif mode == "rate":
            self._json(429, {"type": "error", "error": {"type": "rate_limit_error", "message": "slow down"}})
        elif mode == "http500":
            self._json(500, {"type": "error", "error": {"type": "api_error", "message": "boom"}})
        elif mode == "badjson":
            self._raw(200, b"this is not json")
        elif mode == "empty_content":
            self._json(200, {"content": []})
        elif mode == "tool_use":
            self._json(200, {"content": [{"type": "tool_use", "name": "calc", "input": {}}]})
        elif mode == "auth_secret":
            self._json(401, {"type": "error", "error": {"type": "authentication_error", "message": f"bad key {TEST_SECRET}"}})
        elif mode == "error_json_secret":
            self._json(400, {"type": "error", "error": {"type": "invalid_request_error", "message": "bad request", "details": {"secret": TEST_SECRET}}})
        elif mode == "timeout":
            time.sleep(2)
            self._json(200, {"content": [{"type": "text", "text": "late"}]})

    def _json(self, code, obj):
        self._raw(code, json.dumps(obj).encode("utf-8"))

    def _raw(self, code, body):
        self.send_response(code)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture
def fake_anthropic():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _FakeAnthropic)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    _FakeAnthropic.calls = 0
    host, port = server.server_address
    yield f"http://127.0.0.1:{port}"
    server.shutdown()
    server.server_close()


def _live_provider(base_url, timeout_s=60.0):
    """Adapter using the REAL default HTTP transport (no injection)."""
    cfg = AnthropicProviderConfig(provider_id="anthropic", model="claude-sonnet-5", base_url=base_url, timeout_s=timeout_s)
    return build_anthropic_provider_factory(cfg, api_key=KEY)


def _free_port():
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


# ------------------------------------------------------------- registry
def test_registry_has_anthropic_provider():
    entry = get_provider("anthropic")
    assert entry.provider_id == "anthropic"
    assert entry.display_name == "Anthropic (Claude)"
    assert entry.kind == KIND_CLOUD
    assert entry.transport == TRANSPORT_ANTHROPIC_NATIVE
    assert entry.credential_required is True
    assert entry.default_base_url == "https://api.anthropic.com"
    assert entry.default_model == "claude-sonnet-5"


def test_anthropic_models_support_dialogue_and_cloud():
    entry = get_provider("anthropic")
    sonnet = entry.get_model("claude-sonnet-5")
    haiku = entry.get_model("claude-haiku-4-5-20251001")
    for model in (sonnet, haiku):
        assert model is not None
        assert CAP_DIALOGUE in model.capabilities
        assert CAP_CLOUD in model.capabilities
        assert model.supports_role(ROLE_DIALOGUE)


def test_anthropic_default_model_is_sonnet():
    entry = get_provider("anthropic")
    assert entry.default_model_for_role(ROLE_DIALOGUE) == "claude-sonnet-5"
    assert entry.model_catalog == ("claude-sonnet-5", "claude-haiku-4-5-20251001")


def test_invalid_anthropic_model_rejected():
    with pytest.raises(ProviderRegistryError) as exc:
        require_model_supported("anthropic", "claude-opus-4", ROLE_DIALOGUE)
    assert exc.value.code == "unknown_model"


# ------------------------------------------------------------- role resolution
def test_role_resolution_sonnet():
    http = FakeHttp()
    factory = _resolve(model_id="claude-sonnet-5", http_cloud=http)
    out = factory(None)(MESSAGES)
    assert out == "ok"
    assert len(http.calls) == 1
    assert http.calls[0]["url"] == "https://api.anthropic.com/v1/messages"
    assert http.calls[0]["payload"]["model"] == "claude-sonnet-5"


def test_role_resolution_haiku():
    http = FakeHttp()
    factory = _resolve(model_id="claude-haiku-4-5-20251001", http_cloud=http)
    factory(None)(MESSAGES)
    assert http.calls[0]["payload"]["model"] == "claude-haiku-4-5-20251001"


def test_no_fallback_on_invalid_anthropic_model():
    with pytest.raises(CompanionConfigError) as exc:
        _resolve(model_id="claude-opus-4")
    assert exc.value.code == "unknown_model"


def test_resolve_dialogue_provider_factory_anthropic():
    settings = CompanionSettings(roles={ROLE_DIALOGUE: RoleAssignment("anthropic", "claude-sonnet-5")})
    vault = _vault_with_key()
    http = FakeHttp()
    factory = resolve_dialogue_provider_factory(
        settings, vault, fake_factory=_sentinel_factory(), http_post_cloud=http,
    )
    assert factory is not None
    assert factory(None)(MESSAGES) == "ok"
    assert len(http.calls) == 1


# ------------------------------------------------------------- request translation
def test_request_translation_system_user_assistant_user():
    http = FakeHttp()
    _factory(http)(None)(MESSAGES)
    payload = http.calls[0]["payload"]
    assert payload["system"] == "СИСТЕМА: грунд-промпт уже собран рантаймом."
    assert payload["messages"] == [
        {"role": "user", "content": "Первое сообщение пользователя."},
        {"role": "assistant", "content": "Прошлый ответ персонажа."},
        {"role": "user", "content": "Второе сообщение пользователя."},
    ]


def test_no_system_message_omits_system_key():
    http = FakeHttp()
    messages = [
        {"role": "user", "content": "Первый."},
        {"role": "assistant", "content": "Ответ."},
        {"role": "user", "content": "Второй."},
    ]
    _factory(http)(None)(messages)
    payload = http.calls[0]["payload"]
    assert "system" not in payload
    assert payload["messages"] == messages


def test_multiple_system_messages_joined_with_blank_line():
    http = FakeHttp()
    messages = [
        {"role": "system", "content": "Блок A"},
        {"role": "system", "content": "Блок B"},
        {"role": "user", "content": "Пользователь."},
    ]
    _factory(http)(None)(messages)
    assert http.calls[0]["payload"]["system"] == "Блок A\n\nБлок B"
    assert http.calls[0]["payload"]["messages"] == [{"role": "user", "content": "Пользователь."}]


def test_unsupported_role_fails_closed():
    http = FakeHttp()
    with pytest.raises(AnthropicProviderError) as exc:
        _factory(http)(None)([{"role": "tool", "content": "x"}, {"role": "user", "content": "u"}])
    assert exc.value.code == "provider_failed"
    assert http.calls == []


def test_empty_body_fails_closed():
    http = FakeHttp()
    with pytest.raises(AnthropicProviderError) as exc:
        _factory(http)(None)([{"role": "system", "content": "only system"}])
    assert exc.value.code == "provider_failed"
    assert http.calls == []


# ------------------------------------------------------------- exact request basics
def test_request_basics_endpoint_headers_model_max_tokens():
    http = FakeHttp()
    _factory(http)(None)(MESSAGES)
    call = http.calls[0]
    assert call["url"] == "https://api.anthropic.com/v1/messages"
    assert call["headers"]["Authorization"] == f"Bearer {KEY}"
    assert call["headers"]["anthropic-version"] == ANTHROPIC_VERSION
    assert call["payload"]["model"] == "claude-sonnet-5"
    assert call["payload"]["max_tokens"] == DEFAULT_MAX_TOKENS == 1024
    # minimal request: no unrequested fields
    assert set(call["payload"]) == {"model", "max_tokens", "system", "messages"}
    assert call["timeout_s"] > 0


def test_request_has_no_stream_tools_temperature_top_p():
    http = FakeHttp()
    _factory(http)(None)(MESSAGES)
    payload = http.calls[0]["payload"]
    for forbidden in ("stream", "tools", "temperature", "top_p", "thinking", "response_format"):
        assert forbidden not in payload


# ------------------------------------------------------------- response normalization
def test_response_normalization_exact_str():
    http = FakeHttp(response={"content": [{"type": "text", "text": "Привет, Кира!"}]})
    assert _factory(http)(None)(MESSAGES) == "Привет, Кира!"


def test_response_with_model_identifier_does_not_break_parsing():
    http = FakeHttp(response={
        "id": "msg_01", "type": "message", "role": "assistant",
        "model": "claude-sonnet-5", "stop_reason": "end_turn",
        "content": [{"type": "text", "text": "hi"}],
    })
    assert _factory(http)(None)(MESSAGES) == "hi"


def test_response_multiple_text_blocks_joined():
    http = FakeHttp(response={"content": [
        {"type": "text", "text": "a"},
        {"type": "text", "text": "b"},
    ]})
    assert _factory(http)(None)(MESSAGES) == "a\nb"


def test_response_blank_text_fails_closed():
    http = FakeHttp(response={"content": [{"type": "text", "text": "   "}]})
    with pytest.raises(AnthropicProviderError) as exc:
        _factory(http)(None)(MESSAGES)
    assert exc.value.code == "provider_failed"


def test_response_missing_content_fails_closed():
    http = FakeHttp(response={"id": "msg", "model": "claude-sonnet-5"})
    with pytest.raises(AnthropicProviderError) as exc:
        _factory(http)(None)(MESSAGES)
    assert exc.value.code == "provider_failed"


def test_response_non_text_block_fails_closed():
    http = FakeHttp(response={"content": [{"type": "tool_use", "name": "calc", "input": {}}]})
    with pytest.raises(AnthropicProviderError) as exc:
        _factory(http)(None)(MESSAGES)
    assert exc.value.code == "provider_failed"
    assert "unsupported content block" in exc.value.message


# ------------------------------------------------------------- missing credential
def test_missing_credential_factory():
    cfg = AnthropicProviderConfig(provider_id="anthropic", model="claude-sonnet-5", base_url="https://api.anthropic.com")
    with pytest.raises(AnthropicProviderError) as exc:
        build_anthropic_provider_factory(cfg, api_key="   ")
    assert exc.value.code == "missing_credential"


def test_missing_credential_resolution():
    empty_vault = InMemoryCredentialVault()
    with pytest.raises(CompanionConfigError) as exc:
        _resolve(vault=empty_vault)
    assert exc.value.code == "missing_credential"


# ------------------------------------------------------------- HTTP errors (real transport, loopback only)
@pytest.mark.parametrize("mode,expected", [
    ("auth", "authentication failed"),
    ("rate", "rate limit"),
    ("http500", "service unavailable"),
])
def test_http_error_maps_to_provider_failed(fake_anthropic, mode, expected):
    _FakeAnthropic.mode = mode
    with pytest.raises(AnthropicProviderError) as exc:
        _live_provider(fake_anthropic)(None)(MESSAGES)
    assert exc.value.code == "provider_failed"
    assert expected in exc.value.message
    assert _FakeAnthropic.calls == 1


def test_malformed_json_maps_to_provider_failed(fake_anthropic):
    _FakeAnthropic.mode = "badjson"
    with pytest.raises(AnthropicProviderError) as exc:
        _live_provider(fake_anthropic)(None)(MESSAGES)
    assert exc.value.code == "provider_failed"
    assert "invalid JSON" in exc.value.message
    assert _FakeAnthropic.calls == 1


def test_empty_content_maps_to_provider_failed(fake_anthropic):
    _FakeAnthropic.mode = "empty_content"
    with pytest.raises(AnthropicProviderError) as exc:
        _live_provider(fake_anthropic)(None)(MESSAGES)
    assert exc.value.code == "provider_failed"
    assert _FakeAnthropic.calls == 1


def test_non_text_content_block_via_transport(fake_anthropic):
    _FakeAnthropic.mode = "tool_use"
    with pytest.raises(AnthropicProviderError) as exc:
        _live_provider(fake_anthropic)(None)(MESSAGES)
    assert exc.value.code == "provider_failed"
    assert _FakeAnthropic.calls == 1


def test_timeout_maps_to_provider_unavailable(fake_anthropic):
    _FakeAnthropic.mode = "timeout"
    with pytest.raises(AnthropicProviderError) as exc:
        _live_provider(fake_anthropic, timeout_s=0.3)(None)(MESSAGES)
    assert exc.value.code == "provider_unavailable"


def test_connection_refused_maps_to_provider_unavailable():
    dead = f"http://127.0.0.1:{_free_port()}"
    with pytest.raises(AnthropicProviderError) as exc:
        _live_provider(dead)(None)(MESSAGES)
    assert exc.value.code == "provider_unavailable"


def test_live_transport_ok_roundtrip(fake_anthropic):
    _FakeAnthropic.mode = "ok"
    out = _live_provider(fake_anthropic)(None)(MESSAGES)
    assert out == "ответ модели"
    assert _FakeAnthropic.calls == 1


# ------------------------------------------------------------- one-attempt semantics
def test_one_attempt_on_success():
    http = FakeHttp()
    _factory(http)(None)(MESSAGES)
    assert len(http.calls) == 1


def test_one_attempt_on_failure_no_retry():
    http = FakeHttp(response={"content": []})  # bad response, but reachable
    with pytest.raises(AnthropicProviderError):
        _factory(http)(None)(MESSAGES)
    assert len(http.calls) == 1


# ------------------------------------------------------------- secret safety
def test_secret_not_in_error_text():
    http = FakeHttp(response={"content": []})
    with pytest.raises(AnthropicProviderError) as exc:
        _factory(http)(None)(MESSAGES)
    assert KEY not in str(exc.value)
    assert KEY not in exc.value.message


def test_secret_not_in_recorder():
    http = FakeHttp()
    events = []
    _factory(http)(events.append)(MESSAGES)
    serialized = json.dumps(events, ensure_ascii=False)
    assert KEY not in serialized
    # but the wire header IS the bearer key (correct) -- simply never recorded
    assert http.calls[0]["headers"]["Authorization"] == f"Bearer {KEY}"


def test_recorder_captures_response_model_for_provenance():
    http = FakeHttp(response={"model": "claude-sonnet-5", "content": [{"type": "text", "text": "hi"}]})
    events = []
    _factory(http)(events.append)(MESSAGES)
    response_events = [e for e in events if e["event"] == "response"]
    assert response_events and response_events[0]["data"]["model"] == "claude-sonnet-5"


# ------------------------------------------------------------- existing-provider regression
def test_existing_providers_unaffected():
    assert get_provider("openai").transport == TRANSPORT_OPENAI_COMPAT
    assert get_provider("qwen").transport == TRANSPORT_OPENAI_COMPAT
    assert get_provider("deepseek").transport == TRANSPORT_OPENAI_COMPAT
    assert get_provider("local").transport == TRANSPORT_OLLAMA_NATIVE
    assert get_provider("fake").transport == TRANSPORT_FAKE
    assert get_provider("deepseek").model_catalog == ("deepseek-v4-pro", "deepseek-v4-flash")
    assert get_provider("openai").default_model == "gpt-4o-mini"
    assert get_provider("qwen").default_model == "qwen-plus"
    assert get_provider("local").default_model == "llama3"


# ------------------------------------------------------------- adversarial secret-reflection
@pytest.mark.parametrize("mode", ["auth_secret", "error_json_secret"])
def test_http_error_body_secret_never_surfaced(fake_anthropic, mode):
    _FakeAnthropic.mode = mode
    with pytest.raises(AnthropicProviderError) as exc:
        _live_provider(fake_anthropic)(None)(MESSAGES)
    assert exc.value.code == "provider_failed"
    assert TEST_SECRET not in exc.value.message
    assert TEST_SECRET not in str(exc.value)
    assert _FakeAnthropic.calls == 1


def test_success_response_arbitrary_secret_echo_not_recorded():
    http = FakeHttp(response={"content": [{"type": "text", "text": "ok"}], "provider_echo": TEST_SECRET})
    events = []
    out = _factory(http)(events.append)(MESSAGES)
    assert out == "ok"
    assert TEST_SECRET not in json.dumps(events, ensure_ascii=False)
    assert len(http.calls) == 1


def test_success_response_model_secret_echo_not_recorded():
    http = FakeHttp(response={"content": [{"type": "text", "text": "ok"}], "model": f"claude-sonnet-5-{TEST_SECRET}"})
    events = []
    out = _factory(http)(events.append)(MESSAGES)
    assert out == "ok"
    assert TEST_SECRET not in json.dumps(events, ensure_ascii=False)
    assert len(http.calls) == 1


def test_normal_safe_model_recorder_allowlist_only():
    http = FakeHttp(response={
        "id": "msg_01", "type": "message", "model": "claude-sonnet-5",
        "stop_reason": "end_turn", "content": [{"type": "text", "text": "ok"}],
        "provider_echo": "arbitrary", "usage": {"input_tokens": 5},
    })
    events = []
    _factory(http)(events.append)(MESSAGES)
    response_events = [e for e in events if e["event"] == "response"]
    assert response_events
    data = response_events[0]["data"]
    assert data == {"model": "claude-sonnet-5"}
    for key in ("content", "id", "stop_reason", "provider_echo", "usage", "type"):
        assert key not in data


def test_non_dict_response_list_fails_closed():
    http = FakeHttp(response=[])
    with pytest.raises(AnthropicProviderError) as exc:
        _factory(http)(None)(MESSAGES)
    assert exc.value.code == "provider_failed"
    assert len(http.calls) == 1


def test_non_dict_response_string_fails_closed():
    http = FakeHttp(response="not a dict")
    with pytest.raises(AnthropicProviderError) as exc:
        _factory(http)(None)(MESSAGES)
    assert exc.value.code == "provider_failed"
    assert len(http.calls) == 1

