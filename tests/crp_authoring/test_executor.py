#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CRP MVP S2A -- bounded role executor tests (fake provider only)."""

from __future__ import annotations

import json

import pytest

from services.crp_authoring import (
    CrpError,
    ExecutorError,
    RoleRegistry,
    RoleStatus,
    SourceType,
    execute_role_task,
)
from services.crp_authoring.contracts import VoicePatternLabel
from services.crp_authoring.executor import _assemble_messages, _load_prompt_text

from tests.crp_authoring.conftest import (
    make_fake_provider,
    make_knowledge_profile,
    make_registry_entry,
    make_role_task,
    make_source,
)

# Exact real vNext prompt files (fail-closed prompt assembly requires these).
_R2_PROMPT_REF = "roles/vnext/ROLE_2_PSYCHOLOGICAL_HYPOTHESIS_ANALYST_v1_PROMPT.md"
_R4_PROMPT_REF = "roles/vnext/ROLE_4_VOICE_RECONSTRUCTION_ANALYST_v1_PROMPT.md"


def _r2_result_json(task_id="task-001", role_id="R2", role_version="v1",
                    claim_type="HYPOTHESIS", target="psychology.P2",
                    source_type="OWNER_DIRECT", confidence="POSSIBLE"):
    return json.dumps({
        "task_id": task_id,
        "role_id": role_id,
        "role_version": role_version,
        "completion_status": "COMPLETE",
        "claims": [{
            "claim_id": "c1",
            "subject_id": "char-subject-1",
            "role_id": role_id,
            "claim": "subject is guarded",
            "claim_type": claim_type,
            "source_evidence_ids": ["se-001"],
            "source_type_summary": [source_type],
            "confidence": confidence,
            "rationale_summary": "from evidence",
            "status": "PROPOSED",
            "target_module_or_layer": target,
        }],
        "unknowns": [],
        "contradictions": [],
        "provenance_summary": {"used_evidence": ["se-001"]},
        "requests_for_more_evidence": [],
        "warnings": [],
        "questions_for_r1": [],
        "new_source_evidence": [],
    }, ensure_ascii=False)


def _r2_registry_scope():
    entry = make_registry_entry(role_id="R2", version="v1", prompt_ref=_R2_PROMPT_REF)
    registry = RoleRegistry((entry,))
    profiles = {"profile-r2": make_knowledge_profile(profile_id="profile-r2", role_id="R2")}
    evidence = (make_source(source_id="se-001", source_type=SourceType.OWNER_DIRECT),)
    task = make_role_task(task_id="task-001", role_id="R2", role_version="v1",
                          allowed_evidence_ids=("se-001",))
    return registry, profiles, evidence, task


def _r4_result_json(label=None):
    """R4 voice result JSON, with an optional voice_pattern_label."""
    claim = {
        "claim_id": "v1",
        "subject_id": "char-subject-1",
        "role_id": "R4",
        "claim": "uses clipped sentences",
        "claim_type": "OBSERVATION",
        "source_evidence_ids": ["se-001"],
        "source_type_summary": ["OBSERVATION"],
        "confidence": "KNOWN",
        "rationale_summary": "observed in corpus",
        "status": "PROPOSED",
        "target_module_or_layer": "voice.lexicon",
    }
    if label is not None:
        claim["voice_pattern_label"] = label
    return json.dumps({
        "task_id": "task-004",
        "role_id": "R4",
        "role_version": "v1",
        "completion_status": "COMPLETE",
        "claims": [claim],
        "unknowns": [],
        "contradictions": [],
        "provenance_summary": {"used_evidence": ["se-001"]},
        "requests_for_more_evidence": [],
        "warnings": [],
        "questions_for_r1": [],
        "new_source_evidence": [],
    }, ensure_ascii=False)


def _r4_registry_scope():
    entry = make_registry_entry(role_id="R4", version="v1", prompt_ref=_R4_PROMPT_REF)
    registry = RoleRegistry((entry,))
    profiles = {"profile-r4": make_knowledge_profile(profile_id="profile-r4", role_id="R4")}
    # OBSERVATION is a direct source type; R4 profile must allow it.
    evidence = (make_source(source_id="se-001", source_type=SourceType.OBSERVATION),)
    task = make_role_task(task_id="task-004", role_id="R4", role_version="v1",
                          allowed_evidence_ids=("se-001",))
    return registry, profiles, evidence, task


class TestExecutor:
    def test_fake_provider_executes_and_returns_result(self) -> None:
        registry, profiles, evidence, task = _r2_registry_scope()
        provider = make_fake_provider(_r2_result_json())
        result = execute_role_task(task, registry, profiles, provider, evidence)
        assert result.task_id == "task-001"
        assert result.claims[0].claim_id == "c1"

    def test_inactive_role_rejected(self) -> None:
        entry = make_registry_entry(role_id="R2", version="v1", status=RoleStatus.INACTIVE)
        registry = RoleRegistry((entry,))
        profiles = {"profile-r2": make_knowledge_profile(profile_id="profile-r2", role_id="R2")}
        evidence = (make_source(source_id="se-001", source_type=SourceType.OWNER_DIRECT),)
        task = make_role_task(role_id="R2", allowed_evidence_ids=("se-001",))
        with pytest.raises(ExecutorError):
            execute_role_task(task, registry, profiles, make_fake_provider("{}"), evidence)

    def test_role_version_mismatch_rejected(self) -> None:
        registry, profiles, evidence, _ = _r2_registry_scope()
        task = make_role_task(role_id="R2", role_version="v9")
        with pytest.raises(ExecutorError):
            execute_role_task(task, registry, profiles, make_fake_provider("{}"), evidence)

    def test_absent_role_rejected(self) -> None:
        registry = RoleRegistry((make_registry_entry(role_id="R1"),))
        profiles = {"profile-r1": make_knowledge_profile(profile_id="profile-r1", role_id="R1")}
        evidence = (make_source(source_id="se-001", source_type=SourceType.OWNER_DIRECT),)
        task = make_role_task(role_id="R2")
        with pytest.raises(ExecutorError):
            execute_role_task(task, registry, profiles, make_fake_provider("{}"), evidence)

    def test_revision_round_out_of_range_rejected(self) -> None:
        # revision_round > 2 is rejected at RoleTask construction (fail-closed
        # before the executor is even reachable).
        with pytest.raises(CrpError):
            make_role_task(revision_round=3)

    def test_empty_output_rejected(self) -> None:
        registry, profiles, evidence, task = _r2_registry_scope()
        with pytest.raises(ExecutorError):
            execute_role_task(task, registry, profiles, make_fake_provider("   "), evidence)

    def test_malformed_output_rejected(self) -> None:
        registry, profiles, evidence, task = _r2_registry_scope()
        with pytest.raises(ExecutorError):
            execute_role_task(task, registry, profiles, make_fake_provider("not json"), evidence)

    def test_unknown_field_rejected(self) -> None:
        registry, profiles, evidence, task = _r2_registry_scope()
        payload = json.loads(_r2_result_json())
        payload["extra_field"] = "nope"
        with pytest.raises(ExecutorError):
            execute_role_task(task, registry, profiles, make_fake_provider(json.dumps(payload)), evidence)

    def test_wrong_role_id_rejected(self) -> None:
        registry, profiles, evidence, task = _r2_registry_scope()
        with pytest.raises(ExecutorError):
            execute_role_task(task, registry, profiles, make_fake_provider(_r2_result_json(role_id="R4")), evidence)

    def test_permission_violation_rejected(self) -> None:
        # R2 emits a voice-targeted claim -> ROLE_PERMISSION_VIOLATION.
        registry, profiles, evidence, task = _r2_registry_scope()
        provider = make_fake_provider(_r2_result_json(target="voice.lexicon"))
        with pytest.raises(ExecutorError, match="PERMISSION_VIOLATION"):
            execute_role_task(task, registry, profiles, provider, evidence)

    def test_unsupported_claim_rejected(self) -> None:
        # A FACT claim with only MODEL_INFERENCE evidence is unsupported.
        registry, profiles, evidence, task = _r2_registry_scope()
        provider = make_fake_provider(_r2_result_json(
            claim_type="FACT", source_type="MODEL_INFERENCE", confidence="KNOWN"))
        with pytest.raises(CrpError):
            execute_role_task(task, registry, profiles, provider, evidence)

    def test_evidence_outside_allowlist_rejected(self) -> None:
        registry, profiles, evidence, task = _r2_registry_scope()
        # claim references evidence "se-999" not in allowed_evidence_ids
        payload = json.loads(_r2_result_json())
        payload["claims"][0]["source_evidence_ids"] = ["se-999"]
        with pytest.raises(ExecutorError):
            execute_role_task(task, registry, profiles, make_fake_provider(json.dumps(payload)), evidence)

    def test_no_auto_retry_and_no_chaining(self) -> None:
        registry, profiles, evidence, task = _r2_registry_scope()
        calls = []

        def counted(messages):
            calls.append(messages)
            return _r2_result_json()

        result = execute_role_task(task, registry, profiles, counted, evidence)
        assert len(calls) == 1  # exactly one provider invocation
        assert result.role_id == "R2"

    def test_required_provider_injection(self) -> None:
        registry, profiles, evidence, task = _r2_registry_scope()
        with pytest.raises(ExecutorError, match="required injected callable"):
            execute_role_task(task, registry, profiles, None, evidence)


class TestVoicePatternLabelParsing:
    @pytest.mark.parametrize("label", [
        "OBSERVED", "INFERRED", "GENERATED_RULE", "NEGATIVE_EXAMPLE",
    ])
    def test_authorized_label_parses(self, label: str) -> None:
        registry, profiles, evidence, task = _r4_registry_scope()
        provider = make_fake_provider(_r4_result_json(label=label))
        result = execute_role_task(task, registry, profiles, provider, evidence)
        assert result.claims[0].voice_pattern_label is VoicePatternLabel(label)

    def test_unknown_label_rejected(self) -> None:
        registry, profiles, evidence, task = _r4_registry_scope()
        provider = make_fake_provider(_r4_result_json(label="FABRICATED"))
        with pytest.raises(ExecutorError):
            execute_role_task(task, registry, profiles, provider, evidence)

    def test_missing_label_remains_valid(self) -> None:
        registry, profiles, evidence, task = _r4_registry_scope()
        provider = make_fake_provider(_r4_result_json())
        result = execute_role_task(task, registry, profiles, provider, evidence)
        assert result.claims[0].voice_pattern_label is None

    def test_parsed_label_preserves_other_axes(self) -> None:
        # Parsing voice_pattern_label must not mutate source_type/confidence/
        # claim_type.
        registry, profiles, evidence, task = _r4_registry_scope()
        provider = make_fake_provider(_r4_result_json(label="OBSERVED"))
        result = execute_role_task(task, registry, profiles, provider, evidence)
        claim = result.claims[0]
        assert claim.source_type_summary == (SourceType.OBSERVATION,)
        assert claim.confidence.value == "KNOWN"
        assert claim.claim_type.value == "OBSERVATION"
        assert claim.voice_pattern_label is VoicePatternLabel.OBSERVED

    def test_backwards_compat_non_r4_no_label(self) -> None:
        # Existing R2 JSON (no voice_pattern_label key) still parses with
        # voice_pattern_label=None, identical to pre-fix behavior.
        registry, profiles, evidence, task = _r2_registry_scope()
        provider = make_fake_provider(_r2_result_json())
        result = execute_role_task(task, registry, profiles, provider, evidence)
        assert result.claims[0].voice_pattern_label is None


class TestPromptAssembly:
    def test_exact_prompt_ref_text_loaded(self) -> None:
        text = _load_prompt_text(_R2_PROMPT_REF)
        assert "ROLE_IDENTITY" in text
        assert "psychology" in text.lower()
        # Exact real file, not a placeholder.
        assert "ROLE_2_PSYCHOLOGICAL_HYPOTHESIS_ANALYST" in text

    def test_system_message_is_exact_prompt_text(self) -> None:
        registry, profiles, evidence, task = _r2_registry_scope()
        entry = registry.get("R2")
        prompt_text = _load_prompt_text(entry.prompt_ref)
        seen = {}

        def capture(messages):
            seen["messages"] = messages
            return _r2_result_json()

        execute_role_task(task, registry, profiles, capture, evidence)
        messages = seen["messages"]
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == prompt_text
        # User context message remains present.
        assert any(m["role"] == "user" for m in messages)

    def test_user_context_remains_present(self) -> None:
        registry, profiles, evidence, task = _r2_registry_scope()
        seen = {}

        def capture(messages):
            seen["messages"] = messages
            return _r2_result_json()

        execute_role_task(task, registry, profiles, capture, evidence)
        user = [m for m in seen["messages"] if m["role"] == "user"]
        assert len(user) == 1
        assert "task_goal" in user[0]["content"]
        assert "se-001" in user[0]["content"]

    def test_missing_prompt_ref_fails_closed(self) -> None:
        with pytest.raises(ExecutorError):
            _load_prompt_text("roles/vnext/DOES_NOT_EXIST_v1_PROMPT.md")

    def test_absolute_path_rejected(self) -> None:
        with pytest.raises(ExecutorError):
            _load_prompt_text("C:/somewhere/absolute.md")

    def test_parent_traversal_rejected(self) -> None:
        with pytest.raises(ExecutorError):
            _load_prompt_text("../roles/vnext/ROLE_2_PSYCHOLOGICAL_HYPOTHESIS_ANALYST_v1_PROMPT.md")

    def test_resolved_escape_outside_root_rejected(self) -> None:
        with pytest.raises(ExecutorError):
            _load_prompt_text("roles/ROLE_2_PERSONA_PSYCHOLOGIST_v1.4_PROMPT.md")

    def test_non_file_target_rejected(self) -> None:
        # A directory (roles/vnext) is not a regular file.
        with pytest.raises(ExecutorError):
            _load_prompt_text("roles/vnext")

    def test_assemble_messages_system_first(self) -> None:
        registry, profiles, evidence, task = _r2_registry_scope()
        entry = registry.get("R2")
        prompt_text = _load_prompt_text(entry.prompt_ref)
        messages = _assemble_messages(
            task, evidence, (), prompt_text=prompt_text,
        )
        assert messages[0] == {"role": "system", "content": prompt_text}
        assert messages[1]["role"] == "user"


class TestTaskMetadataExposure:
    """S2C-C2: current task_id/role_id/role_version must be visible to the
    provider so the model can echo them to satisfy exact-equality checks."""

    def _visible_scope(self):
        entry = make_registry_entry(
            role_id="R2", version="v-test-visible", prompt_ref=_R2_PROMPT_REF,
        )
        registry = RoleRegistry((entry,))
        profiles = {"profile-r2": make_knowledge_profile(profile_id="profile-r2", role_id="R2")}
        evidence = (make_source(source_id="se-001", source_type=SourceType.OWNER_DIRECT),)
        task = make_role_task(
            task_id="task-visible-123", role_id="R2", role_version="v-test-visible",
            allowed_evidence_ids=("se-001",),
        )
        return registry, profiles, evidence, task

    def test_current_task_metadata_exposed(self) -> None:
        registry, profiles, evidence, task = self._visible_scope()
        seen = {}

        def capture(messages):
            seen["messages"] = messages
            return _r2_result_json(
                task_id="task-visible-123", role_id="R2", role_version="v-test-visible",
            )

        execute_role_task(task, registry, profiles, capture, evidence)

        user_content = [m["content"] for m in seen["messages"] if m["role"] == "user"][0]
        assert "- task_id: task-visible-123" in user_content
        assert "- role_id: R2" in user_content
        assert "- role_version: v-test-visible" in user_content

    def test_echo_success(self) -> None:
        registry, profiles, evidence, task = self._visible_scope()
        provider = make_fake_provider(_r2_result_json(
            task_id="task-visible-123", role_id="R2", role_version="v-test-visible",
        ))
        result = execute_role_task(task, registry, profiles, provider, evidence)
        assert result.task_id == "task-visible-123"
        assert result.role_id == "R2"
        assert result.role_version == "v-test-visible"

    def test_wrong_task_id_still_fails_closed(self) -> None:
        registry, profiles, evidence, task = self._visible_scope()
        provider = make_fake_provider(_r2_result_json(task_id="some-other-task-id"))
        with pytest.raises(ExecutorError, match="result task_id"):
            execute_role_task(task, registry, profiles, provider, evidence)
