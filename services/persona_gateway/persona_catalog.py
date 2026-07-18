#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PersonaCatalog -- caller-injected multi-character persona catalog
(N7 Persona Data Gateway, P1b Option A: INJECTED_CATALOG_NO_REGISTRY).

Design, per the P1b multi-character compatibility read-only preflight
(``N7_P1B_MULTI_CHARACTER_COMPATIBILITY_READONLY_PREFLIGHT_2026-07-18.md``,
Phase 6/11) and the owner's fixed Option A decisions:

* The caller injects a static ``Mapping[str, pathlib.Path]`` of
  ``character_id -> persona_root``. There is no runtime scan of
  ``personas/``, no ``personas/REGISTRY.json`` read or write, and no
  production-code hardcoded character list.
* One ``PersonaRepository`` is eagerly constructed and validated per
  injected entry, at catalog-construction time -- consistent with
  ``PersonaRepository``'s own eager-construction discipline. A wrong
  root/id pairing, an invalid manifest, or an unsupported module
  extension (e.g. a non-``.json`` module id) fails construction via the
  underlying ``PersonaRepository`` error, unmodified and unwrapped.
* Deterministic public ordering is ascending ``character_id.casefold()``
  (owner decision) -- this is purely a presentation-order concern; the
  original caller-supplied spelling of every character id is always
  preserved verbatim (never re-cased, never renamed).
* Duplicate ids are rejected at construction: both exact duplicates and
  case-insensitive (``casefold()``) collisions.
* The caller's mapping is copied immediately and never referenced again
  after construction returns; mutating it afterwards has no effect on
  the catalog. No mutable internal collection is exposed publicly.

This module intentionally does not modify ``persona_repository.py``,
``provenance.py``, ``state_snapshot_service.py``, or
``history_query_service.py`` -- per the preflight, those are already
character-parametric and require no change for this slice.
"""

from __future__ import annotations

from collections.abc import Mapping as MappingABC
from pathlib import Path
from typing import Dict, Mapping, Tuple

from .errors import CharacterNotFoundError, ManifestIntegrityError
from .models import CharacterManifest, CharacterRef, ModuleResult
from .persona_repository import PersonaRepository

DEFAULT_MAX_CHARACTERS = 16
DEFAULT_MAX_AGGREGATE_MANIFEST_ENTRIES = 1024


def _is_positive_int(value: object) -> bool:
    """``True`` iff ``value`` is a plain ``int`` (never ``bool``) > 0."""
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


class PersonaCatalog:
    """A validated, read-only collection of caller-injected character
    repositories.

    Constructor is eager: every injected entry is validated (and its
    ``PersonaRepository`` fully constructed) once, here, and cached.
    There is no lazy re-validation and no filesystem write of any kind.
    """

    def __init__(
        self,
        entries: Mapping[str, Path],
        *,
        max_characters: int = DEFAULT_MAX_CHARACTERS,
        max_aggregate_manifest_entries: int = DEFAULT_MAX_AGGREGATE_MANIFEST_ENTRIES,
    ) -> None:
        if not _is_positive_int(max_characters):
            raise ValueError(
                "max_characters must be a positive integer (bool is not accepted)"
            )
        if not _is_positive_int(max_aggregate_manifest_entries):
            raise ValueError(
                "max_aggregate_manifest_entries must be a positive integer "
                "(bool is not accepted)"
            )

        if not isinstance(entries, MappingABC):
            raise TypeError("entries must be a Mapping[str, pathlib.Path]")

        # Copy caller input immediately: from this point on, the catalog
        # never touches or retains the caller's own mapping object.
        items = list(entries.items())

        if not items:
            raise ManifestIntegrityError(
                "PersonaCatalog requires at least one injected character"
            )

        if len(items) > max_characters:
            raise ManifestIntegrityError(
                f"catalog has {len(items)} injected characters, exceeds cap "
                f"of {max_characters}"
            )

        seen_casefold: Dict[str, str] = {}
        repositories: Dict[str, PersonaRepository] = {}

        for character_id, persona_root in items:
            if not isinstance(character_id, str) or not character_id:
                raise ManifestIntegrityError(
                    "character id must be a non-empty string"
                )
            if character_id.strip() != character_id:
                raise ManifestIntegrityError(
                    "character id must not have leading/trailing whitespace: "
                    f"{character_id!r}"
                )

            folded = character_id.casefold()
            if folded in seen_casefold:
                raise ManifestIntegrityError(
                    "duplicate character id (exact or case-insensitive "
                    f"collision): {character_id!r} collides with "
                    f"{seen_casefold[folded]!r}"
                )
            seen_casefold[folded] = character_id

            # Delegate all manifest/module/security validation to the
            # existing, unmodified PersonaRepository. A wrong root/id
            # pairing, an invalid manifest, or an unsupported module
            # extension raises here, unmodified, and aborts the whole
            # catalog construction (fail fast, not silent partial catalog).
            repository = PersonaRepository(Path(persona_root), character_id)
            repositories[character_id] = repository

        aggregate_entries = sum(
            len(repo.get_character_manifest(cid).modules)
            for cid, repo in repositories.items()
        )
        if aggregate_entries > max_aggregate_manifest_entries:
            raise ManifestIntegrityError(
                f"catalog aggregate manifest entries {aggregate_entries} "
                f"exceeds cap of {max_aggregate_manifest_entries}"
            )

        self._repositories: Dict[str, PersonaRepository] = repositories
        self._ordered_ids: Tuple[str, ...] = tuple(
            sorted(repositories.keys(), key=lambda cid: cid.casefold())
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def __contains__(self, character_id: object) -> bool:
        return isinstance(character_id, str) and character_id in self._repositories

    def list_characters(self) -> Tuple[CharacterRef, ...]:
        """Return every injected character, ordered ascending by
        ``character_id.casefold()``. Original id spelling is preserved
        verbatim; display names come from each character's own manifest."""
        return tuple(
            CharacterRef(
                id=cid,
                name=self._repositories[cid].get_character_manifest(cid).name,
            )
            for cid in self._ordered_ids
        )

    def get_repository(self, character_id: str) -> PersonaRepository:
        """Return the validated ``PersonaRepository`` for ``character_id``.

        Lookup is exact and case-sensitive: only the precise id spelling
        supplied at construction resolves. Raises ``CharacterNotFoundError``
        for any id not present in the catalog."""
        if isinstance(character_id, str):
            repository = self._repositories.get(character_id)
            if repository is not None:
                return repository
        raise CharacterNotFoundError(f"unknown character_id: {character_id!r}")

    def get_character_manifest(self, character_id: str) -> CharacterManifest:
        return self.get_repository(character_id).get_character_manifest(character_id)

    def read_module(self, character_id: str, module_id: str) -> ModuleResult:
        return self.get_repository(character_id).read_module(character_id, module_id)
