#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Character Core numeric-dimension semantics -- focused, offline, no provider.

Proves WHAT a numeric RELATIONSHIP / PSYCHOLOGY value means, given a
package-declared DimensionDefinition:

- the five generic bands and their exact thresholds;
- out-of-range values are rejected, never clamped;
- MISSING is permanently distinct from a real 0;
- definition validation is fail-closed;
- a RELATIONSHIP definition id is the dimension only (subject stays runtime);
- semantic meaning comes ONLY from the definition -- Core has no built-in
  dimension semantics and never infers meaning from the id;
- the same integer means different things under different definitions;
- the renderer emits value + band + meaning.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from services.character_core.dimensions import (
    BAND_THRESHOLDS,
    REQUIRED_BANDS,
    DimensionDefinition,
    DimensionDefinitionError,
    DimensionSet,
    DimensionValueStatus,
    StateBand,
    StateDomain,
    band_for_value,
    interpret_state_entry,
    interpret_value,
    key_to_dimension_id,
    render_semantic_state,
    semantic_state_line,
)

from tests.fixtures.character_core.synthetic_dimensions import (
    STRESS_DEFINITION_DICT,
    SYNTHETIC_DIMENSION_DICTS,
    TRUST_DEFINITION_DICT,
    synthetic_dimension_set,
)

_CORE_MODULE = Path(__file__).resolve().parents[2] / "services" / "character_core" / "dimensions.py"


def _trust() -> DimensionDefinition:
    return DimensionDefinition.from_dict(TRUST_DEFINITION_DICT)


def _stress() -> DimensionDefinition:
    return DimensionDefinition.from_dict(STRESS_DEFINITION_DICT)


# --------------------------------------------------------------------------
# 1 + 2. exact five bands and exact threshold boundaries
# --------------------------------------------------------------------------


class TestBands:
    def test_exactly_five_bands_named_by_magnitude_not_polarity(self):
        assert [b.value for b in StateBand] == [
            "VERY_LOW", "LOW", "MID", "HIGH", "VERY_HIGH"
        ]
        # Explicitly NOT "negative"/"positive".
        assert not any(
            tok in b.value.lower() for b in StateBand for tok in ("negativ", "positiv")
        )
        assert tuple(REQUIRED_BANDS) == tuple(StateBand)

    def test_thresholds_are_contiguous_and_cover_full_range(self):
        assert BAND_THRESHOLDS == (
            (StateBand.VERY_LOW, -100, -60),
            (StateBand.LOW, -59, -20),
            (StateBand.MID, -19, 19),
            (StateBand.HIGH, 20, 59),
            (StateBand.VERY_HIGH, 60, 100),
        )

    @pytest.mark.parametrize(
        "value, expected",
        [
            (-100, StateBand.VERY_LOW),
            (-60, StateBand.VERY_LOW),
            (-59, StateBand.LOW),
            (-20, StateBand.LOW),
            (-19, StateBand.MID),
            (0, StateBand.MID),
            (19, StateBand.MID),
            (20, StateBand.HIGH),
            (59, StateBand.HIGH),
            (60, StateBand.VERY_HIGH),
            (100, StateBand.VERY_HIGH),
        ],
    )
    def test_exact_boundary_values(self, value, expected):
        assert band_for_value(value) is expected

    # ---------------------------------------------------------------- 3.
    @pytest.mark.parametrize("value", [-101, 101, 1000, -1000])
    def test_out_of_range_rejected_never_clamped(self, value):
        with pytest.raises(DimensionDefinitionError):
            band_for_value(value)

    @pytest.mark.parametrize("value", [True, False, 1.5, "20", None])
    def test_non_integer_rejected(self, value):
        with pytest.raises(DimensionDefinitionError):
            band_for_value(value)


# --------------------------------------------------------------------------
# 4. MISSING != zero
# --------------------------------------------------------------------------


class TestMissingVsZero:
    def test_none_is_missing_status_not_a_band_not_zero(self):
        interp = interpret_value(None, _trust())
        assert interp.status is DimensionValueStatus.MISSING
        assert interp.value is None
        assert interp.band is None
        assert interp.meaning is None

    def test_zero_is_a_real_value_in_mid_band(self):
        interp = interpret_value(0, _trust())
        assert interp.status is DimensionValueStatus.KNOWN
        assert interp.value == 0
        assert interp.band is StateBand.MID
        assert interp.meaning == TRUST_DEFINITION_DICT["band_meanings"]["MID"]

    def test_missing_and_zero_are_distinguishable_results(self):
        assert interpret_value(None, _stress()) != interpret_value(0, _stress())

    def test_no_sixth_numeric_band_exists(self):
        assert len(StateBand) == 5


# --------------------------------------------------------------------------
# 5. definition validation (fail-closed)
# --------------------------------------------------------------------------


class TestDefinitionValidation:
    def test_valid_definition_round_trips(self):
        d = _trust()
        assert d.domain is StateDomain.RELATIONSHIP
        assert d.id == "trust"
        assert {r.band for r in d.band_meaning_records()} == set(StateBand)

    def test_empty_id_rejected(self):
        raw = dict(TRUST_DEFINITION_DICT, id="")
        with pytest.raises(DimensionDefinitionError):
            DimensionDefinition.from_dict(raw)

    def test_invalid_domain_rejected(self):
        raw = dict(TRUST_DEFINITION_DICT, domain="FACT")
        with pytest.raises(DimensionDefinitionError):
            DimensionDefinition.from_dict(raw)

    def test_missing_required_band_meaning_rejected(self):
        bm = dict(TRUST_DEFINITION_DICT["band_meanings"])
        bm.pop("MID")
        raw = dict(TRUST_DEFINITION_DICT, band_meanings=bm)
        with pytest.raises(DimensionDefinitionError):
            DimensionDefinition.from_dict(raw)

    def test_blank_band_meaning_rejected(self):
        bm = dict(TRUST_DEFINITION_DICT["band_meanings"], MID="   ")
        raw = dict(TRUST_DEFINITION_DICT, band_meanings=bm)
        with pytest.raises(DimensionDefinitionError):
            DimensionDefinition.from_dict(raw)

    def test_unknown_field_rejected(self):
        raw = dict(TRUST_DEFINITION_DICT, evolution_policy={"x": 1})
        with pytest.raises(DimensionDefinitionError):
            DimensionDefinition.from_dict(raw)

    def test_subject_prefixed_id_rejected(self):
        raw = dict(TRUST_DEFINITION_DICT, id="andrey.trust")
        with pytest.raises(DimensionDefinitionError):
            DimensionDefinition.from_dict(raw)

    def test_duplicate_definition_in_set_rejected(self):
        with pytest.raises(DimensionDefinitionError):
            DimensionSet.from_dicts([TRUST_DEFINITION_DICT, dict(TRUST_DEFINITION_DICT)])

    def test_dimension_set_lookup(self):
        ds = synthetic_dimension_set()
        assert ds.get(StateDomain.RELATIONSHIP, "trust").id == "trust"
        assert ds.get("PSYCHOLOGY", "stress").label == "Stress"
        assert ds.get(StateDomain.RELATIONSHIP, "stress") is None
        assert len(ds) == 2


# --------------------------------------------------------------------------
# 6 + 7. key -> dimension id rules
# --------------------------------------------------------------------------


class TestKeyGrammar:
    def test_relationship_id_is_dimension_only_subject_is_runtime(self):
        dimension_id, subject = key_to_dimension_id(StateDomain.RELATIONSHIP, "andrey.trust")
        assert dimension_id == "trust"
        assert subject == "andrey"
        # The DEFINITION id must never carry the subject.
        assert _trust().id == "trust"

    def test_psychology_id_is_the_whole_key(self):
        dimension_id, subject = key_to_dimension_id(StateDomain.PSYCHOLOGY, "stress")
        assert dimension_id == "stress"
        assert subject is None

    @pytest.mark.parametrize(
        "domain, key",
        [
            (StateDomain.RELATIONSHIP, "trust"),          # no subject
            (StateDomain.RELATIONSHIP, "a.b.c"),          # too many parts
            (StateDomain.RELATIONSHIP, "Andrey.trust"),   # uppercase
            (StateDomain.PSYCHOLOGY, "a.b"),              # subject not allowed
            (StateDomain.PSYCHOLOGY, "Stress"),           # uppercase
        ],
    )
    def test_key_grammar_not_loosened(self, domain, key):
        with pytest.raises(DimensionDefinitionError):
            key_to_dimension_id(domain, key)


# --------------------------------------------------------------------------
# 8 + 9. meaning comes from the definition; same number, different meaning
# --------------------------------------------------------------------------


class TestSemanticMeaningSource:
    def test_meaning_is_verbatim_from_definition(self):
        interp = interpret_value(72, _trust())
        assert interp.band is StateBand.VERY_HIGH
        assert interp.meaning == TRUST_DEFINITION_DICT["band_meanings"]["VERY_HIGH"]
        assert interp.meaning == "strong trust toward this subject"

    def test_same_value_different_definition_different_meaning_same_band(self):
        trust_interp = interpret_value(70, _trust())
        stress_interp = interpret_value(70, _stress())
        # Same generic band ...
        assert trust_interp.band is StateBand.VERY_HIGH
        assert stress_interp.band is StateBand.VERY_HIGH
        # ... but the character/package meaning differs and is not a value judgement.
        assert trust_interp.meaning == "strong trust toward this subject"
        assert stress_interp.meaning == "severe current stress"
        assert trust_interp.meaning != stress_interp.meaning

    def test_core_module_has_no_character_specific_dimension_semantics(self):
        """Guard: the Core semantics module must not name a specific character
        or hard-code a dimension's meaning. All meaning arrives via a
        DimensionDefinition supplied by the caller."""
        src = _CORE_MODULE.read_text(encoding="utf-8").lower()
        for forbidden in ("kira", "andrey", "sergey", "deepseek"):
            assert forbidden not in src, forbidden
        # The example dimension ids used by tests must not be baked into Core.
        assert "trust" not in src
        assert "stress" not in src
        # No id-driven branching.
        assert 'dimension_id ==' not in src and 'id == "' not in src


# --------------------------------------------------------------------------
# 10. renderer emits number + band + meaning
# --------------------------------------------------------------------------


class TestRenderer:
    def test_line_has_value_band_and_meaning(self):
        line = semantic_state_line(
            "RELATIONSHIP", "test_subject.trust", "72", synthetic_dimension_set()
        )
        assert "test_subject.trust" in line
        assert "72" in line
        assert "VERY_HIGH" in line
        assert "strong trust toward this subject" in line

    def test_psychology_line(self):
        line = semantic_state_line(
            "PSYCHOLOGY", "stress", 72, synthetic_dimension_set()
        )
        assert "stress" in line and "72" in line
        assert "VERY_HIGH" in line and "severe current stress" in line

    def test_line_without_definition_is_raw_and_invents_no_meaning(self):
        line = semantic_state_line(
            "RELATIONSHIP", "test_subject.affinity", "72", synthetic_dimension_set()
        )
        assert line == "- test_subject.affinity: 72"
        assert "band" not in line

    def test_render_block_groups_by_domain_and_skips_fact(self):
        entries = [
            {"domain": "FACT", "key": "living.city", "value": "Prague"},
            {"domain": "RELATIONSHIP", "key": "test_subject.trust", "value": "72"},
            {"domain": "PSYCHOLOGY", "key": "stress", "value": "-80"},
        ]
        block = render_semantic_state(entries, synthetic_dimension_set())
        assert "living.city" not in block
        assert "Prague" not in block
        assert "RELATIONSHIP" in block and "PSYCHOLOGY" in block
        assert "VERY_HIGH" in block  # trust 72
        assert "VERY_LOW" in block   # stress -80

    def test_interpret_state_entry_returns_none_for_uninterpretable(self):
        ds = synthetic_dimension_set()
        assert interpret_state_entry("FACT", "x", "1", ds) is None
        assert interpret_state_entry("RELATIONSHIP", "s.unknowndim", "1", ds) is None
        assert interpret_state_entry("PSYCHOLOGY", "stress", "not-int", ds) is None
        ok = interpret_state_entry("PSYCHOLOGY", "stress", "-70", ds)
        assert ok is not None and ok.band is StateBand.VERY_LOW


def test_fixture_dicts_are_synthetic_only():
    """Sanity: fixtures never claim to be KIRA canon."""
    joined = str(SYNTHETIC_DIMENSION_DICTS).lower()
    assert "kira" not in joined
