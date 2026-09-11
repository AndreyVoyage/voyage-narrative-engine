"""Hermetic headless proof of the read-only desktop shell."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLineEdit, QPushButton, QTextEdit

from services.editor_application import NOT_FOUND, EditorApplicationError
from ui.editor_desktop.main_window import EditorMainWindow


def test_window_populates_facade_collections_and_selects_scene(qapp, populated_service):
    window = EditorMainWindow(populated_service)
    try:
        assert window.windowTitle() == "NARRATIVE Scenario Editor"
        assert window.scene_model.rowCount() == 1
        assert window.character_model.rowCount() == 2
        assert window.location_model.rowCount() == 2
        assert window.character_empty_label.isHidden()
        assert window.location_empty_label.isHidden()

        index = window.scene_model.index(0, 0)
        assert index.data(int(Qt.ItemDataRole.UserRole)) == "sc_test_001"
        window.scene_view.setCurrentIndex(index)
        qapp.processEvents()

        assert window.workspace_values["scene_id"].text() == "sc_test_001"
        assert window.workspace_values["title"].text() == "Test scene"
        assert window.workspace_values["version"].text() == "1"
        assert window.workspace_values["lifecycle"].text() == "DRAFT"
        assert window.workspace_values["acceptance"].text() == "Not accepted"
        assert window.workspace_values["entries"].text() == "2"
        assert window.workspace_values["manifest"].text() == "Included"
        assert "Opened sc_test_001 read-only" == window.statusBar().currentMessage()
    finally:
        window.close()
        qapp.processEvents()
    assert not window.isVisible()


def test_unconfigured_characters_show_neutral_empty_state(qapp, tmp_path):
    from dataclasses import replace

    from services.editor_application import EditorApplicationService
    from tests.editor_application.conftest import build_config

    config = replace(build_config(tmp_path, with_characters=False), character_canon_root=None)
    window = EditorMainWindow(EditorApplicationService(config))
    try:
        assert window.character_model.rowCount() == 0
        assert not window.character_empty_label.isHidden()
        assert "not configured" in window.character_empty_label.text()
    finally:
        window.close()


def test_application_error_code_and_message_are_surfaced_without_traceback(
    qapp, populated_service, monkeypatch
):
    window = EditorMainWindow(populated_service)
    try:
        def fail(_scene_id):
            raise EditorApplicationError(NOT_FOUND, "Scene is unavailable")

        monkeypatch.setattr(populated_service, "get_scene_workspace", fail)
        index = window.scene_model.index(0, 0)
        window._on_scene_selected(index, index)
        qapp.processEvents()

        expected = "NOT_FOUND: Scene is unavailable"
        assert window.statusBar().currentMessage() == expected
        assert window.workspace_error.text() == expected
        assert not window.workspace_error.isHidden()
        assert "Traceback" not in window.workspace_error.text()
    finally:
        window.close()


def test_collection_failure_remains_visible(qapp, populated_service, monkeypatch):
    def fail():
        raise EditorApplicationError(NOT_FOUND, "Manifest unavailable")

    monkeypatch.setattr(populated_service, "list_scenes", fail)
    window = EditorMainWindow(populated_service)
    try:
        assert window.scene_model.rowCount() == 0
        assert window.statusBar().currentMessage() == "NOT_FOUND: Manifest unavailable"
        assert window.workspace_error.text() == "NOT_FOUND: Manifest unavailable"
    finally:
        window.close()


def test_shell_has_no_mutation_controls_or_editors(qapp, populated_service):
    window = EditorMainWindow(populated_service)
    try:
        assert window.findChildren(QPushButton) == []
        assert window.findChildren(QLineEdit) == []
        assert window.findChildren(QTextEdit) == []
        assert window.scene_view.editTriggers().value == 0
    finally:
        window.close()
