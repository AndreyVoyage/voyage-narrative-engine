#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministic offline tests for Visual Asset Registry + Safe Import v0.

Stdlib-only, no Pillow, no network, no character-canon dependency. Fixtures
are tiny synthetic files generated in temporary directories that carry only
the magic-byte signature the import tool actually validates (it does not
decode pixels by design).
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import visual_asset_registry as var


# ---------------------------------------------------------------------------
# Tiny synthetic fixtures (magic-byte only; no decode in v0)
# ---------------------------------------------------------------------------

def _png_bytes(tag: bytes = b"") -> bytes:
    return b"\x89PNG\r\n\x1a\n" + tag


def _jpeg_bytes(tag: bytes = b"") -> bytes:
    return b"\xff\xd8\xff" + tag


def _webp_bytes(tag: bytes = b"") -> bytes:
    # RIFF <u32 size> WEBP ...
    size = (8 + len(tag)).to_bytes(4, "little")
    return b"RIFF" + size + b"WEBP" + tag


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
def env():
    """Return a temporary repo root + registry path, and helper writers."""
    with tempfile.TemporaryDirectory(prefix="vne_var_test_") as tmp:
        root = Path(tmp)
        images = root / "novel" / "game" / "images" / "story"
        registry = root / "scenarios" / "visual_assets" / "ASSET_REGISTRY.json"

        def write_source(name: str, data: bytes) -> Path:
            src = root / "src"
            src.mkdir(exist_ok=True)
            p = src / name
            p.write_bytes(data)
            return p

        yield {
            "root": root,
            "registry": registry,
            "images": images,
            "write_source": write_source,
        }


def _import(env, *, source, asset_id, asset_type, **kwargs):
    kw = dict(
        source_kind="manual",
        notes="",
        dry_run=False,
    )
    kw.update(kwargs)
    return var.import_asset(
        env["root"],
        env["registry"],
        source_path=source,
        asset_id=asset_id,
        asset_type=asset_type,
        **kw,
    )


# ---------------------------------------------------------------------------
# Format / validation
# ---------------------------------------------------------------------------

def test_valid_png_import(env):
    src = env["write_source"]("bg.png", _png_bytes(b"abc"))
    code, msg = _import(env, source=str(src), asset_id="bg_gym_night", asset_type="background")
    assert code == 0, msg
    dest = env["images"] / "backgrounds" / "bg_gym_night.png"
    assert dest.is_file()
    records = json.loads(env["registry"].read_text(encoding="utf-8"))["assets"]
    assert len(records) == 1
    assert records[0]["imported_hash"] == _sha256(_png_bytes(b"abc"))


def test_valid_webp_import(env):
    src = env["write_source"]("e.webp", _webp_bytes(b"x"))
    code, msg = _import(env, source=str(src), asset_id="kira_neutral", asset_type="character", character_id="kira")
    assert code == 0, msg
    assert (env["images"] / "characters" / "kira" / "kira_neutral.webp").is_file()


def test_valid_jpeg_import(env):
    src = env["write_source"]("c.jpg", _jpeg_bytes(b"y"))
    code, msg = _import(env, source=str(src), asset_id="cg_sc017_phone", asset_type="cg")
    assert code == 0, msg
    assert (env["images"] / "cg" / "cg_sc017_phone.jpg").is_file()


def test_jpg_jpeg_canonicalises(env):
    src = env["write_source"]("c.jpeg", _jpeg_bytes(b"y"))
    code, msg = _import(env, source=str(src), asset_id="cg_sc017_phone", asset_type="cg")
    assert code == 0, msg
    # jpeg -> canonical .jpg destination
    assert (env["images"] / "cg" / "cg_sc017_phone.jpg").is_file()


def test_missing_source_rejected(env):
    code, msg = _import(
        env,
        source=str(env["root"] / "nope.png"),
        asset_id="bg_x",
        asset_type="background",
    )
    assert code == 1
    assert "does not exist" in msg


def test_unsupported_extension_rejected(env):
    src = env["write_source"]("x.gif", b"GIF89a")
    code, msg = _import(env, source=str(src), asset_id="bg_x", asset_type="background")
    assert code == 1
    assert "unsupported extension" in msg


def test_extension_signature_mismatch_rejected(env):
    # A renamed non-image pretending to be PNG.
    src = env["write_source"]("fake.png", b"GIF89a" + b"x" * 16)
    code, msg = _import(env, source=str(src), asset_id="bg_x", asset_type="background")
    assert code == 1
    assert "mismatch" in msg


def test_zero_byte_rejected(env):
    src = env["write_source"]("empty.png", b"")
    code, msg = _import(env, source=str(src), asset_id="bg_x", asset_type="background")
    assert code == 1
    assert "empty" in msg


def test_invalid_asset_id_rejected(env):
    src = env["write_source"]("a.png", _png_bytes(b"z"))
    for bad in ("", "A", "ab", "1abc", "has space", "with-dash", "a" * 70):
        code, msg = _import(env, source=str(src), asset_id=bad, asset_type="background")
        assert code == 1, bad
        assert "asset_id" in msg or "asset_id" in str(msg)


def test_invalid_category_rejected(env):
    src = env["write_source"]("a.png", _png_bytes(b"z"))
    code, msg = _import(env, source=str(src), asset_id="bg_x", asset_type="portrait")
    assert code == 1


def test_character_requires_character_id(env):
    src = env["write_source"]("a.png", _png_bytes(b"z"))
    code, msg = _import(env, source=str(src), asset_id="who_neutral", asset_type="character")
    assert code == 1
    assert "character-id" in msg


def test_destination_stays_under_root(env):
    src = env["write_source"]("a.png", _png_bytes(b"z"))
    code, msg = _import(env, source=str(src), asset_id="bg_x", asset_type="background")
    assert code == 0
    rel = json.loads(env["registry"].read_text(encoding="utf-8"))["assets"][0]["relative_path"]
    assert rel.startswith("novel/game/images/story/")
    assert ".." not in rel


def test_source_remains_untouched(env):
    data = _png_bytes(b"preserve-me")
    src = env["write_source"]("a.png", data)
    code, msg = _import(env, source=str(src), asset_id="bg_x", asset_type="background")
    assert code == 0
    assert src.read_bytes() == data  # COPY, not MOVE/modify


# ---------------------------------------------------------------------------
# Duplicate matrix
# ---------------------------------------------------------------------------

def test_duplicate_identical_noop(env):
    src = env["write_source"]("a.png", _png_bytes(b"same"))
    c0, _ = _import(env, source=str(src), asset_id="bg_x", asset_type="background")
    assert c0 == 0
    before = env["registry"].read_text(encoding="utf-8")
    c1, msg = _import(env, source=str(src), asset_id="bg_x", asset_type="background")
    assert c1 == 0
    assert "NO-OP" in msg
    assert env["registry"].read_text(encoding="utf-8") == before


def test_duplicate_same_id_different_bytes_rejected(env):
    src_a = env["write_source"]("a.png", _png_bytes(b"first"))
    _import(env, source=str(src_a), asset_id="bg_x", asset_type="background")
    src_b = env["write_source"]("b.png", _png_bytes(b"second"))
    code, msg = _import(env, source=str(src_b), asset_id="bg_x", asset_type="background")
    assert code == 1
    assert "update" in msg


def test_different_id_identical_bytes_warns(env):
    src = env["write_source"]("a.png", _png_bytes(b"dup"))
    _import(env, source=str(src), asset_id="bg_a", asset_type="background")
    code, msg = _import(env, source=str(src), asset_id="bg_b", asset_type="background", dry_run=False)
    assert code == 0
    records = json.loads(env["registry"].read_text(encoding="utf-8"))["assets"]
    assert len(records) == 2


def test_orphan_destination_rejected(env):
    src = env["write_source"]("a.png", _png_bytes(b"z"))
    # Manually place a file at the computed destination without a registry entry.
    dest = env["images"] / "backgrounds" / "bg_orphan.png"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(_png_bytes(b"z2"))
    code, msg = _import(env, source=str(src), asset_id="bg_orphan", asset_type="background")
    assert code == 1
    assert "no entry" in msg


# ---------------------------------------------------------------------------
# Update / re-import
# ---------------------------------------------------------------------------

def test_update_succeeds(env):
    src_a = env["write_source"]("a.png", _png_bytes(b"v1"))
    _import(env, source=str(src_a), asset_id="kira_neutral", asset_type="character", character_id="kira")
    src_b = env["write_source"]("b.png", _png_bytes(b"v2"))
    code, msg = var.update_asset(
        env["root"], env["registry"], asset_id="kira_neutral", source_path=str(src_b)
    )
    assert code == 0, msg
    rec = json.loads(env["registry"].read_text(encoding="utf-8"))["assets"][0]
    assert rec["imported_hash"] == _sha256(_png_bytes(b"v2"))
    dest = env["images"] / "characters" / "kira" / "kira_neutral.png"
    assert dest.read_bytes() == _png_bytes(b"v2")


def test_update_missing_id_rejected(env):
    src = env["write_source"]("a.png", _png_bytes(b"z"))
    code, msg = var.update_asset(
        env["root"], env["registry"], asset_id="ghost_id", source_path=str(src)
    )
    assert code == 1
    assert "not found" in msg


# ---------------------------------------------------------------------------
# Dry-run
# ---------------------------------------------------------------------------

def test_dry_run_produces_no_writes(env):
    src = env["write_source"]("a.png", _png_bytes(b"z"))
    code, msg = _import(env, source=str(src), asset_id="bg_x", asset_type="background", dry_run=True)
    assert code == 0
    assert "DRY-RUN" in msg
    assert not (env["images"] / "backgrounds" / "bg_x.png").exists()
    assert not env["registry"].exists()


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

def test_registry_deterministic_ordering(env):
    for i, aid in enumerate(["cg_b", "bg_a", "cg_a"]):
        src = env["write_source"]("f{}.png".format(i), _png_bytes(b"d" + str(i).encode()))
        code, _ = _import(env, source=str(src), asset_id=aid, asset_type=("cg" if aid.startswith("cg") else "background"))
        assert code == 0
    text = env["registry"].read_text(encoding="utf-8")
    ids = [r["asset_id"] for r in json.loads(text)["assets"]]
    assert ids == sorted(ids)
    assert text.endswith("\n")
    # Re-serialization with no semantic change should be byte-identical.
    records = var.load_registry(env["registry"])
    assert var.serialize_registry(records) == text


# ---------------------------------------------------------------------------
# Failure safety (compensating rollback / cleanup)
# ---------------------------------------------------------------------------

def test_update_registry_failure_restores_old_asset(env, monkeypatch):
    # MAJOR reproduction: registry-write failure must NOT leave new asset
    # bytes paired with the stale registry hash.
    src_v1 = env["write_source"]("a.png", _png_bytes(b"v1"))
    _import(
        env,
        source=str(src_v1),
        asset_id="kira_neutral",
        asset_type="character",
        character_id="kira",
    )
    dest = env["images"] / "characters" / "kira" / "kira_neutral.png"
    registry_before = env["registry"].read_text(encoding="utf-8")
    dest_before = dest.read_bytes()

    src_v2 = env["write_source"]("b.png", _png_bytes(b"v2-new"))

    def _fail_save(*_args, **_kwargs):
        raise OSError("SIMULATED registry write failure")

    monkeypatch.setattr(var, "save_registry", _fail_save)

    code, msg = var.update_asset(
        env["root"], env["registry"], asset_id="kira_neutral", source_path=str(src_v2)
    )
    assert code == 1
    assert "rolled back" in msg
    # Destination restored to v1; registry unchanged; source untouched.
    assert dest.read_bytes() == dest_before
    assert env["registry"].read_text(encoding="utf-8") == registry_before
    assert src_v2.read_bytes() == _png_bytes(b"v2-new")
    # Registry hash still matches actual destination hash.
    rec = json.loads(registry_before)["assets"][0]
    assert rec["imported_hash"] == _sha256(dest_before) == _sha256(dest.read_bytes())
    # No staging/backup temp artifacts remain.
    leftovers = [p for p in dest.parent.iterdir() if p.name.startswith(".")]
    assert leftovers == []


def test_import_registry_failure_cleans_new_dest(env, monkeypatch):
    src = env["write_source"]("a.png", _png_bytes(b"v1"))
    dest = env["images"] / "backgrounds" / "bg_x.png"

    def _fail_save(*_args, **_kwargs):
        raise OSError("SIMULATED registry write failure")

    monkeypatch.setattr(var, "save_registry", _fail_save)

    code, msg = _import(env, source=str(src), asset_id="bg_x", asset_type="background")
    assert code == 1
    assert "newly copied asset removed" in msg
    assert not env["registry"].exists()
    assert not dest.exists()
    assert src.read_bytes() == _png_bytes(b"v1")


def test_copy_phase_failure_normalized(env, monkeypatch):
    src = env["write_source"]("a.png", _png_bytes(b"v1"))
    dest = env["images"] / "backgrounds" / "bg_x.png"

    def _fail_copy(*_args, **_kwargs):
        raise OSError("SIMULATED copy failure")

    monkeypatch.setattr(var, "_atomic_copy_bytes", _fail_copy)

    code, msg = _import(env, source=str(src), asset_id="bg_x", asset_type="background")
    assert code == 1
    assert "copy failed" in msg
    assert not env["registry"].exists()
    assert not dest.exists()
    assert src.read_bytes() == _png_bytes(b"v1")


def test_update_rollback_failure_surfaced(env, monkeypatch):
    src_v1 = env["write_source"]("a.png", _png_bytes(b"v1"))
    _import(
        env,
        source=str(src_v1),
        asset_id="kira_neutral",
        asset_type="character",
        character_id="kira",
    )
    registry_before = env["registry"].read_text(encoding="utf-8")

    src_v2 = env["write_source"]("b.png", _png_bytes(b"v2-new"))

    def _fail_save(*_args, **_kwargs):
        raise OSError("SIMULATED registry write failure")

    real_replace = os.replace

    def _fail_restore(src_path, dst_path):
        # Only fail the rollback restore (backup -> dest), not the forward
        # stage->dest replace.
        if "asset_bak" in str(src_path):
            raise OSError("SIMULATED rollback failure")
        return real_replace(src_path, dst_path)

    monkeypatch.setattr(var, "save_registry", _fail_save)
    monkeypatch.setattr(os, "replace", _fail_restore)

    code, msg = var.update_asset(
        env["root"], env["registry"], asset_id="kira_neutral", source_path=str(src_v2)
    )
    assert code == 1
    assert "CRITICAL" in msg
    assert "rollback" in msg
    # Registry remained old/unchanged; tool did not claim success.
    assert env["registry"].read_text(encoding="utf-8") == registry_before
    # A recoverable backup is retained (not silently destroyed).
    back_dir = env["images"] / "characters" / "kira"
    backups = [p for p in back_dir.iterdir() if "_bak_" in str(p)]
    assert len(backups) >= 1
    assert src_v2.read_bytes() == _png_bytes(b"v2-new")


# ---------------------------------------------------------------------------
# Validate
# ---------------------------------------------------------------------------

def _snapshot_registry(env):
    return env["registry"].read_text(encoding="utf-8")


def _restore_registry(env, text):
    env["registry"].parent.mkdir(parents=True, exist_ok=True)
    env["registry"].write_text(text, encoding="utf-8")


def test_validate_passes_valid_registry(env):
    src = env["write_source"]("a.png", _png_bytes(b"z"))
    _import(env, source=str(src), asset_id="bg_x", asset_type="background")
    errors, _ = var.validate_registry(env["registry"], env["root"])
    assert errors == []


def test_validate_detects_missing_file(env):
    src = env["write_source"]("a.png", _png_bytes(b"z"))
    _import(env, source=str(src), asset_id="bg_x", asset_type="background")
    dest = env["images"] / "backgrounds" / "bg_x.png"
    dest.unlink()
    errors, _ = var.validate_registry(env["registry"], env["root"])
    assert any("missing" in e for e in errors)


def test_validate_detects_hash_mismatch(env):
    src = env["write_source"]("a.png", _png_bytes(b"z"))
    _import(env, source=str(src), asset_id="bg_x", asset_type="background")
    dest = env["images"] / "backgrounds" / "bg_x.png"
    dest.write_bytes(_png_bytes(b"tampered"))
    errors, _ = var.validate_registry(env["registry"], env["root"])
    assert any("mismatch" in e for e in errors)


def test_validate_detects_invalid_path(env):
    src = env["write_source"]("a.png", _png_bytes(b"z"))
    _import(env, source=str(src), asset_id="bg_x", asset_type="background")
    orig = _snapshot_registry(env)
    data = json.loads(orig)
    data["assets"][0]["relative_path"] = "../evil.png"
    _restore_registry(env, json.dumps(data))
    errors, _ = var.validate_registry(env["registry"], env["root"])
    assert any(".." in e for e in errors)


def test_validate_is_read_only(env):
    src = env["write_source"]("a.png", _png_bytes(b"z"))
    _import(env, source=str(src), asset_id="bg_x", asset_type="background")
    before = _snapshot_registry(env)
    var.validate_registry(env["registry"], env["root"])
    assert _snapshot_registry(env) == before


def test_validate_detects_orphaned_file(env):
    # A supported asset file exists under the story root with no registry entry.
    orphan = env["images"] / "backgrounds" / "bg_orphan.png"
    orphan.parent.mkdir(parents=True, exist_ok=True)
    orphan.write_bytes(_png_bytes(b"orphan"))
    registry_text = '{"assets": []}'
    env["registry"].parent.mkdir(parents=True, exist_ok=True)
    env["registry"].write_text(registry_text, encoding="utf-8")

    errors, _ = var.validate_registry(env["registry"], env["root"])
    assert any("orphaned asset file" in e for e in errors)
    # Read-only: file still present, registry unchanged.
    assert orphan.exists()
    assert env["registry"].read_text(encoding="utf-8") == registry_text


# ---------------------------------------------------------------------------
# Read-only lookup helper (lookup_asset)
# ---------------------------------------------------------------------------


def _record(asset_id, rel):
    return {"asset_id": asset_id, "relative_path": rel}


def test_lookup_asset_returns_exact_record():
    records = [
        _record("asset_a", "novel/game/images/story/cg/a.png"),
        _record("asset_b", "novel/game/images/story/cg/b.png"),
    ]
    assert var.lookup_asset(records, "asset_b")["relative_path"] == "novel/game/images/story/cg/b.png"


def test_lookup_asset_missing_fails_closed():
    with pytest.raises(ValueError):
        var.lookup_asset([_record("asset_a", "novel/game/images/story/cg/a.png")], "asset_nope")


def test_lookup_asset_duplicate_fails_closed():
    records = [
        _record("asset_dup", "novel/game/images/story/cg/a.png"),
        _record("asset_dup", "novel/game/images/story/cg/b.png"),
    ]
    with pytest.raises(ValueError):
        var.lookup_asset(records, "asset_dup")


def test_lookup_asset_invalid_id_fails_closed():
    with pytest.raises(ValueError):
        var.lookup_asset([], "UPPER_CASE")


def test_lookup_asset_does_not_mutate_input():
    records = [_record("asset_a", "novel/game/images/story/cg/a.png")]
    before = json.dumps(records, sort_keys=True)
    var.lookup_asset(records, "asset_a")
    assert json.dumps(records, sort_keys=True) == before
