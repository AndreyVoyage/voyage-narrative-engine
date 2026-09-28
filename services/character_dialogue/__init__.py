"""Character Lab Test Dialogue V1 -- in-character AUTHORING QA sandbox.

This package lets a user open a sandbox conversation against an EXACT, frozen,
immutable Character Authoring revision and receive an in-character reply from a
provider. It is deliberately separate from the AI-first *creation* flow
(``services.character_draft``) and from Studio runtime: it never writes to
authoring, approval, publication, canonical-current, memory or evolution.
"""

from __future__ import annotations

from .contracts import (
    DialogueMessage,
    TestDialogueError,
    TestDialoguePin,
    TestDialogueProviderError,
    TestDialogueSession,
)
from .service import DEFAULT_TRANSCRIPT_TURN_LIMIT, TestDialogueService

__all__ = [
    "DEFAULT_TRANSCRIPT_TURN_LIMIT",
    "DialogueMessage",
    "TestDialogueError",
    "TestDialoguePin",
    "TestDialogueProviderError",
    "TestDialogueSession",
    "TestDialogueService",
]
