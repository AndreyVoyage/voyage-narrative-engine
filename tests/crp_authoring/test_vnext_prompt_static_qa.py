#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CRP MVP S2B-part-2 -- static (non-LLM) vNext prompt QA.

Reads the three vNext prompt files as plain text and verifies structural/
semantic contract markers (section presence, metadata, typed-output keyword
presence, role-specific boundaries). No fixtures, no production imports, no
provider, no Kira. Mirrors ``test_architecture_boundary.py``'s file-reading
style but over Markdown text presence, not AST.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]

_PIDS = {
    "R1": "ROLE_1_EVIDENCE_INTERVIEWER",
    "R2": "ROLE_2_PSYCHOLOGICAL_HYPOTHESIS_ANALYST",
    "R4": "ROLE_4_VOICE_RECONSTRUCTION_ANALYST",
}

_PROMPT_PATHS = {
    "R1": _REPO_ROOT / "roles" / "vnext" / "ROLE_1_EVIDENCE_INTERVIEWER_v1_PROMPT.md",
    "R2": _REPO_ROOT / "roles" / "vnext" / "ROLE_2_PSYCHOLOGICAL_HYPOTHESIS_ANALYST_v1_PROMPT.md",
    "R4": _REPO_ROOT / "roles" / "vnext" / "ROLE_4_VOICE_RECONSTRUCTION_ANALYST_v1_PROMPT.md",
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
    @pytest.mark.parametrize("role_id", ["R1", "R2", "R4"])
    def test_all_required_sections_present(self, role_id: str) -> None:
        sections = _sections(_load()[role_id])
        missing = [s for s in REQUIRED_SECTIONS if s not in sections]
        assert not missing, f"{role_id}: missing sections {missing}"

    @pytest.mark.parametrize("role_id", ["R1", "R2", "R4"])
    def test_metadata_present(self, role_id: str) -> None:
        text = _load()[role_id]
        assert f"role_id: {role_id}" in text
        assert f"prompt_id: {_PIDS[role_id]}" in text
        assert "prompt_version: v1" in text
        assert "contract_version" in text and "1.0" in text
        assert "status: AUTHORING_READY" in text

    @pytest.mark.parametrize("role_id", ["R1", "R2", "R4"])
    def test_typed_output_keywords_present(self, role_id: str) -> None:
        text = _load()[role_id]
        for key in ("target_module_or_layer", "source_type_summary", "completion_status"):
            assert key in text, f"{role_id}: missing typed-output key {key!r}"

    @pytest.mark.parametrize("role_id", ["R1", "R2", "R4"])
    def test_provenance_rules_mention_provenance(self, role_id: str) -> None:
        body = _sections(_load()[role_id])["PROVENANCE_RULES"].lower()
        assert "provenance" in body, f"{role_id}: PROVENANCE_RULES lacks provenance"

    @pytest.mark.parametrize("role_id", ["R1", "R2", "R4"])
    def test_contradiction_rules_preserve(self, role_id: str) -> None:
        body = _sections(_load()[role_id])["CONTRADICTION_RULES"].lower()
        assert "preserved" in body
        assert "silently resolved" in body

    @pytest.mark.parametrize("role_id", ["R1", "R2", "R4"])
    def test_canon_boundary_no_canon_write(self, role_id: str) -> None:
        body = _sections(_load()[role_id])["CANON_BOUNDARY"].lower()
        assert "no canon authority" in body
        assert "write canon" in body

    @pytest.mark.parametrize("role_id", ["R1", "R2", "R4"])
    def test_pac_sandbox_boundary_denied(self, role_id: str) -> None:
        body = _sections(_load()[role_id])["PAC_SANDBOX_BOUNDARY"].lower()
        assert "pac" in body
        assert "sandbox" in body
        assert "direct" in body

    @pytest.mark.parametrize("role_id", ["R1", "R2", "R4"])
    def test_no_hidden_eval(self, role_id: str) -> None:
        body = _sections(_load()[role_id])["NO_HIDDEN_EVAL"].lower()
        assert "kira" in body
        assert "hidden" in body

    @pytest.mark.parametrize("role_id", ["R1", "R2", "R4"])
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