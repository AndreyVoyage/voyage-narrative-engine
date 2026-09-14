#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Character Package V1 verifier/importer tests.  All writes stay in tmp_path."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path

import pytest

import services.character_companion.character_import.package_importer as package_importer_module
from services.character_companion.character_import import (
    PACKAGE_IMPORTED,
    PACKAGE_NO_OP_ALREADY_INSTALLED,
    TRUST_LOCAL_UNTRUSTED,
    CharacterImportService,
    CharacterPackageCollisionError,
    CharacterPackageContractError,
    CharacterPackageImportService,
    CharacterPackageIntegrityError,
    CharacterPackagePathError,
    PackageFileDescriptor,
    SnapshotStore,
    VerifiedCharacterPackage,
    verify_character_package_v1,
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
    authority_class: str = "LOCAL_USER",
    package_origin: str = "LOCAL_USER_CREATION",
    payload_bytes: bytes = b"immutable payload\n",
) -> Path:
    root = tmp_path / dirname
    root.mkdir()
    metadata = {
        "authorityClass": authority_class,
        "characterId": character_id,
        "displayName": character_id.title(),
        "packageOrigin": package_origin,
        "packageSchemaVersion": "1.0",
        "releaseId": release_id,
    }
    files = {
        "domains/core_identity.json": (_canonical({"contentState": "POPULATED"}), "CANONICAL_JSON_V1", "DOMAIN"),
        "package.json": (_canonical(metadata), "CANONICAL_JSON_V1", "PACKAGE_METADATA"),
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


def _manifest(root: Path) -> dict:
    return json.loads((root / "manifest.json").read_bytes().decode("utf-8"))


def _write_manifest(root: Path, payload: dict) -> None:
    (root / "manifest.json").write_bytes(_canonical(payload))


def _entry(payload: dict, path: str) -> dict:
    return next(item for item in payload["files"] if item["path"] == path)


def _refresh_descriptor(root: Path, path: str) -> None:
    payload = _manifest(root)
    data = root.joinpath(*path.split("/")).read_bytes()
    descriptor = _entry(payload, path)
    descriptor["sha256"] = _sha(data)
    descriptor["byteLength"] = len(data)
    _write_manifest(root, payload)


def _set_descriptor_path(root: Path, old: str, new: str) -> None:
    payload = _manifest(root)
    _entry(payload, old)["path"] = new
    payload["files"].sort(key=lambda item: item["path"])
    _write_manifest(root, payload)


def _inventory(root: Path) -> tuple[tuple[str, str, int], ...]:
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


def _service(tmp_path: Path) -> CharacterPackageImportService:
    return CharacterPackageImportService(tmp_path / "companion-data")


def test_01_valid_package_verifies(tmp_path):
    verified = verify_character_package_v1(make_package(tmp_path))
    assert isinstance(verified, VerifiedCharacterPackage)
    assert verified.character_id == "alice"
    assert verified.release_id == "v1"
    assert verified.display_name == "Alice"
    assert verified.authority_class == "LOCAL_USER"
    assert verified.package_origin == "LOCAL_USER_CREATION"
    assert all(isinstance(item, PackageFileDescriptor) for item in verified.files)


def test_02_package_hash_is_raw_manifest_sha256(tmp_path):
    root = make_package(tmp_path)
    assert verify_character_package_v1(root).package_hash == _sha(
        (root / "manifest.json").read_bytes()
    )


def test_03_correct_expected_package_hash_passes(tmp_path):
    root = make_package(tmp_path)
    expected = _sha((root / "manifest.json").read_bytes())
    assert verify_character_package_v1(root, expected_package_hash=expected).package_hash == expected


def test_04_incorrect_expected_package_hash_fails(tmp_path):
    root = make_package(tmp_path)
    with pytest.raises(CharacterPackageIntegrityError, match="packageHash"):
        verify_character_package_v1(root, expected_package_hash="0" * 64)


def test_05_valid_package_imports_to_parallel_store(tmp_path):
    source = make_package(tmp_path)
    result = _service(tmp_path).import_package(source)
    assert result.status == PACKAGE_IMPORTED
    assert result.installed_path == (
        tmp_path / "companion-data" / "character_packages" / "alice" / "v1"
    )
    assert result.installed_path.is_dir()


def test_06_installed_tree_is_byte_identical(tmp_path):
    source = make_package(tmp_path)
    before = _inventory(source)
    result = _service(tmp_path).import_package(source)
    assert _inventory(result.installed_path) == before


def test_07_source_tree_remains_byte_identical(tmp_path):
    source = make_package(tmp_path)
    before = _inventory(source)
    _service(tmp_path).import_package(source)
    assert _inventory(source) == before


def test_08_installed_package_reverifies(tmp_path):
    source = make_package(tmp_path)
    service = _service(tmp_path)
    result = service.import_package(source)
    installed = service.load_installed("alice", "v1", expected_package_hash=result.package_hash)
    assert installed.package_hash == result.package_hash


def test_09_second_identical_import_is_no_op(tmp_path):
    source = make_package(tmp_path)
    service = _service(tmp_path)
    first = service.import_package(source)
    second = service.import_package(source)
    assert first.status == PACKAGE_IMPORTED
    assert second.status == PACKAGE_NO_OP_ALREADY_INSTALLED


def test_10_idempotent_import_does_not_rewrite_installed_bytes(tmp_path):
    source = make_package(tmp_path)
    service = _service(tmp_path)
    installed = service.import_package(source).installed_path
    before = _inventory(installed)
    service.import_package(source)
    assert _inventory(installed) == before


def test_11_release_identity_hash_collision_fails(tmp_path):
    first = make_package(tmp_path, dirname="first", payload_bytes=b"first")
    second = make_package(tmp_path, dirname="second", payload_bytes=b"second")
    service = _service(tmp_path)
    service.import_package(first)
    with pytest.raises(CharacterPackageCollisionError, match="different packageHash"):
        service.import_package(second)


def test_12_collision_preserves_existing_package(tmp_path):
    first = make_package(tmp_path, dirname="first", payload_bytes=b"first")
    second = make_package(tmp_path, dirname="second", payload_bytes=b"second")
    service = _service(tmp_path)
    installed = service.import_package(first).installed_path
    before = _inventory(installed)
    with pytest.raises(CharacterPackageCollisionError):
        service.import_package(second)
    assert _inventory(installed) == before


def test_13_two_releases_for_one_character_coexist(tmp_path):
    one = make_package(tmp_path, dirname="one", release_id="v1", payload_bytes=b"one")
    two = make_package(tmp_path, dirname="two", release_id="v2", payload_bytes=b"two")
    service = _service(tmp_path)
    first = service.import_package(one)
    second = service.import_package(two)
    assert first.installed_path.is_dir() and second.installed_path.is_dir()
    assert first.installed_path != second.installed_path


def test_14_two_characters_coexist(tmp_path):
    alice = make_package(tmp_path, dirname="alice-src", character_id="alice")
    bob = make_package(tmp_path, dirname="bob-src", character_id="bob")
    service = _service(tmp_path)
    assert service.import_package(alice).installed_path.is_dir()
    assert service.import_package(bob).installed_path.is_dir()


def test_15_tampered_file_rejected_before_store_mutation(tmp_path):
    source = make_package(tmp_path)
    (source / "payload.bin").write_bytes(b"tampered")
    data_root = tmp_path / "companion-data"
    with pytest.raises(CharacterPackageIntegrityError):
        CharacterPackageImportService(data_root).import_package(source)
    assert not (data_root / "character_packages").exists()


def test_16_descriptor_sha_mismatch_rejected(tmp_path):
    source = make_package(tmp_path)
    payload = _manifest(source)
    _entry(payload, "payload.bin")["sha256"] = "0" * 64
    _write_manifest(source, payload)
    with pytest.raises(CharacterPackageIntegrityError, match="sha256"):
        verify_character_package_v1(source)


def test_17_descriptor_byte_length_mismatch_rejected(tmp_path):
    source = make_package(tmp_path)
    payload = _manifest(source)
    _entry(payload, "payload.bin")["byteLength"] += 1
    _write_manifest(source, payload)
    with pytest.raises(CharacterPackageIntegrityError, match="byteLength"):
        verify_character_package_v1(source)


def test_18_missing_listed_file_rejected(tmp_path):
    source = make_package(tmp_path)
    (source / "payload.bin").unlink()
    with pytest.raises(CharacterPackageIntegrityError, match="missing"):
        verify_character_package_v1(source)


def test_19_unlisted_extra_file_rejected(tmp_path):
    source = make_package(tmp_path)
    (source / "extra.txt").write_bytes(b"extra")
    with pytest.raises(CharacterPackageIntegrityError, match="extra"):
        verify_character_package_v1(source)


def test_20_manifest_cannot_list_itself(tmp_path):
    source = make_package(tmp_path)
    payload = _manifest(source)
    payload["files"].append(_descriptor("manifest.json", b"not relevant", "RAW", "MANIFEST"))
    payload["files"].sort(key=lambda item: item["path"])
    _write_manifest(source, payload)
    with pytest.raises(CharacterPackageContractError, match="must not list itself"):
        verify_character_package_v1(source)


@pytest.mark.parametrize("unsafe", ["../payload.bin", "/payload.bin", "C:/payload.bin", "dir\\payload.bin"])
def test_21_to_24_unsafe_descriptor_paths_rejected(tmp_path, unsafe):
    source = make_package(tmp_path)
    _set_descriptor_path(source, "payload.bin", unsafe)
    with pytest.raises(CharacterPackagePathError):
        verify_character_package_v1(source)


def test_25_duplicate_descriptor_path_rejected(tmp_path):
    source = make_package(tmp_path)
    payload = _manifest(source)
    payload["files"].append(dict(_entry(payload, "payload.bin")))
    payload["files"].sort(key=lambda item: item["path"])
    _write_manifest(source, payload)
    with pytest.raises(CharacterPackageContractError, match="duplicate descriptor"):
        verify_character_package_v1(source)


def test_26_case_fold_descriptor_collision_rejected(tmp_path):
    source = make_package(tmp_path)
    payload = _manifest(source)
    duplicate = dict(_entry(payload, "payload.bin"))
    duplicate["path"] = "PAYLOAD.bin"
    payload["files"].append(duplicate)
    payload["files"].sort(key=lambda item: item["path"])
    _write_manifest(source, payload)
    with pytest.raises(CharacterPackagePathError, match="case-fold"):
        verify_character_package_v1(source)


def test_27_malformed_manifest_json_rejected(tmp_path):
    source = make_package(tmp_path)
    (source / "manifest.json").write_bytes(b"{not json")
    with pytest.raises(CharacterPackageContractError, match="JSON"):
        verify_character_package_v1(source)


def test_28_duplicate_manifest_object_keys_rejected(tmp_path):
    source = make_package(tmp_path)
    (source / "manifest.json").write_bytes(
        b'{"files": [], "files": [], "manifestSchemaVersion": "1.0"}'
    )
    with pytest.raises(CharacterPackageContractError, match="duplicate JSON object key"):
        verify_character_package_v1(source)


def test_29_noncanonical_manifest_bytes_rejected(tmp_path):
    source = make_package(tmp_path)
    (source / "manifest.json").write_text(
        json.dumps(_manifest(source), indent=2), encoding="utf-8"
    )
    with pytest.raises(CharacterPackageContractError, match="not canonical"):
        verify_character_package_v1(source)


def test_30_noncanonical_canonical_json_file_rejected(tmp_path):
    source = make_package(tmp_path)
    path = source / "domains" / "core_identity.json"
    path.write_bytes(b'{"z": 1, "a": 2}')
    _refresh_descriptor(source, "domains/core_identity.json")
    with pytest.raises(CharacterPackageContractError, match="not canonical"):
        verify_character_package_v1(source)


def test_31_unknown_normalization_rejected(tmp_path):
    source = make_package(tmp_path)
    payload = _manifest(source)
    _entry(payload, "payload.bin")["normalization"] = "FUTURE_MODE"
    _write_manifest(source, payload)
    with pytest.raises(CharacterPackageContractError, match="normalization is unknown"):
        verify_character_package_v1(source)


def _fail_staged_verification(monkeypatch):
    original = package_importer_module.verify_character_package_v1
    calls = 0

    def fail_second(root, *, expected_package_hash=None):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise CharacterPackageIntegrityError("simulated staged verification failure")
        return original(root, expected_package_hash=expected_package_hash)

    monkeypatch.setattr(package_importer_module, "verify_character_package_v1", fail_second)


def test_32_staging_residue_removed_after_failed_install(tmp_path, monkeypatch):
    source = make_package(tmp_path)
    _fail_staged_verification(monkeypatch)
    service = _service(tmp_path)
    with pytest.raises(CharacterPackageIntegrityError, match="simulated"):
        service.import_package(source)
    store = tmp_path / "companion-data" / "character_packages"
    assert store.is_dir()
    assert not any(path.name.startswith(".staging-") for path in store.iterdir())


def test_33_failed_import_preserves_unrelated_store_state(tmp_path, monkeypatch):
    source = make_package(tmp_path)
    unrelated = tmp_path / "companion-data" / "character_packages" / "other" / "keep.bin"
    unrelated.parent.mkdir(parents=True)
    unrelated.write_bytes(b"keep exactly")
    before = unrelated.read_bytes()
    _fail_staged_verification(monkeypatch)
    with pytest.raises(CharacterPackageIntegrityError):
        _service(tmp_path).import_package(source)
    assert unrelated.read_bytes() == before


def test_34_installed_package_survives_source_deletion(tmp_path):
    source = make_package(tmp_path)
    service = _service(tmp_path)
    result = service.import_package(source)
    shutil.rmtree(source)
    assert service.load_installed("alice", "v1").package_hash == result.package_hash


def test_35_import_trust_is_local_untrusted(tmp_path):
    result = _service(tmp_path).import_package(make_package(tmp_path))
    assert result.trust_status == TRUST_LOCAL_UNTRUSTED


def test_36_legacy_compat_is_not_promoted(tmp_path):
    source = make_package(
        tmp_path,
        authority_class="LEGACY_COMPAT",
        package_origin="LEGACY_IMPORT",
    )
    verified = verify_character_package_v1(source)
    result = _service(tmp_path).import_package(source)
    assert verified.authority_class == "LEGACY_COMPAT"
    assert result.trust_status == "LOCAL_UNTRUSTED"
    assert "ACCEPTED" not in result.trust_status


def test_37_legacy_character_import_exports_remain_available():
    assert CharacterImportService is not None
    assert SnapshotStore is not None


@pytest.mark.parametrize(
    "field,value",
    [("characterId", "../alice"), ("releaseId", "v1/next")],
)
def test_38_39_unsafe_package_identity_rejected(tmp_path, field, value):
    source = make_package(tmp_path)
    metadata = json.loads((source / "package.json").read_text(encoding="utf-8"))
    metadata[field] = value
    (source / "package.json").write_bytes(_canonical(metadata))
    _refresh_descriptor(source, "package.json")
    with pytest.raises(CharacterPackagePathError):
        verify_character_package_v1(source)


def _symlink_or_skip(link: Path, target: Path, *, target_is_directory: bool) -> None:
    try:
        link.symlink_to(target, target_is_directory=target_is_directory)
    except OSError as exc:
        pytest.skip(f"symlink fixture unavailable for ordinary user: {exc}")


def test_40_source_root_symlink_rejected_where_supported(tmp_path):
    source = make_package(tmp_path)
    link = tmp_path / "package-link"
    _symlink_or_skip(link, source, target_is_directory=True)
    with pytest.raises(CharacterPackagePathError, match="root.*symbolic link"):
        verify_character_package_v1(link)


def test_41_nested_package_symlink_rejected_where_supported(tmp_path):
    source = make_package(tmp_path)
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"outside")
    link = source / "nested-link.bin"
    _symlink_or_skip(link, outside, target_is_directory=False)
    with pytest.raises(CharacterPackagePathError, match="symbolic link"):
        verify_character_package_v1(source)


def test_package_json_duplicate_keys_rejected(tmp_path):
    source = make_package(tmp_path)
    raw = (
        b'{"authorityClass": "LOCAL_USER", "characterId": "alice", '
        b'"characterId": "mallory", "displayName": "Alice", '
        b'"packageOrigin": "LOCAL_USER_CREATION", "packageSchemaVersion": "1.0", '
        b'"releaseId": "v1"}'
    )
    (source / "package.json").write_bytes(raw)
    _refresh_descriptor(source, "package.json")
    with pytest.raises(CharacterPackageContractError, match="duplicate JSON object key"):
        verify_character_package_v1(source)


@pytest.mark.parametrize("unsafe", ["CON/file.bin", "name./file.bin", "a//file.bin", "a/./file.bin"])
def test_additional_windows_and_segment_path_forms_rejected(tmp_path, unsafe):
    source = make_package(tmp_path)
    _set_descriptor_path(source, "payload.bin", unsafe)
    with pytest.raises(CharacterPackagePathError):
        verify_character_package_v1(source)


def test_manifest_view_is_immutable(tmp_path):
    verified = verify_character_package_v1(make_package(tmp_path))
    with pytest.raises(TypeError):
        verified.manifest["files"] = ()


def test_load_installed_rejects_package_under_wrong_store_identity(tmp_path):
    source = make_package(tmp_path, character_id="bob", release_id="v2")
    data_root = tmp_path / "companion-data"
    wrong_path = data_root / "character_packages" / "alice" / "v1"
    wrong_path.parent.mkdir(parents=True)
    shutil.copytree(source, wrong_path)
    with pytest.raises(CharacterPackageIntegrityError, match="store path"):
        CharacterPackageImportService(data_root).load_installed("alice", "v1")
