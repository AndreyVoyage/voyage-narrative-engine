#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CRP MVP S2A -- RoleTask / RoleResult contract tests."""

from __future__ import annotations

import pytest

from services.crp_authoring import CompletionStatus

from tests.crp_authoring.conftest import make_role_result, make_role_task


class TestRoleTask:
    def test_revision_round_0_1_2_accepted(self) -> None:
        for r in (0, 1, 2):
            assert make_role_task(revision_round=r).revision_round == r

    def test_revision_round_out_of_range_rejected(self) -> None:
        for r in (-1, 3):
            with pytest.raises(Exception):
                make_role_task(revision_round=r)

    def test_empty_task_id_rejected(self) -> None:
        with pytest.raises(Exception):
            make_role_task(task_id="")

    def test_immutable_frozen(self) -> None:
        task = make_role_task()
        with pytest.raises(Exception):
            task.task_goal = "mutated"  # type: ignore[misc]


class TestActivationAuthorization:
    def test_non_gated_role_defaults_none(self) -> None:
        task = make_role_task(role_id="R2")
        assert task.activation_authorization_ref is None

    def test_r3_requires_activation_authorization_ref(self) -> None:
        with pytest.raises(Exception):
            make_role_task(role_id="R3")

    def test_r3_accepted_with_ref(self) -> None:
        task = make_role_task(role_id="R3", activation_authorization_ref="owner-signoff-001")
        assert task.activation_authorization_ref == "owner-signoff-001"

    def test_r3_rejects_blank_ref(self) -> None:
        with pytest.raises(Exception):
            make_role_task(role_id="R3", activation_authorization_ref="   ")

    def test_non_string_ref_rejected(self) -> None:
        with pytest.raises(Exception):
            make_role_task(role_id="R3", activation_authorization_ref=123)  # type: ignore[arg-type]


class TestRoleResult:
    def test_completion_status_vocabulary(self) -> None:
        assert [s.value for s in CompletionStatus] == [
            "COMPLETE", "INSUFFICIENT_EVIDENCE", "BLOCKED", "NEEDS_CLARIFICATION",
        ]

    def test_immutable_frozen(self) -> None:
        result = make_role_result()
        with pytest.raises(Exception):
            result.completion_status = CompletionStatus.BLOCKED  # type: ignore[misc]

    def test_additional_new_source_evidence_defaults_empty(self) -> None:
        result = make_role_result()
        assert result.new_source_evidence == ()

    def test_no_hidden_chain_of_thought(self) -> None:
        # provenance_summary records what was used, not how the role reasoned.
        result = make_role_result(provenance_summary={"used_evidence": ["se-001"]})
        assert result.provenance_summary == {"used_evidence": ["se-001"]}
        assert not hasattr(result, "chain_of_thought")
        assert not hasattr(result, "reasoning")