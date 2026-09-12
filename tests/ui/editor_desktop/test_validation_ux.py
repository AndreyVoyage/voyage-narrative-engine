"""Hermetic workflow proofs for M3-S1 persisted scene validation UX."""

from __future__ import annotations

from PySide6.QtCore import Qt

from services.editor_application import (
    ACCEPTED_IMMUTABLE,
    NOT_FOUND,
    EditorOperationResult,
)
from tests.editor_application.conftest import make_body
from ui.editor_desktop.draft_editing import UnsavedDecision
from ui.editor_desktop.main_window import EditorMainWindow

_USER_ROLE = int(Qt.ItemDataRole.UserRole)


def _select_scene(window: EditorMainWindow, scene_id: str) -> None:
    for row in range(window.scene_model.rowCount()):
        index = window.scene_model.index(row, 0)
        if index.data(_USER_ROLE) == scene_id:
            window.scene_view.setCurrentIndex(index)
            return
    raise AssertionError(f"scene {scene_id!r} not in model")


def _draft_window(qapp, service, scene_id: str = "sc_test_001") -> EditorMainWindow:
    window = EditorMainWindow(service)
    window.show()
    _select_scene(window, scene_id)
    qapp.processEvents()
    return window


def test_clean_draft_can_validate_but_dirty_draft_cannot_call_service(
    qapp, populated_service, monkeypatch
):
    window = _draft_window(qapp, populated_service)
    calls: list[tuple[str, int]] = []

    def forbidden(scene_id: str, version: int):
        calls.append((scene_id, version))
        raise AssertionError("dirty draft must not be validated")

    try:
        assert window.validate_scene_button.isEnabled()
        assert window.validation_status_label.text() == (
            "Saved version has not been validated."
        )
        window.scene_title_edit.setText("Unsaved title")
        qapp.processEvents()
        monkeypatch.setattr(populated_service, "validate_scene", forbidden)

        assert not window.validate_scene_button.isEnabled()
        assert window.validation_status_label.text() == (
            "Save changes before validation."
        )
        window.validate_scene_button.click()
        qapp.processEvents()
        assert window._validate_current_scene() is False
        assert calls == []
    finally:
        window._ask_unsaved_changes = lambda: UnsavedDecision.DISCARD
        window.close()


def test_save_success_reenables_validation_without_reusing_old_result(
    qapp, populated_service
):
    window = _draft_window(qapp, populated_service)
    try:
        window.validate_scene_button.click()
        qapp.processEvents()
        assert window.validation_status_label.text() == "Validation passed"

        window.scene_title_edit.setText("Saved title")
        qapp.processEvents()
        assert not window.validate_scene_button.isEnabled()
        assert "passed" not in window.validation_status_label.text().lower()

        window.save_draft_button.click()
        qapp.processEvents()
        assert window.validate_scene_button.isEnabled()
        assert window.validation_status_label.text() == (
            "Saved version has not been validated."
        )
        assert window.validation_diagnostics_list.count() == 0
    finally:
        window.close()


def test_real_service_validation_pass_shows_current_pass_without_writing(
    qapp, populated_service, tmp_path
):
    window = _draft_window(qapp, populated_service)
    version_path = tmp_path / "scene_drafts" / "sc_test_001" / "versions" / "1.json"
    before = version_path.read_bytes()
    try:
        window.validate_scene_button.click()
        qapp.processEvents()

        assert window.validation_status_label.text() == "Validation passed"
        assert window.statusBar().currentMessage() == "Validation passed"
        assert window.validation_diagnostics_list.count() == 0
        assert window._validated_scene_version == ("sc_test_001", 1)
        assert version_path.read_bytes() == before
    finally:
        window.close()


def test_real_service_validation_failure_shows_structured_entry_diagnostic(
    qapp, populated_service, tmp_path
):
    window = _draft_window(qapp, populated_service)
    try:
        window.entry_text_edits["e1"].setPlainText("   ")
        qapp.processEvents()
        window.save_draft_button.click()
        qapp.processEvents()
        version_path = (
            tmp_path / "scene_drafts" / "sc_test_001" / "versions" / "1.json"
        )
        before_validation = version_path.read_bytes()
        window.validate_scene_button.click()
        qapp.processEvents()

        assert window.validation_status_label.text().startswith("Validation failed")
        assert window.validation_diagnostics_list.isVisible()
        assert window.validation_diagnostics_list.count() >= 1
        item = next(
            window.validation_diagnostics_list.item(row)
            for row in range(window.validation_diagnostics_list.count())
            if "Entry: e1" in window.validation_diagnostics_list.item(row).text()
        )
        assert "VALIDATION_FAILED" in item.text()
        assert "text entry 'e1'" in item.text()

        window.validation_diagnostics_list.itemActivated.emit(item)
        qapp.processEvents()
        assert window.entry_text_edits["e1"].hasFocus()
        assert version_path.read_bytes() == before_validation
    finally:
        window.close()


def test_failed_save_keeps_prior_validation_stale_and_validate_disabled(
    qapp, populated_service, monkeypatch
):
    window = _draft_window(qapp, populated_service)
    try:
        window.validate_scene_button.click()
        qapp.processEvents()
        assert window.validation_status_label.text() == "Validation passed"

        window.scene_title_edit.setText("Unsaved title")
        qapp.processEvents()

        def fail(_scene_id, _version, _body):
            return EditorOperationResult(
                ok=False,
                code=ACCEPTED_IMMUTABLE,
                message="Save refused",
            )

        monkeypatch.setattr(populated_service, "save_draft", fail)
        window.save_draft_button.click()
        qapp.processEvents()

        assert window.dirty_label.text() == "Unsaved changes"
        assert not window.validate_scene_button.isEnabled()
        assert window._validated_scene_version is None
        assert window.validation_status_label.text() == (
            "Save changes before validation."
        )
        assert "passed" not in window.validation_status_label.text().lower()
    finally:
        window._ask_unsaved_changes = lambda: UnsavedDecision.DISCARD
        window.close()


def test_edit_clears_current_validation_and_save_does_not_restore_pass(
    qapp, populated_service
):
    window = _draft_window(qapp, populated_service)
    try:
        window.validate_scene_button.click()
        qapp.processEvents()
        assert window._validated_scene_version == ("sc_test_001", 1)

        window.entry_text_edits["e1"].setPlainText("Changed after validation.")
        qapp.processEvents()
        assert window._validated_scene_version is None
        assert window.validation_diagnostics_list.count() == 0
        assert window.validation_status_label.text() == (
            "Save changes before validation."
        )

        window.save_draft_button.click()
        qapp.processEvents()
        assert window._validated_scene_version is None
        assert window.validation_status_label.text() == (
            "Saved version has not been validated."
        )
        assert "passed" not in window.validation_status_label.text().lower()
    finally:
        window.close()


def test_navigation_clears_validation_result_from_previous_scene(
    qapp, populated_service
):
    created = populated_service.create_scene(
        "sc_test_002", make_body(scene_id="sc_test_002")
    )
    assert created.ok
    window = _draft_window(qapp, populated_service)
    try:
        window.validate_scene_button.click()
        qapp.processEvents()
        assert window.validation_status_label.text() == "Validation passed"

        _select_scene(window, "sc_test_002")
        qapp.processEvents()
        assert window.workspace_values["scene_id"].text() == "sc_test_002"
        assert window._validated_scene_version is None
        assert window.validation_status_label.text() == (
            "Saved version has not been validated."
        )
        assert window.validation_diagnostics_list.count() == 0
    finally:
        window.close()


def test_facade_error_retains_workspace_without_false_pass_or_mutation(
    qapp, populated_service, monkeypatch
):
    window = _draft_window(qapp, populated_service)
    before = populated_service.get_scene_workspace("sc_test_001").body
    calls: list[tuple[str, int]] = []

    def fail(scene_id: str, version: int):
        calls.append((scene_id, version))
        return EditorOperationResult(
            ok=False,
            code=NOT_FOUND,
            message="Persisted version is unavailable",
            scene_id=scene_id,
            version=version,
        )

    monkeypatch.setattr(populated_service, "validate_scene", fail)
    try:
        window.validate_scene_button.click()
        qapp.processEvents()

        assert calls == [("sc_test_001", 1)]
        assert window.workspace_form_container.isVisible()
        assert window.draft_editor_container.isVisible()
        assert window.workspace_values["scene_id"].text() == "sc_test_001"
        assert window.validation_status_label.text() == (
            "Validation could not be completed."
        )
        assert "passed" not in window.validation_status_label.text().lower()
        assert window.workspace_error.text() == (
            "NOT_FOUND: Persisted version is unavailable"
        )
        assert "Traceback" not in window.workspace_error.text()
        assert populated_service.get_scene_workspace("sc_test_001").body == before
    finally:
        window.close()
