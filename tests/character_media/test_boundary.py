#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Application save/load boundary validation tests (no VCP required)."""

from __future__ import annotations

from pathlib import Path

import pytest

from services.character_authoring import CharacterAuthoringStore
from services.character_lab_application import (
    CharacterLabApplicationConfig,
    CharacterLabApplicationError,
    CharacterLabApplicationService,
)
from services.character_media import InvalidBindingError, PortraitBinding


def _semantic(visual_identity) -> dict:
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


@pytest.fixture
def lab(tmp_path: Path):
    root = tmp_path / "authoring"
    service = CharacterLabApplicationService(
        CharacterLabApplicationConfig(character_authoring_root=root)
    )
    return service, CharacterAuthoringStore(root)


def test_malformed_portrait_create_rejected_before_write(lab) -> None:
    service, authoring = lab
    with pytest.raises(CharacterLabApplicationError) as exc:
        service.create_character(
            character_id="synth",
            version_id="v1",
            revision_id="r1",
            version_label="V1",
            semantic=_semantic(
                {"references": [], "primary_portrait": {"bogus": True}}
            ),
        )
    assert exc.value.code == "AUTHORING_VALIDATION_FAILED"
    assert list(authoring.list_character_ids()) == []


def test_malformed_portrait_save_rejected_before_write(lab) -> None:
    service, authoring = lab
    service.create_character(
        character_id="synth",
        version_id="v1",
        revision_id="r1",
        version_label="V1",
        semantic=_semantic({"references": []}),
    )
    with pytest.raises(CharacterLabApplicationError) as exc:
        service.save_character(
            character_id="synth",
            version_id="v1",
            revision_id="r2",
            semantic=_semantic(
                {"references": [], "primary_portrait": {"bogus": True}}
            ),
        )
    assert exc.value.code == "AUTHORING_VALIDATION_FAILED"
    assert list(authoring.list_revisions("synth", "v1")) == ["r1"]


def test_unknown_publishability_save_rejected(lab) -> None:
    service, _authoring = lab
    with pytest.raises(CharacterLabApplicationError) as exc:
        service.create_character(
            character_id="synth",
            version_id="v1",
            revision_id="r1",
            version_label="V1",
            semantic=_semantic(
                {
                    "references": [],
                    "primary_portrait": {
                        "role": "primary_portrait",
                        "asset_sha256": "a" * 64,
                        "format": "PNG",
                        "mime_type": "image/png",
                        "byte_length": 10,
                        "publishability": "BOGUS",
                    },
                }
            ),
        )
    assert exc.value.code == "AUTHORING_VALIDATION_FAILED"


def test_malformed_portrait_load_controlled_failure(lab) -> None:
    service, authoring = lab
    # Persist a deliberately malformed binding directly through the store to
    # simulate corrupted legacy data (bypassing the application save boundary).
    authoring.create_character("synth")
    authoring.create_version("synth", "v1", version_label="V1")
    authoring.persist_revision(
        "synth",
        "v1",
        "r1",
        _semantic({"references": [], "primary_portrait": {"bogus": True}}),
    )
    with pytest.raises(CharacterLabApplicationError) as exc:
        service.load_revision_semantic("synth", "v1", "r1")
    assert exc.value.code == "INVALID_INPUT"


def test_valid_portrait_roundtrips_through_boundary(lab) -> None:
    service, _authoring = lab
    binding = PortraitBinding(
        asset_sha256="c" * 64,
        format="WEBP",
        mime_type="image/webp",
        byte_length=10,
        publishability="AUTHORING_ONLY",
    )
    service.create_character(
        character_id="synth",
        version_id="v1",
        revision_id="r1",
        version_label="V1",
        semantic=_semantic({"references": [], "primary_portrait": binding.to_dict()}),
    )
    loaded = service.load_revision_semantic("synth", "v1", "r1")
    assert loaded.semantic["visual_identity"]["primary_portrait"] == binding.to_dict()
