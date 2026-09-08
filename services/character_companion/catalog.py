#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Companion character catalog.

Companion is character-generic: the UI never hardcodes one character. The
catalog is the single place a character becomes visible to end users, and an
entry is ``available`` only when its ACCEPTED package resolves through the
existing acceptance / runtime gate (``load_accepted_character``). Raw / DRAFT /
non-accepted candidates never become available.

KIRA is the first (and currently only) real entry. Tests may inject extra
synthetic entries; production must not.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Sequence, Tuple

from services.character_lab.source_loader import build_repo_source_loader
from services.character_runtime import CharacterRuntimeError, load_accepted_character


@dataclass(frozen=True)
class CompanionCharacterEntry:
    """One catalog entry. ``subject_id`` is the runtime memory / accepted-package
    subject; ``available`` is False unless the accepted package resolved."""

    character_id: str
    display_name: str
    subject_id: str
    available: bool
    package_id: Optional[str] = None
    package_version: Optional[int] = None
    source_hash: Optional[str] = None


class CompanionCatalog:
    """An ordered set of catalog entries keyed by ``character_id``."""

    def __init__(self, entries: Iterable[CompanionCharacterEntry]) -> None:
        self._entries: Tuple[CompanionCharacterEntry, ...] = tuple(entries)
        seen = set()
        for e in self._entries:
            if e.character_id in seen:
                raise ValueError(f"duplicate catalog character_id {e.character_id!r}")
            seen.add(e.character_id)

    def all(self) -> Tuple[CompanionCharacterEntry, ...]:
        return self._entries

    def available(self) -> Tuple[CompanionCharacterEntry, ...]:
        return tuple(e for e in self._entries if e.available)

    def get(self, character_id: str) -> Optional[CompanionCharacterEntry]:
        for e in self._entries:
            if e.character_id == character_id:
                return e
        return None


_KIRA_ID = "kira"
_KIRA_DISPLAY = "Кира"


def _kira_entry(acceptance_root: Path, source_loader) -> CompanionCharacterEntry:
    try:
        accepted = load_accepted_character(
            _KIRA_ID, acceptance_root=acceptance_root, source_loader=source_loader
        )
    except CharacterRuntimeError:
        return CompanionCharacterEntry(
            character_id=_KIRA_ID, display_name=_KIRA_DISPLAY,
            subject_id=_KIRA_ID, available=False,
        )
    return CompanionCharacterEntry(
        character_id=_KIRA_ID,
        display_name=_KIRA_DISPLAY,
        subject_id=_KIRA_ID,
        available=True,
        package_id=accepted.package.package_id,
        package_version=accepted.package.package_version,
        source_hash=accepted.source_candidate_hash,
    )


def build_default_catalog(
    acceptance_root,
    source_loader=None,
    *,
    extra: Sequence[CompanionCharacterEntry] = (),
) -> CompanionCatalog:
    """The production catalog: KIRA from the accepted package, plus any
    explicitly-supplied ``extra`` entries (tests only)."""
    acceptance_root = Path(acceptance_root)
    loader = source_loader or build_repo_source_loader(acceptance_root=acceptance_root)
    return CompanionCatalog((_kira_entry(acceptance_root, loader), *extra))
