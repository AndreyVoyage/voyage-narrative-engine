#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scene Interpretation Artifact v0 -- public API.

Exposes the deeply immutable ``SceneInterpretationArtifact`` model plus the
deterministic ``build_scene_interpretation_artifact`` builder. This package
performs NO interpretation, makes NO provider/LLM call, and never mutates
ASS, Location Canon, or Character Canon bridge production code.
"""

from __future__ import annotations

from .builder import (
    ARTIFACT_SCHEMA_VERSION,
    build_scene_interpretation_artifact,
)
from .errors import (
    CharacterStatusUnknownError,
    SceneInterpretationError,
    SceneInterpretationValidationError,
)
from .hashing import compute_content_hash
from .model import (
    AssAnchor,
    CharacterAnchor,
    LocationAnchor,
    SceneInterpretationArtifact,
)

__all__ = [
    "build_scene_interpretation_artifact",
    "ARTIFACT_SCHEMA_VERSION",
    "SceneInterpretationArtifact",
    "AssAnchor",
    "LocationAnchor",
    "CharacterAnchor",
    "compute_content_hash",
    "SceneInterpretationError",
    "SceneInterpretationValidationError",
    "CharacterStatusUnknownError",
]