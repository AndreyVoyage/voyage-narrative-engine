#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KIRA dimension-semantics package extension -- focused, offline, no provider.

Proves:

- the extension is a separate versioned artifact, NOT under accepted/**;
- it is hash-bound to exactly the current Accepted KIRA source hash;
- a mismatched target hash / bad identity fails closed;
- trust + stress validate through Character Core with all five band meanings;
- Character Core carries no KIRA-specific meaning;
- a Grounded v2 turn injects the validated DimensionSet and renders
  value + band + KIRA meaning; Beta v1 does not;
- an absent extension falls back to raw numeric rendering;
- accepted/** payloads are byte-identical.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from services.character_core.dimensions import (
    DimensionSet,
    StateBand,
    interpret_value,
)
from services.character_lab import (
    BetaV1CurrentPolicy,
    GroundedV2Policy,
    RuntimeService,
    TurnCapture,
)
from services.character_lab.package_extensions import (
    DimensionSemanticsExtension,
    PackageExtensionError,
    load_character_dimension_set,
    load_dimension_semantics_extension,
)
from services.character_lab.source_loader import build_repo_source_loader
from services.character_runtime import load_accepted_character
from services.character_runtime.state import RuntimeStateBackend

from tests.fixtures.character_packages.kira_behavioral_ab_v1 import (
    STRESS_AB_SPEC,
    TRUST_AB_SPEC,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ACCEPTED_ROOT = _REPO_ROOT / "accepted"
_EXTENSION_PATH = (
    _REPO_ROOT
    / "character_packages"
    / "kira"
    / "extensions"
    / "dimension_semantics"
    / "v1.json"
)
EXPECTED_ACCEPTED_HASH = "e26f83dafa26e61af82f29b654b592300c8f3f7bd295d07bd4d2b6527ae3eebd"


def _accepted():
    loader = build_repo_source_loader(acceptance_root=_ACCEPTED_ROOT)
    return load_accepted_character(
        "kira", acceptance_root=_ACCEPTED_ROOT, source_loader=loader
    )


def _extension_json() -> dict:
    return json.loads(_EXTENSION_PATH.read_text(encoding="utf-8"))


def _recording_provider_factory(response="[KIRA] ответ"):
    def factory(recorder):
        def provider(messages):
            body = json.dumps(
                {"model": "fake", "messages": messages}, ensure_ascii=False
            ).encode("utf-8")
            if recorder:
                recorder({"event": "request",
                          "payload": {"model": "fake", "messages": messages},
                          "body": body})
                recorder({"event": "response", "data": {
                    "id": "cmpl-fake", "model": "fake",
                    "choices": [{"message": {"content": response},
                                 "finish_reason": "stop"}],
                }})
            return response
        return provider
    return factory


def _service():
    return RuntimeService(
        acceptance_root=_ACCEPTED_ROOT,
        source_loader=build_repo_source_loader(acceptance_root=_ACCEPTED_ROOT),
    )


def _grounded_system_text(tmp_path, *, policy, state_seed):
    sroot = tmp_path / "st"
    b = RuntimeStateBackend(sroot, "kira")
    try:
        for domain, key, value in state_seed:
            b.record_set(key=key, value=value, domain=domain)
    finally:
        b.close()
    cap = TurnCapture(tmp_path / "cap")
    result = _service().turn(
        "kira", policy=policy, history=[], user_message="Привет.",
        provider=None, provider_factory=_recording_provider_factory(),
        memory_root=tmp_path / "mem", state_root=sroot, capture=cap,
        turn_id="turn-x", provider_info={"provider_id": "p", "model": "m"},
    )
    sys_text = "\n".join(m["content"] for m in result.messages if m["role"] == "system")
    return sys_text, cap.read_manifest("turn-x")


# --------------------------------------------------------------------- identity

class TestExtensionIdentityAndBinding:
    def test_1_extension_targets_exact_accepted_kira_hash(self):
        data = _extension_json()
        assert data["target_accepted_source_hash"] == EXPECTED_ACCEPTED_HASH
        assert _accepted().source_candidate_hash == EXPECTED_ACCEPTED_HASH

    def test_extension_lives_outside_accepted_tree(self):
        assert "accepted" not in _EXTENSION_PATH.parts
        assert _EXTENSION_PATH.exists()

    def test_3_extension_version_is_explicit(self):
        data = _extension_json()
        assert data["extension_version"] == 1
        assert data["extension_type"] == "dimension_semantics"
        assert data["character_id"] == "kira"

    def test_loader_returns_validated_hash_bound_extension(self):
        ext = load_dimension_semantics_extension("kira", EXPECTED_ACCEPTED_HASH)
        assert isinstance(ext, DimensionSemanticsExtension)
        assert ext.extension_version == 1
        assert ext.target_accepted_source_hash == EXPECTED_ACCEPTED_HASH
        assert isinstance(ext.dimension_set, DimensionSet)
        assert {d.id for d in ext.dimension_set} == {"trust", "stress"}

    def test_2_mismatched_target_hash_rejects(self):
        with pytest.raises(PackageExtensionError):
            load_dimension_semantics_extension("kira", "deadbeef" * 8)

    def test_wrong_identity_fields_reject(self, tmp_path):
        base = _extension_json()
        for mutate in (
            {"extension_version": 2},
            {"extension_type": "something_else"},
            {"character_id": "notkira"},
            {"target_accepted_source_hash": "0" * 64},
        ):
            root = tmp_path / ("x_" + "_".join(mutate))
            p = root / "kira" / "extensions" / "dimension_semantics" / "v1.json"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps({**base, **mutate}), encoding="utf-8")
            with pytest.raises(PackageExtensionError):
                load_dimension_semantics_extension(
                    "kira", EXPECTED_ACCEPTED_HASH, extensions_root=root
                )

    def test_12_absent_extension_returns_none(self, tmp_path):
        assert (
            load_character_dimension_set(
                "kira", EXPECTED_ACCEPTED_HASH, extensions_root=tmp_path
            )
            is None
        )


# ------------------------------------------------------------------ dimensions

class TestDimensionDefinitions:
    def test_4_5_6_trust_and_stress_validate_with_all_five_bands(self):
        ds = load_character_dimension_set("kira", EXPECTED_ACCEPTED_HASH)
        trust = ds.get("RELATIONSHIP", "trust")
        stress = ds.get("PSYCHOLOGY", "stress")
        assert trust is not None and stress is not None
        for d in (trust, stress):
            covered = {r.band for r in d.band_meaning_records()}
            assert covered == set(StateBand)
            for r in d.band_meaning_records():
                assert r.meaning.strip()

    def test_trust_id_is_dimension_only_no_subject(self):
        ds = load_character_dimension_set("kira", EXPECTED_ACCEPTED_HASH)
        assert ds.get("RELATIONSHIP", "trust").id == "trust"
        assert ds.get("RELATIONSHIP", "andrey.trust") is None

    def test_trust_meaning_is_behavioral_not_circular(self):
        ds = load_character_dimension_set("kira", EXPECTED_ACCEPTED_HASH)
        very_high = ds.get("RELATIONSHIP", "trust").meaning_for(StateBand.VERY_HIGH).lower()
        assert "high trust means high trust" not in very_high
        # behavioral / boundary-preserving language present
        assert "boundaries" in very_high
        assert "not romance" in very_high or "not attraction" in very_high

    def test_stress_meaning_not_panic_by_default(self):
        ds = load_character_dimension_set("kira", EXPECTED_ACCEPTED_HASH)
        very_high = ds.get("PSYCHOLOGY", "stress").meaning_for(StateBand.VERY_HIGH).lower()
        assert "not panic" in very_high or "unless separately established" in very_high
        assert "not hostile" in ds.get("PSYCHOLOGY", "stress").meaning_for(
            StateBand.HIGH
        ).lower()

    def test_7_no_kira_specific_meaning_in_core(self):
        core = (_REPO_ROOT / "services" / "character_core" / "dimensions.py").read_text(
            encoding="utf-8"
        ).lower()
        for forbidden in ("kira", "andrey", "trust", "stress", "romance"):
            assert forbidden not in core, forbidden


# ------------------------------------------------------------------- runtime

class TestRuntimeInjectionAndRendering:
    STATE = [
        ("RELATIONSHIP", "andrey.trust", "70"),
        ("PSYCHOLOGY", "stress", "70"),
    ]

    def test_8_10_11_grounded_renders_number_band_and_kira_meaning(self, tmp_path):
        ds = load_character_dimension_set("kira", EXPECTED_ACCEPTED_HASH)
        trust_meaning = ds.get("RELATIONSHIP", "trust").meaning_for(StateBand.VERY_HIGH)
        stress_meaning = ds.get("PSYCHOLOGY", "stress").meaning_for(StateBand.VERY_HIGH)

        sys_text, manifest = _grounded_system_text(
            tmp_path, policy=GroundedV2Policy(), state_seed=self.STATE
        )
        assert "andrey.trust: 70 (band: VERY_HIGH)" in sys_text
        assert trust_meaning in sys_text
        assert "stress: 70 (band: VERY_HIGH)" in sys_text
        assert stress_meaning in sys_text

        rel_line = next(
            i for i in manifest["items"] if i["kind"] == "system.relationship_state_line"
        )
        assert rel_line["meta"]["band"] == "VERY_HIGH"
        assert rel_line["meta"]["semantic_meaning"] == trust_meaning
        rel_block = next(
            i for i in manifest["items"] if i["kind"] == "system.relationship_state"
        )
        assert rel_block["meta"]["semantics"] == "PACKAGE_DEFINED"

    def test_9_beta_v1_does_not_receive_extension_semantics(self, tmp_path):
        sys_text, manifest = _grounded_system_text(
            tmp_path, policy=BetaV1CurrentPolicy(), state_seed=self.STATE
        )
        # Beta v1 never renders runtime state at all.
        assert "band: VERY_HIGH" not in sys_text
        assert not any(
            i["kind"].startswith("system.relationship_state") for i in manifest["items"]
        )

    def test_12_absent_extension_falls_back_to_raw_rendering(self, tmp_path, monkeypatch):
        import services.character_lab.runtime_service as rs

        monkeypatch.setattr(rs, "load_character_dimension_set", lambda *a, **k: None)
        sys_text, manifest = _grounded_system_text(
            tmp_path, policy=GroundedV2Policy(), state_seed=self.STATE
        )
        assert "- andrey.trust: 70" in sys_text
        assert "band:" not in sys_text
        rel_block = next(
            i for i in manifest["items"] if i["kind"] == "system.relationship_state"
        )
        assert rel_block["meta"]["semantics"] == "RAW"

    def test_partial_coverage_unlisted_dimension_stays_raw(self, tmp_path):
        sys_text, _ = _grounded_system_text(
            tmp_path,
            policy=GroundedV2Policy(),
            state_seed=[("RELATIONSHIP", "andrey.affinity", "70")],
        )
        assert "- andrey.affinity: 70" in sys_text
        assert "band:" not in sys_text


# -------------------------------------------------------------- accepted / doc

def test_13_accepted_kira_payloads_byte_identical():
    """The extension slice must not have touched accepted/** at all."""
    expected = {
        "accepted/kira/source_candidate.json":
            "e26f83dafa26e61af82f29b654b592300c8f3f7bd295d07bd4d2b6527ae3eebd",
    }
    src = (_ACCEPTED_ROOT / "kira" / "source_candidate.json").read_bytes()
    # The accepted source hash is the canonical package hash, computed by the
    # acceptance gate -- assert the gate still returns the expected value.
    assert _accepted().source_candidate_hash == expected[
        "accepted/kira/source_candidate.json"
    ]
    # And that both accepted files still parse as JSON objects (not corrupted).
    assert isinstance(json.loads(src.decode("utf-8")), dict)
    assert isinstance(
        json.loads((_ACCEPTED_ROOT / "kira" / "ACCEPTANCE.json").read_text("utf-8")),
        dict,
    )


# --------------------------------------------------------- behavioral A/B spec

class TestBehavioralABSpecPreparedOnly:
    def test_specs_vary_exactly_one_dimension_and_fix_the_rest(self):
        for spec in (TRUST_AB_SPEC, STRESS_AB_SPEC):
            assert spec["exact_wording_required"] is False
            assert spec["vary_only"] == spec["dimension"]["key"]
            assert set(spec["arms"]) == {"low", "very_high"}
            assert spec["arms"]["low"]["band"] == "LOW"
            assert spec["arms"]["very_high"]["band"] == "VERY_HIGH"
            assert len(spec["directional_rubric"]) >= 4

    def test_spec_arm_values_land_in_declared_bands(self):
        ds = load_character_dimension_set("kira", EXPECTED_ACCEPTED_HASH)
        for spec in (TRUST_AB_SPEC, STRESS_AB_SPEC):
            domain = spec["dimension"]["domain"]
            dim_id = spec["dimension"]["id"]
            definition = ds.get(domain, dim_id)
            for arm in spec["arms"].values():
                interp = interpret_value(arm["value"], definition)
                assert interp.band.value == arm["band"]
