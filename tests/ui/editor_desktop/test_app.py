"""Bootstrap configuration remains singular and constructs the real facade."""

from pathlib import Path

from services.editor_application import EditorApplicationService
from ui.editor_desktop.app import PROJECT_ID, create_editor_config, create_editor_service


def test_project_configuration_boundary(tmp_path):
    root = tmp_path.resolve()
    config = create_editor_config(root)
    assert config.project_id == PROJECT_ID == "narrative_game"
    assert config.repo_root == root
    assert config.scene_drafts_root == root / "authoring" / "scene_drafts"
    assert config.accepted_ass_root == root / "authoring" / "accepted_ordered_ass"
    assert config.manifest_path == root / "authoring" / "project" / "PROJECT_MANIFEST.json"
    assert config.batch_path == root / "authoring" / "project" / "ACCEPTED_ORDEREDASS_BATCH.json"
    assert config.character_canon_root is None


def test_same_process_service_construction(tmp_path):
    assert isinstance(create_editor_service(tmp_path), EditorApplicationService)


def test_explicit_character_canon_root_is_supported(tmp_path):
    canon = tmp_path / "external-canon"
    assert create_editor_config(tmp_path, character_canon_root=canon).character_canon_root == canon.resolve()


def test_default_root_is_the_current_checkout():
    expected = Path(__file__).resolve().parents[3]
    assert create_editor_config().repo_root == expected
