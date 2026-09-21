"""Headless Qt and hermetic Character Lab facade fixtures."""

from __future__ import annotations

import os

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
def lab_service(tmp_path) -> CharacterLabApplicationService:
    return CharacterLabApplicationService(build_config(tmp_path))


@pytest.fixture
def offline_lab_service() -> CharacterLabApplicationService:
    from services.character_lab_application import CharacterLabApplicationConfig

    return CharacterLabApplicationService(CharacterLabApplicationConfig(character_canon_root=None))
