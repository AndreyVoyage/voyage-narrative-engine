#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exception hierarchy for Scene Interpretation Artifact v0.

The slice performs NO interpretation and NO provider calls; these errors
describe source-compatibility and validation failures when assembling the
downstream artifact.
"""

from __future__ import annotations


class SceneInterpretationError(Exception):
    """Root of the Scene Interpretation Artifact exception hierarchy."""


class SceneInterpretationValidationError(SceneInterpretationError):
    """Raised when source anchors are incompatible, a character snapshot is
    invalid/duplicate/non-participant, or the interpretation payload is not
    JSON-compatible."""


class CharacterStatusUnknownError(SceneInterpretationError):
    """Raised when a Character Canon snapshot carries an unsupported status.
    The artifact fails closed; it never invents an APPROVED equivalence."""