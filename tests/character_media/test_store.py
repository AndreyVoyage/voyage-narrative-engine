#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Managed-storage tests for the Character Media slice (no VCP required)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from services.character_media import (
    AnimatedImageError,
    AssetNotFoundError,
    CharacterMediaStore,
    MAX_ASSET_BYTES,
    OversizedAssetError,
    Sha256MismatchError,
    UnsupportedFormatError,
)
from tests.character_media._images import gif, jpeg, png, webp_animated, webp_vp8l


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
def store(tmp_path: Path) -> CharacterMediaStore:
    return CharacterMediaStore(tmp_path / "character_media")


def _write(tmp_path: Path, name: str, data: bytes) -> Path:
    path = tmp_path / name
    path.write_bytes(data)
    return path


def test_import_png(store: CharacterMediaStore, tmp_path: Path) -> None:
    data = png(4, 4)
    record = store.import_portrait(_write(tmp_path, "a.png", data), "synth")
    assert record.format == "PNG"
    assert record.asset_sha256 == sha(data)
    assert store.managed_path("synth", record.asset_sha256, "PNG").is_file()


def test_import_jpeg(store: CharacterMediaStore, tmp_path: Path) -> None:
    data = jpeg(4, 4)
    record = store.import_portrait(_write(tmp_path, "b.jpg", data), "synth")
    assert record.format == "JPEG"


def test_import_static_webp(store: CharacterMediaStore, tmp_path: Path) -> None:
    data = webp_vp8l(4, 4)
    record = store.import_portrait(_write(tmp_path, "c.webp", data), "synth")
    assert record.format == "WEBP"


def test_reject_gif(store: CharacterMediaStore, tmp_path: Path) -> None:
    with pytest.raises(UnsupportedFormatError):
        store.import_portrait(_write(tmp_path, "d.gif", gif()), "synth")


def test_reject_apng(store: CharacterMediaStore, tmp_path: Path) -> None:
    with pytest.raises(AnimatedImageError):
        store.import_portrait(
            _write(tmp_path, "e.png", png(4, 4, animated=True)), "synth"
        )


def test_reject_animated_webp(store: CharacterMediaStore, tmp_path: Path) -> None:
    with pytest.raises(AnimatedImageError):
        store.import_portrait(
            _write(tmp_path, "f.webp", webp_animated(4, 4)), "synth"
        )


def test_source_deletion_does_not_break_managed_asset(
    store: CharacterMediaStore, tmp_path: Path
) -> None:
    data = png(4, 4)
    source = _write(tmp_path, "g.png", data)
    record = store.import_portrait(source, "synth")
    source.unlink()
    assert store.read_portrait_bytes("synth", record.asset_sha256, "PNG") == data


def test_deterministic_sha_and_dedup(store: CharacterMediaStore, tmp_path: Path) -> None:
    data = png(4, 4)
    r1 = store.import_portrait(_write(tmp_path, "h1.png", data), "synth")
    r2 = store.import_portrait(_write(tmp_path, "h2.png", data), "synth")
    assert r1.asset_sha256 == r2.asset_sha256
    assert r1.relative_path == r2.relative_path
    files = list((store.root / "synth").glob("*.png"))
    assert len(files) == 1


def test_tampered_managed_bytes_detected(
    store: CharacterMediaStore, tmp_path: Path
) -> None:
    data = png(4, 4)
    record = store.import_portrait(_write(tmp_path, "i.png", data), "synth")
    path = store.managed_path("synth", record.asset_sha256, "PNG")
    path.write_bytes(path.read_bytes() + b"\x00")
    with pytest.raises(Sha256MismatchError):
        store.read_portrait_bytes("synth", record.asset_sha256, "PNG")


def test_missing_asset(store: CharacterMediaStore) -> None:
    with pytest.raises(AssetNotFoundError):
        store.read_portrait_bytes("synth", "a" * 64, "PNG")


def test_same_physical_asset_reusable(store: CharacterMediaStore, tmp_path: Path) -> None:
    data = png(4, 4)
    record = store.import_portrait(_write(tmp_path, "j.png", data), "synth")
    a = record.binding("PUBLISHABLE")
    b = record.binding("PUBLISHABLE")
    assert a.asset_sha256 == b.asset_sha256 == record.asset_sha256


def test_oversized_source_rejected_before_read(
    store: CharacterMediaStore, tmp_path: Path, monkeypatch
) -> None:
    """Prove the PRE-READ stat guard rejects >64 MiB before read_bytes()."""
    import pathlib

    big = tmp_path / "big.png"
    with open(big, "wb") as handle:
        handle.truncate(MAX_ASSET_BYTES + 1)  # sparse: fast, size > limit

    called: list[bool] = []

    def fail_read(self) -> bytes:  # pragma: no cover - must never be called
        called.append(True)
        raise AssertionError("read_bytes must not be called for an oversized source")

    monkeypatch.setattr(pathlib.Path, "read_bytes", fail_read)
    with pytest.raises(OversizedAssetError):
        store.import_portrait(big, "synth")
    assert not called
