#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Focused tests for the physical-profiles snapshot generator + runner block.

Hermetic (synthetic presets / physical profiles) except for a small number of
real-NCC integration tests that skip when the canon root is absent.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import tools.build_physical_profiles as bpp  # noqa: E402
import tools.scene_image_test_app as app  # noqa: E402
from tools.build_physical_profiles import (  # noqa: E402
    CharacterMismatchError,
    build_snapshot,
    discover_preset_paths,
    normalize_preset,
    serialize_snapshot,
)

REAL_CANON = Path("C:/DEV/Narrative/narrative-character-canon")
_NEEDS_REAL_CANON = not REAL_CANON.is_dir()

_ALIASES = {"MARINA": "Marina", "MAKSIM": "Maksim"}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_preset(canon_root: Path, char_id: str, preset: dict) -> Path:
    notes = canon_root / "AI_CHARACTERS" / char_id / "10_notes"
    notes.mkdir(parents=True, exist_ok=True)
    path = notes / f"{char_id}_REFERENCE_PRESETS.json"
    path.write_text(json.dumps(preset), encoding="utf-8")
    return path


def _identity(**kw) -> dict:
    base = {
        "role": "adult female character",
        "body_direction": "default body",
        "face_direction": "default face",
        "hair_direction": "default hair",
    }
    base.update(kw)
    return base


def _preset(char_id: str, identity: dict, **extra) -> dict:
    data = {"character": char_id, "identity_summary": identity}
    data.update(extra)
    return data


def _prof(**kw) -> dict:
    base = {
        "character_id": "X",
        "role": "adult female character",
        "height_cm": None,
        "height_is_approx": False,
        "height_direction": None,
        "weight_kg": None,
        "weight_direction": None,
        "body_direction": "",
        "face_direction": "",
        "hair_direction": "",
        "style_direction_raw": "",
        "confirmed_traits": [],
        "safety_rules": ["record prompt_id, references, output path..."],
        "source_preset_sha256": "a" * 64,
        "source_preset_path": "AI_CHARACTERS/X/10_notes/X_REFERENCE_PRESETS.json",
    }
    base.update(kw)
    return base


def _marina_prof() -> dict:
    return _prof(
        character_id="MARINA",
        role="adult female character",
        height_cm=155,
        weight_kg=45.0,
        body_direction="petite slender feminine adult build, compact realistic "
        "proportions, narrow shoulders, small defined waist, proportionate "
        "feminine build, not exaggerated",
    )


def _maksim_prof() -> dict:
    return _prof(
        character_id="MAKSIM",
        role="adult male character",
        height_cm=188,
        weight_direction="approximately 115 kg",
        body_direction="tall classic golden-era bodybuilder, very wide shoulders, "
        "deep massive chest, powerful back, large arms, controlled flat abdomen, "
        "massive legs",
    )


# ---------------------------------------------------------------------------
# Generator: discovery / determinism / SHA / mismatch (items 1-4)
# ---------------------------------------------------------------------------


def test_preset_discovery(tmp_path):
    canon = tmp_path / "canon"
    for cid, ident in (
        ("CHAR_A", _identity(height_cm=170)),
        ("CHAR_B", _identity(height_cm=180)),
        ("CHAR_C", _identity(height_cm=190)),
    ):
        _write_preset(canon, cid, _preset(cid, ident))
    # An underscore-prefixed meta directory at the same level must be skipped.
    joint_notes = canon / "AI_CHARACTERS" / "_JOINT" / "10_notes"
    joint_notes.mkdir(parents=True, exist_ok=True)
    (joint_notes / "_JOINT_REFERENCE_PRESETS.json").write_text(
        json.dumps(_preset("_JOINT", _identity(height_cm=0))), encoding="utf-8"
    )
    discovered = discover_preset_paths(canon)
    assert set(discovered) == {"CHAR_A", "CHAR_B", "CHAR_C"}


def test_deterministic_output(tmp_path):
    canon = tmp_path / "canon"
    _write_preset(canon, "CHAR_A", _preset("CHAR_A", _identity(height_cm=170)))
    _write_preset(canon, "CHAR_B", _preset("CHAR_B", _identity(height_cm=180)))
    s1 = serialize_snapshot(build_snapshot(canon))
    s2 = serialize_snapshot(build_snapshot(canon))
    assert s1 == s2


def test_source_preset_sha(tmp_path):
    canon = tmp_path / "canon"
    path = _write_preset(canon, "CHAR_A", _preset("CHAR_A", _identity(height_cm=170)))
    snapshot = build_snapshot(canon)
    assert snapshot["characters"]["CHAR_A"]["source_preset_sha256"] == _sha(
        path.read_bytes()
    )


def test_character_directory_mismatch_rejected():
    with pytest.raises(CharacterMismatchError):
        normalize_preset(
            _preset("OTHER", _identity(height_cm=170)),
            "CHAR_A",
            source_sha="a" * 64,
            source_path="AI_CHARACTERS/CHAR_A/10_notes/CHAR_A_REFERENCE_PRESETS.json",
        )


# ---------------------------------------------------------------------------
# Generator: MARINA / MAKSIM normalization (items 5-13)
# ---------------------------------------------------------------------------


def test_marina_height_cm():
    rec = normalize_preset(
        _preset(
            "MARINA",
            _identity(height_cm=155, weight_kg=45, height_direction="petite compact build, 155 cm"),
        ),
        "MARINA",
        source_sha="a" * 64,
        source_path="p",
    )
    assert rec["height_cm"] == 155


def test_marina_exact_height():
    rec = normalize_preset(
        _preset("MARINA", _identity(height_cm=155)),
        "MARINA",
        source_sha="a" * 64,
        source_path="p",
    )
    assert rec["height_is_approx"] is False


def test_marina_weight_kg():
    rec = normalize_preset(
        _preset("MARINA", _identity(height_cm=155, weight_kg=45)),
        "MARINA",
        source_sha="a" * 64,
        source_path="p",
    )
    assert rec["weight_kg"] == 45


def test_marina_petite_wording_preserved():
    rec = normalize_preset(
        _preset(
            "MARINA",
            _identity(height_cm=155, body_direction="petite slender compact build"),
        ),
        "MARINA",
        source_sha="a" * 64,
        source_path="p",
    )
    assert "petite" in rec["body_direction"]


def test_maksim_height_cm_from_owner_approved():
    rec = normalize_preset(
        _preset(
            "MAKSIM",
            _identity(height="188 cm", height_status="OWNER_APPROVED_CANON"),
        ),
        "MAKSIM",
        source_sha="a" * 64,
        source_path="p",
    )
    assert rec["height_cm"] == 188


def test_maksim_exact_height_due_owner_status():
    rec = normalize_preset(
        _preset(
            "MAKSIM",
            _identity(height="188 cm", height_status="OWNER_APPROVED_CANON"),
        ),
        "MAKSIM",
        source_sha="a" * 64,
        source_path="p",
    )
    assert rec["height_is_approx"] is False


def test_maksim_weight_kg_none():
    rec = normalize_preset(
        _preset(
            "MAKSIM",
            _identity(height="188 cm", weight_direction="approximately 115 kg"),
        ),
        "MAKSIM",
        source_sha="a" * 64,
        source_path="p",
    )
    assert rec["weight_kg"] is None


def test_maksim_weight_direction():
    rec = normalize_preset(
        _preset(
            "MAKSIM",
            _identity(height="188 cm", weight_direction="approximately 115 kg"),
        ),
        "MAKSIM",
        source_sha="a" * 64,
        source_path="p",
    )
    assert rec["weight_direction"] == "approximately 115 kg"


def test_maksim_bodybuilder_wording_preserved():
    rec = normalize_preset(
        _preset(
            "MAKSIM",
            _identity(height="188 cm", body_direction="tall classic golden-era bodybuilder"),
        ),
        "MAKSIM",
        source_sha="a" * 64,
        source_path="p",
    )
    assert "bodybuilder" in rec["body_direction"]


# ---------------------------------------------------------------------------
# Generator: prose-only / absent / no-invention (items 14-17)
# ---------------------------------------------------------------------------


def test_prose_only_height_works():
    rec = normalize_preset(
        _preset("KIRA", _identity(height_direction="medium-tall, around 168 cm")),
        "KIRA",
        source_sha="a" * 64,
        source_path="p",
    )
    assert rec["height_cm"] == 168
    assert rec["height_is_approx"] is True


def test_absent_numeric_height_remains_none():
    rec = normalize_preset(
        _preset("NIKA", _identity(height_direction="medium-tall, lean and graceful")),
        "NIKA",
        source_sha="a" * 64,
        source_path="p",
    )
    assert rec["height_cm"] is None


def test_missing_weight_remains_none():
    rec = normalize_preset(
        _preset("NIKA", _identity(height_direction="medium-tall")),
        "NIKA",
        source_sha="a" * 64,
        source_path="p",
    )
    assert rec["weight_kg"] is None
    assert rec["weight_direction"] is None


def test_no_bmi_age_synthetic_weight():
    rec = normalize_preset(
        _preset(
            "EGOR",
            _identity(body_direction="athletic build, realistic proportions, 83 kg"),
        ),
        "EGOR",
        source_sha="a" * 64,
        source_path="p",
    )
    # 83 kg stays inside body_direction; never mined into weight_kg.
    assert rec["weight_kg"] is None
    assert "83 kg" in rec["body_direction"]
    for key in rec:
        assert "bmi" not in key.lower()
        assert "age" not in key.lower()


# ---------------------------------------------------------------------------
# Renderer: aliases / discipline (items 18-21)
# ---------------------------------------------------------------------------


def _block(profiles, cids=("MARINA", "MAKSIM"), aliases=_ALIASES):
    return app._render_physical_block(cids, aliases, profiles)


def test_physical_block_uses_prompt_aliases():
    block = _block({"MARINA": _marina_prof(), "MAKSIM": _maksim_prof()})
    assert "Marina:" in block
    assert "Maksim:" in block
    assert "MARINA" not in block
    assert "MAKSIM" not in block


def test_internal_ids_absent():
    block = _block({"MARINA": _marina_prof(), "MAKSIM": _maksim_prof()})
    assert "MARINA" not in block
    assert "MAKSIM" not in block


def test_style_direction_not_emitted():
    prof = _prof(character_id="MAKSIM", role="adult male character",
                 height_cm=188, body_direction="bodybuilder build",
                 style_direction_raw="formal tailored dark suit")
    block = _block({"MAKSIM": prof}, cids=("MAKSIM",), aliases={"MAKSIM": "Maksim"})
    assert "tailored dark suit" not in block
    assert "formal" not in block


def test_operational_safety_rule_not_emitted():
    prof = _prof(character_id="MARINA", height_cm=155, body_direction="petite build",
                 safety_rules=["record prompt_id, references, output path..."])
    block = _block({"MARINA": prof}, cids=("MARINA",), aliases={"MARINA": "Marina"})
    assert "record prompt_id" not in block


# ---------------------------------------------------------------------------
# Renderer: relative scale thresholds (items 22-25)
# ---------------------------------------------------------------------------


def test_relative_scale_ge8_visibly_taller():
    block = _block({"A": _prof(character_id="A", height_cm=180, role="adult male character"),
                    "B": _prof(character_id="B", height_cm=160, role="adult female character")},
                   cids=("A", "B"), aliases={"A": "Alpha", "B": "Beta"})
    assert "Alpha is visibly taller than Beta." in block


def test_relative_scale_3_to_7_somewhat_taller():
    block = _block({"A": _prof(character_id="A", height_cm=180, role="adult male character"),
                    "B": _prof(character_id="B", height_cm=175, role="adult male character")},
                   cids=("A", "B"), aliases={"A": "Alpha", "B": "Beta"})
    assert "Alpha is somewhat taller than Beta." in block


def test_relative_scale_lt3_comparable():
    block = _block({"A": _prof(character_id="A", height_cm=180, role="adult male character"),
                    "B": _prof(character_id="B", height_cm=179, role="adult male character")},
                   cids=("A", "B"), aliases={"A": "Alpha", "B": "Beta"})
    assert "comparable height" in block


def test_no_number_pair_does_not_invent_numbers():
    block = _block({"A": _prof(character_id="A", height_cm=None, height_direction="short, compact"),
                    "B": _prof(character_id="B", height_cm=None, height_direction="medium-tall")},
                   cids=("A", "B"), aliases={"A": "Alpha", "B": "Beta"})
    import re
    assert not re.search(r"\d+\s*cm", block)


# ---------------------------------------------------------------------------
# Renderer: MARINA+MAKSIM content (items 26-29)
# ---------------------------------------------------------------------------


def test_marina_maksim_block_includes_188_vs_155():
    block = _block({"MARINA": _marina_prof(), "MAKSIM": _maksim_prof()})
    assert "155 cm" in block
    assert "188 cm" in block


def test_approximate_115_kg_remains_qualified():
    block = _block({"MARINA": _marina_prof(), "MAKSIM": _maksim_prof()})
    assert "approximately 115 kg" in block


def test_no_exact_kg_delta_invented():
    block = _block({"MARINA": _marina_prof(), "MAKSIM": _maksim_prof()})
    assert "kg heavier" not in block
    assert "kg difference" not in block
    assert "kg lighter" not in block


def test_strong_size_contrast_wording_present():
    block = _block({"MARINA": _marina_prof(), "MAKSIM": _maksim_prof()})
    assert "contrast" in block
    assert "substantially heavier, broader and more massive" in block


# ---------------------------------------------------------------------------
# Runner integration (items 30-33)
# ---------------------------------------------------------------------------


def _physical_profiles_for_andrey_olga() -> dict:
    return {
        "ANDREY_JUNIOR": _prof(
            character_id="ANDREY_JUNIOR",
            role="adult male character",
            height_cm=172,
            weight_kg=65.0,
            body_direction="slim athletic build, compact frame",
        ),
        "OLGA": _prof(
            character_id="OLGA",
            role="mature adult woman character",
            height_cm=187,
            height_is_approx=True,
            body_direction="tall athletic curvy build",
        ),
    }


def _run_with_and_without_physical(tmp_path):
    from tests.test_scene_image_test_app import _build_hermetic

    hermetic = _build_hermetic(tmp_path)
    root = hermetic["root"]
    manifest = hermetic["manifest"]
    profile = app.Profile(hermetic["profile"])

    r1 = app.orchestrate(profile, repo_root=root, manifest_path=manifest)

    ppath = root / "authoring" / "scene_image_test_profiles" / "physical_profiles.json"
    ppath.write_text(
        json.dumps(
            {
                "schema_version": "vne_physical_profiles/0.1",
                "characters": _physical_profiles_for_andrey_olga(),
            }
        ),
        encoding="utf-8",
    )
    r2 = app.orchestrate(profile, repo_root=root, manifest_path=manifest)
    return r1, r2


def test_final_prompt_hash_changes_with_physical_block(tmp_path):
    r1, r2 = _run_with_and_without_physical(tmp_path)
    assert r1.final_prompt_hash != r2.final_prompt_hash
    assert "CHARACTER PHYSICAL IDENTITY" in r2.final_prompt_text


def test_reference_bundle_unchanged(tmp_path):
    r1, r2 = _run_with_and_without_physical(tmp_path)
    assert r1.bundle.content_hash == r2.bundle.content_hash


def test_attachment_order_unchanged(tmp_path):
    r1, r2 = _run_with_and_without_physical(tmp_path)
    assert r1.attachment_filenames == r2.attachment_filenames


def test_provider_exposure_gate_still_passes(tmp_path):
    _, r2 = _run_with_and_without_physical(tmp_path)
    assert r2.provider_exposure is False
    assert r2.gates["provider_exposure"] is True


# ---------------------------------------------------------------------------
# Real NCC integration (skipped when canon root is absent)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(_NEEDS_REAL_CANON, reason="real NCC canon root not present")
def test_real_snapshot_has_nine_characters():
    snapshot = build_snapshot(REAL_CANON)
    assert set(snapshot["characters"]) == {
        "ANDREY", "ANDREY_JUNIOR", "EGOR", "KIRA", "MAKSIM", "MARINA",
        "NIKA", "OLGA", "SERGEY",
    }


@pytest.mark.skipif(_NEEDS_REAL_CANON, reason="real NCC canon root not present")
def test_real_marina_and_maksim_normalization():
    snapshot = build_snapshot(REAL_CANON)
    marina = snapshot["characters"]["MARINA"]
    maksim = snapshot["characters"]["MAKSIM"]
    assert marina["height_cm"] == 155
    assert marina["height_is_approx"] is False
    assert marina["weight_kg"] == 45
    assert "petite" in marina["height_direction"]
    assert maksim["height_cm"] == 188
    assert maksim["height_is_approx"] is False
    assert maksim["weight_kg"] is None
    assert maksim["weight_direction"] == "approximately 115 kg"
