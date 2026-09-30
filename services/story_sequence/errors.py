#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exception hierarchy for Story Sequence v0.

Small, transport-independent, named exceptions, mirroring the established repo
house style (``services/workspace_project/errors.py`` / ``services/ass/errors.py``).
Messages never carry absolute machine paths or raw scene content -- only stable
logical identifiers (scene_id) and field names.
"""

from __future__ import annotations


class StorySequenceError(Exception):
    """Root of the Story Sequence exception hierarchy."""


class StorySequenceValidationError(StorySequenceError):
    """Raised on a StorySequence model invariant violation: wrong schema version,
    an empty sequence, a duplicate scene_id, an invalid scene identity, or a
    ``start_scene_id`` not present in the ordered sequence."""


class StorySequenceStoreError(StorySequenceError):
    """Raised on a canonical StorySequence file-store failure (read/parse/write)."""


class StorySequenceNotFoundError(StorySequenceStoreError):
    """Raised when the StorySequence file does not exist at the requested path."""


class StorySequenceBatchValidationError(StorySequenceError):
    """Raised when a StorySequence cannot be validated against an accepted
    OrderedASS publication batch (unknown scene, missing scene, or an
    unresolved ``start_scene_id``)."""
