#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Adversarial S8A tests for the read-only Package V1 runtime adapter."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import fields
from pathlib import Path

import pytest

import services.character_companion.package_runtime as package_runtime_module
from services.character_companion.character_import import verify_character_package_v1
from services.character_companion.package_runtime import (
    CRP_IMPORT_SOURCE_KIND,
    ExactPackageRuntimeBinding,
    PACKAGE_RUNTIME_ADAPTER_ID,
    PACKAGE_RUNTIME_ADAPTER_VERSION,
    PackageRuntimeError,
    load_runtime_character_definition,
)
from services.character_core.dimensions import DimensionSet
from services.character_lab.grounding import render_accepted_grounding
from services.character_runtime.definition import RuntimeCharacterDefinition
from services.crp_authoring.acceptance_store import acceptance_record_from_jsonable
from services.crp_authoring.auditor_checks import compute_package_hash
from services.crp_authoring.candidate_rehydration import rehydrate_candidate_package


REAL_PACKAGE_ENV = "KIRA_CURRENT_PACKAGE_V1_ROOT"
EXPECTED_CHARACTER_ID = "kira"
EXPECTED_RELEASE_ID = "crp-import-v1"
EXPECTED_PACKAGE_HASH = (
    "66cda3f4046f2ab8823532ac4e65475ce0df75cc171e3222fda67e5d39514fd8"
)
EXPECTED_ACCEPTED_SEMANTIC_HASH = (
    "e26f83dafa26e61af82f29b654b592300c8f3f7bd295d07bd4d2b6527ae3eebd"
)
EXPECTED_GROUNDING_LENGTH = 29965

REPO_ROOT = Path(__file__).resolve().parents[2]
CURRENT_ACCEPTANCE = REPO_ROOT / "accepted" / "kira" / "ACCEPTANCE.json"
CURRENT_CANDIDATE = REPO_ROOT / "accepted" / "kira" / "source_candidate.json"
CURRENT_DIMENSIONS = (
    REPO_ROOT
    / "character_packages"
    / "kira"
    / "extensions"
    / "dimension_semantics"
    / "v1.json"
)


def _canonical(payload) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@pytest.fixture(scope="session")
def real_package_root() -> Path:
    value = os.environ.get(REAL_PACKAGE_ENV)
    if not value:
        pytest.fail(
            f"{REAL_PACKAGE_ENV} is required for the focused real-package S8A tests"
        )
    root = Path(value)
    assert root.is_dir(), f"real package root does not exist: {root}"
    assert _sha256((root / "manifest.json").read_bytes()) == EXPECTED_PACKAGE_HASH
    return root


@pytest.fixture(scope="session")
def current_oracle():
    candidate_raw = json.loads(CURRENT_CANDIDATE.read_text(encoding="utf-8"))
    acceptance_raw = json.loads(CURRENT_ACCEPTANCE.read_text(encoding="utf-8"))
    dimensions_raw = json.loads(CURRENT_DIMENSIONS.read_text(encoding="utf-8"))
    return {
        "candidate": rehydrate_candidate_package(candidate_raw),
        "acceptance": acceptance_record_from_jsonable(
            acceptance_raw["acceptance_record"]
        ),
        "dimensions_raw": dimensions_raw,
        "dimension_set": DimensionSet.from_dicts(dimensions_raw["dimensions"]),
    }


def _binding(
    root: Path,
    *,
    character_id: str = EXPECTED_CHARACTER_ID,
    release_id: str = EXPECTED_RELEASE_ID,
    package_hash: str | None = None,
) -> ExactPackageRuntimeBinding:
    return ExactPackageRuntimeBinding(
        package_root=root,
        expected_character_id=character_id,
        expected_release_id=release_id,
        expected_package_hash=(
            package_hash
            if package_hash is not None
            else _sha256((root / "manifest.json").read_bytes())
        ),
    )


def _copy_package(real_package_root: Path, tmp_path: Path, name: str = "package") -> Path:
    destination = tmp_path / name
    shutil.copytree(real_package_root, destination)
    return destination


def _manifest(root: Path) -> dict:
    return json.loads((root / "manifest.json").read_text(encoding="utf-8"))


def _write_manifest(root: Path, payload: dict) -> None:
    (root / "manifest.json").write_bytes(_canonical(payload))


def _descriptor(manifest: dict, relative_path: str) -> dict:
    return next(item for item in manifest["files"] if item["path"] == relative_path)


def _rewrite_json(root: Path, relative_path: str, mutate) -> None:
    target = root.joinpath(*relative_path.split("/"))
    payload = json.loads(target.read_text(encoding="utf-8"))
    mutate(payload)
    data = _canonical(payload)
    target.write_bytes(data)
    manifest = _manifest(root)
    item = _descriptor(manifest, relative_path)
    item["byteLength"] = len(data)
    item["sha256"] = _sha256(data)
    _write_manifest(root, manifest)


def _remove_manifested_file(root: Path, relative_path: str) -> None:
    root.joinpath(*relative_path.split("/")).unlink()
    manifest = _manifest(root)
    manifest["files"] = [
        item for item in manifest["files"] if item["path"] != relative_path
    ]
    _write_manifest(root, manifest)


def _tree_snapshot(root: Path) -> tuple[tuple[str, int, str], ...]:
    return tuple(
        sorted(
            (
                path.relative_to(root).as_posix(),
                path.stat().st_size,
                _sha256(path.read_bytes()),
            )
            for path in root.rglob("*")
            if path.is_file() and not path.is_symlink()
        )
    )


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def test_real_package_exact_identity_authority_and_source_kind(real_package_root):
    definition = load_runtime_character_definition(_binding(real_package_root))

    assert isinstance(definition, RuntimeCharacterDefinition)
    assert definition.character_id == EXPECTED_CHARACTER_ID
    assert definition.display_name == "Кира — актуальная CRP"
    assert definition.source_kind is CRP_IMPORT_SOURCE_KIND
    assert definition.package_identity.release_id == EXPECTED_RELEASE_ID
    assert definition.package_identity.package_hash == EXPECTED_PACKAGE_HASH
    assert definition.package_identity.authority_class == "LEGACY_COMPAT"
    assert definition.package_identity.package_origin == "LEGACY_IMPORT"
    assert definition.package_identity.authority_class != "ACCEPTED_RELEASE"
    assert definition.adapter_identity.adapter_id == PACKAGE_RUNTIME_ADAPTER_ID
    assert definition.adapter_identity.adapter_version == PACKAGE_RUNTIME_ADAPTER_VERSION


def test_existing_s6_verifier_is_reused_before_and_after_reads(
    real_package_root, monkeypatch
):
    original = package_runtime_module.verify_character_package_v1
    calls = []

    def recording_verifier(*args, **kwargs):
        calls.append((args, kwargs))
        return original(*args, **kwargs)

    monkeypatch.setattr(
        package_runtime_module, "verify_character_package_v1", recording_verifier
    )
    definition = load_runtime_character_definition(_binding(real_package_root))

    assert definition.package_identity.package_hash == EXPECTED_PACKAGE_HASH
    assert len(calls) == 2
    assert all(
        call_kwargs["expected_package_hash"] == EXPECTED_PACKAGE_HASH
        for _call_args, call_kwargs in calls
    )


def test_source_candidate_and_acceptance_are_strict_and_truthful(real_package_root):
    definition = load_runtime_character_definition(_binding(real_package_root))

    assert definition.candidate.subject_id == EXPECTED_CHARACTER_ID
    assert definition.candidate.status.value == "DRAFT"
    assert definition.source_acceptance.decision.value == "HUMAN_APPROVED"
    assert definition.source_acceptance.acceptance_id == "kira-accepted-package-001"
    assert definition.source_acceptance.package_id == definition.candidate.package_id
    assert (
        definition.source_acceptance.package_version
        == definition.candidate.package_version
    )
    assert definition.accepted_semantic_hash == EXPECTED_ACCEPTED_SEMANTIC_HASH
    assert compute_package_hash(definition.candidate) == EXPECTED_ACCEPTED_SEMANTIC_HASH


def test_dimension_semantics_and_empty_visual_truth_are_preserved(real_package_root):
    definition = load_runtime_character_definition(_binding(real_package_root))
    dimensions = definition.dimension_semantics

    assert dimensions.character_id == EXPECTED_CHARACTER_ID
    assert dimensions.extension_type == "dimension_semantics"
    assert dimensions.extension_version == 1
    assert dimensions.target_accepted_source_hash == EXPECTED_ACCEPTED_SEMANTIC_HASH
    assert {(item.domain.value, item.id) for item in dimensions.dimension_set} == {
        ("RELATIONSHIP", "trust"),
        ("PSYCHOLOGY", "stress"),
    }
    assert definition.visual_identity_state == "EXPLICITLY_EMPTY"


def test_definition_and_hash_are_deterministic_and_path_free(real_package_root):
    first = load_runtime_character_definition(_binding(real_package_root))
    second = load_runtime_character_definition(_binding(real_package_root))

    assert first == second
    assert first.runtime_definition_hash == second.runtime_definition_hash
    assert len(first.runtime_definition_hash) == 64
    assert str(real_package_root) not in repr(first)


def test_definition_is_portable_between_two_package_roots(real_package_root, tmp_path):
    first_root = _copy_package(real_package_root, tmp_path, "first-root")
    second_root = _copy_package(real_package_root, tmp_path, "unrelated-second-root")

    first = load_runtime_character_definition(_binding(first_root))
    second = load_runtime_character_definition(_binding(second_root))

    assert first == second
    assert first.runtime_definition_hash == second.runtime_definition_hash


def test_current_kira_candidate_acceptance_dimensions_and_grounding_exact_parity(
    real_package_root, current_oracle
):
    definition = load_runtime_character_definition(_binding(real_package_root))
    package_grounding = render_accepted_grounding(definition.candidate)
    current_grounding = render_accepted_grounding(current_oracle["candidate"])

    assert definition.candidate == current_oracle["candidate"]
    assert definition.source_acceptance == current_oracle["acceptance"]
    assert definition.dimension_semantics.dimension_set == current_oracle["dimension_set"]
    raw = current_oracle["dimensions_raw"]
    assert definition.dimension_semantics.extension_type == raw["extension_type"]
    assert definition.dimension_semantics.extension_version == raw["extension_version"]
    assert (
        definition.dimension_semantics.target_accepted_source_hash
        == raw["target_accepted_source_hash"]
    )
    assert package_grounding == current_grounding
    assert len(package_grounding) == EXPECTED_GROUNDING_LENGTH


def test_package_only_operation_blocks_repository_kira_and_legacy_reads(
    real_package_root, current_oracle, monkeypatch
):
    original_read_bytes = Path.read_bytes
    original_read_text = Path.read_text
    forbidden_roots = (
        REPO_ROOT / "accepted" / "kira",
        REPO_ROOT / "character_packages" / "kira" / "extensions",
        REPO_ROOT / "personas" / "kira",
    )

    def reject_forbidden(path: Path) -> None:
        resolved = path.resolve()
        if any(_is_within(resolved, root) for root in forbidden_roots):
            raise AssertionError(f"repository-local Kira source read: {resolved}")
        if "legacy-compat-v1" in str(resolved).lower():
            raise AssertionError(f"old legacy package read: {resolved}")

    def guarded_read_bytes(path: Path):
        reject_forbidden(path)
        return original_read_bytes(path)

    def guarded_read_text(path: Path, *args, **kwargs):
        reject_forbidden(path)
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_bytes", guarded_read_bytes)
    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    definition = load_runtime_character_definition(_binding(real_package_root))

    assert definition.candidate == current_oracle["candidate"]
    assert definition.source_acceptance == current_oracle["acceptance"]
    assert definition.dimension_semantics.dimension_set == current_oracle["dimension_set"]


def test_adapter_reads_no_runtime_memory_production_or_external_tree(
    real_package_root, monkeypatch
):
    original_read_bytes = Path.read_bytes
    original_read_text = Path.read_text
    reads = []

    def recording_read_bytes(path: Path):
        reads.append(path.resolve())
        return original_read_bytes(path)

    def recording_read_text(path: Path, *args, **kwargs):
        reads.append(path.resolve())
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_bytes", recording_read_bytes)
    monkeypatch.setattr(Path, "read_text", recording_read_text)
    load_runtime_character_definition(_binding(real_package_root))

    assert reads
    assert all(_is_within(path, real_package_root) for path in reads)
    assert not any("runtime_memory.sqlite3" in str(path) for path in reads)
    assert not any("runtime_state.sqlite3" in str(path) for path in reads)


def test_loading_does_not_write_or_mutate_real_package(real_package_root):
    before = _tree_snapshot(real_package_root)
    load_runtime_character_definition(_binding(real_package_root))
    after = _tree_snapshot(real_package_root)

    assert after == before


def test_definition_has_no_runtime_state_session_policy_or_snapshot_binding():
    names = {item.name for item in fields(RuntimeCharacterDefinition)}
    forbidden = {
        "memory",
        "runtime_memory",
        "runtime_state",
        "session",
        "session_id",
        "selection",
        "policy",
        "snapshot",
        "snapshot_id",
        "relationship_delta",
        "trust_value",
        "stress_value",
    }

    assert names.isdisjoint(forbidden)


def test_product_adapter_contains_no_machine_or_authoring_source_path():
    source = Path(package_runtime_module.__file__).read_text(encoding="utf-8")
    lowered = source.lower().replace("\\", "/")

    assert "local_storage" not in lowered
    assert "accepted/kira" not in lowered
    assert "character_packages/kira" not in lowered
    assert "legacy-compat-v1" not in lowered
    assert "appdata/local/kiracompanion" not in lowered


@pytest.mark.parametrize(
    ("field", "wrong"),
    (
        ("package_hash", "0" * 64),
        ("release_id", "wrong-release"),
        ("character_id", "wrong-character"),
    ),
)
def test_wrong_exact_expected_identity_fails_closed(
    real_package_root, field, wrong
):
    values = {
        "package_hash": EXPECTED_PACKAGE_HASH,
        "release_id": EXPECTED_RELEASE_ID,
        "character_id": EXPECTED_CHARACTER_ID,
    }
    values[field] = wrong

    with pytest.raises(PackageRuntimeError):
        load_runtime_character_definition(
            _binding(
                real_package_root,
                character_id=values["character_id"],
                release_id=values["release_id"],
                package_hash=values["package_hash"],
            )
        )


def test_tampered_package_file_fails_s6_integrity(real_package_root, tmp_path):
    root = _copy_package(real_package_root, tmp_path)
    candidate_path = root / "provenance" / "source_candidate.json"
    candidate_path.write_bytes(candidate_path.read_bytes() + b" ")

    with pytest.raises(PackageRuntimeError, match="verification failed"):
        load_runtime_character_definition(
            _binding(root, package_hash=EXPECTED_PACKAGE_HASH)
        )


@pytest.mark.parametrize(
    "relative_path",
    (
        "provenance/source_candidate.json",
        "provenance/source_acceptance.json",
        "extensions/dimension_semantics/v1.json",
    ),
)
def test_missing_required_crp_supplemental_fails_after_structural_verification(
    real_package_root, tmp_path, relative_path
):
    root = _copy_package(real_package_root, tmp_path)
    _remove_manifested_file(root, relative_path)
    package_hash = _sha256((root / "manifest.json").read_bytes())
    verify_character_package_v1(root, expected_package_hash=package_hash)

    with pytest.raises(PackageRuntimeError, match="profile requires"):
        load_runtime_character_definition(_binding(root))


def test_candidate_subject_mismatch_with_source_acceptance_fails_closed(
    real_package_root, tmp_path
):
    root = _copy_package(real_package_root, tmp_path)
    _rewrite_json(
        root,
        "provenance/source_candidate.json",
        lambda payload: payload.__setitem__("subject_id", "other"),
    )

    with pytest.raises(PackageRuntimeError, match="acceptance subject"):
        load_runtime_character_definition(_binding(root))


def test_source_acceptance_must_be_human_approved(real_package_root, tmp_path):
    root = _copy_package(real_package_root, tmp_path)
    _rewrite_json(
        root,
        "provenance/source_acceptance.json",
        lambda payload: payload["acceptance_record"].__setitem__(
            "decision", "REJECTED"
        ),
    )

    with pytest.raises(PackageRuntimeError, match="not HUMAN_APPROVED"):
        load_runtime_character_definition(_binding(root))


def test_source_acceptance_subject_mismatch_fails_closed(real_package_root, tmp_path):
    root = _copy_package(real_package_root, tmp_path)
    _rewrite_json(
        root,
        "provenance/source_acceptance.json",
        lambda payload: payload["acceptance_record"].__setitem__(
            "subject_id", "other"
        ),
    )

    with pytest.raises(PackageRuntimeError, match="acceptance subject"):
        load_runtime_character_definition(_binding(root))


def test_source_acceptance_semantic_hash_mismatch_fails_closed(
    real_package_root, tmp_path
):
    root = _copy_package(real_package_root, tmp_path)
    _rewrite_json(
        root,
        "provenance/source_acceptance.json",
        lambda payload: payload["acceptance_record"].__setitem__(
            "package_hash", "0" * 64
        ),
    )

    with pytest.raises(PackageRuntimeError, match="semantic hash"):
        load_runtime_character_definition(_binding(root))


@pytest.mark.parametrize(
    ("field", "wrong"),
    (("package_id", "wrong-package"), ("package_version", 999)),
)
def test_source_acceptance_candidate_identity_binding_mismatch_fails_closed(
    real_package_root, tmp_path, field, wrong
):
    root = _copy_package(real_package_root, tmp_path)
    _rewrite_json(
        root,
        "provenance/source_acceptance.json",
        lambda payload: payload["acceptance_record"].__setitem__(field, wrong),
    )

    with pytest.raises(PackageRuntimeError, match=field):
        load_runtime_character_definition(_binding(root))


def test_dimension_extension_accepted_hash_mismatch_fails_closed(
    real_package_root, tmp_path
):
    root = _copy_package(real_package_root, tmp_path)
    _rewrite_json(
        root,
        "extensions/dimension_semantics/v1.json",
        lambda payload: payload.__setitem__("target_accepted_source_hash", "0" * 64),
    )

    with pytest.raises(PackageRuntimeError, match="accepted-source hash"):
        load_runtime_character_definition(_binding(root))


def test_package_character_id_vs_dimension_extension_mismatch_fails_closed(
    real_package_root, tmp_path
):
    root = _copy_package(real_package_root, tmp_path)
    _rewrite_json(
        root,
        "extensions/dimension_semantics/v1.json",
        lambda payload: payload.__setitem__("character_id", "other"),
    )

    with pytest.raises(PackageRuntimeError, match="dimension semantics extension"):
        load_runtime_character_definition(_binding(root))


def test_package_character_id_vs_embedded_candidate_mismatch_fails_closed(
    real_package_root, tmp_path
):
    root = _copy_package(real_package_root, tmp_path)
    _rewrite_json(
        root,
        "package.json",
        lambda payload: payload.__setitem__("characterId", "other"),
    )

    with pytest.raises(PackageRuntimeError, match="embedded Candidate"):
        load_runtime_character_definition(_binding(root, character_id="other"))


def test_malformed_candidate_fails_strict_rehydration(real_package_root, tmp_path):
    root = _copy_package(real_package_root, tmp_path)
    _rewrite_json(
        root,
        "provenance/source_candidate.json",
        lambda payload: payload.pop("status"),
    )

    with pytest.raises(PackageRuntimeError, match="source Candidate is invalid"):
        load_runtime_character_definition(_binding(root))


def test_malformed_acceptance_fails_strict_rehydration(real_package_root, tmp_path):
    root = _copy_package(real_package_root, tmp_path)
    _rewrite_json(
        root,
        "provenance/source_acceptance.json",
        lambda payload: payload["acceptance_record"].pop("acceptance_id"),
    )

    with pytest.raises(PackageRuntimeError, match="source acceptance is invalid"):
        load_runtime_character_definition(_binding(root))


def test_malformed_dimension_semantics_fails_core_validation(
    real_package_root, tmp_path
):
    root = _copy_package(real_package_root, tmp_path)
    _rewrite_json(
        root,
        "extensions/dimension_semantics/v1.json",
        lambda payload: payload.__setitem__("dimensions", "not-a-list"),
    )

    with pytest.raises(PackageRuntimeError, match="dimension semantics content"):
        load_runtime_character_definition(_binding(root))


def test_structural_package_without_crp_import_descriptor_profile_is_ineligible(
    real_package_root, tmp_path
):
    root = _copy_package(real_package_root, tmp_path)
    manifest = _manifest(root)
    _descriptor(manifest, "provenance/source_candidate.json")[
        "semanticRole"
    ] = "PROVENANCE"
    _write_manifest(root, manifest)
    package_hash = _sha256((root / "manifest.json").read_bytes())
    verify_character_package_v1(root, expected_package_hash=package_hash)

    with pytest.raises(PackageRuntimeError, match="required canonical"):
        load_runtime_character_definition(_binding(root))


def test_incomplete_legacy_compat_cannot_masquerade_as_current_kira(
    real_package_root, tmp_path
):
    root = _copy_package(real_package_root, tmp_path)
    for relative_path in (
        "provenance/source_candidate.json",
        "provenance/source_acceptance.json",
        "extensions/dimension_semantics/v1.json",
    ):
        _remove_manifested_file(root, relative_path)
    package_hash = _sha256((root / "manifest.json").read_bytes())
    verified = verify_character_package_v1(root, expected_package_hash=package_hash)
    assert verified.authority_class == "LEGACY_COMPAT"

    with pytest.raises(PackageRuntimeError, match="profile requires"):
        load_runtime_character_definition(_binding(root))


def test_verify_then_semantic_file_change_is_detected(real_package_root, tmp_path, monkeypatch):
    root = _copy_package(real_package_root, tmp_path)
    original = package_runtime_module.verify_character_package_v1
    candidate_path = root / "provenance" / "source_candidate.json"
    calls = 0

    def verify_then_tamper(*args, **kwargs):
        nonlocal calls
        result = original(*args, **kwargs)
        calls += 1
        if calls == 1:
            candidate_path.write_bytes(candidate_path.read_bytes() + b" ")
        return result

    monkeypatch.setattr(
        package_runtime_module, "verify_character_package_v1", verify_then_tamper
    )

    with pytest.raises(PackageRuntimeError, match="changed after S6 verification"):
        load_runtime_character_definition(_binding(root))


def test_nonempty_visual_identity_is_not_silently_discarded(real_package_root, tmp_path):
    root = _copy_package(real_package_root, tmp_path)

    def populate(payload):
        payload["contentState"] = "POPULATED"
        payload["content"] = {"legacyPayload": [], "structured": {"portrait": "x"}}

    _rewrite_json(root, "domains/visual_identity.json", populate)

    with pytest.raises(PackageRuntimeError, match="visual binding belongs to S8C"):
        load_runtime_character_definition(_binding(root))
