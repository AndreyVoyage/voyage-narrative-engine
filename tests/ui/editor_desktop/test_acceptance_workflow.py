"""Hermetic workflow proofs for M4-S1 UI-driven scene acceptance.

All scenarios use a real, hermetic ``EditorApplicationService`` over a
temporary project (via ``populated_service`` / ``build_config``). No test in
this module ever targets the real repository project; real-project safety is
covered separately by ``test_real_project_read_only.py``.
"""

from __future__ import annotations

from PySide6.QtCore import Qt

from services.editor_application import (
    ACCEPTED_IMMUTABLE,
    PARTIAL_PROJECT_STATE,
    EditorApplicationError,
    EditorOperationResult,
)
from services.workspace_project import WorkspaceProjectError
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


def _validated_pass_window(qapp, service, scene_id: str = "sc_test_001") -> EditorMainWindow:
    window = _draft_window(qapp, service, scene_id)
    assert window.validate_scene_button.click() or True  # real signal path
    qapp.processEvents()
    assert window._validation_state is not None
    assert window.accept_scene_button.isEnabled()
    return window


# ---------------------------------------------------------------------------
# 1. ACCEPTANCE ELIGIBILITY
# ---------------------------------------------------------------------------


def test_clean_unvalidated_draft_cannot_accept(qapp, populated_service):
    window = _draft_window(qapp, populated_service)
    try:
        assert not window.accept_scene_button.isEnabled()
    finally:
        window.close()


def test_validation_failure_cannot_accept(qapp, populated_service):
    incomplete = make_body(scene_id="sc_bad_001")
    incomplete["entries"][0]["text"] = ""  # blank NARRATIVE text -> fails acceptance-completeness
    assert populated_service.create_scene("sc_bad_001", incomplete).ok
    window = _draft_window(qapp, populated_service, "sc_bad_001")
    try:
        window.validate_scene_button.click()
        qapp.processEvents()
        assert "failed" in window.validation_status_label.text().lower()
        assert not window.accept_scene_button.isEnabled()
    finally:
        window.close()


def test_validation_pass_makes_accept_available(qapp, populated_service):
    window = _validated_pass_window(qapp, populated_service)
    try:
        assert window.accept_scene_button.isEnabled()
    finally:
        window.close()


def test_edit_after_pass_immediately_disables_accept(qapp, populated_service, monkeypatch):
    window = _validated_pass_window(qapp, populated_service)
    try:
        window.scene_title_edit.setText("Edited after pass")
        qapp.processEvents()
        assert not window.accept_scene_button.isEnabled()
    finally:
        monkeypatch.setattr(
            window, "_ask_unsaved_changes", lambda: UnsavedDecision.DISCARD
        )
        window.close()


def test_save_after_edit_without_revalidation_keeps_accept_disabled(qapp, populated_service):
    window = _validated_pass_window(qapp, populated_service)
    try:
        window.scene_title_edit.setText("Edited then saved")
        qapp.processEvents()
        window.save_draft_button.click()
        qapp.processEvents()
        assert window.dirty_label.text() == ""
        assert not window.accept_scene_button.isEnabled()
        assert "not been validated" in window.validation_status_label.text()
    finally:
        window.close()


# ---------------------------------------------------------------------------
# 2. CANCEL
# ---------------------------------------------------------------------------


def test_accept_confirmation_cancel_performs_zero_mutation(qapp, populated_service, monkeypatch):
    window = _validated_pass_window(qapp, populated_service)
    calls: list[tuple] = []
    real_accept = populated_service.accept_scene

    def counting_accept(*args):
        calls.append(args)
        return real_accept(*args)

    monkeypatch.setattr(populated_service, "accept_scene", counting_accept)
    monkeypatch.setattr(window, "_confirm_accept_scene", lambda *_: False)
    try:
        window.accept_scene_button.click()
        qapp.processEvents()
        assert calls == []
        assert window.workspace_values["lifecycle"].text() == "DRAFT"
        assert window.draft_editor_container.isVisible()
        assert not window.accepted_immutable_label.isVisible()

        persisted = populated_service.get_scene_workspace("sc_test_001")
        assert persisted.lifecycle == "DRAFT"
        assert persisted.acceptance is None
    finally:
        window.close()


# ---------------------------------------------------------------------------
# 3. SUCCESSFUL AUTHORITY TRANSITION  +  4. POST-ACCEPT UI
# ---------------------------------------------------------------------------


def test_successful_accept_transitions_authority_and_ui(qapp, populated_service, monkeypatch):
    before = populated_service.get_scene_workspace("sc_test_001")
    assert before.lifecycle == "DRAFT"
    before_body = before.body

    window = _validated_pass_window(qapp, populated_service)
    monkeypatch.setattr(window, "_confirm_accept_scene", lambda *_: True)
    try:
        window.accept_scene_button.click()
        qapp.processEvents()

        # --- UI (POST-ACCEPT) ---
        assert window.workspace_values["lifecycle"].text() == "ACCEPTED"
        assert not window.draft_editor_container.isVisible()
        assert window.accepted_immutable_label.isVisible()
        assert not window.save_draft_button.isEnabled()
        assert not window.accept_scene_button.isEnabled()
        assert window.validation_status_label.text() == ""  # stale validation cleared
        assert window.start_revision_button.isVisible()
        assert window.start_revision_button.isEnabled()
        assert "accepted" in window.statusBar().currentMessage().lower()

        # --- ACTUAL AUTHORITY (real hermetic service) ---
        after = populated_service.get_scene_workspace("sc_test_001")
        assert after.lifecycle == "ACCEPTED"
        assert after.latest_version == before.latest_version  # same SceneVersion, no new version
        assert after.body == before_body  # body unchanged by acceptance
        assert after.acceptance is not None
        assert after.acceptance["ass_id"] == "ass_sc_test_001_v1"
        assert isinstance(after.acceptance["ass_content_hash"], str)
        assert len(after.acceptance["ass_content_hash"]) == 64

        acceptance_state = populated_service.get_acceptance_state("sc_test_001", 1)
        assert acceptance_state.accepted is True
        assert acceptance_state.manifest_included is True
        assert acceptance_state.batch_included is True
        assert acceptance_state.batch_resolvable is True
    finally:
        window.close()


# ---------------------------------------------------------------------------
# 5. HISTORICAL VERSION PRESERVATION
# ---------------------------------------------------------------------------


def test_accepting_forked_revision_preserves_historical_accepted_version(
    qapp, populated_service, monkeypatch
):
    assert populated_service.accept_scene("sc_test_001", 1).ok
    v1_before = populated_service.get_scene_workspace("sc_test_001")
    assert v1_before.lifecycle == "ACCEPTED"

    fork_result = populated_service.fork_scene_version("sc_test_001", 1)
    assert fork_result.ok
    assert fork_result.version == 2

    window = EditorMainWindow(populated_service)
    window.show()
    _select_scene(window, "sc_test_001")
    qapp.processEvents()
    monkeypatch.setattr(window, "_ask_unsaved_changes", lambda: UnsavedDecision.DISCARD)
    try:
        assert window.workspace_values["version"].text() == "2"
        assert window.workspace_values["lifecycle"].text() == "DRAFT"
        window.entry_text_edits["e1"].setPlainText("Revised in v2.")
        qapp.processEvents()
        window.save_draft_button.click()
        qapp.processEvents()
        window.validate_scene_button.click()
        qapp.processEvents()
        assert window.accept_scene_button.isEnabled()

        monkeypatch.setattr(window, "_confirm_accept_scene", lambda *_: True)
        window.accept_scene_button.click()
        qapp.processEvents()
        assert window.workspace_values["version"].text() == "2"
        assert window.workspace_values["lifecycle"].text() == "ACCEPTED"

        # v1 (historical accepted authority) is untouched.
        v1_after_json = populated_service._scene_store.read_version("sc_test_001", 1)
        assert v1_after_json.body_plain() == v1_before.body
        assert v1_after_json.acceptance.to_dict() == v1_before.acceptance
        v2 = populated_service.get_scene_workspace("sc_test_001")
        assert v2.latest_version == 2
        assert v2.body["entries"][0]["text"] == "Revised in v2."
    finally:
        window.close()


# ---------------------------------------------------------------------------
# 6. STALE VALIDATION
# ---------------------------------------------------------------------------


def test_stale_validation_after_edit_blocks_accept_until_revalidated(qapp, populated_service):
    window = _validated_pass_window(qapp, populated_service)
    try:
        window.scene_title_edit.setText("Stale after this edit")
        qapp.processEvents()
        assert not window.accept_scene_button.isEnabled()

        window.save_draft_button.click()
        qapp.processEvents()
        assert not window.accept_scene_button.isEnabled()

        window.validate_scene_button.click()
        qapp.processEvents()
        assert window.accept_scene_button.isEnabled()
    finally:
        window.close()


# ---------------------------------------------------------------------------
# 7. BOUNDED (ORDINARY) FAILURE
# ---------------------------------------------------------------------------


def test_ordinary_acceptance_failure_reports_cleanly_with_no_authority_mutation(
    qapp, populated_service, monkeypatch
):
    window = _validated_pass_window(qapp, populated_service)

    def fail(_scene_id, _version):
        return EditorOperationResult(
            ok=False, code=ACCEPTED_IMMUTABLE, message="Simulated ordinary failure",
        )

    monkeypatch.setattr(populated_service, "accept_scene", fail)
    monkeypatch.setattr(window, "_confirm_accept_scene", lambda *_: True)
    try:
        window.accept_scene_button.click()
        qapp.processEvents()

        expected = "ACCEPTED_IMMUTABLE: Simulated ordinary failure"
        assert window.workspace_error.text() == expected
        assert not window.workspace_error.isHidden()
        assert "Traceback" not in window.workspace_error.text()
        assert window.workspace_values["lifecycle"].text() == "DRAFT"
        assert window.draft_editor_container.isVisible()

        persisted = populated_service.get_scene_workspace("sc_test_001")
        assert persisted.lifecycle == "DRAFT"
        assert persisted.acceptance is None
    finally:
        window.close()


# ---------------------------------------------------------------------------
# 8. PARTIAL PROJECT STATE
# ---------------------------------------------------------------------------


def test_partial_project_state_surfaces_recovery_and_true_authority(
    qapp, populated_service, monkeypatch
):
    """accept_draft succeeds (SceneVersion -> ACCEPTED) but manifest inclusion
    fails afterward: accept_scene must report PARTIAL_PROJECT_STATE with
    recovery_required=True, and the UI must render the scene as ACCEPTED
    (the true state) rather than falsely implying nothing happened."""

    def broken_manifest_inclusion(_scene_id):
        raise WorkspaceProjectError("simulated manifest write failure")

    monkeypatch.setattr(
        populated_service, "_ensure_manifest_inclusion", broken_manifest_inclusion
    )

    window = _validated_pass_window(qapp, populated_service)
    monkeypatch.setattr(window, "_confirm_accept_scene", lambda *_: True)
    try:
        window.accept_scene_button.click()
        qapp.processEvents()

        assert "PARTIAL_PROJECT_STATE" in window.workspace_error.text()
        assert not window.workspace_error.isHidden()

        # The real, unmodified domain call already ran: the SceneVersion is
        # truly ACCEPTED even though the reported result is not ``ok``.
        # (get_scene_workspace never calls _ensure_manifest_inclusion, so the
        # still-active monkeypatch on that method does not affect this read.)
        real_state = populated_service.get_scene_workspace("sc_test_001")
        assert real_state.lifecycle == "ACCEPTED"
        assert real_state.acceptance is not None

        # The UI's own reload (taken while still patched) must have shown
        # this true ACCEPTED state, not a false "still DRAFT" state.
        assert window.workspace_values["lifecycle"].text() == "ACCEPTED"
        assert not window.draft_editor_container.isVisible()
        assert window.accepted_immutable_label.isVisible()
    finally:
        window.close()


def test_partial_project_state_never_auto_retries_or_repairs(qapp, populated_service, monkeypatch):
    """A single click performs exactly one accept_scene call, even when it
    reports PARTIAL_PROJECT_STATE; there is no automatic retry/repair."""

    calls: list[tuple] = []
    real_accept = populated_service.accept_scene

    def counting_accept(*args):
        calls.append(args)
        return real_accept(*args)

    def broken_manifest_inclusion(_scene_id):
        raise WorkspaceProjectError("simulated manifest write failure")

    monkeypatch.setattr(populated_service, "accept_scene", counting_accept)
    monkeypatch.setattr(
        populated_service, "_ensure_manifest_inclusion", broken_manifest_inclusion
    )
    window = _validated_pass_window(qapp, populated_service)
    monkeypatch.setattr(window, "_confirm_accept_scene", lambda *_: True)
    try:
        window.accept_scene_button.click()
        qapp.processEvents()
        assert len(calls) == 1  # exactly one call; no retry loop
        assert not window.accept_scene_button.isEnabled()  # no longer a DRAFT to accept again
    finally:
        window.close()


# ---------------------------------------------------------------------------
# 9. IDEMPOTENCY (application-service seam; no "Accept again" UI is added)
# ---------------------------------------------------------------------------


def test_accept_scene_is_idempotent_on_already_accepted_version(populated_service):
    first = populated_service.accept_scene("sc_test_001", 1)
    assert first.ok
    first_state = populated_service.get_scene_workspace("sc_test_001")

    second = populated_service.accept_scene("sc_test_001", 1)
    assert second.ok
    second_state = populated_service.get_scene_workspace("sc_test_001")

    assert second_state.lifecycle == "ACCEPTED"
    assert second_state.acceptance == first_state.acceptance
    assert second_state.body == first_state.body
    assert second_state.latest_version == first_state.latest_version


# ---------------------------------------------------------------------------
# 10. EXCEPTION-PATH AUTHORITATIVE RELOAD (F-M4-QA-02 correction)
# ---------------------------------------------------------------------------


def test_raw_exception_after_acceptance_reloads_authority(
    qapp, populated_service, monkeypatch
):
    """F-M4-QA-02: when ``accept_draft`` durably ACCEPTS the SceneVersion but a
    later project-inclusion step raises an unwrapped exception, ``accept_scene``
    propagates it and the UI must reload authority and render the true ACCEPTED
    state rather than a stale editable DRAFT."""

    calls: list[tuple] = []
    real_accept = populated_service.accept_scene

    def counting_accept(*args):
        calls.append(args)
        return real_accept(*args)

    def broken_manifest_inclusion(_scene_id):
        raise RuntimeError("simulated raw inclusion failure")

    monkeypatch.setattr(populated_service, "accept_scene", counting_accept)
    monkeypatch.setattr(
        populated_service, "_ensure_manifest_inclusion", broken_manifest_inclusion
    )
    window = _validated_pass_window(qapp, populated_service)
    monkeypatch.setattr(window, "_confirm_accept_scene", lambda *_: True)
    try:
        window.accept_scene_button.click()
        qapp.processEvents()

        # REAL AUTHORITY: durably ACCEPTED despite the raw exception escaping.
        real_state = populated_service.get_scene_workspace("sc_test_001")
        assert real_state.lifecycle == "ACCEPTED"
        assert real_state.acceptance is not None

        # UI reloaded to the true ACCEPTED state; no stale editable DRAFT.
        assert window.workspace_values["lifecycle"].text() == "ACCEPTED"
        assert not window.draft_editor_container.isVisible()
        assert window.accepted_immutable_label.isVisible()
        assert not window.save_draft_button.isEnabled()
        assert not window.accept_scene_button.isEnabled()

        # INTERNAL_ERROR remains surfaced.
        assert "INTERNAL_ERROR" in window.workspace_error.text()
        assert not window.workspace_error.isHidden()

        # Exactly one accept call; no retry/repair/second mutation.
        assert len(calls) == 1
    finally:
        window.close()


def test_editor_application_error_branch_reloads_before_error(
    qapp, populated_service, monkeypatch
):
    """After ``accept_scene`` raises ``EditorApplicationError``, the UI must
    attempt an authoritative reload before finalizing the bounded error."""

    window = _validated_pass_window(qapp, populated_service)
    monkeypatch.setattr(window, "_confirm_accept_scene", lambda *_: True)

    reloaded_scenes: list[str] = []
    real_load = window._load_scene_workspace

    def spying_load(scene_id, *, preserve_workspace_on_error=False):
        reloaded_scenes.append(scene_id)
        return real_load(scene_id, preserve_workspace_on_error=preserve_workspace_on_error)

    monkeypatch.setattr(window, "_load_scene_workspace", spying_load)

    def raise_eae(_scene_id, _version):
        raise EditorApplicationError("NOT_FOUND", "Simulated bounded acceptance error")

    monkeypatch.setattr(populated_service, "accept_scene", raise_eae)
    try:
        window.accept_scene_button.click()
        qapp.processEvents()

        assert reloaded_scenes == ["sc_test_001"]  # reload attempted before finalize
        assert "NOT_FOUND" in window.workspace_error.text()
        assert not window.workspace_error.isHidden()
    finally:
        window.close()
