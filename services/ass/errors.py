#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exception hierarchy for Accepted Scene Snapshot (ASS v0).

Mirrors the domain-level error style of ``services/persona_gateway/errors.py``:
small, transport-independent, named exceptions. Messages must never contain
raw scene content or absolute local filesystem paths -- only stable logical
identifiers (scene_id, beat_id, branch_id, field names) may appear.
"""

from __future__ import annotations


class ASSError(Exception):
    """Root of the Accepted Scene Snapshot exception hierarchy."""


class ASSSourceError(ASSError):
    """Raised when the source scenario payload is absent, malformed, or fails
    the shared ``narrative_schema_v2.validate_scene`` semantic validation.

    Covers: unreadable/missing source files, invalid JSON, unsupported
    ``schema_version``, and any structural violation of the V2 source schema.
    """


class ASSNormalizationError(ASSError):
    """Raised when a source that has already passed validation cannot be
    normalized into an ASS envelope.

    Covers: missing explicit ``location_id`` or ``source_ref``, an unknown
    ``branch_id``, a beat whose single content channel cannot be derived,
    and duplicate ``beat_id`` detected at the ASS layer (defense in depth,
    independently of the shared source validator).
    """