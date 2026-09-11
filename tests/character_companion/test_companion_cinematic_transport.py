#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CINEMATIC COMPANION FIRST RELEASE UX V1 -- transport + loopback HTTP.

Dict-level CompanionTransport roundtrip plus a real loopback roundtrip through
tools/character_companion_server.py. Offline fake dialogue provider + approved
synthetic visual snapshot + injected fake image transport; no external network."""

from __future__ import annotations

import json
import socket
import urllib.request
from pathlib import Path

import pytest

from services.character_companion import (
    CompanionService,
    CompanionTransport,
)
from services.character_companion.character_import import SnapshotStore
from services.character_companion.transport import CompanionTransportError
from services.character_companion.visual import ImageProviderAdapter, RealCompanionImageGenerator

from tests.character_companion.conftest import ACCEPTED_ROOT, FAKE_PROVIDER_INFO, make_fake_factory
from tests.character_companion.test_image_product_wiring import (
    FakeImageHttp,
    _configured_settings_store,
    _seed_snapshot,
    _vault_with_key,
)

SCENE = {"place": "Крыша", "time": "Ночь", "situation": "Смотрят на город", "mood": "Тихое",
         "freeform": "Город внизу мерцает."}


def _transport(tmp_path, *, data_root=None):
    data_root = Path(data_root or (tmp_path / "cd"))
    if SnapshotStore(data_root).read_active_version("kira") is None:
        _seed_snapshot(data_root, tmp_path)
    settings_store = _configured_settings_store(data_root)
    vault = _vault_with_key()
    image_generator = RealCompanionImageGenerator(
        data_root=data_root,
        settings_store=settings_store,
        credential_vault=vault,
        adapter=ImageProviderAdapter(http_post=FakeImageHttp()),
    )
    svc = CompanionService(
        acceptance_root=ACCEPTED_ROOT, data_root=data_root,
        provider_factory=make_fake_factory("Ответ."), provider_info=FAKE_PROVIDER_INFO,
        image_generator=image_generator, settings_store=settings_store,
        credential_vault=vault,
    )
    return CompanionTransport(svc)


# ---------------------------------------------------- 23..27 dict roundtrip
def test_23_24_25_26_27_scene_and_scenario(tmp_path):
    t = _transport(tmp_path)

    ordinary = t.create_session({"characterId": "kira"})                       # 23
    assert ordinary["scene"] is None and ordinary["purpose"] == "COMPANION"

    scened = t.create_session({"characterId": "kira", "title": "Ночь", "scene": SCENE})  # 24
    sid = scened["sessionId"]
    assert scened["scene"]["place"] == "Крыша" and scened["title"] == "Ночь"

    listed = t.list_sessions("kira")["sessions"]                               # 25 (enhanced)
    assert {s["sessionId"] for s in listed} == {ordinary["sessionId"], sid}
    assert all("lastMessagePreview" in s and "sceneCoverRef" in s for s in listed)

    fetched = t.get_session(sid)                                              # 26
    assert fetched["scene"]["freeform"] == "Город внизу мерцает."

    whole = t.random_scenario({"seed": 3})                                   # 27
    assert set(whole["scenario"]) == {"place", "time", "situation", "mood"}
    one = t.random_scenario({"field": "mood", "seed": 3})
    assert one["field"] == "mood" and isinstance(one["value"], str)
    with pytest.raises(CompanionTransportError):
        t.random_scenario({"field": "bogus"})


# ---------------------------------------------------- 28..31 image jobs
def test_28_29_30_31_image_jobs_and_cover(tmp_path):
    t = _transport(tmp_path)
    sid = t.create_session({"characterId": "kira", "scene": SCENE})["sessionId"]

    created = t.create_image_job({"sessionId": sid, "kind": "context"})       # 28
    job_id = created["jobId"]
    assert created["state"] == "QUEUED"

    # 31: conversation continues while the job is pending / generating
    r1 = t.send_message({"sessionId": sid, "text": "Пока рисуется, поговорим."})
    assert r1["response"] == "Ответ."
    first_poll = t.list_image_jobs(sid)["jobs"]                              # 29 -> GENERATING
    assert first_poll[0]["state"] in ("GENERATING", "READY")
    r2 = t.send_message({"sessionId": sid, "text": "И ещё сообщение."})
    assert r2["response"] == "Ответ."

    for _ in range(4):
        jobs = t.list_image_jobs(sid)["jobs"]
    ready = jobs[0]
    assert ready["state"] == "READY" and ready["resultRef"]

    with pytest.raises(CompanionTransportError):
        t.set_scene_cover({"sessionId": sid, "resultRef": "images/nope.svg"})
    covered = t.set_scene_cover({"sessionId": sid, "resultRef": ready["resultRef"]})  # 30
    assert covered["sceneCoverRef"] == ready["resultRef"]

    # history unaffected by all the image activity
    msgs = t.get_messages(sid)["messages"]
    assert [m["role"] for m in msgs] == ["user", "character", "user", "character"]


# ---------------------------------------------------- 32 loopback + restart
def _free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def _http(base, method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as r:  # noqa: S310 -- loopback only
        return r.status, json.loads(r.read().decode())


def test_32_loopback_server_and_restart_retains_metadata_and_ready_result(tmp_path):
    from tools.character_companion_server import CompanionServer

    data_root = tmp_path / "cd"

    s1 = CompanionServer(_transport(tmp_path, data_root=data_root), port=_free_port())
    s1.start()
    try:
        base = s1.base_url
        sid = _http(base, "POST", "/api/companion/sessions",
                    {"characterId": "kira", "title": "Ночь", "scene": SCENE})[1]["sessionId"]
        _http(base, "POST", "/api/companion/messages", {"sessionId": sid, "text": "Привет."})
        job = _http(base, "POST", "/api/companion/images", {"sessionId": sid, "kind": "context"})[1]
        for _ in range(5):
            jobs = _http(base, "GET", f"/api/companion/sessions/{sid}/images")[1]["jobs"]
        ref = jobs[0]["resultRef"]
        assert jobs[0]["state"] == "READY" and ref
        _http(base, "POST", "/api/companion/sessions/cover", {"sessionId": sid, "resultRef": ref})
    finally:
        s1.shutdown()

    s2 = CompanionServer(_transport(tmp_path, data_root=data_root), port=_free_port())
    s2.start()
    try:
        base = s2.base_url
        sess = _http(base, "GET", f"/api/companion/sessions/{sid}")[1]
        assert sess["scene"]["place"] == "Крыша" and sess["sceneCoverRef"] == ref
        again = _http(base, "GET", f"/api/companion/images/{job['jobId']}")[1]
        assert again["state"] == "READY" and again["resultRef"] == ref
        cont = _http(base, "POST", "/api/companion/messages", {"sessionId": sid, "text": "Ещё."})[1]
        assert len(cont["messages"]) == 4
    finally:
        s2.shutdown()
