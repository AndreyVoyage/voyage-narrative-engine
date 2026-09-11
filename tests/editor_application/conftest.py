#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared fixtures for Editor Application Service v1 tests.

Builds a fully hermetic temp project (scene drafts root, accepted ASS root,
empty manifest, absent batch, synthetic locations and characters) so the full
editor workflow can be exercised through the facade without touching production
authoring authority.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from services.editor_application import EditorApplicationConfig, EditorApplicationService

PROJECT_ID = "test_project"


def make_body(scene_id: str = "sc_test_001", **overrides) -> dict[str, Any]:
    """A valid, acceptance-complete SceneBody (scene_body/1.0) as a plain dict."""
    body: dict[str, Any] = {
        "authoring_schema_version": "scene_body/1.0",
        "scene_id": scene_id,
        "scene_title": "Test scene",
        "location_id": "yoga_hall",
        "participants": [{"character_id": "KIRA", "role": "protagonist", "present": True}],
        "content_rating": "PG-13",
        "character_state_overrides": None,
        "location_state_overrides": None,
        "entries": [
            {
                "entry_id": "e1",
                "kind": "TEXT",
                "presentation": "NARRATIVE",
                "text": "Kira enters the yoga hall.",
                "character_id": None,
                "thought_visibility": None,
            },
            {
                "entry_id": "c1",
                "kind": "CHOICE",
                "prompt": "What next?",
                "options": [
                    {
                        "option_id": "o1",
                        "display_text": "Continue",
                        "target": {"target_kind": "SCENE", "target_id": "sc_next_001"},
                    }
                ],
            },
        ],
    }
    body.update(overrides)
    return body


def write_character_preset(
    canon_root: Path, character_id: str, status: str = "APPROVED_AS_CANON"
) -> None:
    char_dir = canon_root / "AI_CHARACTERS" / character_id / "10_notes"
    char_dir.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "character": character_id,
        "active_version": "v1",
        "status": status,
        "active_canon": {"face": f"AI_CHARACTERS/{character_id}/03_face_sheet/face.png"},
    }
    (char_dir / f"{character_id}_REFERENCE_PRESETS.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )


def write_location(repo_root: Path, location_id: str, tier: str = "premium") -> None:
    locations_dir = repo_root / "scenarios" / "locations"
    locations_dir.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "schema_version": "location/0.1",
        "location_id": location_id,
        "tier": tier,
        "scale": ["small", "intimate"],
        "identity": ["test"],
        "palette": ["warm"],
        "fixed_features": [{"feature_id": "f1", "label": "feature one"}],
    }
    (locations_dir / f"{location_id}.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )


def write_empty_manifest(manifest_path: Path, project_id: str) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "schema_version": "vne_workspace_project_manifest/0.1",
        "project_id": project_id,
        "entities": [],
    }
    manifest_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def build_config(
    tmp_path: Path,
    *,
    with_manifest: bool = True,
    with_characters: bool = True,
    with_locations: bool = True,
) -> EditorApplicationConfig:
    scene_drafts_root = tmp_path / "scene_drafts"
    accepted_ass_root = tmp_path / "accepted_ass"
    manifest_path = tmp_path / "project" / "PROJECT_MANIFEST.json"
    batch_path = tmp_path / "project" / "ACCEPTED_ORDEREDASS_BATCH.json"
    repo_root = tmp_path / "repo"
    character_canon_root = tmp_path / "character_canon"

    scene_drafts_root.mkdir(parents=True, exist_ok=True)
    accepted_ass_root.mkdir(parents=True, exist_ok=True)
    repo_root.mkdir(parents=True, exist_ok=True)

    if with_manifest:
        write_empty_manifest(manifest_path, PROJECT_ID)
    if with_characters:
        write_character_preset(character_canon_root, "KIRA")
        write_character_preset(character_canon_root, "SERGEY")
    if with_locations:
        write_location(repo_root, "gym")
        write_location(repo_root, "yoga_hall")

    return EditorApplicationConfig(
        project_id=PROJECT_ID,
        scene_drafts_root=scene_drafts_root,
        accepted_ass_root=accepted_ass_root,
        manifest_path=manifest_path,
        batch_path=batch_path,
        repo_root=repo_root,
        character_canon_root=character_canon_root,
    )


@pytest.fixture
def service(tmp_path: Path) -> EditorApplicationService:
    return EditorApplicationService(build_config(tmp_path))
