"""Hermetic workflow proofs for the M1-S1 editable draft workspace."""

from __future__ import annotations

import copy

from PySide6.QtCore import Qt

from services.editor_application import ACCEPTED_IMMUTABLE, EditorOperationResult
from tests.editor_application.conftest import make_body
from ui.editor_desktop.draft_editing import DraftEditSession, UnsavedDecision
from ui.editor_desktop.main_window import EditorMainWindow

_USER_ROLE = int(Qt.ItemDataRole.UserRole)


def _sample_body() -> dict:
    return make_body()


def _select_scene(window, scene_id: str) -> None:
    for row in range(window.scene_model.rowCount()):
        index = window.scene_model.index(row, 0)
        if index.data(_USER_ROLE) == scene_id:
            window.scene_view.setCurrentIndex(index)
            return
    raise AssertionError(f"scene {scene_id!r} not in model")


def _current_scene_id(window) -> str:
    return window.scene_view.currentIndex().data(_USER_ROLE)


def _make_dirty(window) -> None:
    window.scene_title_edit.setText("Edited title")


# ---------------------------------------------------------------- session model


def test_session_dirty_tracks_edits_and_revert():
    session = DraftEditSession("sc_test_001", 1, "DRAFT", _sample_body())
    assert session.editable
    assert not session.is_dirty

    session.set_scene_field("scene_title", "New title")
    assert session.is_dirty
    session.set_scene_field("scene_title", "Test scene")
    assert not session.is_dirty

    session.set_entry_text("e1", "Edited text.")
    assert session.is_dirty
    assert session.entry_text("e1") == "Edited text."

    session.mark_saved()
    assert not session.is_dirty


def test_session_rejects_non_editable_targets():
    session = DraftEditSession("sc_test_001", 1, "DRAFT", _sample_body())
    for key in ("scene_id", "entries", "participants"):
        try:
            session.set_scene_field(key, "x")
        except KeyError:
            pass
        else:
            raise AssertionError(f"{key} must not be editable")
    for entry_id in ("c1", "missing"):
        try:
            session.set_entry_text(entry_id, "x")
        except KeyError:
            pass
        else:
            raise AssertionError(f"entry {entry_id} must not be text-editable")


def test_session_body_for_save_preserves_unsupported_entries():
    body = _sample_body()
    original_choice = copy.deepcopy(body["entries"][1])
    session = DraftEditSession("sc_test_001", 1, "DRAFT", body)
    session.set_entry_text("e1", "Edited text.")
    session.set_scene_field("location_id", "gym")

    saved = session.body_for_save()
    assert [entry["entry_id"] for entry in saved["entries"]] == ["e1", "c1"]
    assert saved["entries"][1] == original_choice
    assert saved["entries"][0]["text"] == "Edited text."
    assert saved["location_id"] == "gym"
    assert saved["scene_id"] == "sc_test_001"


# ------------------------------------------------------- A: edit/save/reload


def test_draft_edit_save_reload_round_trip(qapp, populated_service):
    window = EditorMainWindow(populated_service)
    try:
        _select_scene(window, "sc_test_001")
        qapp.processEvents()
        assert window.dirty_label.text() == ""
        assert not window.save_draft_button.isEnabled()

        _make_dirty(window)
        window.entry_text_edits["e1"].setPlainText("Kira warms up slowly.")
        qapp.processEvents()
        assert window.dirty_label.text() == "Unsaved changes"
        assert window.save_draft_button.isEnabled()

        window.save_draft_button.click()
        qapp.processEvents()
        assert window.dirty_label.text() == ""
        assert not window.save_draft_button.isEnabled()
        assert "saved" in window.statusBar().currentMessage()

        persisted = populated_service.get_scene_workspace("sc_test_001")
        assert persisted.body["scene_title"] == "Edited title"
        assert persisted.body["entries"][0]["text"] == "Kira warms up slowly."
    finally:
        window.close()

    reloaded = EditorMainWindow(populated_service)
    try:
        _select_scene(reloaded, "sc_test_001")
        qapp.processEvents()
        assert reloaded.workspace_values["title"].text() == "Edited title"
        assert reloaded.scene_title_edit.text() == "Edited title"
        assert reloaded.entry_text_edits["e1"].toPlainText() == "Kira warms up slowly."
    finally:
        reloaded.close()


# ------------------------------------------------------------- B: save failure


def test_failed_save_keeps_dirty_buffer(qapp, populated_service, monkeypatch):
    window = EditorMainWindow(populated_service)
    try:
        _select_scene(window, "sc_test_001")
        qapp.processEvents()
        _make_dirty(window)
        qapp.processEvents()

        def fail(_scene_id, _version, _body):
            return EditorOperationResult(
                ok=False, code=ACCEPTED_IMMUTABLE, message="Version is immutable"
            )

        monkeypatch.setattr(populated_service, "save_draft", fail)
        window.save_draft_button.click()
        qapp.processEvents()

        assert window.dirty_label.text() == "Unsaved changes"
        assert window.save_draft_button.isEnabled()
        assert window.scene_title_edit.text() == "Edited title"
        assert window.workspace_error.text() == "ACCEPTED_IMMUTABLE: Version is immutable"
        assert not window.workspace_error.isHidden()
        assert "saved" not in window.statusBar().currentMessage()
        assert "Traceback" not in window.workspace_error.text()
        persisted = populated_service.get_scene_workspace("sc_test_001")
        assert persisted.body["scene_title"] == "Test scene"
    finally:
        monkeypatch.setattr(
            window, "_ask_unsaved_changes", lambda: UnsavedDecision.DISCARD
        )
        window.close()


# -------------------------------------------------------- C: accepted read-only


def test_accepted_scene_is_read_only(qapp, populated_service):
    result = populated_service.accept_scene("sc_test_001", 1)
    assert result.ok
    window = EditorMainWindow(populated_service)
    window.show()
    try:
        _select_scene(window, "sc_test_001")
        qapp.processEvents()
        assert not window.draft_editor_container.isVisible()
        assert window.accepted_immutable_label.isVisible()
        assert "immutable" in window.accepted_immutable_label.text()
        assert not window.save_draft_button.isEnabled()
        assert window.workspace_values["lifecycle"].text() == "ACCEPTED"
        assert "read-only" in window.statusBar().currentMessage()
    finally:
        window.close()
        qapp.processEvents()


# --------------------------------------------------- D: mixed-body preservation


def test_text_edit_preserves_unsupported_entries(qapp, populated_service):
    before = populated_service.get_scene_workspace("sc_test_001")
    original_entries = copy.deepcopy(before.body["entries"])

    window = EditorMainWindow(populated_service)
    try:
        _select_scene(window, "sc_test_001")
        qapp.processEvents()
        window.entry_text_edits["e1"].setPlainText("Only the text changed.")
        qapp.processEvents()
        window.save_draft_button.click()
        qapp.processEvents()
        assert window.dirty_label.text() == ""
    finally:
        window.close()

    after = populated_service.get_scene_workspace("sc_test_001")
    after_entries = after.body["entries"]
    assert [entry["entry_id"] for entry in after_entries] == [
        entry["entry_id"] for entry in original_entries
    ]
    assert after_entries[1] == original_entries[1]
    changed = copy.deepcopy(original_entries[0])
    changed["text"] = "Only the text changed."
    assert after_entries[0] == changed


# ------------------------------------------- E: navigation with dirty buffer


def _two_scene_window(qapp, populated_service):
    result = populated_service.create_scene("sc_test_002", make_body(scene_id="sc_test_002"))
    assert result.ok
    window = EditorMainWindow(populated_service)
    _select_scene(window, "sc_test_001")
    qapp.processEvents()
    _make_dirty(window)
    qapp.processEvents()
    return window


def test_navigation_save_decision_saves_and_continues(qapp, populated_service, monkeypatch):
    window = _two_scene_window(qapp, populated_service)
    try:
        monkeypatch.setattr(
            window, "_ask_unsaved_changes", lambda: UnsavedDecision.SAVE
        )
        _select_scene(window, "sc_test_002")
        qapp.processEvents()
        assert _current_scene_id(window) == "sc_test_002"
        persisted = populated_service.get_scene_workspace("sc_test_001")
        assert persisted.body["scene_title"] == "Edited title"
    finally:
        window.close()


def test_navigation_failed_save_aborts_navigation(qapp, populated_service, monkeypatch):
    window = _two_scene_window(qapp, populated_service)
    try:
        monkeypatch.setattr(
            window, "_ask_unsaved_changes", lambda: UnsavedDecision.SAVE
        )

        def fail(_scene_id, _version, _body):
            return EditorOperationResult(
                ok=False, code=ACCEPTED_IMMUTABLE, message="Version is immutable"
            )

        monkeypatch.setattr(populated_service, "save_draft", fail)
        _select_scene(window, "sc_test_002")
        qapp.processEvents()
        assert _current_scene_id(window) == "sc_test_001"
        assert window.dirty_label.text() == "Unsaved changes"
        assert window.scene_title_edit.text() == "Edited title"
    finally:
        monkeypatch.setattr(
            window, "_ask_unsaved_changes", lambda: UnsavedDecision.DISCARD
        )
        window.close()


def test_navigation_discard_decision_drops_buffer(qapp, populated_service, monkeypatch):
    window = _two_scene_window(qapp, populated_service)
    try:
        monkeypatch.setattr(
            window, "_ask_unsaved_changes", lambda: UnsavedDecision.DISCARD
        )
        _select_scene(window, "sc_test_002")
        qapp.processEvents()
        assert _current_scene_id(window) == "sc_test_002"
        persisted = populated_service.get_scene_workspace("sc_test_001")
        assert persisted.body["scene_title"] == "Test scene"
    finally:
        window.close()


def test_navigation_cancel_decision_stays_with_dirty_buffer(
    qapp, populated_service, monkeypatch
):
    window = _two_scene_window(qapp, populated_service)
    try:
        monkeypatch.setattr(
            window, "_ask_unsaved_changes", lambda: UnsavedDecision.CANCEL
        )

        def forbidden(_scene_id, _version, _body):
            raise AssertionError("save_draft must not be called on CANCEL")

        monkeypatch.setattr(populated_service, "save_draft", forbidden)
        _select_scene(window, "sc_test_002")
        qapp.processEvents()
        assert _current_scene_id(window) == "sc_test_001"
        assert window.dirty_label.text() == "Unsaved changes"
        assert window.scene_title_edit.text() == "Edited title"
    finally:
        monkeypatch.setattr(
            window, "_ask_unsaved_changes", lambda: UnsavedDecision.DISCARD
        )
        window.close()


# -------------------------------------------------- F: close with dirty buffer


def _shown_dirty_window(qapp, populated_service):
    window = EditorMainWindow(populated_service)
    window.show()
    _select_scene(window, "sc_test_001")
    qapp.processEvents()
    _make_dirty(window)
    qapp.processEvents()
    return window


def test_close_cancel_keeps_window_open(qapp, populated_service, monkeypatch):
    window = _shown_dirty_window(qapp, populated_service)
    monkeypatch.setattr(window, "_ask_unsaved_changes", lambda: UnsavedDecision.CANCEL)
    try:
        closed = window.close()
        qapp.processEvents()
        assert not closed
        assert window.isVisible()
        assert window.dirty_label.text() == "Unsaved changes"
    finally:
        monkeypatch.setattr(
            window, "_ask_unsaved_changes", lambda: UnsavedDecision.DISCARD
        )
        window.close()
        qapp.processEvents()


def test_close_discard_closes_without_saving(qapp, populated_service, monkeypatch):
    window = _shown_dirty_window(qapp, populated_service)
    monkeypatch.setattr(window, "_ask_unsaved_changes", lambda: UnsavedDecision.DISCARD)
    closed = window.close()
    qapp.processEvents()
    assert closed
    assert not window.isVisible()
    persisted = populated_service.get_scene_workspace("sc_test_001")
    assert persisted.body["scene_title"] == "Test scene"


def test_close_save_success_closes_and_persists(qapp, populated_service, monkeypatch):
    window = _shown_dirty_window(qapp, populated_service)
    monkeypatch.setattr(window, "_ask_unsaved_changes", lambda: UnsavedDecision.SAVE)
    closed = window.close()
    qapp.processEvents()
    assert closed
    assert not window.isVisible()
    persisted = populated_service.get_scene_workspace("sc_test_001")
    assert persisted.body["scene_title"] == "Edited title"


def test_close_failed_save_keeps_window_open(qapp, populated_service, monkeypatch):
    window = _shown_dirty_window(qapp, populated_service)
    monkeypatch.setattr(window, "_ask_unsaved_changes", lambda: UnsavedDecision.SAVE)

    def fail(_scene_id, _version, _body):
        return EditorOperationResult(
            ok=False, code=ACCEPTED_IMMUTABLE, message="Version is immutable"
        )

    monkeypatch.setattr(populated_service, "save_draft", fail)
    try:
        closed = window.close()
        qapp.processEvents()
        assert not closed
        assert window.isVisible()
        assert window.dirty_label.text() == "Unsaved changes"
        assert window.scene_title_edit.text() == "Edited title"
    finally:
        monkeypatch.setattr(
            window, "_ask_unsaved_changes", lambda: UnsavedDecision.DISCARD
        )
        window.close()
        qapp.processEvents()
