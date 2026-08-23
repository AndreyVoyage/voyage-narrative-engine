#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline tests for Character Visual Reference Conditioning v0 (C3).

Deterministic, hermetic, and fully offline:

    NETWORK_CALLS = 0
    PROVIDER_CALLS = 0
    MEDIA_GENERATION = 0
    CANON_WRITES = 0
    OPENAI_API_KEY_ACCESS = NO

Selection logic is exercised against synthetic in-memory references written
to a temp directory (never the real KIRA Canon). Provider transport is
exercised against a faked ``urllib.request.urlopen``.
"""

from __future__ import annotations

import base64
import dataclasses
import hashlib
import json
import sys
import urllib.error
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from services.character_canon_bridge import (  # noqa: E402
    CanonReference,
    CharacterCanonSnapshot,
    Provenance,
)
from services.character_visual_conditioning import (  # noqa: E402
    ConditionedImage,
    ProviderInputConfigurationError,
    ProviderInputResultError,
    ProviderInputTransportError,
    ReferenceBinaryError,
    ReferenceImageInput,
    ReferenceSelectionError,
    VisualReference,
    VisualReferenceSet,
    build_visual_reference_set,
    generate_conditioned_image,
    reference_inputs_from_set,
    validate_reference_set_integrity,
)

_PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32
_JPEG = b"\xff\xd8\xff" + b"1" * 32
_WEBP = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"2" * 32

_MODEL = "gpt-image-2"
_PROMPT = "KIRA находится в yoga_hall и разминается на беговой дорожке."
_MEDIA_ITEM_ID = "kira_yoga_hall_pilot_image_01"
_PROMPT_ITEM_HASH = "prompt_item_hash_c1_0001"


def _snapshot(character_id="KIRA", references=(), content_hash=None):
    return CharacterCanonSnapshot(
        schema_version="character_canon/0.1",
        character_id=character_id,
        status="PENDING_APPROVAL",
        references=tuple(references),
        content_hash=content_hash or "canon_hash_000",
        provenance=Provenance(
            source_kind="character_canon_reference_presets",
            source_ref=f"AI_CHARACTERS/{character_id}/10_notes/{character_id}_REFERENCE_PRESETS.json",
            source_hash="src_hash",
        ),
        active_version="kira_base_canon_v1.1",
    )


def _write_ref(tmp_path: Path, rel: str, payload: bytes) -> CanonReference:
    full = tmp_path / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_bytes(payload)
    return CanonReference(key=rel.replace("/", "_"), path=rel)


# ---------------------------------------------------------------------------
# Selection: determinism and role preservation
# ---------------------------------------------------------------------------


def test_selection_preserves_order_and_excludes_scene_variants(tmp_path):
    face = _write_ref(tmp_path, "03_face_sheet/face_A.png", _PNG)
    expr = _write_ref(tmp_path, "03_face_sheet/expressions/expr_A.png", _PNG)
    scene = _write_ref(tmp_path, "05_outfits/sports.png", _PNG)
    snap = _snapshot(
        references=[
            CanonReference(key="primary_face_reference", path=face.path),
            CanonReference(key="expression_canon", path=expr.path),
            CanonReference(key="scene:sports:0", path=scene.path),
        ]
    )
    rset = build_visual_reference_set(
        snap,
        canon_root=tmp_path,
        source_media_item_id=_MEDIA_ITEM_ID,
        source_prompt_item_hash=_PROMPT_ITEM_HASH,
    )
    ids = [r.reference_id for r in rset.references]
    assert ids == ["primary_face_reference", "expression_canon"]
    assert any(r.reference_id == "scene:sports:0" for r in rset.references) is False


def test_selection_dedupes_by_path(tmp_path):
    face_a = _write_ref(tmp_path, "03_face_sheet/face_A.png", _PNG)
    snap = _snapshot(
        references=[
            CanonReference(key="primary_face_reference", path=face_a.path),
            CanonReference(key="face_canon", path=face_a.path),
        ]
    )
    rset = build_visual_reference_set(
        snap,
        canon_root=tmp_path,
        source_media_item_id=_MEDIA_ITEM_ID,
        source_prompt_item_hash=_PROMPT_ITEM_HASH,
    )
    assert len(rset.references) == 1
    assert rset.references[0].reference_id == "primary_face_reference"


def test_selection_binds_sha_format_and_length(tmp_path):
    face = _write_ref(tmp_path, "face.png", _PNG)
    snap = _snapshot(references=[CanonReference(key="face_canon", path=face.path)])
    rset = build_visual_reference_set(
        snap,
        canon_root=tmp_path,
        source_media_item_id=_MEDIA_ITEM_ID,
        source_prompt_item_hash=_PROMPT_ITEM_HASH,
    )
    ref = rset.references[0]
    assert ref.image_sha256 == hashlib.sha256(_PNG).hexdigest()
    assert ref.image_format == "PNG"
    assert ref.image_byte_length == len(_PNG)


def test_selection_no_active_references_rejected(tmp_path):
    snap = _snapshot(references=[])
    with pytest.raises(ReferenceSelectionError):
        build_visual_reference_set(
            snap,
            canon_root=tmp_path,
            source_media_item_id=_MEDIA_ITEM_ID,
            source_prompt_item_hash=_PROMPT_ITEM_HASH,
        )


def test_selection_unsupported_format_rejected(tmp_path):
    bad = _write_ref(tmp_path, "bad.bin", b"not-an-image")
    snap = _snapshot(references=[CanonReference(key="face_canon", path=bad.path)])
    with pytest.raises(ReferenceBinaryError):
        build_visual_reference_set(
            snap,
            canon_root=tmp_path,
            source_media_item_id=_MEDIA_ITEM_ID,
            source_prompt_item_hash=_PROMPT_ITEM_HASH,
        )


def test_selection_missing_file_rejected(tmp_path):
    snap = _snapshot(references=[CanonReference(key="face_canon", path="missing.png")])
    with pytest.raises(ReferenceBinaryError):
        build_visual_reference_set(
            snap,
            canon_root=tmp_path,
            source_media_item_id=_MEDIA_ITEM_ID,
            source_prompt_item_hash=_PROMPT_ITEM_HASH,
        )


# ---------------------------------------------------------------------------
# Selection: immutability and portability
# ---------------------------------------------------------------------------


def test_reference_set_is_frozen_and_portable(tmp_path):
    face = _write_ref(tmp_path, "face.png", _PNG)
    snap = _snapshot(references=[CanonReference(key="face_canon", path=face.path)])
    rset = build_visual_reference_set(
        snap,
        canon_root=tmp_path,
        source_media_item_id=_MEDIA_ITEM_ID,
        source_prompt_item_hash=_PROMPT_ITEM_HASH,
    )
    # Frozen dataclass: assignment raises.
    with pytest.raises(dataclasses.FrozenInstanceError):
        rset.content_hash = "x"  # type: ignore[misc]

    blob = json.dumps(rset.to_dict(), ensure_ascii=False, sort_keys=True)
    # operational source_path must NOT leak into portable serialization.
    assert "source_path" not in blob
    assert str(tmp_path).replace("\\", "/") not in blob


def test_reference_set_hash_changes_with_content(tmp_path):
    face_a = _write_ref(tmp_path, "a.png", _PNG)
    face_b = _write_ref(tmp_path, "b.png", _JPEG)
    snap_a = _snapshot(references=[CanonReference(key="face_canon", path=face_a.path)])
    snap_b = _snapshot(references=[CanonReference(key="face_canon", path=face_b.path)])
    ra = build_visual_reference_set(
        snap_a, canon_root=tmp_path,
        source_media_item_id=_MEDIA_ITEM_ID, source_prompt_item_hash=_PROMPT_ITEM_HASH,
    )
    rb = build_visual_reference_set(
        snap_b, canon_root=tmp_path,
        source_media_item_id=_MEDIA_ITEM_ID, source_prompt_item_hash=_PROMPT_ITEM_HASH,
    )
    assert ra.content_hash != rb.content_hash


def test_reference_set_content_hash_binds_source_ids(tmp_path):
    face = _write_ref(tmp_path, "face.png", _PNG)
    snap = _snapshot(references=[CanonReference(key="face_canon", path=face.path)])
    a = build_visual_reference_set(
        snap, canon_root=tmp_path,
        source_media_item_id="item_a", source_prompt_item_hash="hash_a",
    )
    b = build_visual_reference_set(
        snap, canon_root=tmp_path,
        source_media_item_id="item_b", source_prompt_item_hash="hash_a",
    )
    assert a.content_hash != b.content_hash


def test_integrity_check_passes_and_fails(tmp_path):
    face = _write_ref(tmp_path, "face.png", _PNG)
    snap = _snapshot(references=[CanonReference(key="face_canon", path=face.path)])
    rset = build_visual_reference_set(
        snap, canon_root=tmp_path,
        source_media_item_id=_MEDIA_ITEM_ID, source_prompt_item_hash=_PROMPT_ITEM_HASH,
    )
    validate_reference_set_integrity(rset)  # should not raise
    tampered = dataclasses.replace(rset, content_hash="deadbeef")
    with pytest.raises(ReferenceSelectionError):
        validate_reference_set_integrity(tampered)


# ---------------------------------------------------------------------------
# Provider transport: request shape (fake transport)
# ---------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, raw: bytes):
        self._raw = raw

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._raw


def _b64_response(payload: bytes = _PNG):
    return json.dumps(
        {"data": [{"b64_json": base64.b64encode(payload).decode("ascii")}]}
    ).encode("utf-8")


def _patch_transport(monkeypatch, raw: bytes):
    calls: list[object] = []
    monkeypatch.setattr(
        "services.character_visual_conditioning.provider._get_ssl_context",
        lambda: None,
    )

    def fake_urlopen(request, timeout=None, context=None):
        calls.append(request)
        return _FakeResponse(raw)

    monkeypatch.setattr(
        "services.character_visual_conditioning.provider.urllib.request.urlopen",
        fake_urlopen,
    )
    return calls


def _one_image_input() -> ReferenceImageInput:
    return ReferenceImageInput(filename="face.png", content_type="image/png", payload=_PNG)


def test_conditioned_request_endpoint_and_multipart(monkeypatch):
    calls = _patch_transport(monkeypatch, _b64_response())
    result = generate_conditioned_image(
        _PROMPT,
        model=_MODEL,
        reference_images=[_one_image_input()],
        api_key="sk-test",
        base_url="https://api.example.invalid",
    )
    assert len(calls) == 1
    req = calls[0]
    assert req.method == "POST"
    assert req.full_url == "https://api.example.invalid/v1/images/edits"
    assert req.get_header("Content-type").startswith("multipart/form-data; boundary=")
    body = req.data

    # Prompt text unchanged, model explicit, n=1, size, quality=low.
    assert _PROMPT.encode("utf-8") in body
    assert b'name="model"' in body and _MODEL.encode("utf-8") in body
    assert b'name="n"' in body and b"1" in body
    assert b'name="size"' in body and b"1024x1024" in body
    assert b'name="quality"' in body and b"low" in body
    # One explicit image part.
    assert b'name="image[]"' in body
    assert isinstance(result, ConditionedImage)
    assert result.model == _MODEL


def test_conditioned_request_missing_model_rejected(monkeypatch):
    with pytest.raises(ProviderInputConfigurationError):
        generate_conditioned_image(
            _PROMPT,
            model="  ",
            reference_images=[_one_image_input()],
            api_key="sk-test",
        )


def test_conditioned_request_missing_key_rejected(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ProviderInputConfigurationError):
        generate_conditioned_image(
            _PROMPT,
            model=_MODEL,
            reference_images=[_one_image_input()],
        )


def test_conditioned_request_missing_images_rejected(monkeypatch):
    with pytest.raises(ProviderInputConfigurationError):
        generate_conditioned_image(
            _PROMPT,
            model=_MODEL,
            reference_images=[],
            api_key="sk-test",
        )


def test_conditioned_request_single_call_no_retry(monkeypatch):
    calls = _patch_transport(monkeypatch, _b64_response())
    generate_conditioned_image(
        _PROMPT,
        model=_MODEL,
        reference_images=[_one_image_input()],
        api_key="sk-test",
    )
    assert len(calls) == 1


def test_conditioned_url_result_refused(monkeypatch):
    raw = json.dumps({"data": [{"url": "https://example.invalid/img.png"}]}).encode("utf-8")
    calls = _patch_transport(monkeypatch, raw)
    with pytest.raises(ProviderInputResultError):
        generate_conditioned_image(
            _PROMPT,
            model=_MODEL,
            reference_images=[_one_image_input()],
            api_key="sk-test",
        )
    assert len(calls) == 1


def test_conditioned_http_error_terminal_no_retry(monkeypatch):
    calls: list[object] = []
    monkeypatch.setattr(
        "services.character_visual_conditioning.provider._get_ssl_context",
        lambda: None,
    )

    def raise_http(request, timeout=None, context=None):
        calls.append(request)
        raise urllib.error.HTTPError(
            request.full_url, 401, "Unauthorized", {}, _io_bytes()
        )

    monkeypatch.setattr(
        "services.character_visual_conditioning.provider.urllib.request.urlopen",
        raise_http,
    )
    with pytest.raises(ProviderInputTransportError):
        generate_conditioned_image(
            _PROMPT,
            model=_MODEL,
            reference_images=[_one_image_input()],
            api_key="sk-test",
        )
    assert len(calls) == 1


def _io_bytes():
    import io

    return io.BytesIO(b'{"error":{"message":"unauthorized"}}')