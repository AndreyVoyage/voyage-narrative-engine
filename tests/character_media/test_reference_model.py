#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ReferenceBinding / reference-role validation tests (no VCP required)."""

from __future__ import annotations

import pytest

from services.character_media import (
    REFERENCE_ROLES,
    InvalidBindingError,
    MediaPublishability,
    ReferenceBinding,
    reference_role_package_token,
    validate_visual_identity_references,
)


def _binding(**overrides) -> dict:
    data = {
        "role": "face",
        "asset_sha256": "a" * 64,
        "format": "PNG",
        "mime_type": "image/png",
        "byte_length": 10,
        "publishability": "PUBLISHABLE",
    }
    data.update(overrides)
    return data


def test_reference_roles_vocabulary() -> None:
    assert REFERENCE_ROLES == ("face", "body", "expression", "identity", "motion")


def test_package_tokens() -> None:
    assert reference_role_package_token("face") == "FACE"
    assert reference_role_package_token("body") == "BODY"
    assert reference_role_package_token("expression") == "EXPRESSION"
    assert reference_role_package_token("identity") == "IDENTITY"
    assert reference_role_package_token("motion") == "MOTION"


def test_package_token_unknown_role_fails_closed() -> None:
    with pytest.raises(InvalidBindingError):
        reference_role_package_token("pose")


def test_binding_roundtrip() -> None:
    binding = ReferenceBinding.from_dict(_binding())
    assert binding.role == "face"
    assert binding.publishability is MediaPublishability.PUBLISHABLE
    assert binding.package_token == "FACE"
    assert ReferenceBinding.from_dict(binding.to_dict()) == binding


def test_each_role_constructs() -> None:
    for role in REFERENCE_ROLES:
        binding = ReferenceBinding.from_dict(_binding(role=role))
        assert binding.role == role


def test_authoring_only_roundtrip() -> None:
    binding = ReferenceBinding.from_dict(_binding(publishability="AUTHORING_ONLY"))
    assert binding.publishability is MediaPublishability.AUTHORING_ONLY


def test_unknown_role_fails_closed() -> None:
    with pytest.raises(InvalidBindingError):
        ReferenceBinding.from_dict(_binding(role="pose"))


def test_unknown_publishability_fails_closed() -> None:
    with pytest.raises(InvalidBindingError):
        ReferenceBinding.from_dict(_binding(publishability="BOGUS"))


def test_extra_key_rejected() -> None:
    with pytest.raises(InvalidBindingError):
        ReferenceBinding.from_dict(_binding(extra=True))


def test_missing_field_rejected() -> None:
    data = _binding()
    del data["byte_length"]
    with pytest.raises(InvalidBindingError):
        ReferenceBinding.from_dict(data)


def test_sha256_must_be_lowercase_hex() -> None:
    with pytest.raises(InvalidBindingError):
        ReferenceBinding.from_dict(_binding(asset_sha256="A" * 64))


def test_mime_must_match_format() -> None:
    with pytest.raises(InvalidBindingError):
        ReferenceBinding.from_dict(_binding(mime_type="image/jpeg"))


def test_non_object_rejected() -> None:
    with pytest.raises(InvalidBindingError):
        ReferenceBinding.from_dict("not-an-object")


# -- validate_visual_identity_references ---------------------------------


def test_validate_absent_is_noop() -> None:
    validate_visual_identity_references(None)
    validate_visual_identity_references({})
    validate_visual_identity_references({"primary_portrait": {}})


def test_validate_empty_list_is_noop() -> None:
    validate_visual_identity_references({"references": []})


def test_validate_valid_managed_references() -> None:
    validate_visual_identity_references(
        {"references": [_binding(role="face"), _binding(role="identity")]}
    )


def test_validate_unknown_role_fails_closed() -> None:
    with pytest.raises(InvalidBindingError):
        validate_visual_identity_references({"references": [_binding(role="pose")]})


def test_validate_unknown_publishability_fails_closed() -> None:
    with pytest.raises(InvalidBindingError):
        validate_visual_identity_references(
            {"references": [_binding(publishability="BOGUS")]}
        )


def test_validate_malformed_managed_fails_closed() -> None:
    with pytest.raises(InvalidBindingError):
        validate_visual_identity_references({"references": [{"role": "face"}]})


def test_validate_non_list_rejected() -> None:
    with pytest.raises(InvalidBindingError):
        validate_visual_identity_references({"references": "face"})


def test_validate_legacy_path_reference_left_open() -> None:
    # Legacy/unresolved Canon {key, path} reference is NOT silently
    # reinterpreted as a managed binding at the authoring boundary.
    validate_visual_identity_references(
        {"references": [{"key": "legacy", "path": "characters/x/face.png"}]}
    )


def test_validate_unrelated_keys_stay_open() -> None:
    validate_visual_identity_references(
        {"references": [], "future_extension": {"anything": True}}
    )


def test_duplicate_identical_binding_rejected() -> None:
    # Same (role, asset_sha256) twice inside one revision is a structural
    # duplicate and must fail closed at the authoring boundary.
    with pytest.raises(InvalidBindingError):
        validate_visual_identity_references(
            {"references": [_binding(role="face"), _binding(role="face")]}
        )


def test_same_sha_different_roles_allowed() -> None:
    sha = "b" * 64
    validate_visual_identity_references(
        {
            "references": [
                _binding(role="face", asset_sha256=sha),
                _binding(role="identity", asset_sha256=sha),
            ]
        }
    )


def test_same_role_different_sha_allowed() -> None:
    validate_visual_identity_references(
        {
            "references": [
                _binding(role="face", asset_sha256="a" * 64),
                _binding(role="face", asset_sha256="b" * 64),
            ]
        }
    )
