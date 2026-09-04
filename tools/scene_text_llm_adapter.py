#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Real DeepSeek semantic proposer for the Scene Text Interpreter v0.

Provider-specific wiring ONLY. The domain package
(``services/scene_text_interpreter``) stays provider-neutral: this adapter
lives in ``tools/`` and is injected through the existing
``SceneTextProposer`` protocol.

Contract:

- builds a strict JSON-only instruction from the provider-neutral
  ``InterpreterInput`` (allowed ids/aliases, allowed locations/aliases,
  controlled scene tags, the exact proposal schema, grounding rules);
- performs EXACTLY ONE call through the shared
  ``tools/llm_provider.py`` ``cloud`` transport, DeepSeek endpoint, with the
  bearer secret sourced from ``DEEPSEEK_API_KEY`` via ``api_key_env``
  (the adapter never reads the key itself and never sees its value);
- parses the response ONCE through the existing strict
  ``ProposedInterpretation.from_dict`` parser.

No retry. No fallback. No second model. No markdown-fence stripping. No JSON
"repair" call. The deterministic validator downstream remains authoritative
over the untrusted proposal.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from services.scene_text_interpreter import (
    InterpreterInput,
    ProposalSchemaError,
    ProposedInterpretation,
)
from tools import llm_provider

# Exact project DeepSeek convention (novel/game/aside.rpy).
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-v4-flash"
DEEPSEEK_API_KEY_ENV = "DEEPSEEK_API_KEY"

_DEFAULT_TIMEOUT_S = 120.0

_SYSTEM_INSTRUCTION = (
    "You convert a short prose scene into ONE structured JSON object for an "
    "authoring pipeline. Output requirements:\n"
    "- Respond with a SINGLE JSON object and nothing else. No prose, no "
    "markdown, no code fences.\n"
    "- Use ONLY character_id values from the allowed roster and ONLY "
    "location_id values from the allowed locations.\n"
    "- Use ONLY scene tags from the allowed list. Do NOT emit the location id "
    "as a scene tag.\n"
    "- There must be EXACTLY two characters, both named in the source text.\n"
    "- Every source_spans / location_span / text_span / action_phrase / "
    "gaze_phrase / positioning_phrase value MUST be copied VERBATIM as an exact "
    "substring of the source text (same characters, same case).\n"
    "- Do NOT invent physical contact, characters, dialogue, locations, or "
    "actions that are not in the source text. Do NOT infer ages.\n"
    "- location_id must be derivable from a phrase actually present in the "
    "source text.\n"
    "- If something required is genuinely ambiguous, list it in "
    "unresolved_items instead of guessing, and set confidence to \"low\".\n"
    "- Do not include any explanation or chain-of-thought. Only the structured "
    "answer with verbatim source evidence."
)


def _allowed_context(request: InterpreterInput) -> dict[str, Any]:
    return {
        "allowed_characters": [
            {
                "character_id": c.character_id,
                "provider_alias": c.provider_alias,
                "surface_aliases": list(c.surface_aliases),
            }
            for c in request.allowed_characters
        ],
        "allowed_locations": [
            {"location_id": l.location_id, "surface_aliases": list(l.surface_aliases)}
            for l in request.allowed_locations
        ],
        "allowed_scene_tags": list(request.allowed_scene_tags),
        "required_characters_in_frame": request.min_characters_in_frame,
        "max_still_candidates": request.still_candidate_count,
    }


_SCHEMA_HINT = {
    "source_language": "ru|en|...",
    "confidence": "high|low",
    "unresolved_items": ["string"],
    "characters": [
        {"character_id": "<allowed id>", "source_spans": ["<verbatim substring>"]}
    ],
    "location_id": "<allowed id or null>",
    "location_span": "<verbatim substring or null>",
    "scene_tags": ["<allowed tag>"],
    "beats": [
        {
            "index": 0,
            "text_span": "<verbatim substring>",
            "actor_character_ids": ["<allowed id>"],
            "action_phrase": "<verbatim substring>",
            "gaze_phrase": "<verbatim substring or null>",
            "positioning_phrase": "<verbatim substring or null>",
            "contact_flag": False,
        }
    ],
    "still_candidates": [
        {
            "beat_index": 0,
            "rationale_tags": ["both_characters_present", "static_pose"],
            "visual_goal_text": "<one composed sentence describing the still>",
        }
    ],
}


def _build_user_message(request: InterpreterInput) -> str:
    return (
        "SOURCE_TEXT (interpret only this; add no facts):\n"
        f"{request.raw_scene_text}\n\n"
        "ALLOWED_CONTEXT (closed allowlists):\n"
        f"{json.dumps(_allowed_context(request), ensure_ascii=False, indent=2)}\n\n"
        "OUTPUT_SCHEMA (shape only; fill with grounded values):\n"
        f"{json.dumps(_SCHEMA_HINT, ensure_ascii=False, indent=2)}\n\n"
        "Guidance: you MAY include one beat whose text_span covers two adjacent "
        "sentences if that single span depicts one coherent still-frame moment "
        "involving both characters. Propose up to "
        f"{request.still_candidate_count} still candidates, best first. "
        "Return ONLY the JSON object."
    )


class DeepSeekSceneTextProposer:
    """Live ``SceneTextProposer`` backed by the DeepSeek cloud transport."""

    def __init__(self, *, timeout_s: float = _DEFAULT_TIMEOUT_S) -> None:
        self.provider = "deepseek"
        self.model = DEEPSEEK_MODEL
        self.mock = False
        self._timeout_s = float(timeout_s)
        self.raw_response_sha256: str | None = None

    def propose(self, request: InterpreterInput) -> ProposedInterpretation:
        raw = llm_provider.complete(
            [{"role": "user", "content": _build_user_message(request)}],
            provider="cloud",
            model=DEEPSEEK_MODEL,
            system=_SYSTEM_INSTRUCTION,
            params={
                "base_url": DEEPSEEK_BASE_URL,
                "api_key_env": DEEPSEEK_API_KEY_ENV,
                "timeout_s": self._timeout_s,
                "thinking": {"type": "disabled"},
                "response_format": {"type": "json_object"},
                "temperature": 0,
            },
        )
        # The raw response describes a public fictional scene; hashing it is
        # safe and useful for audit. It never contains the API key.
        self.raw_response_sha256 = hashlib.sha256(raw.encode("utf-8")).hexdigest()

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ProposalSchemaError(
                f"DeepSeek response is not a single valid JSON object: {exc}"
            ) from None
        # Parsed exactly once through the existing strict parser. No repair.
        return ProposedInterpretation.from_dict(payload)
