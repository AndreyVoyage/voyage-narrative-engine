"""Offscreen UI tests for the human-readable expanded editor.

Verifies the nine product sections exist, the technical IDs are surfaced only
through a collapsed "Технические данные" group, and the semantic collection /
loading round-trips the new sexology + description fields.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QGroupBox, QLineEdit  # noqa: E402

from services.character_lab_application import (  # noqa: E402
    CharacterLabApplicationConfig,
    CharacterLabApplicationService,
)

HUMAN_SECTIONS = (
    "Обзор",
    "Биография",
    "Психология",
    "Речь",
    "Отношения",
    "Сексология",
    "Границы",
    "Внешность",
    "Медиа",
)

SEXOLOGY_KEYS = (
    "intimacy_attitudes",
    "preferences",
    "emotional_dynamics",
    "communication",
    "vulnerabilities",
    "intimacy_boundaries",
)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def window(qapp, tmp_path):
    from ui.character_lab.main_window import CharacterLabMainWindow

    config = CharacterLabApplicationConfig(
        character_canon_root=None,
        character_authoring_root=tmp_path / "authoring",
        character_release_store_root=None,
    )
    service = CharacterLabApplicationService(config)
    return CharacterLabMainWindow(service)


def _group(window, title):
    for box in window.findChildren(QGroupBox):
        if box.title() == title:
            return box
    return None


def test_editor_exposes_human_readable_sections(window):
    titles = {box.title() for box in window.findChildren(QGroupBox)}
    for section in HUMAN_SECTIONS:
        assert section in titles, f"missing section {section!r}"


def test_technical_ids_are_in_collapsed_advanced_group(window):
    technical = _group(window, "Технические данные")
    assert technical is not None
    assert technical.isCheckable()
    assert not technical.isChecked(), "technical group must be collapsed by default"

    # The machine IDs are descendants of the technical group...
    for edit in (
        window.authoring_character_id_edit,
        window.authoring_version_id_edit,
        window.authoring_revision_id_edit,
    ):
        assert edit in technical.findChildren(QLineEdit)

    # ...and are NOT exposed in the human-readable Обзор section.
    overview = _group(window, "Обзор")
    assert overview is not None
    assert window.authoring_character_id_edit not in overview.findChildren(QLineEdit)


def test_collect_semantic_includes_sexology_and_descriptions(window):
    window.authoring_display_name_edit.setText("Катя")
    window.authoring_short_description_edit.setPlainText("Коротко")
    window.authoring_detailed_description_edit.setPlainText("Подробно")
    window.authoring_intimacy_attitudes_edit.setText("нежная, сдержанная")
    window.authoring_preferences_edit.setText("медленно")

    data = window._collect_semantic()
    assert data["identity"]["display_name"] == "Катя"
    assert data["identity"]["short_description"] == "Коротко"
    assert data["identity"]["detailed_description"] == "Подробно"
    assert data["sexology"]["intimacy_attitudes"] == ["нежная", "сдержанная"]
    assert data["sexology"]["preferences"] == ["медленно"]
    assert set(data["sexology"]) == set(SEXOLOGY_KEYS)


def test_load_semantic_populates_sexology_and_descriptions(window):
    window._load_semantic_to_form(
        {
            "identity": {
                "display_name": "Катя",
                "short_description": "Коротко",
                "detailed_description": "Подробно",
            },
            "biography": "",
            "psychology": {},
            "speech": {},
            "character_relations": {},
            "appearance": {},
            "boundaries": {},
            "visual_identity": {},
            "sexology": {
                "intimacy_attitudes": ["нежная"],
                "preferences": ["медленно"],
                "emotional_dynamics": [],
                "communication": [],
                "vulnerabilities": [],
                "intimacy_boundaries": [],
            },
        }
    )

    assert window.authoring_short_description_edit.toPlainText() == "Коротко"
    assert window.authoring_detailed_description_edit.toPlainText() == "Подробно"
    assert window.authoring_intimacy_attitudes_edit.text() == "нежная"
    assert window.authoring_preferences_edit.text() == "медленно"
