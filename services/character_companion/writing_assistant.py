#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Composer Writing Assistant -- an in-app text utility, NOT a character.

Flow:  composer draft  ->  WRITING_ASSISTANT provider/model  ->  suggested text.

It deliberately does **not** touch Character Runtime, the Grounded prompt,
Character Memory, Scene, Relationship, Psychology, Evolution or Epistemic
Context. It receives only the user's current draft -- never conversation
history, the Character Package or KIRA memory -- and returns rewritten message
text only. It resolves exactly the explicitly configured WRITING_ASSISTANT
provider/model through the existing secure credential vault; there is NO silent
fallback to DIALOGUE / DeepSeek / Local and (for V1) no automatic retry.
"""

from __future__ import annotations

from typing import Callable, Optional

from .provider_registry import ROLE_WRITING_ASSISTANT
from .provider_resolution import CompanionConfigError, _factory_for
from .settings import CompanionSettings

__all__ = ["WritingAssistantError", "WRITING_ASSISTANT_SYSTEM_PROMPT", "rewrite_draft"]

#: Utility instruction. Language-agnostic: the assistant rewrites in the draft's
#: own language and never answers, translates or role-plays.
WRITING_ASSISTANT_SYSTEM_PROMPT = (
    "You are a writing assistant embedded in a chat composer. The user gives you "
    "a rough draft of a message they are about to send. Rewrite it so it is "
    "correct and natural: fix spelling and grammar, improve readability, and "
    "keep the user's intended meaning and approximate tone. Rules: reply in the "
    "SAME language as the draft; do NOT translate; do NOT answer the message or "
    "continue the conversation; do NOT role-play or speak as any character; do "
    "NOT invent new personal facts, events or details; keep it roughly the same "
    "length. Return ONLY the rewritten message text, with no quotes, labels or "
    "commentary."
)

_MAX_DRAFT_CHARS = 4000


class WritingAssistantError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def rewrite_draft(
    draft: str,
    *,
    settings: CompanionSettings,
    vault,
    fake_factory,
    http_post_local: Optional[Callable] = None,
    http_post_cloud: Optional[Callable] = None,
    locale_hint: Optional[str] = None,
) -> dict:
    """Rewrite ``draft`` with the configured WRITING_ASSISTANT model.

    Returns ``{"suggestion", "provider", "model"}``. Raises
    :class:`WritingAssistantError` (bounded code) on bad input, an unconfigured
    role, or a provider failure -- never a fallback to a different provider.
    """
    if not isinstance(draft, str) or not draft.strip():
        raise WritingAssistantError("invalid_draft", "draft must be a non-empty string")
    if len(draft) > _MAX_DRAFT_CHARS:
        raise WritingAssistantError("invalid_draft", "draft is too long")

    assignment = settings.roles.get(ROLE_WRITING_ASSISTANT)
    if assignment is None:
        raise WritingAssistantError(
            "assistant_not_configured",
            "Настройте модель «Помощник написания» в настройках.",
        )

    try:
        factory = _factory_for(
            settings, vault, assignment.provider_id, assignment.model_id,
            role=ROLE_WRITING_ASSISTANT,
            fake_factory=fake_factory,
            http_post_local=http_post_local,
            http_post_cloud=http_post_cloud,
        )
    except CompanionConfigError as exc:
        # missing_credential / unsupported_role / unknown_provider ... -- surface
        # as a bounded assistant error; never try another provider.
        raise WritingAssistantError(exc.code, exc.message) from exc

    system = WRITING_ASSISTANT_SYSTEM_PROMPT
    if locale_hint:
        system += f" The draft language hint is '{locale_hint}'."
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": draft.strip()},
    ]

    try:
        text = factory(None)(messages)   # ONE call, no retry
    except Exception as exc:  # noqa: BLE001 -- bounded; never leak internals/secret
        raise WritingAssistantError("assistant_failed", "Не удалось получить подсказку.") from exc

    if not isinstance(text, str) or not text.strip():
        raise WritingAssistantError("assistant_failed", "Подсказка пуста.")

    return {
        "suggestion": text.strip(),
        "provider": assignment.provider_id,
        "model": assignment.model_id,
    }
