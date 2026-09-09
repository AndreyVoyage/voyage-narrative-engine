#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministic local reference selection.

Adapted from ``tools/reference_selector.py`` in the VNE repo: the proven
priority ladder (face/identity authority -> body -> face/expression support ->
motion support), bounded 2-4 per character, SHA + asset-identity de-dupe, stable
ordering. The VNE version consumes a curated semantic *catalog*; Companion V1
drives the ladder directly off ``CharacterLocalSnapshot.references[].roles`` (a
small hand-imported set), and "one body" is relaxed to "all body views" up to
the cap. Roles come ONLY from the snapshot manifest -- never a filename guess,
never Character Canon.
"""

from __future__ import annotations

from typing import Optional, Sequence, Tuple

from ..character_import.local_snapshot import CharacterLocalSnapshot, SnapshotReference
from .errors import ReferenceSelectionError

MIN_AUTO_REFS = 2
MAX_AUTO_REFS = 4

ROLE_PORTRAIT = "portrait"
ROLE_FACE = "face"
ROLE_BODY = "body"
ROLE_EXPRESSION = "expression"
ROLE_MOTION = "motion"


def _has(ref: SnapshotReference, role: str) -> bool:
    return role in ref.roles


def select_reference_asset_ids(
    snapshot: CharacterLocalSnapshot,
    *,
    explicit_asset_ids: Optional[Sequence[str]] = None,
) -> Tuple[str, ...]:
    """Return the ordered asset ids to condition on.

    * ``explicit_asset_ids`` supplied -> validate every id belongs to the active
      snapshot, preserve caller order, reject unknown ids. No auto min/max clamp
      (a manual override is trusted; still de-duped while preserving first use).
    * otherwise -> deterministic auto selection (2..4).
    """
    by_id = {r.asset_id: r for r in snapshot.references}

    if explicit_asset_ids is not None:
        chosen: list[str] = []
        seen: set[str] = set()
        for aid in explicit_asset_ids:
            if aid not in by_id:
                raise ReferenceSelectionError(
                    f"explicit reference {aid!r} is not in snapshot {snapshot.character_id!r} "
                    f"{snapshot.snapshot_version!r}"
                )
            if aid not in seen:
                seen.add(aid)
                chosen.append(aid)
        if not chosen:
            raise ReferenceSelectionError("explicit_asset_ids resolved to an empty selection")
        return tuple(chosen)

    refs = list(snapshot.references)
    face_pool = sorted(
        (r for r in refs if _has(r, ROLE_PORTRAIT) or _has(r, ROLE_FACE)),
        key=lambda r: (0 if _has(r, ROLE_PORTRAIT) else 1, r.asset_id),
    )
    body_pool = sorted((r for r in refs if _has(r, ROLE_BODY)), key=lambda r: r.asset_id)
    expr_pool = sorted((r for r in refs if _has(r, ROLE_EXPRESSION)), key=lambda r: r.asset_id)
    motion_pool = sorted((r for r in refs if _has(r, ROLE_MOTION)), key=lambda r: r.asset_id)

    if not face_pool:
        raise ReferenceSelectionError(
            f"no face/portrait identity reference for {snapshot.character_id!r}"
        )

    ordered: list[str] = []
    seen_id: set[str] = set()
    seen_sha: set[str] = set()

    def add(ref: SnapshotReference) -> None:
        if ref.asset_id in seen_id or ref.sha256 in seen_sha:
            return
        seen_id.add(ref.asset_id)
        seen_sha.add(ref.sha256)
        ordered.append(ref.asset_id)

    add(face_pool[0])                       # 1. identity authority (portrait preferred)
    for b in body_pool:                     # 2. body view(s)
        add(b)
    if expr_pool:                           # 3. face/expression support
        add(expr_pool[0])
    if motion_pool:                         # 4. motion support
        add(motion_pool[0])

    selected = tuple(ordered[:MAX_AUTO_REFS])
    if len(selected) < MIN_AUTO_REFS:
        raise ReferenceSelectionError(
            f"fewer than {MIN_AUTO_REFS} usable references for {snapshot.character_id!r}"
        )
    return selected
