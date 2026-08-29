#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Minimal provider-independent Runtime/CIS facade for accepted CRP packages.

CRP creates the character (``CandidateCharacterPackage`` -> accepted). Runtime
lets the character live: it loads the accepted package through the committed
acceptance gate, runs sessions, records runtime events to durable memory, and
builds runtime context for a future model. Runtime memory NEVER rewrites the
accepted package.

This is the small "runtime lets the character live" surface (CASE C), not the
external CIS behavioral-validation adapter from ``CRP_MVP_CONTRACTS_v1.md`` §J.
No provider, no network, no reconstruction, no R1/R2/R3/R4/R8.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from services.crp_authoring import (
    PackageStatus,
    compute_package_hash,
)
from services.crp_authoring.acceptance_store import load_acceptance_record
from services.crp_authoring.candidate_package import CandidateCharacterPackage
from services.crp_authoring.errors import CrpValidationError

from .memory import RuntimeEvent, RuntimeMemoryBackend

__all__ = [
    "CharacterRuntimeError",
    "AcceptedCharacter",
    "RuntimeSession",
    "SourceLoader",
    "load_accepted_character",
    "start_session",
]


class CharacterRuntimeError(RuntimeError):
    """Fail-closed error for the accepted-character runtime facade."""


# A source loader rehydrates the accepted source for a subject into a typed
# CandidateCharacterPackage (provider-free, injected so tests stay hermetic).
SourceLoader = Callable[[str], CandidateCharacterPackage]


@dataclass(frozen=True)
class AcceptedCharacter:
    """The immutable accepted character: package + its canonical binding."""

    subject_id: str
    package: CandidateCharacterPackage
    source_candidate_hash: str
    acceptance_id: str


def _require_non_empty(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CharacterRuntimeError(f"{field_name} must be a non-empty string")
    return value


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_accepted_character(
    subject_id: str,
    *,
    acceptance_root: Path,
    source_loader: SourceLoader,
) -> AcceptedCharacter:
    """Resolve ``subject_id`` -> acceptance record -> rehydrated immutable package.

    Fail-closed when:

    - no acceptance record exists for the subject (a DRAFT-only source is not a
      runtime character);
    - the acceptance decision is not HUMAN_APPROVED;
    - the rehydrated package is not a ``CandidateCharacterPackage``;
    - the package subject mismatches;
    - ``compute_package_hash(package)`` mismatches the acceptance record hash.
    """
    _require_non_empty(subject_id, "subject_id")
    if not callable(source_loader):
        raise CharacterRuntimeError("source_loader must be a callable")

    try:
        record = load_acceptance_record(acceptance_root, subject_id)
    except CrpValidationError as exc:
        raise CharacterRuntimeError(
            f"no accepted character for subject {subject_id!r}: {exc}"
        ) from exc

    if record.decision is not PackageStatus.HUMAN_APPROVED:
        raise CharacterRuntimeError(
            f"accepted character {subject_id!r} is not HUMAN_APPROVED "
            f"(decision {record.decision.value!r})"
        )

    package = source_loader(subject_id)
    if not isinstance(package, CandidateCharacterPackage):
        raise CharacterRuntimeError(
            "source_loader must return a CandidateCharacterPackage"
        )
    if package.subject_id != subject_id:
        raise CharacterRuntimeError(
            f"source subject {package.subject_id!r} != requested {subject_id!r}"
        )
    source_hash = compute_package_hash(package)
    if source_hash != record.package_hash:
        raise CharacterRuntimeError(
            f"accepted source hash mismatch: computed {source_hash!r} "
            f"!= acceptance record {record.package_hash!r}"
        )

    return AcceptedCharacter(
        subject_id=subject_id,
        package=package,
        source_candidate_hash=record.package_hash,
        acceptance_id=record.acceptance_id,
    )

class RuntimeSession:
    """One runtime session bound to an accepted character + durable memory."""

    def __init__(
        self,
        accepted: AcceptedCharacter,
        memory: RuntimeMemoryBackend,
        session_id: str,
    ) -> None:
        self._accepted = accepted
        self._memory = memory
        self._session_id = _require_non_empty(session_id, "session_id")
        self._closed = False

    @property
    def accepted(self) -> AcceptedCharacter:
        return self._accepted

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def subject_id(self) -> str:
        return self._accepted.subject_id

    def record_runtime_event(
        self,
        event_type: str,
        meaning: str,
        *,
        event_id: Optional[str] = None,
        created_at: Optional[str] = None,
    ) -> RuntimeEvent:
        """Persist one runtime event to durable memory (never package seed)."""
        if self._closed:
            raise CharacterRuntimeError("runtime session is already closed")
        _require_non_empty(event_type, "event_type")
        _require_non_empty(meaning, "meaning")
        event = RuntimeEvent(
            event_id=event_id or f"evt-{uuid.uuid4().hex}",
            subject_id=self._accepted.subject_id,
            session_id=self._session_id,
            event_type=event_type,
            meaning=meaning,
            created_at=created_at or _now_iso(),
        )
        self._memory.record_event(event)
        return event

    def build_runtime_context(self) -> dict:
        """Assemble the context a future model would receive.

        Contains accepted package identity/data plus persisted runtime memory,
        so the smoke can prove both are present without a provider.
        """
        if self._closed:
            raise CharacterRuntimeError("runtime session is already closed")
        package = self._accepted.package
        events = self._memory.load_events(self._accepted.subject_id)
        return {
            "subject_id": self._accepted.subject_id,
            "source_candidate_hash": self._accepted.source_candidate_hash,
            "package_id": package.package_id,
            "package_version": package.package_version,
            "package_status": package.status.value,
            "claim_count": len(package.claims),
            "contradiction_count": len(package.contradictions),
            "unknown_count": len(package.unknowns),
            "runtime_memory": [
                {
                    "event_id": e.event_id,
                    "session_id": e.session_id,
                    "event_type": e.event_type,
                    "meaning": e.meaning,
                    "created_at": e.created_at,
                }
                for e in events
            ],
        }

    def close(self) -> None:
        """Close this session's durable-memory backend."""
        if not self._closed:
            self._memory.close()
            self._closed = True


def start_session(
    subject_id: str,
    *,
    acceptance_root: Path,
    source_loader: SourceLoader,
    memory_root: Path,
    session_id: Optional[str] = None,
) -> RuntimeSession:
    """Load the accepted character and open a new session with a fresh backend."""
    accepted = load_accepted_character(
        subject_id,
        acceptance_root=acceptance_root,
        source_loader=source_loader,
    )
    sid = session_id or f"session-{uuid.uuid4().hex}"
    memory = RuntimeMemoryBackend(memory_root, subject_id)
    return RuntimeSession(accepted, memory, sid)
