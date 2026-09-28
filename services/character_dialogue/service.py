"""In-memory Test Dialogue service: exact revision pin + role-play provider.

Owns active test sessions. Depends only on Character Authoring (semantic
validation + snapshot re-verification) and the shared provider transport. It
never writes to authoring, approval, publication, canonical-current, memory or
evolution. Sessions are in-memory only and may be discarded on app close.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any, Optional

from services.character_authoring import (
    CharacterAuthoringValidationError,
    CharacterSemantic,
    compute_snapshot_hash,
)
from services.character_draft import CharacterDraftError
from services.character_draft.provider import ProviderCallable

from .context import display_name, persona_context
from .contracts import (
    DialogueMessage,
    TestDialogueError,
    TestDialoguePin,
    TestDialogueProviderError,
    TestDialogueSession,
)
from .prompts import build_role_play_system_prompt

DEFAULT_TRANSCRIPT_TURN_LIMIT = 12

# Public transcript roles -> provider roles (system/assistant are provider-only).
_ROLE_TO_PROVIDER = {"user": "user", "character": "assistant"}

# Stable, locally-defined user-facing provider messages. The user-visible text
# ALWAYS originates from these trusted constants, never from a provider
# exception. Arbitrary provider exception text (HTTP bodies, Authorization
# headers, request/response bodies, URLs with credentials, tracebacks) is
# discarded at this boundary and never surfaced.
GENERIC_PROVIDER_FAILURE_MESSAGE = (
    "Не удалось получить ответ персонажа от AI-провайдера."
)
EMPTY_PROVIDER_RESPONSE_MESSAGE = "Провайдер вернул пустой ответ."
SAFE_MISSING_KEY_MESSAGE = "API key is not configured. Set DEEPSEEK_API_KEY and retry."

# The EXACT contract messages the shared provider layer emits for the
# missing-credential condition. Only an exact, full-string match (never a
# prefix/substring/regex) identifies this case; every other message -- including
# any prefix-spoofed variant -- collapses to the generic failure message.
_KNOWN_MISSING_KEY_MESSAGES = frozenset(
    {
        "API key is not configured. Set DEEPSEEK_API_KEY and retry.",
        "API key is not configured. Set OPENAI_API_KEY and retry.",
    }
)


def _safe_provider_message(exc: BaseException) -> str:
    """Return a sanitized user-facing message for a provider failure.

    Fails closed: the only non-generic case is the exact, contract-guaranteed
    missing-credential error, identified by (a) the shared provider's exception
    type and (b) an exact full-string match -- and even then the returned text
    is a local canonical constant, never ``str(exc)``. No regex, no prefix, no
    substring, no passthrough of the original exception string.
    """

    if isinstance(exc, CharacterDraftError) and str(exc) in _KNOWN_MISSING_KEY_MESSAGES:
        return SAFE_MISSING_KEY_MESSAGE
    return GENERIC_PROVIDER_FAILURE_MESSAGE


@dataclass(frozen=True)
class _ActiveDialogue:
    """Internal per-session state: the public session + frozen persona context."""

    session: TestDialogueSession
    persona: str


class TestDialogueService:
    """Bound the frozen revision, hold in-memory sessions, run role-play turns."""

    def __init__(
        self,
        provider: ProviderCallable,
        *,
        transcript_turn_limit: int = DEFAULT_TRANSCRIPT_TURN_LIMIT,
    ) -> None:
        if not callable(provider):
            raise TestDialogueError("provider must be callable")
        if (
            not isinstance(transcript_turn_limit, int)
            or isinstance(transcript_turn_limit, bool)
            or transcript_turn_limit < 1
        ):
            raise TestDialogueError("transcript_turn_limit must be a positive integer")
        self._provider = provider
        self._transcript_turn_limit = transcript_turn_limit
        self._active: dict[str, _ActiveDialogue] = {}

    # -- session lifecycle -------------------------------------------------

    def start(self, pin: TestDialoguePin, semantic: Mapping[str, Any]) -> TestDialogueSession:
        """Freeze the exact revision and open a new in-memory session.

        Re-validates the semantic and re-verifies ``snapshot_hash`` so a session
        can never bind to mismatched semantic data, then builds the persona
        context ONCE. The session never re-resolves "latest" afterwards.
        """
        if not isinstance(pin, TestDialoguePin):
            raise TestDialogueError("pin must be a TestDialoguePin")
        model = self._validate_semantic(semantic)
        if compute_snapshot_hash(model) != pin.snapshot_hash:
            raise TestDialogueError(
                "snapshot hash mismatch: the semantic data does not match the "
                "selected revision"
            )
        persona = build_role_play_system_prompt(persona_context(semantic))
        session = TestDialogueSession(
            session_id=f"td-{uuid.uuid4().hex}",
            pin=pin,
            display_name=display_name(semantic),
        )
        self._active[session.session_id] = _ActiveDialogue(session=session, persona=persona)
        return session

    def send(self, session_id: str, text: str) -> TestDialogueSession:
        """Append the user message, call the provider, append the character reply."""

        active = self._require_active(session_id)
        text = self._require_text(text)

        base = len(active.session.messages)
        user_message = DialogueMessage(role="user", content=text, seq=base + 1)

        provider_messages = self._bounded_history(active.session)
        provider_messages.append({"role": "user", "content": text})

        response = self._call_provider(provider_messages, active.persona)

        character_message = DialogueMessage(role="character", content=response, seq=base + 2)
        session = replace(
            active.session,
            messages=active.session.messages + (user_message, character_message),
        )
        self._active[session_id] = _ActiveDialogue(session=session, persona=active.persona)
        return session

    def reset(self, session_id: str) -> TestDialogueSession:
        """Clear the transcript but keep the frozen revision pin and persona."""

        active = self._require_active(session_id)
        session = replace(active.session, messages=())
        self._active[session_id] = _ActiveDialogue(session=session, persona=active.persona)
        return session

    def get_session(self, session_id: str) -> TestDialogueSession:
        return self._require_active(session_id).session

    # -- internal helpers --------------------------------------------------

    def _validate_semantic(self, semantic: object) -> CharacterSemantic:
        if not isinstance(semantic, Mapping):
            raise TestDialogueError("semantic must be a mapping")
        try:
            return CharacterSemantic.from_dict(dict(semantic))
        except CharacterAuthoringValidationError as exc:
            raise TestDialogueError(f"semantic validation failed: {exc}") from exc

    def _require_active(self, session_id: object) -> _ActiveDialogue:
        if not isinstance(session_id, str) or not session_id.strip():
            raise TestDialogueError("session_id must be a non-empty string")
        active = self._active.get(session_id)
        if active is None:
            raise TestDialogueError(f"unknown test dialogue session: {session_id!r}")
        return active

    @staticmethod
    def _require_text(text: object) -> str:
        if not isinstance(text, str) or not text.strip():
            raise TestDialogueError("message text must be a non-empty string")
        return text.strip()

    def _bounded_history(self, session: TestDialogueSession) -> list[dict[str, str]]:
        """Return at most the last N completed turns (user+character pairs)."""

        limit = self._transcript_turn_limit * 2
        recent = session.messages[-limit:]
        return [{"role": _ROLE_TO_PROVIDER[m.role], "content": m.content} for m in recent]

    def _call_provider(self, messages: list[dict[str, str]], persona: str) -> str:
        try:
            response = self._provider(messages, persona)
        except Exception as exc:  # noqa: BLE001 -- sanitized at this boundary
            raise TestDialogueProviderError(_safe_provider_message(exc)) from exc
        if not isinstance(response, str) or not response.strip():
            raise TestDialogueProviderError(EMPTY_PROVIDER_RESPONSE_MESSAGE)
        return response.strip()


__all__ = [
    "DEFAULT_TRANSCRIPT_TURN_LIMIT",
    "EMPTY_PROVIDER_RESPONSE_MESSAGE",
    "GENERIC_PROVIDER_FAILURE_MESSAGE",
    "SAFE_MISSING_KEY_MESSAGE",
    "TestDialogueService",
]
