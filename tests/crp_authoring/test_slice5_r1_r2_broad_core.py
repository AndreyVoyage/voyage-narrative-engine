#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CRP MVP Slice 5 -- R1/R2 broad-core role-intelligence contract tests.

Deterministic, offlined static checks over the versioned v2 prompt files and
the registry/permission grant surface. No provider, no Kira, no LLM.
"""

from __future__ import annotations

from pathlib import Path

from services.crp_authoring import (
    PERMISSIONS_BY_ROLE,
    Permission,
)
from services.crp_authoring.registry import load_role_registry

_REPO_ROOT = Path(__file__).resolve().parents[2]

_R1_V2 = _REPO_ROOT / "roles" / "vnext" / "ROLE_1_EVIDENCE_INTERVIEWER_v2_PROMPT.md"
_R2_V2 = _REPO_ROOT / "roles" / "vnext" / "ROLE_2_PSYCHOLOGICAL_HYPOTHESIS_ANALYST_v2_PROMPT.md"


def _text(path: Path) -> str:
    assert path.exists(), f"missing file: {path}"
    return path.read_text(encoding="utf-8")


def _low(path: Path) -> str:
    return _text(path).lower()


class TestR1V2PromptContract:
    def test_direct_evidence_only(self) -> None:
        low = _low(_R1_V2)
        assert "direct-evidence" in low or "direct evidence" in low
        assert "direct fact" in low or "direct fact" in low.replace("\n", " ")

    def test_unknown_on_insufficient_evidence(self) -> None:
        low = _low(_R1_V2)
        assert "insufficient evidence" in low
        assert "unknown" in low

    def test_no_invented_motives(self) -> None:
        low = _low(_R1_V2)
        assert "infer motive" in low

    def test_no_invented_cause(self) -> None:
        low = _low(_R1_V2)
        assert "infer cause" in low

    def test_structural_relationship_boundary(self) -> None:
        low = _low(_R1_V2)
        assert "structural" in low
        assert "relation_type" in low
        # Trust/attraction/familiarity must be explicitly excluded for R1.
        assert "trust" in low
        assert "attraction" in low
        assert "familiarity" in low

    def test_seed_memory_boundary(self) -> None:
        low = _low(_R1_V2)
        assert "seed_memory" in low
        assert "not runtime memory" in low

    def test_general_boundaries_support(self) -> None:
        low = _low(_R1_V2)
        assert "boundaries." in low or "boundaries" in low

    def test_behavior_excluded_for_r1(self) -> None:
        low = _low(_R1_V2)
        assert "behavior" in low  # must be mentioned as excluded
        assert "emit `behavior.*` claims" in low or "behavior.*" in low

    def test_no_absence_as_negative_fact(self) -> None:
        low = _low(_R1_V2)
        assert "absence of evidence" in low


class TestR2V2PromptContract:
    def test_behavior_first_class(self) -> None:
        low = _low(_R2_V2)
        assert "behavior.*" in low or "behavior." in low
        assert "first-class" in low

    def test_psychology_beliefs_values_preferences_motivations(self) -> None:
        low = _low(_R2_V2)
        assert "beliefs" in low
        assert "values" in low
        assert "preferences" in low
        assert "motivations" in low

    def test_initial_relationship_state_boundary(self) -> None:
        low = _low(_R2_V2)
        assert "initial" in low
        assert "relationships" in low

    def test_runtime_evolution_excluded(self) -> None:
        low = _low(_R2_V2)
        assert "runtime evolution" in low
        assert "runtime memory" in low

    def test_hypothesis_fact_discipline(self) -> None:
        low = _low(_R2_V2)
        assert "hypothesis" in low
        assert "fact" in low

    def test_identity_biography_not_owned(self) -> None:
        low = _low(_R2_V2)
        assert "identity_biography" in low

    def test_seed_memory_not_owned(self) -> None:
        low = _low(_R2_V2)
        assert "seed_memory" in low


class TestSlice5RegistryVersions:
    def test_r1_authoritative_version_v4(self) -> None:
        # R1 advanced v3 -> v4 (CRP_ROLE_CONTRACT_CONVERGENCE_V1 correction);
        # the single-entry registry pins exactly v4, predecessor v3.
        registry = load_role_registry()
        assert registry.get("R1").version == "v4"
        assert registry.get("R1").predecessor_version == "v3"

    def test_r2_authoritative_version_v4(self) -> None:
        registry = load_role_registry()
        assert registry.get("R2").version == "v4"
        assert registry.get("R2").predecessor_version == "v3"

    def test_r1_prompt_ref_resolves_to_v4_file(self) -> None:
        registry = load_role_registry()
        assert registry.get("R1").prompt_ref.endswith("v4_PROMPT.md")

    def test_r2_prompt_ref_resolves_to_v4_file(self) -> None:
        registry = load_role_registry()
        assert registry.get("R2").prompt_ref.endswith("v4_PROMPT.md")


class TestSlice5PermissionSurface:
    def test_r1_has_expected_broad_core_grants(self) -> None:
        perms = PERMISSIONS_BY_ROLE["R1"]
        assert Permission.EMIT_CLAIMS_IDENTITY_BIOGRAPHY in perms
        assert Permission.EMIT_CLAIMS_RELATIONSHIPS in perms
        assert Permission.EMIT_CLAIMS_BOUNDARIES in perms
        assert Permission.EMIT_CLAIMS_SEED_MEMORY in perms
        assert Permission.EMIT_CLAIMS_BEHAVIOR not in perms

    def test_r2_has_expected_broad_core_grants(self) -> None:
        perms = PERMISSIONS_BY_ROLE["R2"]
        assert Permission.EMIT_CLAIMS_BEHAVIOR in perms
        assert Permission.EMIT_CLAIMS_RELATIONSHIPS in perms
        assert Permission.EMIT_CLAIMS_IDENTITY_BIOGRAPHY not in perms
        assert Permission.EMIT_CLAIMS_SEED_MEMORY not in perms
        assert Permission.EMIT_CLAIMS_BOUNDARIES not in perms

    def test_r4_unchanged(self) -> None:
        perms = PERMISSIONS_BY_ROLE["R4"]
        assert Permission.EMIT_CLAIMS_VOICE in perms
        assert Permission.EMIT_CLAIMS_IDENTITY_BIOGRAPHY not in perms
        assert Permission.EMIT_CLAIMS_BEHAVIOR not in perms
        assert Permission.EMIT_CLAIMS_RELATIONSHIPS not in perms
        assert Permission.EMIT_CLAIMS_BOUNDARIES not in perms
        assert Permission.EMIT_CLAIMS_SEED_MEMORY not in perms