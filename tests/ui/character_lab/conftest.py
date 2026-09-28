"""Headless Qt and hermetic Character Lab facade fixtures."""

from __future__ import annotations

import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from services.character_lab_application import CharacterLabApplicationService
from tests.character_lab_application.conftest import build_config


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    existing = QApplication.instance()
    app = existing if isinstance(existing, QApplication) else QApplication([])
    yield app
    app.processEvents()


@pytest.fixture
def wait_until(qapp):
    """Spin the Qt event loop until ``condition()`` is true (or timeout)."""

    def _wait(condition, timeout_ms: int = 5000) -> bool:
        deadline = time.monotonic() + timeout_ms / 1000.0
        while time.monotonic() < deadline:
            qapp.processEvents()
            if condition():
                return True
            time.sleep(0.005)
        qapp.processEvents()
        return bool(condition())

    return _wait


@pytest.fixture
def lab_service(tmp_path) -> CharacterLabApplicationService:
    return CharacterLabApplicationService(build_config(tmp_path))


@pytest.fixture
def offline_lab_service() -> CharacterLabApplicationService:
    from services.character_lab_application import CharacterLabApplicationConfig

    return CharacterLabApplicationService(CharacterLabApplicationConfig(character_canon_root=None))
