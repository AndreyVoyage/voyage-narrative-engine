"""Offscreen Qt tests for the Character Lab "Тестирование" tab."""

from __future__ import annotations

from services.character_lab_application import (
    CharacterLabApplicationConfig,
    CharacterLabApplicationService,
)
from ui.character_lab.main_window import (
    _AUTH_DATA_ROLE,
    _KIND_AUTH_REVISION,
    CharacterLabMainWindow,
)

from tests.character_dialogue._helpers import capturing_provider, make_semantic


def _make_service(tmp_path, provider):
    return CharacterLabApplicationService(
        CharacterLabApplicationConfig(
            character_authoring_root=tmp_path / "authoring",
            character_release_store_root=tmp_path / "releases",
        ),
        dialogue_provider=provider,
    )


def _create(service):
    return service.create_character(
        character_id="char_marina",
        version_id="v1",
        revision_id="r1",
        version_label="Марина v1",
        semantic=make_semantic(),
    )


def _select_revision(window):
    def find(item):
        for i in range(item.childCount()):
            child = item.child(i)
            data = child.data(0, _AUTH_DATA_ROLE)
            if isinstance(data, dict) and data.get("kind") == _KIND_AUTH_REVISION:
                return child
            found = find(child)
            if found is not None:
                return found
        return None

    for i in range(window.authoring_tree.topLevelItemCount()):
        found = find(window.authoring_tree.topLevelItem(i))
        if found is not None:
            return found
    return None


def test_testing_tab_exists_and_dialogue_tab_preserved(qapp, tmp_path):
    service = _make_service(tmp_path, capturing_provider()[0])
    window = CharacterLabMainWindow(service)

    tabs = [window.center_tabs.tabText(i) for i in range(window.center_tabs.count())]
    assert "Тестирование" in tabs
    assert "Диалог" in tabs


def test_no_selection_shows_clear_message_no_silent_fallback(qapp, tmp_path):
    service = _make_service(tmp_path, capturing_provider()[0])
    window = CharacterLabMainWindow(service)

    window.testing_new_session_button.click()

    assert window._testing_session_id is None
    assert "Авторинг" in window.testing_hint_label.text()


def test_selected_revision_opens_test_dialogue(qapp, tmp_path):
    service = _make_service(tmp_path, capturing_provider("Привет, я Марина.")[0])
    _create(service)
    window = CharacterLabMainWindow(service)
    assert _select_revision(window) is not None
    window.authoring_tree.setCurrentItem(_select_revision(window))

    window.testing_new_session_button.click()

    assert window._testing_session_id is not None
    header = window.testing_header_label.text()
    assert "Марина" in header
    assert "v1" in header
    assert "r1" in header
    assert "char_marina" not in header  # raw character_id not prominent


def test_send_shows_user_and_character_messages(qapp, tmp_path):
    service = _make_service(tmp_path, capturing_provider("Привет, я Марина.")[0])
    _create(service)
    window = CharacterLabMainWindow(service)
    window.authoring_tree.setCurrentItem(_select_revision(window))
    window.testing_new_session_button.click()

    window.testing_composer_edit.setText("Здравствуйте")
    window.testing_send_button.click()

    items = [window.testing_transcript_view.item(i).text() for i in range(window.testing_transcript_view.count())]
    assert len(items) == 2
    assert "Вы: Здравствуйте" in items[0]
    assert "Марина: Привет, я Марина." in items[1]


def test_reset_clears_transcript(qapp, tmp_path):
    service = _make_service(tmp_path, capturing_provider("Привет.")[0])
    _create(service)
    window = CharacterLabMainWindow(service)
    window.authoring_tree.setCurrentItem(_select_revision(window))
    window.testing_new_session_button.click()
    window.testing_composer_edit.setText("один")
    window.testing_send_button.click()

    window.testing_reset_button.click()

    assert window.testing_transcript_view.count() == 0


def test_provider_failure_shown_safely(qapp, tmp_path):
    def boom(messages, system):
        raise RuntimeError("connection failed")

    service = _make_service(tmp_path, boom)
    _create(service)
    window = CharacterLabMainWindow(service)
    window.authoring_tree.setCurrentItem(_select_revision(window))
    window.testing_new_session_button.click()

    window.testing_composer_edit.setText("привет")
    window.testing_send_button.click()

    assert "TEST_DIALOGUE_PROVIDER_ERROR" in window.statusBar().currentMessage()


def test_provider_failure_sensitive_content_not_in_ui(qapp, tmp_path):
    def leak(messages, system):
        raise RuntimeError(
            "API key is not configured. Authorization: Bearer fake-secret-123 "
            "api_key=fake-secret-456 "
            '{"private": "request-body-secret"} '
            "https://example.invalid/?token=fake-secret "
            '{"secret": "response-body-secret"}'
        )

    service = _make_service(tmp_path, leak)
    _create(service)
    window = CharacterLabMainWindow(service)
    window.authoring_tree.setCurrentItem(_select_revision(window))
    window.testing_new_session_button.click()

    window.testing_composer_edit.setText("привет")
    window.testing_send_button.click()

    message = window.statusBar().currentMessage()
    assert "TEST_DIALOGUE_PROVIDER_ERROR" in message
    assert "Не удалось получить ответ персонажа от AI-провайдера." in message
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
        assert fragment not in message
