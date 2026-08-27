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
from services.crp_authoring.dataset_freeze import canonical_json_sha256
from services.crp_authoring.executor import _assemble_messages, _load_prompt_text

from tests.crp_authoring.conftest import (
    make_fake_provider,
    make_knowledge_profile,
    make_payload_map,
    make_registry_entry,
    make_role_task,
    make_source,
)

# Exact real vNext prompt files (fail-closed prompt assembly requires these).
_R2_PROMPT_REF = "roles/vnext/ROLE_2_PSYCHOLOGICAL_HYPOTHESIS_ANALYST_v1_PROMPT.md"
_R4_PROMPT_REF = "roles/vnext/ROLE_4_VOICE_RECONSTRUCTION_ANALYST_v1_PROMPT.md"


def _r2_result_json(task_id="task-001", role_id="R2", role_version="v1",
                    subject_id="char-subject-1",
                    claim_type="HYPOTHESIS", target="psychology.P2",
                    source_type="OWNER_DIRECT", confidence="POSSIBLE"):
    return json.dumps({
        "task_id": task_id,
        "role_id": role_id,
        "role_version": role_version,
        "completion_status": "COMPLETE",
        "claims": [{
            "claim_id": "c1",
            "subject_id": subject_id,
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
        result = execute_role_task(task, registry, profiles, provider, evidence,
                                   evidence_payloads=make_payload_map("se-001"))
        assert result.task_id == "task-001"
        assert result.claims[0].claim_id == "c1"

    def test_inactive_role_rejected(self) -> None:
        entry = make_registry_entry(role_id="R2", version="v1", status=RoleStatus.INACTIVE)
        registry = RoleRegistry((entry,))
        profiles = {"profile-r2": make_knowledge_profile(profile_id="profile-r2", role_id="R2")}
        evidence = (make_source(source_id="se-001", source_type=SourceType.OWNER_DIRECT),)
        task = make_role_task(role_id="R2", allowed_evidence_ids=("se-001",))
        with pytest.raises(ExecutorError):
            execute_role_task(task, registry, profiles, make_fake_provider("{}"), evidence,
                              evidence_payloads=make_payload_map("se-001"))

    def test_role_version_mismatch_rejected(self) -> None:
        registry, profiles, evidence, _ = _r2_registry_scope()
        task = make_role_task(role_id="R2", role_version="v9")
        with pytest.raises(ExecutorError):
            execute_role_task(task, registry, profiles, make_fake_provider("{}"), evidence,
                              evidence_payloads=make_payload_map("se-001"))

    def test_absent_role_rejected(self) -> None:
        registry = RoleRegistry((make_registry_entry(role_id="R1"),))
        profiles = {"profile-r1": make_knowledge_profile(profile_id="profile-r1", role_id="R1")}
        evidence = (make_source(source_id="se-001", source_type=SourceType.OWNER_DIRECT),)
        task = make_role_task(role_id="R2")
        with pytest.raises(ExecutorError):
            execute_role_task(task, registry, profiles, make_fake_provider("{}"), evidence,
                              evidence_payloads=make_payload_map("se-001"))

    def test_revision_round_out_of_range_rejected(self) -> None:
        # revision_round > 2 is rejected at RoleTask construction (fail-closed
        # before the executor is even reachable).
        with pytest.raises(CrpError):
            make_role_task(revision_round=3)

    def test_empty_output_rejected(self) -> None:
        registry, profiles, evidence, task = _r2_registry_scope()
        with pytest.raises(ExecutorError):
            execute_role_task(task, registry, profiles, make_fake_provider("   "), evidence,
                              evidence_payloads=make_payload_map("se-001"))

    def test_malformed_output_rejected(self) -> None:
        registry, profiles, evidence, task = _r2_registry_scope()
        with pytest.raises(ExecutorError):
            execute_role_task(task, registry, profiles, make_fake_provider("not json"), evidence,
                              evidence_payloads=make_payload_map("se-001"))

    def test_unknown_field_rejected(self) -> None:
        registry, profiles, evidence, task = _r2_registry_scope()
        payload = json.loads(_r2_result_json())
        payload["extra_field"] = "nope"
        with pytest.raises(ExecutorError):
            execute_role_task(task, registry, profiles, make_fake_provider(json.dumps(payload)),
                              evidence, evidence_payloads=make_payload_map("se-001"))

    def test_wrong_role_id_rejected(self) -> None:
        registry, profiles, evidence, task = _r2_registry_scope()
        with pytest.raises(ExecutorError):
            execute_role_task(task, registry, profiles,
                              make_fake_provider(_r2_result_json(role_id="R4")), evidence,
                              evidence_payloads=make_payload_map("se-001"))

    def test_permission_violation_rejected(self) -> None:
        # R2 emits a voice-targeted claim -> ROLE_PERMISSION_VIOLATION.
        registry, profiles, evidence, task = _r2_registry_scope()
        provider = make_fake_provider(_r2_result_json(target="voice.lexicon"))
        with pytest.raises(ExecutorError, match="PERMISSION_VIOLATION"):
            execute_role_task(task, registry, profiles, provider, evidence,
                              evidence_payloads=make_payload_map("se-001"))

    def test_unsupported_claim_rejected(self) -> None:
        # A FACT claim with only MODEL_INFERENCE evidence is unsupported.
        registry, profiles, evidence, task = _r2_registry_scope()
        provider = make_fake_provider(_r2_result_json(
            claim_type="FACT", source_type="MODEL_INFERENCE", confidence="KNOWN"))
        with pytest.raises(CrpError):
            execute_role_task(task, registry, profiles, provider, evidence,
                              evidence_payloads=make_payload_map("se-001"))

    def test_evidence_outside_allowlist_rejected(self) -> None:
        registry, profiles, evidence, task = _r2_registry_scope()
        # claim references evidence "se-999" not in allowed_evidence_ids
        payload = json.loads(_r2_result_json())
        payload["claims"][0]["source_evidence_ids"] = ["se-999"]
        with pytest.raises(ExecutorError):
            execute_role_task(task, registry, profiles, make_fake_provider(json.dumps(payload)),
                              evidence, evidence_payloads=make_payload_map("se-001"))

    def test_no_auto_retry_and_no_chaining(self) -> None:
        registry, profiles, evidence, task = _r2_registry_scope()
        calls = []

        def counted(messages):
            calls.append(messages)
            return _r2_result_json()

        result = execute_role_task(task, registry, profiles, counted, evidence,
                                   evidence_payloads=make_payload_map("se-001"))
        assert len(calls) == 1  # exactly one provider invocation
        assert result.role_id == "R2"

    def test_required_provider_injection(self) -> None:
        registry, profiles, evidence, task = _r2_registry_scope()
        with pytest.raises(ExecutorError, match="required injected callable"):
            execute_role_task(task, registry, profiles, None, evidence,
                              evidence_payloads=make_payload_map("se-001"))


class TestExecutorNoneFailClosed:
    """MAT-02: metadata-only fallback and explicit-None must fail before provider."""

    def test_gen_none_01_explicit_none_fails_before_provider(self) -> None:
        registry, profiles, evidence, task = _r2_registry_scope()
        calls = []

        def counted(messages):
            calls.append(messages)
            return _r2_result_json()

        with pytest.raises(ExecutorError):
            execute_role_task(task, registry, profiles, counted, evidence,
                              evidence_payloads=None)
        assert len(calls) == 0

    def test_gen_none_02_omitted_argument_fails_at_api(self) -> None:
        registry, profiles, evidence, task = _r2_registry_scope()
        calls = []

        def counted(messages):
            calls.append(messages)
            return _r2_result_json()

        with pytest.raises(TypeError):
            execute_role_task(task, registry, profiles, counted, evidence)
        assert len(calls) == 0

    def test_gen_none_03_empty_map_with_nonempty_evidence_fails(self) -> None:
        registry, profiles, evidence, task = _r2_registry_scope()
        calls = []

        def counted(messages):
            calls.append(messages)
            return _r2_result_json()

        with pytest.raises(ExecutorError):
            execute_role_task(task, registry, profiles, counted, evidence,
                              evidence_payloads={})
        assert len(calls) == 0


class TestVoicePatternLabelParsing:
    @pytest.mark.parametrize("label", [
        "OBSERVED", "INFERRED", "GENERATED_RULE", "NEGATIVE_EXAMPLE",
    ])
    def test_authorized_label_parses(self, label: str) -> None:
        registry, profiles, evidence, task = _r4_registry_scope()
        provider = make_fake_provider(_r4_result_json(label=label))
        result = execute_role_task(task, registry, profiles, provider, evidence,
                                   evidence_payloads=make_payload_map("se-001"))
        assert result.claims[0].voice_pattern_label is VoicePatternLabel(label)

    def test_unknown_label_rejected(self) -> None:
        registry, profiles, evidence, task = _r4_registry_scope()
        provider = make_fake_provider(_r4_result_json(label="FABRICATED"))
        with pytest.raises(ExecutorError):
            execute_role_task(task, registry, profiles, provider, evidence,
                              evidence_payloads=make_payload_map("se-001"))

    def test_missing_label_remains_valid(self) -> None:
        registry, profiles, evidence, task = _r4_registry_scope()
        provider = make_fake_provider(_r4_result_json())
        result = execute_role_task(task, registry, profiles, provider, evidence,
                                   evidence_payloads=make_payload_map("se-001"))
        assert result.claims[0].voice_pattern_label is None

    def test_parsed_label_preserves_other_axes(self) -> None:
        # Parsing voice_pattern_label must not mutate source_type/confidence/
        # claim_type.
        registry, profiles, evidence, task = _r4_registry_scope()
        provider = make_fake_provider(_r4_result_json(label="OBSERVED"))
        result = execute_role_task(task, registry, profiles, provider, evidence,
                                   evidence_payloads=make_payload_map("se-001"))
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
        result = execute_role_task(task, registry, profiles, provider, evidence,
                                   evidence_payloads=make_payload_map("se-001"))
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

        execute_role_task(task, registry, profiles, capture, evidence,
                          evidence_payloads=make_payload_map("se-001"))
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

        execute_role_task(task, registry, profiles, capture, evidence,
                          evidence_payloads=make_payload_map("se-001"))
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
            evidence_payloads=make_payload_map("se-001"),
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
            subject_id="subject-visible-456", allowed_evidence_ids=("se-001",),
        )
        return registry, profiles, evidence, task

    def test_current_task_metadata_exposed(self) -> None:
        registry, profiles, evidence, task = self._visible_scope()
        seen = {}

        def capture(messages):
            seen["messages"] = messages
            return _r2_result_json(
                task_id="task-visible-123", role_id="R2", role_version="v-test-visible",
                subject_id="subject-visible-456",
            )

        execute_role_task(task, registry, profiles, capture, evidence,
                          evidence_payloads=make_payload_map("se-001"))

        user_content = [m["content"] for m in seen["messages"] if m["role"] == "user"][0]
        assert "- task_id: task-visible-123" in user_content
        assert "- role_id: R2" in user_content
        assert "- role_version: v-test-visible" in user_content
        assert "- subject_id: subject-visible-456" in user_content

    def test_subject_id_exposed_exact_value(self) -> None:
        # Distinct value proves _assemble_messages() preserves task.subject_id
        # verbatim (no rewriting/slugging/normalization).
        registry, profiles, evidence, task = self._visible_scope()
        entry = registry.get("R2")
        prompt_text = _load_prompt_text(entry.prompt_ref)
        messages = _assemble_messages(task, evidence, (), prompt_text=prompt_text,
                                      evidence_payloads=make_payload_map("se-001"))
        user_content = messages[1]["content"]
        assert "- subject_id: subject-visible-456" in user_content

    def test_echo_success(self) -> None:
        registry, profiles, evidence, task = self._visible_scope()
        provider = make_fake_provider(_r2_result_json(
            task_id="task-visible-123", role_id="R2", role_version="v-test-visible",
            subject_id="subject-visible-456",
        ))
        result = execute_role_task(task, registry, profiles, provider, evidence,
                                   evidence_payloads=make_payload_map("se-001"))
        assert result.task_id == "task-visible-123"
        assert result.role_id == "R2"
        assert result.role_version == "v-test-visible"

    def test_wrong_task_id_still_fails_closed(self) -> None:
        registry, profiles, evidence, task = self._visible_scope()
        provider = make_fake_provider(_r2_result_json(task_id="some-other-task-id"))
        with pytest.raises(ExecutorError, match="result task_id"):
            execute_role_task(task, registry, profiles, provider, evidence,
                              evidence_payloads=make_payload_map("se-001"))

    def test_wrong_subject_id_fails_closed(self) -> None:
        # Claim subject_id differing from task.subject_id must fail closed.
        registry, profiles, evidence, task = self._visible_scope()
        provider = make_fake_provider(_r2_result_json(
            task_id="task-visible-123", role_id="R2", role_version="v-test-visible",
            subject_id="some-other-subject",
        ))
        with pytest.raises(ExecutorError, match="subject_id"):
            execute_role_task(task, registry, profiles, provider, evidence,
                              evidence_payloads=make_payload_map("se-001"))


class TestForbiddenRefEnforcement:
    """GAP-2: forbidden refs rejected deterministically before the provider."""

    def _forbidden_scope(self, forbidden_refs, *, content_ref="ref://raw/001",
                         provenance="synthetic-fixture"):
        entry = make_registry_entry(role_id="R2", version="v1", prompt_ref=_R2_PROMPT_REF)
        registry = RoleRegistry((entry,))
        profiles = {
            "profile-r2": make_knowledge_profile(
                profile_id="profile-r2", role_id="R2", forbidden_refs=forbidden_refs,
            )
        }
        evidence = (
            make_source(
                source_id="se-001", source_type=SourceType.OWNER_DIRECT,
                content_ref=content_ref, provenance=provenance,
            ),
        )
        task = make_role_task(
            task_id="task-001", role_id="R2", role_version="v1",
            allowed_evidence_ids=("se-001",),
        )
        return registry, profiles, evidence, task

    def test_exact_forbidden_ref_rejected_before_provider(self) -> None:
        registry, profiles, evidence, task = self._forbidden_scope(
            ("personas/kira/profile.json",),
            content_ref="personas/kira/profile.json",
        )
        calls = []

        def counted(messages):
            calls.append(messages)
            return _r2_result_json()

        with pytest.raises(ExecutorError, match="forbidden"):
            execute_role_task(task, registry, profiles, counted, evidence,
                              evidence_payloads=make_payload_map("se-001"))
        assert len(calls) == 0  # never reached the provider boundary

    def test_prefix_descendant_rejected_before_provider(self) -> None:
        registry, profiles, evidence, task = self._forbidden_scope(
            ("personas/kira/**",),
            content_ref="personas/kira/notes.md",
        )
        calls = []

        def counted(messages):
            calls.append(messages)
            return _r2_result_json()

        with pytest.raises(ExecutorError, match="forbidden"):
            execute_role_task(task, registry, profiles, counted, evidence,
                              evidence_payloads=make_payload_map("se-001"))
        assert len(calls) == 0

    def test_windows_backslash_rejected_before_provider(self) -> None:
        registry, profiles, evidence, task = self._forbidden_scope(
            ("personas/kira/**",),
            content_ref=r"personas\kira\notes.md",
        )
        calls = []

        def counted(messages):
            calls.append(messages)
            return _r2_result_json()

        with pytest.raises(ExecutorError, match="forbidden"):
            execute_role_task(task, registry, profiles, counted, evidence,
                              evidence_payloads=make_payload_map("se-001"))
        assert len(calls) == 0

    def test_case_variant_rejected_before_provider(self) -> None:
        registry, profiles, evidence, task = self._forbidden_scope(
            ("personas/kira/**",),
            content_ref="Personas/Kira/Notes.md",
        )
        calls = []

        def counted(messages):
            calls.append(messages)
            return _r2_result_json()

        with pytest.raises(ExecutorError, match="forbidden"):
            execute_role_task(task, registry, profiles, counted, evidence,
                              evidence_payloads=make_payload_map("se-001"))
        assert len(calls) == 0

    def test_near_miss_is_allowed(self) -> None:
        # personas/kira2/... must NOT match personas/kira/**.
        registry, profiles, evidence, task = self._forbidden_scope(
            ("personas/kira/**",),
            content_ref="personas/kira2/notes.md",
        )
        provider = make_fake_provider(_r2_result_json())
        result = execute_role_task(task, registry, profiles, provider, evidence,
                                   evidence_payloads=make_payload_map("se-001"))
        assert result.task_id == "task-001"

    def test_provenance_only_kira_is_allowed(self) -> None:
        # The literal word in provenance must not trigger rejection when
        # content_ref is clean (structured-ref matching, not prose scanning).
        registry, profiles, evidence, task = self._forbidden_scope(
            ("personas/kira/**",),
            content_ref="ref://raw/001",
            provenance="owner notes mentioning a kira-like reference",
        )
        provider = make_fake_provider(_r2_result_json())
        result = execute_role_task(task, registry, profiles, provider, evidence,
                                   evidence_payloads=make_payload_map("se-001"))
        assert result.task_id == "task-001"

    def test_empty_forbidden_refs_preserves_behavior(self) -> None:
        registry, profiles, evidence, task = self._forbidden_scope(())
        calls = []

        def counted(messages):
            calls.append(messages)
            return _r2_result_json()

        result = execute_role_task(task, registry, profiles, counted, evidence,
                                   evidence_payloads=make_payload_map("se-001"))
        assert result.task_id == "task-001"
        assert len(calls) == 1


class TestClaimRoleIdEnforcement:
    """Part B: individual RoleClaim.role_id must equal task.role_id."""

    def test_wrong_claim_role_rejected(self) -> None:
        # A correctly-labeled wrapper (RoleResult.role_id == R2) must not hide
        # a misattributed individual claim (RoleClaim.role_id == R4).
        registry, profiles, evidence, task = _r2_registry_scope()
        payload = json.loads(_r2_result_json(role_id="R2"))
        payload["claims"][0]["role_id"] = "R4"
        provider = make_fake_provider(json.dumps(payload))
        with pytest.raises(ExecutorError, match="role_id"):
            execute_role_task(task, registry, profiles, provider, evidence,
                              evidence_payloads=make_payload_map("se-001"))

    def test_correct_claim_role_continues_to_pass(self) -> None:
        registry, profiles, evidence, task = _r2_registry_scope()
        provider = make_fake_provider(_r2_result_json(role_id="R2"))
        result = execute_role_task(task, registry, profiles, provider, evidence,
                                   evidence_payloads=make_payload_map("se-001"))
        assert result.claims[0].role_id == "R2"


class TestSubstantiveMaterialization:
    """CRP R4 pre-provider correction: substantive owner-authored facts must be
    hash-bound and rendered into provider-visible messages (synthetic evidence).

    Sentinel text originates ONLY in the synthetic payload; fail-closed cases
    must never reach the provider callable.
    """

    SENTINEL = "OWNER_FACT_SENTINEL_9F3B7"
    UNALLOWED = "UNALLOWED_SENTINEL_B7C21"

    def _facts(self):
        return [{"fact": self.SENTINEL, "detail": "owner-authored substantive fact"}]

    def _scope(self, *, allowed=("se-001",), evidence_ids=("se-001",)):
        facts = self._facts()
        content_hash = canonical_json_sha256(facts)
        evidence = tuple(
            make_source(source_id=eid, source_type=SourceType.OWNER_DIRECT,
                        content_hash=content_hash)
            for eid in evidence_ids
        )
        entry = make_registry_entry(role_id="R2", version="v1", prompt_ref=_R2_PROMPT_REF)
        registry = RoleRegistry((entry,))
        profiles = {"profile-r2": make_knowledge_profile(profile_id="profile-r2", role_id="R2")}
        task = make_role_task(task_id="task-001", role_id="R2", role_version="v1",
                              allowed_evidence_ids=allowed)
        payloads = {
            eid: {"section_id": "s1", "title": "section title", "facts": facts}
            for eid in evidence_ids
        }
        return registry, profiles, evidence, task, payloads

    def _user_content(self, messages):
        return [m["content"] for m in messages if m["role"] == "user"][0]

    def test_mat01_substantive_fact_reaches_provider(self) -> None:
        registry, profiles, evidence, task, payloads = self._scope()
        seen = {}

        def capture(messages):
            seen["messages"] = messages
            return _r2_result_json()

        execute_role_task(task, registry, profiles, capture, evidence,
                          evidence_payloads=payloads)
        user = self._user_content(seen["messages"])
        assert self.SENTINEL in user
        assert "substantive_payload" in user

    def test_mat02_provenance_preserved(self) -> None:
        registry, profiles, evidence, task, payloads = self._scope()
        seen = {}

        def capture(messages):
            seen["messages"] = messages
            return _r2_result_json()

        execute_role_task(task, registry, profiles, capture, evidence,
                          evidence_payloads=payloads)
        user = self._user_content(seen["messages"])
        # source_id and content_ref provenance remain present.
        assert "se-001" in user
        assert "ref://raw/001" in user

    def test_mat03_unallowed_payload_not_rendered(self) -> None:
        # Two evidence items exist; the task authorizes only se-001. The
        # se-002 payload must never be rendered.
        registry, profiles, evidence, task, payloads = self._scope(
            allowed=("se-001",), evidence_ids=("se-001", "se-002"),
        )
        payloads["se-002"] = {"section_id": "s2", "title": "t2",
                              "facts": [{"fact": self.UNALLOWED}]}
        seen = {}

        def capture(messages):
            seen["messages"] = messages
            return _r2_result_json()

        execute_role_task(task, registry, profiles, capture, evidence,
                          evidence_payloads=payloads)
        user = self._user_content(seen["messages"])
        assert self.SENTINEL in user
        assert self.UNALLOWED not in user

    def test_mat04_missing_payload_fails_before_provider(self) -> None:
        registry, profiles, evidence, task, _payloads = self._scope()
        calls = []

        def counted(messages):
            calls.append(messages)
            return _r2_result_json()

        with pytest.raises(ExecutorError):
            execute_role_task(task, registry, profiles, counted, evidence,
                              evidence_payloads={})
        assert len(calls) == 0

    def test_mat05_hash_mismatch_fails_before_provider(self) -> None:
        registry, profiles, evidence, task, payloads = self._scope()
        payloads["se-001"] = {"section_id": "s1", "title": "t",
                              "facts": [{"fact": "TAMPERED_FACTS"}]}
        calls = []

        def counted(messages):
            calls.append(messages)
            return _r2_result_json()

        with pytest.raises(ExecutorError):
            execute_role_task(task, registry, profiles, counted, evidence,
                              evidence_payloads=payloads)
        assert len(calls) == 0

    def test_mat06_extra_payload_key_does_not_leak(self) -> None:
        registry, profiles, evidence, task, payloads = self._scope()
        payloads["ghost-id"] = {"section_id": "g", "title": "g",
                                "facts": [{"fact": self.UNALLOWED}]}
        seen = {}

        def capture(messages):
            seen["messages"] = messages
            return _r2_result_json()

        execute_role_task(task, registry, profiles, capture, evidence,
                          evidence_payloads=payloads)
        user = self._user_content(seen["messages"])
        assert self.SENTINEL in user
        assert self.UNALLOWED not in user
        assert "ghost-id" not in user


# ---------------------------------------------------------------------------
# R1 v3 canonical post-parse quality gate (CRP-OD-R4-KIRA-R1-V3-01).
#
# The gate runs at the exact seam AFTER _parse_role_result and all existing
# canonical executor checks, BEFORE execute_role_task returns, and ONLY when
# task.role_id == "R1" and task.role_version == "v3". It never fires for R1
# v2, R2, R3, R4, or R8. It verifies (A) union(claim.source_evidence_ids) ==
# set(task.allowed_evidence_ids) and (B) provenance_summary.sources_used ==
# that same actual claim-evidence set -- deterministic ExecutorError, no
# retry / fallback / mutation / repair / synthesis on any violation.
# ---------------------------------------------------------------------------

_R1_V3_PROMPT_REF = "roles/vnext/ROLE_1_EVIDENCE_INTERVIEWER_v3_PROMPT.md"
_R1_V2_PROMPT_REF = "roles/vnext/ROLE_1_EVIDENCE_INTERVIEWER_v2_PROMPT.md"


def _r1_result_json(*, task_id="task-r1", role_version="v3",
                    claim_evidence_ids=("se-001", "se-002"),
                    provenance_summary=None, subject_id="char-subject-1"):
    if provenance_summary is None:
        provenance_summary = {"sources_used": list(claim_evidence_ids)}
    return json.dumps({
        "task_id": task_id,
        "role_id": "R1",
        "role_version": role_version,
        "completion_status": "COMPLETE",
        "claims": [{
            "claim_id": "r1-c1",
            "subject_id": subject_id,
            "role_id": "R1",
            "claim": "the subject's stated birthplace is a named coastal city",
            "claim_type": "FACT",
            "source_evidence_ids": list(claim_evidence_ids),
            "source_type_summary": ["OWNER_DIRECT"],
            "confidence": "KNOWN",
            "rationale_summary": "owner stated the birthplace directly; both cited sources agree",
            "status": "PROPOSED",
            "target_module_or_layer": "identity_biography.birthplace",
        }],
        "unknowns": [],
        "contradictions": [],
        "provenance_summary": provenance_summary,
        "requests_for_more_evidence": [],
        "warnings": [],
        "questions_for_r1": [],
        "new_source_evidence": [],
    }, ensure_ascii=False)


def _r1_registry_scope(*, role_version="v3", prompt_ref=_R1_V3_PROMPT_REF,
                       allowed_evidence_ids=("se-001", "se-002")):
    entry = make_registry_entry(role_id="R1", version=role_version, prompt_ref=prompt_ref)
    registry = RoleRegistry((entry,))
    profiles = {"profile-r1": make_knowledge_profile(profile_id="profile-r1", role_id="R1")}
    evidence = tuple(
        make_source(source_id=sid, source_type=SourceType.OWNER_DIRECT)
        for sid in allowed_evidence_ids
    )
    task = make_role_task(task_id="task-r1", role_id="R1", role_version=role_version,
                          allowed_evidence_ids=tuple(allowed_evidence_ids))
    return registry, profiles, evidence, task


class TestR1V3QualityGate:
    def test_full_coverage_and_consistent_summary_passes(self) -> None:
        registry, profiles, evidence, task = _r1_registry_scope()
        provider = make_fake_provider(_r1_result_json(
            claim_evidence_ids=("se-001", "se-002"),
            provenance_summary={"sources_used": ["se-001", "se-002"]},
        ))
        result = execute_role_task(task, registry, profiles, provider, evidence,
                                   evidence_payloads=make_payload_map("se-001", "se-002"))
        assert result.role_id == "R1" and result.role_version == "v3"
        union: set = set()
        for c in result.claims:
            union.update(c.source_evidence_ids)
        assert union == set(task.allowed_evidence_ids)
        assert set(result.provenance_summary["sources_used"]) == union

    def test_missing_allowed_evidence_id_fails_closed(self) -> None:
        registry, profiles, evidence, task = _r1_registry_scope()
        provider = make_fake_provider(_r1_result_json(
            claim_evidence_ids=("se-001",),
            provenance_summary={"sources_used": ["se-001"]},
        ))
        with pytest.raises(ExecutorError) as ei:
            execute_role_task(task, registry, profiles, provider, evidence,
                              evidence_payloads=make_payload_map("se-001", "se-002"))
        assert "R1_V3_CLAIM_COVERAGE_INCOMPLETE" in str(ei.value)

    def test_provenance_summary_extra_id_absent_from_claims_fails_closed(self) -> None:
        registry, profiles, evidence, task = _r1_registry_scope()
        provider = make_fake_provider(_r1_result_json(
            claim_evidence_ids=("se-001", "se-002"),
            provenance_summary={"sources_used": ["se-001", "se-002", "se-003"]},
        ))
        with pytest.raises(ExecutorError) as ei:
            execute_role_task(task, registry, profiles, provider, evidence,
                              evidence_payloads=make_payload_map("se-001", "se-002"))
        assert "R1_V3_PROVENANCE_SUMMARY_MISMATCH" in str(ei.value)

    def test_claim_evidence_id_absent_from_provenance_summary_fails_closed(self) -> None:
        registry, profiles, evidence, task = _r1_registry_scope()
        provider = make_fake_provider(_r1_result_json(
            claim_evidence_ids=("se-001", "se-002"),
            provenance_summary={"sources_used": ["se-001"]},
        ))
        with pytest.raises(ExecutorError) as ei:
            execute_role_task(task, registry, profiles, provider, evidence,
                              evidence_payloads=make_payload_map("se-001", "se-002"))
        assert "R1_V3_PROVENANCE_SUMMARY_MISMATCH" in str(ei.value)

    def test_provenance_summary_without_sources_used_fails_closed(self) -> None:
        registry, profiles, evidence, task = _r1_registry_scope()
        provider = make_fake_provider(_r1_result_json(
            claim_evidence_ids=("se-001", "se-002"),
            provenance_summary={"used_evidence": ["se-001", "se-002"]},
        ))
        with pytest.raises(ExecutorError) as ei:
            execute_role_task(task, registry, profiles, provider, evidence,
                              evidence_payloads=make_payload_map("se-001", "se-002"))
        assert "R1_V3_PROVENANCE_SUMMARY_INVALID" in str(ei.value)

    def test_r1_v2_is_not_subjected_to_the_v3_gate(self) -> None:
        # Same payload shape that would FAIL the v3 gate (one source id, two
        # authorized) executes cleanly for an R1 v2 task: the gate is
        # version-scoped and never runs for v2.
        registry, profiles, evidence, task = _r1_registry_scope(
            role_version="v2", prompt_ref=_R1_V2_PROMPT_REF,
        )
        provider = make_fake_provider(_r1_result_json(
            role_version="v2",
            claim_evidence_ids=("se-001",),
            provenance_summary={"used_evidence": ["se-001"]},
        ))
        result = execute_role_task(task, registry, profiles, provider, evidence,
                                   evidence_payloads=make_payload_map("se-001", "se-002"))
        assert result.role_id == "R1" and result.role_version == "v2"
        assert len(result.claims) == 1

    def test_r2_is_not_subjected_to_the_v3_gate(self) -> None:
        # A non-R1 role with a provenance_summary that lacks 'sources_used'
        # (and a single-source claim) is unaffected by the R1 v3 gate.
        registry, profiles, evidence, task = _r2_registry_scope()
        provider = make_fake_provider(_r2_result_json())
        result = execute_role_task(task, registry, profiles, provider, evidence,
                                   evidence_payloads=make_payload_map("se-001"))
        assert result.role_id == "R2"
        assert "sources_used" not in result.provenance_summary


class TestParseFailureRawOutputObservability:
    """Fail-closed observability for a provider string that was returned
    successfully but fails inside ``_parse_role_result`` (e.g. an unknown enum
    value). The SAME ExecutorError must carry the EXACT original raw string on
    a stable ``raw_provider_output`` attribute -- no repair, no RoleResult."""

    def _bad_enum_raw(self):
        # Structurally valid RoleResult JSON whose only defect is a claim
        # ``claim_type`` of "OWNER_DIRECT" -- a SourceType value that is NOT a
        # member of ClaimType. The real strict parser reaches
        # ``_enum(ClaimType, "OWNER_DIRECT", "claim_type")`` and fails closed.
        return _r2_result_json(claim_type="OWNER_DIRECT")

    def test_schema_failure_still_raises_executor_error(self) -> None:
        registry, profiles, evidence, task = _r2_registry_scope()
        raw = self._bad_enum_raw()
        with pytest.raises(ExecutorError) as ei:
            execute_role_task(task, registry, profiles, make_fake_provider(raw),
                              evidence, evidence_payloads=make_payload_map("se-001"))
        # the real enum-failure class was reached (no earlier rejection)
        assert "OWNER_DIRECT" in str(ei.value)
        assert "ClaimType" in str(ei.value)

    def test_same_exception_carries_exact_unmodified_raw_provider_output(self) -> None:
        registry, profiles, evidence, task = _r2_registry_scope()
        raw = self._bad_enum_raw()
        with pytest.raises(ExecutorError) as ei:
            execute_role_task(task, registry, profiles, make_fake_provider(raw),
                              evidence, evidence_payloads=make_payload_map("se-001"))
        exc = ei.value
        assert hasattr(exc, "raw_provider_output")
        # exact, byte-for-string identical, and not copied/rewritten
        assert exc.raw_provider_output == raw
        assert exc.raw_provider_output is raw

    def test_no_repair_and_no_roleresult_produced(self) -> None:
        registry, profiles, evidence, task = _r2_registry_scope()
        raw = self._bad_enum_raw()
        produced = []

        def capture(messages):
            return raw

        with pytest.raises(ExecutorError) as ei:
            produced.append(execute_role_task(
                task, registry, profiles, capture, evidence,
                evidence_payloads=make_payload_map("se-001"),
            ))
        assert produced == []  # no RoleResult ever returned
        # raw was neither parsed-and-repaired nor mutated: it still round-trips
        # to the exact original object content, still carrying the bad enum.
        assert ei.value.raw_provider_output == raw
        assert json.loads(ei.value.raw_provider_output)["claims"][0]["claim_type"] == "OWNER_DIRECT"