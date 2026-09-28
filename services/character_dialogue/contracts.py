"""Immutable contracts for Character Lab Test Dialogue V1.

Test Dialogue is an AUTHORING QA sandbox: a user talks IN CHARACTER against an
exact, frozen, immutable Authoring revision. It is not Studio runtime and it
never writes to authoring, approval, publication, memory or evolution.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Tuple

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

_VALID_ROLES = ("user", "character")


class TestDialogueError(RuntimeError):
    """Application-level Test Dialogue error (invalid state / validation)."""


class TestDialogueProviderError(TestDialogueError):
    """The provider failed or returned an empty response; nothing persisted."""


@dataclass(frozen=True)
class DialogueMessage:
    """One transcript entry.

    ``role`` is either ``user`` or ``character``. Provider-specific roles
    (``system``/``assistant``) are a provider-boundary concern only and never
    appear in the public transcript.
    """

    role: str
    content: str
    seq: int

    def __post_init__(self) -> None:
        if self.role not in _VALID_ROLES:
            raise TestDialogueError(f"unknown dialogue role: {self.role!r}")
        if not isinstance(self.content, str):
            raise TestDialogueError("dialogue message content must be a string")
        if not isinstance(self.seq, int) or isinstance(self.seq, bool):
            raise TestDialogueError("dialogue message seq must be an integer")


@dataclass(frozen=True)
class TestDialoguePin:
    """Exact immutable Authoring revision coordinate for a test session.

    Deliberately mirrors ``CharacterSessionPin`` field-for-field but lives in
    this package so the dialogue layer never imports
    ``services.character_lab_application`` (which would create an import cycle:
    the facade imports this package). The facade maps one to the other.
    """

    character_id: str
    version_id: str
    revision_id: str
    snapshot_hash: str

    def __post_init__(self) -> None:
        for name in ("character_id", "version_id", "revision_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise TestDialogueError(f"{name} must be a non-empty string")
        if not isinstance(self.snapshot_hash, str) or not _SHA256_RE.fullmatch(self.snapshot_hash):
            raise TestDialogueError("snapshot_hash must be a lowercase SHA-256 digest")


@dataclass(frozen=True)
class TestDialogueSession:
    """An in-memory test session bound to one frozen revision.

    ``messages`` is the full in-memory transcript (user + character turns in
    order). It is never persisted and never written to authoring/memory. The
    persona/system context is deliberately NOT part of this public value; it
    stays internal to :class:`TestDialogueService`.
    """

    session_id: str
    pin: TestDialoguePin
    display_name: str
    messages: Tuple[DialogueMessage, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.session_id, str) or not self.session_id.strip():
            raise TestDialogueError("session_id must be a non-empty string")
        if not isinstance(self.display_name, str):
            raise TestDialogueError("display_name must be a string")
        if not isinstance(self.pin, TestDialoguePin):
            raise TestDialogueError("pin must be a TestDialoguePin")


__all__ = [
    "DialogueMessage",
    "TestDialogueError",
    "TestDialoguePin",
    "TestDialogueProviderError",
    "TestDialogueSession",
]
