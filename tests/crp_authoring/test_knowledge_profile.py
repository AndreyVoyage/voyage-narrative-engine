#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CRP MVP S2A -- KnowledgeProfile tests."""

from __future__ import annotations

import pytest

from services.crp_authoring import (
    KnowledgeProfile,
    RetrievalPolicy,
    SourceType,
)
from services.crp_authoring.knowledge_profile import forbidden_ref_violation

from tests.crp_authoring.conftest import make_knowledge_profile


class TestKnowledgeProfile:
    def test_minimal_profile(self) -> None:
        profile = make_knowledge_profile()
        assert profile.retrieval_policy is RetrievalPolicy.EXACT_MODULAR_ONLY
        assert profile.allowed_kb_refs == ()
        assert SourceType.OWNER_DIRECT in profile.allowed_source_types

    def test_non_exact_retrieval_policy_rejected(self) -> None:
        with pytest.raises(Exception):
            KnowledgeProfile(
                profile_id="p", role_id="R2", version="v1",
                allowed_kb_refs=(), allowed_source_types=(SourceType.OWNER_DIRECT,),
                forbidden_refs=(), retrieval_policy="WRONG",
            )

    def test_empty_allowed_source_types_rejected(self) -> None:
        with pytest.raises(Exception):
            make_knowledge_profile(allowed_source_types=())

    def test_legacy_kb_auto_inherited_rejected(self) -> None:
        # A legacy/knowledge_base ref without a legacy_kb_reuse record is a
        # structural defect (D-CRP-14), not silently inherited.
        with pytest.raises(Exception):
            make_knowledge_profile(allowed_kb_refs=("knowledge_base/R2/x",))

    def test_frozen(self) -> None:
        profile = make_knowledge_profile()
        with pytest.raises(Exception):
            profile.allowed_kb_refs = ("mutated",)  # type: ignore[misc]


class TestForbiddenRefMatcher:
    """GAP-2 structured-reference matching (content_ref only, bounded syntax)."""

    def test_exact_literal_match_rejected(self) -> None:
        matched = forbidden_ref_violation(
            "personas/kira/profile.json",
            ("personas/kira/profile.json",),
        )
        assert matched == "personas/kira/profile.json"

    def test_descendant_of_prefix_rejected(self) -> None:
        matched = forbidden_ref_violation(
            "personas/kira/profile.json",
            ("personas/kira/**",),
        )
        assert matched == "personas/kira/**"

    def test_prefix_root_itself_rejected(self) -> None:
        matched = forbidden_ref_violation(
            "personas/kira",
            ("personas/kira/**",),
        )
        assert matched == "personas/kira/**"

    def test_windows_backslashes_rejected(self) -> None:
        matched = forbidden_ref_violation(
            r"personas\kira\profile.json",
            ("personas/kira/**",),
        )
        assert matched == "personas/kira/**"

    def test_case_variant_rejected(self) -> None:
        matched = forbidden_ref_violation(
            "Personas/Kira/Profile.json",
            ("personas/kira/**",),
        )
        assert matched == "personas/kira/**"

    def test_near_miss_kira2_allowed(self) -> None:
        assert forbidden_ref_violation(
            "personas/kira2/profile.json",
            ("personas/kira/**",),
        ) is None

    def test_near_miss_kirabyte_allowed(self) -> None:
        assert forbidden_ref_violation(
            "personas/kirabyte/profile.json",
            ("personas/kira/**",),
        ) is None

    def test_empty_forbidden_refs_rejects_nothing(self) -> None:
        assert forbidden_ref_violation("personas/kira/profile.json", ()) is None

    def test_leading_dot_slash_stripped(self) -> None:
        matched = forbidden_ref_violation(
            "./personas/kira/profile.json",
            ("personas/kira/**",),
        )
        assert matched == "personas/kira/**"

    def test_no_hash_free_text_scanning(self) -> None:
        # The matcher never sees provenance/metadata; a raw prose word unrelated
        # to a content_ref path pattern is irrelevant here. Verify the matcher
        # performs structured path comparison, not substring scanning.
        assert forbidden_ref_violation(
            "ref://owner/notes/001",
            ("personas/kira/**",),
        ) is None
