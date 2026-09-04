#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scene Image Test App v0 -- thin offline orchestration CLI.

Orchestrates the existing backend pipeline end-to-end for a single profile:

    profile JSON
    -> Scenario Schema V2 fixture (in-memory cast override)
    -> ASS import / Location Canon / Scene Interpretation / MediaPlan /
       PromptPackage
    -> controlled Reference Library import (SHA-gated, exact configured set)
    -> ReferenceBundle from the Library (with prompt aliases)
    -> provider-neutral preview (--preview) or a gated single live call
       (--generate, NOT authorized in this task)

This module contains NO domain logic, NO alternate service implementations, and
NO HTTP of its own. It reuses the existing services exclusively. --preview
performs ZERO network I/O.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

# Make ``services``/``tools`` importable when this script is run directly.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from services.ass import import_scene  # noqa: E402
from services.character_canon_bridge import (  # noqa: E402
    SNAPSHOT_SCHEMA_VERSION,
    CharacterCanonSnapshot,
    Provenance,
    compute_content_hash,
)
from services.character_visual_conditioning import (  # noqa: E402
    build_reference_bundle_from_library,
    build_reference_map,
    generate_conditioned_image_from_bundle,
    reference_inputs_from_bundle,
    validate_reference_bundle_integrity,
)
from services.location_canon import load_location  # noqa: E402
from services.mediaplan import MediaItem, MediaKind, build_mediaplan  # noqa: E402
from services.prompt_composer import build_prompt_package  # noqa: E402
from services.reference_library import (  # noqa: E402
    IMPORTED,
    NO_OP_DUPLICATE,
    NO_OP_EXISTING_ASSET,
    ReferenceLibraryError,
    compute_sha256,
    default_manifest_path,
    import_reference,
    load_manifest,
)
from services.scene_interpretation import build_scene_interpretation_artifact  # noqa: E402
from services.scene_text_interpreter import (  # noqa: E402
    FixtureProposer,
    SceneStillPlan,
    SceneTextInterpreterError,
    interpret_scene_text,
    load_scene_still_plan,
)
from tools.reference_selector import (  # noqa: E402
    CatalogError,
    SelectionError,
    load_semantic_catalog,
    select_references,
)

# ---------------------------------------------------------------------------
# Application constants (owner-ratified defaults for this test app only).
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "gpt-image-2"
DEFAULT_SIZE = "1024x1024"
DEFAULT_QUALITY = "medium"

LIVE_ENV_VAR = "SCENE_IMAGE_TEST_LIVE"
API_KEY_ENV_VAR = "OPENAI_API_KEY"

PROFILES_DIR_REL = "authoring/scene_image_test_profiles"
PHYSICAL_PROFILES_REL = "authoring/scene_image_test_profiles/physical_profiles.json"
CATALOG_REL = "authoring/reference_library/REFERENCE_SEMANTIC_CATALOG.json"

# Raw-scene-text mode reuses one generic structured fixture only where the
# existing Profile/orchestrate path requires a Scenario Schema V2 scene. The
# in-memory cast_override remaps the placeholder cast to the resolved
# characters; the resolved location_id is passed explicitly to the ASS
# importer. No second scenario system is introduced.
SCENE_TEXT_GENERIC_FIXTURE_REL = (
    "tests/fixtures/scene_image_test_app/GENERIC_2CHAR.v2.json"
)
SCENE_TEXT_GENERIC_SCENE_ID = "SC_900"
SCENE_TEXT_GENERIC_BRANCH_ID = "B1"
SCENE_TEXT_GENERIC_CAST = ("KIRA", "SERGEY")

# Dedicated gate for a LIVE semantic (LLM) interpretation. This is SEPARATE
# from the image-generation gate (LIVE_ENV_VAR) on purpose: the semantic model
# may be live while the image provider stays disabled.
SEMANTIC_LIVE_ENV_VAR = "SCENE_TEXT_INTERPRETER_LIVE"
DEEPSEEK_API_KEY_ENV_VAR = "DEEPSEEK_API_KEY"

OUTPUT_ROOT = Path(
    "C:/DEV/Narrative/LOCAL_STORAGE/generated_media_smokes/SCENE_IMAGE_TEST_APP"
)


def _output_filename(profile_id: str) -> str:
    """Return a safe, deterministic output filename for a profile id.

    ``SC_004_MARINA_MAKSIM`` -> ``sc_004_marina_maksim_image_01.png``.
    """
    safe = "".join(ch.lower() if ch.isalnum() else "_" for ch in profile_id)
    return f"{safe}_image_01.png"

# In-memory cast-override snapshots are synthetic: the real Canon for the
# effective cast is in ``CONTROL_TESTS_APPROVED`` status, which the Canon bridge
# does not (yet) recognize. ``APPROVED_AS_TEST`` is the closest KNOWN status and
# is honest for a test app (it yields production_eligible=False, which is
# correct -- this is a test, not a production render).
IN_MEMORY_SNAPSHOT_STATUS = "APPROVED_AS_TEST"

# Generic youth/family safety tokens (case-insensitive). These also guard the
# ANDREY_JUNIOR relationship without hardcoding any single character. Raw
# configured internal ids are tested dynamically against the profile cast.
_FORBIDDEN_EXACT_SUBSTRINGS = ("father-son", "father_son")
_FORBIDDEN_WORDS = ("junior", "son", "boy", "teen")


# ---------------------------------------------------------------------------
# Errors (fail closed).
# ---------------------------------------------------------------------------


class SceneImageTestAppError(Exception):
    """Base error for the thin test app."""


class ProfileError(SceneImageTestAppError):
    """Profile JSON is missing or invalid."""


class ReferenceShaMismatchError(SceneImageTestAppError):
    """A configured source file's recomputed SHA-256 does not match expected."""


class ReferenceConflictError(SceneImageTestAppError):
    """A configured asset_id already exists with conflicting bytes/ownership."""


class GateFailureError(SceneImageTestAppError):
    """One or more offline gates failed."""


# ---------------------------------------------------------------------------
# Profile model.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReferenceSpec:
    character_id: str
    asset_id: str
    source_path: str
    expected_sha256: str
    role: str


class Profile:
    """Parsed profile (plain read-only value object)."""

    def __init__(self, data: Mapping[str, Any]):
        if not isinstance(data, Mapping):
            raise ProfileError("profile root must be an object")

        self.profile_id = _require_str(data, "profile_id")
        self.scene_id = _require_str(data, "scene_id")
        self.branch_id = _require_str(data, "branch_id")
        self.location_id = _require_str(data, "location_id")
        self.fixture_ref = _require_str(data, "fixture_ref")
        self.media_item_id = _require_str(data, "media_item_id")
        self.scene_intent = _require_str(data, "scene_intent")
        self.visual_goal = _require_str(data, "visual_goal")

        cast_override = data.get("cast_override")
        if not isinstance(cast_override, Mapping) or not cast_override:
            raise ProfileError("cast_override must be a non-empty object")
        self.cast_override: dict[str, str] = {}
        for src, dst in cast_override.items():
            if not isinstance(src, str) or not src:
                raise ProfileError("cast_override keys must be non-empty strings")
            if not isinstance(dst, str) or not dst:
                raise ProfileError("cast_override values must be non-empty strings")
            self.cast_override[src] = dst

        prompt_aliases = data.get("prompt_aliases")
        if not isinstance(prompt_aliases, Mapping):
            raise ProfileError("prompt_aliases must be an object")
        self.prompt_aliases: dict[str, str] = {}
        for internal, alias in prompt_aliases.items():
            if not isinstance(internal, str) or not internal:
                raise ProfileError("prompt_aliases keys must be non-empty strings")
            if not isinstance(alias, str) or not alias.strip():
                raise ProfileError("prompt_aliases values must be non-empty strings")
            self.prompt_aliases[internal] = alias

        effective = set(self.cast_override.values())
        if set(self.prompt_aliases.keys()) != effective:
            raise ProfileError(
                "prompt_aliases keys must equal the effective cast ids "
                f"(got {sorted(self.prompt_aliases)} vs {sorted(effective)})"
            )

        scene_tags = data.get("scene_tags")
        if scene_tags is None:
            scene_tags = []
        if not isinstance(scene_tags, list) or not all(
            isinstance(t, str) and t.strip() for t in scene_tags
        ):
            raise ProfileError("scene_tags must be a list of non-empty strings")
        self.scene_tags: tuple[str, ...] = tuple(scene_tags)

        refs = data.get("references")
        if refs is None:
            self.mode = "auto"
            self.references: tuple[ReferenceSpec, ...] = ()
        elif isinstance(refs, list):
            if not refs:
                raise ProfileError(
                    "references must not be empty when present "
                    "(omit references to use auto mode)"
                )
            self.mode = "explicit"
            self.references = tuple(
                ReferenceSpec(
                    character_id=_require_str(r, "character_id", prefix=f"references[{i}]."),
                    asset_id=_require_str(r, "asset_id", prefix=f"references[{i}]."),
                    source_path=_require_str(r, "source_path", prefix=f"references[{i}]."),
                    expected_sha256=_require_str(
                        r, "expected_sha256", prefix=f"references[{i}]."
                    ),
                    role=_require_str(r, "role", prefix=f"references[{i}]."),
                )
                for i, r in enumerate(refs)
                if isinstance(r, Mapping)
            )
            if len(self.references) != len(refs):
                raise ProfileError("references entries must all be objects")

            for spec in self.references:
                if spec.character_id not in effective:
                    raise ProfileError(
                        f"reference {spec.asset_id!r} character_id "
                        f"{spec.character_id!r} is not an effective cast id"
                    )
                if not _is_sha256(spec.expected_sha256):
                    raise ProfileError(
                        f"reference {spec.asset_id!r} expected_sha256 is not a valid sha256"
                    )
        else:
            raise ProfileError("references must be an array when present")

    @property
    def characters_in_frame(self) -> tuple[str, ...]:
        """Effective internal character ids, in cast_override order."""
        return tuple(self.cast_override.values())

    @property
    def roles_by_asset_id(self) -> dict[str, tuple[str, ...]]:
        return {spec.asset_id: (spec.role,) for spec in self.references}


def _require_str(data: Mapping[str, Any], key: str, prefix: str = "") -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ProfileError(f"{prefix}{key}: required non-empty string")
    return value


def _is_sha256(value: str) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(c in "0123456789abcdef" for c in value)
    )


def load_profile(profile_id: str, profiles_dir: Path) -> Profile:
    """Load and validate one profile JSON file by ``profile_id``."""
    path = Path(profiles_dir) / f"{profile_id}.json"
    if not path.exists():
        raise ProfileError(f"unknown profile: {profile_id!r}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive
        raise ProfileError(f"invalid profile JSON: {exc}") from exc
    profile = Profile(data)
    if profile.profile_id != profile_id:
        raise ProfileError(
            f"profile_id mismatch: requested {profile_id!r} but file declares "
            f"{profile.profile_id!r}"
        )
    return profile


# ---------------------------------------------------------------------------
# In-memory cast override + snapshots.
# ---------------------------------------------------------------------------


def apply_cast_override(value: Any, cast_override: Mapping[str, str]) -> Any:
    """Recursively replace internal source ids with effective ids (in memory).

    Returns fresh data; the input is never mutated. Only string values are
    rewritten (never dict keys), and source ids never overlap so replacement
    order is irrelevant.
    """
    if isinstance(value, str):
        result = value
        for src, dst in cast_override.items():
            result = result.replace(src, dst)
        return result
    if isinstance(value, dict):
        return {
            key: apply_cast_override(item, cast_override) for key, item in value.items()
        }
    if isinstance(value, list):
        return [apply_cast_override(item, cast_override) for item in value]
    return value


def build_in_memory_snapshot(
    character_id: str, *, profile_id: str
) -> CharacterCanonSnapshot:
    """Build a synthetic frozen snapshot for the effective cast (in memory).

    The snapshot carries a KNOWN status and empty references so the Scene
    Interpretation contract is satisfied without re-reading Character Canon and
    without leaking any raw internal identity/paths into the prompt.
    """
    provenance = Provenance(
        source_kind="scene_image_test_app_in_memory_cast_override",
        source_ref="scene_image_test_app:in_memory_cast_override",
        source_hash=compute_content_hash(
            {"profile_id": profile_id, "character_id": character_id}
        ),
    )
    provisional = CharacterCanonSnapshot(
        schema_version=SNAPSHOT_SCHEMA_VERSION,
        character_id=character_id,
        status=IN_MEMORY_SNAPSHOT_STATUS,
        references=(),
        content_hash="",
        provenance=provenance,
        active_version=None,
    )
    content_hash = compute_content_hash(provisional.semantic_payload())
    return dataclasses.replace(provisional, content_hash=content_hash)


# ---------------------------------------------------------------------------
# Controlled reference preparation (SHA gate + RL2 import/reuse).
# ---------------------------------------------------------------------------


def prepare_references(
    profile: Profile, *, repo_root: Path, manifest_path: Path
) -> tuple[dict[str, Any], list[str], list[str], int]:
    """Prepare the exact configured reference set into the Reference Library.

    For every configured reference (never scanning, never importing any file
    outside the profile): recompute the source SHA and fail closed on mismatch,
    reuse an existing matching asset, or import through RL2. Returns
    ``(records_by_character, imported_ids, reused_ids, manifest_count)``.
    """
    records = load_manifest(manifest_path) if manifest_path.exists() else []
    by_asset_id: dict[str, Any] = {r.asset_id: r for r in records}

    imported_ids: list[str] = []
    reused_ids: list[str] = []
    prepared: list[tuple[ReferenceSpec, Any]] = []

    for spec in profile.references:
        source = Path(spec.source_path)
        try:
            data = source.read_bytes()
        except OSError as exc:
            raise ReferenceShaMismatchError(
                f"cannot read source for {spec.asset_id!r}: {exc}"
            ) from exc

        actual_sha = compute_sha256(data)
        if actual_sha != spec.expected_sha256:
            raise ReferenceShaMismatchError(
                f"source SHA mismatch for {spec.asset_id!r}: "
                f"got {actual_sha}, expected {spec.expected_sha256}"
            )

        existing = by_asset_id.get(spec.asset_id)
        if existing is not None:
            if (
                existing.sha256 == spec.expected_sha256
                and existing.character_id == spec.character_id
            ):
                reused_ids.append(spec.asset_id)
                record = existing
            else:
                raise ReferenceConflictError(
                    f"asset_id {spec.asset_id!r} already exists with conflicting "
                    "bytes or ownership"
                )
        else:
            try:
                result = import_reference(
                    source,
                    repo_root=repo_root,
                    manifest_path=manifest_path,
                    asset_id=spec.asset_id,
                    character_id=spec.character_id,
                    collection="scene_image_test_app",
                )
            except ReferenceLibraryError as exc:
                raise ReferenceConflictError(
                    f"import failed for {spec.asset_id!r}: {exc}"
                ) from exc
            if result.status == IMPORTED:
                imported_ids.append(spec.asset_id)
            elif result.status in (NO_OP_EXISTING_ASSET, NO_OP_DUPLICATE):
                reused_ids.append(spec.asset_id)
            else:  # pragma: no cover - defensive
                raise ReferenceConflictError(
                    f"unexpected import status for {spec.asset_id!r}: {result.status}"
                )
            record = result.record
            by_asset_id[spec.asset_id] = record

        prepared.append((spec, record))

    records_by_character: dict[str, Any] = {}
    for cid in profile.characters_in_frame:
        records_by_character[cid] = [
            record for spec, record in prepared if spec.character_id == cid
        ]

    manifest_count = len(by_asset_id)
    return records_by_character, imported_ids, reused_ids, manifest_count


# ---------------------------------------------------------------------------
# Offline orchestration.
# ---------------------------------------------------------------------------


@dataclass
class RunResult:
    """Everything produced by one offline orchestration run."""

    profile: Profile
    source: dict[str, Any]
    ass: Any
    location: Any
    interpretation: Any
    mediaplan: Any
    prompt_package: Any
    prompt_item: Any
    bundle: Any
    reference_map: str
    attachment_filenames: tuple[str, ...]
    raw_prompt_text: str
    final_prompt_text: str
    final_prompt_hash: str
    imported_asset_ids: tuple[str, ...]
    reused_asset_ids: tuple[str, ...]
    manifest_record_count: int
    selection_mode: str
    effective_scene_tags: tuple[str, ...]
    selected_assets_by_char: dict[str, tuple[tuple[str, str], ...]]
    provider_exposure: bool
    gates: dict[str, bool]

    @property
    def all_gates_pass(self) -> bool:
        return bool(self.gates) and all(self.gates.values())


def _apply_prompt_aliases(text: str, prompt_aliases: Mapping[str, str]) -> str:
    result = text
    # Longest internal id first to avoid any partial-overlap edge cases.
    for internal, alias in sorted(
        prompt_aliases.items(), key=lambda kv: (-len(kv[0]), kv[0])
    ):
        result = result.replace(internal, alias)
    return result


def _has_forbidden_tokens(text: str, internal_ids: Sequence[str]) -> bool:
    """Return True if ``text`` exposes a configured internal id or a generic
    youth/family token.

    - Each configured internal id is matched exactly (case-sensitive) so a
      case-only alias such as ``Marina`` for ``MARINA`` is not a false positive.
    - Father-son relationship forms are matched case-insensitively as substrings.
    - Single-word youth tokens are matched whole-word (letters/digits delimit
      the word) so benign substrings such as ``json`` never false-positive on
      ``son``.
    """
    for cid in internal_ids:
        if cid in text:
            return True
    lowered = text.lower()
    for token in _FORBIDDEN_EXACT_SUBSTRINGS:
        if token in lowered:
            return True
    for word in _FORBIDDEN_WORDS:
        if re.search(rf"(?<![a-z0-9]){re.escape(word)}(?![a-z0-9])", lowered):
            return True
    return False


def has_provider_exposure(
    *,
    prompt_text: str,
    reference_map: str,
    filenames: Sequence[str],
    internal_ids: Sequence[str] = (),
) -> bool:
    """Return True if ANY provider-facing payload leaks a configured internal id
    or a generic youth/family token (case-insensitive for the tokens)."""
    return (
        _has_forbidden_tokens(prompt_text, internal_ids)
        or _has_forbidden_tokens(reference_map, internal_ids)
        or any(_has_forbidden_tokens(name, internal_ids) for name in filenames)
    )


def _gender_label(role: str) -> str:
    """Return a concise adult-gender label derived from a role string."""
    r = role.lower()
    if "female" in r or "woman" in r:
        base = "woman"
    elif "male" in r or "man" in r:
        base = "man"
    else:
        return role
    if "mature" in r:
        return f"mature adult {base}"
    return f"adult {base}"


def _format_weight(weight_kg: Any) -> str:
    if weight_kg is None:
        return ""
    if float(weight_kg).is_integer():
        return f"{int(weight_kg)} kg"
    return f"{weight_kg} kg"


def _height_line(prof: Mapping[str, Any]) -> str:
    height_cm = prof.get("height_cm")
    if height_cm is not None:
        prefix = "approximately " if bool(prof.get("height_is_approx", False)) else ""
        return f"{prefix}{height_cm} cm"
    return prof.get("height_direction") or ""


def _load_physical_profiles(repo_root: Path) -> dict:
    """Load the vendored physical profiles snapshot (empty if absent)."""
    path = Path(repo_root) / PHYSICAL_PROFILES_REL
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    characters = data.get("characters")
    return characters if isinstance(characters, dict) else {}


def _render_relative_scale(
    characters_in_frame: Sequence[str],
    prompt_aliases: Mapping[str, str],
    physical_profiles: Mapping[str, Any],
) -> str:
    """Render the RELATIVE SCALE section (never inventing numbers)."""
    infos = []
    for cid in characters_in_frame:
        alias = prompt_aliases.get(cid, cid)
        prof = physical_profiles.get(cid) or {}
        infos.append((alias, prof.get("height_cm"), prof.get("height_direction")))
    if len(infos) < 2:
        return ""

    lines = ["RELATIVE SCALE", ""]
    (a_alias, a_h, a_dir), (b_alias, b_h, b_dir) = infos[0], infos[1]

    if a_h is not None and b_h is not None:
        taller, shorter = (a_alias, b_alias) if a_h >= b_h else (b_alias, a_alias)
        diff = abs(a_h - b_h)
        if diff >= 8:
            lines.append(f"{taller} is visibly taller than {shorter}.")
            lines.append(
                f"{taller} must appear substantially heavier, broader and more "
                f"massive than {shorter}."
            )
            lines.append("Preserve the strong body-size contrast in the same frame.")
            lines.append("Do not normalize their body sizes toward each other.")
        elif diff >= 3:
            lines.append(f"{taller} is somewhat taller than {shorter}.")
        else:
            lines.append(f"{taller} and {shorter} are of comparable height.")
    else:
        def _tallness(direction: Any) -> int:
            d = (direction or "").lower()
            if "very tall" in d or " tall" in d:
                return 2
            if "medium-tall" in d:
                return 1
            if any(w in d for w in ("short", "petite", "compact", "not tall")):
                return -1
            return 0

        ta, tb = _tallness(a_dir), _tallness(b_dir)
        if ta > tb:
            lines.append(f"{a_alias} appears taller than {b_alias}.")
        elif tb > ta:
            lines.append(f"{b_alias} appears taller than {a_alias}.")
        else:
            lines.append(
                "Relative height is not numerically specified for these characters."
            )

    return "\n".join(lines)


def _render_physical_block(
    characters_in_frame: Sequence[str],
    prompt_aliases: Mapping[str, str],
    physical_profiles: Mapping[str, Any],
) -> str:
    """Render the provider-facing physical identity + relative scale block.

    Uses only facts present in the snapshot, provider aliases only (never
    internal ids), and never style_direction / safety_rules / paths / SHAs.
    """
    if not characters_in_frame or not physical_profiles:
        return ""

    lines = ["CHARACTER PHYSICAL IDENTITY", ""]
    for cid in characters_in_frame:
        alias = prompt_aliases.get(cid, cid)
        prof = physical_profiles.get(cid) or {}
        if not prof:
            continue
        lines.append(f"{alias}:")
        role = prof.get("role") or ""
        if role:
            lines.append(f"- {_gender_label(role)}")
        hl = _height_line(prof)
        if hl:
            lines.append(f"- {hl}")
        weight_kg = prof.get("weight_kg")
        weight_direction = prof.get("weight_direction")
        if weight_kg is not None:
            lines.append(f"- {_format_weight(weight_kg)}")
        elif weight_direction:
            lines.append(f"- {weight_direction}")
        body = prof.get("body_direction")
        if body:
            lines.append(f"- {body}")
        lines.append("")

    relative = _render_relative_scale(
        characters_in_frame, prompt_aliases, physical_profiles
    )
    if relative:
        lines.append(relative)

    return "\n".join(lines).rstrip("\n")


def orchestrate(
    profile: Profile, *, repo_root: Path, manifest_path: Path
) -> RunResult:
    """Run the full offline pipeline and return the deterministic result."""
    fixture_path = Path(repo_root) / profile.fixture_ref
    try:
        source = json.loads(fixture_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ProfileError(f"cannot read fixture {profile.fixture_ref!r}: {exc}") from exc

    # 1. In-memory cast override (never mutates the fixture on disk).
    overridden = apply_cast_override(source, profile.cast_override)

    # 2. ASS import (explicit branch selection).
    ass = import_scene(
        overridden,
        ass_id=f"{profile.profile_id.lower()}_ass_v1",
        version=1,
        location_id=profile.location_id,
        source_ref=profile.fixture_ref,
        branch_id=profile.branch_id,
    )

    # 3. Location Canon.
    location = load_location(repo_root, profile.location_id)

    # 4. In-memory snapshots for the effective cast.
    snapshots = [
        build_in_memory_snapshot(cid, profile_id=profile.profile_id)
        for cid in profile.characters_in_frame
    ]

    # 5. Scene Interpretation -> MediaPlan -> PromptPackage.
    interpretation = build_scene_interpretation_artifact(
        ass=ass,
        location=location,
        character_snapshots=snapshots,
        interpretation_payload={"visual_goal": profile.scene_intent},
    )
    media_item = MediaItem(
        media_item_id=profile.media_item_id,
        media_kind=MediaKind.IMAGE,
        characters_in_frame=profile.characters_in_frame,
        planning_payload={"visual_goal": profile.visual_goal},
    )
    mediaplan = build_mediaplan(
        scene_interpretation=interpretation, media_items=(media_item,)
    )
    prompt_package = build_prompt_package(
        scene_interpretation=interpretation, mediaplan=mediaplan
    )
    prompt_item = prompt_package.prompt_items[0]

    # 6. Reference resolution: explicit import or automatic selection.
    if profile.mode == "explicit":
        records_by_character, imported_ids, reused_ids, manifest_count = (
            prepare_references(profile, repo_root=repo_root, manifest_path=manifest_path)
        )
        roles_by_asset_id = profile.roles_by_asset_id
        selected_assets_by_char = {
            cid: tuple(
                (spec.asset_id, spec.role)
                for spec in profile.references
                if spec.character_id == cid
            )
            for cid in profile.characters_in_frame
        }
    else:
        records = load_manifest(manifest_path) if manifest_path.exists() else []
        catalog_path = Path(repo_root) / CATALOG_REL
        catalog = load_semantic_catalog(catalog_path, records)
        records_by_character, roles_by_asset_id = select_references(
            profile.characters_in_frame,
            profile.location_id,
            profile.scene_tags,
            records,
            catalog,
        )
        imported_ids, reused_ids, manifest_count = [], [], len(records)
        selected_assets_by_char = {
            cid: tuple(
                (record.asset_id, roles_by_asset_id[record.asset_id][0])
                for record in records_by_character[cid]
            )
            for cid in profile.characters_in_frame
        }

    # 7. ReferenceBundle from the Library (provider-neutral, aliased).
    bundle = build_reference_bundle_from_library(
        records_by_character,
        characters_in_frame=profile.characters_in_frame,
        repo_root=repo_root,
        roles_by_asset_id=roles_by_asset_id,
        prompt_alias_by_character=profile.prompt_aliases,
    )
    validate_reference_bundle_integrity(bundle)

    reference_map = build_reference_map(bundle)
    inputs = reference_inputs_from_bundle(bundle)
    attachment_filenames = tuple(i.filename for i in inputs)

    # 8. Provider-facing prompt (internal ids aliased out, then physical block).
    raw_prompt_text = prompt_item.prompt_text
    aliased_prompt = _apply_prompt_aliases(raw_prompt_text, profile.prompt_aliases)
    physical_block = _render_physical_block(
        profile.characters_in_frame,
        profile.prompt_aliases,
        _load_physical_profiles(repo_root),
    )
    final_prompt_text = (
        aliased_prompt + "\n\n" + physical_block if physical_block else aliased_prompt
    )
    final_prompt_hash = hashlib.sha256(final_prompt_text.encode("utf-8")).hexdigest()

    # 9. Offline gates.
    refs_by_char = {
        g.character_id: len(g.references) for g in bundle.character_groups
    }
    _seen_tags: set[str] = set()
    _eff_tags: list[str] = []
    for _t in [profile.location_id] + list(profile.scene_tags):
        if _t not in _seen_tags:
            _seen_tags.add(_t)
            _eff_tags.append(_t)
    effective_scene_tags = tuple(_eff_tags)
    provider_exposure = has_provider_exposure(
        prompt_text=final_prompt_text,
        reference_map=reference_map,
        filenames=attachment_filenames,
        internal_ids=profile.characters_in_frame,
    )
    gates = {
        "scene_resolved": ass.scene_id == profile.scene_id,
        "branch_resolved": any(
            b.beat_id == f"{profile.branch_id}-b1" for b in ass.ordered_beats
        ),
        "location_resolved": location.location_id == profile.location_id,
        "cast_override_applied": {p.character_id for p in ass.participants}
        == set(profile.characters_in_frame),
        "reference_count_exact": (
            sum(refs_by_char.values()) == len(profile.references)
            if profile.mode == "explicit"
            else True
        ),
        "reference_group_count": len(bundle.character_groups)
        == len(profile.characters_in_frame),
        "reference_count_within_bounds": (
            all(2 <= refs_by_char[cid] <= 4 for cid in profile.characters_in_frame)
            if profile.mode == "auto"
            else all(refs_by_char[cid] == 4 for cid in profile.characters_in_frame)
        ),
        "bundle_valid": True,  # validate_reference_bundle_integrity already ran
        "prompt_package_built": len(prompt_package.prompt_items) == 1,
        "provider_exposure": not provider_exposure,
    }

    return RunResult(
        profile=profile,
        source=source,
        ass=ass,
        location=location,
        interpretation=interpretation,
        mediaplan=mediaplan,
        prompt_package=prompt_package,
        prompt_item=prompt_item,
        bundle=bundle,
        reference_map=reference_map,
        attachment_filenames=attachment_filenames,
        raw_prompt_text=raw_prompt_text,
        final_prompt_text=final_prompt_text,
        final_prompt_hash=final_prompt_hash,
        imported_asset_ids=tuple(imported_ids),
        reused_asset_ids=tuple(reused_ids),
        manifest_record_count=manifest_count,
        selection_mode=profile.mode,
        effective_scene_tags=effective_scene_tags,
        selected_assets_by_char=selected_assets_by_char,
        provider_exposure=provider_exposure,
        gates=gates,
    )


# ---------------------------------------------------------------------------
# Preview rendering (deterministic, zero network).
# ---------------------------------------------------------------------------


def format_preview(result: RunResult, *, model: str, size: str, quality: str) -> str:
    """Render a deterministic, concise preview for a RunResult."""
    p = result.profile
    lines: list[str] = []

    lines.append(f"PROFILE={p.profile_id}")
    lines.append(f"SCENE={p.scene_id}")
    lines.append(f"BRANCH={p.branch_id}")
    lines.append(f"LOCATION={p.location_id}")
    lines.append("")

    lines.append("CAST OVERRIDE")
    for src, dst in p.cast_override.items():
        lines.append(f"  {src} -> {dst}")
    lines.append("")

    lines.append("INTERNAL IDS")
    for cid in p.characters_in_frame:
        lines.append(f"  {cid}")
    lines.append("")

    lines.append("PROVIDER ALIASES")
    for internal, alias in p.prompt_aliases.items():
        lines.append(f"  {internal} -> {alias}")
    lines.append("")

    lines.append(f"REFERENCE_SELECTION_MODE={result.selection_mode.upper()}")
    if result.selection_mode == "auto":
        lines.append(f"EFFECTIVE_SCENE_TAGS={','.join(result.effective_scene_tags)}")
    lines.append("")

    if result.selection_mode == "explicit":
        lines.append("REFERENCE ASSET IDS")
        for spec in p.references:
            lines.append(f"  {spec.asset_id}")
        lines.append("")
    else:
        lines.append("SELECTED_REFERENCES:")
        for cid in p.characters_in_frame:
            lines.append(f"{cid}:")
            for asset_id, role in result.selected_assets_by_char.get(cid, ()):
                lines.append(f"  {asset_id} [{role}]")
        lines.append("")
        lines.append("REFERENCE_COUNT_BY_CHARACTER:")
        for cid in p.characters_in_frame:
            lines.append(f"{cid}={len(result.selected_assets_by_char.get(cid, ()))}")
        lines.append("")

    lines.append(f"REFERENCE BUNDLE HASH={result.bundle.content_hash}")
    lines.append(f"PROMPT PACKAGE HASH={result.prompt_package.content_hash}")
    lines.append(f"PROMPT ITEM HASH={result.prompt_item.content_hash}")
    lines.append(f"FINAL PROMPT HASH={result.final_prompt_hash}")
    lines.append("")

    lines.append("FINAL PROMPT TEXT")
    lines.append(result.final_prompt_text)
    lines.append("")

    lines.append("REFERENCE MAP")
    lines.append(result.reference_map)
    lines.append("")

    lines.append("ORDERED ATTACHMENT FILENAMES")
    for name in result.attachment_filenames:
        lines.append(f"  {name}")
    lines.append("")

    lines.append(f"MODEL DEFAULT={model}")
    lines.append(f"SIZE={size}")
    lines.append(f"QUALITY={quality}")
    lines.append("")

    exposure_line = "YES" if result.provider_exposure else "NO"
    lines.append(f"PROVIDER_INTERNAL_ID_EXPOSURE={exposure_line}")

    result_line = "PASS" if result.all_gates_pass else "FAIL"
    ready_line = "YES" if result.all_gates_pass else "NO"
    lines.append(f"DRY_RUN_RESULT={result_line}")
    lines.append(f"READY_FOR_LIVE_GENERATION={ready_line}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI.
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scene Image Test App v0 (offline orchestration)."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--profile", dest="profile_id", help="Existing scene image test profile id."
    )
    source.add_argument(
        "--scene-text",
        dest="scene_text",
        help=(
            "Ordinary scene prose. Interpreted (offline) into an in-memory AUTO "
            "profile via services.scene_text_interpreter."
        ),
    )
    source.add_argument(
        "--scene-file",
        dest="scene_file",
        help="Path to a UTF-8 file containing ordinary scene prose.",
    )
    source.add_argument(
        "--plan-file",
        dest="plan_file",
        help=(
            "Replay a previously emitted, validated SceneStillPlan JSON. Strict "
            "load + content_hash recompute + bridge revalidation; NO semantic "
            "call. Mutually exclusive with --scene-text/--scene-file/"
            "--proposal-fixture/--live-interpreter."
        ),
    )
    parser.add_argument(
        "--proposal-fixture",
        dest="proposal_fixture",
        help=(
            "Recorded interpreter proposal JSON (offline replay). Required with "
            "--scene-text/--scene-file unless --live-interpreter is used."
        ),
    )
    parser.add_argument(
        "--live-interpreter",
        dest="live_interpreter",
        action="store_true",
        help=(
            "Use the LIVE DeepSeek semantic proposer instead of a recorded "
            "fixture. Gated by SCENE_TEXT_INTERPRETER_LIVE=1 + DEEPSEEK_API_KEY. "
            "Never enables image generation."
        ),
    )
    parser.add_argument(
        "--emit-plan",
        dest="emit_plan",
        help="Optional path to write the validated SceneStillPlan JSON (scene-text mode).",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preview", action="store_true", help="Offline dry-run only.")
    mode.add_argument("--generate", action="store_true", help="Live call (gated).")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--size", default=DEFAULT_SIZE)
    parser.add_argument("--quality", default=DEFAULT_QUALITY)
    return parser


def _default_repo_root() -> Path:
    return _REPO_ROOT


def _default_profiles_dir(repo_root: Path) -> Path:
    return repo_root / PROFILES_DIR_REL


def format_still_plan_section(plan: SceneStillPlan, *, replay: bool = False) -> str:
    """Render a deterministic, auditable SCENE STILL PLAN section."""
    lines: list[str] = []
    lines.append("SCENE STILL PLAN")
    lines.append("RAW_TEXT_MODE=YES")
    lines.append(f"PLAN_REPLAY_MODE={'YES' if replay else 'NO'}")
    if replay:
        lines.append("SEMANTIC_PROVIDER_CALLS=0")
    lines.append(f"PLAN_STATUS={plan.status}")
    lines.append(
        f"SOURCE_LANGUAGE={plan.interpreter.get('source_language') or 'unknown'}"
    )
    lines.append(f"SOURCE_TEXT_HASH={plan.source_text_hash}")
    lines.append(f"PLAN_CONTENT_HASH={plan.content_hash}")
    lines.append(
        "INTERPRETER="
        f"{plan.interpreter.get('provider')}/{plan.interpreter.get('model')} "
        f"mock={plan.interpreter.get('mock')}"
    )
    lines.append(f"RESOLVED_CHARACTERS={','.join(plan.characters_in_frame)}")
    lines.append(f"RESOLVED_LOCATION={plan.location_id}")
    lines.append(f"RESOLVED_SCENE_TAGS={','.join(plan.scene_tags)}")
    lines.append("GROUNDING_VALID=YES")
    lines.append(
        "UNRESOLVED_ITEMS="
        + (",".join(plan.unresolved_items) if plan.unresolved_items else "none")
    )
    lines.append("CHARACTER_EVIDENCE:")
    for cid in plan.characters_in_frame:
        spans = plan.evidence["character_spans"].get(cid, ())
        lines.append(f"  {cid}: {' | '.join(spans)}")
    lines.append(f"LOCATION_EVIDENCE={plan.evidence['location_span']}")
    lines.append(f"STILL_CANDIDATE_COUNT={len(plan.still_candidates)}")
    lines.append("STILL_CANDIDATES:")
    for cand in plan.still_candidates:
        lines.append(
            f"  beat[{cand.beat_index}] score={cand.score} "
            f"tags={','.join(cand.rationale_tags)}"
        )
    real_llm = plan.interpreter.get("mock") is False
    lines.append(f"REAL_LLM_PROPOSER={'YES' if real_llm else 'NO'}")
    raw_sha = plan.interpreter.get("raw_response_sha256")
    if raw_sha:
        lines.append(f"RAW_RESPONSE_SHA256={raw_sha}")
    lines.append(f"CHOSEN_STILL_BEAT_INDEX={plan.chosen_still.beat_index}")
    lines.append(f"CHOSEN_STILL_EVIDENCE={plan.evidence['chosen_still_beat_span']}")
    lines.append("CHOSEN_STILL_VISUAL_GOAL")
    lines.append(plan.chosen_still.visual_goal)
    return "\n".join(lines)


def _build_live_scene_text_proposer():
    """Construct the LIVE DeepSeek semantic proposer, gated + fail-closed.

    Requires the dedicated semantic gate (never the image gate) and a present
    ``DEEPSEEK_API_KEY`` (presence only -- the value is never read here). The
    adapter itself never reads the key; the shared cloud transport does, via
    ``api_key_env``.
    """
    if os.environ.get(SEMANTIC_LIVE_ENV_VAR) != "1":
        raise ProfileError(
            f"{SEMANTIC_LIVE_ENV_VAR}=1 is required for --live-interpreter "
            "(this gate is separate from image generation)"
        )
    if not os.environ.get(DEEPSEEK_API_KEY_ENV_VAR):
        raise ProfileError(
            f"{DEEPSEEK_API_KEY_ENV_VAR} is required for --live-interpreter"
        )
    from tools.scene_text_llm_adapter import DeepSeekSceneTextProposer

    return DeepSeekSceneTextProposer()


def _profile_from_plan(plan: SceneStillPlan) -> Profile:
    """Bridge a validated SceneStillPlan to the existing in-memory AUTO-mode
    Profile. Identical shape whether the plan came from live interpretation or
    from a persisted replay. Never enumerates ``references[]``."""
    cif = plan.characters_in_frame
    if len(cif) != len(SCENE_TEXT_GENERIC_CAST):
        raise ProfileError(
            f"scene-text v0 requires exactly {len(SCENE_TEXT_GENERIC_CAST)} in-frame "
            f"characters; got {len(cif)}"
        )
    src_slug = plan.source_text_hash[:12]
    profile_data = {
        "profile_id": f"SCENE_TEXT_{src_slug.upper()}",
        "scene_id": SCENE_TEXT_GENERIC_SCENE_ID,
        "branch_id": SCENE_TEXT_GENERIC_BRANCH_ID,
        "location_id": plan.location_id,
        "fixture_ref": SCENE_TEXT_GENERIC_FIXTURE_REL,
        "media_item_id": f"scene_text_{src_slug}_image_01",
        "cast_override": {
            SCENE_TEXT_GENERIC_CAST[i]: cif[i] for i in range(len(cif))
        },
        "prompt_aliases": dict(plan.provider_alias_by_character),
        "scene_tags": list(plan.scene_tags),
        "scene_intent": plan.chosen_still.visual_goal,
        "visual_goal": plan.chosen_still.visual_goal,
        # NOTE: no "references" key -> AUTO reference selection.
    }
    return Profile(profile_data)


def profile_from_scene_text(
    raw_scene_text: str,
    *,
    repo_root: Path,
    proposal_fixture: Optional[Path] = None,
    proposer: Optional[object] = None,
) -> tuple[Profile, SceneStillPlan]:
    """Interpret ordinary scene prose into a validated plan and an in-memory
    AUTO-mode Profile that the existing ``orchestrate`` path consumes unchanged.

    Supply either ``proposal_fixture`` (offline replay) or an explicit
    ``proposer`` (e.g. the live DeepSeek adapter). The Profile never enumerates
    ``references[]``: the scene-aware AUTO reference selector stays authoritative.
    """
    if proposer is None:
        if proposal_fixture is None:
            raise ProfileError(
                "profile_from_scene_text requires proposal_fixture or proposer"
            )
        proposer = FixtureProposer(Path(proposal_fixture))
    plan = interpret_scene_text(
        raw_scene_text, repo_root=repo_root, proposer=proposer
    )
    return _profile_from_plan(plan), plan


def profile_from_plan_file(
    plan_file: Path, *, repo_root: Path
) -> tuple[Profile, SceneStillPlan]:
    """Replay a persisted, validated SceneStillPlan into the existing Profile.

    Strictly loads + hash-verifies + bridge-revalidates the plan. NEVER
    instantiates or calls a SceneTextProposer and makes NO semantic/network
    call.
    """
    plan = load_scene_still_plan(Path(plan_file), repo_root=repo_root)
    return _profile_from_plan(plan), plan


def _resolve_profile_and_plan(
    *,
    profile_id: Optional[str],
    scene_text: Optional[str],
    scene_file: Optional[str],
    proposal_fixture: Optional[str],
    live_interpreter: bool = False,
    plan_file: Optional[str] = None,
    repo_root: Path,
) -> tuple[Profile, Optional[SceneStillPlan]]:
    """Resolve a Profile from an existing profile id, ordinary prose, or a
    persisted SceneStillPlan replay."""
    if profile_id:
        return load_profile(profile_id, _default_profiles_dir(repo_root)), None

    if plan_file:
        if proposal_fixture or live_interpreter or scene_text or scene_file:
            raise ProfileError(
                "--plan-file is a self-contained replay; do not combine it with "
                "--scene-text/--scene-file/--proposal-fixture/--live-interpreter"
            )
        try:
            return profile_from_plan_file(Path(plan_file), repo_root=repo_root)
        except SceneTextInterpreterError as exc:
            raise ProfileError(f"plan replay failed: {exc}") from exc

    text = scene_text
    if scene_file is not None:
        try:
            text = Path(scene_file).read_text(encoding="utf-8")
        except OSError as exc:
            raise ProfileError(
                f"cannot read --scene-file {scene_file!r}: {exc}"
            ) from exc
    if not text or not text.strip():
        raise ProfileError("scene text is empty")

    if live_interpreter:
        proposer = _build_live_scene_text_proposer()
        try:
            return profile_from_scene_text(
                text, repo_root=repo_root, proposer=proposer
            )
        except SceneTextInterpreterError as exc:
            raise ProfileError(f"scene-text interpretation failed: {exc}") from exc

    if not proposal_fixture:
        raise ProfileError(
            "--proposal-fixture PATH is required with --scene-text/--scene-file "
            "(offline replay), or pass --live-interpreter for the gated live "
            "DeepSeek proposer"
        )
    try:
        return profile_from_scene_text(
            text, repo_root=repo_root, proposal_fixture=Path(proposal_fixture)
        )
    except SceneTextInterpreterError as exc:
        raise ProfileError(f"scene-text interpretation failed: {exc}") from exc


def _run_orchestrate(
    profile: Profile, *, repo_root: Path, manifest_path: Path
) -> tuple[int, Optional[RunResult]]:
    try:
        result = orchestrate(
            profile, repo_root=repo_root, manifest_path=manifest_path
        )
        return 0, result
    except SceneImageTestAppError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        print("DRY_RUN_RESULT=FAIL", file=sys.stderr)
        print("READY_FOR_LIVE_GENERATION=NO", file=sys.stderr)
        return 1, None
    except Exception as exc:  # pragma: no cover - defensive
        print(f"FAIL: unexpected error: {exc}", file=sys.stderr)
        print("DRY_RUN_RESULT=FAIL", file=sys.stderr)
        print("READY_FOR_LIVE_GENERATION=NO", file=sys.stderr)
        return 1, None


def _emit_plan_if_requested(plan: SceneStillPlan, emit_plan: Optional[str]) -> None:
    if not emit_plan:
        return
    Path(emit_plan).write_text(
        json.dumps(plan.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def run_preview(
    profile_id: Optional[str] = None,
    *,
    repo_root: Optional[Path] = None,
    manifest_path: Optional[Path] = None,
    model: str = DEFAULT_MODEL,
    size: str = DEFAULT_SIZE,
    quality: str = DEFAULT_QUALITY,
    scene_text: Optional[str] = None,
    scene_file: Optional[str] = None,
    proposal_fixture: Optional[str] = None,
    live_interpreter: bool = False,
    plan_file: Optional[str] = None,
    emit_plan: Optional[str] = None,
) -> int:
    """Run the offline preview and print the deterministic report."""
    root = repo_root if repo_root is not None else _default_repo_root()
    manifest = (
        manifest_path if manifest_path is not None else default_manifest_path(root)
    )
    try:
        profile, plan = _resolve_profile_and_plan(
            profile_id=profile_id,
            scene_text=scene_text,
            scene_file=scene_file,
            proposal_fixture=proposal_fixture,
            live_interpreter=live_interpreter,
            plan_file=plan_file,
            repo_root=root,
        )
    except SceneImageTestAppError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        print("DRY_RUN_RESULT=FAIL", file=sys.stderr)
        print("READY_FOR_LIVE_GENERATION=NO", file=sys.stderr)
        return 1
    if plan is not None:
        print(format_still_plan_section(plan, replay=plan_file is not None))
        print()
        _emit_plan_if_requested(plan, emit_plan)
    code, result = _run_orchestrate(profile, repo_root=root, manifest_path=manifest)
    if code != 0 or result is None:
        return code
    print(format_preview(result, model=model, size=size, quality=quality))
    return 0 if result.all_gates_pass else 1


def run_generate(
    profile_id: Optional[str] = None,
    *,
    repo_root: Optional[Path] = None,
    manifest_path: Optional[Path] = None,
    model: str = DEFAULT_MODEL,
    size: str = DEFAULT_SIZE,
    quality: str = DEFAULT_QUALITY,
    output_root: Optional[Path] = None,
    provider_calls: Optional[list[int]] = None,
    scene_text: Optional[str] = None,
    scene_file: Optional[str] = None,
    proposal_fixture: Optional[str] = None,
    live_interpreter: bool = False,
    plan_file: Optional[str] = None,
    emit_plan: Optional[str] = None,
) -> int:
    """Run a gated single live generation (NOT authorized in this task)."""
    if os.environ.get(LIVE_ENV_VAR) != "1":
        print(
            f"REJECT: {LIVE_ENV_VAR}=1 is required for --generate", file=sys.stderr
        )
        return 1
    if not os.environ.get(API_KEY_ENV_VAR):
        print(
            f"REJECT: {API_KEY_ENV_VAR} is required for --generate", file=sys.stderr
        )
        return 1

    root = repo_root if repo_root is not None else _default_repo_root()
    manifest = (
        manifest_path if manifest_path is not None else default_manifest_path(root)
    )
    try:
        profile, plan = _resolve_profile_and_plan(
            profile_id=profile_id,
            scene_text=scene_text,
            scene_file=scene_file,
            proposal_fixture=proposal_fixture,
            live_interpreter=live_interpreter,
            plan_file=plan_file,
            repo_root=root,
        )
    except SceneImageTestAppError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        print("DRY_RUN_RESULT=FAIL", file=sys.stderr)
        print("READY_FOR_LIVE_GENERATION=NO", file=sys.stderr)
        return 1
    if plan is not None:
        print(format_still_plan_section(plan, replay=plan_file is not None))
        print()
        _emit_plan_if_requested(plan, emit_plan)
    effective_profile_id = profile.profile_id
    code, result = _run_orchestrate(profile, repo_root=root, manifest_path=manifest)
    if code != 0 or result is None:
        return code
    if not result.all_gates_pass:
        print("DRY_RUN_RESULT=FAIL", file=sys.stderr)
        print("READY_FOR_LIVE_GENERATION=NO", file=sys.stderr)
        return 1

    if provider_calls is not None:
        provider_calls.append(1)

    conditioned = generate_conditioned_image_from_bundle(
        prompt=result.final_prompt_text,
        reference_bundle=result.bundle,
        model=model,
        api_key=os.environ[API_KEY_ENV_VAR],
        size=size,
        quality=quality,
    )

    out_dir = (
        output_root if output_root is not None else OUTPUT_ROOT
    ) / effective_profile_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / _output_filename(effective_profile_id)
    out_path.write_bytes(conditioned.payload)

    meta = {
        "profile_id": effective_profile_id,
        "model": conditioned.model,
        "payload_sha256": conditioned.payload_sha256,
        "content_type": conditioned.content_type,
        "reference_bundle_hash": result.bundle.content_hash,
        "prompt_item_hash": result.prompt_item.content_hash,
        "final_prompt_hash": result.final_prompt_hash,
        "attachment_filenames": list(result.attachment_filenames),
    }
    meta_path = out_dir / f"{_output_filename(effective_profile_id)}.json"
    meta_path.write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    print(f"GENERATED={out_path}")
    print("PROVIDER_CALLS=1")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    shared = dict(
        model=args.model,
        size=args.size,
        quality=args.quality,
        scene_text=args.scene_text,
        scene_file=args.scene_file,
        proposal_fixture=args.proposal_fixture,
        live_interpreter=args.live_interpreter,
        plan_file=args.plan_file,
        emit_plan=args.emit_plan,
    )
    if args.preview:
        return run_preview(args.profile_id, **shared)
    return run_generate(args.profile_id, **shared)


if __name__ == "__main__":
    sys.exit(main())
