#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scene Editor domain lifecycle -- ordered acceptance compiler.

Turns an existing DRAFT ``SceneVersion`` (whose authored body is a
``SceneBody``) into an ACCEPTED one by:

1. reading the persisted SceneVersion;
2. requiring DRAFT;
3. running acceptance-completeness validation on the SceneBody;
4. deterministically projecting it into an OrderedASS via
   ``services.ass.build_ordered_ass`` (location comes from the SceneBody);
5. verifying scene_id / version equality;
6. recording only an ``AcceptanceLink`` (ass_id + ass_content_hash).

This compiler never calls the legacy ``services.ass.importer.import_scene`` and
never introduces a second canonical accepted artifact. ASS/OrderedASS remains
the canonical accepted-scene contract.

Stdlib only. No network, no provider calls.
"""

from __future__ import annotations

from typing import Optional

from services.ass import OrderedASS, build_ordered_ass
from services.scene_body import validate_acceptance_complete

from .errors import AcceptanceError, AcceptanceIncompleteError, AlreadyAcceptedError
from .model import LIFECYCLE_DRAFT, AcceptanceLink, SceneVersion
from .store import SceneDraftStore


def accept_draft(
    store: SceneDraftStore,
    scene_id: str,
    version: int,
    *,
    ass_id: str,
    source_ref: str,
    supersedes: Optional[str] = None,
    created_at: Optional[str] = None,
    author: Optional[str] = None,
) -> tuple[SceneVersion, OrderedASS]:
    """Accept a DRAFT SceneVersion into an OrderedASS and link them.

    ``ass_id`` and ``source_ref`` are acceptance/provenance inputs, not editable
    scene content. The authoritative ``location_id`` comes from the SceneBody.
    Returns ``(updated SceneVersion with lifecycle ACCEPTED, OrderedASS)``. The
    transition is one-time: calling again on the same version fails closed.
    """
    record = store.read_version(scene_id, version)
    if record.lifecycle != LIFECYCLE_DRAFT:
        raise AlreadyAcceptedError(f"scene {scene_id!r} version {version} is not DRAFT")

    # Completeness failure MUST occur before OrderedASS construction and before
    # any lifecycle mutation.
    errors = validate_acceptance_complete(record.body)
    if errors:
        raise AcceptanceIncompleteError(
            f"scene {scene_id!r} version {version} is not acceptance-complete: {errors[0]}"
        )

    ordered_ass = build_ordered_ass(
        record.body,
        ass_id=ass_id,
        version=record.version,
        source_ref=source_ref,
        source_hash=record.content_hash,
        supersedes=supersedes,
        created_at=created_at,
        author=author,
    )

    if ordered_ass.scene_id != record.scene_id:
        raise AcceptanceError(
            f"OrderedASS scene_id {ordered_ass.scene_id!r} does not equal "
            f"SceneVersion scene_id {record.scene_id!r}"
        )
    if ordered_ass.version != record.version:
        raise AcceptanceError(
            f"OrderedASS version {ordered_ass.version} does not equal "
            f"SceneVersion version {record.version}"
        )

    acceptance = AcceptanceLink(
        ass_id=ordered_ass.ass_id,
        ass_content_hash=ordered_ass.content_hash,
    )
    updated = store.commit_acceptance(scene_id, version, acceptance)
    return updated, ordered_ass
