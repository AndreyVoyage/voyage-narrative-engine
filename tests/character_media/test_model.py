#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PortraitBinding / MediaPublishability model tests."""

from __future__ import annotations

import pytest

from services.character_media import (
    InvalidBindingError,
    MAX_ASSET_BYTES,
    MediaPublishability,
    PortraitBinding,
    PRIMARY_PORTRAIT_ROLE,
    validate_visual_identity_portrait,
)


def test_binding_roundtrip() -> None:
    binding = PortraitBinding(
        asset_sha256="a" * 64,
        format="PNG",
        mime_type="image/png",
        byte_length=10,
        publishability=MediaPublishability.PUBLISHABLE,
    )
    assert binding.role == PRIMARY_PORTRAIT_ROLE
    data = binding.to_dict()
    assert data["publishability"] == "PUBLISHABLE"
    assert PortraitBinding.from_dict(data) == binding


def test_authoring_only_value_roundtrip() -> None:
    binding = PortraitBinding(
        asset_sha256="b" * 64,
        format="JPEG",
        mime_type="image/jpeg",
        byte_length=12,
        publishability="AUTHORING_ONLY",
    )
    assert binding.publishability is MediaPublishability.AUTHORING_ONLY


def test_unknown_publishability_fails_closed() -> None:
    with pytest.raises(InvalidBindingError):
        PortraitBinding(
            asset_sha256="a" * 64,
            format="PNG",
            mime_type="image/png",
            byte_length=10,
            publishability="BOGUS",
        )


def test_unknown_binding_keys_rejected() -> None:
    with pytest.raises(InvalidBindingError):
        PortraitBinding.from_dict(
            {
                "role": "primary_portrait",
                "asset_sha256": "a" * 64,
                "format": "PNG",
                "mime_type": "image/png",
                "byte_length": 10,
                "publishability": "PUBLISHABLE",
                "extra": True,
            }
        )


def test_role_must_be_primary_portrait() -> None:
    with pytest.raises(InvalidBindingError):
        PortraitBinding(
            asset_sha256="a" * 64,
            format="PNG",
            mime_type="image/png",
            byte_length=10,
            publishability="PUBLISHABLE",
            role="face",
        )


def test_sha256_must_be_lowercase_hex() -> None:
    with pytest.raises(InvalidBindingError):
        PortraitBinding(
            asset_sha256="A" * 64,
            format="PNG",
            mime_type="image/png",
            byte_length=10,
            publishability="PUBLISHABLE",
        )


def test_mime_type_must_match_format() -> None:
    with pytest.raises(InvalidBindingError):
        PortraitBinding(
            asset_sha256="a" * 64,
            format="PNG",
            mime_type="image/jpeg",
            byte_length=10,
            publishability="PUBLISHABLE",
        )


def test_byte_length_over_limit_rejected() -> None:
    with pytest.raises(InvalidBindingError):
        PortraitBinding(
            asset_sha256="a" * 64,
            format="PNG",
            mime_type="image/png",
            byte_length=MAX_ASSET_BYTES + 1,
            publishability="PUBLISHABLE",
        )


def test_validate_visual_identity_portrait_is_open() -> None:
    # visual_identity stays extensible: unknown sibling keys are NOT rejected.
    validate_visual_identity_portrait(
        {"references": [], "future_extension": {"anything": True}}
    )


def test_validate_visual_identity_portrait_absent_is_noop() -> None:
    validate_visual_identity_portrait({"references": []})
    validate_visual_identity_portrait({})
    validate_visual_identity_portrait(None)


def test_validate_visual_identity_portrait_malformed_rejected() -> None:
    with pytest.raises(InvalidBindingError):
        validate_visual_identity_portrait(
            {"primary_portrait": {"bogus": True}}
        )
