#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Character Canon Read Bridge v0 tests -- resolution, status gating,
snapshot determinism/immutability, hash, path safety, and read-only boundary."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any

import pytest

from services.character_canon_bridge import (
    AmbiguousCharacterError,
    CanonRootMissingError,
    CanonStatusUnknownError,
    CharacterCanonBridgeError,
    CharacterNotFoundError,
    ProductionNotAllowedError,
    ReferencePathSafetyError,
    compute_content_hash,
    read_character_canon,
)

from .conftest import _write_preset, make_approved, make_pending


def _read(canon_root: Path, character_id: str, usage_context: str):
    return read_character_canon(canon_root, character_id, usage_context)


# ---------------------------------------------------------------------------
# A. Exact resolution
# ---------------------------------------------------------------------------


def test_exact_id_resolves(canon_root, pending_kira):
    snap = _read(canon_root, pending_kira, "draft")
    assert snap.character_id == "KIRA"
    assert snap.status == "PENDING_APPROVAL"


def test_unknown_character_fails(canon_root):
    # Ensure the root exists with an unrelated character so the missing
    # character deterministically produces CharacterNotFoundError.
    make_approved(canon_root, character_id="OTHER_ONE")
    with pytest.raises(CharacterNotFoundError):
        _read(canon_root, "NO_SUCH", "draft")


def test_case_mismatch_fails_no_fuzzy(canon_root, pending_kira):
    # Exact resolution: 'kira' must not resolve to 'KIRA'. On a case-sensitive
    # filesystem this fails as not-found; on a case-insensitive filesystem the
    # directory silently resolves and the declared-id mismatch fails closed.
    # Either way a CharacterCanonBridgeError (fail-closed) must be raised.
    with pytest.raises(CharacterCanonBridgeError):
        _read(canon_root, "kira", "draft")


def test_missing_root_fails(tmp_path):
    with pytest.raises(CanonRootMissingError):
        _read(tmp_path / "does-not-exist", "KIRA", "draft")


# ---------------------------------------------------------------------------
# B. Status resolution
# ---------------------------------------------------------------------------


def test_approved_status_resolves(canon_root):
    cid = make_approved(canon_root)
    snap = _read(canon_root, cid, "draft")
    assert snap.status == "APPROVED"


def test_unknown_status_fails_closed(canon_root):
    make_pending(canon_root, character_id="WEIRD_ONE")
    path = canon_root / "AI_CHARACTERS" / "WEIRD_ONE" / "10_notes" / "WEIRD_ONE_REFERENCE_PRESETS.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["status"] = "SOME_FUTURE_STATUS"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(CanonStatusUnknownError):
        _read(canon_root, "WEIRD_ONE", "draft")


# ---------------------------------------------------------------------------
# C. Usage gate
# ---------------------------------------------------------------------------


def test_pending_draft_allowed(canon_root, pending_kira):
    snap = _read(canon_root, pending_kira, "draft")
    assert snap.status == "PENDING_APPROVAL"


def test_pending_authoring_allowed(canon_root, pending_kira):
    snap = _read(canon_root, pending_kira, "authoring")
    assert snap.status == "PENDING_APPROVAL"


def test_pending_production_blocked(canon_root, pending_kira):
    with pytest.raises(ProductionNotAllowedError):
        _read(canon_root, pending_kira, "production")


def test_approved_production_allowed(canon_root):
    cid = make_approved(canon_root)
    snap = _read(canon_root, cid, "production")
    assert snap.status == "APPROVED"


# ---------------------------------------------------------------------------
# D. Snapshot content
# ---------------------------------------------------------------------------


def test_snapshot_preserves_status_and_references(canon_root, pending_kira):
    snap = _read(canon_root, pending_kira, "draft")
    assert snap.status == "PENDING_APPROVAL"
    keys = {r.key for r in snap.references}
    assert "face" in keys
    assert "body" in keys
    assert any(k.startswith("scene:") for k in keys)


def test_references_are_repo_relative(canon_root, pending_kira):
    snap = _read(canon_root, pending_kira, "draft")
    for ref in snap.references:
        assert not ref.path.startswith("/")
        assert not ref.path.startswith("\\")
        assert "C:" not in ref.path.upper()


# ---------------------------------------------------------------------------
# E. Deep immutability
# ---------------------------------------------------------------------------


def test_snapshot_is_frozen(canon_root, pending_kira):
    snap = _read(canon_root, pending_kira, "draft")
    with pytest.raises(dataclasses.FrozenInstanceError):
        snap.status = "APPROVED"  # type: ignore[misc]


def test_references_is_tuple(canon_root, pending_kira):
    snap = _read(canon_root, pending_kira, "draft")
    assert isinstance(snap.references, tuple)


def test_payload_mutation_does_not_affect_snapshot(canon_root, pending_kira):
    snap = _read(canon_root, pending_kira, "draft")
    stored = snap.content_hash
    payload = snap.semantic_payload()
    payload["status"] = "APPROVED"
    payload["references"].append({"key": "x", "path": "y"})

    assert snap.status == "PENDING_APPROVAL"
    assert compute_content_hash(snap.semantic_payload()) == stored


def test_to_dict_mutation_does_not_affect_snapshot(canon_root, pending_kira):
    snap = _read(canon_root, pending_kira, "draft")
    stored = snap.content_hash
    envelope = snap.to_dict()
    envelope["status"] = "APPROVED"
    envelope["references"].append({"key": "x", "path": "y"})

    assert snap.status == "PENDING_APPROVAL"
    assert snap.content_hash == stored


# ---------------------------------------------------------------------------
# F. Hash determinism
# ---------------------------------------------------------------------------


def test_same_canon_same_hash(canon_root, pending_kira):
    a = _read(canon_root, pending_kira, "draft")
    b = _read(canon_root, pending_kira, "draft")
    assert a.content_hash == b.content_hash


def test_status_change_changes_hash(canon_root, pending_kira):
    a = _read(canon_root, pending_kira, "draft")
    # Rewrite the same character with APPROVED status and read again.
    path = canon_root / "AI_CHARACTERS" / pending_kira / "10_notes" / f"{pending_kira}_REFERENCE_PRESETS.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["status"] = "APPROVED"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    b = _read(canon_root, pending_kira, "draft")
    assert b.content_hash != a.content_hash


def test_provenance_not_in_semantic_payload(canon_root, pending_kira):
    snap = _read(canon_root, pending_kira, "draft")
    payload = snap.semantic_payload()
    assert "provenance" not in payload
    assert "schema_version" not in payload
    assert "content_hash" not in payload


# ---------------------------------------------------------------------------
# G. Path safety
# ---------------------------------------------------------------------------


def test_traversal_reference_rejected(canon_root):
    # Build a preset whose active_canon path contains '..'.
    bad = {
        "character": "EVIL_ONE",
        "active_version": "v1",
        "status": "APPROVED",
        "active_canon": {"face": "../escape.png"},
    }
    _write_preset(canon_root, "EVIL_ONE", bad)
    with pytest.raises(ReferencePathSafetyError):
        _read(canon_root, "EVIL_ONE", "draft")


def test_absolute_reference_rejected(canon_root):
    bad = {
        "character": "ABS_ONE",
        "active_version": "v1",
        "status": "APPROVED",
        "active_canon": {"face": "C:/absolute/path.png"},
    }
    _write_preset(canon_root, "ABS_ONE", bad)
    with pytest.raises(ReferencePathSafetyError):
        _read(canon_root, "ABS_ONE", "draft")


# ---------------------------------------------------------------------------
# H. Read-only boundary
# ---------------------------------------------------------------------------


def test_read_does_not_modify_source(canon_root, pending_kira):
    preset = canon_root / "AI_CHARACTERS" / pending_kira / "10_notes" / f"{pending_kira}_REFERENCE_PRESETS.json"
    before = preset.read_bytes()
    _read(canon_root, pending_kira, "draft")
    after = preset.read_bytes()
    assert before == after