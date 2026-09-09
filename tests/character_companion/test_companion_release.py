#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KIRA COMPANION RELEASE ASSEMBLY V1 -- release-specific behaviour.

Offline: fake / local-fake providers, in-memory vault, temp data root. No cloud,
no real local generation, no network. Proves: release manifest content + no
secrets, release-mode fake guard, end-to-end restart persistence, num_ctx path,
launcher/build-script sanity."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.character_companion import (
    RELEASE_NAME,
    RELEASE_VERSION,
    CompanionError,
    CompanionService,
    InMemoryCredentialVault,
    LocalLLMConfig,
    SettingsStore,
    build_local_llm_provider_factory,
    build_release_manifest,
    normalize_mode,
)

from tests.character_companion.conftest import ACCEPTED_ROOT, FAKE_PROVIDER_INFO, make_fake_factory

_REPO = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------- helpers
def _svc(tmp_path, *, mode="dev", data_root=None, vault=None, http_post_local=None):
    dr = data_root or (tmp_path / "cd")
    return CompanionService(
        acceptance_root=ACCEPTED_ROOT, data_root=dr,
        provider_factory=make_fake_factory("fake reply"), provider_info=FAKE_PROVIDER_INFO,
        settings_store=SettingsStore(dr), credential_vault=vault or InMemoryCredentialVault(),
        mode=mode, http_post_local=http_post_local,
    )


def _walk_strings(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield str(k)
            yield from _walk_strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_strings(v)
    else:
        yield str(obj)


# ---------------------------------------------------------- 1. manifest
def test_release_manifest_identity_and_no_secrets():
    m = build_release_manifest(acceptance_root=ACCEPTED_ROOT, frontend_build_id="index-abc123")
    assert m["release"]["name"] == RELEASE_NAME == "KIRA Companion MVP RC1"
    assert m["release"]["version"] == RELEASE_VERSION
    ac = m["acceptedCharacter"]
    assert ac["characterId"] == "kira"
    assert ac["packageId"] == "kira-r4-canonical-run-1-package"
    assert ac["sourceHash"] == "e26f83dafa26e61af82f29b654b592300c8f3f7bd295d07bd4d2b6527ae3eebd"
    assert m["characterCore"]["contractVersion"]
    assert m["secrets"] == "none"
    assert m["localContext"]["recommendedMinNumCtx"] == 16384
    assert m["localContext"]["kiraGroundedObservedPromptTokens"] == 10014
    assert m["frontendBuildId"] == "index-abc123"
    # absolutely no credential-shaped content anywhere
    blob = json.dumps(m, ensure_ascii=False).lower()
    for banned in ("api_key", "authorization", "bearer ", "sk-", "secret\":"):
        assert banned not in blob


def test_release_info_via_service_carries_mode_and_dialogue_provider(tmp_path):
    svc = _svc(tmp_path, mode="release")
    info = svc.release_info(frontend_build_id="fb")
    assert info["mode"] == "release" and info["dialogueProvider"] == "fake"
    assert info["acceptedCharacter"]["characterId"] == "kira"


def test_normalize_mode_rejects_unknown():
    assert normalize_mode(None) == "dev" and normalize_mode("RELEASE") == "release"
    with pytest.raises(Exception):
        normalize_mode("prod")


# ---------------------------------------------------------- 2. release-mode fake guard
def test_release_mode_never_answers_as_fake_kira(tmp_path):
    svc = _svc(tmp_path, mode="release")                       # default settings -> DIALOGUE = fake
    sid = svc.create_session("kira").session_id
    with pytest.raises(CompanionError) as exc:
        svc.send_message(sid, "Привет, Кира.")
    assert exc.value.code == "provider_not_configured"
    assert svc.get_messages(sid) == ()                         # nothing persisted


def test_dev_mode_fake_still_works(tmp_path):
    svc = _svc(tmp_path, mode="dev")
    sid = svc.create_session("kira").session_id
    assert svc.send_message(sid, "hi").response == "fake reply"


def test_release_mode_with_configured_local_provider_works(tmp_path):
    box = []

    def cap(url, payload, timeout):
        box.append(payload)
        return {"message": {"content": "local kira reply"}}

    svc = _svc(tmp_path, mode="release", http_post_local=cap)
    svc._settings_store.set_role("DIALOGUE", "local", "llama3")
    svc._settings_store.set_local_num_ctx(16384)
    sid = svc.create_session("kira").session_id
    turn = svc.send_message(sid, "Привет.")
    assert turn.response == "local kira reply"
    # num_ctx path: settings -> resolution -> LocalLLMConfig -> options.num_ctx
    assert box[-1]["options"] == {"num_ctx": 16384}


# ---------------------------------------------------------- 3. end-to-end restart acceptance
SCENE = {"place": "Кухня", "time": "Вечер", "situation": "Пьют чай", "mood": "Тёплое", "freeform": "Дождь."}


def test_full_restart_persistence_acceptance(tmp_path):
    data_root = tmp_path / "cd"

    # --- session 1 ---
    s1 = _svc(tmp_path, mode="dev", data_root=data_root)
    scened = s1.create_session("kira", title="Сцена", scene=SCENE)
    s1.send_message(scened.session_id, "Первое.")
    s1.send_message(scened.session_id, "Второе.")
    ordinary = s1.create_session("kira")
    s1.send_message(ordinary.session_id, "Отдельный разговор.")
    s1._settings_store.set_role("DIALOGUE", "local", "llama3.1")
    s1._settings_store.set_local_num_ctx(20480)
    s1._vault.store("deepseek", "sk-test-restart-SECRET-000111")   # in-memory here; DPAPI covered elsewhere
    before_scene = [(m.role, m.text) for m in s1.get_messages(scened.session_id)]
    del s1

    # --- fresh process (new instances, same data root; vault re-seeded like DPAPI would persist) ---
    vault2 = InMemoryCredentialVault()
    vault2.store("deepseek", "sk-test-restart-SECRET-000111")     # simulates the durable vault blob
    s2 = _svc(tmp_path, mode="dev", data_root=data_root, vault=vault2)

    chats = {c.session_id: c for c in s2.list_sessions("kira")}
    assert scened.session_id in chats and ordinary.session_id in chats     # both chats remain
    assert chats[scened.session_id].scene.place == "Кухня"                 # scene remains
    hist = s2.get_messages(scened.session_id)
    assert [(m.role, m.text) for m in hist] == before_scene               # history + order remain
    assert [m.seq for m in hist] == sorted(m.seq for m in hist)

    view = s2.settings_view()
    assert view["roles"]["DIALOGUE"] == {"providerId": "local", "modelId": "llama3.1"}   # settings remain
    assert view["local"]["numCtx"] == 20480                                # num_ctx remains
    ds = next(p for p in view["providers"] if p["providerId"] == "deepseek")
    assert ds["connected"] is True                                         # secure credential remains (metadata only)
    assert "sk-test-restart" not in json.dumps(view)                       # never the raw key

    # continue after restart
    s2._settings_store.set_role("DIALOGUE", "fake", "fake")
    s2.send_message(scened.session_id, "После перезапуска.")
    after = s2.get_messages(scened.session_id)
    assert len(after) == len(before_scene) + 2 and after[-1].role == "character"


# ---------------------------------------------------------- 4. launcher / build script sanity
def test_windows_launcher_and_build_script_present_and_anchored():
    launcher = (_REPO / "tools" / "start_character_companion.ps1").read_text(encoding="utf-8")
    build = (_REPO / "tools" / "build_character_companion_release.ps1").read_text(encoding="utf-8")

    # launcher does not depend on the shell CWD, uses release mode + web-root,
    # never prints a credential, and puts user data outside the build output
    assert "$MyInvocation.MyCommand.Path" in launcher and "Split-Path -Parent" in launcher
    assert '"--mode", "release"' in launcher and '"--web-root"' in launcher
    assert "LOCALAPPDATA" in launcher and "KiraCompanion" in launcher
    assert "api_key" not in launcher.lower() and "authorization" not in launcher.lower()

    # build script uses installed tooling only, emits a no-secret manifest
    build_code = "\n".join(l for l in build.splitlines() if not l.lstrip().startswith("#"))
    assert "npm install" not in build_code and "pip install" not in build_code
    assert "build_release_manifest" in build and "RELEASE_MANIFEST.json" in build
    assert "vite" in build


def test_release_manifest_module_has_no_hardcoded_secret():
    src = (_REPO / "services" / "character_companion" / "release.py").read_text(encoding="utf-8")
    for banned in ("sk-", "api_key =", "OPENAI_API_KEY", "DEEPSEEK_API_KEY"):
        assert banned not in src
