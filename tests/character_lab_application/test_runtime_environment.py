"""Pinned VCP runtime gate — deterministic, offline parts (no VCP import)."""

from __future__ import annotations

import importlib.util

import pytest

from services.character_lab_application.runtime_environment import (
    PINNED_SOURCE_COMMIT,
    PinnedVcpDependencyError,
    _load_provenance,
    pinned_vcp_identity,
    pinned_vcp_site_packages,
)

EXPECTED_WHEEL_SHA256 = "58c05ae065e0c0a400a53e73241e5fed2aee6b3a30c149071d17e06aa9126cee"


def test_site_packages_path_is_under_build_output():
    path = pinned_vcp_site_packages()
    parts = path.parts
    assert path.name == "site-packages"
    assert "build" in parts and "output" in parts
    assert "lab_vcp_env" in parts


def test_provenance_pin_matches_expected():
    provenance = _load_provenance()
    assert provenance["source_commit"] == PINNED_SOURCE_COMMIT
    assert provenance["dependency_name"] == "voyage-character-platform"
    assert provenance["dependency_version"] == "0.1.0"
    assert provenance["wheel_sha256"] == EXPECTED_WHEEL_SHA256


def test_missing_vcp_fails_closed():
    if importlib.util.find_spec("voyage_character_platform") is not None:
        pytest.skip("ambient VCP present; cannot exercise missing-VCP path")
    with pytest.raises(PinnedVcpDependencyError):
        pinned_vcp_identity()
