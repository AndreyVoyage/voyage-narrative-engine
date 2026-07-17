#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for services/persona_gateway/persona_repository.py.

All persona/manifest/module fixtures are synthetic, built under
pytest's ``tmp_path`` via ``build_persona_root`` (see conftest.py). No
real Kira canon is read or copied by this test file.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from services.persona_gateway.errors import (
    CharacterNotFoundError,
    ManifestIntegrityError,
    ManifestNotFoundError,
    ManifestParseError,
    ModuleEncodingError,
    ModuleParseError,
    ModuleSizeLimitError,
    PathSecurityError,
    PersonaModuleNotFoundError,
    UnsupportedExtensionError,
)
from services.persona_gateway.persona_repository import PersonaRepository


# ---------------------------------------------------------------------
# Manifest / construction
# ---------------------------------------------------------------------

def test_valid_injected_kira_like_manifest_constructs(build_persona_root):
    root = build_persona_root()
    repo = PersonaRepository(root, "kira")
    manifest = repo.get_character_manifest("kira")
    assert manifest.id == "kira"
    assert manifest.name == "Кира"
    assert len(manifest.modules) == 3


def test_list_characters_returns_singleton_from_manifest(build_persona_root):
    root = build_persona_root(character_id="kira", character_name="Кира")
    repo = PersonaRepository(root, "kira")
    refs = repo.list_characters()
    assert refs == (repo.list_characters()[0],)
    assert len(refs) == 1
    assert refs[0].id == "kira"
    assert refs[0].name == "Кира"


def test_wrong_character_id_raises_character_not_found(build_persona_root):
    root = build_persona_root(character_id="kira")
    with pytest.raises(CharacterNotFoundError):
        PersonaRepository(root, "someone_else")


def test_missing_index_json_raises_manifest_not_found(tmp_path):
    empty_root = tmp_path / "empty_persona_root"
    empty_root.mkdir()
    with pytest.raises(ManifestNotFoundError):
        PersonaRepository(empty_root, "kira")


def test_invalid_manifest_json_raises_manifest_parse_error(tmp_path, write_text_file):
    root = tmp_path / "broken_root"
    write_text_file(root / "INDEX.json", "{ this is not valid json ")
    with pytest.raises(ManifestParseError):
        PersonaRepository(root, "kira")


def test_manifest_structure_failure_missing_modules_key(tmp_path, write_json_file):
    root = tmp_path / "structure_fail_root"
    write_json_file(root / "INDEX.json", {"id": "kira", "name": "Кира"})
    with pytest.raises(ManifestIntegrityError):
        PersonaRepository(root, "kira")


def test_manifest_structure_failure_missing_id(tmp_path, write_json_file):
    root = tmp_path / "structure_fail_root2"
    write_json_file(root / "INDEX.json", {"name": "Кира", "modules": {}})
    with pytest.raises(ManifestIntegrityError):
        PersonaRepository(root, "kira")


def test_manifest_entry_limit_enforced(build_persona_root):
    modules = {f"levels/L{i}.json": {"version": "1.0.0"} for i in range(200)}
    content = {mod: {"level_id": mod} for mod in modules}
    root = build_persona_root(modules=modules, module_content=content)
    with pytest.raises(ManifestIntegrityError):
        PersonaRepository(root, "kira", max_manifest_entries=128)


def test_manifest_entry_limit_allows_exactly_at_cap(build_persona_root):
    modules = {f"levels/L{i}.json": {"version": "1.0.0"} for i in range(128)}
    content = {mod: {"level_id": mod} for mod in modules}
    root = build_persona_root(modules=modules, module_content=content)
    repo = PersonaRepository(root, "kira", max_manifest_entries=128)
    assert len(repo.get_character_manifest("kira").modules) == 128


def test_duplicate_manifest_keys_in_raw_json_rejected(tmp_path, write_text_file):
    # A literal duplicate top-level key in the raw JSON text -- json.loads
    # normally silently collapses this; our object_pairs_hook must reject
    # it explicitly.
    raw_text = (
        '{"id": "kira", "name": "Кира", "modules": {'
        '"core/IDENTITY.json": {"version": "1.0.0"}, '
        '"core/IDENTITY.json": {"version": "2.0.0"}'
        '}}'
    )
    root = tmp_path / "dup_key_root"
    write_text_file(root / "INDEX.json", raw_text)
    write_text_file(root / "core" / "IDENTITY.json", "{}")
    with pytest.raises(ManifestIntegrityError):
        PersonaRepository(root, "kira")


def test_manifest_module_path_escaping_root_rejected(tmp_path, write_json_file):
    root = tmp_path / "escape_root"
    write_json_file(
        root / "INDEX.json",
        {
            "id": "kira",
            "name": "Кира",
            "modules": {"../outside.json": {"version": "1.0.0"}},
        },
    )
    with pytest.raises(PathSecurityError):
        PersonaRepository(root, "kira")


# ---------------------------------------------------------------------
# read_module -- happy path & provenance
# ---------------------------------------------------------------------

def test_valid_allowlisted_module_reads_successfully(build_persona_root):
    root = build_persona_root()
    repo = PersonaRepository(root, "kira")
    result = repo.read_module("kira", "core/IDENTITY.json")
    assert result.module_id == "core/IDENTITY.json"
    assert isinstance(result.data, dict)
    assert result.data["id"] == "kira_identity"


def test_provenance_fields_present_and_correct(build_persona_root):
    root = build_persona_root()
    repo = PersonaRepository(root, "kira")
    result = repo.read_module("kira", "core/IDENTITY.json")
    prov = result.provenance
    assert prov.source == "personas/kira/core/IDENTITY.json"
    assert prov.schema is None
    assert prov.read_only is True
    assert prov.version == "1.0.0"
    assert len(prov.content_hash) == 64
    int(prov.content_hash, 16)  # must be valid lowercase hex
    assert prov.content_hash == prov.content_hash.lower()


def test_hash_stability_across_repeated_reads(build_persona_root):
    root = build_persona_root()
    repo = PersonaRepository(root, "kira")
    first = repo.read_module("kira", "core/IDENTITY.json")
    second = repo.read_module("kira", "core/IDENTITY.json")
    assert first.provenance.content_hash == second.provenance.content_hash


def test_read_module_wrong_character_id_raises(build_persona_root):
    root = build_persona_root()
    repo = PersonaRepository(root, "kira")
    with pytest.raises(CharacterNotFoundError):
        repo.read_module("not_kira", "core/IDENTITY.json")


# ---------------------------------------------------------------------
# read_module -- security / allowlist rejections
# ---------------------------------------------------------------------

def test_unknown_module_id_raises_persona_module_not_found(build_persona_root):
    root = build_persona_root()
    repo = PersonaRepository(root, "kira")
    with pytest.raises(PersonaModuleNotFoundError):
        repo.read_module("kira", "not/in/manifest.json")


def test_path_traversal_module_id_raises_path_security_error(build_persona_root):
    root = build_persona_root()
    repo = PersonaRepository(root, "kira")
    with pytest.raises(PathSecurityError):
        repo.read_module("kira", "../../secret")


def test_absolute_module_id_raises_path_security_error(build_persona_root):
    root = build_persona_root()
    repo = PersonaRepository(root, "kira")
    with pytest.raises(PathSecurityError):
        repo.read_module("kira", "/etc/passwd")


def test_windows_drive_absolute_module_id_raises_path_security_error(build_persona_root):
    root = build_persona_root()
    repo = PersonaRepository(root, "kira")
    with pytest.raises(PathSecurityError):
        repo.read_module("kira", "C:/secret.json")


def test_unsupported_extension_raises(build_persona_root):
    modules = {
        "core/IDENTITY.json": {"version": "1.0.0"},
        "psychology/BASE.json": {"version": "1.0.0"},
        "levels/U2-A.json": {"version": "1.0.0"},
        "notes/README.txt": {"version": "1.0.0"},
    }
    content = {
        "core/IDENTITY.json": {"id": "kira_identity"},
        "psychology/BASE.json": {"module_id": "base"},
        "levels/U2-A.json": {"level_id": "U2-A"},
    }
    root = build_persona_root(modules=modules, module_content=content)
    (root / "notes").mkdir(parents=True, exist_ok=True)
    (root / "notes" / "README.txt").write_text("not json", encoding="utf-8")

    with pytest.raises(UnsupportedExtensionError):
        PersonaRepository(root, "kira")


def test_module_size_limit_enforced(build_persona_root, write_text_file):
    root = build_persona_root()
    big_path = root / "core" / "IDENTITY.json"
    payload = '{"id": "kira_identity", "padding": "' + ("x" * 300) + '"}'
    write_text_file(big_path, payload)
    repo = PersonaRepository(root, "kira", max_module_bytes=50)
    with pytest.raises(ModuleSizeLimitError):
        repo.read_module("kira", "core/IDENTITY.json")


def test_missing_allowlisted_file_raises_persona_module_not_found(build_persona_root):
    root = build_persona_root()
    (root / "core" / "IDENTITY.json").unlink()
    repo = PersonaRepository(root, "kira")
    with pytest.raises(PersonaModuleNotFoundError):
        repo.read_module("kira", "core/IDENTITY.json")


def test_invalid_utf8_module_raises_module_encoding_error(build_persona_root, write_bytes_file):
    root = build_persona_root()
    write_bytes_file(root / "core" / "IDENTITY.json", b"\xff\xfe\x00\x01broken")
    repo = PersonaRepository(root, "kira")
    with pytest.raises(ModuleEncodingError):
        repo.read_module("kira", "core/IDENTITY.json")


def test_malformed_json_module_raises_module_parse_error(build_persona_root, write_text_file):
    root = build_persona_root()
    write_text_file(root / "core" / "IDENTITY.json", "{ not valid json !!")
    repo = PersonaRepository(root, "kira")
    with pytest.raises(ModuleParseError):
        repo.read_module("kira", "core/IDENTITY.json")


def test_unlisted_file_on_disk_is_ignored(build_persona_root):
    root = build_persona_root(unlisted_files={"levels/ALGORITHMS.json": {"secret": "unlisted"}})
    repo = PersonaRepository(root, "kira")
    with pytest.raises(PersonaModuleNotFoundError):
        repo.read_module("kira", "levels/ALGORITHMS.json")


def test_algorithms_style_unlisted_file_present_on_disk_but_ignored(build_persona_root):
    # Mirrors the real repo's proven case: personas/kira/levels/ALGORITHMS.json
    # exists and is tracked by git, but is NOT a key in INDEX.json["modules"].
    root = build_persona_root(unlisted_files={"levels/ALGORITHMS.json": {"tag": "unlisted"}})
    assert (root / "levels" / "ALGORITHMS.json").is_file()
    repo = PersonaRepository(root, "kira")
    manifest = repo.get_character_manifest("kira")
    module_ids = {m.module_id for m in manifest.modules}
    assert "levels/ALGORITHMS.json" not in module_ids
    with pytest.raises(PersonaModuleNotFoundError):
        repo.read_module("kira", "levels/ALGORITHMS.json")


# ---------------------------------------------------------------------
# Symlink rejection
# ---------------------------------------------------------------------

def test_symlink_root_rejected(tmp_path, build_persona_root, attempt_symlink, patch_is_symlink):
    real_root = build_persona_root(root_name="real_persona_root")
    link_root = tmp_path / "linked_persona_root"

    created = attempt_symlink(link_root, real_root, target_is_directory=True)
    if not created:
        # Windows without Developer Mode/elevation commonly refuses symlink
        # creation for an unprivileged process -- fall back to mocking
        # Path.is_symlink() so the production rejection logic is still
        # exercised faithfully.
        link_root = real_root
        patch_is_symlink(link_root)

    with pytest.raises(PathSecurityError):
        PersonaRepository(link_root, "kira")


def test_symlink_manifest_rejected(tmp_path, build_persona_root, attempt_symlink, patch_is_symlink):
    root = build_persona_root()
    real_manifest = root / "INDEX.json"
    link_manifest = tmp_path / "linked_index.json"

    created = attempt_symlink(link_manifest, real_manifest, target_is_directory=False)
    if created:
        real_manifest.unlink()
        link_manifest.rename(real_manifest)
        # renaming a symlink preserves its symlink-ness on POSIX; on some
        # platforms this may materialize the link differently, so verify:
        if not real_manifest.is_symlink():
            created = False

    if not created:
        patch_is_symlink(root / "INDEX.json")

    with pytest.raises(PathSecurityError):
        PersonaRepository(root, "kira")


def test_symlink_module_rejected(tmp_path, build_persona_root, attempt_symlink, patch_is_symlink):
    # Module-level symlink checks happen lazily, inside read_module() for
    # the specific requested module -- not eagerly for all 61 modules at
    # construction time (construction only eagerly checks the persona
    # root and the manifest file itself).
    root = build_persona_root()
    real_module = root / "core" / "IDENTITY.json"
    link_module = tmp_path / "linked_identity.json"

    created = attempt_symlink(link_module, real_module, target_is_directory=False)
    if created:
        real_module.unlink()
        link_module.rename(real_module)
        if not real_module.is_symlink():
            created = False

    if not created:
        patch_is_symlink(root / "core" / "IDENTITY.json")

    repo = PersonaRepository(root, "kira")
    with pytest.raises(PathSecurityError):
        repo.read_module("kira", "core/IDENTITY.json")


# ---------------------------------------------------------------------
# Path containment / duplicate resolved paths
# ---------------------------------------------------------------------

def test_duplicate_resolved_module_path_rejected(tmp_path, write_json_file):
    root = tmp_path / "dup_resolved_root"
    write_json_file(
        root / "INDEX.json",
        {
            "id": "kira",
            "name": "Кира",
            "modules": {
                "core/IDENTITY.json": {"version": "1.0.0"},
                "core/./IDENTITY.json": {"version": "1.0.0"},
            },
        },
    )
    write_json_file(root / "core" / "IDENTITY.json", {"id": "kira_identity"})
    with pytest.raises((ManifestIntegrityError, PathSecurityError)):
        PersonaRepository(root, "kira")


def test_outside_root_resolution_rejected_for_absolute_style_manifest_entry(tmp_path, write_json_file):
    root = tmp_path / "escape_root2"
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    write_json_file(outside_dir / "secret.json", {"leak": True})
    write_json_file(
        root / "INDEX.json",
        {
            "id": "kira",
            "name": "Кира",
            "modules": {"../outside/secret.json": {"version": "1.0.0"}},
        },
    )
    with pytest.raises(PathSecurityError):
        PersonaRepository(root, "kira")


# ---------------------------------------------------------------------
# No directory scan / no write side effects
# ---------------------------------------------------------------------

def test_construction_never_scans_directories(build_persona_root, monkeypatch):
    root = build_persona_root()

    def _forbidden(*args, **kwargs):
        raise AssertionError("PersonaRepository must not scan directories")

    monkeypatch.setattr(os, "walk", _forbidden)
    monkeypatch.setattr(os, "scandir", _forbidden)
    original_iterdir = Path.iterdir

    def _forbidden_iterdir(self):
        raise AssertionError("PersonaRepository must not call Path.iterdir")

    monkeypatch.setattr(Path, "iterdir", _forbidden_iterdir)
    try:
        repo = PersonaRepository(root, "kira")
        repo.read_module("kira", "core/IDENTITY.json")
        repo.list_characters()
        repo.get_character_manifest("kira")
    finally:
        monkeypatch.setattr(Path, "iterdir", original_iterdir)


def test_no_filesystem_write_side_effects(build_persona_root):
    root = build_persona_root()

    def snapshot_tree():
        entries = {}
        for path in sorted(root.rglob("*")):
            if path.is_file():
                entries[str(path.relative_to(root))] = path.read_bytes()
        return entries

    before = snapshot_tree()
    repo = PersonaRepository(root, "kira")
    repo.list_characters()
    repo.get_character_manifest("kira")
    repo.read_module("kira", "core/IDENTITY.json")
    with pytest.raises(PersonaModuleNotFoundError):
        repo.read_module("kira", "not/in/manifest.json")
    after = snapshot_tree()

    assert before == after
    assert before.keys() == after.keys()
