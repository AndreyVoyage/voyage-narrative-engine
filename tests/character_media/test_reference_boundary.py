#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Application save/load boundary validation tests for references (no VCP)."""

from __future__ import annotations

from pathlib import Path

import pytest

from services.character_authoring import CharacterAuthoringStore
from services.character_lab_application import (
    CharacterLabApplicationConfig,
    CharacterLabApplicationError,
    CharacterLabApplicationService,
)
from services.character_media import ReferenceBinding


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


def _ref(role: str, *, sha: str | None = None, **overrides) -> dict:
    data = {
        "role": role,
        "asset_sha256": sha or "a" * 64,
        "format": "PNG",
        "mime_type": "image/png",
        "byte_length": 10,
        "publishability": "PUBLISHABLE",
    }
    data.update(overrides)
    return data


def test_unknown_role_create_rejected_before_write(lab) -> None:
    service, authoring = lab
    with pytest.raises(CharacterLabApplicationError) as exc:
        service.create_character(
            character_id="synth",
            version_id="v1",
            revision_id="r1",
            version_label="V1",
            semantic=_semantic({"references": [_ref("pose")]}),
        )
    assert exc.value.code == "AUTHORING_VALIDATION_FAILED"
    assert list(authoring.list_character_ids()) == []


def test_unknown_publishability_create_rejected(lab) -> None:
    service, _authoring = lab
    with pytest.raises(CharacterLabApplicationError) as exc:
        service.create_character(
            character_id="synth",
            version_id="v1",
            revision_id="r1",
            version_label="V1",
            semantic=_semantic({"references": [_ref("face", publishability="BOGUS")]}),
        )
    assert exc.value.code == "AUTHORING_VALIDATION_FAILED"


def test_malformed_reference_save_rejected_before_write(lab) -> None:
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
            semantic=_semantic({"references": [{"role": "face"}]}),
        )
    assert exc.value.code == "AUTHORING_VALIDATION_FAILED"
    assert list(authoring.list_revisions("synth", "v1")) == ["r1"]


def test_malformed_persisted_reference_controlled_on_load(lab) -> None:
    service, authoring = lab
    authoring.create_character("synth")
    authoring.create_version("synth", "v1", version_label="V1")
    authoring.persist_revision(
        "synth",
        "v1",
        "r1",
        _semantic({"references": [{"role": "face", "bogus": True}]}),
    )
    with pytest.raises(CharacterLabApplicationError) as exc:
        service.load_revision_semantic("synth", "v1", "r1")
    assert exc.value.code == "INVALID_INPUT"


def test_valid_reference_roundtrips_through_boundary(lab) -> None:
    service, _authoring = lab
    binding = ReferenceBinding(
        role="face",
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
        semantic=_semantic({"references": [binding.to_dict()]}),
    )
    loaded = service.load_revision_semantic("synth", "v1", "r1")
    assert loaded.semantic["visual_identity"]["references"] == [binding.to_dict()]


def test_legacy_path_reference_persists_open_at_authoring(lab) -> None:
    # Legacy/unresolved Canon {key, path} entries are NOT silently converted to
    # managed bindings; they persist unchanged and are rejected only at
    # publication (covered by test_reference_publication.py).
    service, _authoring = lab
    service.create_character(
        character_id="synth",
        version_id="v1",
        revision_id="r1",
        version_label="V1",
        semantic=_semantic(
            {"references": [{"key": "legacy", "path": "characters/x/face.png"}]}
        ),
    )
    loaded = service.load_revision_semantic("synth", "v1", "r1")
    assert loaded.semantic["visual_identity"]["references"] == [
        {"key": "legacy", "path": "characters/x/face.png"}
    ]


def test_duplicate_binding_create_rejected_before_write(lab) -> None:
    # Two identical (role, asset_sha256) bindings in one revision are a
    # structural duplicate and must be rejected before any immutable write.
    service, authoring = lab
    ref = _ref("face")
    with pytest.raises(CharacterLabApplicationError) as exc:
        service.create_character(
            character_id="synth",
            version_id="v1",
            revision_id="r1",
            version_label="V1",
            semantic=_semantic({"references": [ref, dict(ref)]}),
        )
    assert exc.value.code == "AUTHORING_VALIDATION_FAILED"
    assert list(authoring.list_character_ids()) == []
