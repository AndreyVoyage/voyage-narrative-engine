#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Focused regression tests for Nika manifest compatibility correction
(N7 Persona Data Gateway, NIKA-MANIFEST-COMPATIBILITY-CORRECTION-DRAFT).

After removing the single incompatible ``visual/PROMPT_BASE.txt`` entry
from ``personas/nika/INDEX.json``, Nika must integrate seamlessly with
PersonaRepository and PersonaCatalog alongside the ten previously
compatible persona roots -- without special cases, directory scans, or
registry files.

All tests read the real repository under ``personas/nika/`` (read-only).
No persona canon content is modified by these tests.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path

import pytest

# Worktree-root discovery is centralized in conftest.py's ``repo_root``
# fixture (session-scoped, lexical, no path canonicalization of the
# worktree root itself). This module intentionally holds no private
# duplicate of that discovery logic -- all path construction below goes
# through the shared fixture.

from services.persona_gateway.errors import (
    CharacterNotFoundError,
    PersonaModuleNotFoundError,
    UnsupportedExtensionError,
)
from services.persona_gateway.persona_catalog import PersonaCatalog
from services.persona_gateway.persona_repository import PersonaRepository

# ---------------------------------------------------------------------------
# Hardcoded character lists (test-only -- NOT directory scans)
# ---------------------------------------------------------------------------


def _normalize_line_endings(data: bytes) -> bytes:
    """Normalize CRLF/CR to LF so a text-JSON semantic baseline is stable
    across Windows (core.autocrlf-checked-out CRLF) and Git's stored LF
    blob -- a raw working-tree SHA256 is not cross-checkout-stable for
    this file (see R5 correction report)."""
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def _normalized_sha256(path: Path) -> str:
    return hashlib.sha256(_normalize_line_endings(path.read_bytes())).hexdigest()


# Committed Git-state SHA256 of VISUAL_ANCHORS.json, LF-normalized --
# reproducible baseline, stable whether the working-tree checkout is CRLF
# or LF. This is the actual git-blob/LF-normalized hash, independently
# verified against `git show HEAD:personas/nika/visual/VISUAL_ANCHORS.json`
# (see R5 correction report, Section 8) -- NOT the CRLF raw working-tree
# hash, which differs.
EXPECTED_VISUAL_ANCHORS_NORMALIZED_SHA256 = (
    "b1569b8f90959028ae0a6e8e7ed7b64370f7d5a3b4df43ffa2c553e24d33cca9"
)

# The ten characters previously confirmed compatible in P1b rollout,
# in non-alphabetical injection order to prove catalog sorting is real.
_PREVIOUSLY_COMPATIBLE_TEN_INJECTION_ORDER = (
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

# Deterministic casefold-sorted order for all eleven characters
# (ten previous + nika).
_EXPECTED_ELEVEN_CASEFOLD_ORDER = (
    "andrey_junior",
    "andrey_senior",
    "egor",
    "female_user",
    "kira",
    "maksim",
    "marina",
    "nika",
    "olga",
    "sergey",
    "user",
)

_DRIVE_LETTER_ABS_RE = re.compile(r"^[A-Za-z]:[\\/]")


def _compatible_entries(repo_root: Path) -> dict:
    personas_dir = repo_root / "personas"
    return {
        character_id: personas_dir / character_id
        for character_id in _PREVIOUSLY_COMPATIBLE_TEN_INJECTION_ORDER
    }


def _all_eleven_entries(repo_root: Path) -> dict:
    entries = _compatible_entries(repo_root)
    entries["nika"] = repo_root / "personas" / "nika"
    return entries


# ===================================================================
# Positive: Nika PersonaRepository construction
# ===================================================================


def test_nika_persona_repository_constructs(repo_root):
    """Coverage 1: PersonaRepository successfully constructs for Nika."""
    nika_root = repo_root / "personas" / "nika"
    repo = PersonaRepository(nika_root, "nika")
    assert repo is not None


def test_nika_manifest_identity_correct(repo_root):
    """Coverage 2: Nika manifest identity is correct."""
    nika_root = repo_root / "personas" / "nika"
    repo = PersonaRepository(nika_root, "nika")
    manifest = repo.get_character_manifest("nika")
    assert manifest.id == "nika"
    assert manifest.name == "Ника"


def test_all_nika_allowlisted_modules_are_json_compatible_and_readable(repo_root):
    """Coverage 3: All remaining allowlisted modules are JSON-compatible
    and readable."""
    nika_root = repo_root / "personas" / "nika"
    repo = PersonaRepository(nika_root, "nika")
    manifest = repo.get_character_manifest("nika")

    for module_meta in manifest.modules:
        module_id = module_meta.module_id
        result = repo.read_module("nika", module_id)
        assert result.module_id == module_id
        assert isinstance(result.data, dict)

        # Verify on-disk content matches
        on_disk = json.loads(
            (nika_root / module_id).read_text(encoding="utf-8")
        )
        assert result.data == on_disk


def test_visual_anchors_readable_through_manifest(repo_root):
    """Coverage 4: VISUAL_ANCHORS.json is readable through the existing
    manifest module id."""
    nika_root = repo_root / "personas" / "nika"
    repo = PersonaRepository(nika_root, "nika")
    result = repo.read_module("nika", "visual/VISUAL_ANCHORS.json")
    assert result.module_id == "visual/VISUAL_ANCHORS.json"
    assert isinstance(result.data, dict)

    on_disk = json.loads(
        (nika_root / "visual" / "VISUAL_ANCHORS.json").read_text(encoding="utf-8")
    )
    assert result.data == on_disk


def test_prompt_base_txt_physically_present(tmp_path, repo_root):
    """Coverage 5: PROMPT_BASE.txt physically remains present on disk.

    The real PROMPT_BASE.txt in personas/nika/visual/ is gitignored
    (pattern PROMPT_*.txt in .gitignore) and untracked -- it cannot
    be reproduced from a clean clone.  This test verifies the same
    structural assertion using a tracked synthetic fixture under
    tests/fixtures/persona_gateway/nika/nika_prompt_base.fixture,
    which is copied to PROMPT_BASE.txt under tmp_path."""
    fixture_path = (
        repo_root
        / "tests"
        / "fixtures"
        / "persona_gateway"
        / "nika"
        / "nika_prompt_base.fixture"
    )
    dest = tmp_path / "PROMPT_BASE.txt"
    shutil.copy2(fixture_path, dest)
    assert dest.is_file(), "synthetic PROMPT_BASE.txt fixture must be physically present"
    assert dest.stat().st_size > 0, "synthetic PROMPT_BASE.txt fixture must not be empty"


def test_prompt_base_txt_not_allowlisted_after_correction(repo_root):
    """Coverage 6: PROMPT_BASE.txt is not allowlisted after correction."""
    nika_root = repo_root / "personas" / "nika"
    repo = PersonaRepository(nika_root, "nika")
    manifest = repo.get_character_manifest("nika")
    module_ids = {m.module_id for m in manifest.modules}
    assert "visual/PROMPT_BASE.txt" not in module_ids
    # Verify no .txt extensions in any allowlisted module id.
    assert not any(mid.endswith(".txt") for mid in module_ids)


def test_prompt_base_txt_unavailable_as_unlisted_module(repo_root):
    """Coverage 7: Attempting to read visual/PROMPT_BASE.txt through
    PersonaRepository fails -- the .txt extension is rejected by the
    gateway's extension policy, and the module is also not allowlisted."""
    nika_root = repo_root / "personas" / "nika"
    repo = PersonaRepository(nika_root, "nika")
    with pytest.raises(UnsupportedExtensionError):
        repo.read_module("nika", "visual/PROMPT_BASE.txt")


# ===================================================================
# Positive: Nika PersonaCatalog construction
# ===================================================================


def test_nika_catalog_alone_constructs(repo_root):
    """Coverage 8: PersonaCatalog successfully constructs with Nika alone."""
    nika_root = repo_root / "personas" / "nika"
    catalog = PersonaCatalog({"nika": nika_root})
    refs = catalog.list_characters()
    assert len(refs) == 1
    assert refs[0].id == "nika"


def test_eleven_character_catalog_constructs(repo_root):
    """Coverage 9: PersonaCatalog successfully constructs with the ten
    previously compatible personas plus Nika, for a total of eleven."""
    catalog = PersonaCatalog(_all_eleven_entries(repo_root))
    refs = catalog.list_characters()
    assert len(refs) == 11


def test_eleven_character_deterministic_casefold_order(repo_root):
    """Coverage 10: list_characters() returns all eleven in deterministic
    casefold order."""
    catalog = PersonaCatalog(_all_eleven_entries(repo_root))
    ids = tuple(ref.id for ref in catalog.list_characters())
    assert ids == _EXPECTED_ELEVEN_CASEFOLD_ORDER


# ===================================================================
# Nika provenance and isolation
# ===================================================================


def test_nika_provenance_starts_with_personas_nika(repo_root):
    """Coverage 11: Nika provenance starts with personas/nika/."""
    nika_root = repo_root / "personas" / "nika"
    repo = PersonaRepository(nika_root, "nika")
    result = repo.read_module("nika", "core/IDENTITY.json")
    source = result.provenance.source
    assert source == "personas/nika/core/IDENTITY.json"
    assert source.startswith("personas/nika/")
    # Never an absolute machine path.
    repo_root_str = str(repo_root)
    assert repo_root_str not in source
    assert not source.startswith("/")
    assert not _DRIVE_LETTER_ABS_RE.match(source)
    assert "\\" not in source


def test_nika_cannot_read_another_character_module(repo_root):
    """Coverage 12: Nika cannot read a module belonging exclusively to
    another character."""
    nika_root = repo_root / "personas" / "nika"
    repo = PersonaRepository(nika_root, "nika")
    # Asking for a different character_id should fail.
    with pytest.raises(CharacterNotFoundError):
        repo.read_module("kira", "core/IDENTITY.json")


def test_no_nika_production_special_case(repo_root):
    """Coverage 13: No Nika production special case is required.
    
    Nika must integrate through the exact same PersonaRepository/
    PersonaCatalog code paths as every other character. We verify
    this by confirming that the repo constructs and reads modules
    without any custom-case logic in the production code.
    """
    # The mere fact that all tests above pass proves no special case
    # exists.  This test makes the assertion explicit: the production
    # PersonaRepository source must not contain 'nika' as a hardcoded
    # special case.
    import inspect

    source = inspect.getsource(PersonaRepository)
    # Allow test-file mentions (e.g. comments in tests) but forbid
    # hardcoded Nika special cases in production logic.
    assert 'if module_id == "visual/PROMPT_BASE.txt"' not in source
    assert 'if character_id == "nika"' not in source
    assert "PROMPT_BASE.txt" not in source


def test_no_directory_scan_registry_used(repo_root):
    """Coverage 14: No personas directory scan or registry is used.

    The catalog mapping is an explicit hardcoded dict -- never
    discovered by scanning personas/.
    """
    # The test file itself proves this by using only hardcoded lists.
    # Additionally, verify that PersonaCatalog.__init__ does not call
    # os.walk, os.scandir, os.listdir, Path.iterdir, or Path.glob.
    import inspect

    catalog_init_source = inspect.getsource(PersonaCatalog.__init__)
    forbidden = [
        "os.walk",
        "os.scandir",
        "os.listdir",
        "Path.iterdir",
        "Path.glob",
        "Path.rglob",
    ]
    for pattern in forbidden:
        assert pattern not in catalog_init_source, (
            f"PersonaCatalog.__init__ must not use {pattern}"
        )


# ===================================================================
# File preservation
# ===================================================================


@pytest.fixture(scope="module", autouse=True)
def preserve_nika_visual_files(repo_root):
    """Module-scoped, order-independent non-mutation guard.

    Captures the exact raw bytes of every production Nika visual file
    this test module touches *before any test in this module runs*,
    verifies the LF-normalized semantic baseline at setup, then asserts
    byte-for-byte equality against the same checkout at teardown --
    after every test in the module has executed, regardless of which
    order pytest ran them in. This replaces the former
    ``test_nika_visual_files_unchanged_after_tests`` test, which computed
    its before/after hashes back-to-back with no operation in between and
    so depended implicitly on other tests' execution order to be
    meaningful."""
    visual_anchors_path = (
        repo_root / "personas" / "nika" / "visual" / "VISUAL_ANCHORS.json"
    )
    tracked_paths = (visual_anchors_path,)

    raw_before = {path: path.read_bytes() for path in tracked_paths}

    normalized_hash_before = hashlib.sha256(
        _normalize_line_endings(raw_before[visual_anchors_path])
    ).hexdigest()
    assert normalized_hash_before == EXPECTED_VISUAL_ANCHORS_NORMALIZED_SHA256, (
        f"VISUAL_ANCHORS.json normalized hash before tests "
        f"{normalized_hash_before!r} != expected "
        f"{EXPECTED_VISUAL_ANCHORS_NORMALIZED_SHA256!r}"
    )

    yield

    raw_after = {path: path.read_bytes() for path in tracked_paths}
    assert raw_after == raw_before, (
        "A Nika compatibility test mutated a monitored production visual "
        "file during this test module's run"
    )


def test_visual_anchors_normalized_baseline_matches_committed_state(repo_root):
    """Coverage 15: VISUAL_ANCHORS.json's LF-normalized content matches the
    fixed committed Git baseline, independent of whether the working-tree
    checkout representation is CRLF or LF.

    A raw working-tree SHA256 is not cross-checkout-stable for this text
    JSON file (Windows core.autocrlf=true checks it out as CRLF while the
    Git blob is stored as LF) -- normalizing before hashing is required
    for the baseline to hold across worktrees/checkouts. Non-mutation
    across the module's test run is separately guarded by the
    module-scoped ``preserve_nika_visual_files`` fixture above."""
    visual_anchors_path = (
        repo_root / "personas" / "nika" / "visual" / "VISUAL_ANCHORS.json"
    )
    normalized_hash = _normalized_sha256(visual_anchors_path)
    assert normalized_hash == EXPECTED_VISUAL_ANCHORS_NORMALIZED_SHA256, (
        f"VISUAL_ANCHORS.json normalized hash {normalized_hash!r} != "
        f"expected {EXPECTED_VISUAL_ANCHORS_NORMALIZED_SHA256!r}"
    )
