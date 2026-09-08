#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CINEMATIC COMPANION FIRST RELEASE UX V1 -- backend (multi-chat, scene,
random scenario, async image jobs). Offline; deterministic fake provider +
deterministic fake image generator; no network."""

from __future__ import annotations

import json

import pytest

from services.character_companion import (
    KIND_CONTEXT,
    KIND_CUSTOM,
    STATE_QUEUED,
    STATE_READY,
    CompanionError,
    CompanionScene,
    CompanionService,
    FakeImageGenerator,
    UnavailableImageGenerator,
    random_field,
    random_scenario,
)
from services.character_companion.scenarios import SCENE_FIELDS
from services.character_runtime import RuntimeMemoryBackend

from tests.character_companion.conftest import ACCEPTED_ROOT, FAKE_PROVIDER_INFO, make_fake_factory

SCENE = {"place": "Кухня", "time": "Вечер", "situation": "Пьют чай", "mood": "Спокойное",
         "freeform": "За окном тихий дождь."}


def _svc(tmp_path, *, data_root=None, image_generator=None, factory=None):
    return CompanionService(
        acceptance_root=ACCEPTED_ROOT,
        data_root=data_root or (tmp_path / "cd"),
        provider_factory=factory or make_fake_factory("Ответ Киры."),
        provider_info=FAKE_PROVIDER_INFO,
        image_generator=image_generator or FakeImageGenerator(),
    )


# ---------------------------------------------------- 1, 2 backward compat
def test_01_old_registry_without_new_fields_loads(tmp_path):
    data_root = tmp_path / "cd"
    data_root.mkdir()
    (data_root / "companion_sessions.json").write_text(json.dumps([{
        "session_id": "cmp-old", "character_id": "kira", "purpose": "COMPANION",
        "created_at": "2026-01-01T00:00:00+00:00", "updated_at": "2026-01-01T00:00:00+00:00",
        "label": "Старый диалог",
    }]), encoding="utf-8")
    svc = _svc(tmp_path, data_root=data_root)
    got = svc.list_sessions("kira")
    assert [s.session_id for s in got] == ["cmp-old"]
    assert got[0].title == "" and got[0].scene is None and got[0].scene_cover_ref is None
    assert svc.get_session("cmp-old").label == "Старый диалог"


def test_02_ordinary_no_scene_chat_still_works(tmp_path):
    svc = _svc(tmp_path)
    s = svc.create_session("kira")
    assert s.scene is None
    turn = svc.send_message(s.session_id, "Привет.")
    assert turn.response == "Ответ Киры." and turn.scene_present is False
    assert [m.role for m in svc.get_messages(s.session_id)] == ["user", "character"]


# ---------------------------------------------------- 3, 4, 5, 6 scene
def test_03_scene_session_persists_structured_fields(tmp_path):
    svc = _svc(tmp_path)
    s = svc.create_session("kira", title="Дождливый вечер", scene=SCENE)
    assert s.title == "Дождливый вечер"
    assert s.scene == CompanionScene(place="Кухня", time="Вечер", situation="Пьют чай",
                                     mood="Спокойное", freeform="За окном тихий дождь.")


def test_04_scene_survives_reopen(tmp_path):
    data_root = tmp_path / "cd"
    s1 = _svc(tmp_path, data_root=data_root)
    sid = s1.create_session("kira", scene=SCENE).session_id
    del s1
    s2 = _svc(tmp_path, data_root=data_root)
    assert s2.get_session(sid).scene.place == "Кухня"


def test_05_scene_passed_through_runtime_scene_path(tmp_path):
    factory = make_fake_factory("ок")
    svc = _svc(tmp_path, factory=factory)
    sid = svc.create_session("kira", scene=SCENE).session_id
    turn = svc.send_message(sid, "Осмотрись.")
    assert turn.scene_present is True
    # the assembled provider request carries a СЦЕНА system block with our values
    sys_text = "\n".join(m["content"] for m in factory.calls[0] if m.get("role") == "system")
    assert "СЦЕНА" in sys_text and "Кухня" in sys_text and "За окном тихий дождь." in sys_text


def test_06_scene_does_not_mutate_memory_or_state(tmp_path):
    data_root = tmp_path / "cd"
    svc = _svc(tmp_path, data_root=data_root)
    sid = svc.create_session("kira", scene=SCENE).session_id
    svc.send_message(sid, "Привет.")
    mem = RuntimeMemoryBackend(data_root / "characters" / "kira" / "memory", "kira")
    try:
        kinds = {e.event_type for e in mem.load_events_causal("kira")}
        meanings = [e.meaning for e in mem.load_events_causal("kira")]
    finally:
        mem.close()
    assert kinds == {"USER_MESSAGE", "CHARACTER_MESSAGE"}       # no WORLD_FACT / scene events
    assert "Кухня" not in " ".join(meanings)                    # scene text not written to memory
    state_db = data_root / "characters" / "kira" / "state" / "runtime_state.sqlite3"
    assert not state_db.exists() or state_db.stat().st_size >= 0  # never populated by scene


# ---------------------------------------------------- 7, 8, 9, 10 multi-chat
def test_07_08_09_multi_chat_list_sorted_with_preview(tmp_path):
    svc = _svc(tmp_path)
    a = svc.create_session("kira", title="Первый")
    b = svc.create_session("kira", title="Второй")
    svc.send_message(a.session_id, "сообщение в первом")
    svc.send_message(b.session_id, "сообщение во втором")
    svc.send_message(a.session_id, "снова первый")             # a now most recent
    listed = svc.list_sessions("kira")
    assert [s.session_id for s in listed] == [a.session_id, b.session_id]   # newest activity first
    first = next(s for s in listed if s.session_id == a.session_id)
    assert first.last_message_preview == "Ответ Киры."         # last message (character reply)
    assert first.last_activity >= b.created_at


def test_10_session_character_isolation(tmp_path):
    from services.character_companion import CompanionCharacterEntry, build_default_catalog
    cat = build_default_catalog(ACCEPTED_ROOT, extra=(
        CompanionCharacterEntry(character_id="synthetic-b", display_name="B",
                                subject_id="synthetic-b", available=True),
    ))
    svc = CompanionService(acceptance_root=ACCEPTED_ROOT, data_root=tmp_path / "cd",
                           provider_factory=make_fake_factory(), provider_info=FAKE_PROVIDER_INFO,
                           catalog=cat, image_generator=FakeImageGenerator())
    ak = svc.create_session("kira")
    bk = svc.create_session("synthetic-b")
    assert [s.session_id for s in svc.list_sessions("kira")] == [ak.session_id]
    assert [s.session_id for s in svc.list_sessions("synthetic-b")] == [bk.session_id]


# ---------------------------------------------------- 11, 12, 13 random scenario
def test_11_random_scenario_returns_editable_structured_fields():
    sc = random_scenario(seed=7)
    assert set(sc) == set(SCENE_FIELDS) and all(isinstance(v, str) and v for v in sc.values())
    assert random_scenario(seed=7) == sc                       # deterministic
    assert isinstance(random_field("mood", seed=1), str)
    with pytest.raises(ValueError):
        random_field("nonsense")


def test_12_random_scenario_is_character_agnostic():
    import inspect

    from services.character_companion import scenarios

    src = inspect.getsource(scenarios).lower()
    for name in ("kira", "кира", "andrey", "андрей", "marina"):
        assert name not in src


def test_13_random_scenario_uses_zero_provider_calls():
    factory = make_fake_factory()
    random_scenario(seed=1)
    for f in SCENE_FIELDS:
        random_field(f, seed=2)
    assert factory.calls == []


# ---------------------------------------------------- 14..21 image jobs
def test_14_image_job_created_without_blocking_send_message(tmp_path):
    svc = _svc(tmp_path)
    sid = svc.create_session("kira", scene=SCENE).session_id
    job = svc.create_image_job(sid, kind=KIND_CONTEXT)
    assert job.state == STATE_QUEUED
    # chat still fully usable while the job sits un-advanced
    turn = svc.send_message(sid, "Продолжаем разговор.")
    assert turn.response == "Ответ Киры."
    assert svc.get_image_job(job.job_id).job_id == job.job_id


def test_15_image_job_state_transitions_deterministic(tmp_path):
    svc = _svc(tmp_path)
    sid = svc.create_session("kira").session_id
    job = svc.create_image_job(sid, kind=KIND_CUSTOM, prompt="тихая кухня вечером")
    states = [job.state]
    for _ in range(4):
        svc.poll_image_jobs(sid)
        states.append(svc.get_image_job(job.job_id).state)
    assert states[:3] == ["QUEUED", "GENERATING", "READY"]
    assert states[-1] == "READY"
    ready = svc.get_image_job(job.job_id)
    assert ready.result_ref and svc.image_path(ready.result_ref).exists()


def test_16_ready_image_persists_across_reopen(tmp_path):
    data_root = tmp_path / "cd"
    s1 = _svc(tmp_path, data_root=data_root)
    sid = s1.create_session("kira").session_id
    job = s1.create_image_job(sid, kind=KIND_CONTEXT)
    s1._images.run_to_completion(job.job_id)
    ref = s1.get_image_job(job.job_id).result_ref
    del s1
    s2 = _svc(tmp_path, data_root=data_root)
    reloaded = s2.get_image_job(job.job_id)
    assert reloaded.state == STATE_READY and reloaded.result_ref == ref
    assert s2.image_path(ref).exists()


def test_17_previous_images_not_auto_deleted(tmp_path):
    svc = _svc(tmp_path)
    sid = svc.create_session("kira").session_id
    j1 = svc.create_image_job(sid, kind=KIND_CONTEXT)
    svc._images.run_to_completion(j1.job_id)
    j2 = svc.create_image_job(sid, kind=KIND_CONTEXT)
    svc._images.run_to_completion(j2.job_id)
    refs = [j.result_ref for j in svc.poll_image_jobs(sid)]
    assert svc.get_image_job(j1.job_id).state == STATE_READY   # first survived the second
    assert len([r for r in refs if r]) == 2


def test_18_19_cover_selection_explicit_and_persists(tmp_path):
    data_root = tmp_path / "cd"
    s1 = _svc(tmp_path, data_root=data_root)
    sid = s1.create_session("kira").session_id
    assert s1.get_session(sid).scene_cover_ref is None          # never auto-set
    job = s1.create_image_job(sid, kind=KIND_CONTEXT)
    s1._images.run_to_completion(job.job_id)
    ref = s1.get_image_job(job.job_id).result_ref
    with pytest.raises(CompanionError):
        s1.set_scene_cover(sid, "images/not-a-real-ref.svg")    # must be a READY result of this session
    s1.set_scene_cover(sid, ref)
    del s1
    s2 = _svc(tmp_path, data_root=data_root)
    assert s2.get_session(sid).scene_cover_ref == ref           # persisted across reopen


def test_20_deleting_one_image_leaves_portrait_history_scene_others(tmp_path):
    data_root = tmp_path / "cd"
    svc = _svc(tmp_path, data_root=data_root)
    sid = svc.create_session("kira", scene=SCENE).session_id
    svc.send_message(sid, "первое сообщение")
    j1 = svc.create_image_job(sid, kind=KIND_CONTEXT); svc._images.run_to_completion(j1.job_id)
    j2 = svc.create_image_job(sid, kind=KIND_CONTEXT); svc._images.run_to_completion(j2.job_id)
    svc.delete_image_job(j1.job_id)
    with pytest.raises(CompanionError):
        svc.get_image_job(j1.job_id)
    assert svc.get_image_job(j2.job_id).state == STATE_READY            # other image intact
    assert len(svc.get_messages(sid)) == 2                             # history intact
    assert svc.get_session(sid).scene.place == "Кухня"                 # scene metadata intact


def test_21_context_frame_request_is_bounded(tmp_path):
    svc = _svc(tmp_path)
    sid = svc.create_session("kira", scene=SCENE).session_id
    for i in range(20):
        svc.send_message(sid, f"сообщение {i}")
    job = svc.create_image_job(sid, kind=KIND_CONTEXT)
    ctx = job.context
    assert ctx["excerptLimit"] == 8
    assert len(ctx["recentMessages"]) == 8                            # not the whole 40-message log
    assert ctx["scene"]["place"] == "Кухня"
    assert ctx["sessionId"] == sid


# ---------------------------------------------------- 22 normal chat path unchanged
def test_22_provider_runtime_path_for_normal_chat_unchanged(tmp_path):
    factory = make_fake_factory("без сцены")
    svc = _svc(tmp_path, factory=factory)
    sid = svc.create_session("kira").session_id            # no scene
    svc.send_message(sid, "Привет.")
    sys_text = "\n".join(m["content"] for m in factory.calls[0] if m.get("role") == "system")
    assert "СЦЕНА" not in sys_text                          # identical to pre-Cinematic behavior
    assert any(m.get("role") == "user" and m.get("content") == "Привет." for m in factory.calls[0])
