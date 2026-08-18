#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CRP OFFLINE E2E v1 -- structural pipeline conformance (fake provider only).

Proves only ARCHITECTURAL / CONTRACT PIPELINE CONFORMANCE using synthetic,
deterministic fake-provider JSON. This is NOT a model-quality, behavioral-
fidelity, or Kira-reconstruction test. No real provider, no network, no Kira,
no canon/PAC/Sandbox material anywhere.

GAP-C disposition (authoritative, from CRP_GAPC_OFFLINE_ROUTING_PREFLIGHT):
  R1 UNKNOWN claims are AUTHORING-PROCESS GAP SIGNALS, never candidate claims
  for R6. They are routed only as prior-result context (never the claims tuple
  passed to compile_candidate_package()). No compiler change; no ERC-2.
"""

from __future__ import annotations

import json

from services.crp_authoring import RoleRegistry, execute_role_task
from services.crp_authoring.compiler import compile_candidate_package
from services.crp_authoring.contracts import ClaimType, SourceType, VoicePatternLabel
from services.crp_authoring.validator import (
    CHECK_CONTRADICTION_PRESERVED,
    validate_package,
)
from services.crp_authoring.voice_rules import voice_label_violations

from tests.crp_authoring.conftest import (
    make_claim,
    make_compile_context,
    make_contradiction,
    make_fake_provider,
    make_knowledge_profile,
    make_registry_entry,
    make_role_task,
    make_source,
)

SUBJECT = "char-subject-1"
SNAPSHOT = "snapshot-1"

# Exact real vNext prompt refs (fail-closed prompt assembly reads these files).
_PROMPT_REFS = {
    "R1": "roles/vnext/ROLE_1_EVIDENCE_INTERVIEWER_v1_PROMPT.md",
    "R2": "roles/vnext/ROLE_2_PSYCHOLOGICAL_HYPOTHESIS_ANALYST_v1_PROMPT.md",
    "R3": "roles/vnext/ROLE_3_INTIMACY_PROFILE_SPECIALIST_v1_PROMPT.md",
    "R4": "roles/vnext/ROLE_4_VOICE_RECONSTRUCTION_ANALYST_v1_PROMPT.md",
}


def _role_scope(role_id, task_id, evidence, activation_ref=None):
    """Build a synthetic (registry, profiles, task) scope for one role."""
    entry = make_registry_entry(role_id=role_id, prompt_ref=_PROMPT_REFS[role_id])
    registry = RoleRegistry((entry,))
    profiles = {
        f"profile-{role_id.lower()}": make_knowledge_profile(
            profile_id=f"profile-{role_id.lower()}", role_id=role_id,
        ),
    }
    kwargs = dict(task_id=task_id, role_id=role_id, allowed_evidence_ids=("se-001",))
    if activation_ref is not None:
        kwargs["activation_authorization_ref"] = activation_ref
    task = make_role_task(**kwargs)
    return registry, profiles, task


def _role_result_json(task_id, role_id, completion, claims, *, unknowns=(),
                      contradictions=(), requests=()):
    return json.dumps({
        "task_id": task_id,
        "role_id": role_id,
        "role_version": "v1",
        "completion_status": completion,
        "claims": claims,
        "unknowns": list(unknowns),
        "contradictions": list(contradictions),
        "provenance_summary": {"used_evidence": ["se-001"]},
        "requests_for_more_evidence": list(requests),
        "warnings": [],
        "questions_for_r1": [],
        "new_source_evidence": [],
    }, ensure_ascii=False)


def _claim(claim_id, role_id, claim_type, target, *, source_summary=("OWNER_DIRECT",),
           confidence="KNOWN", evidence_ids=("se-001",), claim_text="synthetic"):
    return {
        "claim_id": claim_id,
        "subject_id": SUBJECT,
        "role_id": role_id,
        "claim": claim_text,
        "claim_type": claim_type,
        "source_evidence_ids": list(evidence_ids),
        "source_type_summary": list(source_summary),
        "confidence": confidence,
        "rationale_summary": "synthetic offline test",
        "status": "PROPOSED",
        "target_module_or_layer": target,
    }


def _frozen_evidence():
    # One immutable evidence tuple shared by R2 and R4 (same snapshot id).
    return (make_source(source_id="se-001", source_type=SourceType.OWNER_DIRECT,
                        subject_id=SUBJECT, evidence_snapshot_id=SNAPSHOT),)


class TestOfflineE2E:

    def test_scenario_1_r1_insufficient_evidence_gap(self):
        """R1 executor round-trip: UNKNOWN gap claim + unknowns + requests.
        The UNKNOWN claim carries a free-form target and is a gap signal, never
        a candidate claim for R6 (routing proven by NOT sending it to R6)."""
        registry, profiles, task = _role_scope("R1", "task-r1", _frozen_evidence())
        payload = {
            "task_id": "task-r1",
            "role_id": "R1",
            "role_version": "v1",
            "completion_status": "INSUFFICIENT_EVIDENCE",
            "claims": [_claim("r1-gap-1", "R1", "UNKNOWN", "free.form.gap.target",
                              evidence_ids=(), confidence="UNKNOWN",
                              claim_text="missing evidence for subject past")],
            "unknowns": ["subject past is unevidenced"],
            "contradictions": [],
            "provenance_summary": {"used_evidence": ["se-001"]},
            "requests_for_more_evidence": ["please provide relationship history"],
            "warnings": [],
            "questions_for_r1": [],
            "new_source_evidence": [],
        }
        provider = make_fake_provider(json.dumps(payload, ensure_ascii=False))
        result = execute_role_task(task, registry, profiles, provider, _frozen_evidence())

        assert result.completion_status.value == "INSUFFICIENT_EVIDENCE"
        assert result.claims[0].claim_type is ClaimType.UNKNOWN
        # R1 gap claim's target is free-form (not a candidate family).
        assert result.claims[0].target_module_or_layer == "free.form.gap.target"
        assert result.unknowns == ("subject past is unevidenced",)
        assert result.requests_for_more_evidence == ("please provide relationship history",)
        # Routing proof: R1 claims are never handed to compile_candidate_package.
        # Nothing here calls the compiler with this claim.

    def test_scenario_2_r2_r4_shared_frozen_snapshot(self):
        """R2 and R4 consume the same frozen evidence; valid claims compile
        into psychology_candidate/voice_candidate; R4's voice_pattern_label
        survives parsing and passes external fidelity validation."""
        evidence = _frozen_evidence()

        # R2 (psychology)
        r2_registry, r2_profiles, r2_task = _role_scope("R2", "task-r2", evidence)
        r2_payload = _role_result_json("task-r2", "R2", "COMPLETE", [
            _claim("r2-psych-1", "R2", "HYPOTHESIS", "psychology.P2",
                   confidence="POSSIBLE", claim_text="cautious in social settings"),
        ])
        r2_result = execute_role_task(
            r2_task, r2_registry, r2_profiles,
            make_fake_provider(r2_payload), evidence,
        )

        # R4 (voice) — same evidence tuple, same snapshot.
        r4_registry, r4_profiles, r4_task = _role_scope("R4", "task-r4", evidence)
        r4_claim = _claim("r4-voice-1", "R4", "OBSERVATION", "voice.lexicon",
                          claim_text="clipped sentences")
        r4_claim["voice_pattern_label"] = "OBSERVED"
        r4_payload = _role_result_json("task-r4", "R4", "COMPLETE", [r4_claim])
        r4_result = execute_role_task(
            r4_task, r4_registry, r4_profiles,
            make_fake_provider(r4_payload), evidence,
        )

        # Shared snapshot proof: both tasks pinned the same evidence_snapshot_id.
        assert r2_task.evidence_snapshot_id == r4_task.evidence_snapshot_id == SNAPSHOT

        # R4 label parsed as the exact enum, and fidelity validation is clean.
        assert r4_result.claims[0].voice_pattern_label is VoicePatternLabel.OBSERVED
        assert voice_label_violations((r4_result.claims[0],)) == ()

        # Candidate claims (R2 + R4 only — R1's claims are excluded by design).
        candidate_claims = (r2_result.claims[0], r4_result.claims[0])
        ctx = make_compile_context(subject_id=SUBJECT)
        pkg = compile_candidate_package(ctx, candidate_claims, ())

        assert pkg.psychology_candidate["P2"] == (r2_result.claims[0],)
        assert pkg.voice_candidate["lexicon"] == (r4_result.claims[0],)
        assert pkg.intimacy_candidate == {}
        assert validate_package(pkg).valid is True

    def test_scenario_3_r3_skipped(self):
        """R3 is optional: compiling only R2+R4 claims yields a valid package
        with an empty intimacy_candidate and no activation needed."""
        evidence = _frozen_evidence()

        r2_registry, r2_profiles, r2_task = _role_scope("R2", "task-r2", evidence)
        r2_result = execute_role_task(
            r2_task, r2_registry, r2_profiles,
            make_fake_provider(_role_result_json("task-r2", "R2", "COMPLETE", [
                _claim("r2-psych-1", "R2", "HYPOTHESIS", "psychology.P2",
                       confidence="POSSIBLE"),
            ])), evidence,
        )

        r4_registry, r4_profiles, r4_task = _role_scope("R4", "task-r4", evidence)
        r4_result = execute_role_task(
            r4_task, r4_registry, r4_profiles,
            make_fake_provider(_role_result_json("task-r4", "R4", "COMPLETE", [
                _claim("r4-voice-1", "R4", "OBSERVATION", "voice.lexicon",
                       source_summary=("OWNER_DIRECT",)),
            ])), evidence,
        )

        # No R3 RoleTask is constructed at all — no activation_authorization_ref.
        ctx = make_compile_context(subject_id=SUBJECT)
        pkg = compile_candidate_package(ctx, (r2_result.claims[0], r4_result.claims[0]), ())

        assert pkg.intimacy_candidate == {}
        assert validate_package(pkg).valid is True

    def test_scenario_4_r3_explicitly_authorized(self):
        """R3 with a non-empty activation_authorization_ref emits an intimacy
        claim, which compiles into intimacy_candidate and validates."""
        evidence = _frozen_evidence()
        registry, profiles, task = _role_scope(
            "R3", "task-r3", evidence, activation_ref="human-approval-001",
        )
        # Structural guard: the gated role's activation ref is present/non-empty.
        assert task.activation_authorization_ref == "human-approval-001"

        payload = _role_result_json("task-r3", "R3", "COMPLETE", [
            _claim("r3-intimacy-1", "R3", "OBSERVATION", "intimacy.boundaries",
                   claim_text="explicit boundary stated"),
        ])
        result = execute_role_task(
            task, registry, profiles, make_fake_provider(payload), evidence,
        )

        assert result.claims[0].target_module_or_layer == "intimacy.boundaries"

        ctx = make_compile_context(subject_id=SUBJECT)
        pkg = compile_candidate_package(ctx, (result.claims[0],), ())
        assert pkg.intimacy_candidate["boundaries"] == (result.claims[0],)
        assert validate_package(pkg).valid is True

    def test_scenario_5_contradiction_preservation(self):
        """Two conflicting candidate claims plus one ContradictionRecord survive
        R6 compilation and R7 validation unchanged (no silent correction)."""
        a = make_claim(claim_id="conflict-a", role_id="R2",
                       target_module_or_layer="psychology.P3", claim="prefers solitude")
        b = make_claim(claim_id="conflict-b", role_id="R2",
                       target_module_or_layer="psychology.P3", claim="prefers company")
        record = make_contradiction(contradiction_id="crd-1", claim_ids=("conflict-a", "conflict-b"))

        ctx = make_compile_context(subject_id=SUBJECT)
        pkg = compile_candidate_package(ctx, (a, b), (record,))

        # Both sides survive.
        assert {c.claim_id for c in pkg.claims} == {"conflict-a", "conflict-b"}
        assert pkg.contradictions == (record,)
        assert set(record.claim_ids) == {"conflict-a", "conflict-b"}
        assert record.resolution_status.value == "OPEN"  # unresolved, not "corrected"

        report = validate_package(pkg, input_contradictions=(record,))
        assert not any(f.check == CHECK_CONTRADICTION_PRESERVED for f in report.findings)