"""Offline facade tests for the Test Dialogue slice (application layer)."""

from __future__ import annotations

import pytest

from services.character_lab_application import (
    CharacterLabApplicationConfig,
    CharacterLabApplicationError,
    CharacterLabApplicationService,
)
from services.character_dialogue.service import GENERIC_PROVIDER_FAILURE_MESSAGE

from tests.character_dialogue._helpers import capturing_provider, make_semantic


def _service(tmp_path, response: str = "Ответ персонажа."):
    provider, calls = capturing_provider(response)
    service = CharacterLabApplicationService(
        CharacterLabApplicationConfig(character_authoring_root=tmp_path / "authoring"),
        dialogue_provider=provider,
    )
    return service, calls


def _create(service, *, revision_id="r1", semantic=None):
    return service.create_character(
        character_id="char_marina",
        version_id="v1",
        revision_id=revision_id,
        version_label="Марина v1",
        semantic=semantic or make_semantic(),
    )


def test_draft_revision_can_start_test_dialogue(tmp_path):
    service, _ = _service(tmp_path)
    _create(service, revision_id="r1")

    session = service.start_test_dialogue(
        character_id="char_marina", version_id="v1", revision_id="r1"
    )

    assert session.pin.revision_id == "r1"
    assert session.display_name == "Марина"


def test_session_pin_is_exact_immutable_coordinate(tmp_path):
    service, _ = _service(tmp_path)
    created = _create(service, revision_id="r1")

    session = service.start_test_dialogue(
        character_id="char_marina", version_id="v1", revision_id="r1"
    )

    assert session.pin.character_id == "char_marina"
    assert session.pin.version_id == "v1"
    assert session.pin.revision_id == "r1"
    assert session.pin.snapshot_hash == created.snapshot_hash


def test_later_revision_does_not_alter_existing_session(tmp_path):
    service, calls = _service(tmp_path)
    _create(service, revision_id="r1", semantic=make_semantic(biography="Выросла у моря."))

    session = service.start_test_dialogue(
        character_id="char_marina", version_id="v1", revision_id="r1"
    )
    service.save_character(
        character_id="char_marina",
        version_id="v1",
        revision_id="r2",
        semantic=make_semantic(biography="Жила в горах."),
    )

    updated = service.send_test_dialogue_message(session.session_id, "привет")

    assert updated.pin.revision_id == "r1"
    assert "Выросла у моря." in calls[-1]["system"]
    assert "Жила в горах." not in calls[-1]["system"]


def test_new_session_can_explicitly_select_new_revision(tmp_path):
    service, calls = _service(tmp_path)
    _create(service, revision_id="r1", semantic=make_semantic(biography="Выросла у моря."))
    service.save_character(
        character_id="char_marina",
        version_id="v1",
        revision_id="r2",
        semantic=make_semantic(biography="Жила в горах."),
    )

    session = service.start_test_dialogue(
        character_id="char_marina", version_id="v1", revision_id="r2"
    )
    service.send_test_dialogue_message(session.session_id, "привет")

    assert session.pin.revision_id == "r2"
    assert "Жила в горах." in calls[-1]["system"]


def test_no_new_revision_created_by_dialogue(tmp_path):
    service, _ = _service(tmp_path)
    _create(service, revision_id="r1")
    session = service.start_test_dialogue(
        character_id="char_marina", version_id="v1", revision_id="r1"
    )
    service.send_test_dialogue_message(session.session_id, "привет")

    revisions = service.list_authoring_revisions("char_marina", "v1")
    assert [r.revision_id for r in revisions] == ["r1"]


def test_no_approval_or_publication_by_dialogue(tmp_path):
    service, _ = _service(tmp_path)
    _create(service, revision_id="r1")
    session = service.start_test_dialogue(
        character_id="char_marina", version_id="v1", revision_id="r1"
    )
    service.send_test_dialogue_message(session.session_id, "привет")

    pointer = service.read_version_lifecycle("char_marina", "v1")
    assert pointer.lifecycle_state == "DRAFT"
    assert service.list_published_releases("char_marina") == ()
    assert service.read_canonical_current("char_marina") is None


def test_missing_revision_maps_to_not_found(tmp_path):
    service, _ = _service(tmp_path)
    _create(service, revision_id="r1")

    with pytest.raises(CharacterLabApplicationError) as exc:
        service.start_test_dialogue(
            character_id="char_marina", version_id="v1", revision_id="r9"
        )
    assert exc.value.code == "AUTHORING_NOT_FOUND"


def test_no_authoring_root_maps_to_unavailable(tmp_path):
    service = CharacterLabApplicationService(
        CharacterLabApplicationConfig(character_authoring_root=None),
        dialogue_provider=capturing_provider()[0],
    )
    with pytest.raises(CharacterLabApplicationError) as exc:
        service.start_test_dialogue(
            character_id="char_marina", version_id="v1", revision_id="r1"
        )
    assert exc.value.code == "AUTHORING_UNAVAILABLE"


def test_provider_failure_maps_to_provider_error(tmp_path):
    def boom(messages, system):
        raise RuntimeError("connection failed")

    service = CharacterLabApplicationService(
        CharacterLabApplicationConfig(character_authoring_root=tmp_path / "authoring"),
        dialogue_provider=boom,
    )
    _create(service, revision_id="r1")
    session = service.start_test_dialogue(
        character_id="char_marina", version_id="v1", revision_id="r1"
    )

    with pytest.raises(CharacterLabApplicationError) as exc:
        service.send_test_dialogue_message(session.session_id, "привет")
    assert exc.value.code == "TEST_DIALOGUE_PROVIDER_ERROR"


def test_empty_provider_response_maps_to_provider_error(tmp_path):
    service, _ = _service(tmp_path, response="   ")
    _create(service, revision_id="r1")
    session = service.start_test_dialogue(
        character_id="char_marina", version_id="v1", revision_id="r1"
    )

    with pytest.raises(CharacterLabApplicationError) as exc:
        service.send_test_dialogue_message(session.session_id, "привет")
    assert exc.value.code == "TEST_DIALOGUE_PROVIDER_ERROR"


def test_reset_clears_transcript_via_facade(tmp_path):
    service, _ = _service(tmp_path)
    _create(service, revision_id="r1")
    session = service.start_test_dialogue(
        character_id="char_marina", version_id="v1", revision_id="r1"
    )
    service.send_test_dialogue_message(session.session_id, "привет")

    reset = service.reset_test_dialogue(session.session_id)

    assert reset.messages == ()
    assert reset.pin.revision_id == "r1"


def test_provider_failure_sensitive_content_not_in_app_error(tmp_path):
    def leak(messages, system):
        raise RuntimeError(
            "API key is not configured. Authorization: Bearer fake-secret-123 "
            "api_key=fake-secret-456 "
            '{"private": "request-body-secret"} '
            "https://example.invalid/?token=fake-secret "
            '{"secret": "response-body-secret"}'
        )

    service = CharacterLabApplicationService(
        CharacterLabApplicationConfig(character_authoring_root=tmp_path / "authoring"),
        dialogue_provider=leak,
    )
    _create(service, revision_id="r1")
    session = service.start_test_dialogue(
        character_id="char_marina", version_id="v1", revision_id="r1"
    )

    with pytest.raises(CharacterLabApplicationError) as exc:
        service.send_test_dialogue_message(session.session_id, "привет")

    assert exc.value.code == "TEST_DIALOGUE_PROVIDER_ERROR"
    assert exc.value.message == GENERIC_PROVIDER_FAILURE_MESSAGE
    for fragment in (
        "Authorization",
        "Bearer",
        "fake-secret-123",
        "fake-secret-456",
        "api_key=",
        "token=",
        "request-body-secret",
        "response-body-secret",
        "https://",
    ):
        assert fragment not in exc.value.message
