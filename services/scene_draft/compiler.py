#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scene Editor domain lifecycle -- thin acceptance compiler.

Turns an existing DRAFT ``SceneVersion`` into an ACCEPTED one by calling the
existing UNMODIFIED ASS importer (``services.ass.importer.import_scene``) and
recording only an ``AcceptanceLink`` (ass_id + ass_content_hash) on the
SceneVersion. ASS remains the canonical accepted-scene contract; no new ASS
store or directory convention is introduced here.

Stdlib only. No network, no provider calls.
"""

from __future__ import annotations

from typing import Any

from services.ass import import_scene

from .errors import AcceptanceError, AlreadyAcceptedError
from .model import LIFECYCLE_DRAFT, AcceptanceLink, SceneVersion
from .store import SceneDraftStore


def accept_draft(
    store: SceneDraftStore,
    scene_id: str,
    version: int,
    *,
    ass_id: str,
    location_id: str,
    source_ref: str,
) -> tuple[SceneVersion, Any]:
    """Accept a DRAFT SceneVersion into an ASS and link them.

    Returns ``(updated SceneVersion with lifecycle ACCEPTED, ASS)``. The
    transition is one-time: calling again on the same version fails closed.
    """
    record = store.read_version(scene_id, version)
    if record.lifecycle != LIFECYCLE_DRAFT:
        raise AlreadyAcceptedError(f"scene {scene_id!r} version {version} is not DRAFT")

    ass = import_scene(
        record.body_plain(),
        ass_id=ass_id,
        version=record.version,
        location_id=location_id,
        source_ref=source_ref,
    )

    if ass.scene_id != record.scene_id:
        raise AcceptanceError(
            f"ASS scene_id {ass.scene_id!r} does not equal SceneVersion scene_id {record.scene_id!r}"
        )
    if ass.version != record.version:
        raise AcceptanceError(
            f"ASS version {ass.version} does not equal SceneVersion version {record.version}"
        )

    acceptance = AcceptanceLink(ass_id=ass.ass_id, ass_content_hash=ass.content_hash)
    updated = store.commit_acceptance(scene_id, version, acceptance)
    return updated, ass
