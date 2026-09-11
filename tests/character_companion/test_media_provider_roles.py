#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MEDIA PROVIDERS AND MODEL ROLES V1 -- provider registry, settings, resolver.

Offline. No provider call, no network, no real credential. Proves the media
model-role configuration foundation: capability-driven catalog, per-provider
credential reuse across roles, role-assignment persistence + validation, a
provider-call-free role resolver, and "configured != implemented" readiness.
"""

from __future__ import annotations

import json

import pytest

from services.character_companion import (
    CompanionService,
    CompanionTransport,
    InMemoryCredentialVault,
    SettingsStore,
    resolve_role_config,
)
from services.character_companion.provider_registry import (
    ALL_ROLES,
    MODEL_UNVERIFIED,
    POLICY_UNKNOWN,
    ROLE_DIALOGUE,
    ROLE_IMAGE_GENERATION,
    ROLE_REALTIME,
    ROLE_STT,
    ROLE_TTS,
    ROLE_VIDEO_GENERATION,
    ROLE_VISION,
    ProviderRegistryError,
    all_providers,
    get_provider,
    providers_supporting_role,
    require_model_supported,
)
from services.character_companion.provider_resolution import (
    READINESS_CREDENTIAL_MISSING,
    READINESS_FUTURE_NOT_WIRED,
    READINESS_NOT_CONFIGURED,
    READINESS_READY,
    READINESS_UNSUPPORTED,
)
from services.character_companion.settings import CompanionSettings, RoleAssignment, SettingsError, SettingsStore as _SS

from tests.character_companion.conftest import ACCEPTED_ROOT, FAKE_PROVIDER_INFO, make_fake_factory

MEDIA_ROLES = (ROLE_VISION, ROLE_IMAGE_GENERATION, ROLE_VIDEO_GENERATION, ROLE_STT, ROLE_TTS, ROLE_REALTIME)
KEY = "sk-media-roles-test-SECRET-abc123def456"


# --------------------------------------------------------------- registry
def test_media_roles_exist_and_dialogue_plus_image_generation_runtime_wired():
    for role in (ROLE_DIALOGUE, *MEDIA_ROLES, "LOCAL_ALTERNATIVE"):
        assert role in ALL_ROLES
    from services.character_companion.provider_registry import RUNTIME_WIRED_ROLES
    # V1D: IMAGE_GENERATION has a real release execution path -> runtime-wired.
    assert RUNTIME_WIRED_ROLES == (ROLE_DIALOGUE, ROLE_IMAGE_GENERATION)
    # ...but its catalog model stays unverified (runtime-wired != live-verified).
    assert get_provider("openai").get_model("gpt-image-1").status == MODEL_UNVERIFIED
    assert ROLE_VIDEO_GENERATION in ALL_ROLES  # added additively


def test_model_catalog_is_capability_driven_and_backward_compatible():
    openai = get_provider("openai")
    # legacy id-list still present
    assert "gpt-4o-mini" in openai.model_catalog
    # capability metadata on models
    img = openai.get_model("gpt-image-1")
    assert img is not None and "IMAGE_GENERATION" in img.capabilities
    assert img.status == MODEL_UNVERIFIED            # not pretending it works
    assert img.supports_image_to_image is True
    assert img.supports_character_reference is None  # UNKNOWN, never guessed
    # provider-level capability summary is derived, not hand-maintained
    caps = openai.capabilities
    assert "CLOUD" in caps and "VISION" in caps and "IMAGE_GENERATION" in caps


def test_capabilities_that_are_uncertain_are_marked_unverified_not_guessed():
    for pid in ("openai", "qwen", "local"):
        for m in get_provider(pid).models:
            if set(m.capabilities) & {"IMAGE_GENERATION", "VIDEO_GENERATION", "STT", "TTS", "REALTIME"} \
                    or (m.model_id == "llava"):
                assert m.status == MODEL_UNVERIFIED, (pid, m.model_id)
            # never fabricated media facts
            for fact in (m.supports_character_reference, m.supports_video, m.max_duration_seconds):
                assert fact is None or isinstance(fact, (bool, int))


def test_no_registry_entry_deleted():
    ids = {e.provider_id for e in all_providers(include_fake=True)}
    assert {"deepseek", "openai", "qwen", "local", "fake"} <= ids


def test_policy_metadata_is_neutral_and_defaults_unknown():
    # a plain dialogue-only model with no explicit profile stays UNKNOWN
    from services.character_companion.provider_registry import ModelEntry
    m = ModelEntry("x", "X", ("DIALOGUE",))
    assert m.content_policy_profile == POLICY_UNKNOWN
    # nothing in the shipped catalog asserts an adult-content permission
    blob = json.dumps([e.to_json() for e in all_providers()], ensure_ascii=False).lower()
    assert "nsfw" not in blob and "adult" not in blob


def test_require_model_supported_validation():
    # unknown provider
    with pytest.raises(ProviderRegistryError) as e1:
        require_model_supported("ghost", "x", ROLE_DIALOGUE)
    assert e1.value.code == "unknown_provider"
    # provider does not support the role at all
    with pytest.raises(ProviderRegistryError) as e2:
        require_model_supported("deepseek", "deepseek-chat", ROLE_IMAGE_GENERATION)
    assert e2.value.code == "unsupported_role"
    # unknown model id
    with pytest.raises(ProviderRegistryError) as e3:
        require_model_supported("openai", "gpt-9-ultra", ROLE_VISION)
    assert e3.value.code == "unknown_model"
    # known model but wrong capability for the role
    with pytest.raises(ProviderRegistryError) as e4:
        require_model_supported("openai", "gpt-image-1", ROLE_VISION)
    assert e4.value.code == "unsupported_model_role"
    # happy path
    entry, model = require_model_supported("openai", "gpt-image-1", ROLE_IMAGE_GENERATION)
    assert entry.provider_id == "openai" and model.model_id == "gpt-image-1"


def test_providers_supporting_role():
    assert "openai" in providers_supporting_role(ROLE_IMAGE_GENERATION)
    assert "deepseek" not in providers_supporting_role(ROLE_IMAGE_GENERATION)
    assert set(providers_supporting_role(ROLE_DIALOGUE)) >= {"deepseek", "openai", "qwen", "local"}


# --------------------------------------------------------------- settings
def test_old_settings_load_when_media_roles_absent(tmp_path):
    (tmp_path / "companion_settings.json").write_text(json.dumps({
        "version": 1,
        "roles": {"DIALOGUE": {"providerId": "deepseek", "modelId": "deepseek-chat"}},
        "localNumCtx": 20480,
    }), encoding="utf-8")
    s = SettingsStore(tmp_path).load()
    assert s.roles["DIALOGUE"] == RoleAssignment("deepseek", "deepseek-v4-pro")
    assert "VISION" not in s.roles              # media roles simply default unconfigured
    assert s.local_num_ctx == 20480


def test_dialogue_assignment_preserved_across_media_edits(tmp_path):
    store = SettingsStore(tmp_path)
    store.set_role(ROLE_DIALOGUE, "deepseek", "deepseek-chat")
    store.set_role(ROLE_IMAGE_GENERATION, "openai", "gpt-image-1")
    store.set_role(ROLE_VISION, "openai", "gpt-4o-mini")
    s = store.load()
    assert s.roles[ROLE_DIALOGUE] == RoleAssignment("deepseek", "deepseek-v4-pro")  # migrated; media edits preserve it
    assert s.roles[ROLE_IMAGE_GENERATION] == RoleAssignment("openai", "gpt-image-1")
    assert s.roles[ROLE_VISION] == RoleAssignment("openai", "gpt-4o-mini")


def test_media_role_assignment_persists_and_survives_reload(tmp_path):
    SettingsStore(tmp_path).set_role(ROLE_STT, "openai", "whisper-1")
    SettingsStore(tmp_path).set_role(ROLE_TTS, "openai", "gpt-4o-mini-tts")
    SettingsStore(tmp_path).set_role(ROLE_REALTIME, "openai", "gpt-4o-realtime-preview")
    SettingsStore(tmp_path).set_role(ROLE_VIDEO_GENERATION, "openai", "sora-2")
    reopened = SettingsStore(tmp_path).load()
    assert reopened.roles[ROLE_STT] == RoleAssignment("openai", "whisper-1")
    assert reopened.roles[ROLE_VIDEO_GENERATION] == RoleAssignment("openai", "sora-2")


def test_empty_model_id_picks_a_role_capable_default(tmp_path):
    s = SettingsStore(tmp_path).set_role(ROLE_IMAGE_GENERATION, "openai", "")
    assert s.roles[ROLE_IMAGE_GENERATION].model_id == "gpt-image-1"   # not gpt-4o-mini


def test_unsupported_provider_model_and_pair_rejected(tmp_path):
    store = SettingsStore(tmp_path)
    with pytest.raises(SettingsError) as e1:
        store.set_role(ROLE_DIALOGUE, "ghost", "x")
    assert e1.value.code == "unknown_provider"
    with pytest.raises(SettingsError) as e2:
        store.set_role(ROLE_IMAGE_GENERATION, "deepseek", "deepseek-chat")
    assert e2.value.code == "unsupported_role"
    with pytest.raises(SettingsError) as e3:
        store.set_role(ROLE_VISION, "openai", "gpt-9-ultra")
    assert e3.value.code == "unknown_model"
    with pytest.raises(SettingsError) as e4:
        store.set_role(ROLE_VISION, "openai", "gpt-image-1")
    assert e4.value.code == "unsupported_model_role"


def test_one_provider_credential_reused_across_multiple_roles(tmp_path):
    store = SettingsStore(tmp_path)
    for role, model in [
        (ROLE_VISION, "gpt-4o-mini"), (ROLE_IMAGE_GENERATION, "gpt-image-1"),
        (ROLE_STT, "whisper-1"), (ROLE_TTS, "gpt-4o-mini-tts"),
    ]:
        store.set_role(role, "openai", model)
    vault = InMemoryCredentialVault()
    vault.store("openai", KEY)                       # ONE vault entry
    settings = store.load()
    for role in (ROLE_VISION, ROLE_IMAGE_GENERATION, ROLE_STT, ROLE_TTS):
        res = resolve_role_config(role, settings, vault)
        assert res["providerId"] == "openai" and res["providerConnected"] is True
    # the assignments themselves carry no secret
    assert KEY not in json.dumps(settings.to_row(), ensure_ascii=False)


# --------------------------------------------------------------- resolver
def test_resolver_returns_only_selected_provider_and_no_fallback(tmp_path):
    store = SettingsStore(tmp_path)
    store.set_role(ROLE_IMAGE_GENERATION, "openai", "gpt-image-1")
    vault = InMemoryCredentialVault()                 # no key stored
    res = resolve_role_config(ROLE_IMAGE_GENERATION, store.load(), vault)
    assert res["providerId"] == "openai" and res["modelId"] == "gpt-image-1"
    assert res["runtimeWired"] is True
    # credential missing -> bounded readiness, NOT a switch to another provider
    assert res["readiness"] == READINESS_CREDENTIAL_MISSING
    assert "deepseek" not in json.dumps(res) and "qwen" not in json.dumps(res)


def test_resolver_readiness_states(tmp_path):
    store = SettingsStore(tmp_path)
    vault = InMemoryCredentialVault()
    # NOT_CONFIGURED
    assert resolve_role_config(ROLE_VISION, store.load(), vault)["readiness"] == READINESS_NOT_CONFIGURED
    # FUTURE_NOT_WIRED once configured + credential present (media role)
    store.set_role(ROLE_VISION, "openai", "gpt-4o-mini")
    vault.store("openai", KEY)
    assert resolve_role_config(ROLE_VISION, store.load(), vault)["readiness"] == READINESS_FUTURE_NOT_WIRED
    # DIALOGUE with a satisfied credential -> READY (runtime-wired)
    store.set_role(ROLE_DIALOGUE, "openai", "gpt-4o-mini")
    assert resolve_role_config(ROLE_DIALOGUE, store.load(), vault)["readiness"] == READINESS_READY
    # local dialogue needs no credential -> READY
    store.set_role(ROLE_DIALOGUE, "local", "llama3")
    assert resolve_role_config(ROLE_DIALOGUE, store.load(), vault)["readiness"] == READINESS_READY


def test_resolver_reports_unsupported_for_a_stale_pair(tmp_path):
    # write a stale assignment directly (provider later can't serve the role)
    raw = {
        "version": 1,
        "roles": {"IMAGE_GENERATION": {"providerId": "deepseek", "modelId": "deepseek-chat"}},
    }
    (tmp_path / "companion_settings.json").write_text(json.dumps(raw), encoding="utf-8")
    res = resolve_role_config(ROLE_IMAGE_GENERATION, SettingsStore(tmp_path).load(), InMemoryCredentialVault())
    assert res["readiness"] == READINESS_UNSUPPORTED


def test_resolver_never_exposes_raw_credential(tmp_path):
    store = SettingsStore(tmp_path)
    store.set_role(ROLE_TTS, "openai", "gpt-4o-mini-tts")
    vault = InMemoryCredentialVault()
    vault.store("openai", KEY)
    res = resolve_role_config(ROLE_TTS, store.load(), vault)
    blob = json.dumps(res, ensure_ascii=False)
    assert KEY not in blob and "apiKey" not in blob and "secret" not in blob.lower()
    assert res["maskedTail"] and KEY[-4:] in res["maskedTail"]   # only the hint


# --------------------------------------------------------------- via service
def _service(tmp_path, vault=None):
    return CompanionService(
        acceptance_root=ACCEPTED_ROOT, data_root=tmp_path / "cd",
        provider_factory=make_fake_factory("fake reply"), provider_info=FAKE_PROVIDER_INFO,
        settings_store=SettingsStore(tmp_path / "cd"), credential_vault=vault or InMemoryCredentialVault(),
    )


def test_settings_view_exposes_catalog_capabilities_and_role_readiness(tmp_path):
    svc = _service(tmp_path)
    view = svc.settings_view()
    # models + capabilities per provider
    openai = next(p for p in view["providers"] if p["providerId"] == "openai")
    assert any(m["modelId"] == "gpt-image-1" for m in openai["models"])
    assert "IMAGE_GENERATION" in openai["capabilities"]
    # role catalog covers every canonical role, DIALOGUE first
    roles = [r["role"] for r in view["roleCatalog"]]
    assert roles[0] == ROLE_DIALOGUE
    for r in MEDIA_ROLES:
        assert r in roles
    img_row = next(r for r in view["roleCatalog"] if r["role"] == ROLE_IMAGE_GENERATION)
    assert img_row["runtimeWired"] is True
    assert "openai" in img_row["providerIds"]
    assert img_row["readiness"] == READINESS_NOT_CONFIGURED


def test_dialogue_runtime_selection_unchanged(tmp_path):
    """DIALOGUE still resolves through the existing factory path; media config
    additions do not alter which provider a turn uses."""
    svc = _service(tmp_path)
    # default install: fake dialogue -> the injected fake factory answers
    turn_provider = svc._dialogue_provider_id()
    assert turn_provider == "fake"
    factory = svc._dialogue_factory()
    assert factory is svc._provider_factory      # unchanged wiring for fake
    # configure media roles -> dialogue provider id is still 'fake'
    svc.set_role(ROLE_IMAGE_GENERATION, "openai", "gpt-image-1")
    svc.set_role(ROLE_VISION, "openai", "gpt-4o-mini")
    assert svc._dialogue_provider_id() == "fake"


def test_no_provider_call_during_configuration(tmp_path):
    factory = make_fake_factory("should-not-be-called")
    svc = CompanionService(
        acceptance_root=ACCEPTED_ROOT, data_root=tmp_path / "cd",
        provider_factory=factory, provider_info=FAKE_PROVIDER_INFO,
        settings_store=SettingsStore(tmp_path / "cd"), credential_vault=InMemoryCredentialVault(),
    )
    svc.set_role(ROLE_IMAGE_GENERATION, "openai", "gpt-image-1")
    svc.set_role(ROLE_VIDEO_GENERATION, "openai", "sora-2")
    svc.resolve_media_role(ROLE_IMAGE_GENERATION)
    svc.settings_view()
    assert factory.calls == []          # nothing invoked a provider


def test_video_and_speech_roles_configurable_without_executable_pretence(tmp_path):
    svc = _service(tmp_path)
    for role, model in [
        (ROLE_VIDEO_GENERATION, "sora-2"), (ROLE_STT, "whisper-1"),
        (ROLE_TTS, "gpt-4o-mini-tts"), (ROLE_REALTIME, "gpt-4o-realtime-preview"),
    ]:
        svc.set_role(role, "openai", model)
        res = svc.resolve_media_role(role)
        assert res["runtimeWired"] is False
        assert res["readiness"] in (READINESS_FUTURE_NOT_WIRED, READINESS_CREDENTIAL_MISSING)
        assert res["modelStatus"] == MODEL_UNVERIFIED   # honest: not a working feature


def test_settings_survive_reopen_via_transport(tmp_path):
    vault = InMemoryCredentialVault()
    t1 = CompanionTransport(_service(tmp_path, vault))
    t1.set_role({"role": ROLE_VISION, "providerId": "qwen", "modelId": "qwen-vl-plus"})
    t1.set_role({"role": ROLE_IMAGE_GENERATION, "providerId": "openai", "modelId": "gpt-image-1"})
    # brand-new service instance, same data root
    t2 = CompanionTransport(_service(tmp_path, vault))
    view = t2.get_settings()
    assert view["roles"]["VISION"] == {"providerId": "qwen", "modelId": "qwen-vl-plus"}
    assert view["roles"]["IMAGE_GENERATION"] == {"providerId": "openai", "modelId": "gpt-image-1"}


def test_local_text_behavior_unchanged(tmp_path):
    """LocalLLMProvider stays DIALOGUE/local-text; configuring a local VISION
    model is catalog metadata only and does not touch the dialogue path."""
    svc = _service(tmp_path)
    svc.set_role(ROLE_DIALOGUE, "local", "llama3")
    assert svc._dialogue_provider_id() == "local"
    svc.set_role(ROLE_VISION, "local", "llava")
    assert svc._dialogue_provider_id() == "local"        # dialogue unchanged
    res = svc.resolve_media_role(ROLE_VISION)
    assert res["modelStatus"] == MODEL_UNVERIFIED and res["runtimeWired"] is False


def test_raw_credential_never_in_role_or_settings_view(tmp_path):
    vault = InMemoryCredentialVault()
    svc = _service(tmp_path, vault)
    svc.store_credential("openai", KEY)
    svc.set_role(ROLE_IMAGE_GENERATION, "openai", "gpt-image-1")
    blob = json.dumps(svc.settings_view(), ensure_ascii=False)
    assert KEY not in blob
    assert KEY not in json.dumps(svc.resolve_media_role(ROLE_IMAGE_GENERATION), ensure_ascii=False)
