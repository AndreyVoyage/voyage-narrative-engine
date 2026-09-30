#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Story Sequence v0 -- load/save boundary.

Deterministic serialize/parse/load/save of one ``StorySequence`` JSON file,
mirroring ``services/workspace_project/accepted_batch.py``: fixed key order,
one trailing LF, UTF-8, strict duplicate-key / non-finite-number rejection,
unknown-field rejection, and same-directory atomic replacement (``os.replace``
of a sibling temp file) so a reader never observes a partial write. A malformed
manifest fails closed and is never silently repaired.

There is no ratified canonical location for a StorySequence file inside this
module; callers always supply an explicit path (the real project manifest lives
under the existing ``authoring/project/`` boundary).
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .errors import (
    StorySequenceNotFoundError,
    StorySequenceStoreError,
    StorySequenceValidationError,
)
from .model import STORY_SEQUENCE_SCHEMA_VERSION, StorySequence


def serialize_story_sequence(story_sequence: StorySequence) -> bytes:
    """Return deterministic UTF-8 JSON (fixed key order, one trailing LF)."""
    if not isinstance(story_sequence, StorySequence):
        raise StorySequenceValidationError("expected StorySequence")
    return (
        json.dumps(story_sequence.to_dict(), indent=2, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise StorySequenceValidationError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise StorySequenceValidationError("non-finite JSON number")


def parse_story_sequence(data: bytes) -> StorySequence:
    """Strictly parse StorySequence JSON bytes into a validated StorySequence.

    Rejects malformed JSON, non-object roots, wrong schema, duplicate JSON keys,
    non-finite numbers, and any unknown field. Caller identity values are never
    silently normalized.
    """
    if not isinstance(data, (bytes, bytearray)):
        raise StorySequenceStoreError("parse_story_sequence: expected bytes")
    try:
        text = bytes(data).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise StorySequenceStoreError("story sequence is not valid UTF-8") from exc

    try:
        raw = json.loads(
            text, object_pairs_hook=_unique_object, parse_constant=_reject_constant
        )
    except json.JSONDecodeError as exc:
        raise StorySequenceStoreError(f"story sequence is not valid JSON: {exc}") from exc

    if not isinstance(raw, dict):
        raise StorySequenceValidationError("story sequence root must be an object")
    if raw.get("schema_version") != STORY_SEQUENCE_SCHEMA_VERSION:
        raise StorySequenceValidationError(
            f"schema_version: expected {STORY_SEQUENCE_SCHEMA_VERSION!r}"
        )
    return StorySequence.from_dict(raw)


def load_story_sequence(path: Path) -> StorySequence:
    """Load and validate the StorySequence at the explicit ``path``."""
    path = Path(path)
    if not path.exists():
        raise StorySequenceNotFoundError(f"story sequence does not exist: {path.name}")
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise StorySequenceStoreError(f"cannot read story sequence: {exc}") from exc
    return parse_story_sequence(data)


def save_story_sequence(path: Path, story_sequence: StorySequence) -> None:
    """Atomically write the deterministic serialization to the explicit ``path``.

    Validates the complete story sequence before any filesystem mutation, then
    writes to a sibling temp file and ``os.replace``-s it into place (a reader
    never observes a partial write). Malformed content is never silently repaired.
    """
    if not isinstance(story_sequence, StorySequence):
        raise StorySequenceValidationError("expected StorySequence")
    data = serialize_story_sequence(story_sequence)
    parse_story_sequence(data)  # validate the complete story sequence before mutation

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        dir=str(path.parent), prefix=".story_sequence_", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
        os.replace(tmp, str(path))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def validate_story_sequence(path: Path) -> list[str]:
    """Read-only structural validation; returns a list of error strings ([] = valid)."""
    path = Path(path)
    if not path.exists():
        return ["story sequence does not exist"]
    try:
        load_story_sequence(path)
    except StorySequenceError as exc:
        return [str(exc)]
    return []
