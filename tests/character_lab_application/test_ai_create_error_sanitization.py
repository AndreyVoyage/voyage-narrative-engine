"""AI-Create provider error sanitization (offline, fail-closed, anti-spoof)."""

from __future__ import annotations

import pytest

from services.character_draft import CharacterDraftError
from services.character_lab_application import (
    DRAFT_AI_ERROR,
    CharacterLabApplicationConfig,
    CharacterLabApplicationError,
    CharacterLabApplicationService,
)
from services.character_lab_application.provider import (
    AI_CREATE_GENERIC_FAILURE_MESSAGE,
    AI_CREATE_SAFE_MISSING_KEY_MESSAGE,
    DEEPSEEK_CONFIG_INVALID_MESSAGE,
    safe_ai_create_provider_message,
)


def _service(tmp_path):
    return CharacterLabApplicationService(
        CharacterLabApplicationConfig(character_authoring_root=tmp_path / "authoring")
    )


def _run_create(service, provider):
    with pytest.raises(CharacterLabApplicationError) as caught:
        service.start_ai_creation(
            display_name="Катя", description="shy", provider=provider
        )
    return caught.value


def test_provider_error_body_not_surfaced(tmp_path):
    def leaking(messages, system):
        raise CharacterDraftError(
            "provider error: HTTP 401 "
            '{"private":"response-body-secret"} '
            "Authorization: Bearer fake-secret "
            "api_key=fake-secret "
            "https://example.invalid/?token=fake-secret "
            "request-body-secret"
        )

    exc = _run_create(_service(tmp_path), leaking)
    assert exc.code == DRAFT_AI_ERROR
    assert exc.message == AI_CREATE_GENERIC_FAILURE_MESSAGE
    for fragment in (
        "response-body-secret",
        "Authorization",
        "Bearer",
        "fake-secret",
        "api_key=",
        "token=",
        "request-body-secret",
        "https://",
        "HTTP 401",
    ):
        assert fragment not in exc.message


def test_prefix_spoof_not_accepted_as_safe(tmp_path):
    def spoof(messages, system):
        raise CharacterDraftError(
            "API key is not configured. Set DEEPSEEK_API_KEY and retry. "
            "Authorization: Bearer fake-secret"
        )

    exc = _run_create(_service(tmp_path), spoof)
    assert exc.message == AI_CREATE_GENERIC_FAILURE_MESSAGE


def test_exact_missing_key_maps_to_canonical_guidance(tmp_path):
    def missing(messages, system):
        raise CharacterDraftError(
            "API key is not configured. Set DEEPSEEK_API_KEY and retry."
        )

    exc = _run_create(_service(tmp_path), missing)
    assert exc.message == AI_CREATE_SAFE_MISSING_KEY_MESSAGE


def test_invalid_config_guidance_preserved(tmp_path):
    def invalid(messages, system):
        raise CharacterDraftError(DEEPSEEK_CONFIG_INVALID_MESSAGE)

    exc = _run_create(_service(tmp_path), invalid)
    assert exc.message == DEEPSEEK_CONFIG_INVALID_MESSAGE


def test_helper_non_draft_error_is_generic():
    assert (
        safe_ai_create_provider_message(RuntimeError("boom"))
        == AI_CREATE_GENERIC_FAILURE_MESSAGE
    )


def test_helper_http_body_is_generic():
    exc = CharacterDraftError('provider error: HTTP 500 {"secret":"x"}')
    assert safe_ai_create_provider_message(exc) == AI_CREATE_GENERIC_FAILURE_MESSAGE
