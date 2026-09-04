#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Character Core release metadata + Core/Package/Runtime-data boundary."""

from __future__ import annotations

import pytest

from services.character_core.contract import SessionPurpose
from services.character_core.release import (
    CHARACTER_CORE_RELEASE_BOUNDARY,
    CONTRACT_VERSION,
    CORE_VERSION,
    ReleaseArtifactCategory,
    build_core_release_info,
)


class TestCoreReleaseInfo:
    def test_core_version_is_independent_from_package_version(self):
        # Accepted KIRA is package_version=0 (see accepted/kira/ACCEPTANCE.json);
        # Core carries its OWN, unrelated dev version.
        kira_package_version = 0
        assert CORE_VERSION != str(kira_package_version)
        assert CORE_VERSION == "0.1.0-dev"
        assert not CORE_VERSION.startswith("1.0")  # not falsely called 1.0

    def test_contract_version_is_tracked_separately_from_core_version(self):
        info = build_core_release_info(
            supported_session_purposes=(SessionPurpose.TESTING,), capabilities=()
        )
        assert info.core_version == CORE_VERSION
        assert info.contract_version == CONTRACT_VERSION
        # they are independently-named fields, even if coincidentally equal today
        assert hasattr(info, "core_version") and hasattr(info, "contract_version")

    def test_recognized_vs_supported_purposes_are_distinct(self):
        info = build_core_release_info(
            supported_session_purposes=(SessionPurpose.TESTING,), capabilities=()
        )
        assert set(info.recognized_session_purposes) == {
            "TESTING", "AUTHORING", "GAME_RUNTIME", "COMPANION",
        }
        assert info.supported_session_purposes == ("TESTING",)
        assert set(info.supported_session_purposes) < set(info.recognized_session_purposes)

    def test_unrecognized_supported_purpose_rejected(self):
        with pytest.raises(ValueError):
            build_core_release_info(
                supported_session_purposes=("NOT_A_REAL_PURPOSE",), capabilities=()
            )

    def test_source_commit_optional_and_never_fabricated(self):
        info = build_core_release_info(
            supported_session_purposes=(SessionPurpose.TESTING,), capabilities=()
        )
        assert info.source_commit is None
        supplied = build_core_release_info(
            supported_session_purposes=(SessionPurpose.TESTING,), capabilities=(),
            source_commit="deadbeef",
        )
        assert supplied.source_commit == "deadbeef"


class TestReleaseBoundary:
    def test_runtime_mechanism_and_contract_are_core_eligible(self):
        assert CHARACTER_CORE_RELEASE_BOUNDARY.eligible(
            ReleaseArtifactCategory.RUNTIME_MECHANISM
        ) is True
        assert CHARACTER_CORE_RELEASE_BOUNDARY.eligible(
            ReleaseArtifactCategory.SERVICE_CONTRACT
        ) is True
        assert CHARACTER_CORE_RELEASE_BOUNDARY.eligible(
            ReleaseArtifactCategory.RELEASE_METADATA
        ) is True

    def test_runtime_user_data_marked_external(self):
        for category in (
            ReleaseArtifactCategory.RUNTIME_MEMORY_DB,
            ReleaseArtifactCategory.RUNTIME_STATE_DB,
            ReleaseArtifactCategory.WORKSPACE_DATA,
            ReleaseArtifactCategory.SESSION_DATA,
            ReleaseArtifactCategory.SCENE_DATA,
            ReleaseArtifactCategory.TURN_CAPTURE,
            ReleaseArtifactCategory.USER_DATA,
        ):
            assert CHARACTER_CORE_RELEASE_BOUNDARY.eligible(category) is False, category

    def test_accepted_character_package_marked_external(self):
        assert CHARACTER_CORE_RELEASE_BOUNDARY.eligible(
            ReleaseArtifactCategory.ACCEPTED_CHARACTER_PACKAGE
        ) is False

    def test_boundary_is_exhaustive_no_silent_default(self):
        every_category = set(ReleaseArtifactCategory)
        classified = set(CHARACTER_CORE_RELEASE_BOUNDARY.included) | set(
            CHARACTER_CORE_RELEASE_BOUNDARY.excluded
        )
        assert every_category == classified
