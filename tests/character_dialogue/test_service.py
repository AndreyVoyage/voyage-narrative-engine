"""Offline unit tests for :class:`TestDialogueService`."""

from __future__ import annotations

import pytest

from services.character_dialogue import (
    DialogueMessage,
    TestDialogueError,
    TestDialoguePin,
    TestDialogueProviderError,
    TestDialogueService,
)
from services.character_dialogue.service import (
    GENERIC_PROVIDER_FAILURE_MESSAGE,
    SAFE_MISSING_KEY_MESSAGE,
)
from services.character_draft import CharacterDraftError

from tests.character_dialogue._helpers import capturing_provider, make_pin, make_semantic


def test_start_binds_exact_pin_and_freezes_display_name():
    semantic = make_semantic()
    pin = make_pin(semantic)
    provider, _ = capturing_provider()
    service = TestDialogueService(provider)

    session = service.start(pin, semantic)

    assert session.pin == pin
    assert session.pin.revision_id == "r1"
    assert session.pin.snapshot_hash == pin.snapshot_hash
    assert session.display_name == "Марина"
    assert session.messages == ()


def test_start_rejects_snapshot_mismatch():
    semantic = make_semantic()
    pin = make_pin(semantic)
    wrong = TestDialoguePin(
        character_id=pin.character_id,
        version_id=pin.version_id,
        revision_id=pin.revision_id,
        snapshot_hash="0" * 64,
    )
    service = TestDialogueService(capturing_provider()[0])
    with pytest.raises(TestDialogueError):
        service.start(wrong, semantic)


def test_start_rejects_malformed_semantic():
    pin = make_pin(make_semantic())
    service = TestDialogueService(capturing_provider()[0])
    with pytest.raises(TestDialogueError):
        service.start(pin, {"identity": {"display_name": "x"}})


def test_send_appends_user_then_character_in_order():
    provider, calls = capturing_provider("Привет.")
    service = TestDialogueService(provider)
    session = service.start(make_pin(make_semantic()), make_semantic())

    session = service.send(session.session_id, "Здравствуйте")

    assert len(session.messages) == 2
    assert session.messages[0].role == "user"
    assert session.messages[0].content == "Здравствуйте"
    assert session.messages[0].seq == 1
    assert session.messages[1].role == "character"
    assert session.messages[1].content == "Привет."
    assert session.messages[1].seq == 2


def test_send_supplies_persona_and_free_form_response():
    semantic = make_semantic()
    provider, calls = capturing_provider("Многострочный\nсвободный ответ.")
    service = TestDialogueService(provider)
    session = service.start(make_pin(semantic), semantic)

    service.send(session.session_id, "Расскажи о себе")

    assert calls[-1]["system"].startswith(
        "Ты — выбранный вымышленный персонаж"
    )
    assert "Выросла у моря, давно работает врачом." in calls[-1]["system"]
    assert calls[-1]["messages"][-1] == {"role": "user", "content": "Расскажи о себе"}


def test_send_empty_input_rejected():
    service = TestDialogueService(capturing_provider()[0])
    session = service.start(make_pin(make_semantic()), make_semantic())
    with pytest.raises(TestDialogueError):
        service.send(session.session_id, "   ")


def test_send_unknown_session_rejected():
    service = TestDialogueService(capturing_provider()[0])
    with pytest.raises(TestDialogueError):
        service.send("td-unknown", "hi")


def test_empty_provider_response_rejected():
    provider, _ = capturing_provider("")
    service = TestDialogueService(provider)
    session = service.start(make_pin(make_semantic()), make_semantic())
    with pytest.raises(TestDialogueProviderError):
        service.send(session.session_id, "hi")


def test_provider_exception_mapped_cleanly():
    def boom(messages, system):
        raise RuntimeError("connection failed")

    service = TestDialogueService(boom)
    session = service.start(make_pin(make_semantic()), make_semantic())
    with pytest.raises(TestDialogueProviderError):
        service.send(session.session_id, "hi")
    # Prior transcript is unchanged on provider failure.
    assert service.get_session(session.session_id).messages == ()


def test_reset_clears_transcript_keeps_pin():
    provider, _ = capturing_provider()
    service = TestDialogueService(provider)
    semantic = make_semantic()
    pin = make_pin(semantic)
    session = service.start(pin, semantic)
    service.send(session.session_id, "один")

    session = service.reset(session.session_id)

    assert session.messages == ()
    assert session.pin == pin
    assert session.display_name == "Марина"


def test_transcript_bounding_limits_history():
    provider, calls = capturing_provider()
    service = TestDialogueService(provider, transcript_turn_limit=1)
    session = service.start(make_pin(make_semantic()), make_semantic())

    service.send(session.session_id, "один")
    service.send(session.session_id, "два")
    service.send(session.session_id, "три")

    last = calls[-1]["messages"]
    # bounded history = previous turn (user "два", character reply) + current "три".
    assert [m["role"] for m in last] == ["user", "assistant", "user"]
    assert last[0]["content"] == "два"
    assert last[2]["content"] == "три"


def test_full_transcript_is_retained_in_memory_even_when_bounded():
    provider, _ = capturing_provider()
    service = TestDialogueService(provider, transcript_turn_limit=1)
    session = service.start(make_pin(make_semantic()), make_semantic())

    for text in ("один", "два", "три"):
        session = service.send(session.session_id, text)

    assert len(session.messages) == 6  # full in-memory transcript, not bounded


def test_provider_exception_sensitive_content_is_not_surfaced():
    def leak(messages, system):
        raise RuntimeError(
            "Authorization: Bearer fake-secret-123 api_key=fake-secret-456 "
            '{"private": "request-body-secret"}'
        )

    service = TestDialogueService(leak)
    session = service.start(make_pin(make_semantic()), make_semantic())
    with pytest.raises(TestDialogueProviderError) as exc:
        service.send(session.session_id, "hi")

    message = str(exc.value)
    assert message == GENERIC_PROVIDER_FAILURE_MESSAGE
    for fragment in (
        "Authorization",
        "Bearer",
        "fake-secret-123",
        "fake-secret-456",
        "request-body-secret",
    ):
        assert fragment not in message


def test_safe_missing_key_message_is_preserved():
    # Exact clean missing-key condition → canonical LOCAL constant (never the
    # original exception string), for both supported credential env vars.
    for env_name in ("DEEPSEEK_API_KEY", "OPENAI_API_KEY"):

        def missing_key(messages, system, _env=env_name):
            raise CharacterDraftError(
                f"API key is not configured. Set {_env} and retry."
            )

        service = TestDialogueService(missing_key)
        session = service.start(make_pin(make_semantic()), make_semantic())
        with pytest.raises(TestDialogueProviderError) as exc:
            service.send(session.session_id, "hi")

        assert str(exc.value) == SAFE_MISSING_KEY_MESSAGE


_ADVERSARIAL_MESSAGES = (
    "API key is not configured. Authorization: Bearer fake-secret-123",
    "API key is not configured. api_key=fake-secret-456",
    "API key is not configured. https://example.invalid/?token=fake-secret",
    'API key is not configured. HTTP 401 {"secret":"response-body-secret"}',
    'API key is not configured. {"private":"request-body-secret"}',
    "API key is not configured.EXTRA",
    (
        "API key is not configured. Set DEEPSEEK_API_KEY and retry. "
        "Authorization: Bearer fake-secret-123"
    ),
)

_SENSITIVE_FRAGMENTS = (
    "Authorization",
    "Bearer",
    "fake-secret-123",
    "fake-secret-456",
    "api_key=",
    "token=",
    "request-body-secret",
    "response-body-secret",
    "EXTRA",
    "HTTP 401",
    "https://",
)


@pytest.mark.parametrize("message", _ADVERSARIAL_MESSAGES)
def test_adversarial_provider_exceptions_collapse_to_generic(message):
    """Any prefix-spoofed / near-match provider message must not pass through."""

    def leak(messages, system, _message=message):
        raise CharacterDraftError(_message)

    service = TestDialogueService(leak)
    session = service.start(make_pin(make_semantic()), make_semantic())
    with pytest.raises(TestDialogueProviderError) as exc:
        service.send(session.session_id, "hi")

    result = str(exc.value)
    assert result == GENERIC_PROVIDER_FAILURE_MESSAGE
    for fragment in _SENSITIVE_FRAGMENTS:
        assert fragment not in result
