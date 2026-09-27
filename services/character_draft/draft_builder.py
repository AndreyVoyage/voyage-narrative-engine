"""Deterministic draft builder: AI semantic payload -> validated CharacterSemantic.

The builder never invents content.  It takes the AI's ``semantic`` object,
applies two deterministic overrides that are NOT fabrications (the display name
is the user's explicit input; ``visual_identity`` is empty because media assets
are out of scope), and validates the result against the real Character Authoring
model.  Malformed payloads fail closed.
"""

from __future__ import annotations

from typing import Any, Mapping

from services.character_authoring import (
    CharacterAuthoringValidationError,
    CharacterSemantic,
)

from .contracts import CharacterDraftError, extract_json_object


def parse_draft_text(text: str) -> dict[str, Any]:
    """Extract and return the ``semantic`` object from a draft provider response."""
    data = extract_json_object(text)
    if "semantic" not in data:
        raise CharacterDraftError("malformed AI draft: missing 'semantic' object")
    semantic = data["semantic"]
    if not isinstance(semantic, Mapping):
        raise CharacterDraftError("malformed AI draft: 'semantic' must be an object")
    return dict(semantic)


def build_semantic(semantic: Mapping[str, Any], *, display_name: str) -> CharacterSemantic:
    """Validate an AI semantic payload and apply deterministic overrides."""
    try:
        data = dict(semantic)
        identity = dict(data.get("identity") or {})
        identity["display_name"] = display_name
        data["identity"] = identity
        data["visual_identity"] = {}
        return CharacterSemantic.from_dict(data)
    except CharacterAuthoringValidationError as exc:
        raise CharacterDraftError(f"AI draft is malformed: {exc}") from exc


__all__ = ["build_semantic", "parse_draft_text"]
