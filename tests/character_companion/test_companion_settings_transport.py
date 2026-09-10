#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SECURE COMPANION DESKTOP FOUNDATIONS V1 -- settings transport + loopback.

Dict-level CompanionTransport plus real loopback HTTP through
tools/character_companion_server.py. Offline; in-memory vault (fast) or DPAPI
(restart-persistence test); no external network; no raw-secret GET anywhere."""

from __future__ import annotations

import json
import socket
import sys
import urllib.request

import pytest

from services.character_companion import CompanionService, CompanionTransport, InMemoryCredentialVault, SettingsStore
from services.character_companion.transport import CompanionTransportError

from tests.character_companion.conftest import ACCEPTED_ROOT, FAKE_PROVIDER_INFO, make_fake_factory

KEY = "sk-transport-test-SECRET-abcdef123456"


def _transport(tmp_path, *, vault=None, data_root=None):
    dr = data_root or (tmp_path / "cd")
    svc = CompanionService(
        acceptance_root=ACCEPTED_ROOT, data_root=dr,
        provider_factory=make_fake_factory("fake reply"), provider_info=FAKE_PROVIDER_INFO,
        settings_store=SettingsStore(dr), credential_vault=vault or InMemoryCredentialVault(),
    )
    return CompanionTransport(svc)


def test_dict_roundtrip_providers_roles_credentials(tmp_path):
    t = _transport(tmp_path)

    # list providers
    view = t.get_settings()
    ids = [p["providerId"] for p in view["providers"]]
    assert {"deepseek", "openai", "qwen", "local", "fake"} <= set(ids)
    assert view["dataRoutingNote"] and "выбранному провайдеру" in view["dataRoutingNote"]

    # save role mapping (DIALOGUE only is runtime-wired)
    assert "DIALOGUE" in view["runtimeWiredRoles"]
    t.set_role({"role": "DIALOGUE", "providerId": "deepseek", "modelId": "deepseek-chat"})
    assert t.get_settings()["roles"]["DIALOGUE"] == {"providerId": "deepseek", "modelId": "deepseek-v4-pro"}

    # save credential -> connected=true, NEVER the raw key in any response
    saved = t.store_credential({"providerId": "deepseek", "secret": KEY})
    ds = next(p for p in saved["providers"] if p["providerId"] == "deepseek")
    assert ds["connected"] is True and ds["maskedTail"] and KEY not in json.dumps(saved, ensure_ascii=False)

    # replace credential
    t.store_credential({"providerId": "deepseek", "secret": KEY + "-v2"})
    assert KEY not in json.dumps(t.get_settings(), ensure_ascii=False)

    # remove credential
    removed = t.delete_credential("deepseek")
    assert next(p for p in removed["providers"] if p["providerId"] == "deepseek")["connected"] is False

    # local num_ctx config
    out = t.set_local_settings({"numCtx": 16384})
    assert out["local"]["numCtx"] == 16384
    out2 = t.set_local_settings({"numCtx": 4096})
    assert out2["local"]["numCtxWarning"] is True          # below the KIRA-safe hint

    # missing credential -> bounded, structured failure, NO silent fallback
    t.set_role({"role": "DIALOGUE", "providerId": "openai", "modelId": "gpt-4o-mini"})
    res = t.test_provider({"providerId": "openai"})
    assert res["ok"] is False and res["status"] in ("missing_credential", "provider_unavailable", "provider_failed")
    assert "fake reply" not in json.dumps(res, ensure_ascii=False) and KEY not in json.dumps(res)


def test_dialogue_context_budget_setting(tmp_path):
    """COMPANION_CONTEXT_POLICY_V1C: the DIALOGUE-only estimated-token context
    budget -- default, round-trip, validation, and separation from num_ctx."""
    from services.character_companion.settings import (
        DIALOGUE_CONTEXT_BUDGET_DEFAULT,
        DIALOGUE_CONTEXT_BUDGET_MAX,
        DIALOGUE_CONTEXT_BUDGET_MIN,
        CompanionSettings,
        SettingsError,
        SettingsStore,
    )

    assert (DIALOGUE_CONTEXT_BUDGET_MIN, DIALOGUE_CONTEXT_BUDGET_DEFAULT,
            DIALOGUE_CONTEXT_BUDGET_MAX) == (16384, 32768, 131072)

    # 2 -- key absent everywhere -> normalized to the default, no write needed
    assert CompanionSettings().dialogue_context_budget_est_tokens == 32768
    assert CompanionSettings.from_row({}).dialogue_context_budget_est_tokens == 32768
    store = SettingsStore(tmp_path / "s2")
    assert not store.path.exists()
    assert store.load().dialogue_context_budget_est_tokens == 32768   # in-memory default
    assert not store.path.exists()                                    # NOT migrated on load

    # 3 -- round-trip through save/load and to_row/from_row
    for value in (16384, 32768, 65536, 131072):
        out = store.set_dialogue_context_budget_est_tokens(value)
        assert out.dialogue_context_budget_est_tokens == value
        assert store.load().dialogue_context_budget_est_tokens == value
        row = out.to_row()
        assert row["dialogueContextBudgetEstTokens"] == value
        assert CompanionSettings.from_row(row).dialogue_context_budget_est_tokens == value

    # 4 -- invalid / out-of-range: setter raises (like set_local_num_ctx),
    #      persisted junk normalizes to the default on load
    for bad in (16383, 131073, 0, -5):
        with pytest.raises(SettingsError) as exc:
            store.set_dialogue_context_budget_est_tokens(bad)
        assert exc.value.code == "invalid_context_budget"
    with pytest.raises(SettingsError):
        store.set_dialogue_context_budget_est_tokens(True)          # bool is not an int here
    for junk in (999, "x", None, 200000):
        assert CompanionSettings.from_row(
            {"dialogueContextBudgetEstTokens": junk}
        ).dialogue_context_budget_est_tokens == 32768

    # 23 -- completely separate from local_num_ctx
    store.set_local_num_ctx(20480)
    store.set_dialogue_context_budget_est_tokens(65536)
    loaded = store.load()
    assert loaded.local_num_ctx == 20480
    assert loaded.dialogue_context_budget_est_tokens == 65536
    assert "dialogueContextBudgetEstTokens" != "localNumCtx"
    # the settings row never trips the secret guard with the "...tokens" key
    saved_row = loaded.to_row()
    assert "dialogueContextBudgetEstTokens" in saved_row and "localNumCtx" in saved_row


def test_bounded_errors(tmp_path):
    t = _transport(tmp_path)
    with pytest.raises(CompanionTransportError) as e1:
        t.set_role({"role": "STT", "providerId": "deepseek", "modelId": "x"})
    assert (e1.value.status, e1.value.code) == (400, "unsupported_role")
    with pytest.raises(CompanionTransportError) as e2:
        t.store_credential({"providerId": "local", "secret": KEY})
    assert e2.value.code == "no_credential_needed"
    with pytest.raises(CompanionTransportError) as e3:
        t.set_local_settings({"numCtx": -5})
    assert e3.value.code in ("invalid_num_ctx",)
    with pytest.raises(CompanionTransportError):
        t.store_credential({"providerId": "deepseek", "secret": "  "})
    with pytest.raises(CompanionTransportError) as e5:
        t.set_role({"role": "DIALOGUE", "providerId": "ghost", "modelId": "x"})
    assert e5.value.code == "unknown_provider"


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


def test_loopback_settings_and_no_raw_secret_get(tmp_path):
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
        st, providers = _http(b, "GET", "/api/companion/settings")
        assert st == 200 and any(p["providerId"] == "deepseek" for p in providers["providers"])

        _http(b, "POST", "/api/companion/settings/roles",
              {"role": "DIALOGUE", "providerId": "deepseek", "modelId": "deepseek-chat"})
        _, saved = _http(b, "POST", "/api/companion/settings/credentials",
                         {"providerId": "deepseek", "secret": KEY})
        assert KEY not in json.dumps(saved)
        ds = next(p for p in saved["providers"] if p["providerId"] == "deepseek")
        assert ds["connected"] is True

        # there is NO route that returns the raw key
        st2, _ = _http(b, "GET", "/api/companion/settings/credentials/deepseek")
        assert st2 == 404   # unknown route -- no secret GET exists

        _, out = _http(b, "POST", "/api/companion/settings/local", {"numCtx": 12000})
        assert out["local"]["numCtx"] == 12000

        st3, err = _http(b, "POST", "/api/companion/settings/roles", {"role": "STT", "providerId": "deepseek"})
        assert st3 == 400 and err["error"]["code"] == "unsupported_role"
    finally:
        server.shutdown()


@pytest.mark.skipif(sys.platform != "win32", reason="secret persistence uses DPAPI")
def test_loopback_restart_retains_settings_and_secure_secret(tmp_path):
    from services.character_companion import build_default_credential_vault
    from tools.character_companion_server import CompanionServer, build_transport

    data_root = tmp_path / "cd"

    s1 = CompanionServer(build_transport(data_root=data_root, env={"COMPANION_PROVIDER": "fake"},
                                         credential_vault=build_default_credential_vault(data_root)),
                         port=_free_port())
    s1.start()
    try:
        b = s1.base_url
        _http(b, "POST", "/api/companion/settings/roles",
              {"role": "DIALOGUE", "providerId": "deepseek", "modelId": "deepseek-reasoner"})
        _http(b, "POST", "/api/companion/settings/local", {"numCtx": 20480})
        _http(b, "POST", "/api/companion/settings/credentials", {"providerId": "deepseek", "secret": KEY})
    finally:
        s1.shutdown()

    s2 = CompanionServer(build_transport(data_root=data_root, env={"COMPANION_PROVIDER": "fake"},
                                         credential_vault=build_default_credential_vault(data_root)),
                         port=_free_port())
    s2.start()
    try:
        _, view = _http(s2.base_url, "GET", "/api/companion/settings")
        assert view["roles"]["DIALOGUE"] == {"providerId": "deepseek", "modelId": "deepseek-v4-pro"}
        assert view["local"]["numCtx"] == 20480
        ds = next(p for p in view["providers"] if p["providerId"] == "deepseek")
        assert ds["connected"] is True          # DPAPI-encrypted secret survived the restart
        assert KEY not in json.dumps(view)
    finally:
        s2.shutdown()
