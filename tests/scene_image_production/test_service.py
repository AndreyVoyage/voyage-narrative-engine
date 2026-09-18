#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Focused tests for services.scene_image_production -- the first production
application-service entry point wiring REAL approved Character Canon into
the existing character_visual_conditioning generation path.

No live network / provider calls anywhere in this file: the provider seam is
always an explicit, injected call-counting stub.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from services.character_canon_bridge import (
    CanonRootMissingError,
    CharacterNotFoundError,
    ProductionNotAllowedError,
)
from services.character_visual_conditioning import ConditionedImage
from services.scene_image_production import (
    ProductionSceneImageRequest,
    generate_production_scene_image,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Fixtures / helpers (self-contained; mirrors the pattern used in
# tests/character_canon_bridge/conftest.py without cross-importing it).
# ---------------------------------------------------------------------------


def _write_preset(canon_root: Path, character_id: str, payload: dict[str, Any]) -> None:
    char_dir = canon_root / "AI_CHARACTERS" / character_id / "10_notes"
    char_dir.mkdir(parents=True, exist_ok=True)
    (char_dir / f"{character_id}_REFERENCE_PRESETS.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )


def _write_png(canon_root: Path, relative_path: str) -> None:
    full = canon_root / relative_path
    full.parent.mkdir(parents=True, exist_ok=True)
    # Minimal valid PNG magic bytes + a little payload so format sniffing succeeds.
    full.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)


def _preset(character_id: str, status: str) -> dict[str, Any]:
    return {
        "character": character_id,
        "active_version": "v1",
        "status": status,
        "active_canon": {
            "primary_face_reference": (
                f"AI_CHARACTERS/{character_id}/03_face_sheet/face.png"
            ),
        },
        "scene_presets": {},
    }


def _approved_canon_root(tmp_path: Path, character_id: str = "TESTCHAR") -> Path:
    canon_root = tmp_path / "canon"
    _write_preset(canon_root, character_id, _preset(character_id, "APPROVED_AS_CANON"))
    _write_png(canon_root, f"AI_CHARACTERS/{character_id}/03_face_sheet/face.png")
    return canon_root


class _CountingProvider:
    """Injected provider stub: records call count and exact kwargs, never
    touches the network."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def __call__(self, **kwargs: Any) -> ConditionedImage:
        self.calls.append(kwargs)
        return ConditionedImage(
            payload=b"fake-image-bytes",
            payload_sha256=hashlib.sha256(b"fake-image-bytes").hexdigest(),
            content_type="image/png",
            model=kwargs["model"],
        )


def _request(canon_root: Path, character_id: str, **overrides: Any) -> ProductionSceneImageRequest:
    fields: dict[str, Any] = dict(
        canon_root=canon_root,
        character_id=character_id,
        prompt="a test prompt",
        model="test-model",
    )
    fields.update(overrides)
    return ProductionSceneImageRequest(**fields)


# ---------------------------------------------------------------------------
# 2. Non-APPROVED_AS_CANON character fails before provider invocation.
# ---------------------------------------------------------------------------


def test_non_approved_canon_fails_closed_before_provider_call(tmp_path: Path) -> None:
    canon_root = tmp_path / "canon"
    _write_preset(canon_root, "PENDING_ONE", _preset("PENDING_ONE", "PENDING_APPROVAL"))
    _write_png(canon_root, "AI_CHARACTERS/PENDING_ONE/03_face_sheet/face.png")
    provider = _CountingProvider()

    with pytest.raises(ProductionNotAllowedError):
        generate_production_scene_image(
            _request(canon_root, "PENDING_ONE"), provider_call=provider
        )

    assert provider.calls == []


# ---------------------------------------------------------------------------
# 3. Missing character fails before provider invocation.
# ---------------------------------------------------------------------------


def test_missing_character_fails_closed_before_provider_call(tmp_path: Path) -> None:
    canon_root = _approved_canon_root(tmp_path, character_id="OTHER_ONE")
    provider = _CountingProvider()

    with pytest.raises(CharacterNotFoundError):
        generate_production_scene_image(
            _request(canon_root, "NO_SUCH_CHARACTER"), provider_call=provider
        )

    assert provider.calls == []


# ---------------------------------------------------------------------------
# 4. Invalid/nonexistent Canon root fails before provider invocation.
# ---------------------------------------------------------------------------


def test_invalid_canon_root_fails_closed_before_provider_call(tmp_path: Path) -> None:
    nonexistent = tmp_path / "does_not_exist"
    provider = _CountingProvider()

    with pytest.raises(CanonRootMissingError):
        generate_production_scene_image(
            _request(nonexistent, "ANYONE"), provider_call=provider
        )

    assert provider.calls == []


# ---------------------------------------------------------------------------
# 5 + 6. Character ownership preserved through reference selection/bundle
# creation, and the provider seam receives the validated conditioned bundle
# on the successful path.
# ---------------------------------------------------------------------------


def test_successful_path_preserves_ownership_and_reaches_provider_seam(
    tmp_path: Path,
) -> None:
    canon_root = _approved_canon_root(tmp_path, character_id="TESTCHAR")
    provider = _CountingProvider()

    result = generate_production_scene_image(
        _request(canon_root, "TESTCHAR", prompt="portrait shot", model="edit-model-x"),
        provider_call=provider,
    )

    # Provider called exactly once with the validated bundle and pass-through fields.
    assert len(provider.calls) == 1
    call = provider.calls[0]
    assert call["prompt"] == "portrait shot"
    assert call["model"] == "edit-model-x"
    bundle = call["reference_bundle"]
    assert len(bundle.character_groups) == 1
    group = bundle.character_groups[0]
    assert group.character_id == "TESTCHAR"
    assert group.status == "APPROVED_AS_CANON"
    assert len(group.references) == 1
    assert group.references[0].character_id == "TESTCHAR"

    # Result carries the real hashes for audit/traceability.
    assert result.character_id == "TESTCHAR"
    assert result.reference_bundle_content_hash == bundle.content_hash
    assert result.conditioned_image.model == "edit-model-x"


def test_optional_provider_fields_pass_through_only_when_supplied(
    tmp_path: Path,
) -> None:
    canon_root = _approved_canon_root(tmp_path, character_id="TESTCHAR")
    provider = _CountingProvider()

    generate_production_scene_image(
        _request(canon_root, "TESTCHAR", size="512x512", quality="high"),
        provider_call=provider,
    )

    call = provider.calls[0]
    assert call["size"] == "512x512"
    assert call["quality"] == "high"
    assert "api_key" not in call
    assert "base_url" not in call
    assert "timeout_s" not in call


# ---------------------------------------------------------------------------
# 1. Approved KIRA real Canon resolves in production mode.
# ---------------------------------------------------------------------------


def _real_canon_root_or_skip() -> Path:
    import os

    root = os.environ.get("VNE_CHARACTER_CANON_ROOT")
    if not root:
        pytest.skip("VNE_CHARACTER_CANON_ROOT not set; real KIRA Canon proof skipped")
    path = Path(root)
    if not (path / "AI_CHARACTERS").exists():
        pytest.skip(f"canon root missing AI_CHARACTERS: {root}")
    return path


def test_real_kira_canon_resolves_in_production_mode_no_kira_branching() -> None:
    canon_root = _real_canon_root_or_skip()
    provider = _CountingProvider()

    result = generate_production_scene_image(
        _request(canon_root, "KIRA", prompt="real canon proof"),
        provider_call=provider,
    )

    assert len(provider.calls) == 1
    bundle = provider.calls[0]["reference_bundle"]
    group = bundle.character_groups[0]
    assert group.character_id == "KIRA"
    assert group.status == "APPROVED_AS_CANON"
    assert len(group.references) >= 1
    assert result.character_id == "KIRA"
    assert result.canon_content_hash  # non-empty real Canon content hash


# ---------------------------------------------------------------------------
# 8. tools/scene_image_test_app.py remains unchanged.
# ---------------------------------------------------------------------------


def test_scene_image_test_app_unchanged() -> None:
    result = subprocess.run(
        ["git", "diff", "--stat", "--", "tools/scene_image_test_app.py"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "", (
        "tools/scene_image_test_app.py must remain unchanged by this slice:\n"
        + result.stdout
    )
