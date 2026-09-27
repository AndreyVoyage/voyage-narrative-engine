"""Shared offline builders for AI-first draft tests (no network)."""

from __future__ import annotations

import json


def analysis_json(
    readiness: str = "NEEDS_INPUT",
    *,
    questions=None,
    contradictions=None,
    **overrides,
) -> str:
    data = {
        "analysis_summary": "A shy young woman.",
        "known_facts": ["shy"],
        "missing_topics": ["psychology"] if readiness == "NEEDS_INPUT" else [],
        "contradictions": contradictions if contradictions is not None else [],
        "questions": questions
        if questions is not None
        else (
            [{"question_id": "q1", "text": "What drives her?", "target_area": "psychology"}]
            if readiness == "NEEDS_INPUT"
            else []
        ),
        "readiness": readiness,
    }
    data.update(overrides)
    return json.dumps(data)


def draft_semantic(**overrides) -> dict:
    semantic = {
        "identity": {
            "display_name": "x",
            "short_description": "Shy",
            "detailed_description": "A shy character",
        },
        "biography": "A shy young woman.",
        "psychology": {
            "personality": ["shy"],
            "behavioral_traits": [],
            "emotional_tendencies": [],
            "goals_motivations": [],
        },
        "speech": {"speech_style": "soft", "register": None},
        "character_relations": {"relational_tendencies": [], "attachment_traits": []},
        "appearance": {"descriptors": []},
        "boundaries": {"principles": []},
        "visual_identity": {},
    }
    semantic.update(overrides)
    return semantic


def draft_json(**overrides) -> str:
    return json.dumps({"semantic": draft_semantic(**overrides)})
