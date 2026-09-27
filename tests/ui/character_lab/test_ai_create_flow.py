"""AI-first creation UI flow (headless/offscreen, injected provider)."""

from __future__ import annotations

from services.character_draft import CharacterDraftError, scripted_provider
from services.character_lab_application import (
    CharacterLabApplicationConfig,
    CharacterLabApplicationService,
)
from tests.character_draft._helpers import analysis_json, draft_json
from ui.character_lab.main_window import CharacterLabMainWindow


def _window(tmp_path, provider):
    config = CharacterLabApplicationConfig(
        character_authoring_root=tmp_path / "authoring"
    )
    service = CharacterLabApplicationService(config, draft_provider=provider)
    return CharacterLabMainWindow(service)


def test_create_tab_asks_name_and_description_not_ids(qapp, tmp_path):
    window = _window(tmp_path, scripted_provider([analysis_json()]))
    assert window.ai_name_edit is not None
    assert window.ai_description_edit is not None
    assert not hasattr(window, "ai_character_id_edit")


def test_analysis_renders_summary_questions_contradictions(qapp, tmp_path):
    window = _window(
        tmp_path,
        scripted_provider(
            [analysis_json(contradictions=[{"description": "age 24 vs age 28"}])]
        ),
    )
    window.ai_name_edit.setText("Катя")
    window.ai_description_edit.setPlainText("shy")
    window._on_analyze_clicked()

    assert window.create_stack.currentIndex() == 1
    assert "shy" in window.ai_summary_label.text()
    assert "age 24 vs age 28" in window.ai_contradictions_label.text()
    assert "What drives her?" in window.ai_questions_label.text()


def test_provider_error_is_user_readable(qapp, tmp_path):
    def failing(messages, system):
        raise CharacterDraftError(
            "API key is not configured. Set DEEPSEEK_API_KEY and retry."
        )

    window = _window(tmp_path, failing)
    window.ai_name_edit.setText("Катя")
    window.ai_description_edit.setPlainText("shy")
    window._on_analyze_clicked()
    assert window.create_stack.currentIndex() == 0  # stays on step 1


def test_successful_creation_targets_editor(qapp, tmp_path):
    window = _window(
        tmp_path,
        scripted_provider([analysis_json(readiness="READY_FOR_DRAFT"), draft_json()]),
    )
    window.ai_name_edit.setText("Катя")
    window.ai_description_edit.setPlainText("shy")
    window._on_analyze_clicked()
    assert window.create_stack.currentIndex() == 1

    window._on_build_now_clicked()
    assert window.create_stack.currentIndex() == 2

    window._on_open_editor_clicked()
    assert window.center_tabs.currentIndex() == 2
    assert window._ai_created is not None
    assert window.authoring_display_name_edit.text() == "Катя"


def test_creation_status_is_human_readable_without_technical_id(qapp, tmp_path):
    window = _window(
        tmp_path,
        scripted_provider([analysis_json(readiness="READY_FOR_DRAFT"), draft_json()]),
    )
    window.ai_name_edit.setText("Катя")
    window.ai_description_edit.setPlainText("shy")
    window._on_analyze_clicked()

    window._on_build_now_clicked()
    assert window.create_stack.currentIndex() == 2

    status = window.statusBar().currentMessage()
    # Human-readable, no technical identifier in the normal-user message.
    assert "Катя" in status
    assert "черновик" in status
    assert "char_" not in status

    # Technical ID is still retained internally for editor targeting.
    assert window._ai_created is not None
    assert window._ai_created[0].startswith("char_")

    # The expanded editor still loads the created character...
    window._on_open_editor_clicked()
    assert window.center_tabs.currentIndex() == 2
    assert window.authoring_display_name_edit.text() == "Катя"

    # ...and technical IDs remain only in the collapsed Технические данные area.
    assert window.authoring_character_id_edit.text().startswith("char_")
