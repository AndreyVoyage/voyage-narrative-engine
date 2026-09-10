#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SECURE COMPANION DESKTOP FOUNDATIONS V1 -- credential vault, provider
registry, settings, attachment security gateway, no-silent-fallback, num_ctx.

Offline: in-memory test vault, local fake HTTP servers, no external network, no
real credentials, no provider behavioural calls."""

from __future__ import annotations

import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from services.character_companion import (
    ALL_ROLES,
    AUTHORITY_USER_ATTACHMENT_DATA,
    AttachmentError,
    AttachmentSecurityGateway,
    CloudProviderConfig,
    CompanionConfigError,
    CompanionService,
    CredentialError,
    InMemoryCredentialVault,
    LocalLLMConfig,
    RoleAssignment,
    SettingsError,
    SettingsStore,
    build_local_llm_provider_factory,
    build_openai_compat_provider_factory,
    get_provider,
    resolve_dialogue_provider_factory,
)
from services.character_companion import test_provider_connection as probe_provider_connection
from services.character_companion.settings import NUM_CTX_MAX, NUM_CTX_MIN
from services.character_runtime import RuntimeMemoryBackend

from tests.character_companion.conftest import ACCEPTED_ROOT, FAKE_PROVIDER_INFO, make_fake_factory

FAKE_KEY = "sk-test-DEADBEEF-secret-value-123456"


# ----------------------------------------------------------- helpers
def _free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


class _FakeCloud(BaseHTTPRequestHandler):
    seen_auth: list = []
    reply = "cloud ok"
    status = 200

    def log_message(self, *a):
        pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0) or 0)
        self.rfile.read(n)
        _FakeCloud.seen_auth.append(self.headers.get("Authorization"))
        body = json.dumps({"choices": [{"message": {"content": _FakeCloud.reply}}]}) \
            if _FakeCloud.status == 200 else json.dumps({"error": "bad key"})
        raw = body.encode()
        self.send_response(_FakeCloud.status)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


@pytest.fixture
def fake_cloud():
    _FakeCloud.seen_auth = []
    _FakeCloud.reply = "cloud ok"
    _FakeCloud.status = 200
    port = _free_port()
    srv = ThreadingHTTPServer(("127.0.0.1", port), _FakeCloud)
    threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        srv.shutdown(); srv.server_close()


class _FakeOllama(BaseHTTPRequestHandler):
    seen: list = []

    def log_message(self, *a):
        pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0) or 0)
        _FakeOllama.seen.append(json.loads(self.rfile.read(n).decode()))
        raw = json.dumps({"message": {"content": "local ok"}}).encode()
        self.send_response(200); self.send_header("Content-Length", str(len(raw))); self.end_headers()
        self.wfile.write(raw)


@pytest.fixture
def fake_ollama():
    _FakeOllama.seen = []
    port = _free_port()
    srv = ThreadingHTTPServer(("127.0.0.1", port), _FakeOllama)
    threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        srv.shutdown(); srv.server_close()


def _store(tmp_path):
    return SettingsStore(tmp_path)


# ============================================================ 1..5 vault
def test_01_02_04_vault_store_resolve_delete(tmp_path):
    v = InMemoryCredentialVault()
    assert not v.has("deepseek")
    meta = v.store("deepseek", FAKE_KEY)                      # 2
    assert v.has("deepseek") and v.resolve("deepseek") == FAKE_KEY
    assert meta.connected and meta.masked_tail and FAKE_KEY not in (meta.masked_tail or "")
    assert v.delete("deepseek") is True and not v.has("deepseek")  # 4
    with pytest.raises(CredentialError):
        v.resolve("deepseek")


def test_01_api_key_never_in_settings_json(tmp_path):
    store = _store(tmp_path)
    store.set_role("DIALOGUE", "deepseek", "deepseek-chat")
    store.set_local_num_ctx(8192)
    raw = store.path.read_text("utf-8")
    assert FAKE_KEY not in raw and "secret" not in raw.lower() and "authorization" not in raw.lower()
    # and the store refuses to persist a dict that smuggles a secret
    s = store.load()
    s.ui["api_key"] = FAKE_KEY
    with pytest.raises(SettingsError):
        SettingsStore(tmp_path).save(_inject_secret(s))


def _inject_secret(settings):
    # bypass from_row filtering to prove save() itself fails closed
    settings.ui = {"api_key": FAKE_KEY}
    return settings


def test_03_frontend_view_never_contains_raw_key(tmp_path):
    vault = InMemoryCredentialVault()
    vault.store("deepseek", FAKE_KEY)
    svc = _service(tmp_path, vault=vault)
    view = json.dumps(svc.settings_view(), ensure_ascii=False)
    assert FAKE_KEY not in view
    ds = next(p for p in svc.settings_view()["providers"] if p["providerId"] == "deepseek")
    assert ds["connected"] is True and ds["maskedTail"] and FAKE_KEY not in ds["maskedTail"]


def test_05_errors_and_repr_do_not_expose_key():
    v = InMemoryCredentialVault()
    v.store("openai", FAKE_KEY)
    try:
        CloudProviderConfig(provider_id="", model="x", base_url="y")
    except Exception as exc:  # noqa: BLE001
        assert FAKE_KEY not in str(exc)
    err = CredentialError("missing_credential", "no stored credential for 'openai'")
    assert FAKE_KEY not in str(err) and FAKE_KEY not in repr(err)


# ============================================================ service helper
def _service(tmp_path, *, vault=None, http_post_local=None, http_post_cloud=None, data_root=None):
    return CompanionService(
        acceptance_root=ACCEPTED_ROOT,
        data_root=data_root or (tmp_path / "cd"),
        provider_factory=make_fake_factory("fake reply"),
        provider_info=FAKE_PROVIDER_INFO,
        settings_store=SettingsStore(data_root or (tmp_path / "cd")),
        credential_vault=vault or InMemoryCredentialVault(),
        http_post_local=http_post_local,
        http_post_cloud=http_post_cloud,
    )


# ============================================================ 6..14 providers / roles / fallback
def test_06_07_08_cloud_config_uses_vault_resolved_secret(fake_cloud, tmp_path):
    for provider_id, model in (("deepseek", "deepseek-chat"), ("openai", "gpt-4o-mini"), ("qwen", "qwen-plus")):
        vault = InMemoryCredentialVault(); vault.store(provider_id, FAKE_KEY)
        store = _store(tmp_path / provider_id)
        store.set_base_url(provider_id, fake_cloud)
        store.set_role("DIALOGUE", provider_id, model)
        factory = resolve_dialogue_provider_factory(store.load(), vault, fake_factory=make_fake_factory())
        out = factory(None)([{"role": "user", "content": "hi"}])
        assert out == "cloud ok"
    assert all(a == f"Bearer {FAKE_KEY}" for a in _FakeCloud.seen_auth)


def test_09_local_requires_no_credential(fake_ollama, tmp_path):
    store = _store(tmp_path)
    store.set_base_url("local", fake_ollama)
    store.set_role("DIALOGUE", "local", "llama3")
    factory = resolve_dialogue_provider_factory(store.load(), InMemoryCredentialVault(), fake_factory=make_fake_factory())
    assert factory(None)([{"role": "user", "content": "hi"}]) == "local ok"


def test_10_missing_cloud_credential_fails_bounded(tmp_path):
    store = _store(tmp_path)
    store.set_role("DIALOGUE", "deepseek", "deepseek-chat")
    with pytest.raises(CompanionConfigError) as exc:
        resolve_dialogue_provider_factory(store.load(), InMemoryCredentialVault(), fake_factory=make_fake_factory())
    assert exc.value.code == "missing_credential" and FAKE_KEY not in exc.value.message


def test_11_no_silent_fallback_on_cloud_failure(fake_cloud, tmp_path):
    _FakeCloud.status = 500
    vault = InMemoryCredentialVault(); vault.store("deepseek", FAKE_KEY)
    svc = _service(tmp_path, vault=vault)
    svc._settings_store.set_base_url("deepseek", fake_cloud)
    svc._settings_store.set_role("DIALOGUE", "deepseek", "deepseek-chat")
    sid = svc.create_session("kira").session_id
    with pytest.raises(Exception) as exc:
        svc.send_message(sid, "привет")
    # bounded error -- NOT a fake/local/openai answer
    assert getattr(exc.value, "code", "") in ("provider_failed", "provider_unavailable")
    assert "fake reply" not in str(exc.value)
    assert svc.get_messages(sid) == ()                        # nothing persisted


def test_12_role_routing_selects_exactly_one_provider(fake_cloud, fake_ollama, tmp_path):
    vault = InMemoryCredentialVault(); vault.store("deepseek", FAKE_KEY)
    store = _store(tmp_path)
    store.set_base_url("deepseek", fake_cloud)
    store.set_base_url("local", fake_ollama)
    store.set_role("DIALOGUE", "deepseek", "deepseek-chat")
    factory = resolve_dialogue_provider_factory(store.load(), vault, fake_factory=make_fake_factory())
    factory(None)([{"role": "user", "content": "hi"}])
    assert len(_FakeCloud.seen_auth) == 1 and _FakeOllama.seen == []   # dialogue went to deepseek ONLY


def test_13_14_unsupported_role_and_unknown_provider_rejected(tmp_path):
    store = _store(tmp_path)
    with pytest.raises(SettingsError) as e1:
        store.set_role("STT", "deepseek", "x")               # deepseek doesn't support STT
    assert e1.value.code == "unsupported_role"
    with pytest.raises(SettingsError):
        store.set_role("DIALOGUE", "not-a-provider", "x")     # 14
    with pytest.raises(SettingsError):
        store.set_role("NOT_A_ROLE", "deepseek", "x")


# ============================================================ 15..18 num_ctx / local guard
def test_15_num_ctx_positive_validation(tmp_path):
    store = _store(tmp_path)
    for bad in (0, -5, NUM_CTX_MIN - 1, NUM_CTX_MAX + 1, True):
        with pytest.raises(SettingsError):
            store.set_local_num_ctx(bad)
    assert store.set_local_num_ctx(8192).local_num_ctx == 8192
    assert store.set_local_num_ctx(None).local_num_ctx is None


def test_16_17_num_ctx_serialized_into_ollama_options_only_when_set(fake_ollama):
    box = []
    def cap(url, payload, timeout):
        box.append(payload); return {"message": {"content": "ok"}}
    # unset -> unchanged shape
    build_local_llm_provider_factory(LocalLLMConfig(base_url=fake_ollama, model="llama3"), http_post=cap)(None)(
        [{"role": "user", "content": "hi"}])
    assert "options" not in box[-1] and set(box[-1]) == {"model", "messages", "stream"}
    # set -> options.num_ctx
    build_local_llm_provider_factory(
        LocalLLMConfig(base_url=fake_ollama, model="llama3", num_ctx=16384), http_post=cap
    )(None)([{"role": "user", "content": "hi"}])
    assert box[-1]["options"] == {"num_ctx": 16384}


def test_18_remote_local_url_guard_preserved():
    from services.character_companion import LocalLLMProviderError
    with pytest.raises(LocalLLMProviderError):
        LocalLLMConfig(base_url="http://evil.example.com:11434", model="llama3")


# ============================================================ 19..21 settings persistence
def test_19_20_21_settings_persist_without_secrets_and_survive_reopen(tmp_path):
    store = SettingsStore(tmp_path)
    store.set_role("DIALOGUE", "local", "llama3.1")
    store.set_local_num_ctx(24576)
    store.set_base_url("local", "http://127.0.0.1:11434")
    # 20: reopen
    reopened = SettingsStore(tmp_path).load()
    assert reopened.dialogue() == RoleAssignment("local", "llama3.1")
    assert reopened.local_num_ctx == 24576
    # 19: never a secret on disk
    assert FAKE_KEY not in store.path.read_text("utf-8")
    # 21: malformed file -> safe defaults, no crash
    store.path.write_text("{ this is not json", encoding="utf-8")
    assert SettingsStore(tmp_path).load().dialogue().provider_id == "fake"


# ============================================================ 22 test connection, no secret log
def test_22_provider_test_does_not_expose_secret(fake_cloud, tmp_path, capsys):
    vault = InMemoryCredentialVault(); vault.store("deepseek", FAKE_KEY)
    store = _store(tmp_path)
    store.set_base_url("deepseek", fake_cloud)
    res = probe_provider_connection("deepseek", "deepseek-v4-pro", store.load(), vault,
                                   fake_factory=make_fake_factory())
    assert res["ok"] is True
    _FakeCloud.status = 401
    res2 = probe_provider_connection("deepseek", "deepseek-v4-pro", store.load(), vault,
                                    fake_factory=make_fake_factory())
    assert res2["ok"] is False and vault.has("deepseek")      # failure does not erase credential
    out = capsys.readouterr()
    assert FAKE_KEY not in (out.out + out.err) and FAKE_KEY not in json.dumps(res2)


# ============================================================ 23..35 attachment gateway
_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
_JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
_WEBP = b"RIFF" + b"\x00\x00\x00\x20" + b"WEBP" + b"\x00" * 32
_PDF = b"%PDF-1.7\n" + b"x" * 64


def _gw():
    return AttachmentSecurityGateway()


@pytest.mark.parametrize("name,data,ctype", [
    ("a.png", _PNG, "image/png"),
    ("b.jpg", _JPEG, "image/jpeg"),
    ("c.webp", _WEBP, "image/webp"),
    ("d.pdf", _PDF, "application/pdf"),
])
def test_23_26_signature_accept(name, data, ctype):
    acc = _gw().inspect(filename=name, data=data)
    assert acc.content_type == ctype and acc.authority == AUTHORITY_USER_ATTACHMENT_DATA


def test_27_extension_spoof_rejected():
    with pytest.raises(AttachmentError) as exc:
        _gw().inspect(filename="totally.png", data=b"not a png at all")
    assert exc.value.code == "signature_mismatch"
    with pytest.raises(AttachmentError):
        _gw().inspect(filename="x.exe", data=_PNG)             # not on allowlist


def test_28_oversized_file_rejected():
    with pytest.raises(AttachmentError) as exc:
        _gw().inspect(filename="huge.txt", data=b"a" * (13 * 1024 * 1024))
    assert exc.value.code == "too_large"


def test_29_txt_bounded_decode_works():
    acc = _gw().inspect(filename="note.md", data="# Заголовок\nтекст".encode("utf-8"))
    assert acc.category == "document" and acc.text_preview.startswith("# Заголовок")


def test_30_binary_as_text_rejected():
    with pytest.raises(AttachmentError) as exc:
        _gw().inspect(filename="fake.txt", data=b"\x00\x01\x02binary\xff")
    assert exc.value.code in ("binary_as_text", "bad_text_encoding")


def test_31_attachment_metadata_uses_generated_id():
    acc = _gw().inspect(filename="report.pdf", data=_PDF)
    assert acc.attachment_id.startswith("att-") and "report" not in acc.attachment_id
    same = _gw().inspect(filename="different-name.pdf", data=_PDF)
    assert same.attachment_id == acc.attachment_id            # id derives from content, not name


def test_32_traversal_like_filename_is_reduced_to_a_label():
    acc = _gw().inspect(filename="../../../../etc/passwd.txt", data=b"hello")
    assert "/" not in acc.declared_name and "\\" not in acc.declared_name and ".." not in acc.declared_name
    acc2 = _gw().inspect(filename="..\\..\\windows\\system32\\x.png", data=_PNG)
    assert acc2.declared_name == "x.png"


def test_33_attachment_authority_is_data():
    acc = _gw().inspect(filename="a.png", data=_PNG)
    assert acc.authority == AUTHORITY_USER_ATTACHMENT_DATA
    for forbidden in ("SYSTEM", "TOOL", "RUNTIME_CONTROL", "STATE_WRITE"):
        assert acc.authority != forbidden


def test_34_35_gateway_zero_network_zero_shell():
    import inspect

    from services.character_companion import attachments

    src = inspect.getsource(attachments)
    import_lines = [l for l in src.splitlines() if l.strip().startswith(("import ", "from "))]
    for line in import_lines:
        for mod in ("subprocess", "socket", "urllib", "requests", "httpx", "asyncio", "http.client"):
            assert mod not in line, line
    for call in ("subprocess.", "os.system(", "os.popen(", "Popen(", "eval(", "exec(", "__import__("):
        assert call not in src, call


# ============================================================ 23-integration: dialogue role -> runtime
def test_dialogue_role_used_by_send_message_through_runtime(fake_ollama, tmp_path):
    data_root = tmp_path / "cd"
    vault = InMemoryCredentialVault()
    svc = _service(tmp_path, vault=vault, data_root=data_root)
    svc._settings_store.set_base_url("local", fake_ollama)
    svc._settings_store.set_role("DIALOGUE", "local", "llama3")
    sid = svc.create_session("kira").session_id
    turn = svc.send_message(sid, "Привет.")
    assert turn.response == "local ok"                        # from the fake ollama, via RuntimeService
    mem = RuntimeMemoryBackend(data_root / "characters" / "kira" / "memory", "kira")
    try:
        kinds = [(e.event_type, e.provenance) for e in mem.load_events_causal("kira")]
    finally:
        mem.close()
    assert ("USER_MESSAGE", "USER_STATED") in kinds and ("CHARACTER_MESSAGE", "CHARACTER_UTTERANCE") in kinds
    assert len(_FakeOllama.seen) == 1                         # exactly one provider, one call


def test_fake_mode_is_explicit_not_automatic(tmp_path):
    svc = _service(tmp_path)                                  # default settings -> DIALOGUE = fake
    assert svc._settings_store.load().dialogue().provider_id == "fake"
    sid = svc.create_session("kira").session_id
    assert svc.send_message(sid, "hi").response == "fake reply"
