#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Headless Character Package Management V1 tests using temporary data only."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
from dataclasses import FrozenInstanceError, fields
from pathlib import Path

import pytest

from services.character_companion.character_import import (
    PACKAGE_IMPORTED,
    PACKAGE_NO_OP_ALREADY_INSTALLED,
    TRUST_LOCAL_UNTRUSTED,
    CharacterPackageCollisionError,
    CharacterPackageIntegrityError,
    CharacterPackageManagementError,
    CharacterPackageManagementService,
    CharacterPackagePathError,
    CharacterPackageV1Error,
    InstalledCharacter,
    InstalledPackageCorruptError,
    InstalledPackageNotFoundError,
    InstalledPackageRelease,
    PackageImportResult,
)


def _canonical(payload) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _descriptor(path: str, data: bytes, normalization: str, role: str) -> dict:
    return {
        "byteLength": len(data),
        "normalization": normalization,
        "path": path,
        "required": True,
        "semanticRole": role,
        "sha256": _sha(data),
    }


def make_package(
    tmp_path: Path,
    *,
    dirname: str = "package",
    character_id: str = "alice",
    release_id: str = "v1",
    display_name: str | None = None,
    authority_class: str = "LOCAL_USER",
    package_origin: str = "LOCAL_USER_CREATION",
    payload_bytes: bytes = b"immutable payload\n",
) -> Path:
    root = tmp_path / dirname
    root.mkdir()
    metadata = {
        "authorityClass": authority_class,
        "characterId": character_id,
        "displayName": display_name or character_id.title(),
        "packageOrigin": package_origin,
        "packageSchemaVersion": "1.0",
        "releaseId": release_id,
    }
    if authority_class == "ACCEPTED_RELEASE":
        metadata["acceptedAggregateHash"] = "a" * 64
        metadata["acceptanceRecordHash"] = "b" * 64

    files = {
        "domains/core_identity.json": (
            _canonical({"contentState": "POPULATED"}),
            "CANONICAL_JSON_V1",
            "DOMAIN",
        ),
        "package.json": (
            _canonical(metadata),
            "CANONICAL_JSON_V1",
            "PACKAGE_METADATA",
        ),
        "payload.bin": (payload_bytes, "RAW", "TEST_PAYLOAD"),
    }
    descriptors = []
    for relative, (data, normalization, role) in files.items():
        destination = root.joinpath(*relative.split("/"))
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        descriptors.append(_descriptor(relative, data, normalization, role))
    manifest = {
        "files": sorted(descriptors, key=lambda item: item["path"]),
        "manifestSchemaVersion": "1.0",
    }
    (root / "manifest.json").write_bytes(_canonical(manifest))
    return root


def _service(tmp_path: Path) -> CharacterPackageManagementService:
    return CharacterPackageManagementService(tmp_path / "companion-data")


def _store(tmp_path: Path) -> Path:
    return tmp_path / "companion-data" / "character_packages"


def _manifest(root: Path) -> dict:
    return json.loads((root / "manifest.json").read_bytes().decode("utf-8"))


def _refresh_descriptor(root: Path, relative: str) -> None:
    manifest = _manifest(root)
    content = root.joinpath(*relative.split("/")).read_bytes()
    descriptor = next(item for item in manifest["files"] if item["path"] == relative)
    descriptor["sha256"] = _sha(content)
    descriptor["byteLength"] = len(content)
    (root / "manifest.json").write_bytes(_canonical(manifest))


def _file_inventory(root: Path) -> tuple[tuple[str, str, int], ...]:
    return tuple(
        sorted(
            (
                path.relative_to(root).as_posix(),
                _sha(path.read_bytes()),
                path.stat().st_size,
            )
            for path in root.rglob("*")
            if path.is_file() and not path.is_symlink()
        )
    )


def _tree_inventory(root: Path) -> tuple[tuple[str, str, int, int, str], ...]:
    if not os.path.lexists(root):
        return ()
    result: list[tuple[str, str, int, int, str]] = []
    paths = [root, *root.rglob("*")]
    for path in sorted(paths, key=lambda item: str(item.relative_to(root))):
        status = path.lstat()
        relative = "." if path == root else path.relative_to(root).as_posix()
        if stat.S_ISLNK(status.st_mode):
            kind = "link"
            digest = os.readlink(path)
        elif stat.S_ISDIR(status.st_mode):
            kind = "directory"
            digest = ""
        elif stat.S_ISREG(status.st_mode):
            kind = "file"
            digest = _sha(path.read_bytes())
        else:
            kind = "other"
            digest = ""
        result.append((relative, kind, status.st_size, status.st_mtime_ns, digest))
    return tuple(result)


def _symlink_or_skip(link: Path, target: Path, *, target_is_directory: bool) -> None:
    try:
        link.symlink_to(target, target_is_directory=target_is_directory)
    except OSError as exc:
        pytest.skip(f"symlink fixture unavailable for ordinary user: {exc}")


def test_01_absent_store_returns_empty_immutable_collection(tmp_path):
    result = _service(tmp_path).list_characters()
    assert result == ()
    assert isinstance(result, tuple)
    assert not (tmp_path / "companion-data").exists()


def test_02_existing_empty_store_returns_empty(tmp_path):
    _store(tmp_path).mkdir(parents=True)
    assert _service(tmp_path).list_characters() == ()


def test_03_single_character_single_release(tmp_path):
    service = _service(tmp_path)
    service.import_package(make_package(tmp_path))
    characters = service.list_characters()
    assert [(item.character_id, len(item.releases)) for item in characters] == [
        ("alice", 1)
    ]


def test_04_multiple_characters(tmp_path):
    service = _service(tmp_path)
    service.import_package(make_package(tmp_path, dirname="alice", character_id="alice"))
    service.import_package(make_package(tmp_path, dirname="bob", character_id="bob"))
    assert [item.character_id for item in service.list_characters()] == ["alice", "bob"]


def test_05_multiple_releases_for_one_character(tmp_path):
    service = _service(tmp_path)
    service.import_package(make_package(tmp_path, dirname="one", release_id="v1"))
    service.import_package(make_package(tmp_path, dirname="two", release_id="v2"))
    assert [item.release_id for item in service.list_characters()[0].releases] == [
        "v1",
        "v2",
    ]


def test_06_multiple_characters_with_multiple_releases(tmp_path):
    service = _service(tmp_path)
    for character in ("alice", "bob"):
        for release in ("v1", "v2"):
            service.import_package(
                make_package(
                    tmp_path,
                    dirname=f"{character}-{release}",
                    character_id=character,
                    release_id=release,
                )
            )
    assert [(item.character_id, len(item.releases)) for item in service.list_characters()] == [
        ("alice", 2),
        ("bob", 2),
    ]


def test_07_character_order_is_explicitly_lexical(tmp_path):
    service = _service(tmp_path)
    for character in ("zeta", "alpha", "middle"):
        service.import_package(
            make_package(tmp_path, dirname=character, character_id=character)
        )
    assert [item.character_id for item in service.list_characters()] == [
        "alpha",
        "middle",
        "zeta",
    ]


def test_08_release_order_is_explicitly_lexical_not_semver(tmp_path):
    service = _service(tmp_path)
    for release in ("v2", "v10", "v1"):
        service.import_package(
            make_package(tmp_path, dirname=release, release_id=release)
        )
    assert [item.release_id for item in service.list_releases("alice")] == [
        "v1",
        "v10",
        "v2",
    ]


def test_09_ordering_introduces_no_release_selection_semantics(tmp_path):
    service = _service(tmp_path)
    for release in ("v2", "v10", "v1"):
        service.import_package(
            make_package(tmp_path, dirname=release, release_id=release)
        )
    forbidden = {"latest_release", "default_release", "active_release", "preferred_release"}
    character = service.list_characters()[0]
    assert forbidden.isdisjoint({field.name for field in fields(character)})
    assert all(forbidden.isdisjoint({field.name for field in fields(item)}) for item in character.releases)


def test_10_release_exposes_exact_character_id(tmp_path):
    service = _service(tmp_path)
    service.import_package(make_package(tmp_path, character_id="alice-id"))
    assert service.list_characters()[0].releases[0].character_id == "alice-id"


def test_11_release_exposes_exact_release_id(tmp_path):
    service = _service(tmp_path)
    service.import_package(make_package(tmp_path, release_id="release-1.2"))
    assert service.list_characters()[0].releases[0].release_id == "release-1.2"


def test_12_release_exposes_exact_display_name(tmp_path):
    service = _service(tmp_path)
    service.import_package(make_package(tmp_path, display_name="Alice Display"))
    assert service.list_characters()[0].releases[0].display_name == "Alice Display"


def test_13_release_exposes_exact_manifest_hash(tmp_path):
    source = make_package(tmp_path)
    expected = _sha((source / "manifest.json").read_bytes())
    service = _service(tmp_path)
    service.import_package(source)
    assert service.get_release("alice", "v1").package_hash == expected


def test_14_release_exposes_exact_authority_class(tmp_path):
    service = _service(tmp_path)
    service.import_package(make_package(tmp_path, authority_class="LEGACY_COMPAT", package_origin="LEGACY_IMPORT"))
    assert service.get_release("alice", "v1").authority_class == "LEGACY_COMPAT"


def test_15_release_exposes_exact_package_origin(tmp_path):
    service = _service(tmp_path)
    service.import_package(make_package(tmp_path, authority_class="LEGACY_COMPAT", package_origin="LEGACY_IMPORT"))
    assert service.get_release("alice", "v1").package_origin == "LEGACY_IMPORT"


def test_16_release_trust_is_local_untrusted(tmp_path):
    service = _service(tmp_path)
    service.import_package(make_package(tmp_path))
    assert service.get_release("alice", "v1").trust_status == TRUST_LOCAL_UNTRUSTED


def test_17_accepted_authority_does_not_promote_trust(tmp_path):
    service = _service(tmp_path)
    source = make_package(
        tmp_path,
        authority_class="ACCEPTED_RELEASE",
        package_origin="ACCEPTED_AGGREGATE",
    )
    service.import_package(source)
    release = service.get_release("alice", "v1")
    assert release.authority_class == "ACCEPTED_RELEASE"
    assert release.trust_status == "LOCAL_UNTRUSTED"


def test_18_legacy_authority_does_not_promote_trust(tmp_path):
    service = _service(tmp_path)
    source = make_package(
        tmp_path,
        authority_class="LEGACY_COMPAT",
        package_origin="LEGACY_IMPORT",
    )
    service.import_package(source)
    release = service.get_release("alice", "v1")
    assert release.authority_class == "LEGACY_COMPAT"
    assert release.trust_status == "LOCAL_UNTRUSTED"


def test_19_list_releases_for_valid_character(tmp_path):
    service = _service(tmp_path)
    service.import_package(make_package(tmp_path))
    result = service.list_releases("alice")
    assert isinstance(result, tuple)
    assert [item.release_id for item in result] == ["v1"]


def test_20_get_release_for_valid_coordinate(tmp_path):
    service = _service(tmp_path)
    imported = service.import_package(make_package(tmp_path))
    release = service.get_release("alice", "v1")
    assert isinstance(release, InstalledPackageRelease)
    assert (release.character_id, release.release_id, release.package_hash) == (
        imported.character_id,
        imported.release_id,
        imported.package_hash,
    )


def test_21_missing_character_has_explicit_empty_and_not_found_semantics(tmp_path):
    service = _service(tmp_path)
    assert service.list_releases("missing") == ()
    with pytest.raises(InstalledPackageNotFoundError, match="not found"):
        service.get_release("missing", "v1")


def test_22_missing_release_raises_not_found(tmp_path):
    service = _service(tmp_path)
    service.import_package(make_package(tmp_path))
    with pytest.raises(InstalledPackageNotFoundError, match="not found"):
        service.get_release("alice", "missing")


def test_23_unsafe_requested_character_preserves_s6_path_error(tmp_path):
    service = _service(tmp_path)
    with pytest.raises(CharacterPackagePathError):
        service.list_releases("../alice")
    with pytest.raises(CharacterPackagePathError):
        service.get_release("../alice", "v1")


def test_24_unsafe_requested_release_preserves_s6_path_error(tmp_path):
    with pytest.raises(CharacterPackagePathError):
        _service(tmp_path).get_release("alice", "../v1")


def test_25_tampered_installed_package_is_corrupt(tmp_path):
    service = _service(tmp_path)
    installed = service.import_package(make_package(tmp_path)).installed_path
    (installed / "payload.bin").write_bytes(b"tampered")
    with pytest.raises(InstalledPackageCorruptError) as error:
        service.list_characters()
    assert isinstance(error.value.__cause__, CharacterPackageIntegrityError)


def test_26_missing_installed_package_file_is_corrupt(tmp_path):
    service = _service(tmp_path)
    installed = service.import_package(make_package(tmp_path)).installed_path
    (installed / "payload.bin").unlink()
    with pytest.raises(InstalledPackageCorruptError):
        service.get_release("alice", "v1")


def test_27_extra_installed_package_file_is_corrupt(tmp_path):
    service = _service(tmp_path)
    installed = service.import_package(make_package(tmp_path)).installed_path
    (installed / "extra.txt").write_bytes(b"unexpected")
    with pytest.raises(InstalledPackageCorruptError):
        service.list_releases("alice")


def test_28_corrupt_installed_manifest_is_rejected(tmp_path):
    service = _service(tmp_path)
    installed = service.import_package(make_package(tmp_path)).installed_path
    (installed / "manifest.json").write_bytes(b"{not-json")
    with pytest.raises(InstalledPackageCorruptError):
        service.get_release("alice", "v1")


def test_29_directory_identity_metadata_mismatch_is_rejected(tmp_path):
    service = _service(tmp_path)
    installed = service.import_package(make_package(tmp_path)).installed_path
    metadata = json.loads((installed / "package.json").read_text(encoding="utf-8"))
    metadata["characterId"] = "bob"
    (installed / "package.json").write_bytes(_canonical(metadata))
    _refresh_descriptor(installed, "package.json")
    with pytest.raises(InstalledPackageCorruptError, match="corrupt") as error:
        service.get_release("alice", "v1")
    assert isinstance(error.value.__cause__, CharacterPackageIntegrityError)


def test_30_symlinked_installed_release_fails_closed_where_supported(tmp_path):
    source = make_package(tmp_path)
    character = _store(tmp_path) / "alice"
    character.mkdir(parents=True)
    _symlink_or_skip(character / "v1", source, target_is_directory=True)
    with pytest.raises(InstalledPackageCorruptError, match="symbolic link"):
        _service(tmp_path).list_characters()


def test_31_exact_s6_staging_directory_is_excluded(tmp_path):
    staging = _store(tmp_path) / (".staging-" + "0123456789abcdef" * 2)
    staging.mkdir(parents=True)
    (staging / "incomplete.bin").write_bytes(b"staged")
    assert _service(tmp_path).list_characters() == ()


def test_32_unknown_dot_directory_is_not_hidden_as_staging(tmp_path):
    (_store(tmp_path) / ".staging-not-a-uuid").mkdir(parents=True)
    with pytest.raises(InstalledPackageCorruptError, match="unsafe character"):
        _service(tmp_path).list_characters()


def test_33_unexpected_root_file_fails_closed(tmp_path):
    _store(tmp_path).mkdir(parents=True)
    (_store(tmp_path) / "unexpected.txt").write_text("unexpected", encoding="utf-8")
    with pytest.raises(InstalledPackageCorruptError, match="not a directory"):
        _service(tmp_path).list_characters()


def test_34_unsafe_character_directory_fails_closed(tmp_path):
    (_store(tmp_path) / "unsafe character").mkdir(parents=True)
    with pytest.raises(InstalledPackageCorruptError, match="unsafe character"):
        _service(tmp_path).list_characters()


def test_35_unsafe_release_directory_fails_closed(tmp_path):
    (_store(tmp_path) / "alice" / "unsafe release").mkdir(parents=True)
    with pytest.raises(InstalledPackageCorruptError, match="unsafe release"):
        _service(tmp_path).list_characters()


def test_36_empty_character_parent_is_ignored_as_s6_publish_residue(tmp_path):
    (_store(tmp_path) / "alice").mkdir(parents=True)
    service = _service(tmp_path)
    assert service.list_characters() == ()
    assert service.list_releases("alice") == ()


def test_37_management_import_installs_via_s6(tmp_path):
    result = _service(tmp_path).import_package(make_package(tmp_path))
    assert isinstance(result, PackageImportResult)
    assert result.installed_path == _store(tmp_path) / "alice" / "v1"
    assert result.installed_path.is_dir()


def test_38_management_import_preserves_imported_status(tmp_path):
    assert _service(tmp_path).import_package(make_package(tmp_path)).status == PACKAGE_IMPORTED


def test_39_management_import_preserves_idempotent_no_op(tmp_path):
    source = make_package(tmp_path)
    service = _service(tmp_path)
    first = service.import_package(source)
    second = service.import_package(source)
    assert first.status == PACKAGE_IMPORTED
    assert second.status == PACKAGE_NO_OP_ALREADY_INSTALLED


def test_40_management_import_preserves_collision_failure(tmp_path):
    service = _service(tmp_path)
    service.import_package(make_package(tmp_path, dirname="first", payload_bytes=b"first"))
    conflicting = make_package(tmp_path, dirname="second", payload_bytes=b"second")
    with pytest.raises(CharacterPackageCollisionError):
        service.import_package(conflicting)


def test_41_expected_package_hash_is_delegated_and_enforced(tmp_path):
    source = make_package(tmp_path)
    expected = _sha((source / "manifest.json").read_bytes())
    service = _service(tmp_path)
    assert service.import_package(source, expected_package_hash=expected).package_hash == expected

    another = make_package(tmp_path, dirname="another", release_id="v2")
    with pytest.raises(CharacterPackageIntegrityError, match="packageHash"):
        service.import_package(another, expected_package_hash="0" * 64)


def test_42_source_package_remains_unchanged(tmp_path):
    source = make_package(tmp_path)
    before = _tree_inventory(source)
    _service(tmp_path).import_package(source)
    assert _tree_inventory(source) == before


def test_43_installed_package_is_byte_identical_to_s6_materialization(tmp_path):
    source = make_package(tmp_path)
    before = _file_inventory(source)
    result = _service(tmp_path).import_package(source)
    assert _file_inventory(result.installed_path) == before


def test_44_import_creates_no_s7_metadata_or_index(tmp_path):
    source = make_package(tmp_path)
    result = _service(tmp_path).import_package(source)
    assert _file_inventory(result.installed_path) == _file_inventory(source)
    forbidden = {
        "registry.json",
        "index.json",
        "installed.json",
        "active.json",
        "preferences.json",
        "metadata.json",
        "trust.json",
    }
    actual_names = {path.name.casefold() for path in _store(tmp_path).rglob("*")}
    assert forbidden.isdisjoint(actual_names)


def test_import_method_delegates_directly_and_returns_same_object(tmp_path, monkeypatch):
    service = _service(tmp_path)
    sentinel = object()
    calls = []

    def delegated(package_root, *, expected_package_hash=None):
        calls.append((package_root, expected_package_hash))
        return sentinel

    monkeypatch.setattr(service._importer, "import_package", delegated)
    source = tmp_path / "delegated-source"
    assert service.import_package(source, expected_package_hash="a" * 64) is sentinel
    assert calls == [(source, "a" * 64)]


def test_45_reconstructed_service_discovers_without_index(tmp_path):
    source = make_package(tmp_path)
    _service(tmp_path).import_package(source)
    reconstructed = _service(tmp_path)
    assert reconstructed.get_release("alice", "v1").release_id == "v1"
    assert not (_store(tmp_path) / "index.json").exists()


def test_46_multiple_releases_survive_service_reconstruction(tmp_path):
    service = _service(tmp_path)
    for release in ("v1", "v2"):
        service.import_package(make_package(tmp_path, dirname=release, release_id=release))
    reconstructed = _service(tmp_path)
    assert [item.release_id for item in reconstructed.list_releases("alice")] == [
        "v1",
        "v2",
    ]


def test_47_trust_is_derived_without_persisted_trust_metadata(tmp_path):
    _service(tmp_path).import_package(make_package(tmp_path))
    reconstructed = _service(tmp_path)
    assert reconstructed.get_release("alice", "v1").trust_status == "LOCAL_UNTRUSTED"
    assert not any(path.name.casefold() == "trust.json" for path in _store(tmp_path).rglob("*"))


def test_48_list_characters_does_not_mutate_filesystem(tmp_path):
    service = _service(tmp_path)
    service.import_package(make_package(tmp_path))
    before = _tree_inventory(tmp_path / "companion-data")
    service.list_characters()
    assert _tree_inventory(tmp_path / "companion-data") == before


def test_49_list_releases_does_not_mutate_filesystem(tmp_path):
    service = _service(tmp_path)
    service.import_package(make_package(tmp_path))
    before = _tree_inventory(tmp_path / "companion-data")
    service.list_releases("alice")
    assert _tree_inventory(tmp_path / "companion-data") == before


def test_50_get_release_does_not_mutate_filesystem(tmp_path):
    service = _service(tmp_path)
    service.import_package(make_package(tmp_path))
    before = _tree_inventory(tmp_path / "companion-data")
    service.get_release("alice", "v1")
    assert _tree_inventory(tmp_path / "companion-data") == before


def test_51_no_active_latest_preferred_default_fields_or_methods(tmp_path):
    forbidden = {
        "active",
        "canonical",
        "current_release",
        "default",
        "default_release",
        "is_active",
        "is_default",
        "is_latest",
        "is_preferred",
        "latest_release",
        "newest_release",
        "preferred",
        "preferred_release",
        "trusted",
    }
    assert forbidden.isdisjoint({field.name for field in fields(InstalledPackageRelease)})
    assert forbidden.isdisjoint({field.name for field in fields(InstalledCharacter)})
    service = _service(tmp_path)
    assert all(not hasattr(service, name) for name in forbidden)
    assert all(
        not hasattr(service, name)
        for name in (
            "activate_release",
            "delete_release",
            "remove_release",
            "rollback",
            "select_release",
            "set_active",
            "set_default",
            "set_preferred",
            "uninstall",
            "update",
        )
    )


def test_52_no_runtime_or_catalog_state_is_created(tmp_path):
    service = _service(tmp_path)
    service.import_package(make_package(tmp_path))
    service.list_characters()
    data_root = tmp_path / "companion-data"
    assert [path.name for path in data_root.iterdir()] == ["character_packages"]


def test_management_errors_have_explicit_hierarchy():
    assert issubclass(CharacterPackageManagementError, CharacterPackageV1Error)
    assert issubclass(InstalledPackageCorruptError, CharacterPackageManagementError)
    assert issubclass(InstalledPackageNotFoundError, CharacterPackageManagementError)


def test_management_value_objects_are_frozen_and_nested_collection_is_tuple(tmp_path):
    service = _service(tmp_path)
    service.import_package(make_package(tmp_path))
    character = service.list_characters()[0]
    assert isinstance(character, InstalledCharacter)
    assert isinstance(character.releases, tuple)
    with pytest.raises(FrozenInstanceError):
        character.character_id = "bob"
    with pytest.raises(FrozenInstanceError):
        character.releases[0].release_id = "v2"


def test_list_characters_uses_s6_load_installed_for_every_release(tmp_path, monkeypatch):
    service = _service(tmp_path)
    for release in ("v1", "v2"):
        service.import_package(make_package(tmp_path, dirname=release, release_id=release))
    original = service._importer.load_installed
    calls = []

    def tracked(character_id, release_id, *, expected_package_hash=None):
        calls.append((character_id, release_id, expected_package_hash))
        return original(
            character_id,
            release_id,
            expected_package_hash=expected_package_hash,
        )

    monkeypatch.setattr(service._importer, "load_installed", tracked)
    service.list_characters()
    assert calls == [("alice", "v1", None), ("alice", "v2", None)]


def test_exact_staging_name_as_symlink_fails_closed_where_supported(tmp_path):
    target = tmp_path / "outside-staging"
    target.mkdir()
    _store(tmp_path).mkdir(parents=True)
    link = _store(tmp_path) / (".staging-" + "0" * 32)
    _symlink_or_skip(link, target, target_is_directory=True)
    with pytest.raises(InstalledPackageCorruptError, match="symbolic link"):
        _service(tmp_path).list_characters()


def test_uppercase_hex_staging_near_match_is_not_excluded(tmp_path):
    (_store(tmp_path) / (".staging-" + "A" * 32)).mkdir(parents=True)
    with pytest.raises(InstalledPackageCorruptError, match="unsafe character"):
        _service(tmp_path).list_characters()


def test_package_store_symlink_fails_closed_where_supported(tmp_path):
    data_root = tmp_path / "companion-data"
    data_root.mkdir()
    outside = tmp_path / "outside-store"
    outside.mkdir()
    _symlink_or_skip(data_root / "character_packages", outside, target_is_directory=True)
    with pytest.raises(InstalledPackageCorruptError, match="symbolic link"):
        CharacterPackageManagementService(data_root).list_characters()


def test_safe_release_file_fails_closed(tmp_path):
    release = _store(tmp_path) / "alice" / "v1"
    release.parent.mkdir(parents=True)
    release.write_bytes(b"not a package directory")
    with pytest.raises(InstalledPackageCorruptError, match="not a directory"):
        _service(tmp_path).list_characters()


def test_get_release_classifies_existing_release_file_as_corrupt(tmp_path):
    release = _store(tmp_path) / "alice" / "v1"
    release.parent.mkdir(parents=True)
    release.write_bytes(b"not a package directory")
    with pytest.raises(InstalledPackageCorruptError, match="not a directory"):
        _service(tmp_path).get_release("alice", "v1")


def test_missing_store_file_shape_is_corrupt_not_absent(tmp_path):
    store = _store(tmp_path)
    store.parent.mkdir(parents=True)
    store.write_bytes(b"not a directory")
    with pytest.raises(InstalledPackageCorruptError, match="not a directory"):
        _service(tmp_path).list_characters()
