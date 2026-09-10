#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Character PUBLIC PROFILE -- the editable, editorial, user-facing presentation
layer for a companion character.

Architectural boundary (do not blur):

* Accepted Character Package  = who the character actually is for the runtime.
* CharacterLocalSnapshot      = the visual identity / reference authority.
* CharacterPublicProfile      = what the PRODUCT chooses to show a user.

Editing a public profile (display name, short/long description, ordered
sections, ordered public media, section/media visibility) NEVER mutates the
Accepted Package, runtime personality, relationship / psychology state, Memory,
the local visual snapshot, or any CRP reconstruction artefact. A public profile
is curated editorial content only -- it must never carry CRP R1-R8 data, claim
ids, evidence, prompts, package/snapshot hashes, provider config, numeric
relationship / psychology state, Memory, conversation history, credentials, or
filesystem paths.

Precedence: a profile persisted through :class:`CharacterPublicProfileStore`
(the seam a future Admin Studio writes) overrides the built-in restrained
default. When nothing is persisted the default is returned with
``is_fallback=True`` so the product can label it honestly.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Tuple

PROFILE_SCHEMA_VERSION = "companion_public_profile/0.1"

MEDIA_IMAGE = "image"
MEDIA_VIDEO = "video"
_MEDIA_TYPES = (MEDIA_IMAGE, MEDIA_VIDEO)

#: A card short description is one line of editorial copy, never the long text.
SHORT_DESCRIPTION_MAX = 240
SECTION_TITLE_MAX = 120
SECTION_BODY_MAX = 8000
LONG_DESCRIPTION_MAX = 20000
MEDIA_TITLE_MAX = 200
MAX_SECTIONS = 24
MAX_MEDIA = 60

_PROFILES_DIRNAME = "character_profiles"
_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

#: Transport-safe media reference prefixes. ``characters/`` mirrors the existing
#: static portrait convention (``apps/.../public/characters/<id>/...``);
#: ``images/`` mirrors the existing generated-image serving ref
#: (``ImageJobService`` result_ref, served by ``/api/companion/image-file/``).
_SAFE_MEDIA_PREFIXES = ("characters/", "images/")
_URL_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")


class PublicProfileError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


# ---------------------------------------------------------------------------
# safe-reference helpers
# ---------------------------------------------------------------------------
def is_safe_media_ref(ref: Any) -> bool:
    """True only for a relative, traversal-free ref under a known public root.

    Rejects absolute paths, drive-qualified paths (``C:/...``), UNC / backslash
    paths, ``..`` segments, and any URL scheme (``http:``, ``file:``, ``data:``…).
    """
    if not isinstance(ref, str) or not ref.strip():
        return False
    value = ref.strip()
    if value.startswith(("/", "\\")) or "\\" in value:
        return False
    if _URL_SCHEME_RE.match(value):
        return False
    parts = value.split("/")
    if any(p in ("", ".", "..") for p in parts):
        return False
    return value.startswith(_SAFE_MEDIA_PREFIXES)


def _clean(value: Any, limit: int) -> str:
    return str(value).strip()[:limit] if isinstance(value, str) else ""


def _one_line(value: Any, limit: int) -> str:
    return re.sub(r"\s+", " ", str(value)).strip()[:limit] if isinstance(value, str) else ""


# ---------------------------------------------------------------------------
# immutable model
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ProfileSection:
    section_id: str
    title: str
    body: str
    visible: bool = True

    def validate(self) -> None:
        if not _ID_RE.match(self.section_id or ""):
            raise PublicProfileError("invalid_profile", f"bad section_id {self.section_id!r}")
        if not (self.title or "").strip():
            raise PublicProfileError("invalid_profile", "a profile section needs a title")

    def to_dict(self) -> dict:
        return {
            "sectionId": self.section_id,
            "title": self.title,
            "body": self.body,
            "visible": self.visible,
        }

    @classmethod
    def from_dict(cls, data: Any) -> "ProfileSection":
        if not isinstance(data, dict):
            raise PublicProfileError("invalid_profile", "section must be an object")
        return cls(
            section_id=_clean(data.get("sectionId"), 64),
            title=_one_line(data.get("title"), SECTION_TITLE_MAX),
            body=_clean(data.get("body"), SECTION_BODY_MAX),
            visible=bool(data.get("visible", True)),
        )


@dataclass(frozen=True)
class ProfileMedia:
    media_id: str
    media_type: str
    source_ref: str
    thumbnail_ref: Optional[str] = None
    title: Optional[str] = None
    visible: bool = True

    def validate(self) -> None:
        if not _ID_RE.match(self.media_id or ""):
            raise PublicProfileError("invalid_profile", f"bad media_id {self.media_id!r}")
        if self.media_type not in _MEDIA_TYPES:
            raise PublicProfileError("invalid_profile", f"bad media_type {self.media_type!r}")
        if not is_safe_media_ref(self.source_ref):
            raise PublicProfileError("unsafe_media_ref", f"unsafe media source_ref {self.source_ref!r}")
        if self.thumbnail_ref is not None and not is_safe_media_ref(self.thumbnail_ref):
            raise PublicProfileError("unsafe_media_ref", f"unsafe media thumbnail_ref {self.thumbnail_ref!r}")

    def to_dict(self) -> dict:
        return {
            "mediaId": self.media_id,
            "mediaType": self.media_type,
            "sourceRef": self.source_ref,
            "thumbnailRef": self.thumbnail_ref,
            "title": self.title,
            "visible": self.visible,
        }

    @classmethod
    def from_dict(cls, data: Any) -> "ProfileMedia":
        if not isinstance(data, dict):
            raise PublicProfileError("invalid_profile", "media must be an object")
        thumb = data.get("thumbnailRef")
        title = data.get("title")
        return cls(
            media_id=_clean(data.get("mediaId"), 64),
            media_type=_clean(data.get("mediaType"), 16),
            source_ref=_clean(data.get("sourceRef"), 512),
            thumbnail_ref=_clean(thumb, 512) or None if thumb is not None else None,
            title=_one_line(title, MEDIA_TITLE_MAX) or None if title is not None else None,
            visible=bool(data.get("visible", True)),
        )


@dataclass(frozen=True)
class CharacterPublicProfile:
    schema_version: str
    character_id: str
    display_name: str
    short_description: str
    long_description: str = ""
    sections: Tuple[ProfileSection, ...] = ()
    media: Tuple[ProfileMedia, ...] = ()
    primary_media_id: Optional[str] = None
    #: True when no author/admin profile is persisted yet (restrained default).
    is_fallback: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "sections", tuple(self.sections))
        object.__setattr__(self, "media", tuple(self.media))

    # -- derived -----------------------------------------------------------
    @property
    def has_detailed_profile(self) -> bool:
        return bool(self.long_description.strip() or any(s.visible for s in self.sections))

    def visible_sections(self) -> Tuple[ProfileSection, ...]:
        return tuple(s for s in self.sections if s.visible)

    def visible_media(self) -> Tuple[ProfileMedia, ...]:
        return tuple(m for m in self.media if m.visible)

    # -- validation ------------------------------------------------------
    def validate(self) -> None:
        if not _ID_RE.match(self.character_id or ""):
            raise PublicProfileError("invalid_profile", f"bad character_id {self.character_id!r}")
        if not (self.display_name or "").strip():
            raise PublicProfileError("invalid_profile", "display_name is required")
        if "\n" in self.short_description or len(self.short_description) > SHORT_DESCRIPTION_MAX:
            raise PublicProfileError("invalid_profile", "short_description must be a single bounded line")
        if len(self.long_description) > LONG_DESCRIPTION_MAX:
            raise PublicProfileError("invalid_profile", "long_description exceeds the maximum length")
        if len(self.sections) > MAX_SECTIONS or len(self.media) > MAX_MEDIA:
            raise PublicProfileError("invalid_profile", "too many sections or media items")
        seen_sections: set[str] = set()
        for s in self.sections:
            s.validate()
            if s.section_id in seen_sections:
                raise PublicProfileError("invalid_profile", f"duplicate section_id {s.section_id!r}")
            seen_sections.add(s.section_id)
        seen_media: set[str] = set()
        for m in self.media:
            m.validate()
            if m.media_id in seen_media:
                raise PublicProfileError("invalid_profile", f"duplicate media_id {m.media_id!r}")
            seen_media.add(m.media_id)
        if self.primary_media_id is not None and self.primary_media_id not in seen_media:
            raise PublicProfileError("invalid_profile", "primary_media_id is not one of the media items")

    def to_dict(self) -> dict:
        return {
            "schemaVersion": self.schema_version,
            "characterId": self.character_id,
            "displayName": self.display_name,
            "shortDescription": self.short_description,
            "longDescription": self.long_description,
            "sections": [s.to_dict() for s in self.sections],
            "media": [m.to_dict() for m in self.media],
            "primaryMediaId": self.primary_media_id,
            "isFallback": self.is_fallback,
        }

    @classmethod
    def from_dict(cls, data: Any, *, is_fallback: bool = False) -> "CharacterPublicProfile":
        if not isinstance(data, dict):
            raise PublicProfileError("invalid_profile", "profile must be an object")
        primary = data.get("primaryMediaId")
        return cls(
            schema_version=str(data.get("schemaVersion") or PROFILE_SCHEMA_VERSION),
            character_id=_clean(data.get("characterId"), 64),
            display_name=_one_line(data.get("displayName"), 200),
            short_description=_one_line(data.get("shortDescription"), SHORT_DESCRIPTION_MAX),
            long_description=_clean(data.get("longDescription"), LONG_DESCRIPTION_MAX),
            sections=tuple(ProfileSection.from_dict(s) for s in (data.get("sections") or [])),
            media=tuple(ProfileMedia.from_dict(m) for m in (data.get("media") or [])),
            primary_media_id=_clean(primary, 64) or None if primary is not None else None,
            is_fallback=is_fallback,
        )


# ---------------------------------------------------------------------------
# restrained built-in default (no invented biography)
# ---------------------------------------------------------------------------
#: Owner-approved detailed editorial copy does not exist yet. Until Admin Studio
#: publishes one, only a short, non-committal line is shown. The detail body is
#: deliberately absent (empty long_description, no sections).
_KIRA_FALLBACK_SHORT = "Тёплая, вдумчивая собеседница для неспешных разговоров."


def default_profile(character_id: str, *, display_name: str) -> CharacterPublicProfile:
    cid = (character_id or "").strip()
    short = _KIRA_FALLBACK_SHORT if cid.lower() == "kira" else ""
    return CharacterPublicProfile(
        schema_version=PROFILE_SCHEMA_VERSION,
        character_id=cid,
        display_name=(display_name or cid).strip(),
        short_description=short,
        long_description="",
        sections=(),
        media=(),
        primary_media_id=None,
        is_fallback=True,
    )


# ---------------------------------------------------------------------------
# persistence seam (the surface a future Admin Studio writes)
# ---------------------------------------------------------------------------
class CharacterPublicProfileStore:
    """Reads / writes one small additive JSON file per character under
    ``<data_root>/character_profiles/<character_id>.json``. No SQLite, no
    coupling to the accepted package / runtime / snapshot / memory."""

    def __init__(self, data_root: Path) -> None:
        self._root = Path(data_root) / _PROFILES_DIRNAME

    def _path(self, character_id: str) -> Path:
        if not _ID_RE.match(character_id or ""):
            raise PublicProfileError("invalid_profile", f"bad character_id {character_id!r}")
        return self._root / f"{character_id}.json"

    def has_persisted(self, character_id: str) -> bool:
        return self._path(character_id).is_file()

    def load(self, character_id: str, *, display_name: str) -> CharacterPublicProfile:
        """Persisted profile if one exists and is valid; otherwise the restrained
        default (``is_fallback=True``). A malformed persisted file fails closed to
        the default -- a broken edit never removes the character from the UI."""
        path = self._path(character_id)
        if path.is_file():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                profile = CharacterPublicProfile.from_dict(raw, is_fallback=False)
                # never trust the file's id/name over the catalog's
                profile = _rebind(profile, character_id=character_id, display_name_hint=display_name)
                profile.validate()
                return profile
            except (json.JSONDecodeError, OSError, PublicProfileError):
                pass
        return default_profile(character_id, display_name=display_name)

    def save(self, profile: CharacterPublicProfile) -> CharacterPublicProfile:
        """Atomic write of an author/admin profile. Validates first; stamps
        ``is_fallback=False``."""
        stored = _rebind(profile, character_id=profile.character_id,
                         display_name_hint=profile.display_name, is_fallback=False)
        stored.validate()
        self._root.mkdir(parents=True, exist_ok=True)
        path = self._path(stored.character_id)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(stored.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)
        return stored

    def delete(self, character_id: str) -> bool:
        path = self._path(character_id)
        if path.is_file():
            path.unlink()
            return True
        return False


def _rebind(
    profile: CharacterPublicProfile,
    *,
    character_id: str,
    display_name_hint: str,
    is_fallback: Optional[bool] = None,
) -> CharacterPublicProfile:
    return CharacterPublicProfile(
        schema_version=profile.schema_version or PROFILE_SCHEMA_VERSION,
        character_id=character_id,
        display_name=(profile.display_name or display_name_hint or character_id).strip(),
        short_description=profile.short_description,
        long_description=profile.long_description,
        sections=profile.sections,
        media=profile.media,
        primary_media_id=profile.primary_media_id,
        is_fallback=profile.is_fallback if is_fallback is None else is_fallback,
    )
