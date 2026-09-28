"""Safe window close with an in-flight provider task (no QThread destroyed)."""

from __future__ import annotations

import threading

from services.character_lab_application import (
    CharacterLabApplicationConfig,
    CharacterLabApplicationService,
)
from tests.character_draft._helpers import analysis_json
from ui.character_lab.main_window import CharacterLabMainWindow


def _window(tmp_path, provider):
    config = CharacterLabApplicationConfig(
        character_authoring_root=tmp_path / "authoring"
    )
    service = CharacterLabApplicationService(config, draft_provider=provider)
    return CharacterLabMainWindow(service)


def test_close_defers_until_worker_finishes(qapp, tmp_path, wait_until):
    release = threading.Event()
    started = threading.Event()
    thread_finished = []

    def blocking_provider(messages, system):
        started.set()
        release.wait(timeout=5)
        return analysis_json()

    window = _window(tmp_path, blocking_provider)
    window.ai_name_edit.setText("Катя")
    window.ai_description_edit.setPlainText("shy")
    window.show()
    qapp.processEvents()

    window._on_analyze_clicked()
    assert started.wait(timeout=5)

    task = window._active_task
    assert task is not None
    thread = task._thread
    assert thread.isRunning()

    # Observe the worker's queued 'finished' signal so we can prove the thread
    # finished naturally (never destroyed while running).
    task.finished.connect(lambda: thread_finished.append(True))

    window.close()

    # Close is deferred while the worker is active: window stays visible and the
    # task/thread remain owned and running (no destroyed-while-running path).
    assert window._close_pending
    assert window.isVisible()
    assert window._active_task is task
    assert thread.isRunning()

    # Release the provider; the worker finishes naturally, then the window closes.
    release.set()
    assert wait_until(lambda: bool(thread_finished), timeout_ms=5000)
    assert wait_until(lambda: not window.isVisible(), timeout_ms=5000)
    assert window._active_task is None


def test_close_after_result_before_thread_finished(qapp, tmp_path, wait_until):
    """Close in the gap: result delivered but QThread.finished not yet emitted.

    This is the exact Codex reproduction: ``_active_task`` must remain a strong
    reference until ``BackgroundTask.finished`` (after QThread.finished), not at
    result delivery.
    """
    delivered_and_closed = threading.Event()
    thread_finished = []

    window = _window(tmp_path, lambda messages, system: analysis_json())
    window.ai_name_edit.setText("Катя")
    window.ai_description_edit.setPlainText("shy")
    window.show()
    qapp.processEvents()

    window._on_analyze_clicked()
    task = window._active_task
    assert task is not None

    def on_succeeded(_result):
        # succeeded runs before finished: ownership must still be held here.
        assert window._active_task is task
        assert window._close_pending is False
        window.close()
        # Close deferred; ownership retained until BackgroundTask.finished.
        assert window._close_pending is True
        assert window._active_task is task
        delivered_and_closed.set()

    task.succeeded.connect(on_succeeded)
    task.finished.connect(lambda: thread_finished.append(True))

    assert wait_until(lambda: delivered_and_closed.is_set(), timeout_ms=5000)

    # Only now does the QThread finish; ownership releases, then close proceeds.
    assert wait_until(lambda: bool(thread_finished), timeout_ms=5000)
    assert window._active_task is None
    assert wait_until(lambda: not window.isVisible(), timeout_ms=5000)


def test_close_pending_rejects_new_task(qapp, tmp_path, wait_until):
    """A new provider operation must not start while close is pending."""
    release = threading.Event()
    started = threading.Event()

    def blocking_provider(messages, system):
        started.set()
        release.wait(timeout=5)
        return analysis_json()

    window = _window(tmp_path, blocking_provider)
    window.ai_name_edit.setText("Катя")
    window.ai_description_edit.setPlainText("shy")
    window.show()
    qapp.processEvents()

    window._on_analyze_clicked()
    assert started.wait(timeout=5)
    task = window._active_task
    assert task is not None

    window.close()
    assert window._close_pending is True

    accepted = window._run_background(
        lambda: None,
        busy_message="busy",
        set_busy=lambda: None,
        clear_busy=lambda: None,
        on_success=lambda r: None,
        on_failure=lambda c, m: None,
    )
    assert accepted is False
    assert window._active_task is task

    release.set()
    assert wait_until(lambda: not window.isVisible(), timeout_ms=5000)
    assert window._active_task is None


def test_run_background_rejects_while_close_pending_only(qapp, tmp_path):
    """Isolate the ``_close_pending`` guard (no active task, closing already set)."""
    window = _window(tmp_path, lambda messages, system: analysis_json())
    window._close_pending = True

    accepted = window._run_background(
        lambda: None,
        busy_message="busy",
        set_busy=lambda: None,
        clear_busy=lambda: None,
        on_success=lambda r: None,
        on_failure=lambda c, m: None,
    )
    assert accepted is False
    assert window._active_task is None
