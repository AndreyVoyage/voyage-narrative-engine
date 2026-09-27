"""Provider boundary and prompt construction for the AI-first draft flow.

The service depends only on :data:`ProviderCallable` (a plain function that
takes a message list plus an optional system prompt and returns text).  The
default implementation reuses the existing ``tools.llm_provider`` cloud path
(OpenAI-compatible), which already accepts ``DEEPSEEK_API_KEY``; no new
credential store or hard-coded model identifier is introduced here.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .contracts import CharacterDraftError

ProviderCallable = Callable[[list[dict[str, str]], str | None], str]


@dataclass(frozen=True)
class DraftProviderConfig:
    provider: str = "cloud"
    model: str | None = None
    base_url: str | None = None
    api_key_env: str = "DEEPSEEK_API_KEY"
    timeout_s: float | None = None

    @classmethod
    def from_env(cls) -> "DraftProviderConfig":
        return cls(
            model=os.environ.get("DEEPSEEK_MODEL"),
            base_url=os.environ.get("DEEPSEEK_BASE_URL"),
            api_key_env=(
                "DEEPSEEK_API_KEY"
                if os.environ.get("DEEPSEEK_API_KEY")
                else "OPENAI_API_KEY"
            ),
        )


def make_llm_provider(config: DraftProviderConfig) -> ProviderCallable:
    """Return a provider callable backed by ``tools.llm_provider.complete``."""
    from tools import llm_provider as _llm

    def _call(messages: list[dict[str, str]], system: str | None) -> str:
        params: dict[str, Any] = {"api_key_env": config.api_key_env}
        if config.base_url:
            params["base_url"] = config.base_url
        if config.timeout_s is not None:
            params["timeout_s"] = config.timeout_s
        try:
            return _llm.complete(
                messages,
                provider=config.provider,
                model=config.model,
                system=system,
                params=params,
            )
        except _llm.LLMProviderError as exc:
            message = str(exc)
            if "is required for cloud provider" in message:
                raise CharacterDraftError(
                    f"API key is not configured. Set {config.api_key_env} and retry."
                ) from exc
            raise CharacterDraftError(f"provider error: {message}") from exc

    return _call


def scripted_provider(responses: list[str]) -> ProviderCallable:
    """Test double: returns responses in order, then repeats the last one."""
    if not responses:
        raise ValueError("scripted_provider needs at least one response")

    def _call(messages: list[dict[str, str]], system: str | None) -> str:
        if len(responses) > 1:
            return responses.pop(0)
        return responses[0]

    return _call


ANALYSIS_SYSTEM_PROMPT = (
    "You are the character-construction analysis assistant for NARRATIVE "
    "Character Lab. Given a free-form character description, return ONLY one "
    "JSON object with this exact shape:\n"
    '{"analysis_summary": "<summary>", "known_facts": ["<fact>"], '
    '"missing_topics": ["<area>"], '
    '"contradictions": [{"description": "<conflict>"}], '
    '"questions": [{"question_id": "q1", "text": "<question>", '
    '"target_area": "<area>"}], "readiness": "READY_FOR_DRAFT" | "NEEDS_INPUT"}\n\n'
    "target_area must be one of: identity, biography, psychology, speech, "
    "relationships, sexology, boundaries, appearance.\n"
    "Rules: DO NOT fabricate missing facts; leave unknown information unknown. "
    "Express inference as a question, never as fact. If enough is known to "
    "author a draft, return READY_FOR_DRAFT (questions may be empty); otherwise "
    "return NEEDS_INPUT with a few genuinely useful questions. Do NOT infer "
    "intimate/sexual preferences from appearance, age, personality or gender "
    "stereotypes. Preserve contradictions; never silently pick one side. "
    "Reply with JSON only, no prose, no markdown fences."
)

DRAFT_SYSTEM_PROMPT = (
    "You are the character-draft builder for NARRATIVE Character Lab. Using ONLY "
    "facts the user provided in this conversation, return ONE JSON object with "
    "exactly this shape:\n"
    '{"semantic": {"identity": {"display_name": "", "short_description": "", '
    '"detailed_description": ""}, "biography": "", '
    '"psychology": {"personality": [], "behavioral_traits": [], '
    '"emotional_tendencies": [], "goals_motivations": []}, '
    '"speech": {"speech_style": "", "register": null}, '
    '"character_relations": {"relational_tendencies": [], "attachment_traits": []}, '
    '"appearance": {"descriptors": []}, "boundaries": {"principles": []}, '
    '"visual_identity": {}}}\n\n'
    'Include "sexology" ONLY if the user gave real sexology information; '
    "otherwise omit it. When present, sexology must contain exactly these six "
    "keys (each a list of strings, possibly empty): intimacy_attitudes, "
    "preferences, emotional_dynamics, communication, vulnerabilities, "
    "intimacy_boundaries.\n"
    "Rules: DO NOT fabricate; every filled field must come from the user's "
    "words. Empty lists and empty strings are fine. biography is separate from "
    "detailed_description; do not merge them. visual_identity must be {}. "
    "Reply with JSON only, no prose, no markdown fences."
)

__all__ = [
    "ANALYSIS_SYSTEM_PROMPT",
    "DRAFT_SYSTEM_PROMPT",
    "DraftProviderConfig",
    "ProviderCallable",
    "make_llm_provider",
    "scripted_provider",
]
