# -*- coding: utf-8 -*-
"""CRP convergence -- ACTIVE-prompt offline conformance gate (hermetic).

Derives the ACTIVE role versions/prompt refs/permissions from the authoritative
registry (never hardcoded old prompt paths), then proves the active prompts
carry the contract-convergence protections: axis separation, probability-
language guard, exact-bound identity copying, role-namespaced unique claim ids,
a claim_ids >= 2 contradiction contract, parser-survivable contradiction
outcomes, and legal per-role target families. Also proves canonical provider
policy (65536 / thinking disabled / budget 5 / no retry / no fallback) and the
R8 dedicated contract.

No provider, no network, no Kira, no canon/PAC/Sandbox access.
"""

from __future__ import annotations

import dataclasses
import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TOOLS_DIR = _REPO_ROOT / "tools"
for _p in (str(_REPO_ROOT), str(_TOOLS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import crp_kira_r4_runner as runner  # noqa: E402
from crp_provider_adapter import ProviderConfig  # noqa: E402

from services.crp_authoring import (  # noqa: E402
    ClaimType,
    ExecutionType,
    PERMISSIONS_BY_ROLE,
    Permission,
    RoleStatus,
)
from services.crp_authoring.registry import load_role_registry  # noqa: E402
from services.crp_authoring.r8_llm_judgment import (  # noqa: E402
    R8_ROLE_ID,
    R8_ROLE_VERSION,
    _R8_PROMPT_PATH,
    _SEMANTIC_CHECK_IDS,
)

_AUTHORING_ROLES = ("R1", "R2", "R3", "R4")


def _registry():
    return load_role_registry()


def _prompt_text(role_id: str) -> str:
    return (_REPO_ROOT / _registry().get(role_id).prompt_ref).read_text(encoding="utf-8")


def _sections(text: str) -> dict:
    result: dict = {}
    for block in text.split("\n## "):
        if not block.strip():
            continue
        parts = block.split("\n", 1)
        result[parts[0].strip()] = parts[1] if len(parts) > 1 else ""
    return result


def _claim_type_enum_values(text: str) -> set:
    m = re.search(r'"claim_type":\s*"([^"]+)"', text)
    if not m:
        return set()
    return {v.strip() for v in m.group(1).split("|")}


class TestCanonicalTopology:
    def test_canonical_role_order(self) -> None:
        assert runner.ROLE_ORDER == ("R1", "R2", "R3", "R4")

    def test_canonical_provider_role_count_is_five(self) -> None:
        assert runner.CANONICAL_RECONSTRUCTION_ROLE_IDS == ("R1", "R2", "R3", "R4", "R8")
        assert len(runner.CANONICAL_RECONSTRUCTION_ROLE_IDS) == 5


class TestActiveVersionPath:
    EXPECTED = {"R1": "v4", "R2": "v4", "R3": "v2", "R4": "v3"}

    def test_active_registry_versions(self) -> None:
        reg = _registry()
        for rid, ver in self.EXPECTED.items():
            entry = reg.get(rid)
            assert entry.version == ver
            assert entry.status is RoleStatus.ACTIVE
            assert entry.execution_type is ExecutionType.LLM_ROLE

    def test_active_prompt_refs_exist(self) -> None:
        for rid in _AUTHORING_ROLES:
            assert (_REPO_ROOT / _registry().get(rid).prompt_ref).is_file()

    def test_runner_pins_match_registry(self) -> None:
        reg = _registry()
        for rid in _AUTHORING_ROLES:
            assert runner.ROLE_VERSIONS[rid] == reg.get(rid).version

    def test_predecessor_versions(self) -> None:
        reg = _registry()
        assert reg.get("R1").predecessor_version == "v3"
        assert reg.get("R2").predecessor_version == "v3"
        assert reg.get("R3").predecessor_version == "v1"


class TestAxisSeparation:
    def test_axis_separation_section_present(self) -> None:
        for rid in _AUTHORING_ROLES:
            assert "AXIS_SEPARATION" in _sections(_prompt_text(rid))

    def test_claim_type_enum_uses_only_claimtype_values(self) -> None:
        legal = {ct.value for ct in ClaimType}
        for rid in _AUTHORING_ROLES:
            vals = _claim_type_enum_values(_prompt_text(rid))
            assert vals, rid
            assert vals <= legal, f"{rid}: illegal claim_type values {vals - legal}"

    def test_axis_separation_names_cross_axis_values_as_forbidden(self) -> None:
        for rid in _AUTHORING_ROLES:
            body = _sections(_prompt_text(rid)).get("AXIS_SEPARATION", "")
            assert "Confidence values, NEVER ClaimType values" in body
            assert "SourceType values, NEVER ClaimType values" in body
            assert "claim_type = PROBABLE" in body

    def test_r4_voice_labels_stay_on_voice_pattern_label(self) -> None:
        vals = _claim_type_enum_values(_prompt_text("R4"))
        # VoicePatternLabel values must never leak into R4's claim_type enum.
        for v in ("OBSERVED", "GENERATED_RULE", "NEGATIVE_EXAMPLE"):
            assert v not in vals
        body = _sections(_prompt_text("R4")).get("AXIS_SEPARATION", "")
        assert "voice_pattern_label" in body


class TestExactBinding:
    def test_exact_binding_section_present(self) -> None:
        for rid in _AUTHORING_ROLES:
            body = _sections(_prompt_text(rid)).get("EXACT_BINDING", "")
            assert body, rid
            low = body.lower()
            assert "task_id" in low
            assert "role_version" in low
            assert "claims[].subject_id" in low
            assert "claims[].role_id" in low
            assert "contradictions[].subject_id" in low

    def test_r1_exact_binding_covers_new_source_evidence_subject(self) -> None:
        body = _sections(_prompt_text("R1")).get("EXACT_BINDING", "").lower()
        assert "new_source_evidence[].subject_id" in body


class TestClaimIds:
    def test_role_namespaced_claim_ids(self) -> None:
        for rid, prefix in (
            ("R1", "r1-claim-"),
            ("R2", "r2-claim-"),
            ("R3", "r3-claim-"),
            ("R4", "r4-claim-"),
        ):
            body = _sections(_prompt_text(rid)).get("CLAIM_ID_RULES", "")
            assert prefix in body, rid

    def test_claim_id_namespaces_do_not_collide(self) -> None:
        prefixes = {"r1-claim-", "r2-claim-", "r3-claim-", "r4-claim-"}
        assert len(prefixes) == 4


class TestContradictionContract:
    def test_output_skeleton_claim_ids_ge_2(self) -> None:
        for rid in _AUTHORING_ROLES:
            text = _prompt_text(rid)
            assert '"claim_ids": ["<string>", "<string>"]' in text, rid
            assert '"claim_ids": ["<string>"]' not in text, rid

    def test_contradiction_rules_require_at_least_two_claim_ids(self) -> None:
        for rid in _AUTHORING_ROLES:
            body = _sections(_prompt_text(rid)).get("CONTRADICTION_RULES", "").lower()
            assert "at least two" in body, rid

    def test_contradiction_resolution_outcomes_are_parser_survivable(self) -> None:
        for rid in _AUTHORING_ROLES:
            text = _prompt_text(rid)
            assert '"resolution_status": "OPEN | UNRESOLVED"' in text, rid
            # No skeleton invites a resolution status that cannot survive the
            # current parser + R6 contract.
            assert '"resolution_status": "OPEN | RESOLVED_BY_EVIDENCE' not in text, rid
            assert '"resolution_status": "OPEN | OWNER_RESOLVED' not in text, rid


_FAMILY_OF_PERMISSION = {
    Permission.EMIT_CLAIMS_IDENTITY_BIOGRAPHY: "identity_biography",
    Permission.EMIT_CLAIMS_RELATIONSHIPS: "relationships",
    Permission.EMIT_CLAIMS_BOUNDARIES: "boundaries",
    Permission.EMIT_CLAIMS_SEED_MEMORY: "seed_memory",
    Permission.EMIT_CLAIMS_PSYCHOLOGY: "psychology",
    Permission.EMIT_CLAIMS_VOICE: "voice",
    Permission.EMIT_CLAIMS_INTIMACY: "intimacy",
    Permission.EMIT_CLAIMS_BEHAVIOR: "behavior",
}


class TestTargetFamilyContract:
    def test_target_family_contract_present_for_all(self) -> None:
        for rid in _AUTHORING_ROLES:
            assert "TARGET_FAMILY_CONTRACT" in _sections(_prompt_text(rid))

    def test_r1_prompt_target_guidance_matches_permissions(self) -> None:
        r1_allowed = {
            fam for perm, fam in _FAMILY_OF_PERMISSION.items()
            if perm in PERMISSIONS_BY_ROLE["R1"]
        }
        assert r1_allowed == {"identity_biography", "relationships", "boundaries", "seed_memory"}
        body = _sections(_prompt_text("R1")).get("TARGET_FAMILY_CONTRACT", "")
        for fam in r1_allowed:
            assert f"{fam}." in body, fam

    def test_r1_prompt_forbids_development_model(self) -> None:
        body = _sections(_prompt_text("R1")).get("TARGET_FAMILY_CONTRACT", "")
        assert "development_model" in body
        assert "must not emit" in body.lower()


class TestUnknownRouting:
    def test_r1_unknown_claim_type_is_permitted(self) -> None:
        assert Permission.EMIT_CLAIMS_UNKNOWN in PERMISSIONS_BY_ROLE["R1"]
        assert "UNKNOWN" in _claim_type_enum_values(_prompt_text("R1"))

    def test_r2_r3_r4_unknown_claim_type_forbidden(self) -> None:
        for rid in ("R2", "R3", "R4"):
            assert Permission.EMIT_CLAIMS_UNKNOWN not in PERMISSIONS_BY_ROLE[rid]
            assert "UNKNOWN" not in _claim_type_enum_values(_prompt_text(rid))


class TestProviderPolicy:
    def test_canonical_max_tokens_and_thinking(self) -> None:
        assert runner.LIVE_CANONICAL_MAX_TOKENS == 65536
        assert runner.LIVE_CANONICAL_EXTRA_PARAMS == {"thinking": {"type": "disabled"}}
        assert runner.LIVE_MAX_TOKENS == 8192  # default transport unchanged

    def test_budget_and_no_retry_fallback(self) -> None:
        assert runner.PROVIDER_CALL_BUDGET == 5
        fields = {f.name for f in dataclasses.fields(ProviderConfig)}
        assert "retry" not in fields
        assert "fallback" not in fields

    def test_canonical_versions_do_not_fall_through_to_default_8192(self) -> None:
        assert runner.LIVE_CANONICAL_MAX_TOKENS != runner.LIVE_MAX_TOKENS


class TestR8DedicatedConformance:
    def test_r8_identity_and_version(self) -> None:
        assert R8_ROLE_ID == "R8"
        assert R8_ROLE_VERSION == "v1"

    def test_r8_prompt_path_resolves(self) -> None:
        assert (_REPO_ROOT / _R8_PROMPT_PATH).is_file()

    def test_r8_semantic_check_ids_closed_set(self) -> None:
        assert set(_SEMANTIC_CHECK_IDS) == {
            "R8_ROLE_BOUNDARY_SEMANTIC",
            "R8_MODULE_PLACEMENT",
            "R8_UNKNOWN_COVERAGE",
        }

    def test_r8_not_in_authoring_registry(self) -> None:
        assert _registry().get("R8").status is not RoleStatus.ACTIVE


class TestHistoricalPromptImmutability:
    def test_historical_prompts_still_declare_historical_version_and_are_not_active(self) -> None:
        for rid, path, ver in (
            ("R1", "roles/vnext/ROLE_1_EVIDENCE_INTERVIEWER_v3_PROMPT.md", "v3"),
            ("R2", "roles/vnext/ROLE_2_PSYCHOLOGICAL_HYPOTHESIS_ANALYST_v3_PROMPT.md", "v3"),
            ("R3", "roles/vnext/ROLE_3_INTIMACY_PROFILE_SPECIALIST_v1_PROMPT.md", "v1"),
        ):
            text = (_REPO_ROOT / path).read_text(encoding="utf-8")
            assert f"prompt_version: {ver}" in text
            assert _registry().get(rid).prompt_ref != path


class TestR4CrossFieldClauses:
    """The ACTIVE R4 prompt (resolved via registry) must carry enforceable
    cross-field pre-output self-validation, not merely enum definitions."""

    def _validation(self) -> str:
        return _sections(_prompt_text("R4")).get("FINAL_PRE_OUTPUT_VALIDATION", "")

    def test_final_pre_output_validation_sections_present(self) -> None:
        sections = _sections(_prompt_text("R4"))
        assert "FINAL_PRE_OUTPUT_VALIDATION" in sections
        assert "FINAL_SELF_CHECK_CHECKLIST" in sections

    def test_inferred_confidence_clause(self) -> None:
        body = self._validation()
        assert "`confidence` MUST be exactly `POSSIBLE` or `UNKNOWN`" in body
        assert "`PROBABLE` is INVALID here" in body
        assert "with `confidence = PROBABLE`" in body

    def test_generated_rule_clause(self) -> None:
        body = self._validation()
        assert "MUST include `MODEL_EXAMPLE`" in body
        assert "`confidence` MUST be exactly `POSSIBLE` or `UNKNOWN`" in body

    def test_negative_example_clause(self) -> None:
        body = self._validation()
        assert "`claim_type` MUST NOT be `FACT`" in body

    def test_r4_only_and_voice_target_clause(self) -> None:
        body = self._validation()
        assert "`role_id` MUST be `R4`" in body
        assert "start with `voice.`" in body
