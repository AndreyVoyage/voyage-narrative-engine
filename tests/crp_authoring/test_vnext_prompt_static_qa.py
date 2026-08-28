#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CRP MVP S2B-part-2 -- static (non-LLM) vNext prompt QA.

Reads the vNext prompt files as plain text and verifies structural/semantic
contract markers (section presence, metadata, typed-output keyword presence,
role-specific boundaries). No fixtures, no production imports, no provider, no
Kira. Mirrors ``test_architecture_boundary.py``'s file-reading style but over
Markdown text presence, not AST.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]

_PIDS = {
    "R1": "ROLE_1_EVIDENCE_INTERVIEWER",
    "R2": "ROLE_2_PSYCHOLOGICAL_HYPOTHESIS_ANALYST",
    "R4": "ROLE_4_VOICE_RECONSTRUCTION_ANALYST",
    "R3": "ROLE_3_INTIMACY_PROFILE_SPECIALIST",
}

_ALL_ROLES = ["R1", "R2", "R4", "R3"]

_PROMPT_PATHS = {
    "R1": _REPO_ROOT / "roles" / "vnext" / "ROLE_1_EVIDENCE_INTERVIEWER_v1_PROMPT.md",
    "R2": _REPO_ROOT / "roles" / "vnext" / "ROLE_2_PSYCHOLOGICAL_HYPOTHESIS_ANALYST_v1_PROMPT.md",
    "R4": _REPO_ROOT / "roles" / "vnext" / "ROLE_4_VOICE_RECONSTRUCTION_ANALYST_v1_PROMPT.md",
    "R3": _REPO_ROOT / "roles" / "vnext" / "ROLE_3_INTIMACY_PROFILE_SPECIALIST_v1_PROMPT.md",
}

REQUIRED_SECTIONS = (
    "ROLE_IDENTITY",
    "PURPOSE",
    "AUTHORIZED_INPUTS",
    "FORBIDDEN_INPUTS",
    "ALLOWED_OPERATIONS",
    "FORBIDDEN_OPERATIONS",
    "EVIDENCE_RULES",
    "PROVENANCE_RULES",
    "CONFIDENCE_RULES",
    "CONTRADICTION_RULES",
    "OUTPUT_CONTRACT",
    "STOP_CONDITIONS",
    "REVISION_ROUND",
    "CANON_BOUNDARY",
    "PAC_SANDBOX_BOUNDARY",
    "NO_HIDDEN_EVAL",
    "NO_CHAIN_OF_THOUGHT_DISCLOSURE",
)


def _load() -> dict[str, str]:
    texts: dict[str, str] = {}
    for role_id, path in _PROMPT_PATHS.items():
        assert path.exists(), f"missing vNext prompt file: {path}"
        texts[role_id] = path.read_text(encoding="utf-8")
    return texts


def _sections(text: str) -> dict[str, str]:
    """Split prompt text into ``section_name -> body`` by ``## `` headings."""
    result: dict[str, str] = {}
    for block in text.split("\n## "):
        if not block.strip():
            continue
        parts = block.split("\n", 1)
        name = parts[0].strip()
        body = parts[1] if len(parts) > 1 else ""
        result[name] = body
    return result


def _lower(text: str) -> str:
    return text.lower()


class TestCommonPromptContract:
    @pytest.mark.parametrize("role_id", _ALL_ROLES)
    def test_all_required_sections_present(self, role_id: str) -> None:
        sections = _sections(_load()[role_id])
        missing = [s for s in REQUIRED_SECTIONS if s not in sections]
        assert not missing, f"{role_id}: missing sections {missing}"

    @pytest.mark.parametrize("role_id", _ALL_ROLES)
    def test_metadata_present(self, role_id: str) -> None:
        text = _load()[role_id]
        assert f"role_id: {role_id}" in text
        assert f"prompt_id: {_PIDS[role_id]}" in text
        assert "prompt_version: v1" in text
        assert "contract_version" in text and "1.0" in text
        assert "status: AUTHORING_READY" in text

    @pytest.mark.parametrize("role_id", _ALL_ROLES)
    def test_typed_output_keywords_present(self, role_id: str) -> None:
        text = _load()[role_id]
        for key in ("target_module_or_layer", "source_type_summary", "completion_status"):
            assert key in text, f"{role_id}: missing typed-output key {key!r}"

    @pytest.mark.parametrize("role_id", _ALL_ROLES)
    def test_provenance_rules_mention_provenance(self, role_id: str) -> None:
        body = _sections(_load()[role_id])["PROVENANCE_RULES"].lower()
        assert "provenance" in body, f"{role_id}: PROVENANCE_RULES lacks provenance"

    @pytest.mark.parametrize("role_id", _ALL_ROLES)
    def test_contradiction_rules_preserve(self, role_id: str) -> None:
        body = _sections(_load()[role_id])["CONTRADICTION_RULES"].lower()
        assert "preserved" in body
        assert "silently resolved" in body

    @pytest.mark.parametrize("role_id", _ALL_ROLES)
    def test_canon_boundary_no_canon_write(self, role_id: str) -> None:
        body = _sections(_load()[role_id])["CANON_BOUNDARY"].lower()
        assert "no canon authority" in body
        assert "write canon" in body

    @pytest.mark.parametrize("role_id", _ALL_ROLES)
    def test_pac_sandbox_boundary_denied(self, role_id: str) -> None:
        body = _sections(_load()[role_id])["PAC_SANDBOX_BOUNDARY"].lower()
        assert "pac" in body
        assert "sandbox" in body
        assert "direct" in body

    @pytest.mark.parametrize("role_id", _ALL_ROLES)
    def test_no_hidden_eval(self, role_id: str) -> None:
        body = _sections(_load()[role_id])["NO_HIDDEN_EVAL"].lower()
        assert "kira" in body
        assert "hidden" in body

    @pytest.mark.parametrize("role_id", _ALL_ROLES)
    def test_no_chain_of_thought_disclosure(self, role_id: str) -> None:
        body = _sections(_load()[role_id])["NO_CHAIN_OF_THOUGHT_DISCLOSURE"].lower()
        assert "rationale_summary" in body
        assert "chain-of-thought" in body


class TestR1Prompt:
    def test_evidence_only_boundary(self) -> None:
        low = _lower(_load()["R1"]).replace(" ", "")
        assert "inferpsychology" in low or "infer psychology" in _lower(_load()["R1"])
        assert "psychology" in low
        assert "personality" in low
        assert "sexuality" in low

    def test_no_autofill_or_literary_expansion(self) -> None:
        low = _lower(_load()["R1"])
        assert "literary expansion" in low
        assert "auto-fill" in low or "autofill" in low

    def test_unknown_only_claims(self) -> None:
        text = _load()["R1"]
        assert "claim_type=UNKNOWN" in text.replace(" ", "")

    def test_asks_instead_of_fills(self) -> None:
        low = _lower(_load()["R1"])
        assert "requests_for_more_evidence" in low
        assert "unknown" in low


_R1_V3_PATH = _REPO_ROOT / "roles" / "vnext" / "ROLE_1_EVIDENCE_INTERVIEWER_v3_PROMPT.md"


class TestR1V3QualityCorrection:
    """Static QA for the owner-approved R1 v3 quality correction
    (CRP-OD-R4-KIRA-R1-V3-01). The v1-based common-contract checks above are
    unchanged; these read the new v3 prompt file directly."""

    def _text(self) -> str:
        assert _R1_V3_PATH.exists(), f"missing v3 prompt: {_R1_V3_PATH}"
        return _R1_V3_PATH.read_text(encoding="utf-8")

    def test_v3_metadata_and_predecessor(self) -> None:
        text = self._text()
        assert "prompt_version: v3" in text
        assert "predecessor_version: v2" in text
        assert "role_id: R1" in text
        assert "prompt_id: ROLE_1_EVIDENCE_INTERVIEWER" in text

    def test_v3_requires_corroborating_multi_source_merge(self) -> None:
        low = self._text().lower()
        assert "corroboration" in low
        assert "union of every supporting" in low or "union of all supporting" in low
        assert "one self-contained claim" in low
        assert "do not merge materially different propositions" in low

    def test_v3_requires_self_contained_claims(self) -> None:
        low = self._text().lower()
        assert "self-contained" in low
        assert "understandable independently" in low
        assert "must not depend on a previous claim" in low

    def test_v3_forbids_semantic_duplicate_restatements(self) -> None:
        low = self._text().lower()
        assert "semantic_duplicates" in low
        assert "same substantive proposition" in low
        assert "minor wording differences" in low
        assert "keep distinct propositions distinct" in low

    def test_v3_requires_non_mechanical_rationale(self) -> None:
        low = " ".join(self._text().lower().split())
        assert "rationale_summary" in low
        assert "must not mechanically paraphrase the" in low
        assert "evidence states" in low  # named forbidden boilerplate
        assert "never a reasoning trace" in low

    def test_v3_requires_exact_claim_level_evidence_accounting(self) -> None:
        text = self._text()
        low = text.lower()
        assert "union(claim.source_evidence_ids)" in text
        assert "allowed_evidence_ids" in text
        assert "must equal" in low and "exactly" in low
        assert "hollow" in low  # do not invent a hollow UNKNOWN just for coverage

    def test_v3_requires_provenance_summary_consistency(self) -> None:
        text = self._text()
        low = text.lower()
        assert "provenance_summary" in text
        assert "sources_used" in text
        assert "union of every" in low
        assert "no missing id" in low and "no extra id" in low

    def test_v3_preserves_v2_output_shape_and_a_only_boundary(self) -> None:
        text = self._text()
        for key in ("target_module_or_layer", "source_type_summary",
                    "completion_status", "claim_type", "provenance_summary"):
            assert key in text, f"v3 dropped output key {key!r}"
        low = text.lower()
        assert "infer psychology" in low
        assert "claim_type=UNKNOWN" in text.replace(" ", "")
        assert "contradictions are preserved" in low


class TestR2Prompt:
    def test_psychology_only_target(self) -> None:
        text = _load()["R2"]
        assert "psychology.P" in text

    def test_competing_hypotheses(self) -> None:
        low = _lower(_load()["R2"])
        assert "competing hypotheses" in low

    def test_no_single_forced_label(self) -> None:
        low = _lower(_load()["R2"])
        assert "single" in low
        assert "label" in low

    def test_no_numeric_baseline(self) -> None:
        low = _lower(_load()["R2"])
        assert "vscno" in low
        assert "baseline" in low

    def test_no_canon_write(self) -> None:
        low = _lower(_load()["R2"])
        assert "write canon" in low


class TestR4Prompt:
    def test_voice_only_boundary(self) -> None:
        text = _load()["R4"]
        assert "voice." in text

    def test_four_voice_pattern_labels_present(self) -> None:
        text = _load()["R4"]
        for label in ("OBSERVED", "INFERRED", "GENERATED_RULE", "NEGATIVE_EXAMPLE"):
            assert label in text, f"R4: missing voice label {label}"

    def test_no_psychology_personality_inference(self) -> None:
        low = _lower(_load()["R4"])
        assert "psychology" in low
        assert "personality" in low

    def test_no_free_form_voice_monolith(self) -> None:
        low = _lower(_load()["R4"])
        assert "voice portrait" in low

    def test_axes_independence_stated(self) -> None:
        low = _lower(_load()["R4"])
        assert "independent" in low


class TestR3Prompt:
    def test_gated_activation_rules_section_present(self) -> None:
        sections = _sections(_load()["R3"])
        assert "GATED_ACTIVATION_RULES" in sections

    def test_optional_gated_skippable_identity(self) -> None:
        low = _lower(_load()["R3"])
        assert "optional" in low
        assert "gated" in low
        assert "skippable" in low

    def test_human_activation_required(self) -> None:
        body = _sections(_load()["R3"])["GATED_ACTIVATION_RULES"].lower()
        assert "activation_authorization_ref" in body
        assert "human-driven" in body

    def test_no_self_activation(self) -> None:
        body = _sections(_load()["R3"])["GATED_ACTIVATION_RULES"].lower()
        assert "self-activation" in body

    def test_relevant_evidence_not_authorization(self) -> None:
        body = _sections(_load()["R3"])["GATED_ACTIVATION_RULES"].lower()
        assert "does not" in body
        assert "authorize" in body

    def test_intimacy_target_family(self) -> None:
        text = _load()["R3"]
        assert "intimacy." in text

    def test_psychology_and_voice_excluded_for_r3(self) -> None:
        text = _load()["R3"]
        assert "psychology.*" in text
        assert "voice.*" in text

    def test_no_appearance_inference(self) -> None:
        low = _lower(_load()["R3"])
        for term in ("appearance", "body features", "clothing", "attractiveness",
                     "facial expression", "physiognomy", "presentation style"):
            assert term in low, f"R3: missing appearance-boundary term {term!r}"

    def test_no_attachment_only_inference(self) -> None:
        low = _lower(_load()["R3"])
        assert "attachment style" in low
        assert "personality type" in low
        assert "psychological archetype" in low
        assert "relationship score" in low

    def test_no_stereotype_inference(self) -> None:
        low = _lower(_load()["R3"])
        assert "stereotype" in low

    def test_no_cross_character_comparison(self) -> None:
        low = _lower(_load()["R3"])
        assert "another named character" in low

    def test_no_sexual_history_autofill(self) -> None:
        low = _lower(_load()["R3"])
        assert "autofill" in low

    def test_no_forced_completeness(self) -> None:
        low = _lower(_load()["R3"])
        assert "force completeness" in low

    def test_no_unknown_claim_emission(self) -> None:
        low = _lower(_load()["R3"])
        assert "claim_type=unknown" in low.replace(" ", "")
        assert "insufficient_evidence" in low


_R2_V2_PATH = _REPO_ROOT / "roles" / "vnext" / "ROLE_2_PSYCHOLOGICAL_HYPOTHESIS_ANALYST_v2_PROMPT.md"
_R2_V3_PATH = _REPO_ROOT / "roles" / "vnext" / "ROLE_2_PSYCHOLOGICAL_HYPOTHESIS_ANALYST_v3_PROMPT.md"

_NO_UNKNOWN_CLAIM_TYPE_ENUM = (
    '"claim_type": "HYPOTHESIS | INFERENCE | OBSERVATION | SELF_REPORT | '
    'THIRD_PARTY_REPORT | BEHAVIORAL_EVIDENCE | FACT | CONTRADICTION"'
)
_UNKNOWN_CLAIM_TYPE_ENUM = (
    '"claim_type": "HYPOTHESIS | INFERENCE | OBSERVATION | SELF_REPORT | '
    'THIRD_PARTY_REPORT | BEHAVIORAL_EVIDENCE | FACT | CONTRADICTION | UNKNOWN"'
)


class TestR2V3ContractCorrection:
    """Static QA for the R2 v3 prompt-contract correction (RUN_010):
    claim_type=UNKNOWN is not emittable by R2; insufficient evidence routes to
    top-level ``unknowns`` instead of a UNKNOWN claim. v2 remains unchanged."""

    def _text(self) -> str:
        assert _R2_V3_PATH.exists(), f"missing v3 prompt: {_R2_V3_PATH}"
        return _R2_V3_PATH.read_text(encoding="utf-8")

    def test_v3_metadata_and_predecessor(self) -> None:
        text = self._text()
        assert "prompt_version: v3" in text
        assert "predecessor_version: v2" in text
        assert "role_id: R2" in text
        assert "prompt_id: ROLE_2_PSYCHOLOGICAL_HYPOTHESIS_ANALYST" in text

    def test_v3_claim_type_enum_excludes_unknown(self) -> None:
        text = self._text()
        assert _NO_UNKNOWN_CLAIM_TYPE_ENUM in text
        assert _UNKNOWN_CLAIM_TYPE_ENUM not in text

    def test_v3_unknown_not_emittable_stated(self) -> None:
        low = self._text().lower()
        assert "claim_type=unknown" in low.replace(" ", "")
        assert "not emittable" in low

    def test_v3_routes_insufficient_evidence_to_unknowns(self) -> None:
        low = " ".join(self._text().lower().split())
        assert "insufficient evidence" in low
        assert "top-level" in low
        assert "unknowns" in low
        assert "completion_status" in low
        assert "requests_for_more_evidence" in low
        assert "questions_for_r1" in low

    def test_v2_remains_unchanged_and_present(self) -> None:
        assert _R2_V2_PATH.exists(), "v2 prompt must remain on disk"
        text = _R2_V2_PATH.read_text(encoding="utf-8")
        assert "prompt_version: v2" in text
        assert _UNKNOWN_CLAIM_TYPE_ENUM in text


_R4_V1_PATH = _REPO_ROOT / "roles" / "vnext" / "ROLE_4_VOICE_RECONSTRUCTION_ANALYST_v1_PROMPT.md"
_R4_V2_PATH = _REPO_ROOT / "roles" / "vnext" / "ROLE_4_VOICE_RECONSTRUCTION_ANALYST_v2_PROMPT.md"

# Stale v1 instructions the RUN_012 correction removes from v2 (matched against
# whitespace-collapsed prompt text so line wrapping is irrelevant).
_STALE_V1_MARKERS = (
    "FOLLOW_UP_REQUIRED_BEFORE_REAL_R4_EXECUTION",
    "not yet part of the executor's",
    "do not add a `voice_pattern_label` key yet",
    "executor gap",
)


def _collapsed(text: str) -> str:
    return " ".join(text.split())


class TestR4V2ContractCorrection:
    """Static QA for the R4 v2 prompt-contract / evidence-boundary correction
    (RUN_012): `voice_pattern_label` is an executor-supported first-class field
    independent of `claim_type`; `claim_type=NEGATIVE_EXAMPLE` is never legal;
    `claim_type=UNKNOWN` is not emittable by R4 (R4 lacks EMIT_CLAIMS_UNKNOWN)
    and insufficient evidence routes to top-level mechanisms; OBSERVED voice
    claims require actual attributed speech, not owner-authored descriptive
    prose. v1 remains unchanged on disk."""

    def _text(self) -> str:
        assert _R4_V2_PATH.exists(), f"missing v2 prompt: {_R4_V2_PATH}"
        return _R4_V2_PATH.read_text(encoding="utf-8")

    def test_v2_metadata_and_predecessor(self) -> None:
        text = self._text()
        assert "prompt_version: v2" in text
        assert "predecessor_version: v1" in text
        assert "role_id: R4" in text
        assert "prompt_id: ROLE_4_VOICE_RECONSTRUCTION_ANALYST" in text

    def test_v2_output_contract_includes_voice_pattern_label(self) -> None:
        text = self._text()
        # The OUTPUT_CONTRACT JSON example carries the key with the exact
        # executor-supported enum, not a parallel invented structure.
        assert (
            '"voice_pattern_label": "OBSERVED | INFERRED | GENERATED_RULE | NEGATIVE_EXAMPLE"'
            in text
        )
        assert "voice_pattern_label" in _sections(text)["OUTPUT_CONTRACT"]

    def test_v2_states_executor_supports_voice_pattern_label(self) -> None:
        low = _collapsed(self._text()).lower()
        assert "executor supports the `voice_pattern_label` key" in low
        assert "first-class executor-parsed field" in low

    def test_v2_legal_voice_pattern_label_values(self) -> None:
        text = self._text()
        for label in ("OBSERVED", "INFERRED", "GENERATED_RULE", "NEGATIVE_EXAMPLE"):
            assert label in text, f"R4 v2: missing voice_pattern_label value {label}"

    def test_v2_label_axis_independent_of_claim_type(self) -> None:
        low = _collapsed(self._text()).lower()
        assert "independent of `claim_type`" in low

    def test_v2_forbids_claim_type_negative_example(self) -> None:
        low = _collapsed(self._text()).lower()
        assert "`claim_type = negative_example` is never legal" in low
        assert "`negative_example` is not a `claimtype` value at all" in low
        # The anti-pattern is encoded on the label axis instead.
        assert "encode an anti-pattern as `voice_pattern_label = negative_example`" in low
        # And a NEGATIVE_EXAMPLE claim_type must not be FACT.
        assert "the `claim_type` must not be `fact`" in low

    def test_v2_claim_type_enum_excludes_unknown(self) -> None:
        text = self._text()
        # OUTPUT_CONTRACT JSON claim_type enum: exactly the values R4 may emit,
        # no UNKNOWN (R4 lacks EMIT_CLAIMS_UNKNOWN; executor rejects it).
        assert (
            '"claim_type": "OBSERVATION | INFERENCE | BEHAVIORAL_EVIDENCE | HYPOTHESIS | CONTRADICTION"'
            in text
        )
        assert (
            '"claim_type": "OBSERVATION | INFERENCE | BEHAVIORAL_EVIDENCE | HYPOTHESIS | CONTRADICTION | UNKNOWN"'
            not in text
        )
        low = _collapsed(text).lower()
        assert (
            "the legal `claim_type` values r4 may emit are "
            "`observation | inference | behavioral_evidence | hypothesis | contradiction`"
            in low
        )
        assert "| contradiction | unknown`" not in low

    def test_v2_prohibits_claim_type_unknown(self) -> None:
        low = _collapsed(self._text()).lower()
        assert "`claim_type = unknown` is not emittable by r4" in low
        assert "r4 lacks `emit_claims_unknown`" in low
        assert "do not emit a claim with `claim_type = unknown`" in low

    def test_v2_routes_insufficient_evidence_to_top_level_mechanisms(self) -> None:
        low = _collapsed(_sections(self._text())["STOP_CONDITIONS"]).lower()
        assert "top-level `unknowns` array" in low
        assert "completion_status` to `insufficient_evidence`" in low
        assert "requests_for_more_evidence" in low
        assert "questions_for_r1" in low

    def test_v2_stale_not_supported_instruction_is_gone(self) -> None:
        collapsed = _collapsed(self._text())
        for marker in _STALE_V1_MARKERS:
            assert marker not in collapsed, (
                f"R4 v2 still carries stale v1 marker: {marker!r}"
            )

    def test_v2_evidence_boundary_distinguishes_speech_from_prose(self) -> None:
        text = self._text()
        assert "VOICE_EVIDENCE_BOUNDARY" in _sections(text)
        low = _collapsed(text).lower()
        assert "actual character speech evidence" in low
        assert "owner-authored descriptive prose about the character" in low
        assert "actual attributed speech vs description about speech" in low

    def test_v2_observed_voice_claims_require_actual_speech_evidence(self) -> None:
        body = _sections(self._text())["VOICE_EVIDENCE_BOUNDARY"]
        low = _collapsed(body).lower()
        assert "requires actual speech evidence" in low
        assert "`direct_quote` attributable to kira" in low
        assert "speaker-attributed dialogue" in low
        for dim in ("voice.lexicon", "voice.syntax", "voice.register",
                    "voice.address_forms", "voice.taboo_avoidance"):
            assert dim in body
        # Owner-authored prose does not by itself prove literal speech.
        assert "stop is absolute at every state" in low
        assert "does not automatically prove" in low

    def test_v2_prose_only_supports_bounded_inference_not_fake_observed(self) -> None:
        low = _collapsed(_sections(self._text())["VOICE_EVIDENCE_BOUNDARY"]).lower()
        assert "may support a bounded `inferred` or `generated_rule` voice pattern" in low
        assert "it must not be mislabeled `observed`" in low
        assert "no quote or exact wording may be invented" in low
        assert "use `unknowns` / `requests_for_more_evidence`" in low

    def test_v1_remains_unchanged_and_present(self) -> None:
        assert _R4_V1_PATH.exists(), "v1 prompt must remain on disk"
        collapsed = _collapsed(_R4_V1_PATH.read_text(encoding="utf-8"))
        assert "prompt_version: v1" in collapsed
        # The stale instructions the correction targets are still in v1,
        # proving v1 was not edited by this change.
        assert "FOLLOW_UP_REQUIRED_BEFORE_REAL_R4_EXECUTION" in collapsed
        assert "do not add a `voice_pattern_label` key yet" in collapsed
        # v1's claim_type enum still carries UNKNOWN (removed only in v2).
        assert (
            '"claim_type": "OBSERVATION | INFERENCE | BEHAVIORAL_EVIDENCE | HYPOTHESIS | CONTRADICTION | UNKNOWN"'
            in _R4_V1_PATH.read_text(encoding="utf-8")
        )
