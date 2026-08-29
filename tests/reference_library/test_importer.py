#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reference Library v0 tests -- controlled import (SVA-RL2).

Deterministic, stdlib-only, offline tests. Sources are tiny synthetic files
carrying only the magic-byte signature the importer actually checks (it never
decodes pixels). No real NCC files are imported.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from services.reference_library import (
    IMPORTED,
    NO_OP_DUPLICATE,
    NO_OP_EXISTING_ASSET,
    AssetIdCollisionError,
    CrossCharacterDuplicateError,
    FormatMismatchError,
    ReferenceLibraryValidationError,
    SourceValidationError,
    UnsupportedFormatError,
    compute_sha256,
    import_reference,
    load_manifest,
    parse_manifest,
    serialize_manifest,
)

from .conftest import sha256_of


# ---------------------------------------------------------------------------
# Tiny synthetic fixtures (magic-byte only; no decode)
# ---------------------------------------------------------------------------

def png_bytes(tag: bytes = b"") -> bytes:
    return b"\x89PNG\r\n\x1a\n" + tag


def jpeg_bytes(tag: bytes = b"") -> bytes:
    return b"\xff\xd8\xff" + tag


def webp_bytes(tag: bytes = b"") -> bytes:
    size = (8 + len(tag)).to_bytes(4, "little")
    return b"RIFF" + size + b"WEBP" + tag


@pytest.fixture
def env(tmp_path: Path):
    root = tmp_path
    manifest = root / "authoring" / "reference_library" / "REFERENCE_LIBRARY_MANIFEST.json"
    src_dir = root / "src"
    src_dir.mkdir(exist_ok=True)

    def write_source(name: str, data: bytes) -> Path:
        p = src_dir / name
        p.write_bytes(data)
        return p

    return {"root": root, "manifest": manifest, "src_dir": src_dir, "write_source": write_source}


def _import(env, source, asset_id, character_id, **kw):
    return import_reference(
        source,
        repo_root=env["root"],
        manifest_path=env["manifest"],
        asset_id=asset_id,
        character_id=character_id,
        **kw,
    )


# ---------------------------------------------------------------------------
# Valid imports (PNG / JPEG / WEBP)
# ---------------------------------------------------------------------------


def test_valid_png_import(env):
    src = env["write_source"]("n.png", png_bytes(b"abc"))
    result = _import(env, src, "kira_neutral", "kira")
    assert result.status == IMPORTED
    assert result.copied is True
    dest = env["root"] / "authoring/reference_library/assets/characters/kira/kira_neutral.png"
    assert dest.is_file()
    records = load_manifest(env["manifest"])
    assert len(records) == 1
    assert records[0].file_type == "PNG"
    assert records[0].sha256 == sha256_of(png_bytes(b"abc"))


def test_valid_jpeg_import(env):
    src = env["write_source"]("n.jpeg", jpeg_bytes(b"x"))
    result = _import(env, src, "a", "c")
    assert result.status == IMPORTED
    dest = env["root"] / "authoring/reference_library/assets/characters/c/a.jpg"
    assert dest.is_file()
    assert load_manifest(env["manifest"])[0].file_type == "JPEG"


def test_valid_webp_import(env):
    src = env["write_source"]("n.webp", webp_bytes(b"x"))
    result = _import(env, src, "a", "c")
    assert result.status == IMPORTED
    dest = env["root"] / "authoring/reference_library/assets/characters/c/a.webp"
    assert dest.is_file()
    assert load_manifest(env["manifest"])[0].file_type == "WEBP"


# ---------------------------------------------------------------------------
# Source validation
# ---------------------------------------------------------------------------


def test_extension_signature_mismatch_rejected(env):
    src = env["write_source"]("n.png", jpeg_bytes(b"x"))
    with pytest.raises(FormatMismatchError):
        _import(env, src, "a", "c")


def test_unsupported_format_rejected(env):
    src = env["write_source"]("n.gif", b"GIF89a" + b"x" * 10)
    with pytest.raises(UnsupportedFormatError):
        _import(env, src, "a", "c")


def test_empty_file_rejected(env):
    src = env["write_source"]("n.png", b"")
    with pytest.raises(SourceValidationError):
        _import(env, src, "a", "c")


def test_directory_source_rejected(env):
    with pytest.raises(SourceValidationError):
        _import(env, env["src_dir"], "a", "c")


# ---------------------------------------------------------------------------
# Copy semantics / integrity
# ---------------------------------------------------------------------------


def test_source_unchanged_after_import(env):
    data = png_bytes(b"abc")
    src = env["write_source"]("n.png", data)
    _import(env, src, "a", "c")
    assert src.read_bytes() == data


def test_destination_path_deterministic(env):
    src = env["write_source"]("n.png", png_bytes(b"x"))
    result = _import(env, src, "a", "c")
    assert result.relative_path == "authoring/reference_library/assets/characters/c/a.png"
    assert result.record.relative_path == result.relative_path


def test_copied_sha_equals_source_sha(env):
    data = png_bytes(b"abc")
    src = env["write_source"]("n.png", data)
    result = _import(env, src, "a", "c")
    dest = env["root"] / result.relative_path
    assert compute_sha256(dest.read_bytes()) == sha256_of(data)
    assert result.sha256 == sha256_of(data)


def test_manifest_record_created(env):
    src = env["write_source"]("n.png", png_bytes(b"x"))
    _import(env, src, "a", "c")
    records = load_manifest(env["manifest"])
    assert len(records) == 1
    r = records[0]
    assert r.asset_id == "a"
    assert r.character_id == "c"
    assert r.filename == "a.png"
    assert r.file_type == "PNG"


def test_manifest_round_trip_deterministic(env):
    src = env["write_source"]("n.png", png_bytes(b"x"))
    _import(env, src, "a", "c")
    text = env["manifest"].read_text(encoding="utf-8")
    assert serialize_manifest(parse_manifest(text)) == text


# ---------------------------------------------------------------------------
# Duplicate / ownership policies
# ---------------------------------------------------------------------------


def test_duplicate_same_sha_same_character_noop(env):
    data = png_bytes(b"x")
    src = env["write_source"]("n.png", data)
    _import(env, src, "a", "c")
    result = _import(env, src, "b", "c")
    assert result.status == NO_OP_DUPLICATE
    assert result.copied is False
    assert result.record.asset_id == "a"
    assert len(load_manifest(env["manifest"])) == 1
    assert not (env["root"] / "authoring/reference_library/assets/characters/c/b.png").exists()


def test_duplicate_cross_character_rejected(env):
    data = png_bytes(b"x")
    src = env["write_source"]("n.png", data)
    _import(env, src, "a", "c1")
    with pytest.raises(CrossCharacterDuplicateError):
        _import(env, src, "b", "c2")


def test_existing_asset_id_same_sha_noop(env):
    data = png_bytes(b"x")
    src = env["write_source"]("n.png", data)
    _import(env, src, "a", "c")
    result = _import(env, src, "a", "c")
    assert result.status == NO_OP_EXISTING_ASSET
    assert result.copied is False
    assert len(load_manifest(env["manifest"])) == 1


def test_existing_asset_id_different_sha_rejected(env):
    src1 = env["write_source"]("n1.png", png_bytes(b"x"))
    src2 = env["write_source"]("n2.png", png_bytes(b"y"))
    _import(env, src1, "a", "c")
    with pytest.raises(AssetIdCollisionError):
        _import(env, src2, "a", "c")


# ---------------------------------------------------------------------------
# Path safety / collection / arbitrary IDs
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad", ["../evil", "a/b", "..", "a\\b"])
def test_unsafe_character_id_rejected(env, bad):
    src = env["write_source"]("n.png", png_bytes(b"x"))
    with pytest.raises(ReferenceLibraryValidationError):
        _import(env, src, "a", bad)


def test_unsafe_asset_id_rejected(env):
    src = env["write_source"]("n.png", png_bytes(b"x"))
    with pytest.raises(ReferenceLibraryValidationError):
        _import(env, src, "../evil", "c")


def test_collection_does_not_alter_destination(env):
    src = env["write_source"]("n.png", png_bytes(b"x"))
    result = _import(env, src, "a", "c", collection="outfit")
    assert result.relative_path == "authoring/reference_library/assets/characters/c/a.png"
    assert "outfit" not in result.relative_path
    assert result.record.collection == "outfit"


@pytest.mark.parametrize("character_id", ["TEST_NEW_CHARACTER", "ZZ-999_UNUSUAL"])
def test_arbitrary_future_character_id(env, character_id):
    src = env["write_source"]("n.png", png_bytes(b"x"))
    result = _import(env, src, "a", character_id)
    assert result.record.character_id == character_id
    assert result.status == IMPORTED


# ---------------------------------------------------------------------------
# Rollback / fail-closed
# ---------------------------------------------------------------------------


def test_manifest_write_failure_rolls_back_only_new_destination(env, monkeypatch):
    src1 = env["write_source"]("n1.png", png_bytes(b"x"))
    src2 = env["write_source"]("n2.png", png_bytes(b"y"))
    _import(env, src1, "a", "c")
    dest_a = env["root"] / "authoring/reference_library/assets/characters/c/a.png"
    assert dest_a.exists()

    from services.reference_library import importer as imp

    def boom(manifest_path, records):
        raise OSError("manifest write failed")

    monkeypatch.setattr(imp, "save_manifest", boom)

    with pytest.raises(OSError):
        _import(env, src2, "b", "c")

    assert not (env["root"] / "authoring/reference_library/assets/characters/c/b.png").exists()
    assert dest_a.exists()
    assert len(load_manifest(env["manifest"])) == 1


def test_failed_copy_leaves_manifest_unchanged(env, monkeypatch):
    src = env["write_source"]("n.png", png_bytes(b"x"))

    from services.reference_library import importer as imp

    def boom(data, expected_sha, dest):
        raise OSError("copy failed")

    monkeypatch.setattr(imp, "_atomic_copy_verified", boom)

    with pytest.raises(OSError):
        _import(env, src, "a", "c")

    assert not env["manifest"].exists()


def test_no_source_deletion_or_move(env):
    data = png_bytes(b"x")
    src = env["write_source"]("n.png", data)
    _import(env, src, "a", "c")
    assert src.exists()
    assert src.read_bytes() == data


# ---------------------------------------------------------------------------
# No production-character hardcodes
# ---------------------------------------------------------------------------


def test_no_production_character_hardcodes():
    import services.reference_library.importer as imp
    import services.reference_library.model as model

    src = Path(imp.__file__).read_text(encoding="utf-8")
    src += Path(model.__file__).read_text(encoding="utf-8")
    for name in ("kira", "sergey", "egor", "olga", "marina", "maksim", "nika"):
        assert name not in src


# ---------------------------------------------------------------------------
# CLI smoke (thin wrapper only)
# ---------------------------------------------------------------------------


def test_cli_import_smoke(env, capsys):
    from tools.reference_library_import import main as cli_main

    src = env["write_source"]("n.png", png_bytes(b"x"))
    code = cli_main(
        ["import", "--source", str(src), "--asset-id", "a", "--character-id", "c"],
        repo_root=env["root"],
        manifest_path=env["manifest"],
    )
    assert code == 0
    assert "IMPORTED" in capsys.readouterr().out
