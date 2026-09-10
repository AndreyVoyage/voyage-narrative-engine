#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Composer Co-Author -- contextual writing help for the USER's own next line.

Two semantic modes, derived from the draft itself:

  COMPOSE  (trimmed draft empty)     -> propose ONE plausible next USER message
  EXPAND   (trimmed draft non-empty) -> deepen / enrich the user's draft while
                                        keeping the same intent and voice

It is NOT a proofreader. It never speaks as the character, never answers the
draft, never routes through ``RuntimeService.turn`` / ``policy.persist`` and
never writes memory or state. It runs on the SAME provider/model as DIALOGUE --
the caller resolves and supplies that factory (there is no separate
WRITING_ASSISTANT execution assignment any more). One provider call, no retry,
no fallback.

Only USER-safe context is ever assembled: the visible dialogue history, the
shared Scene, and the user's own prior statements. The KIRA core instruction,
RELATIONSHIP / PSYCHOLOGY state, epistemic context, FACT runtime-state blocks
and the Accepted Character package are deliberately excluded -- the co-author
writes the USER's line and must not gain narrator-level or character-private
knowledge. Context is bounded by the SAME estimated-token dialogue context
budget (there is no second budget), reusing the committed estimator by import.
"""

from __future__ import annotations

from typing import Callable, Optional, Sequence

# Committed estimator semantics -- import only; runtime_policy.py is never
# modified. These are estimated-token heuristics, NOT an exact tokenizer.
from services.character_lab.runtime_policy import (
    CONTEXT_BUDGET_ESTIMATOR_ID,
    OUTPUT_RESERVE_EST_TOKENS,
    content_est_tokens,
    message_est_tokens,
)

__all__ = [
    "WritingAssistantError",
    "MODE_COMPOSE",
    "MODE_EXPAND",
    "COAUTHOR_COMPOSE_SYSTEM_PROMPT",
    "COAUTHOR_EXPAND_SYSTEM_PROMPT",
    "WRITING_ASSISTANT_SYSTEM_PROMPT",
    "CONTEXT_BUDGET_ESTIMATOR_ID",
    "derive_mode",
    "coauthor_suggest",
    "rewrite_draft",
]

MODE_COMPOSE = "COMPOSE"
MODE_EXPAND = "EXPAND"

_MAX_DRAFT_CHARS = 4000
#: Generous upper bound on the returned suggestion. Multi-paragraph output is
#: legitimate and is NOT truncated to a first paragraph; this only guards
#: against a runaway response.
_MAX_SUGGESTION_CHARS = 8000

# --- co-author system instructions -----------------------------------------

COAUTHOR_COMPOSE_SYSTEM_PROMPT = (
    "Ты помогаешь ПОЛЬЗОВАТЕЛЮ написать его следующее сообщение в этом диалоге. "
    "Ты не персонаж и не отвечаешь за персонажа. Опираясь только на приведённый "
    "видимый пользователю контекст, напиши ОДНО правдоподобное сообщение, "
    "которое пользователь мог бы отправить сейчас. Пиши от первого лица от "
    "имени пользователя, на языке диалога. Верни только текст сообщения — без "
    "пояснений, подписей, кавычек, вариантов и разбора."
)

COAUTHOR_EXPAND_SYSTEM_PROMPT = (
    "У ПОЛЬЗОВАТЕЛЯ есть черновик его следующего сообщения (последняя реплика "
    "ниже — это черновик пользователя, а не сообщение, на которое нужно "
    "отвечать). Сохрани замысел и голос пользователя, но сделай сообщение "
    "глубже и живее: добавь уместную конкретику, эмоциональный нюанс, подтекст "
    "и естественные формулировки, заверши недосказанную мысль, где это уместно. "
    "Не отвечай на черновик. Не пиши за персонажа. Не превращай это в разбор. "
    "Не своди задачу к исправлению орфографии и грамматики. Верни только "
    "улучшенный текст сообщения ПОЛЬЗОВАТЕЛЯ."
)

#: Back-compat alias for importers of the previous name (e.g. the package
#: ``__init__``). The co-author's EXPAND instruction is the closest analogue of
#: the old single "rewrite" prompt.
WRITING_ASSISTANT_SYSTEM_PROMPT = COAUTHOR_EXPAND_SYSTEM_PROMPT

_SCENE_HEADER = "СЦЕНА (общая для собеседников)"
_USER_MEMORY_HEADER = (
    "ПАМЯТЬ СО СЛОВ ПОЛЬЗОВАТЕЛЯ (сказано в прошлых разговорах этого профиля — "
    "не проверенные факты)"
)
_HISTORY_FRAME = (
    "Ниже — видимая пользователю переписка. Твоя задача — следующее сообщение "
    "ПОЛЬЗОВАТЕЛЯ, а не персонажа."
)


class WritingAssistantError(RuntimeError):
    """Bounded co-author error. Never leaks internals or secrets."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def derive_mode(draft) -> str:
    """COMPOSE when the trimmed draft is empty, otherwise EXPAND."""
    return MODE_EXPAND if isinstance(draft, str) and draft.strip() else MODE_COMPOSE


def _newest_contiguous_turn_units(history: Sequence[dict]) -> list:
    """Group a flat [{'role','content'}] history into complete turn units,
    NEWEST unit first, each a list of original indices in chronological order.

    * ``assistant`` preceded by ``user`` -> a [user, assistant] unit.
    * a lone trailing ``user`` -> a 1-index unit.
    * a leading orphan ``assistant`` -> dropped (never emitted first).

    A caller walks these newest->oldest and STOPS at the first unit that does
    not fit -- it never skips a newer non-fitting unit to reach an older one.
    """
    units: list = []
    i = len(history) - 1
    while i >= 0:
        role = history[i].get("role")
        if role == "assistant" and i - 1 >= 0 and history[i - 1].get("role") == "user":
            units.append([i - 1, i])
            i -= 2
        elif role == "user":
            units.append([i])
            i -= 1
        else:  # orphan assistant / unknown role at this edge
            i -= 1
    return units


def coauthor_suggest(
    draft,
    *,
    mode: Optional[str] = None,
    provider_factory: Callable,
    provider_id: str,
    model_id: str,
    budget_est_tokens: int,
    visible_history: Sequence[dict] = (),
    scene_text: Optional[str] = None,
    user_memory_block: Optional[str] = None,
    locale_hint: Optional[str] = None,
) -> dict:
    """Run one co-author generation.

    ``provider_factory`` / ``provider_id`` / ``model_id`` are the EFFECTIVE
    DIALOGUE assignment (resolved by the caller). ``visible_history`` is a flat
    ``[{'role': 'user'|'assistant', 'content': str}]`` list the user was
    actually shown (hidden messages already removed). ``scene_text`` and
    ``user_memory_block`` are pre-rendered whole blocks or ``None``.

    Returns ``{"suggestion", "provider", "model", "mode"}``. Raises
    :class:`WritingAssistantError` (bounded code) on bad input, a mandatory
    overflow of the estimated-token budget (before any provider call), or a
    provider failure -- never a fallback to another provider/model.
    """
    if not isinstance(draft, str):
        raise WritingAssistantError("invalid_draft", "draft must be a string")
    if len(draft) > _MAX_DRAFT_CHARS:
        raise WritingAssistantError("invalid_draft", "draft is too long")

    resolved_mode = mode or derive_mode(draft)
    if resolved_mode not in (MODE_COMPOSE, MODE_EXPAND):
        raise WritingAssistantError("invalid_request", f"unknown co-author mode {resolved_mode!r}")

    instruction = (
        COAUTHOR_EXPAND_SYSTEM_PROMPT
        if resolved_mode == MODE_EXPAND
        else COAUTHOR_COMPOSE_SYSTEM_PROMPT
    )
    if locale_hint:
        instruction += f" Язык подсказки: '{locale_hint}'."

    try:
        budget = int(budget_est_tokens)
    except (TypeError, ValueError):
        raise WritingAssistantError("invalid_request", "context budget must be an integer") from None
    effective = budget - OUTPUT_RESERVE_EST_TOKENS

    # ---- MUST KEEP: co-author instruction (+ EXPAND draft) -------------------
    system_msg = {"role": "system", "content": instruction}
    used = message_est_tokens(instruction)
    draft_msg = None
    if resolved_mode == MODE_EXPAND:
        draft_msg = {"role": "user", "content": draft.strip()}
        used += message_est_tokens(draft.strip())
    if used > effective:
        raise WritingAssistantError(
            "context_budget_exceeded",
            "the mandatory co-author context exceeds the configured dialogue "
            "context budget",
        )

    extra_system: list = []  # whole blocks, emission order: scene, user-memory

    # HIGH: shared Scene (whole block or omit -- never clipped).
    if scene_text and scene_text.strip():
        block = f"{_SCENE_HEADER}\n\n{scene_text.strip()}"
        cost = message_est_tokens(block)
        if used + cost <= effective:
            extra_system.append(block)
            used += cost

    # HIGH: newest-contiguous visible history.
    hist = [
        {"role": m.get("role"), "content": m.get("content")}
        for m in visible_history
        if m.get("role") in ("user", "assistant") and isinstance(m.get("content"), str)
    ]
    selected_idx: set = set()
    if hist:
        frame_cost = message_est_tokens(_HISTORY_FRAME)
        running = used + frame_cost
        took_any = False
        for unit in _newest_contiguous_turn_units(hist):
            unit_cost = sum(message_est_tokens(hist[i]["content"]) for i in unit)
            if running + unit_cost <= effective:
                running += unit_cost
                selected_idx.update(unit)
                took_any = True
            else:
                break  # strict newest-contiguous cutoff: no skip-ahead
        if took_any:
            used = running

    # LOWER: the user's own prior statements (whole block or omit).
    mem_block = None
    if user_memory_block and user_memory_block.strip():
        block = f"{_USER_MEMORY_HEADER}\n\n{user_memory_block.strip()}"
        cost = message_est_tokens(block)
        if used + cost <= effective:
            mem_block = block
            used += cost

    # ---- assemble messages (fixed order) -----------------------------------
    messages: list = [system_msg]
    for block in extra_system:
        messages.append({"role": "system", "content": block})
    if mem_block is not None:
        messages.append({"role": "system", "content": mem_block})
    if selected_idx:
        messages.append({"role": "system", "content": _HISTORY_FRAME})
        for i, m in enumerate(hist):
            if i in selected_idx:
                messages.append({"role": m["role"], "content": m["content"]})
    if draft_msg is not None:
        messages.append(draft_msg)

    # ---- ONE provider call. No retry. No fallback. ------------------------
    try:
        text = provider_factory(None)(messages)
    except Exception as exc:  # noqa: BLE001 -- bounded; never leak internals/secret
        raise WritingAssistantError("assistant_failed", "Не удалось получить подсказку.") from exc

    if not isinstance(text, str) or not text.strip():
        raise WritingAssistantError("assistant_failed", "Подсказка пуста.")
    suggestion = text.strip()
    if len(suggestion) > _MAX_SUGGESTION_CHARS:
        suggestion = suggestion[:_MAX_SUGGESTION_CHARS].rstrip()

    return {
        "suggestion": suggestion,
        "provider": provider_id,
        "model": model_id,
        "mode": resolved_mode,
    }


def rewrite_draft(
    draft: str,
    *,
    settings,
    vault,
    fake_factory,
    http_post_local: Optional[Callable] = None,
    http_post_cloud: Optional[Callable] = None,
    locale_hint: Optional[str] = None,
) -> dict:
    """Back-compat helper: EXPAND a non-empty ``draft`` with NO conversation
    context, resolving the EFFECTIVE DIALOGUE provider/model (never a separate
    WRITING_ASSISTANT assignment). Converges on :func:`coauthor_suggest`.

    ``CompanionService`` no longer uses this -- it builds safe context and calls
    the core directly -- but the symbol stays for existing importers/tests.
    """
    if not isinstance(draft, str) or not draft.strip():
        raise WritingAssistantError("invalid_draft", "draft must be a non-empty string")

    from .provider_registry import ROLE_DIALOGUE
    from .provider_resolution import CompanionConfigError, _factory_for

    assignment = settings.dialogue()
    try:
        factory = _factory_for(
            settings, vault, assignment.provider_id, assignment.model_id,
            role=ROLE_DIALOGUE,
            fake_factory=fake_factory,
            http_post_local=http_post_local,
            http_post_cloud=http_post_cloud,
        )
    except CompanionConfigError as exc:
        raise WritingAssistantError(exc.code, exc.message) from exc

    return coauthor_suggest(
        draft,
        mode=MODE_EXPAND,
        provider_factory=factory,
        provider_id=assignment.provider_id,
        model_id=assignment.model_id,
        budget_est_tokens=settings.dialogue_context_budget_est_tokens,
        locale_hint=locale_hint,
    )
