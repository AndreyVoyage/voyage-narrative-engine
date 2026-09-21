# -*- coding: utf-8 -*-
"""CRP convergence -- golden negative fixtures (offline, hermetic).

Proves the two verbatim historical parse failures (RUN_013 claim_type=PROBABLE
and RUN_012 claim_type=NEGATIVE_EXAMPLE) are still rejected by the strict
parser, and that their corrected positive counterparts pass the relevant seam.
Also proves hand-authored minimal negatives for the R2/R4 claim_type=UNKNOWN
permission seam.

Fixture honesty is enforced by naming and module constants:
VERBATIM_HISTORICAL_NEGATIVE (extracted byte-for-byte from the immutable
C:\\DEV\\Narrative\\LOCAL_STORAGE\\crp_r4_live_runs diagnostics) is strictly
separated from HAND_AUTHORED_MINIMAL_NEGATIVE (constructed here; no verbatim
live data is reconstructed or mislabeled as historical).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pytest

from services.crp_authoring import (
    ClaimType,
    ExecutorError,
    RoleRegistry,
    SourceType,
    execute_role_task,
)
from services.crp_authoring.executor import _parse_role_result
from services.crp_authoring.voice_rules import voice_label_violations

from tests.crp_authoring.conftest import (
    make_fake_provider,
    make_knowledge_profile,
    make_payload_map,
    make_registry_entry,
    make_role_task,
    make_source,
)

_FIXTURE_DIR = _REPO_ROOT / "tests" / "fixtures" / "crp_authoring" / "historical_negatives"

# Verbatim historical negatives (extracted byte-for-byte from the immutable
# local-storage diagnostics; NOT hand-authored, NOT cleaned up).
VERBATIM_HISTORICAL_NEGATIVE_RUN_013_R1_PROBABLE = _FIXTURE_DIR / "RUN_013_R1_PROBABLE.verbatim.json"
VERBATIM_HISTORICAL_NEGATIVE_RUN_012_R4_NEGATIVE_EXAMPLE = _FIXTURE_DIR / "RUN_012_R4_NEGATIVE_EXAMPLE.verbatim.json"

# Synthetic prompt refs used only to stand up a minimal executor scope for the
# hand-authored permission negatives (the prompt text is not under test here).
_R2_PROMPT_REF = "roles/vnext/ROLE_2_PSYCHOLOGICAL_HYPOTHESIS_ANALYST_v1_PROMPT.md"
_R4_PROMPT_REF = "roles/vnext/ROLE_4_VOICE_RECONSTRUCTION_ANALYST_v1_PROMPT.md"


def _scope(role_id, version, prompt_ref, source_type):
    entry = make_registry_entry(role_id=role_id, version=version, prompt_ref=prompt_ref)
    registry = RoleRegistry((entry,))
    profiles = {
        f"profile-{role_id.lower()}": make_knowledge_profile(
            profile_id=f"profile-{role_id.lower()}", role_id=role_id,
        ),
    }
    evidence = (make_source(source_id="se-001", source_type=source_type),)
    task = make_role_task(
        task_id="task-001", role_id=role_id, role_version=version,
        allowed_evidence_ids=("se-001",),
    )
    return registry, profiles, evidence, task


class TestVerbatimHistoricalNegatives:
    def test_fixture_files_exist(self) -> None:
        assert VERBATIM_HISTORICAL_NEGATIVE_RUN_013_R1_PROBABLE.is_file()
        assert VERBATIM_HISTORICAL_NEGATIVE_RUN_012_R4_NEGATIVE_EXAMPLE.is_file()

    def test_run_013_r1_probable_rejected_as_invalid_claimtype(self) -> None:
        raw = VERBATIM_HISTORICAL_NEGATIVE_RUN_013_R1_PROBABLE.read_text(encoding="utf-8")
        # The verbatim defect is claim_type=PROBABLE (a Confidence value).
        assert '"PROBABLE"' in raw
        with pytest.raises(ExecutorError) as ei:
            _parse_role_result(raw)
        assert "PROBABLE" in str(ei.value)

    def test_run_012_r4_negative_example_rejected_as_invalid_claimtype(self) -> None:
        raw = VERBATIM_HISTORICAL_NEGATIVE_RUN_012_R4_NEGATIVE_EXAMPLE.read_text(encoding="utf-8")
        # The verbatim defect is claim_type=NEGATIVE_EXAMPLE (a VoicePatternLabel).
        assert '"NEGATIVE_EXAMPLE"' in raw
        with pytest.raises(ExecutorError) as ei:
            _parse_role_result(raw)
        assert "NEGATIVE_EXAMPLE" in str(ei.value)


class TestPositiveCounterparts:
    def test_r1_probable_corrected_positive_parses(self) -> None:
        # Corrected: claim_type is a legal R1 ClaimType; the probability lives
        # in confidence, and the target is a legal R1 family.
        raw = json.dumps({
            "task_id": "t",
            "role_id": "R1",
            "role_version": "v4",
            "completion_status": "COMPLETE",
            "claims": [{
                "claim_id": "r1-claim-0001",
                "subject_id": "s",
                "role_id": "R1",
                "claim": "the subject likely prefers calm environments",
                "claim_type": "INFERENCE",
                "source_evidence_ids": ["e1"],
                "source_type_summary": ["OWNER_DIRECT"],
                "confidence": "PROBABLE",
                "rationale_summary": "hedged by the evidence",
                "status": "PROPOSED",
                "target_module_or_layer": "identity_biography.preference",
            }],
            "unknowns": [],
            "contradictions": [],
            "provenance_summary": {"sources_used": ["e1"]},
            "requests_for_more_evidence": [],
            "warnings": [],
            "questions_for_r1": [],
            "new_source_evidence": [],
        }, ensure_ascii=False)
        result = _parse_role_result(raw)
        assert result.claims[0].claim_type is ClaimType.INFERENCE
        assert result.claims[0].confidence.value == "PROBABLE"

    def test_r4_negative_example_corrected_positive_passes_voice_rule(self) -> None:
        # Corrected: legal claim_type (INFERENCE, != FACT) + the anti-pattern
        # encoded as voice_pattern_label=NEGATIVE_EXAMPLE.
        raw = json.dumps({
            "task_id": "t",
            "role_id": "R4",
            "role_version": "v2",
            "completion_status": "COMPLETE",
            "claims": [{
                "claim_id": "r4-claim-0001",
                "subject_id": "s",
                "role_id": "R4",
                "claim": "Kira does not use formal honorifics",
                "claim_type": "INFERENCE",
                "voice_pattern_label": "NEGATIVE_EXAMPLE",
                "source_evidence_ids": ["e1"],
                "source_type_summary": ["OWNER_DIRECT"],
                "confidence": "POSSIBLE",
                "rationale_summary": "anti-pattern inferred from the corpus",
                "status": "PROPOSED",
                "target_module_or_layer": "voice.address_forms",
            }],
            "unknowns": [],
            "contradictions": [],
            "provenance_summary": {},
            "requests_for_more_evidence": [],
            "warnings": [],
            "questions_for_r1": [],
            "new_source_evidence": [],
        }, ensure_ascii=False)
        result = _parse_role_result(raw)
        assert result.claims[0].voice_pattern_label.value == "NEGATIVE_EXAMPLE"
        assert result.claims[0].claim_type is ClaimType.INFERENCE  # != FACT
        assert voice_label_violations(result.claims) == ()


class TestHandAuthoredMinimalNegatives:
    """Hand-authored (NOT verbatim historical) minimal negatives for the
    claim_type=UNKNOWN permission seam."""

    def _result_json(self, role_id, role_version, target):
        return json.dumps({
            "task_id": "task-001",
            "role_id": role_id,
            "role_version": role_version,
            "completion_status": "COMPLETE",
            "claims": [{
                "claim_id": f"{role_id.lower()}-claim-0001",
                "subject_id": "char-subject-1",
                "role_id": role_id,
                "claim": "insufficient evidence",
                "claim_type": "UNKNOWN",
                "source_evidence_ids": [],
                "source_type_summary": ["OWNER_DIRECT"],
                "confidence": "UNKNOWN",
                "rationale_summary": "gap claim",
                "status": "PROPOSED",
                "target_module_or_layer": target,
            }],
            "unknowns": [],
            "contradictions": [],
            "provenance_summary": {},
            "requests_for_more_evidence": [],
            "warnings": [],
            "questions_for_r1": [],
            "new_source_evidence": [],
        }, ensure_ascii=False)

    def test_r2_claim_type_unknown_hand_authored_rejected_by_permissions(self) -> None:
        registry, profiles, evidence, task = _scope(
            "R2", "v1", _R2_PROMPT_REF, SourceType.OWNER_DIRECT,
        )
        raw = self._result_json("R2", "v1", "free.form.gap.target")
        with pytest.raises(ExecutorError) as ei:
            execute_role_task(task, registry, profiles, make_fake_provider(raw),
                              evidence, evidence_payloads=make_payload_map("se-001"))
        assert "ROLE_PERMISSION_VIOLATION" in str(ei.value)

    def test_r4_claim_type_unknown_hand_authored_rejected_by_permissions(self) -> None:
        registry, profiles, evidence, task = _scope(
            "R4", "v1", _R4_PROMPT_REF, SourceType.OWNER_DIRECT,
        )
        raw = self._result_json("R4", "v1", "voice.lexicon")
        with pytest.raises(ExecutorError) as ei:
            execute_role_task(task, registry, profiles, make_fake_provider(raw),
                              evidence, evidence_payloads=make_payload_map("se-001"))
        assert "ROLE_PERMISSION_VIOLATION" in str(ei.value)
