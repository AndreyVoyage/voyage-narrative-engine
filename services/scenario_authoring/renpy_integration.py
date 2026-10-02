#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scenario Authoring (SE-1.5) -- Ren'Py export integration bridge.

Connects the Scenario Editor authoring pipeline to the EXISTING NARRATIVE
Ren'Py exporter. This module is the thinnest possible integration boundary and
reuses engine-native functionality end to end; it does NOT create a second
renderer, story runtime, acceptance protocol, or independent Ren'Py exporter.

Verified path (see the SE-1.5 design draft)::

    Project
      -> project_scenes(project, ProjectionConfig)      # SE-1.3 projection
      -> SceneBody (scene_body/1.0)
      -> build_ordered_ass(...)                         # existing acceptance -> ass/0.2
      -> OrderedASS
      -> build_ordered_project_candidate(...)           # existing Ren'Py exporter
      -> Ren'Py source (.rpy)

The bridge is PURE and deterministic: it never performs filesystem writes,
never invokes the Ren'Py SDK, never scans the workspace, and never mutates the
source ``Project`` (all authoring entities are frozen). The only filesystem
reads are delegated to the existing asset resolver inside the existing
exporter; the exporter returns an immutable ``OrderedProjectCandidate``.

Explicit boundaries (fail closed):

- The complete Utterance ``text`` is always projected and exported (the single
  authoritative value). Display Portions are NOT merged, substituted, or
  silently discarded: they are carried through as the SE-1.3
  ``DisplayPortionManifest`` TECHNICAL CANDIDATE sidecar on the result, and are
  NOT representable in OrderedASS / ass/0.2 / the Ren'Py exporter, so they are
  NOT emitted into the generated source. This is a documented limitation, not a
  silent fidelity claim.
- Unsupported authoring content (group-speaker utterances, MEDIA items,
  ``relative_path`` backgrounds, unreachable content, ambiguous continuations,
  undeclared cross-scene transitions) fails closed during ``project_scenes``.
- Missing / unresolved media (a background ``asset_id`` that cannot be resolved
  to a verified image) fails closed during the exporter's asset resolution.
- ``character_symbols`` maps ``character_id -> Ren'Py Character symbol`` and is
  supplied by the caller (the bridge invents no symbol policy). A DIALOGUE
  character without a mapping fails closed inside the exporter.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Tuple

from services.ass import OrderedASS, build_ordered_ass, compute_source_hash
from services.story_sequence import STORY_SEQUENCE_SCHEMA_VERSION, StorySequence
from tools.vne_to_renpy import (
    OrderedProjectCandidate,
    build_ordered_project_candidate,
)

from .errors import ScenarioAuthoringValidationError
from .model import Project
from .projection import (
    DisplayPortionManifest,
    ProjectionConfig,
    project_scenes,
)
from .validation import validate_project

__all__ = [
    "RenpyExportResult",
    "export_project_to_renpy",
]


@dataclass(frozen=True)
class RenpyExportResult:
    """Immutable deterministic result of a successful Ren'Py export.

    Wraps the existing ``OrderedProjectCandidate`` (the exporter's real output)
    plus the SE-1.3 projection metadata that produced it, so a caller can later
    feed ``candidate`` to the existing canonical publisher / linter without
    re-running the projection.
    """

    candidate: OrderedProjectCandidate
    ordered_ass_scenes: Tuple[OrderedASS, ...]
    story_sequence: StorySequence
    portion_manifests: Tuple[DisplayPortionManifest, ...]

    @property
    def source(self) -> str:
        """The generated Ren'Py source (.rpy) string."""
        return self.candidate.source

    @property
    def source_sha256(self) -> str:
        """Lowercase hex SHA-256 of ``source``."""
        return self.candidate.source_sha256

    @property
    def scene_ids(self) -> Tuple[str, ...]:
        """Scene ids in exported (story-sequence) order."""
        return self.candidate.scene_ids

    @property
    def ass_ids(self) -> Tuple[str, ...]:
        """Accepted ass ids in exported order."""
        return self.candidate.ass_ids

    @property
    def reading_mode(self) -> str:
        """The compile-time reading mode used for the export."""
        return self.candidate.reading_mode


def export_project_to_renpy(
    project: Project,
    config: ProjectionConfig,
    *,
    reading_mode: str,
    character_symbols: Mapping[str, str],
    registry_path: Path,
    repo_root: Path,
) -> RenpyExportResult:
    """Export a validated authored ``Project`` to deterministic Ren'Py source.

    Reuses, in order: the existing cross-object integrity validation, the
    existing ``project_scenes`` projection, the existing ``build_ordered_ass``
    acceptance boundary, the existing ``StorySequence``, and the existing
    ``build_ordered_project_candidate`` exporter. No exporter logic is
    duplicated and no alternative renderer is substituted.

    Raises ``ScenarioAuthoringValidationError`` on a bridge-level input or
    integrity violation. Exporter-level failures (unsupported reading mode,
    missing character symbol, unresolved media, etc.) propagate unchanged from
    the existing exporter so the real exporter remains the authority.
    """
    if not isinstance(project, Project):
        raise ScenarioAuthoringValidationError("export_project_to_renpy: expected a Project")
    if not isinstance(config, ProjectionConfig):
        raise ScenarioAuthoringValidationError("export_project_to_renpy: expected a ProjectionConfig")

    violations = validate_project(project)
    if violations:
        raise ScenarioAuthoringValidationError(
            "export_project_to_renpy: project is inconsistent: " + "; ".join(violations)
        )

    projection = project_scenes(project, config)

    ordered_ass_scenes = []
    for body in projection.scene_bodies:
        ordered_ass_scenes.append(
            build_ordered_ass(
                body,
                ass_id="ass_{}".format(body.scene_id),
                version=1,
                source_ref="{}/{}".format(project.project_id, body.scene_id),
                source_hash=compute_source_hash(body.to_dict()),
            )
        )

    story_sequence = StorySequence(
        schema_version=STORY_SEQUENCE_SCHEMA_VERSION,
        ordered_scene_ids=projection.scene_order,
        start_scene_id=projection.start_scene_id,
    )

    candidate = build_ordered_project_candidate(
        tuple(ordered_ass_scenes),
        reading_mode=reading_mode,
        character_symbols=character_symbols,
        registry_path=Path(registry_path),
        repo_root=Path(repo_root),
        story_sequence=story_sequence,
    )

    return RenpyExportResult(
        candidate=candidate,
        ordered_ass_scenes=tuple(ordered_ass_scenes),
        story_sequence=story_sequence,
        portion_manifests=projection.portion_manifests,
    )
