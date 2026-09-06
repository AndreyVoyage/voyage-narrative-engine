#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OrderedASS multi-scene project-candidate builder v1 (pure).

Builds a deterministic combined Ren'Py source string from a non-empty tuple of
accepted ``OrderedASS`` scenes, using the CLOSED per-scene renderer
(``ordered_ass_exporter.render_ordered_ass``) and the CLOSED asset resolver
(``ordered_asset_resolver.resolve_ordered_assets_for_renpy``).

Boundary:

- explicit non-empty ``tuple[OrderedASS, ...]`` input (no dict / SceneBody /
  legacy ASS / filesystem loading / directory scanning / ASS store / Scenario V2);
- canonical scene order = ascending raw ``scene_id`` sort (never caller order);
- batch-wide ``known_scene_ids`` and a single batch-wide SET asset union;
- exactly one asset-resolver call over the sorted unique asset union;
- defensive label-uniqueness validation (no new label scheme);
- pure: returns a frozen ``OrderedProjectCandidate`` and performs NO filesystem
  write (the only filesystem reads are delegated to the asset resolver).

The reserved candidate filename is TEMP identity only -- it is NOT the
permanent canonical generated-file decision.
"""

from __future__ import annotations

import base64
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from services.ass import OrderedASS
from services.scene_body import VISUAL_OP_SET, VisualChangeEvent

from .ordered_ass_exporter import (
    READING_MODES,
    ReadingMode,
    entry_label,
    render_ordered_ass,
    scene_end_label,
    scene_start_label,
)
from .ordered_asset_resolver import resolve_ordered_assets_for_renpy

__all__ = [
    "build_ordered_project_candidate",
    "OrderedProjectCandidate",
    "ORDERED_ASS_CANDIDATE_FILENAME",
    "OrderedProjectExportError",
]

# Reserved TEMP candidate identity. Not a permanent canonical filename decision.
ORDERED_ASS_CANDIDATE_FILENAME = "vne_ordered_ass_candidate.rpy"

_CONTENT_HASH_RE = re.compile(r"[0-9a-f]{64}\Z")


class OrderedProjectExportError(ValueError):
    """Raised when a multi-scene project candidate cannot be built. Fails closed."""


def _b32_token(raw: str) -> str:
    """RFC 4648 Base32 (UTF-8) -> lowercase, '=' padding stripped.

    Comment-safe deterministic encoding of an untrusted identifier. Mirrors the
    closed exporter's base32 token so labels and comment tokens stay consistent.
    """
    return base64.b32encode(raw.encode("utf-8")).decode("ascii").lower().rstrip("=")


@dataclass(frozen=True)
class OrderedProjectCandidate:
    """Immutable deterministic multi-scene Ren'Py project candidate."""

    source: str
    source_sha256: str
    scene_ids: tuple[str, ...]
    ass_ids: tuple[str, ...]
    reading_mode: str
    candidate_filename: str


def _validate_batch(scenes: tuple[OrderedASS, ...]) -> None:
    if not isinstance(scenes, tuple):
        raise OrderedProjectExportError("scenes must be a tuple[OrderedASS, ...]")
    if len(scenes) == 0:
        raise OrderedProjectExportError("scenes must be non-empty")
    seen_scene_ids: set[str] = set()
    seen_ass_ids: set[str] = set()
    for scene in scenes:
        if not isinstance(scene, OrderedASS):
            raise OrderedProjectExportError("every scene must be an OrderedASS")
        if scene.scene_id in seen_scene_ids:
            raise OrderedProjectExportError("duplicate scene_id {!r}".format(scene.scene_id))
        seen_scene_ids.add(scene.scene_id)
        if scene.ass_id in seen_ass_ids:
            raise OrderedProjectExportError("duplicate ass_id {!r}".format(scene.ass_id))
        seen_ass_ids.add(scene.ass_id)
        _validate_identity(scene)


def _validate_identity(scene: OrderedASS) -> None:
    if not isinstance(scene.version, int) or isinstance(scene.version, bool) or scene.version < 1:
        raise OrderedProjectExportError("version must be a positive integer")
    if not isinstance(scene.content_hash, str) or _CONTENT_HASH_RE.fullmatch(scene.content_hash) is None:
        raise OrderedProjectExportError("content_hash must be 64 lowercase hex characters")


def _canonical_order(scenes: tuple[OrderedASS, ...]) -> tuple[OrderedASS, ...]:
    return tuple(sorted(scenes, key=lambda s: s.scene_id))


def _validate_label_uniqueness(scenes: tuple[OrderedASS, ...]) -> None:
    seen: set[str] = set()
    for scene in scenes:
        for label in (scene_start_label(scene.scene_id), scene_end_label(scene.scene_id)):
            if label in seen:
                raise OrderedProjectExportError("duplicate generated label {!r}".format(label))
            seen.add(label)
        for entry in scene.ordered_flow:
            label = entry_label(scene.scene_id, entry.entry_id)
            if label in seen:
                raise OrderedProjectExportError("duplicate generated label {!r}".format(label))
            seen.add(label)


def _collect_set_asset_ids(scenes: tuple[OrderedASS, ...]) -> list[str]:
    asset_ids: set[str] = set()
    for scene in scenes:
        for entry in scene.ordered_flow:
            if isinstance(entry, VisualChangeEvent) and entry.operation == VISUAL_OP_SET:
                if entry.asset_id is not None:
                    asset_ids.add(entry.asset_id)
    return sorted(asset_ids)


def _build_source(
    sorted_scenes: tuple[OrderedASS, ...],
    *,
    reading_mode: str,
    character_symbols: Mapping[str, str],
    known_scene_ids: frozenset[str],
    resolved_assets: Mapping[str, object],
) -> str:
    lines: list[str] = [
        "# AUTO-GENERATED OrderedASS Ren'Py project candidate.",
        "# generated by tools/vne_to_renpy/ordered_ass_project_exporter.py",
        "# reading_mode: {}".format(reading_mode),
        "# scene_count: {}".format(len(sorted_scenes)),
    ]
    for scene in sorted_scenes:
        lines.append("")
        lines.append(
            "# accepted_ass: {} version={} content_hash={} scene_label={}".format(
                _b32_token(scene.ass_id),
                scene.version,
                scene.content_hash,
                scene_start_label(scene.scene_id),
            )
        )
        lines.append("")
        scene_src = render_ordered_ass(
            scene,
            reading_mode=reading_mode,
            character_symbols=character_symbols,
            known_scene_ids=known_scene_ids,
            resolved_assets=resolved_assets,
        )
        lines.extend(scene_src.rstrip("\n").split("\n"))
    return "\n".join(lines) + "\n"


def build_ordered_project_candidate(
    scenes: tuple[OrderedASS, ...],
    *,
    reading_mode: ReadingMode,
    character_symbols: Mapping[str, str],
    registry_path: Path,
    repo_root: Path,
) -> OrderedProjectCandidate:
    """Build an immutable deterministic multi-scene OrderedASS project candidate.

    Canonical scene order is ascending raw ``scene_id``; the batch-wide
    ``known_scene_ids`` is exactly the supplied scene IDs; the SET asset union is
    resolved exactly once over the sorted unique asset IDs; every scene is
    rendered through the closed per-scene renderer. Pure: no filesystem write,
    no Story Graph, no Variables, no ASS store, no Scenario V2 conversion.
    """
    _validate_batch(scenes)
    if reading_mode not in READING_MODES:
        raise OrderedProjectExportError(
            "unsupported reading_mode {!r}; expected one of {}".format(reading_mode, READING_MODES)
        )

    sorted_scenes = _canonical_order(scenes)
    _validate_label_uniqueness(sorted_scenes)

    known_scene_ids = frozenset(scene.scene_id for scene in sorted_scenes)

    asset_union = _collect_set_asset_ids(sorted_scenes)
    resolved_assets = resolve_ordered_assets_for_renpy(
        asset_union,
        registry_path=registry_path,
        repo_root=repo_root,
    )

    source = _build_source(
        sorted_scenes,
        reading_mode=reading_mode,
        character_symbols=character_symbols,
        known_scene_ids=known_scene_ids,
        resolved_assets=resolved_assets,
    )
    source_sha256 = hashlib.sha256(source.encode("utf-8")).hexdigest()

    return OrderedProjectCandidate(
        source=source,
        source_sha256=source_sha256,
        scene_ids=tuple(scene.scene_id for scene in sorted_scenes),
        ass_ids=tuple(scene.ass_id for scene in sorted_scenes),
        reading_mode=reading_mode,
        candidate_filename=ORDERED_ASS_CANDIDATE_FILENAME,
    )
