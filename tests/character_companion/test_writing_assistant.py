#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CHAT CONTROL AND COMPOSER ASSISTANT V1 -- Writing Assistant utility role.

Offline. The assistant is an in-app text helper, NOT a character: it must never
route through Character Runtime / Memory, it resolves only its explicitly
configured provider/model, and it has no silent fallback. Tests use the
deterministic fake provider only -- no DeepSeek/OpenAI/Qwen/Ollama, no network.
"""

from __future__ import annotations

import json

import pytest

from services.character_companion import (
    CompanionError,
    CompanionService,
    CompanionTransport,
    InMemoryCredentialVault,
    SettingsStore,
    WritingAssistantError,
    rewrite_draft,
)
from services.character_companion.provider_registry import (
    ALL_ROLES,
    ROLE_DIALOGUE,
    ROLE_DISPLAY_ORDER,
    ROLE_WRITING_ASSISTANT,
    RUNTIME_WIRED_ROLES,
    get_provider,
)
from services.character_runtime import RuntimeMemoryBackend

from tests.character_companion.conftest import ACCEPTED_ROOT, FAKE_PROVIDER_INFO, make_fake_factory

KEY = "sk-writing-assistant-SECRET-abc123def456"
DRAFT = "прив я сегодня устал давай просто поговорим"


def _service(tmp_path, *, factory=None, vault=None):
    dr = tmp_path / "cd"
    return CompanionService(
        acceptance_root=ACCEPTED_ROOT, data_root=dr,
        provider_factory=factory or make_fake_factory("Привет. Я сегодня устал — давай просто поговорим."),
        provider_info=FAKE_PROVIDER_INFO,
        settings_store=SettingsStore(dr), credential_vault=vault or InMemoryCredentialVault(),
    )


# --------------------------------------------------------------- role
def test_writing_assistant_role_added_additively():
    assert ROLE_WRITING_ASSISTANT in ALL_ROLES
    assert ROLE_WRITING_ASSISTANT in ROLE_DISPLAY_ORDER
    assert ROLE_WRITING_ASSISTANT not in RUNTIME_WIRED_ROLES        # utility, not runtime
    # every DIALOGUE-capable provider can serve it; no dedicated media capability
    assert ROLE_WRITING_ASSISTANT in get_provider("deepseek").supported_roles
    assert ROLE_WRITING_ASSISTANT in get_provider("local").supported_roles


def test_old_settings_load_with_assistant_absent(tmp_path):
    (tmp_path / "companion_settings.json").write_text(json.dumps({
        "version": 1,
        "roles": {"DIALOGUE": {"providerId": "deepseek", "modelId": "deepseek-chat"}},
    }), encoding="utf-8")
    s = SettingsStore(tmp_path).load()
    assert "WRITING_ASSISTANT" not in s.roles                       # defaults unconfigured
    assert s.roles["DIALOGUE"].provider_id == "deepseek"            # existing KIRA path intact


def test_assistant_provider_model_persists(tmp_path):
    SettingsStore(tmp_path).set_role(ROLE_WRITING_ASSISTANT, "openai", "gpt-4o-mini")
    reopened = SettingsStore(tmp_path).load()
    assert reopened.roles[ROLE_WRITING_ASSISTANT].provider_id == "openai"
    assert reopened.roles[ROLE_WRITING_ASSISTANT].model_id == "gpt-4o-mini"


# --------------------------------------------------------------- resolver
def test_rewrite_rejects_empty_draft(tmp_path):
    store = SettingsStore(tmp_path)
    store.set_role(ROLE_WRITING_ASSISTANT, "local", "llama3")
    with pytest.raises(WritingAssistantError) as e:
        rewrite_draft("   ", settings=store.load(), vault=InMemoryCredentialVault(),
                      fake_factory=make_fake_factory("x"))
    assert e.value.code == "invalid_draft"


def test_coauthor_needs_no_separate_writing_assistant_config(tmp_path):
    """V2A: the co-author inherits the DIALOGUE assignment. With no separate
    WRITING_ASSISTANT role and the default fake DIALOGUE model it just works --
    there is no 'assistant_not_configured' gate any more."""
    store = SettingsStore(tmp_path)                                  # no roles at all
    assert ROLE_WRITING_ASSISTANT not in store.load().roles
    out = rewrite_draft(DRAFT, settings=store.load(), vault=InMemoryCredentialVault(),
                        fake_factory=make_fake_factory("ok"))
    assert out["suggestion"] == "ok" and out["provider"] == "fake" and out["model"] == "fake"


def test_coauthor_has_no_fallback_and_ignores_writing_assistant_assignment(tmp_path):
    """DIALOGUE -> openai without a key fails closed; a separately stored
    WRITING_ASSISTANT assignment must NOT rescue or redirect it."""
    store = SettingsStore(tmp_path)
    store.set_role(ROLE_DIALOGUE, "openai", "gpt-4o-mini")           # co-author source, no key
    store.set_role(ROLE_WRITING_ASSISTANT, "local", "llama3")        # must be ignored for execution
    with pytest.raises(WritingAssistantError) as e:
        rewrite_draft(DRAFT, settings=store.load(), vault=InMemoryCredentialVault(),
                      fake_factory=make_fake_factory("SHOULD-NOT-APPEAR"))
    assert e.value.code == "missing_credential"                      # NOT a silent switch to local/fake


def test_fake_assistant_returns_suggestion(tmp_path):
    store = SettingsStore(tmp_path)
    store.set_role(ROLE_DIALOGUE, "fake", "fake")
    out = rewrite_draft(DRAFT, settings=store.load(), vault=InMemoryCredentialVault(),
                        fake_factory=make_fake_factory("Привет. Я сегодня устал — давай просто поговорим."))
    assert out["suggestion"].startswith("Привет.") and out["provider"] == "fake" and out["model"] == "fake"


def test_repeated_rewrite_operates_from_supplied_source(tmp_path):
    """The endpoint is stateless: each call rewrites exactly the draft it is
    given. Regeneration-from-original is the caller's (composer's) contract."""
    store = SettingsStore(tmp_path)
    store.set_role(ROLE_WRITING_ASSISTANT, "fake", "fake")
    seen = []
    fac = make_fake_factory("polished")
    orig_factory = fac

    def spy(recorder):
        prov = orig_factory(recorder)

        def wrapped(messages):
            seen.append(messages[-1]["content"])
            return prov(messages)
        return wrapped

    rewrite_draft("draft one", settings=store.load(), vault=InMemoryCredentialVault(), fake_factory=spy)
    rewrite_draft("draft one", settings=store.load(), vault=InMemoryCredentialVault(), fake_factory=spy)
    assert seen == ["draft one", "draft one"]                       # never fed a previous suggestion


# --------------------------------------------------------------- boundary
def _events(tmp_path, character_id="kira"):
    backend = RuntimeMemoryBackend(tmp_path / "cd" / "characters" / character_id / "memory", character_id)
    try:
        return list(backend.load_events_causal(character_id))
    finally:
        backend.close()


def test_rewrite_does_not_touch_character_runtime_or_memory(tmp_path):
    svc = _service(tmp_path)
    svc.set_role(ROLE_WRITING_ASSISTANT, "fake", "fake")
    # a live session with real history
    session = svc.create_session("kira", title="RC")
    svc.send_message(session.session_id, "первое сообщение")
    before_events = _events(tmp_path)
    before_msgs = svc.get_messages(session.session_id)
    before_registry = (tmp_path / "cd" / "companion_sessions.json").read_text(encoding="utf-8")

    out = svc.writing_assistant_rewrite("прив как дела я хотел спросить")
    assert out["suggestion"]

    after_events = _events(tmp_path)
    assert [e.seq for e in after_events] == [e.seq for e in before_events]   # no new / changed events
    assert [(e.event_type, e.meaning) for e in after_events] == [(e.event_type, e.meaning) for e in before_events]
    assert svc.get_messages(session.session_id) == before_msgs              # transcript unchanged
    assert (tmp_path / "cd" / "companion_sessions.json").read_text(encoding="utf-8") == before_registry
    # no runtime state file was written by the rewrite
    state_dir = tmp_path / "cd" / "characters" / "kira" / "state"
    state_before = sorted(p.name for p in state_dir.glob("*")) if state_dir.exists() else []
    svc.writing_assistant_rewrite("ещё один черновик")
    state_after = sorted(p.name for p in state_dir.glob("*")) if state_dir.exists() else []
    assert state_after == state_before


def test_rewrite_does_not_send_history_or_package(tmp_path):
    """The provider only ever sees a 2-message [system, user(draft)] payload."""
    svc = _service(tmp_path)
    svc.set_role(ROLE_WRITING_ASSISTANT, "fake", "fake")
    session = svc.create_session("kira", title="RC")
    svc.send_message(session.session_id, "секрет из истории 42")

    captured = {}
    real = make_fake_factory("ok")

    def spy(recorder):
        prov = real(recorder)

        def wrapped(messages):
            captured["messages"] = messages
            return prov(messages)
        return wrapped

    svc2 = CompanionService(
        acceptance_root=ACCEPTED_ROOT, data_root=tmp_path / "cd",
        provider_factory=spy, provider_info=FAKE_PROVIDER_INFO,
        settings_store=SettingsStore(tmp_path / "cd"), credential_vault=InMemoryCredentialVault(),
    )
    svc2.writing_assistant_rewrite("почисти этот текст пожалуйста")
    msgs = captured["messages"]
    assert len(msgs) == 2 and msgs[0]["role"] == "system" and msgs[1]["role"] == "user"
    assert msgs[1]["content"] == "почисти этот текст пожалуйста"
    blob = json.dumps(msgs, ensure_ascii=False)
    assert "секрет из истории 42" not in blob and "kira-r4" not in blob and "source_hash" not in blob


def test_raw_credential_never_exposed_by_rewrite(tmp_path):
    vault = InMemoryCredentialVault()
    svc = _service(tmp_path, vault=vault)
    svc.store_credential("openai", KEY)
    svc.set_role(ROLE_WRITING_ASSISTANT, "openai", "gpt-4o-mini")

    svc2 = CompanionService(
        acceptance_root=ACCEPTED_ROOT, data_root=tmp_path / "cd",
        provider_factory=make_fake_factory("unused"), provider_info=FAKE_PROVIDER_INFO,
        settings_store=SettingsStore(tmp_path / "cd"), credential_vault=vault,
        http_post_cloud=lambda url, payload, headers, timeout_s: {"choices": [{"message": {"content": "cleaned"}}]},
    )
    out = svc2.writing_assistant_rewrite(DRAFT)
    assert KEY not in json.dumps(out, ensure_ascii=False)
    assert KEY not in json.dumps(svc2.settings_view(), ensure_ascii=False)


# --------------------------------------------------------------- transport
def test_transport_rewrite_and_settings_expose_role(tmp_path):
    svc = _service(tmp_path)
    t = CompanionTransport(svc)
    view = t.get_settings()
    assert any(r["role"] == "WRITING_ASSISTANT" for r in view["roleCatalog"])
    wa = next(r for r in view["roleCatalog"] if r["role"] == "WRITING_ASSISTANT")
    assert wa["runtimeWired"] is False and wa["readiness"] == "NOT_CONFIGURED"

    from services.character_companion.transport import CompanionTransportError
    with pytest.raises(CompanionTransportError) as e1:
        t.writing_assistant_rewrite({"draft": "   "})
    assert e1.value.status == 400 and e1.value.code == "invalid_draft"

    # V2A: no separate WRITING_ASSISTANT config needed -- the default fake
    # DIALOGUE model backs the legacy endpoint for a non-empty draft.
    res = t.writing_assistant_rewrite({"draft": DRAFT})
    assert isinstance(res["suggestion"], str) and res["suggestion"].strip()
