#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S8B2 adversarial tests: deterministic pinned storage-namespace isolation.

All tests are offline and use isolated temporary data roots only. No real
package, no provider, no network, no production path.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from services.character_companion import (
    CompanionCatalog,
    CompanionCharacterEntry,
    CompanionError,
    CompanionService,
)
from services.character_companion.session_character import (
    SessionCharacterPinStatus,
    SessionCharacterPinV1,
)

from tests.character_companion.conftest import FAKE_PROVIDER_INFO, make_fake_factory


def _canonical_digest(character_id: str, release_id: str, package_hash: str) -> str:
    payload = {
        "character_id": character_id,
        "package_hash": package_hash,
        "release_id": release_id,
        "scheme": "pinned-storage-v1",
    }
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _pin(
    character_id: str = "alice",
    release_id: str = "v1",
    package_hash: str | None = None,
    runtime_definition_hash: str | None = None,
) -> SessionCharacterPinV1:
    return SessionCharacterPinV1(
        character_id=character_id,
        release_id=release_id,
        package_hash=package_hash or "a" * 64,
        runtime_definition_hash=runtime_definition_hash or "b" * 64,
    )


def _make_service(tmp_path: Path, *, character_id: str = "alice") -> CompanionService:
    (tmp_path / "acceptance").mkdir(parents=True, exist_ok=True)
    return CompanionService(
        acceptance_root=tmp_path / "acceptance",
        data_root=tmp_path / "companion-data",
        provider_factory=make_fake_factory(),
        provider_info=FAKE_PROVIDER_INFO,
        catalog=CompanionCatalog(
            [
                CompanionCharacterEntry(
                    character_id=character_id,
                    display_name=character_id.title(),
                    subject_id=character_id,
                    available=True,
                )
            ]
        ),
    )


def _row(session_id: str, character_id: str = "alice", **extra) -> dict:
    row = {
        "session_id": session_id,
        "character_id": character_id,
        "purpose": "COMPANION",
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "label": "session",
        "activity_seq": 1,
    }
    row.update(extra)
    return row


def _write_registry(data_root: Path, rows: list) -> None:
    path = data_root / "companion_sessions.json"
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


# --------------------------------------------------------------------------- #
# pure deterministic identity
# --------------------------------------------------------------------------- #
def test_A_same_character_different_release_different_namespace():
    a = _pin(release_id="v1").storage_namespace_id()
    b = _pin(release_id="v2").storage_namespace_id()
    assert a != b


def test_B_same_release_different_package_hash_different_namespace():
    a = _pin(package_hash="a" * 64).storage_namespace_id()
    b = _pin(package_hash="b" * 64).storage_namespace_id()
    assert a != b


def test_C_different_character_same_release_hash_different_namespace():
    a = _pin(character_id="alice").storage_namespace_id()
    b = _pin(character_id="bob").storage_namespace_id()
    assert a != b


def test_D_same_identity_same_digest():
    assert _pin().storage_namespace_id() == _pin().storage_namespace_id()


def test_E_runtime_definition_hash_not_in_namespace():
    a = _pin(runtime_definition_hash="1" * 64).storage_namespace_id()
    b = _pin(runtime_definition_hash="2" * 64).storage_namespace_id()
    assert a == b


def test_R_canonical_digest_matches_manual_bytes():
    pin = _pin(character_id="kira", release_id="crp-import-v1", package_hash="0" * 64)
    expected = _canonical_digest("kira", "crp-import-v1", "0" * 64)
    assert pin.storage_namespace_id() == expected
    assert len(pin.storage_namespace_id()) == 64
    assert set(pin.storage_namespace_id()) <= set("0123456789abcdef")


def test_namespace_id_is_64_lower_hex():
    digest = _pin().storage_namespace_id()
    assert len(digest) == 64
    assert digest == digest.lower()


# --------------------------------------------------------------------------- #
# service storage-root isolation
# --------------------------------------------------------------------------- #
def test_FG_pinned_roots_differ_from_legacy(tmp_path):
    service = _make_service(tmp_path)
    legacy = service._char_root("alice")
    pinned = service._pinned_storage_root(_pin())
    assert (pinned / "memory") != (legacy / "memory")
    assert (pinned / "state") != (legacy / "state")


def test_HI_two_releases_roots_differ(tmp_path):
    service = _make_service(tmp_path)
    r1 = service._pinned_storage_root(_pin(release_id="v1"))
    r2 = service._pinned_storage_root(_pin(release_id="v2"))
    assert (r1 / "memory") != (r2 / "memory")
    assert (r1 / "state") != (r2 / "state")


def test_J_legacy_layout_exact(tmp_path):
    service = _make_service(tmp_path)
    root = service._char_root("alice")
    assert root == service._data_root / "characters" / "alice"
    assert (root / "memory").is_dir()
    assert (root / "state").is_dir()


def test_K_pin_absent_routes_to_legacy(tmp_path):
    service = _make_service(tmp_path)
    row = _row("cmp-legacy")
    _write_registry(service._data_root, [row])
    root = service._storage_root_for_session(row)
    assert root == service._data_root / "characters" / "alice"


def test_L_partial_or_null_pin_fail_closed(tmp_path):
    service = _make_service(tmp_path)
    _write_registry(service._data_root, [_row("cmp-partial", character_pin_v1={"character_id": "alice"})])
    with pytest.raises(CompanionError) as exc:
        service._storage_root_for_session(_row("cmp-partial", character_pin_v1={"character_id": "alice"}))
    assert exc.value.code == "pin_invalid"

    _write_registry(service._data_root, [_row("cmp-null", character_pin_v1=None)])
    with pytest.raises(CompanionError):
        service._storage_root_for_session(_row("cmp-null", character_pin_v1=None))


def test_M_character_mismatch_fail_closed(tmp_path):
    service = _make_service(tmp_path)
    pin = _pin(character_id="bob")
    row = _row("cmp-mismatch", "alice", character_pin_v1=pin.to_json())
    with pytest.raises(CompanionError) as exc:
        service._storage_root_for_session(row)
    assert exc.value.code == "pin_invalid"


def test_N_namespace_stable_when_another_release(tmp_path):
    service = _make_service(tmp_path)
    pin_v1 = _pin(release_id="v1")
    root_before = service._pinned_storage_root(pin_v1)
    # another release "appears" — derivation is pure, so it must not matter
    _pin(release_id="v2")
    assert service._pinned_storage_root(pin_v1) == root_before


def test_O_no_package_locator_needed(tmp_path):
    service = _make_service(tmp_path)
    pin = _pin()
    root = service._pinned_storage_root(pin)
    expected = (
        service._data_root / "character_namespaces" / "pinned-v1" / pin.storage_namespace_id()
    )
    assert root == expected


def test_P_path_like_material_no_escape(tmp_path):
    service = _make_service(tmp_path)
    pin = _pin(release_id="../etc")
    root = service._pinned_storage_root(pin)
    base = service._data_root / "character_namespaces" / "pinned-v1"
    assert root.parent == base
    assert root.name == pin.storage_namespace_id()
    assert len(root.name) == 64
    assert base in root.parents


def test_Q_raw_ids_not_in_path(tmp_path):
    service = _make_service(tmp_path)
    pin = _pin(character_id="alice", release_id="v1", package_hash="a" * 64)
    root = service._pinned_storage_root(pin)
    parts = set(root.parts)
    assert "alice" not in parts
    assert "v1" not in parts
    assert ("a" * 64) not in parts
    assert root.name == pin.storage_namespace_id()


def test_S_no_provider_called(tmp_path):
    factory = make_fake_factory()
    (tmp_path / "acceptance").mkdir(parents=True, exist_ok=True)
    service = CompanionService(
        acceptance_root=tmp_path / "acceptance",
        data_root=tmp_path / "companion-data",
        provider_factory=factory,
        provider_info=FAKE_PROVIDER_INFO,
        catalog=CompanionCatalog(
            [
                CompanionCharacterEntry(
                    character_id="alice",
                    display_name="Alice",
                    subject_id="alice",
                    available=True,
                )
            ]
        ),
    )
    service._pinned_storage_root(_pin())
    assert factory.calls == []


def test_T_no_production_path(tmp_path):
    service = _make_service(tmp_path)
    root = service._pinned_storage_root(_pin())
    assert str(root).startswith(str(tmp_path))


def test_U_pinned_execution_guards_remain_blocked(tmp_path):
    service = _make_service(tmp_path)
    pin = _pin()
    _write_registry(
        service._data_root,
        [_row("cmp-pinned", "alice", character_pin_v1=pin.to_json())],
    )
    # S8C1: valid pinned send is no longer rejected by the generic execution
    # guard. With an unresolved exact package it fails closed at definition
    # resolution, not at the pinned-blocked guard.
    with pytest.raises(CompanionError) as exc:
        service.send_message("cmp-pinned", "Hello")
    assert exc.value.code == "package_missing"

    # S8C1: valid pinned history reads its S8B2 namespace and is no longer
    # rejected by the generic guard; it needs no package or provider.
    assert service.get_messages("cmp-pinned") == ()

    # S8C2: pinned co-author is no longer generically blocked; it advances to
    # exact-definition resolution, failing closed on the unresolved package.
    with pytest.raises(CompanionError) as exc:
        service._coauthor_context("cmp-pinned")
    assert exc.value.code == "package_missing"
