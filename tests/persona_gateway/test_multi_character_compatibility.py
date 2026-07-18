#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Real-repository multi-character compatibility tests for PersonaCatalog
(N7 Persona Data Gateway, P1b Option A).

Per the P1b multi-character compatibility read-only preflight
(``N7_P1B_MULTI_CHARACTER_COMPATIBILITY_READONLY_PREFLIGHT_2026-07-18.md``),
10 of the 11 persona roots under ``personas/`` that carry a valid
``INDEX.json`` are fully compatible with the current manifest/extension
contract: ``andrey_junior``, ``andrey_senior``, ``egor``, ``female_user``,
``kira``, ``maksim``, ``marina``, ``olga``, ``sergey``, ``user``.
``nika`` is excluded from this rollout because its manifest allowlists
``visual/PROMPT_BASE.txt`` -- a real, on-disk ``.txt`` module id, which
violates the current ``.json``-only extension policy. This file proves
that exclusion is real (an injected ``nika`` root fails construction) --
it does not repair, skip, or normalize ``nika`` in any way.

These tests read the real repository under ``personas/`` (read-only) but
never scan it: every character mapping below is an explicit, hardcoded
dict of ``character_id -> persona_root``, exactly mirroring how a real
caller would inject a static catalog. ``personas/visual_prompts/`` (no
``INDEX.json``) and the top-level legacy monolithic ``*_MODULE_*.json``
files are explicitly never treated as characters.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

from services.persona_gateway.errors import (
    ManifestNotFoundError,
    PersonaModuleNotFoundError,
    UnsupportedExtensionError,
)
from services.persona_gateway.persona_catalog import PersonaCatalog

# Explicit, hardcoded (test-only) list -- NOT discovered by scanning
# personas/. Order is deliberately NOT alphabetical, to prove the
# catalog's own casefold-based sort is real and not an insertion-order
# coincidence.
_COMPATIBLE_IDS_INJECTION_ORDER = (
    "user",
    "sergey",
    "olga",
    "marina",
    "maksim",
    "kira",
    "female_user",
    "egor",
    "andrey_senior",
    "andrey_junior",
)

_DRIVE_LETTER_ABS_RE = re.compile(r"^[A-Za-z]:[\\/]")

_EXPECTED_CASEFOLD_ORDER = (
    "andrey_junior",
    "andrey_senior",
    "egor",
    "female_user",
    "kira",
    "maksim",
    "marina",
    "olga",
    "sergey",
    "user",
)


def _compatible_entries(repo_root: Path) -> dict:
    personas_dir = repo_root / "personas"
    return {
        character_id: personas_dir / character_id
        for character_id in _COMPATIBLE_IDS_INJECTION_ORDER
    }


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------
# Ten compatible real personas
# ---------------------------------------------------------------------

def test_ten_compatible_characters_construct_together(repo_root):
    catalog = PersonaCatalog(_compatible_entries(repo_root))
    ids = [ref.id for ref in catalog.list_characters()]
    assert len(ids) == 10
    assert set(ids) == set(_EXPECTED_CASEFOLD_ORDER)


def test_deterministic_order_matches_casefold_sort(repo_root):
    catalog = PersonaCatalog(_compatible_entries(repo_root))
    ids = tuple(ref.id for ref in catalog.list_characters())
    assert ids == _EXPECTED_CASEFOLD_ORDER


def test_every_manifest_id_equals_injected_id(repo_root):
    catalog = PersonaCatalog(_compatible_entries(repo_root))
    for character_id in _EXPECTED_CASEFOLD_ORDER:
        manifest = catalog.get_character_manifest(character_id)
        assert manifest.id == character_id


def test_allowlisted_module_readable_for_every_character(repo_root):
    catalog = PersonaCatalog(_compatible_entries(repo_root))
    personas_dir = repo_root / "personas"
    for character_id in _EXPECTED_CASEFOLD_ORDER:
        result = catalog.read_module(character_id, "core/IDENTITY.json")
        assert result.module_id == "core/IDENTITY.json"
        assert isinstance(result.data, dict)

        on_disk = json.loads(
            (personas_dir / character_id / "core" / "IDENTITY.json").read_text(
                encoding="utf-8"
            )
        )
        assert result.data == on_disk


def test_provenance_source_is_character_specific_and_relative(repo_root):
    catalog = PersonaCatalog(_compatible_entries(repo_root))
    repo_root_str = str(repo_root)
    for character_id in _EXPECTED_CASEFOLD_ORDER:
        result = catalog.read_module(character_id, "core/IDENTITY.json")
        source = result.provenance.source
        assert source == f"personas/{character_id}/core/IDENTITY.json"
        assert source.startswith(f"personas/{character_id}/")
        # Never an absolute machine path.
        assert repo_root_str not in source
        assert not source.startswith("/")
        assert not _DRIVE_LETTER_ABS_RE.match(source)
        assert "\\" not in source


def test_cross_character_identical_module_names_remain_isolated(repo_root):
    catalog = PersonaCatalog(_compatible_entries(repo_root))
    kira_result = catalog.read_module("kira", "core/IDENTITY.json")
    marina_result = catalog.read_module("marina", "core/IDENTITY.json")

    assert kira_result.provenance.source == "personas/kira/core/IDENTITY.json"
    assert marina_result.provenance.source == "personas/marina/core/IDENTITY.json"
    assert kira_result.provenance.content_hash != marina_result.provenance.content_hash
    assert kira_result.data != marina_result.data


def test_unlisted_file_present_on_disk_remains_unavailable(repo_root):
    # personas/andrey_junior/levels/ALGORITHMS.json exists on disk but is
    # not a key in INDEX.json["modules"] -- must remain unreadable.
    catalog = PersonaCatalog(_compatible_entries(repo_root))
    on_disk = repo_root / "personas" / "andrey_junior" / "levels" / "ALGORITHMS.json"
    assert on_disk.is_file()
    manifest = catalog.get_character_manifest("andrey_junior")
    module_ids = {m.module_id for m in manifest.modules}
    assert "levels/ALGORITHMS.json" not in module_ids
    with pytest.raises(PersonaModuleNotFoundError):
        catalog.read_module("andrey_junior", "levels/ALGORITHMS.json")


def test_no_repository_file_changes(repo_root):
    personas_dir = repo_root / "personas"
    watched = []
    for character_id in _EXPECTED_CASEFOLD_ORDER:
        watched.append(personas_dir / character_id / "INDEX.json")
        watched.append(personas_dir / character_id / "core" / "IDENTITY.json")

    before = {str(p): _hash_file(p) for p in watched}

    catalog = PersonaCatalog(_compatible_entries(repo_root))
    for character_id in _EXPECTED_CASEFOLD_ORDER:
        catalog.get_character_manifest(character_id)
        catalog.read_module(character_id, "core/IDENTITY.json")

    after = {str(p): _hash_file(p) for p in watched}
    assert before == after


# ---------------------------------------------------------------------
# Nika negative test -- must actually fail, not be worked around
# ---------------------------------------------------------------------

def test_nika_injected_alone_fails_unsupported_extension(repo_root):
    nika_root = repo_root / "personas" / "nika"
    assert (nika_root / "visual" / "PROMPT_BASE.txt").is_file()
    with pytest.raises(UnsupportedExtensionError):
        PersonaCatalog({"nika": nika_root})


def test_nika_injected_alongside_compatible_characters_aborts_whole_catalog(repo_root):
    entries = _compatible_entries(repo_root)
    entries["nika"] = repo_root / "personas" / "nika"
    with pytest.raises(UnsupportedExtensionError):
        PersonaCatalog(entries)


# ---------------------------------------------------------------------
# Explicit exclusions -- visual_prompts / legacy monoliths
# ---------------------------------------------------------------------

def test_visual_prompts_directory_is_not_a_valid_character_root(repo_root):
    # personas/visual_prompts has no INDEX.json -- not a character.
    visual_prompts_root = repo_root / "personas" / "visual_prompts"
    assert visual_prompts_root.is_dir()
    assert not (visual_prompts_root / "INDEX.json").is_file()
    with pytest.raises(ManifestNotFoundError):
        PersonaCatalog({"visual_prompts": visual_prompts_root})


def test_legacy_monolithic_json_file_is_not_a_valid_character_root(repo_root):
    # personas/KIRA_MODULE_v15.json is a legacy top-level monolith file,
    # not a modular persona directory with its own INDEX.json.
    legacy_file = repo_root / "personas" / "KIRA_MODULE_v15.json"
    assert legacy_file.is_file()
    with pytest.raises(ManifestNotFoundError):
        PersonaCatalog({"kira": legacy_file})
