"""Qt-native Character Lab shell tests (headless/offscreen)."""

from __future__ import annotations

from services.character_lab_application import CharacterLabApplicationConfig, CharacterLabApplicationService
from tests.character_canon_bridge.conftest import make_status
from ui.character_lab.main_window import CharacterLabMainWindow, _KIND_CHARACTER, _KIND_VERSION, _ID_ROLE, _KIND_ROLE


def _service_with_canon(tmp_path):
    canon_root = tmp_path / "character_canon"
    service = CharacterLabApplicationService(CharacterLabApplicationConfig(character_canon_root=canon_root))
    return service, canon_root


def test_application_shell_initializes_offline(qapp, offline_lab_service):
    window = CharacterLabMainWindow(offline_lab_service)
    window.show()
    assert window.character_model.rowCount() == 0
    assert window.character_empty_label.isVisible()
    assert not window.composer_edit.isEnabled()


def test_missing_canon_shows_graceful_empty_state_not_a_crash(qapp, offline_lab_service):
    window = CharacterLabMainWindow(offline_lab_service)
    window.show()
    window.reload_characters()
    assert window.character_empty_label.isVisible()
    assert window.character_view.isVisible() is False


def test_characters_are_listed_through_the_application_boundary(qapp, tmp_path):
    service, canon_root = _service_with_canon(tmp_path)
    make_status(canon_root, "KIRA", "APPROVED_AS_CANON")
    make_status(canon_root, "SERGEY", "DRAFT")
    window = CharacterLabMainWindow(service)
    assert window.character_model.rowCount() == 2
    ids = {
        window.character_model.item(row).data(_ID_ROLE)
        for row in range(window.character_model.rowCount())
    }
    assert ids == {"KIRA", "SERGEY"}


def test_selecting_a_character_updates_inspector_state(qapp, tmp_path):
    service, canon_root = _service_with_canon(tmp_path)
    make_status(canon_root, "KIRA", "APPROVED_AS_CANON")
    window = CharacterLabMainWindow(service)
    character_item = window.character_model.item(0)
    assert character_item.data(_KIND_ROLE) == _KIND_CHARACTER
    index = window.character_model.indexFromItem(character_item)
    window.character_view.setCurrentIndex(index)
    assert window.inspector_values["character_id"].text() == "KIRA"
    assert window.inspector_values["approved"].text() == "Да"


def test_versions_are_represented_generically(qapp, tmp_path):
    service, canon_root = _service_with_canon(tmp_path)
    make_status(canon_root, "KIRA", "APPROVED_AS_CANON")
    window = CharacterLabMainWindow(service)
    character_item = window.character_model.item(0)
    assert character_item.rowCount() == 1
    version_item = character_item.child(0)
    assert version_item.data(_KIND_ROLE) == _KIND_VERSION
    assert version_item.data(_ID_ROLE) == "KIRA"


def test_creating_a_new_local_session_binds_selected_character_and_version(qapp, tmp_path):
    service, canon_root = _service_with_canon(tmp_path)
    make_status(canon_root, "KIRA", "APPROVED_AS_CANON")
    window = CharacterLabMainWindow(service)
    character_item = window.character_model.item(0)
    window.character_view.setCurrentIndex(window.character_model.indexFromItem(character_item))

    window._on_new_session_clicked()

    assert window.session_model.rowCount() == 1
    assert window._current_session_id is not None
    assert window.composer_edit.isEnabled()
    session = service.get_session(window._current_session_id)
    assert session.character_id == "KIRA"


def test_changing_character_selection_does_not_mutate_an_existing_session(qapp, tmp_path):
    service, canon_root = _service_with_canon(tmp_path)
    make_status(canon_root, "KIRA", "APPROVED_AS_CANON")
    make_status(canon_root, "SERGEY", "DRAFT")
    window = CharacterLabMainWindow(service)

    kira_item = window.character_model.item(0)
    window.character_view.setCurrentIndex(window.character_model.indexFromItem(kira_item))
    window._on_new_session_clicked()
    bound_session_id = window._current_session_id
    original_binding = service.get_session(bound_session_id).character_id
    assert original_binding == "KIRA"

    sergey_item = window.character_model.item(1)
    window.character_view.setCurrentIndex(window.character_model.indexFromItem(sergey_item))

    # Changing the left-panel selection must never retroactively rebind the
    # already-created session.
    reloaded = service.get_session(bound_session_id)
    assert reloaded.character_id == "KIRA"
    assert window._current_session_id == bound_session_id


def test_sending_a_local_message_updates_transcript_offline(qapp, tmp_path):
    service, canon_root = _service_with_canon(tmp_path)
    make_status(canon_root, "KIRA", "APPROVED_AS_CANON")
    window = CharacterLabMainWindow(service)
    character_item = window.character_model.item(0)
    window.character_view.setCurrentIndex(window.character_model.indexFromItem(character_item))
    window._on_new_session_clicked()

    window.composer_edit.setText("Привет!")
    window._on_send_clicked()

    assert window.transcript_view.count() == 1
    assert "Привет!" in window.transcript_view.item(0).text()
    assert window.composer_edit.text() == ""


def test_kira_pilot_path_renders_in_the_shell(qapp, tmp_path):
    service, canon_root = _service_with_canon(tmp_path)
    make_status(canon_root, "KIRA", "APPROVED_AS_CANON")
    window = CharacterLabMainWindow(service)
    kira_item = window.character_model.item(0)
    assert kira_item.data(_ID_ROLE) == "KIRA"
    window.character_view.setCurrentIndex(window.character_model.indexFromItem(kira_item))
    assert window.inspector_values["character_id"].text() == "KIRA"
    assert window.inspector_empty_label.isVisible() is False


def test_application_logic_is_not_kira_specific(qapp, tmp_path):
    service, canon_root = _service_with_canon(tmp_path)
    make_status(canon_root, "SERGEY", "APPROVED_AS_CANON")
    window = CharacterLabMainWindow(service)
    assert window.character_model.rowCount() == 1
    item = window.character_model.item(0)
    assert item.data(_ID_ROLE) == "SERGEY"
    window.character_view.setCurrentIndex(window.character_model.indexFromItem(item))
    assert window.inspector_values["character_id"].text() == "SERGEY"
