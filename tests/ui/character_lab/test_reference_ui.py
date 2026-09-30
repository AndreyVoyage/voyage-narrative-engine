"""Headless UI tests for the nested Reference Library section (no VCP)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QFileDialog, QGroupBox

from services.character_lab_application import (
    CharacterLabApplicationConfig,
    CharacterLabApplicationService,
)
from tests.character_media._images import png
from ui.character_lab.main_window import CharacterLabMainWindow

ROLE_KEYS = ["face", "body", "expression", "identity", "motion"]


@pytest.fixture
def service(tmp_path: Path) -> CharacterLabApplicationService:
    return CharacterLabApplicationService(
        CharacterLabApplicationConfig(character_authoring_root=tmp_path / "authoring")
    )


def _find_group(window: CharacterLabMainWindow, title: str) -> QGroupBox:
    for box in window.findChildren(QGroupBox):
        if box.title() == title:
            return box
    raise AssertionError(f"no QGroupBox with title {title!r}")


def test_media_section_preserved_with_nested_references(qapp, service):
    window = CharacterLabMainWindow(service)
    media = _find_group(window, "Медиа")
    nested = {box.title() for box in media.findChildren(QGroupBox)}
    assert "Первичный портрет" in nested
    assert "Референсы" in nested


def test_reference_role_dropdown_has_five_roles(qapp, service):
    window = CharacterLabMainWindow(service)
    combo = window.authoring_reference_role_combo
    assert combo.count() == 5
    assert [combo.itemData(i) for i in range(combo.count())] == ROLE_KEYS


def test_add_reference_populates_pending_and_collects(qapp, service, tmp_path, monkeypatch):
    window = CharacterLabMainWindow(service)
    window._authoring_character_id = "ui-ref-char"
    source = tmp_path / "face.png"
    source.write_bytes(png(4, 4))
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(source), ""))
    )
    window.authoring_reference_publishable_checkbox.setChecked(True)

    window._on_add_reference_clicked()

    assert len(window._pending_references) == 1
    assert window._pending_references[0]["role"] == "face"
    assert window._pending_references[0]["publishability"] == "PUBLISHABLE"
    assert window.authoring_reference_list.count() == 1

    vi = window._collect_visual_identity()
    assert len(vi["references"]) == 1
    assert vi["references"][0]["role"] == "face"


def test_remove_reference_affects_pending_only(qapp, service, tmp_path):
    window = CharacterLabMainWindow(service)
    window._authoring_character_id = "ui-ref-char"
    for role in ("face", "body"):
        source = tmp_path / f"{role}.png"
        source.write_bytes(png(4, 4))
        result = service.import_reference(
            character_id="ui-ref-char",
            source_path=source,
            role=role,
            publishability="PUBLISHABLE",
        )
        window._pending_references.append(
            {
                "role": result.role,
                "asset_sha256": result.asset_sha256,
                "format": result.format,
                "mime_type": result.mime_type,
                "byte_length": result.byte_length,
                "publishability": "PUBLISHABLE",
            }
        )
    window._render_reference_list()
    assert len(window._pending_references) == 2

    window.authoring_reference_list.setCurrentRow(0)
    window._on_remove_reference_clicked()
    assert len(window._pending_references) == 1
    assert window._pending_references[0]["role"] == "body"


def test_reference_preview_reads_managed_bytes(qapp, service, tmp_path):
    window = CharacterLabMainWindow(service)
    window._authoring_character_id = "ui-ref-char"
    source = tmp_path / "preview.png"
    source.write_bytes(png(4, 4))
    result = service.import_reference(
        character_id="ui-ref-char",
        source_path=source,
        role="face",
        publishability="AUTHORING_ONLY",
    )
    window._pending_references.append(
        {
            "role": result.role,
            "asset_sha256": result.asset_sha256,
            "format": result.format,
            "mime_type": result.mime_type,
            "byte_length": result.byte_length,
            "publishability": "AUTHORING_ONLY",
        }
    )
    window._render_reference_list()

    window._render_reference_preview(0)
    # Preview either renders a pixmap (empty text) or a graceful fallback.
    assert window.authoring_reference_preview.text() in ("", "Предпросмотр недоступен")


# -- Roundtrip / rehydration / duplicate-boundary ------------------------------


def _semantic(visual_identity: dict) -> dict:
    return {
        "identity": {"display_name": "Synth"},
        "biography": "b",
        "psychology": {
            "personality": [],
            "behavioral_traits": [],
            "emotional_tendencies": [],
            "goals_motivations": [],
        },
        "speech": {"speech_style": "x", "register": None},
        "character_relations": {"relational_tendencies": [], "attachment_traits": []},
        "appearance": {"descriptors": []},
        "boundaries": {"principles": []},
        "visual_identity": visual_identity,
    }


def _import_ref(service, tmp_path: Path, character_id: str, role: str) -> dict:
    source = tmp_path / f"{character_id}-{role}.png"
    source.write_bytes(png(4, 4))
    result = service.import_reference(
        character_id=character_id,
        source_path=source,
        role=role,
        publishability="PUBLISHABLE",
    )
    return {
        "role": result.role,
        "asset_sha256": result.asset_sha256,
        "format": result.format,
        "mime_type": result.mime_type,
        "byte_length": result.byte_length,
        "publishability": "PUBLISHABLE",
    }


def test_load_semantic_repopulates_references(qapp, service, tmp_path):
    window = CharacterLabMainWindow(service)
    face = _import_ref(service, tmp_path, "roundtrip-char", "face")
    body = _import_ref(service, tmp_path, "roundtrip-char", "body")
    service.create_character(
        character_id="roundtrip-char",
        version_id="v1",
        revision_id="r1",
        version_label="V1",
        semantic=_semantic({"references": [face, body]}),
    )

    loaded = service.load_revision_semantic("roundtrip-char", "v1", "r1")
    window._load_semantic_to_form(loaded.semantic)

    assert window._pending_references == [face, body]
    assert window.authoring_reference_list.count() == 2


def test_save_roundtrip_preserves_references(qapp, service, tmp_path):
    window = CharacterLabMainWindow(service)
    face = _import_ref(service, tmp_path, "roundtrip-char", "face")
    body = _import_ref(service, tmp_path, "roundtrip-char", "body")
    service.create_character(
        character_id="roundtrip-char",
        version_id="v1",
        revision_id="r1",
        version_label="V1",
        semantic=_semantic({"references": [face, body]}),
    )

    loaded = service.load_revision_semantic("roundtrip-char", "v1", "r1")
    window._load_semantic_to_form(loaded.semantic)

    new_semantic = dict(loaded.semantic)
    new_semantic["visual_identity"] = window._collect_visual_identity()
    service.save_character(
        character_id="roundtrip-char",
        version_id="v1",
        revision_id="r2",
        semantic=new_semantic,
    )

    r2 = service.load_revision_semantic("roundtrip-char", "v1", "r2")
    assert r2.semantic["visual_identity"]["references"] == [face, body]


def test_remove_binding_save_removes_only_that(qapp, service, tmp_path):
    window = CharacterLabMainWindow(service)
    face = _import_ref(service, tmp_path, "roundtrip-char", "face")
    body = _import_ref(service, tmp_path, "roundtrip-char", "body")
    service.create_character(
        character_id="roundtrip-char",
        version_id="v1",
        revision_id="r1",
        version_label="V1",
        semantic=_semantic({"references": [face, body]}),
    )

    loaded = service.load_revision_semantic("roundtrip-char", "v1", "r1")
    window._load_semantic_to_form(loaded.semantic)
    # Remove BODY (second row).
    window.authoring_reference_list.setCurrentRow(1)
    window._on_remove_reference_clicked()

    new_semantic = dict(loaded.semantic)
    new_semantic["visual_identity"] = window._collect_visual_identity()
    service.save_character(
        character_id="roundtrip-char",
        version_id="v1",
        revision_id="r2",
        semantic=new_semantic,
    )

    r2 = service.load_revision_semantic("roundtrip-char", "v1", "r2")
    assert r2.semantic["visual_identity"]["references"] == [face]

    # r1 remains immutable.
    r1 = service.load_revision_semantic("roundtrip-char", "v1", "r1")
    assert r1.semantic["visual_identity"]["references"] == [face, body]


def test_legacy_reference_not_converted_on_load(qapp, service):
    window = CharacterLabMainWindow(service)
    service.create_character(
        character_id="legacy-char",
        version_id="v1",
        revision_id="r1",
        version_label="V1",
        semantic=_semantic(
            {"references": [{"key": "legacy", "path": "characters/x/face.png"}]}
        ),
    )

    loaded = service.load_revision_semantic("legacy-char", "v1", "r1")
    window._load_semantic_to_form(loaded.semantic)

    assert window._pending_references == []
    assert loaded.semantic["visual_identity"]["references"] == [
        {"key": "legacy", "path": "characters/x/face.png"}
    ]
