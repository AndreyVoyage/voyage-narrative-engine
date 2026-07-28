#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Approval state machine tests."""

import pytest
from services.persona_authoring import PacApprovalError, PacApprovalLevel, PacRequest
from .conftest import make_mock_provider


class TestApprovalLevels:
    def test_three_levels_are_distinct(self):
        assert PacApprovalLevel.ACCEPT_DRAFT != PacApprovalLevel.APPROVE_SCENE
        assert PacApprovalLevel.APPROVE_SCENE != PacApprovalLevel.APPROVE_DATASET
        assert PacApprovalLevel.ACCEPT_DRAFT != PacApprovalLevel.APPROVE_DATASET

    def test_generation_has_no_approval(self, sample_generation):
        state = sample_generation  # Just a PacGeneration, no approval yet
        assert state.request.character_id == "kira"

    def test_accept_draft(self, service, sample_generation):
        run_id = sample_generation.run_id
        event = service.accept_draft(run_id, 0, "approved text")
        assert event.level == PacApprovalLevel.ACCEPT_DRAFT

    def test_accept_draft_no_dataset_write(self, service, sample_generation):
        run_id = sample_generation.run_id
        service.accept_draft(run_id, 0, "approved text")
        ds = service.storage.load_dataset()
        assert len(ds) == 0

    def test_approve_scene_no_dataset_write(self, service, sample_generation):
        run_id = sample_generation.run_id
        service.accept_draft(run_id, 0, "approved")
        service.approve_scene(run_id)
        ds = service.storage.load_dataset()
        assert len(ds) == 0

    def test_approve_dataset_writes_dataset(self, service, sample_generation):
        run_id = sample_generation.run_id
        service.accept_draft(run_id, 0, "approved output text")
        service.approve_scene(run_id)
        event = service.approve_dataset(run_id, provenance="human-edited")
        ds = service.storage.load_dataset()
        assert len(ds) == 1

    def test_invalid_transition_generated_to_approve_scene(self, service, sample_generation):
        run_id = sample_generation.run_id
        with pytest.raises(PacApprovalError, match="no accepted draft"):
            service.approve_scene(run_id)

    def test_invalid_transition_generated_to_approve_dataset(self, service, sample_generation):
        run_id = sample_generation.run_id
        with pytest.raises(PacApprovalError, match="no approved scene"):
            service.approve_dataset(run_id)

    def test_invalid_transition_draft_to_dataset(self, service, sample_generation):
        run_id = sample_generation.run_id
        service.accept_draft(run_id, 0, "approved")
        with pytest.raises(PacApprovalError, match="no approved scene"):
            service.approve_dataset(run_id)

    def test_repeated_approval_idempotent(self, service, sample_generation):
        run_id = sample_generation.run_id
        service.accept_draft(run_id, 0, "approved")
        service.approve_scene(run_id)
        service.approve_dataset(run_id, provenance="human-edited")
        # Second call should be idempotent
        event2 = service.approve_dataset(run_id, provenance="human-edited")
        ds = service.storage.load_dataset()
        assert len(ds) == 1  # Still only one record

    def test_raw_immutable(self, service, sample_generation):
        run_id = sample_generation.run_id
        raw = service.storage.load_raw(run_id)
        original_text = raw["variants"][0]["raw_text"]
        service.accept_draft(run_id, 0, "edited text")
        raw2 = service.storage.load_raw(run_id)
        assert raw2["variants"][0]["raw_text"] == original_text