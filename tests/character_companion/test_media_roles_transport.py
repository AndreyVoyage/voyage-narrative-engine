#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MEDIA PROVIDERS AND MODEL ROLES V1 -- transport + loopback HTTP.

Dict-level CompanionTransport and real loopback HTTP through
tools/character_companion_server.py. Offline; in-memory vault; no external
network; no raw-secret in any response.
"""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request

import pytest

from services.character_companion import (
    CompanionService,
    CompanionTransport,
    InMemoryCredentialVault,
    SettingsStore,
)
from services.character_companion.transport import CompanionTransportError

from tests.character_companion.conftest import ACCEPTED_ROOT, FAKE_PROVIDER_INFO, make_fake_factory

KEY = "sk-media-transport-SECRET-zzz999yyy888"


def _transport(tmp_path, vault=None):
    dr = tmp_path / "cd"
    svc = CompanionService(
        acceptance_root=ACCEPTED_ROOT, data_root=dr,
        provider_factory=make_fake_factory("fake reply"), provider_info=FAKE_PROVIDER_INFO,
        settings_store=SettingsStore(dr), credential_vault=vault or InMemoryCredentialVault(),
    )
    return CompanionTransport(svc)


def test_catalog_carries_models_capabilities_and_role_catalog(tmp_path):
    t = _transport(tmp_path)
    view = t.get_settings()
    openai = next(p for p in view["providers"] if p["providerId"] == "openai")
    assert [m["modelId"] for m in openai["models"]]
    assert "IMAGE_GENERATION" in openai["capabilities"]
    # every canonical role present, DIALOGUE first, only DIALOGUE runtime-wired
    roles = [r["role"] for r in view["roleCatalog"]]
    assert roles[0] == "DIALOGUE"
    for r in ("VISION", "IMAGE_GENERATION", "VIDEO_GENERATION", "STT", "TTS", "REALTIME"):
        assert r in roles
    assert view["runtimeWiredRoles"] == ["DIALOGUE"]


def test_save_media_roles_reload_and_bounded_errors(tmp_path):
    t = _transport(tmp_path)
    t.set_role({"role": "IMAGE_GENERATION", "providerId": "openai", "modelId": "gpt-image-1"})
    t.set_role({"role": "VIDEO_GENERATION", "providerId": "openai", "modelId": "sora-2"})
    t.set_role({"role": "VISION", "providerId": "qwen", "modelId": "qwen-vl-plus"})
    t.set_role({"role": "STT", "providerId": "openai", "modelId": "whisper-1"})
    t.set_role({"role": "TTS", "providerId": "openai", "modelId": "gpt-4o-mini-tts"})
    view = t.get_settings()
    assert view["roles"]["IMAGE_GENERATION"] == {"providerId": "openai", "modelId": "gpt-image-1"}
    assert view["roles"]["VISION"] == {"providerId": "qwen", "modelId": "qwen-vl-plus"}

    # DIALOGUE untouched by all of the above
    assert view["roles"]["DIALOGUE"]["providerId"] == "fake"

    # bounded rejections
    with pytest.raises(CompanionTransportError) as e1:
        t.set_role({"role": "IMAGE_GENERATION", "providerId": "deepseek", "modelId": "deepseek-chat"})
    assert (e1.value.status, e1.value.code) == (400, "unsupported_role")
    with pytest.raises(CompanionTransportError) as e2:
        t.set_role({"role": "VISION", "providerId": "openai", "modelId": "nope-1"})
    assert (e2.value.status, e2.value.code) == (400, "unknown_model")
    with pytest.raises(CompanionTransportError) as e3:
        t.set_role({"role": "VISION", "providerId": "openai", "modelId": "gpt-image-1"})
    assert (e3.value.status, e3.value.code) == (400, "unsupported_model_role")


def test_resolve_role_endpoint_is_metadata_only_no_secret(tmp_path):
    vault = InMemoryCredentialVault()
    t = _transport(tmp_path, vault)
    t.set_role({"role": "IMAGE_GENERATION", "providerId": "openai", "modelId": "gpt-image-1"})
    res = t.resolve_role("IMAGE_GENERATION")
    assert res["providerId"] == "openai" and res["modelId"] == "gpt-image-1"
    assert res["runtimeWired"] is False
    assert res["readiness"] == "CONFIGURED_CREDENTIAL_MISSING"
    t.store_credential({"providerId": "openai", "secret": KEY})
    res2 = t.resolve_role("IMAGE_GENERATION")
    assert res2["readiness"] == "FUTURE_NOT_WIRED"
    assert KEY not in json.dumps(res2, ensure_ascii=False)
    with pytest.raises(CompanionTransportError) as e:
        t.resolve_role("BOGUS_ROLE")
    assert e.value.code == "unknown_role"


def test_one_credential_serves_many_roles_over_transport(tmp_path):
    vault = InMemoryCredentialVault()
    t = _transport(tmp_path, vault)
    for role, model in [("VISION", "gpt-4o-mini"), ("IMAGE_GENERATION", "gpt-image-1"),
                        ("STT", "whisper-1"), ("TTS", "gpt-4o-mini-tts")]:
        t.set_role({"role": role, "providerId": "openai", "modelId": model})
    saved = t.store_credential({"providerId": "openai", "secret": KEY})   # ONE key
    assert KEY not in json.dumps(saved, ensure_ascii=False)
    view = t.get_settings()
    for r in ("VISION", "IMAGE_GENERATION", "STT", "TTS"):
        row = next(x for x in view["roleCatalog"] if x["role"] == r)
        assert row["providerConnected"] is True and row["providerId"] == "openai"
    assert KEY not in json.dumps(view, ensure_ascii=False)


# --------------------------------------------------- loopback HTTP
def _free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def _http(base, method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:  # noqa: S310
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


def test_loopback_media_roles_catalog_assignments_and_resolve(tmp_path):
    from tools.character_companion_server import CompanionServer, build_transport

    data_root = tmp_path / "cd"
    vault = InMemoryCredentialVault()
    server = CompanionServer(
        build_transport(data_root=data_root, env={"COMPANION_PROVIDER": "fake"}, credential_vault=vault),
        port=_free_port(),
    )
    server.start()
    try:
        b = server.base_url
        st, view = _http(b, "GET", "/api/companion/settings")
        assert st == 200
        assert any("VIDEO_GENERATION" == r["role"] for r in view["roleCatalog"])
        dialogue_before = view["roles"]["DIALOGUE"]

        for role, pid, model in [
            ("IMAGE_GENERATION", "openai", "gpt-image-1"),
            ("VIDEO_GENERATION", "openai", "sora-2"),
            ("VISION", "openai", "gpt-4o-mini"),
            ("STT", "openai", "whisper-1"),
            ("TTS", "openai", "gpt-4o-mini-tts"),
        ]:
            code, _ = _http(b, "POST", "/api/companion/settings/roles",
                            {"role": role, "providerId": pid, "modelId": model})
            assert code == 200, role

        _, reloaded = _http(b, "GET", "/api/companion/settings")
        assert reloaded["roles"]["IMAGE_GENERATION"] == {"providerId": "openai", "modelId": "gpt-image-1"}
        assert reloaded["roles"]["VIDEO_GENERATION"] == {"providerId": "openai", "modelId": "sora-2"}
        # DIALOGUE remains runtime-wired and unchanged by media edits
        assert reloaded["roles"]["DIALOGUE"] == dialogue_before
        assert reloaded["runtimeWiredRoles"] == ["DIALOGUE"]

        # narrow resolver endpoint
        rc, res = _http(b, "GET", "/api/companion/settings/resolve/IMAGE_GENERATION")
        assert rc == 200 and res["providerId"] == "openai" and res["runtimeWired"] is False

        # unsupported pair -> bounded 400
        bc, err = _http(b, "POST", "/api/companion/settings/roles",
                        {"role": "IMAGE_GENERATION", "providerId": "deepseek", "modelId": "deepseek-chat"})
        assert bc == 400 and err["error"]["code"] == "unsupported_role"

        # no raw secret anywhere; add one and re-check
        _, saved = _http(b, "POST", "/api/companion/settings/credentials",
                         {"providerId": "openai", "secret": KEY})
        assert KEY not in json.dumps(saved)
        _, v2 = _http(b, "GET", "/api/companion/settings")
        assert KEY not in json.dumps(v2)
        rc2, res2 = _http(b, "GET", "/api/companion/settings/resolve/TTS")
        assert rc2 == 200 and KEY not in json.dumps(res2)
    finally:
        server.shutdown()
