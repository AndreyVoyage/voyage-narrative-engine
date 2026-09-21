#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Character Lab Application Service v1 -- thin UI-agnostic facade.

Hides from UI code:

- Character Canon storage layout and raw domain exception types;
- session identity/storage details.

This is an application layer, NOT a new domain model. It never reimplements
Character Canon read semantics, never mutates Character Canon, and never
chooses a UI/desktop technology. Sessions are a local, offline, in-memory
application concept only -- there is no provider/network call anywhere in
this module.
"""

from __future__ import annotations

import uuid
from typing import Optional

from services.character_canon_bridge import (
    CharacterCanonBridgeError,
    list_character_ids,
    read_character_canon,
)
from services.character_canon_bridge.status import is_production_approved

from .config import CharacterLabApplicationConfig
from .errors import CANON_UNAVAILABLE, INVALID_INPUT, NOT_FOUND, CharacterLabApplicationError
from .results import CharacterInspectorDetail, CharacterSummary, CharacterVersionSummary, LabSession, Message

_CHARACTER_USAGE_CONTEXT = "authoring"


class CharacterLabApplicationService:
    """Character Lab facade: character read-side + local session model."""

    def __init__(self, config: CharacterLabApplicationConfig) -> None:
        self._config = config
        self._sessions: dict[str, LabSession] = {}
        self._session_order: list[str] = []

    # -- Character read-side (READ-ONLY over Character Canon) -----------

    def list_characters(self) -> tuple[CharacterSummary, ...]:
        """Return deterministic Character Lab-facing character summaries.

        Returns an empty tuple when no Character Canon root is configured,
        the root has no discoverable entries, or an individual character
        entry cannot be read -- never raises for this read path (the same
        graceful-degradation contract as ``services.editor_application``).
        """
        canon_root = self._config.character_canon_root
        if canon_root is None:
            return ()
        summaries: list[CharacterSummary] = []
        for character_id in list_character_ids(canon_root):
            try:
                snapshot = read_character_canon(canon_root, character_id, _CHARACTER_USAGE_CONTEXT)
            except CharacterCanonBridgeError:
                continue
            summaries.append(
                CharacterSummary(
                    character_id=character_id,
                    label=character_id,
                    status=snapshot.status,
                )
            )
        summaries.sort(key=lambda summary: summary.character_id)
        return tuple(summaries)

    def get_character_detail(self, character_id: str) -> CharacterInspectorDetail:
        """Return inspector detail for one character.

        Raises ``CharacterLabApplicationError`` (never a raw traceback) when
        Character Canon is not configured, the character is unknown, or its
        Canon entry cannot be read.
        """
        if not isinstance(character_id, str) or not character_id:
            raise CharacterLabApplicationError(INVALID_INPUT, "character_id must be a non-empty string")
        canon_root = self._config.character_canon_root
        if canon_root is None:
            raise CharacterLabApplicationError(CANON_UNAVAILABLE, "Character Canon root is not configured")
        try:
            snapshot = read_character_canon(canon_root, character_id, _CHARACTER_USAGE_CONTEXT)
        except CharacterCanonBridgeError as exc:
            raise CharacterLabApplicationError(
                NOT_FOUND, f"Character Canon unavailable for {character_id!r}: {exc}"
            ) from exc
        return CharacterInspectorDetail(
            character_id=snapshot.character_id,
            label=snapshot.character_id,
            status=snapshot.status,
            canon_approved=is_production_approved(snapshot.status),
            active_version_id=snapshot.active_version,
            source_ref=snapshot.provenance.source_ref,
        )

    def list_versions(self, character_id: str) -> tuple[CharacterVersionSummary, ...]:
        """Return the character's versions exactly as represented by current data.

        Current-main Character Canon carries a single ``active_version``
        string tag per character (no version history store). This returns
        zero entries when no tag is present, or exactly one entry -- marked
        active -- when it is. Never invents additional demo versions.
        """
        detail = self.get_character_detail(character_id)
        if detail.active_version_id is None:
            return ()
        return (CharacterVersionSummary(version_id=detail.active_version_id, is_active=True),)

    # -- Local session model (offline; no provider/network call) --------

    def create_session(self, character_id: str, version_id: Optional[str] = None) -> LabSession:
        """Create and bind a new local, offline session. Works without network."""
        if not isinstance(character_id, str) or not character_id:
            raise CharacterLabApplicationError(INVALID_INPUT, "character_id must be a non-empty string")
        session_id = uuid.uuid4().hex
        session = LabSession(
            session_id=session_id,
            character_id=character_id,
            version_id=version_id,
            transcript=(),
        )
        self._sessions[session_id] = session
        self._session_order.append(session_id)
        return session

    def list_sessions(self) -> tuple[LabSession, ...]:
        """Return sessions in creation order."""
        return tuple(self._sessions[session_id] for session_id in self._session_order)

    def get_session(self, session_id: str) -> LabSession:
        session = self._sessions.get(session_id)
        if session is None:
            raise CharacterLabApplicationError(NOT_FOUND, f"no session with id {session_id!r}")
        return session

    def append_message(self, session_id: str, role: str, content: str) -> LabSession:
        """Append one local transcript entry. Offline only -- no provider call.

        Returns the updated session; the session's ``character_id``/
        ``version_id`` binding is unchanged by this call.
        """
        session = self.get_session(session_id)
        if not isinstance(role, str) or not role:
            raise CharacterLabApplicationError(INVALID_INPUT, "role must be a non-empty string")
        if not isinstance(content, str) or not content:
            raise CharacterLabApplicationError(INVALID_INPUT, "content must be a non-empty string")
        updated = LabSession(
            session_id=session.session_id,
            character_id=session.character_id,
            version_id=session.version_id,
            transcript=session.transcript + (Message(role=role, content=content),),
        )
        self._sessions[session_id] = updated
        return updated
