"""Presentation state for the M1-S1 editable draft workspace.

Qt-free session model for one scene version: holds the editable plain-data
copy of the body (``EditorSceneWorkspace.body``), tracks CLEAN/DIRTY by
comparing the working buffer against the last saved snapshot, and rebuilds
the complete body for ``EditorApplicationService.save_draft``.

Only scene-level scalar fields and TextEntry ``text`` are editable. Entry
creation/removal is intentionally absent: entry-id allocation has no existing
project contract, and removal could silently invalidate unsupported
ChoiceEntry targets. Unsupported entry kinds (CHOICE, VISUAL, ...) are never
structurally touched — they round-trip through the deep-copied buffer
unchanged and in original order.
"""

from __future__ import annotations

import copy
import enum
from typing import Any

# The facade exposes lifecycle as a plain string on its DTOs; the domain
# constants live in services.scene_draft, which the UI firewall forbids.
LIFECYCLE_DRAFT = "DRAFT"

EDITABLE_SCENE_FIELDS = ("scene_title", "location_id", "content_rating")

TEXT_ENTRY_KIND = "TEXT"


class UnsavedDecision(enum.Enum):
    """User decision when a dirty buffer is about to be replaced."""

    SAVE = "save"
    DISCARD = "discard"
    CANCEL = "cancel"


class ValidationState(enum.Enum):
    """Presentation state for validation of the persisted draft version."""

    DIRTY = "dirty"
    SAVED_NOT_VALIDATED = "saved_not_validated"
    VALIDATED_CURRENT = "validated_current"


class DraftEditSession:
    """Editable presentation buffer for one scene version.

    ``is_dirty`` is computed (buffer vs last-saved snapshot), so programmatic
    widget updates and reverted edits never produce false dirty state.
    """

    def __init__(
        self, scene_id: str, version: int, lifecycle: str, body: dict[str, Any]
    ) -> None:
        self.scene_id = scene_id
        self.version = version
        self.lifecycle = lifecycle
        self._original = copy.deepcopy(body)
        self._buffer = copy.deepcopy(body)

    @property
    def editable(self) -> bool:
        return self.lifecycle == LIFECYCLE_DRAFT

    @property
    def is_dirty(self) -> bool:
        return self._buffer != self._original

    def scene_field(self, key: str) -> str:
        value = self._buffer.get(key)
        return "" if value is None else str(value)

    def set_scene_field(self, key: str, value: str) -> None:
        if key not in EDITABLE_SCENE_FIELDS:
            raise KeyError(f"scene field {key!r} is not editable in this workspace")
        self._buffer[key] = value

    def entries(self) -> list[dict[str, Any]]:
        entries = self._buffer.get("entries")
        return entries if isinstance(entries, list) else []

    @staticmethod
    def is_text_entry(entry: dict[str, Any]) -> bool:
        return entry.get("kind") == TEXT_ENTRY_KIND

    def entry_text(self, entry_id: str) -> str:
        for entry in self.entries():
            if entry.get("entry_id") == entry_id and self.is_text_entry(entry):
                return str(entry.get("text") or "")
        raise KeyError(f"no editable text entry {entry_id!r}")

    def set_entry_text(self, entry_id: str, text: str) -> None:
        for entry in self.entries():
            if entry.get("entry_id") == entry_id and self.is_text_entry(entry):
                entry["text"] = text
                return
        raise KeyError(f"no editable text entry {entry_id!r}")

    def body_for_save(self) -> dict[str, Any]:
        """Complete intended body; unsupported content preserved verbatim."""
        return copy.deepcopy(self._buffer)

    def mark_saved(self) -> None:
        """Snapshot the current buffer as the new clean baseline."""
        self._original = copy.deepcopy(self._buffer)
