"""Headless Qt and hermetic editor-facade fixtures."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from services.editor_application import EditorApplicationService
from tests.editor_application.conftest import build_config, make_body


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    existing = QApplication.instance()
    app = existing if isinstance(existing, QApplication) else QApplication([])
    yield app
    app.processEvents()


@pytest.fixture
def populated_service(tmp_path) -> EditorApplicationService:
    service = EditorApplicationService(build_config(tmp_path))
    result = service.create_scene("sc_test_001", make_body())
    assert result.ok
    return service
