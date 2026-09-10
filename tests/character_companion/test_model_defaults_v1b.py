"""V1B: каталог, миграция, bootstrap и payload; только temp data и injected HTTP."""

import json
import socket
from dataclasses import replace

import pytest

from services.character_companion import (
    CompanionError, CompanionService, CompanionSettings, CompanionTransport, InMemoryCredentialVault,
    RoleAssignment, SettingsStore,
)
from services.character_companion import provider_registry as registry
from services.character_companion.cloud_provider import CloudProviderError
from services.character_companion.provider_resolution import CompanionConfigError, _factory_for
from services.character_companion.settings import SettingsError
from services.character_runtime import RuntimeMemoryBackend
from tests.character_companion.conftest import ACCEPTED_ROOT, FAKE_PROVIDER_INFO, make_fake_factory
from tools import character_companion_server as server

PRO = "deepseek-v4-pro"
FLASH = "deepseek-v4-flash"
TEXT_ROLES = ("DIALOGUE", "WRITING_ASSISTANT")
REASONING = "PRIVATE_REASONING_FIXTURE_DO_NOT_PERSIST"


def _forbidden(*args, **kwargs):
    raise AssertionError("unexpected network, real vault or fallback access")


@pytest.fixture(autouse=True)
def offline_only(monkeypatch):
    monkeypatch.setattr(socket, "create_connection", _forbidden)
    monkeypatch.setattr(socket.socket, "connect", _forbidden)
    monkeypatch.setattr(server, "build_default_credential_vault", _forbidden)


def test_catalog_and_frontend_writing_assistant_choices(tmp_path):
    entry = registry.get_provider("deepseek")
    assert entry.model_catalog == (PRO, FLASH)
    assert entry.default_model == PRO
    service = _service(tmp_path, _forbidden)
    view = CompanionTransport(service).get_settings()
    exported = next(p for p in view["providers"] if p["providerId"] == "deepseek")
    for role in TEXT_ROLES:
        choices = [m for m in exported["models"] if role in m["roles"]]
        assert [(m["modelId"], m["displayName"]) for m in choices] == [
            (PRO, "DeepSeek V4 Pro"), (FLASH, "DeepSeek V4 Flash"),
        ]


@pytest.mark.parametrize("role", TEXT_ROLES)
def test_empty_model_honors_explicit_default_with_flash_first(tmp_path, monkeypatch, role):
    entry = registry.get_provider("deepseek")
    monkeypatch.setitem(registry._BY_ID, "deepseek", replace(entry, models=tuple(reversed(entry.models))))
    settings = SettingsStore(tmp_path).set_role(role, "deepseek", " ")
    assert settings.roles[role] == RoleAssignment("deepseek", PRO)


@pytest.mark.parametrize("default,code", [("missing", "unknown_model"), ("vision", "unsupported_model_role")])
def test_invalid_text_default_does_not_select_first_model(tmp_path, monkeypatch, default, code):
    entry = registry.get_provider("deepseek")
    vision = registry.ModelEntry("vision", "Fixture", (registry.CAP_VISION,))
    monkeypatch.setitem(registry._BY_ID, "deepseek", replace(entry, default_model=default, models=entry.models + (vision,)))
    with pytest.raises(SettingsError) as exc:
        SettingsStore(tmp_path).set_role("DIALOGUE", "deepseek", "")
    assert exc.value.code == code
    assert not SettingsStore(tmp_path).path.exists()


@pytest.mark.parametrize("legacy", ["deepseek-chat", "deepseek-reasoner"])
@pytest.mark.parametrize("role", TEXT_ROLES)
def test_legacy_load_and_save_migration_is_idempotent(tmp_path, legacy, role):
    store = SettingsStore(tmp_path)
    row = {"roles": {
        role: {"providerId": "deepseek", "modelId": legacy},
        "VISION": {"providerId": "deepseek", "modelId": legacy},
        "LOCAL_ALTERNATIVE": {"providerId": "local", "modelId": "llama3"},
    }, "localNumCtx": 20480, "ui": {"theme": "dark"}}
    store.path.write_text(json.dumps(row), encoding="utf-8")
    before = store.path.read_bytes()
    loaded = store.load()
    assert store.path.read_bytes() == before  # чтение не пишет файл
    assert loaded.roles[role] == RoleAssignment("deepseek", PRO)
    assert loaded.roles["VISION"].model_id == legacy  # только текстовые роли
    assert loaded.roles["LOCAL_ALTERNATIVE"] == RoleAssignment("local", "llama3")
    assert loaded.local_num_ctx == 20480 and loaded.ui == {"theme": "dark"}
    store.save(loaded)
    migrated = store.path.read_bytes()
    store.save(store.load())
    assert store.path.read_bytes() == migrated
    assert store.set_role(role, "deepseek", legacy).roles[role].model_id == PRO


def test_explicit_flash_and_role_independence_survive_restart(tmp_path):
    store = SettingsStore(tmp_path)
    store.set_role("DIALOGUE", "deepseek", PRO)
    store.set_role("WRITING_ASSISTANT", "deepseek", FLASH)
    assert store.load().roles["DIALOGUE"].model_id == PRO
    store.set_role("DIALOGUE", "local", "llama3")
    reopened = SettingsStore(tmp_path).load()
    assert reopened.roles["WRITING_ASSISTANT"] == RoleAssignment("deepseek", FLASH)
    assert reopened.roles["DIALOGUE"] == RoleAssignment("local", "llama3")


@pytest.mark.parametrize("role", TEXT_ROLES)
@pytest.mark.parametrize("provider,model,code", [
    ("ghost", PRO, "unknown_provider"),
    ("deepseek", "stale-model", "unknown_model"),
    ("deepseek", "gpt-4o-mini", "unknown_model"),
    ("deepseek", "", "unknown_model"),
    ("openai", "gpt-image-1", "unsupported_model_role"),
])
def test_loaded_invalid_assignment_fails_before_vault_or_factory(role, provider, model, code):
    class UntouchedVault:
        has = resolve = _forbidden

    settings = CompanionSettings.from_row({"roles": {role: {"providerId": provider, "modelId": model}}})
    assignment = settings.roles[role]
    with pytest.raises(CompanionConfigError) as exc:
        _factory_for(settings, UntouchedVault(), assignment.provider_id, assignment.model_id,
                     role=role, fake_factory=_forbidden, http_post_local=_forbidden, http_post_cloud=_forbidden)
    assert exc.value.code == code


@pytest.mark.parametrize("legacy", ["deepseek-chat", "deepseek-reasoner"])
def test_execution_itself_never_migrates_or_defaults(legacy):
    with pytest.raises(CompanionConfigError) as exc:
        _factory_for(CompanionSettings.defaults(), None, "deepseek", legacy, fake_factory=_forbidden)
    assert exc.value.code == "unknown_model"


def _service(tmp_path, capture):
    vault = InMemoryCredentialVault()
    vault.store("deepseek", "fixture-only-not-a-real-key")
    return CompanionService(
        acceptance_root=ACCEPTED_ROOT, data_root=tmp_path,
        provider_factory=_forbidden, provider_info=FAKE_PROVIDER_INFO,
        settings_store=SettingsStore(tmp_path), credential_vault=vault,
        http_post_cloud=capture, http_post_local=_forbidden,
    )


@pytest.mark.parametrize("role", TEXT_ROLES)
@pytest.mark.parametrize("model", [PRO, FLASH])
def test_selected_model_reaches_payload_and_only_final_content_is_used(tmp_path, role, model):
    calls = []

    def capture(url, payload, headers, timeout):
        calls.append((url, payload))
        return {"choices": [{"message": {"content": "Финальный ответ.", "reasoning_content": REASONING}}]}

    service = _service(tmp_path, capture)
    sid = service.create_session("kira").session_id
    if role == "DIALOGUE":
        service.set_role("DIALOGUE", "deepseek", model)
        assert service.send_message(sid, "Привет.").response == "Финальный ответ."
        assert service.get_messages(sid)[-1].text == "Финальный ответ."
    else:
        # V2A: the co-author executes on the DIALOGUE assignment; a separately
        # stored WRITING_ASSISTANT assignment is IGNORED for execution.
        service.set_role("DIALOGUE", "deepseek", model)
        service.set_role("WRITING_ASSISTANT", "deepseek", FLASH if model == PRO else PRO)
        out = service.writing_assistant_rewrite("черновик")
        assert out == {"suggestion": "Финальный ответ.", "provider": "deepseek",
                       "model": model, "mode": "EXPAND"}
        assert service.get_messages(sid) == ()
    assert len(calls) == 1
    url, payload = calls[0]
    assert url == "https://api.deepseek.com/v1/chat/completions"
    assert set(payload) == {"model", "messages"}  # generic request без thinking controls
    assert payload["model"] == model
    backend = RuntimeMemoryBackend(tmp_path / "characters" / "kira" / "memory", "kira")
    try:
        events = list(backend.load_events_causal("kira"))
        assert REASONING not in repr(events)
    finally:
        backend.close()
    assert REASONING not in repr(service.get_messages(sid))


@pytest.mark.parametrize("role", TEXT_ROLES)
def test_provider_failure_never_retries_or_falls_back(tmp_path, role):
    calls = []

    def fail(url, payload, headers, timeout):
        calls.append(payload["model"])
        raise CloudProviderError("provider_failed", "fixture failure")

    service = _service(tmp_path, fail)
    sid = service.create_session("kira").session_id
    if role == "DIALOGUE":
        service.set_role("DIALOGUE", "deepseek", PRO)
        with pytest.raises(CompanionError) as exc:
            service.send_message(sid, "Привет.")
        assert SettingsStore(tmp_path).load().roles["DIALOGUE"].model_id == PRO
    else:
        # V2A: co-author failure follows the DIALOGUE assignment; the stored
        # WRITING_ASSISTANT assignment neither rescues nor redirects it.
        service.set_role("DIALOGUE", "deepseek", PRO)
        service.set_role("WRITING_ASSISTANT", "deepseek", FLASH)
        with pytest.raises(CompanionError) as exc:
            service.writing_assistant_rewrite("черновик")
        assert SettingsStore(tmp_path).load().roles["WRITING_ASSISTANT"].model_id == FLASH  # untouched
    assert exc.value.code in ("provider_failed", "assistant_failed")
    assert calls == [PRO]  # exactly one attempt, on the DIALOGUE model, never FLASH
    assert service.get_messages(sid) == ()


@pytest.mark.parametrize("content", [None, ""])
def test_reasoning_without_final_content_is_not_a_reply(tmp_path, content):
    service = _service(tmp_path, lambda *args: {"choices": [{"message": {
        "content": content, "reasoning_content": REASONING,
    }}]})
    service.set_role("WRITING_ASSISTANT", "deepseek", PRO)
    with pytest.raises(CompanionError) as exc:
        service.writing_assistant_rewrite("черновик")
    assert exc.value.code == "assistant_failed"


def test_new_release_bootstrap_and_existing_assignments(tmp_path):
    server.build_transport(data_root=tmp_path, env={}, mode="release", credential_vault=InMemoryCredentialVault())
    store = SettingsStore(tmp_path)
    assert store.load().roles == {r: RoleAssignment("deepseek", PRO) for r in TEXT_ROLES}
    store.set_role("DIALOGUE", "local", "llama3")
    store.set_role("WRITING_ASSISTANT", "deepseek", FLASH)
    before = store.path.read_bytes()
    server.build_transport(data_root=tmp_path, env={}, mode="release", credential_vault=InMemoryCredentialVault())
    assert store.path.read_bytes() == before


def test_existing_single_fake_assignment_is_not_reseeded_for_release(tmp_path):
    store = SettingsStore(tmp_path)
    store.set_role("DIALOGUE", "fake", "fake")
    before = store.path.read_bytes()
    server.build_transport(data_root=tmp_path, env={}, mode="release", credential_vault=InMemoryCredentialVault())
    assert store.path.read_bytes() == before
    assert "WRITING_ASSISTANT" not in store.load().roles


@pytest.mark.parametrize("mode,env,expected", [
    ("dev", {}, RoleAssignment("fake", "fake")),
    ("release", {"COMPANION_PROVIDER": "fake"}, RoleAssignment("fake", "fake")),
    ("release", {"COMPANION_PROVIDER": "local", "LOCAL_LLM_MODEL": "llama3.1"}, RoleAssignment("local", "llama3.1")),
])
def test_explicit_fake_local_and_dev_bootstrap_preserved(tmp_path, mode, env, expected):
    server.build_transport(data_root=tmp_path, env=env, mode=mode, credential_vault=InMemoryCredentialVault())
    settings = SettingsStore(tmp_path).load()
    assert settings.dialogue() == expected
    assert "WRITING_ASSISTANT" not in settings.roles


def test_injected_service_factory_without_settings_stays_offline(tmp_path):
    service = CompanionService(acceptance_root=ACCEPTED_ROOT, data_root=tmp_path,
                               provider_factory=make_fake_factory("injected"), provider_info=FAKE_PROVIDER_INFO)
    sid = service.create_session("kira").session_id
    assert service.send_message(sid, "Привет.").response == "injected"
