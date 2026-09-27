"""Analysis contract parsing: fail-closed, strict, no fabrication surface."""

from __future__ import annotations

import json

import pytest

from services.character_draft import (
    AnalysisResult,
    CharacterDraftError,
    Readiness,
    parse_analysis_text,
)
from tests.character_draft._helpers import analysis_json


def test_parse_valid_needs_input():
    result = parse_analysis_text(analysis_json())
    assert isinstance(result, AnalysisResult)
    assert result.readiness is Readiness.NEEDS_INPUT
    assert result.known_facts == ("shy",)
    assert result.questions[0].target_area == "psychology"


def test_parse_valid_ready_for_draft_zero_questions():
    result = parse_analysis_text(
        analysis_json(readiness="READY_FOR_DRAFT", questions=[], missing_topics=[])
    )
    assert result.readiness is Readiness.READY_FOR_DRAFT
    assert result.questions == ()


def test_preserves_contradictions():
    result = parse_analysis_text(
        analysis_json(contradictions=[{"description": "age 24 vs age 28"}])
    )
    assert result.contradictions[0].description == "age 24 vs age 28"


def test_reject_missing_json():
    with pytest.raises(CharacterDraftError):
        parse_analysis_text("no JSON object here at all")


def test_reject_unknown_top_level_key():
    with pytest.raises(CharacterDraftError):
        parse_analysis_text(analysis_json(extra="not allowed"))


def test_reject_missing_required_key():
    data = json.loads(analysis_json())
    del data["known_facts"]
    with pytest.raises(CharacterDraftError):
        parse_analysis_text(json.dumps(data))


def test_reject_unknown_readiness():
    with pytest.raises(CharacterDraftError):
        parse_analysis_text(analysis_json(readiness="MAYBE"))


def test_reject_unknown_target_area():
    data = json.loads(analysis_json())
    data["questions"][0]["target_area"] = "voice"
    with pytest.raises(CharacterDraftError):
        parse_analysis_text(json.dumps(data))


def test_reject_non_string_list():
    with pytest.raises(CharacterDraftError):
        parse_analysis_text(analysis_json(known_facts=[1, 2, 3]))


def test_prose_wrapped_json_is_extracted():
    result = parse_analysis_text("```json\n" + analysis_json() + "\n```")
    assert result.readiness is Readiness.NEEDS_INPUT
