"""Minimal background execution for provider-backed Character Lab operations.

Runs one callable on a worker ``QThread`` and reports success/failure back on
the Qt UI thread via queued signals. No asyncio, no external task framework, no
new dependency. Widget references never cross into the worker thread; failures
are sanitized at this boundary so raw provider exception text never reaches the
UI.
"""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QObject, QThread, Signal

from services.character_lab_application import CharacterLabApplicationError

# Generic, secret-free fallback for unexpected (non-application) failures.
INTERNAL_ERROR_MESSAGE = "Внутренняя ошибка Character Lab."


class ProviderWorker(QObject):
    """Runs a single task on a worker thread and reports the outcome."""

    succeeded = Signal(object)
    failed = Signal(str, str)  # code, safe message
    finished = Signal()

    def __init__(self, task: Callable[[], Any], parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._task = task

    def run(self) -> None:
        try:
            result = self._task()
        except CharacterLabApplicationError as exc:
            self.failed.emit(exc.code, exc.message)
        except Exception:  # noqa: BLE001 -- sanitize unexpected failures
            self.failed.emit("INTERNAL_ERROR", INTERNAL_ERROR_MESSAGE)
        else:
            self.succeeded.emit(result)
        finally:
            self.finished.emit()


class BackgroundTask(QObject):
    """Own a worker + thread for one task; signals fire on the UI thread."""

    succeeded = Signal(object)
    failed = Signal(str, str)
    finished = Signal()

    def __init__(self, task: Callable[[], Any], parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._thread = QThread(self)
        self._worker = ProviderWorker(task)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.succeeded.connect(self.succeeded)
        self._worker.failed.connect(self.failed)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.finished.connect(self._thread.quit)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self.finished)

    def start(self) -> None:
        self._thread.start()


__all__ = [
    "INTERNAL_ERROR_MESSAGE",
    "BackgroundTask",
    "ProviderWorker",
]
