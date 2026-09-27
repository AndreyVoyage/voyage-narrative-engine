"""Strict structured contracts for the AI-first character draft flow.

The provider returns text embedding a single JSON object; this module extracts
and parses it fail-closed so model prose is never treated as trusted data.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

TARGET_AREAS = frozenset(
    {
        "identity",
        "biography",
        "psychology",
        "speech",
        "relationships",
        "sexology",
        "boundaries",
        "appearance",
    }
)


class CharacterDraftError(RuntimeError):
    """Application-level, user-readable character-draft error."""


class Readiness(str, Enum):
    READY_FOR_DRAFT = "READY_FOR_DRAFT"
    NEEDS_INPUT = "NEEDS_INPUT"


@dataclass(frozen=True)
class DraftContradiction:
    description: str


@dataclass(frozen=True)
class DraftQuestion:
    question_id: str
    text: str
    target_area: str


@dataclass(frozen=True)
class AnalysisResult:
    analysis_summary: str
    known_facts: tuple[str, ...]
    missing_topics: tuple[str, ...]
    contradictions: tuple[DraftContradiction, ...]
    questions: tuple[DraftQuestion, ...]
    readiness: Readiness

    def to_dict(self) -> dict[str, Any]:
        return {
            "analysis_summary": self.analysis_summary,
            "known_facts": list(self.known_facts),
            "missing_topics": list(self.missing_topics),
            "contradictions": [
                {"description": item.description} for item in self.contradictions
            ],
            "questions": [
                {
                    "question_id": q.question_id,
                    "text": q.text,
                    "target_area": q.target_area,
                }
                for q in self.questions
            ],
            "readiness": self.readiness.value,
        }


_ANALYSIS_FIELDS = frozenset(
    {
        "analysis_summary",
        "known_facts",
        "missing_topics",
        "contradictions",
        "questions",
        "readiness",
    }
)
_QUESTION_FIELDS = frozenset({"question_id", "text", "target_area"})
_CONTRADICTION_FIELDS = frozenset({"description"})


def _fail(detail: str) -> CharacterDraftError:
    return CharacterDraftError(f"malformed AI analysis: {detail}")


def _require_string(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise _fail(f"{field} must be a string")
    return value


def _require_string_list(value: object, field: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise _fail(f"{field} must be a list of strings")
    return value


def _exact_keys(value: Mapping[str, Any], expected: frozenset[str], field: str) -> None:
    if set(value) != expected:
        missing = sorted(expected - set(value))
        unknown = sorted(set(value) - expected)
        raise _fail(f"{field}: keys differ; missing={missing}, unknown={unknown}")


def extract_json_object(text: str) -> dict[str, Any]:
    """Extract the first balanced JSON object from a model response, or fail."""
    if not isinstance(text, str):
        raise _fail("provider response is not text")
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise _fail("no JSON object found in provider response")
    try:
        parsed = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise _fail(f"provider response is not valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise _fail("provider response JSON is not an object")
    return parsed


def parse_analysis_text(text: str) -> AnalysisResult:
    """Parse a provider analysis response into an :class:`AnalysisResult`."""
    data = extract_json_object(text)
    _exact_keys(data, _ANALYSIS_FIELDS, "analysis")

    contradictions = []
    for item in data["contradictions"]:
        if not isinstance(item, dict):
            raise _fail("each contradiction must be an object")
        _exact_keys(item, _CONTRADICTION_FIELDS, "contradiction")
        contradictions.append(
            DraftContradiction(description=_require_string(item["description"], "description"))
        )

    questions = []
    for item in data["questions"]:
        if not isinstance(item, dict):
            raise _fail("each question must be an object")
        _exact_keys(item, _QUESTION_FIELDS, "question")
        question = DraftQuestion(
            question_id=_require_string(item["question_id"], "question_id"),
            text=_require_string(item["text"], "text"),
            target_area=_require_string(item["target_area"], "target_area"),
        )
        if question.target_area not in TARGET_AREAS:
            raise _fail(
                f"question {question.question_id!r} has unknown target_area "
                f"{question.target_area!r}"
            )
        questions.append(question)

    readiness_raw = data["readiness"]
    if not isinstance(readiness_raw, str):
        raise _fail("readiness must be a string")
    try:
        readiness = Readiness(readiness_raw)
    except ValueError as exc:
        raise _fail(f"unknown readiness {readiness_raw!r}") from exc

    return AnalysisResult(
        analysis_summary=_require_string(data["analysis_summary"], "analysis_summary"),
        known_facts=tuple(_require_string_list(data["known_facts"], "known_facts")),
        missing_topics=tuple(_require_string_list(data["missing_topics"], "missing_topics")),
        contradictions=tuple(contradictions),
        questions=tuple(questions),
        readiness=readiness,
    )


__all__ = [
    "AnalysisResult",
    "CharacterDraftError",
    "DraftContradiction",
    "DraftQuestion",
    "Readiness",
    "TARGET_AREAS",
    "extract_json_object",
    "parse_analysis_text",
]
