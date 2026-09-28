"""Background task runner: thread affinity and sanitized failure marshalling."""

from __future__ import annotations

import threading
import time

from services.character_lab_application import CharacterLabApplicationError
from ui.character_lab.worker import BackgroundTask, INTERNAL_ERROR_MESSAGE


def _run_and_collect(qapp, task):
    state = {"succeeded": None, "failed": None, "finished": False}
    background = BackgroundTask(task)
    background.succeeded.connect(lambda r: state.__setitem__("succeeded", r))
    background.failed.connect(lambda c, m: state.__setitem__("failed", (c, m)))
    background.finished.connect(lambda: state.__setitem__("finished", True))
    background.start()

    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline and not state["finished"]:
        qapp.processEvents()
        time.sleep(0.005)
    qapp.processEvents()
    return state


def test_task_runs_outside_ui_thread(qapp):
    ui_thread = threading.current_thread()
    observed = {}

    def task():
        observed["is_ui_thread"] = threading.current_thread() is ui_thread
        return 1

    state = _run_and_collect(qapp, task)
    assert state["succeeded"] == 1
    assert observed["is_ui_thread"] is False


def test_success_result_delivered(qapp):
    state = _run_and_collect(qapp, lambda: "ok")
    assert state["succeeded"] == "ok"
    assert state["failed"] is None


def test_application_error_is_sanitized(qapp):
    def task():
        raise CharacterLabApplicationError("DRAFT_AI_ERROR", "safe message")

    state = _run_and_collect(qapp, task)
    assert state["failed"] == ("DRAFT_AI_ERROR", "safe message")


def test_unexpected_exception_is_sanitized(qapp):
    def task():
        raise RuntimeError("Authorization: Bearer fake-secret-123")

    state = _run_and_collect(qapp, task)
    code, message = state["failed"]
    assert code == "INTERNAL_ERROR"
    assert message == INTERNAL_ERROR_MESSAGE
    assert "fake-secret-123" not in message
    assert "Bearer" not in message
    assert "Authorization" not in message
