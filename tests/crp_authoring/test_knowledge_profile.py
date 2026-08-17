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