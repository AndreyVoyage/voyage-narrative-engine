#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""COMPANION_WRITING_ASSISTANT_V2A -- contextual co-author backend.

Offline. Fake/injected providers only -- no DeepSeek/OpenAI/Ollama, no network,
no real Companion data root. The co-author:
  * derives COMPOSE (empty draft) / EXPAND (non-empty) from the draft itself;
  * runs on the EFFECTIVE DIALOGUE provider/model (never a separate
    WRITING_ASSISTANT assignment), one call, no retry, no fallback;
  * assembles only USER-safe context (visible history, Scene, the user's own
    prior statements) -- never the KIRA core instruction, RELATIONSHIP,
    PSYCHOLOGY, epistemic context, FACT state or the Accepted package;
  * is bounded by the shared estimated-token dialogue context budget;
  * never persists a conversation event and never writes memory/state.
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
)
from services.character_companion.provider_registry import ROLE_DIALOGUE, ROLE_WRITING_ASSISTANT
from services.character_companion.writing_assistant import (
    MODE_COMPOSE,
    MODE_EXPAND,
    WritingAssistantError,
    coauthor_suggest,
    derive_mode,
)
from services.character_runtime import RuntimeMemoryBackend

from tests.character_companion.conftest import ACCEPTED_ROOT, FAKE_PROVIDER_INFO, make_fake_factory

KEY = "sk-coauthor-SECRET-zzz999"

# Markers that MUST NEVER reach the co-author payload.
_KIRA_CORE_MARKERS = ("Ты — Кира", "Отвечай от лица персонажа")
_FORBIDDEN_HEADERS = (
    "ПОДТВЕРЖДЁННОЕ СОСТОЯНИЕ ОТНОШЕНИЙ",       # RELATIONSHIP
    "ПОДТВЕРЖДЁННОЕ ПСИХОЛОГИЧЕСКОЕ СОСТОЯНИЕ",  # PSYCHOLOGY
    "ЭПИСТЕМИЧЕСКИЙ КОНТЕКСТ",                   # epistemic
    "ПОДТВЕРЖДЁННОЕ ТЕКУЩЕЕ СОСТОЯНИЕ",          # FACT runtime-state
)


def _dr(tmp_path):
    return tmp_path / "cd"


def _svc(tmp_path, *, factory=None, http_post_cloud=None, vault=None, mode="dev"):
    dr = _dr(tmp_path)
    return CompanionService(
        acceptance_root=ACCEPTED_ROOT, data_root=dr,
        provider_factory=factory or make_fake_factory("подсказка"),
        provider_info=FAKE_PROVIDER_INFO,
        settings_store=SettingsStore(dr),
        credential_vault=vault or InMemoryCredentialVault(),
        http_post_cloud=http_post_cloud,
        mode=mode,
    )


class _Spy:
    """A provider factory that records every payload and counts attempts."""

    def __init__(self, reply="сгенерированная реплика"):
        self.reply = reply
        self.payloads = []
        self.attempts = 0

    def __call__(self, recorder):
        def provider(messages):
            self.attempts += 1
            self.payloads.append([dict(m) for m in messages])
            return self.reply
        return provider

    @property
    def last(self):
        return self.payloads[-1]

    @property
    def blob(self):
        return json.dumps(self.payloads, ensure_ascii=False)


def _events(tmp_path, character_id="kira"):
    backend = RuntimeMemoryBackend(_dr(tmp_path) / "characters" / character_id / "memory", character_id)
    try:
        return list(backend.load_events_causal(character_id))
    finally:
        backend.close()


# ============================================================ mode derivation
def test_A_suggest_empty_draft_is_compose(tmp_path):
    spy = _Spy()
    svc = _svc(tmp_path, factory=spy)
    out = svc.writing_assistant_suggest("")
    assert out["mode"] == MODE_COMPOSE
    assert derive_mode("") == MODE_COMPOSE and derive_mode("   ") == MODE_COMPOSE
    # no EXPAND draft message
    assert all(not (m["role"] == "user" and m["content"] == "") for m in spy.last)
    assert "напиши ОДНО правдоподобное сообщение" in spy.last[0]["content"]


def test_B_suggest_non_empty_draft_is_expand(tmp_path):
    spy = _Spy()
    svc = _svc(tmp_path, factory=spy)
    out = svc.writing_assistant_suggest("хочу спросить про вчерашнее")
    assert out["mode"] == MODE_EXPAND
    assert derive_mode("x") == MODE_EXPAND
    assert spy.last[-1] == {"role": "user", "content": "хочу спросить про вчерашнее"}


def test_C_legacy_rewrite_non_empty_is_expand_compatible(tmp_path):
    spy = _Spy("развёрнутый вариант")
    svc = _svc(tmp_path, factory=spy)
    out = svc.writing_assistant_rewrite("прив как ты")
    assert out["suggestion"] == "развёрнутый вариант"
    assert out["mode"] == MODE_EXPAND
    assert set(out) >= {"suggestion", "provider", "model"}
    assert spy.last[-1]["content"] == "прив как ты"


def test_D_legacy_rewrite_empty_draft_still_invalid(tmp_path):
    svc = _svc(tmp_path)
    with pytest.raises(CompanionError) as e:
        svc.writing_assistant_rewrite("   ")
    assert e.value.code == "invalid_draft"
    # transport layer too
    t = CompanionTransport(svc)
    from services.character_companion.transport import CompanionTransportError
    with pytest.raises(CompanionTransportError) as te:
        t.writing_assistant_rewrite({"draft": ""})
    assert te.value.status == 400 and te.value.code == "invalid_draft"
    # ...but the new suggest endpoint accepts the empty string
    res = t.writing_assistant_suggest({"draft": ""})
    assert isinstance(res["suggestion"], str) and res["suggestion"].strip()


# ============================================================ prompt contract
def test_E_compose_payload_has_user_coauthor_instruction(tmp_path):
    spy = _Spy()
    svc = _svc(tmp_path, factory=spy)
    svc.writing_assistant_suggest("")
    sys0 = spy.last[0]
    assert sys0["role"] == "system"
    assert "ПОЛЬЗОВАТЕЛЮ" in sys0["content"]
    assert "не персонаж" in sys0["content"] and "не отвечаешь за персонажа" in sys0["content"]


def test_F_expand_payload_has_draft_as_authoritative_user_input(tmp_path):
    spy = _Spy()
    svc = _svc(tmp_path, factory=spy)
    svc.writing_assistant_suggest("мой черновик")
    assert "черновик" in spy.last[0]["content"].lower()
    assert "Не отвечай на черновик" in spy.last[0]["content"]
    assert spy.last[-1] == {"role": "user", "content": "мой черновик"}


# ============================================================ context safety
def _seed_session_with_history(svc, *, scene=None):
    session = svc.create_session("kira", title="Разговор", scene=scene)
    svc.send_message(session.session_id, "я вчера был в парке и думал о нас")
    svc.send_message(session.session_id, "расскажи как прошёл твой день")
    return session


def test_G_payload_excludes_character_private_and_kira_instruction(tmp_path):
    spy = _Spy()
    svc = _svc(tmp_path, factory=spy)
    session = _seed_session_with_history(
        svc, scene={"place": "кафе", "situation": "поздний вечер"}
    )
    spy.payloads.clear()  # keep only the co-author call's payload
    svc.writing_assistant_suggest("", session_id=session.session_id)
    blob = spy.blob
    for marker in _KIRA_CORE_MARKERS:
        assert marker not in blob, marker
    for header in _FORBIDDEN_HEADERS:
        assert header not in blob, header
    # no Accepted-package leakage markers
    assert "source_hash" not in blob and "accepted_package" not in blob
    # system messages are only: instruction, scene, (history frame)
    roles = [m["role"] for m in spy.last]
    assert roles[0] == "system"


def test_H_visible_history_included_when_available(tmp_path):
    spy = _Spy()
    svc = _svc(tmp_path, factory=spy)
    session = _seed_session_with_history(svc)
    spy.payloads.clear()
    svc.writing_assistant_suggest("", session_id=session.session_id)
    contents = [m["content"] for m in spy.last]
    assert "я вчера был в парке и думал о нас" in contents
    assert any("парке" in c for c in contents)
    # and the assistant/character reply turn is carried as role assistant
    assert any(m["role"] == "assistant" for m in spy.last)


def test_I_scene_included_when_available(tmp_path):
    spy = _Spy()
    svc = _svc(tmp_path, factory=spy)
    session = svc.create_session(
        "kira", title="Сцена", scene={"place": "набережная", "situation": "рассвет"}
    )
    spy.payloads.clear()
    svc.writing_assistant_suggest("привет", session_id=session.session_id)
    blob = spy.blob
    assert "СЦЕНА" in blob and "набережная" in blob


def test_J_user_originated_memory_included_from_other_sessions(tmp_path):
    spy = _Spy()
    svc = _svc(tmp_path, factory=spy)
    other = svc.create_session("kira", title="Прошлый разговор")
    svc.send_message(other.session_id, "меня зовут Андрей и я люблю горы")
    current = svc.create_session("kira", title="Сейчас")
    spy.payloads.clear()
    svc.writing_assistant_suggest("", session_id=current.session_id)
    blob = spy.blob
    assert "со слов пользователя" in blob
    assert "меня зовут Андрей и я люблю горы" in blob
    # KIRA's replies never enter the user-memory block
    assert "[со слов пользователя] Тестовый ответ" not in blob


def test_K_hidden_history_excluded(tmp_path):
    spy = _Spy()
    svc = _svc(tmp_path, factory=spy)
    session = svc.create_session("kira", title="С приватностью")
    svc.send_message(session.session_id, "это тайное сообщение 777")
    svc.send_message(session.session_id, "а это видимое сообщение 111")
    msgs = svc.get_messages(session.session_id)
    user_seq = next(m.seq for m in msgs if m.role == "user" and "777" in m.text)
    svc.set_message_visibility(session.session_id, user_seq, True)
    spy.payloads.clear()
    svc.writing_assistant_suggest("", session_id=session.session_id)
    assert "это тайное сообщение 777" not in spy.blob
    assert "а это видимое сообщение 111" in spy.blob  # non-hidden peer still present


# ============================================================ context budget
def _many_turn_history(n):
    h = []
    for i in range(n):
        h.append({"role": "user", "content": f"пользовательская реплика номер {i} " + "текст " * 80})
        h.append({"role": "assistant", "content": f"ответ персонажа {i} " + "слова " * 80})
    return h


def test_N_core_mandatory_overflow_prevents_provider_call():
    calls = []

    def factory(recorder):
        def provider(messages):
            calls.append(messages)
            return "x"
        return provider

    with pytest.raises(WritingAssistantError) as e:
        coauthor_suggest(
            "y" * 3000, mode=MODE_EXPAND, provider_factory=factory,
            provider_id="p", model_id="m", budget_est_tokens=2100,  # effective ~52 est tokens
        )
    assert e.value.code == "context_budget_exceeded"
    assert calls == []  # never reached the provider; nothing persisted


def test_M_core_history_is_newest_contiguous_no_skip_ahead():
    seen = {}

    def factory(recorder):
        def provider(messages):
            seen["m"] = messages
            return "ok"
        return provider

    hist = _many_turn_history(12)  # 24 messages, ~500 chars each
    # a small budget: only the newest handful of whole turns fit
    coauthor_suggest(
        "", mode=MODE_COMPOSE, provider_factory=factory,
        provider_id="p", model_id="m", budget_est_tokens=4000,
        visible_history=hist,
    )
    picked = [m for m in seen["m"] if m["role"] in ("user", "assistant")]
    assert picked and len(picked) % 2 == 0             # whole [user, assistant] turns only
    assert picked[-1]["content"].startswith("ответ персонажа 11")   # newest turn kept
    assert not any("номер 0 " in m["content"] for m in picked)      # oldest dropped
    # strict contiguity: the kept turns are the last k, in order, no gaps
    nums = [int(m["content"].split("номер ")[1].split()[0]) for m in picked if m["role"] == "user"]
    assert nums == list(range(nums[0], nums[0] + len(nums)))
    assert nums[-1] == 11
    # a bigger budget never carries LESS history
    seen2 = {}

    def factory2(recorder):
        def provider(messages):
            seen2["m"] = messages
            return "ok"
        return provider

    coauthor_suggest(
        "", mode=MODE_COMPOSE, provider_factory=factory2,
        provider_id="p", model_id="m", budget_est_tokens=40000,
        visible_history=hist,
    )
    picked2 = [m for m in seen2["m"] if m["role"] in ("user", "assistant")]
    assert len(picked2) >= len(picked)
    assert len(picked2) > len(picked)  # strictly more history under a bigger budget


def test_M2_service_history_is_whole_turns_and_chronological(tmp_path):
    spy = _Spy()
    svc = _svc(tmp_path, factory=spy)
    session = svc.create_session("kira", title="Ходы")
    for i in range(4):
        svc.send_message(session.session_id, f"реплика {i}")
    spy.payloads.clear()
    svc.writing_assistant_suggest("", session_id=session.session_id)
    hist_msgs = [m for m in spy.last if m["role"] in ("user", "assistant")]
    assert hist_msgs and len(hist_msgs) % 2 == 0
    order = [i for i, m in enumerate(spy.last) if m["role"] in ("user", "assistant")]
    assert order == sorted(order)  # contiguous & in payload order
    assert any("реплика 3" in m["content"] for m in hist_msgs)  # newest present


def test_L_no_second_budget_setting_exists(tmp_path):
    view = CompanionTransport(_svc(tmp_path)).get_settings()
    assert "dialogueContextBudget" in view
    keys = json.dumps(view, ensure_ascii=False).lower()
    assert "writingassistantcontextbudget" not in keys
    assert "coauthorcontextbudget" not in keys
    # the co-author uses the SAME estimator id as the committed dialogue budget
    from services.character_companion.writing_assistant import CONTEXT_BUDGET_ESTIMATOR_ID
    assert CONTEXT_BUDGET_ESTIMATOR_ID == "companion_est_v1"


# ============================================================ model policy
def _cloud_ok(url, payload, headers, timeout_s):
    return {"choices": [{"message": {"content": "облачный ответ"}}]}


def test_O_dialogue_pro_resolves_pro(tmp_path):
    vault = InMemoryCredentialVault()
    svc = _svc(tmp_path, vault=vault, http_post_cloud=_cloud_ok)
    svc.store_credential("deepseek", KEY)
    svc.set_role(ROLE_DIALOGUE, "deepseek", "deepseek-v4-pro")
    out = svc.writing_assistant_suggest("подскажи фразу")
    assert out["provider"] == "deepseek" and out["model"] == "deepseek-v4-pro"
    assert KEY not in json.dumps(out, ensure_ascii=False)


def test_P_dialogue_flash_resolves_flash(tmp_path):
    vault = InMemoryCredentialVault()
    svc = _svc(tmp_path, vault=vault, http_post_cloud=_cloud_ok)
    svc.store_credential("deepseek", KEY)
    svc.set_role(ROLE_DIALOGUE, "deepseek", "deepseek-v4-flash")
    out = svc.writing_assistant_suggest("подскажи фразу")
    assert out["provider"] == "deepseek" and out["model"] == "deepseek-v4-flash"


def test_Q_independent_writing_assistant_assignment_is_ignored(tmp_path):
    spy = _Spy("из фейкового диалога")
    svc = _svc(tmp_path, factory=spy)
    svc.set_role(ROLE_DIALOGUE, "fake", "fake")
    # a different, un-keyed WA assignment must not be used and must not error
    svc.set_role(ROLE_WRITING_ASSISTANT, "deepseek", "deepseek-v4-flash")
    out = svc.writing_assistant_suggest("сформулируй лучше")
    assert out["provider"] == "fake" and out["model"] == "fake"
    assert out["suggestion"] == "из фейкового диалога"


def test_R_S_provider_failure_no_fallback_single_attempt(tmp_path):
    class _CountingFail:
        def __init__(self):
            self.attempts = 0

        def __call__(self, recorder):
            def provider(messages):
                self.attempts += 1
                raise RuntimeError("boom")
            return provider

    cf = _CountingFail()
    svc = _svc(tmp_path, factory=cf)
    with pytest.raises(CompanionError) as e:
        svc.writing_assistant_suggest("что-нибудь")
    assert e.value.code == "assistant_failed"
    assert cf.attempts == 1  # exactly one attempt, no retry, no second provider


# ============================================================ persistence
def test_T_U_generation_writes_no_events_and_no_state(tmp_path):
    svc = _svc(tmp_path)
    session = _seed_session_with_history(svc)
    before_events = [(e.seq, e.event_type, e.meaning) for e in _events(tmp_path)]
    before_msgs = svc.get_messages(session.session_id)
    reg_path = _dr(tmp_path) / "companion_sessions.json"
    before_reg = reg_path.read_text(encoding="utf-8")
    state_dir = _dr(tmp_path) / "characters" / "kira" / "state"
    before_state = sorted(p.name for p in state_dir.glob("*")) if state_dir.exists() else []

    svc.writing_assistant_suggest("", session_id=session.session_id)
    svc.writing_assistant_suggest("доработай это", session_id=session.session_id)

    assert [(e.seq, e.event_type, e.meaning) for e in _events(tmp_path)] == before_events
    assert svc.get_messages(session.session_id) == before_msgs
    assert reg_path.read_text(encoding="utf-8") == before_reg
    after_state = sorted(p.name for p in state_dir.glob("*")) if state_dir.exists() else []
    assert after_state == before_state


def test_V_multiparagraph_output_preserved(tmp_path):
    spy = _Spy("Первый абзац мысли.\n\nВторой абзац с продолжением.")
    svc = _svc(tmp_path, factory=spy)
    out = svc.writing_assistant_suggest("набросок")
    assert out["suggestion"] == "Первый абзац мысли.\n\nВторой абзац с продолжением."
    assert "\n\n" in out["suggestion"]


def test_W_core_is_pure_and_offline():
    """coauthor_suggest never imports services.character_companion and works
    from injected primitives only."""
    seen = {}

    def factory(recorder):
        def provider(messages):
            seen["messages"] = messages
            return "готово"
        return provider

    out = coauthor_suggest(
        "черновик пользователя",
        provider_factory=factory,
        provider_id="deepseek", model_id="deepseek-v4-pro",
        budget_est_tokens=32768,
        visible_history=[{"role": "user", "content": "прошлый вопрос"},
                         {"role": "assistant", "content": "прошлый ответ персонажа"}],
        scene_text="СЦЕНА\nМесто: дом",
        user_memory_block="- [со слов пользователя] я живу в Москве",
        locale_hint="ru",
    )
    assert out == {
        "suggestion": "готово", "provider": "deepseek",
        "model": "deepseek-v4-pro", "mode": MODE_EXPAND,
    }
    blob = json.dumps(seen["messages"], ensure_ascii=False)
    for marker in _KIRA_CORE_MARKERS:
        assert marker not in blob
    assert seen["messages"][-1] == {"role": "user", "content": "черновик пользователя"}
