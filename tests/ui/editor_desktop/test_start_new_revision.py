"""Hermetic workflow proofs for M2-S1 Start New Revision."""

from __future__ import annotations

import json

from PySide6.QtCore import Qt

from services.editor_application import NOT_FOUND, EditorOperationResult
from ui.editor_desktop.main_window import EditorMainWindow

_USER_ROLE = int(Qt.ItemDataRole.UserRole)


def _select_scene(window: EditorMainWindow, scene_id: str) -> None:
    for row in range(window.scene_model.rowCount()):
        index = window.scene_model.index(row, 0)
        if index.data(_USER_ROLE) == scene_id:
            window.scene_view.setCurrentIndex(index)
            return
    raise AssertionError(f"scene {scene_id!r} not in model")


def _accepted_window(qapp, service) -> EditorMainWindow:
    result = service.accept_scene("sc_test_001", 1)
    assert result.ok
    window = EditorMainWindow(service)
    window.show()
    _select_scene(window, "sc_test_001")
    qapp.processEvents()
    return window


def test_accepted_scene_shows_start_new_revision(qapp, populated_service):
    window = _accepted_window(qapp, populated_service)
    try:
        assert window.workspace_values["lifecycle"].text() == "ACCEPTED"
        assert window.accepted_immutable_label.isVisible()
        assert window.start_revision_button.isVisible()
        assert window.start_revision_button.isEnabled()
        assert "accepted version unchanged" in window.start_revision_button.toolTip()
    finally:
        window.close()


def test_draft_scene_hides_start_new_revision(qapp, populated_service):
    window = EditorMainWindow(populated_service)
    window.show()
    try:
        _select_scene(window, "sc_test_001")
        qapp.processEvents()
        assert window.workspace_values["lifecycle"].text() == "DRAFT"
        assert window.start_revision_button.isHidden()
        assert not window.start_revision_button.isEnabled()
    finally:
        window.close()


def test_cancel_performs_no_mutation_and_keeps_accepted_workspace(
    qapp, populated_service, monkeypatch
):
    window = _accepted_window(qapp, populated_service)
    calls: list[tuple[str, int]] = []

    def forbidden(scene_id: str, version: int):
        calls.append((scene_id, version))
        raise AssertionError("fork_scene_version must not be called on cancel")

    monkeypatch.setattr(populated_service, "fork_scene_version", forbidden)
    monkeypatch.setattr(window, "_confirm_start_new_revision", lambda *_: False)
    try:
        window.start_revision_button.click()
        qapp.processEvents()
        assert calls == []
        assert window.workspace_values["version"].text() == "1"
        assert window.workspace_values["lifecycle"].text() == "ACCEPTED"
        assert window.accepted_immutable_label.isVisible()
        assert not window.draft_editor_container.isVisible()
    finally:
        window.close()


def test_confirm_forks_exact_loaded_version_and_reloads_editable_draft(
    qapp, populated_service, monkeypatch
):
    window = _accepted_window(qapp, populated_service)
    original_fork = populated_service.fork_scene_version
    calls: list[tuple[str, int]] = []

    def tracked_fork(scene_id: str, version: int):
        calls.append((scene_id, version))
        return original_fork(scene_id, version)

    monkeypatch.setattr(populated_service, "fork_scene_version", tracked_fork)
    monkeypatch.setattr(window, "_confirm_start_new_revision", lambda *_: True)
    try:
        window.start_revision_button.click()
        qapp.processEvents()

        assert calls == [("sc_test_001", 1)]
        latest = populated_service.get_scene_workspace("sc_test_001")
        assert latest.latest_version == 2
        assert latest.lifecycle == "DRAFT"
        assert window.scene_view.currentIndex().data(_USER_ROLE) == "sc_test_001"
        assert window.workspace_values["version"].text() == "2"
        assert window.workspace_values["lifecycle"].text() == "DRAFT"
        assert window.draft_editor_container.isVisible()
        assert window.scene_title_edit.isEnabled()
        assert window.scene_title_edit.text() == "Test scene"
        assert window.accepted_immutable_label.isHidden()
        assert window.start_revision_button.isHidden()
        assert not window.start_revision_button.isEnabled()
        assert "forked to version 2" in window.statusBar().currentMessage()
    finally:
        window.close()


def test_fork_preserves_source_accepted_version_bytes_and_authority(
    qapp, populated_service, tmp_path, monkeypatch
):
    window = _accepted_window(qapp, populated_service)
    source_path = tmp_path / "scene_drafts" / "sc_test_001" / "versions" / "1.json"
    before_bytes = source_path.read_bytes()
    before_record = json.loads(before_bytes)
    before_state = populated_service.get_acceptance_state("sc_test_001", 1)
    monkeypatch.setattr(window, "_confirm_start_new_revision", lambda *_: True)
    try:
        window.start_revision_button.click()
        qapp.processEvents()

        after_bytes = source_path.read_bytes()
        after_record = json.loads(after_bytes)
        after_state = populated_service.get_acceptance_state("sc_test_001", 1)
        assert after_bytes == before_bytes
        assert after_record["body"] == before_record["body"]
        assert after_record["content_hash"] == before_record["content_hash"]
        assert after_record["acceptance"] == before_record["acceptance"]
        assert after_state == before_state
        assert after_state.accepted
    finally:
        window.close()


def test_fork_failure_retains_visible_accepted_workspace(
    qapp, populated_service, monkeypatch
):
    window = _accepted_window(qapp, populated_service)
    calls: list[tuple[str, int]] = []

    def fail(scene_id: str, version: int):
        calls.append((scene_id, version))
        return EditorOperationResult(
            ok=False,
            code=NOT_FOUND,
            message="Source version is unavailable",
            scene_id=scene_id,
            version=version,
        )

    monkeypatch.setattr(populated_service, "fork_scene_version", fail)
    monkeypatch.setattr(window, "_confirm_start_new_revision", lambda *_: True)
    try:
        window.start_revision_button.click()
        qapp.processEvents()

        assert calls == [("sc_test_001", 1)]
        assert window.workspace_values["version"].text() == "1"
        assert window.workspace_values["lifecycle"].text() == "ACCEPTED"
        assert window.workspace_form_container.isVisible()
        assert window.accepted_immutable_label.isVisible()
        assert window.start_revision_button.isVisible()
        assert not window.draft_editor_container.isVisible()
        assert window.workspace_error.text() == (
            "NOT_FOUND: Source version is unavailable"
        )
        assert window.workspace_error.isVisible()
        assert "Traceback" not in window.workspace_error.text()
        latest = populated_service.get_scene_workspace("sc_test_001")
        assert latest.latest_version == 1
        assert latest.lifecycle == "ACCEPTED"
    finally:
        window.close()
