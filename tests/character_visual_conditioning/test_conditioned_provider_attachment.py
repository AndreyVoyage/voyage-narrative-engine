#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline tests for the generic bundle -> conditioned-provider attachment (RC3).

    NETWORK_CALLS = 0
    PROVIDER_CALLS = 0
    IMAGE_GENERATION = 0
    CANON_REREADS = 0
    CANON_FILE_REOPENS = 0

The adapter consumes ReferenceBundle ``payload`` bytes directly and never
reopens Character Canon files. The HTTP transport is intercepted before any
outbound network, mirroring the existing C3 test pattern.
"""

from __future__ import annotations

import base64
import dataclasses
import hashlib
import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from services.character_visual_conditioning import (  # noqa: E402
    REFERENCE_BUNDLE_SCHEMA_VERSION,
    ConditionedImage,
    ProviderInputConfigurationError,
    ReferenceBinaryError,
    ReferenceBundle,
    ReferenceCharacterGroup,
    ReferenceEntry,
    ReferenceImageInput,
    build_reference_map,
    compute_content_hash,
    generate_conditioned_image_from_bundle,
    reference_inputs_from_bundle,
)

_PNG = b"\x89PNG\r\n\x1a\n" + b"A" * 32
_JPEG = b"\xff\xd8\xff" + b"B" * 32
_WEBP = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"C" * 32

_MODEL = "gpt-image-2"
_ORIGINAL_PROMPT = "CHAR_A and CHAR_B in the yoga hall."


def _detect(payload):
    if payload.startswith(b"\x89PNG\r\n\x1a\n"):
        return "PNG", "image/png"
    if payload.startswith(b"\xff\xd8\xff"):
        return "JPEG", "image/jpeg"
    if len(payload) >= 12 and payload[:4] == b"RIFF" and payload[8:12] == b"WEBP":
        return "WEBP", "image/webp"
    raise AssertionError("unsupported test payload")


def _entry(character_id, roles, path, payload):
    fmt, content_type = _detect(payload)
    return ReferenceEntry(
        character_id=character_id,
        roles=tuple(roles),
        path=path,
        image_format=fmt,
        content_type=content_type,
        sha256=hashlib.sha256(payload).hexdigest(),
        byte_length=len(payload),
        payload=payload,
    )


def _group(character_id, entries, status="PENDING_APPROVAL"):
    return ReferenceCharacterGroup(
        character_id=character_id,
        status=status,
        canon_content_hash=f"canon_hash_{character_id.lower()}",
        references=tuple(entries),
    )


def _bundle(groups):
    provisional = ReferenceBundle(
        schema_version=REFERENCE_BUNDLE_SCHEMA_VERSION,
        character_groups=tuple(groups),
        content_hash="",
    )
    content_hash = compute_content_hash(provisional.semantic_payload())
    return dataclasses.replace(provisional, content_hash=content_hash)


class _FakeResponse:
    def __init__(self, raw):
        self._raw = raw

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._raw


def _b64_response(payload=_PNG):
    return json.dumps(
        {"data": [{"b64_json": base64.b64encode(payload).decode("ascii")}]}
    ).encode("utf-8")


def _patch_transport(monkeypatch, raw=None):
    calls = []

    monkeypatch.setattr(
        "services.character_visual_conditioning.provider._get_ssl_context",
        lambda: None,
    )

    def fake_urlopen(request, timeout=None, context=None):
        calls.append(request)
        return _FakeResponse(raw if raw is not None else _b64_response())

    monkeypatch.setattr(
        "services.character_visual_conditioning.provider.urllib.request.urlopen",
        fake_urlopen,
    )
    return calls


def _parse_map(refmap):
    lines = refmap.split("\n")
    assert lines[0] == "[REFERENCE MAP]"
    blocks = {}
    current = None
    for line in lines[1:]:
        if line.startswith("image["):
            current = line.rstrip(":")
            blocks[current] = {}
        elif line == "":
            continue
        elif "=" in line:
            key, value = line.split("=", 1)
            blocks[current][key] = value
    return blocks


def test_single_character_request_shape(monkeypatch):
    bundle = _bundle(
        [_group("CHAR_A", [_entry("CHAR_A", ["face_canon"], "char_a/face.png", _PNG)])]
    )
    calls = _patch_transport(monkeypatch)
    result = generate_conditioned_image_from_bundle(
        prompt=_ORIGINAL_PROMPT,
        reference_bundle=bundle,
        model=_MODEL,
        api_key="sk-test",
        base_url="https://api.example.invalid",
    )
    assert len(calls) == 1
    req = calls[0]
    assert req.full_url == "https://api.example.invalid/v1/images/edits"
    assert req.method == "POST"
    assert req.get_header("Content-type").startswith(
        "multipart/form-data; boundary="
    )
    body = req.data
    assert b'name="model"' in body and _MODEL.encode("utf-8") in body
    assert b'name="n"' in body and b"1" in body
    assert b'name="size"' in body and b"1024x1024" in body
    assert b'name="quality"' in body and b"low" in body
    assert body.count(b'name="image[]"') == 1
    assert _PNG in body
    assert b"Content-Type: image/png" in body
    assert b'filename="ref_000_CHAR_A.png"' in body
    assert b"[REFERENCE MAP]" in body
    assert b"character_id=CHAR_A" in body
    assert b"roles=face_canon" in body
    assert b"source=char_a/face.png" in body
    assert isinstance(result, ConditionedImage)


def test_two_character_request_attachment_order_and_ownership(monkeypatch):
    bundle = _bundle(
        [
            _group(
                "CHAR_A",
                [
                    _entry(
                        "CHAR_A",
                        ["primary_face_reference", "face_canon"],
                        "char_a/face.png",
                        _PNG,
                    ),
                    _entry("CHAR_A", ["body_canon_a"], "char_a/body.png", _JPEG),
                ],
            ),
            _group(
                "CHAR_B",
                [_entry("CHAR_B", ["primary_face_reference"], "char_b/face.png", _WEBP)],
            ),
        ]
    )
    calls = _patch_transport(monkeypatch)
    generate_conditioned_image_from_bundle(
        prompt=_ORIGINAL_PROMPT,
        reference_bundle=bundle,
        model=_MODEL,
        api_key="sk-test",
        base_url="https://api.example.invalid",
    )
    body = calls[0].data
    assert body.count(b'name="image[]"') == 3
    assert b'filename="ref_000_CHAR_A.png"' in body
    assert b'filename="ref_001_CHAR_A.jpg"' in body
    assert b'filename="ref_002_CHAR_B.webp"' in body
    assert _PNG in body and _JPEG in body and _WEBP in body
    assert b"Content-Type: image/png" in body
    assert b"Content-Type: image/jpeg" in body
    assert b"Content-Type: image/webp" in body


def test_three_character_generic_request(monkeypatch):
    ids = ["CHAR_A", "ZZ-999_UNUSUAL", "CHAR_C"]
    groups = [
        _group(cid, [_entry(cid, ["face_canon"], f"{cid}/face.png", _PNG)])
        for cid in ids
    ]
    bundle = _bundle(groups)
    calls = _patch_transport(monkeypatch)
    generate_conditioned_image_from_bundle(
        prompt=_ORIGINAL_PROMPT,
        reference_bundle=bundle,
        model=_MODEL,
        api_key="sk-test",
        base_url="https://api.example.invalid",
    )
    body = calls[0].data
    assert body.count(b'name="image[]"') == 3
    assert b'filename="ref_000_CHAR_A.png"' in body
    assert b'filename="ref_001_ZZ-999_UNUSUAL.png"' in body
    assert b'filename="ref_002_CHAR_C.png"' in body


def test_future_character_request_unchanged(monkeypatch):
    bundle = _bundle(
        [
            _group(
                "TEST_FUTURE_9000",
                [_entry("TEST_FUTURE_9000", ["face_canon"], "future/face.png", _PNG)],
            )
        ]
    )
    calls = _patch_transport(monkeypatch)
    generate_conditioned_image_from_bundle(
        prompt=_ORIGINAL_PROMPT,
        reference_bundle=bundle,
        model=_MODEL,
        api_key="sk-test",
        base_url="https://api.example.invalid",
    )
    body = calls[0].data
    assert b"character_id=TEST_FUTURE_9000" in body
    assert b'filename="ref_000_TEST_FUTURE_9000.png"' in body
    assert _PNG in body



def test_empty_bundle_fails_before_http(monkeypatch):
    bundle = _bundle([])
    calls = _patch_transport(monkeypatch)
    with pytest.raises(ProviderInputConfigurationError):
        generate_conditioned_image_from_bundle(
            prompt=_ORIGINAL_PROMPT,
            reference_bundle=bundle,
            model=_MODEL,
            api_key="sk-test",
            base_url="https://api.example.invalid",
        )
    assert len(calls) == 0


def test_zero_entry_bundle_fails_before_http(monkeypatch):
    bundle = _bundle([_group("CHAR_A", [])])
    calls = _patch_transport(monkeypatch)
    with pytest.raises(ProviderInputConfigurationError):
        generate_conditioned_image_from_bundle(
            prompt=_ORIGINAL_PROMPT,
            reference_bundle=bundle,
            model=_MODEL,
            api_key="sk-test",
            base_url="https://api.example.invalid",
        )
    assert len(calls) == 0


def test_integrity_failure_fails_before_http(monkeypatch):
    bad = ReferenceEntry(
        character_id="CHAR_A",
        roles=("face_canon",),
        path="char_a/face.png",
        image_format="PNG",
        content_type="image/png",
        sha256=hashlib.sha256(_PNG).hexdigest(),
        byte_length=len(_PNG) + 5,  # inconsistent with payload length
        payload=_PNG,
    )
    bundle = _bundle([_group("CHAR_A", [bad])])
    calls = _patch_transport(monkeypatch)
    with pytest.raises(ReferenceBinaryError):
        generate_conditioned_image_from_bundle(
            prompt=_ORIGINAL_PROMPT,
            reference_bundle=bundle,
            model=_MODEL,
            api_key="sk-test",
            base_url="https://api.example.invalid",
        )
    assert len(calls) == 0


def test_empty_prompt_preserves_existing_behavior(monkeypatch):
    bundle = _bundle(
        [_group("CHAR_A", [_entry("CHAR_A", ["face_canon"], "char_a/face.png", _PNG)])]
    )
    calls = _patch_transport(monkeypatch)
    with pytest.raises(ProviderInputConfigurationError):
        generate_conditioned_image_from_bundle(
            prompt="   ",
            reference_bundle=bundle,
            model=_MODEL,
            api_key="sk-test",
            base_url="https://api.example.invalid",
        )
    assert len(calls) == 0



def test_original_prompt_unchanged_and_effective_has_map(monkeypatch):
    bundle = _bundle(
        [_group("CHAR_A", [_entry("CHAR_A", ["face_canon"], "char_a/face.png", _PNG)])]
    )
    original = _ORIGINAL_PROMPT
    calls = _patch_transport(monkeypatch)
    generate_conditioned_image_from_bundle(
        prompt=original,
        reference_bundle=bundle,
        model=_MODEL,
        api_key="sk-test",
        base_url="https://api.example.invalid",
    )
    assert original == _ORIGINAL_PROMPT  # upstream prompt never mutated
    body = calls[0].data
    assert _ORIGINAL_PROMPT.encode("utf-8") in body
    assert b"[REFERENCE MAP]" in body


def test_reference_map_exact_content():
    bundle = _bundle(
        [
            _group(
                "CHAR_A",
                [
                    _entry(
                        "CHAR_A",
                        ["primary_face_reference", "face_canon"],
                        "char_a/face.png",
                        _PNG,
                    )
                ],
            ),
            _group(
                "CHAR_B",
                [_entry("CHAR_B", ["primary_face_reference"], "char_b/face.png", _JPEG)],
            ),
        ]
    )
    expected = (
        "[REFERENCE MAP]\n"
        "image[0]:\n"
        "character_id=CHAR_A\n"
        "roles=primary_face_reference,face_canon\n"
        "source=char_a/face.png\n"
        "\n"
        "image[1]:\n"
        "character_id=CHAR_B\n"
        "roles=primary_face_reference\n"
        "source=char_b/face.png"
    )
    assert build_reference_map(bundle) == expected


def test_reference_inputs_from_bundle_uses_payload_bytes():
    bundle = _bundle(
        [
            _group("CHAR_A", [_entry("CHAR_A", ["face_canon"], "char_a/face.png", _PNG)]),
            _group("CHAR_B", [_entry("CHAR_B", ["face_canon"], "char_b/face.png", _JPEG)]),
        ]
    )
    inputs = reference_inputs_from_bundle(bundle)
    assert [i.filename for i in inputs] == ["ref_000_CHAR_A.png", "ref_001_CHAR_B.jpg"]
    assert [i.content_type for i in inputs] == ["image/png", "image/jpeg"]
    assert inputs[0].payload == _PNG
    assert inputs[1].payload == _JPEG
    assert isinstance(inputs[0], ReferenceImageInput)


def test_reference_map_deterministic():
    bundle = _bundle(
        [
            _group(
                "CHAR_A",
                [
                    _entry("CHAR_A", ["face_canon"], "char_a/face.png", _PNG),
                    _entry("CHAR_A", ["body_canon_a"], "char_a/body.png", _JPEG),
                ],
            )
        ]
    )
    assert build_reference_map(bundle) == build_reference_map(bundle)


def test_b4_offline_shadow_two_character_multi_ref(monkeypatch):
    bundle = _bundle(
        [
            _group(
                "CHAR_A",
                [
                    _entry("CHAR_A", ["primary_face_reference"], "char_a/face.png", _PNG),
                    _entry("CHAR_A", ["body_canon_a"], "char_a/body.png", _JPEG),
                ],
            ),
            _group(
                "CHAR_B",
                [
                    _entry("CHAR_B", ["primary_face_reference"], "char_b/face.png", _WEBP),
                    _entry("CHAR_B", ["body_canon_a"], "char_b/body.png", _PNG),
                ],
            ),
        ]
    )
    calls = _patch_transport(monkeypatch)
    generate_conditioned_image_from_bundle(
        prompt=_ORIGINAL_PROMPT,
        reference_bundle=bundle,
        model=_MODEL,
        api_key="sk-test",
        base_url="https://api.example.invalid",
    )
    body = calls[0].data
    image_count = body.count(b'name="image[]"')
    assert image_count == 4
    assert image_count > 0

    blocks = _parse_map(build_reference_map(bundle))
    assert len(blocks) == 4
    for key, meta in blocks.items():
        assert key.startswith("image[")
        assert "character_id" in meta
        assert "roles" in meta
        assert "source" in meta
