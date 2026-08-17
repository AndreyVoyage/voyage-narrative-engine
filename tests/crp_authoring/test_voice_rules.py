#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CRP MVP S2B-part-1 -- R4 voice-pattern label-fidelity tests.

Hermetic, synthetic only. No Kira, no canon, no provider, no registry data.
"""

from __future__ import annotations

import pytest

from services.crp_authoring.contracts import (
    ClaimType,
    Confidence,
    RoleClaim,
    SourceType,
    VoicePatternLabel,
)
from services.crp_authoring.voice_rules import voice_label_violations

from tests.crp_authoring.conftest import make_claim, make_source


def _r4_voice_claim(**overrides) -> RoleClaim:
    """A minimal valid R4 voice claim with a faithful OBSERVED default."""
    kwargs = dict(
        claim_id="vc-001",
        claim_type=ClaimType.OBSERVATION,
        role_id="R4",
        source_type_summary=(SourceType.OBSERVATION,),
        confidence=Confidence.KNOWN,
        target_module_or_layer="voice.lexicon",
        voice_pattern_label=VoicePatternLabel.OBSERVED,
        rationale_summary="Direct speech example observed in corpus.",
    )
    kwargs.update(overrides)
    return make_claim(**kwargs)


class TestVoicePatternLabelVocabulary:
    def test_exact_authorized_values(self) -> None:
        assert {m.value for m in VoicePatternLabel} == {
            "OBSERVED",
            "INFERRED",
            "GENERATED_RULE",
            "NEGATIVE_EXAMPLE",
        }

    def test_unknown_value_rejected_at_construction(self) -> None:
        with pytest.raises(Exception):
            make_claim(voice_pattern_label="FABRICATED")  # type: ignore[arg-type]

    def test_none_is_default_and_valid(self) -> None:
        claim = make_claim()
        assert claim.voice_pattern_label is None


class TestBackwardCompatibility:
    def test_existing_roleclaim_without_label_still_works(self) -> None:
        # The exact S0/S1/S2A construction path (defaults only) remains valid.
        claim = make_claim(
            claim_id="claim-001",
            claim_type=ClaimType.FACT,
            role_id="R2",
            source_type_summary=(SourceType.OWNER_DIRECT,),
            confidence=Confidence.KNOWN,
            target_module_or_layer="psychology.P0",
        )
        assert claim.voice_pattern_label is None
        assert claim.claim_type is ClaimType.FACT
        assert claim.source_type_summary == (SourceType.OWNER_DIRECT,)
        assert claim.confidence is Confidence.KNOWN

    def test_r1_claim_unchanged(self) -> None:
        claim = make_claim(role_id="R1", claim_type=ClaimType.UNKNOWN)
        assert claim.voice_pattern_label is None


class TestAxesIndependence:
    def test_voice_label_does_not_mutate_confidence(self) -> None:
        claim = _r4_voice_claim(confidence=Confidence.POSSIBLE)
        assert claim.confidence is Confidence.POSSIBLE
        assert claim.voice_pattern_label is VoicePatternLabel.OBSERVED

    def test_voice_label_does_not_mutate_source_type(self) -> None:
        claim = _r4_voice_claim(source_type_summary=(SourceType.DIRECT_QUOTE,))
        assert claim.source_type_summary == (SourceType.DIRECT_QUOTE,)
        assert claim.voice_pattern_label is VoicePatternLabel.OBSERVED

    def test_voice_label_does_not_reinterpret_claim_type(self) -> None:
        # No enumerated ClaimType value equals GENERATED_RULE / NEGATIVE_EXAMPLE.
        assert "GENERATED_RULE" not in {m.value for m in ClaimType}
        assert "NEGATIVE_EXAMPLE" not in {m.value for m in ClaimType}


class TestObservedFidelity:
    def test_observed_requires_direct_evidence(self) -> None:
        ok = _r4_voice_claim(source_type_summary=(SourceType.DIRECT_QUOTE,))
        assert voice_label_violations((ok,)) == ()

    def test_observed_rejected_when_inference_only(self) -> None:
        bad = _r4_voice_claim(source_type_summary=(SourceType.MODEL_INFERENCE,))
        assert voice_label_violations((bad,))


class TestInferredFidelity:
    def test_inferred_requires_possible_or_unknown(self) -> None:
        ok = _r4_voice_claim(
            voice_pattern_label=VoicePatternLabel.INFERRED,
            confidence=Confidence.POSSIBLE,
        )
        assert voice_label_violations((ok,)) == ()

    def test_inferred_rejected_when_known(self) -> None:
        bad = _r4_voice_claim(
            voice_pattern_label=VoicePatternLabel.INFERRED,
            confidence=Confidence.KNOWN,
        )
        assert voice_label_violations((bad,))


class TestGeneratedRuleFidelity:
    def test_generated_rule_requires_model_example_and_lower_confidence(self) -> None:
        ok = _r4_voice_claim(
            claim_type=ClaimType.INFERENCE,
            source_type_summary=(SourceType.MODEL_EXAMPLE,),
            confidence=Confidence.POSSIBLE,
            voice_pattern_label=VoicePatternLabel.GENERATED_RULE,
        )
        assert voice_label_violations((ok,)) == ()

    def test_generated_rule_rejected_without_model_example(self) -> None:
        bad = _r4_voice_claim(
            source_type_summary=(SourceType.OWNER_DIRECT,),
            confidence=Confidence.POSSIBLE,
            voice_pattern_label=VoicePatternLabel.GENERATED_RULE,
        )
        assert voice_label_violations((bad,))

    def test_generated_rule_is_not_model_inference(self) -> None:
        # GENERATED_RULE must not be collapsed into MODEL_INFERENCE; a
        # MODEL_INFERENCE source alone does not satisfy GENERATED_RULE.
        bad = _r4_voice_claim(
            source_type_summary=(SourceType.MODEL_INFERENCE,),
            confidence=Confidence.POSSIBLE,
            voice_pattern_label=VoicePatternLabel.GENERATED_RULE,
        )
        assert voice_label_violations((bad,))

    def test_generated_rule_rejected_when_known(self) -> None:
        bad = _r4_voice_claim(
            source_type_summary=(SourceType.MODEL_EXAMPLE,),
            confidence=Confidence.KNOWN,
            voice_pattern_label=VoicePatternLabel.GENERATED_RULE,
        )
        assert voice_label_violations((bad,))


class TestNegativeExampleFidelity:
    def test_negative_example_requires_non_fact(self) -> None:
        ok = _r4_voice_claim(
            claim_type=ClaimType.INFERENCE,
            source_type_summary=(SourceType.OBSERVATION,),
            confidence=Confidence.POSSIBLE,
            voice_pattern_label=VoicePatternLabel.NEGATIVE_EXAMPLE,
        )
        assert voice_label_violations((ok,)) == ()

    def test_negative_example_rejected_when_fact(self) -> None:
        bad = _r4_voice_claim(
            claim_type=ClaimType.FACT,
            source_type_summary=(SourceType.OWNER_DIRECT,),
            confidence=Confidence.KNOWN,
            voice_pattern_label=VoicePatternLabel.NEGATIVE_EXAMPLE,
        )
        assert voice_label_violations((bad,))

    def test_negative_example_not_conflated_with_contradictory(self) -> None:
        # NEGATIVE_EXAMPLE stays an independent label; it is not re-mapped to
        # the confidence value CONTRADICTORY.
        claim = _r4_voice_claim(
            claim_type=ClaimType.INFERENCE,
            confidence=Confidence.CONTRADICTORY,
            voice_pattern_label=VoicePatternLabel.NEGATIVE_EXAMPLE,
        )
        assert claim.voice_pattern_label is VoicePatternLabel.NEGATIVE_EXAMPLE
        assert claim.confidence is Confidence.CONTRADICTORY


class TestR4Scoping:
    def test_non_r4_claim_with_label_rejected(self) -> None:
        bad = make_claim(
            role_id="R2",
            claim_type=ClaimType.OBSERVATION,
            source_type_summary=(SourceType.OBSERVATION,),
            target_module_or_layer="voice.lexicon",
            voice_pattern_label=VoicePatternLabel.OBSERVED,
        )
        assert voice_label_violations((bad,))

    def test_r4_claim_not_voice_target_rejected(self) -> None:
        bad = _r4_voice_claim(target_module_or_layer="psychology.P1")
        assert voice_label_violations((bad,))


class TestNoLabelNoViolation:
    def test_r4_voice_claim_without_label_no_violation(self) -> None:
        claim = make_claim(
            role_id="R4",
            claim_type=ClaimType.OBSERVATION,
            source_type_summary=(SourceType.OBSERVATION,),
            confidence=Confidence.KNOWN,
            target_module_or_layer="voice.lexicon",
        )
        assert voice_label_violations((claim,)) == ()

    def test_input_must_be_tuple_of_roleclaim(self) -> None:
        with pytest.raises(TypeError):
            voice_label_violations((make_source(),))  # type: ignore[arg-type]
