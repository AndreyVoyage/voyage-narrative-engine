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

        refs = data.get("references")
        if not isinstance(refs, list) or not refs:
            raise ProfileError("references must be a non-empty array")
        self.references: tuple[ReferenceSpec, ...] = tuple(
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

    # 6. Controlled reference preparation (import/reuse into the Library).
    records_by_character, imported_ids, reused_ids, manifest_count = (
        prepare_references(profile, repo_root=repo_root, manifest_path=manifest_path)
    )

    # 7. ReferenceBundle from the Library (provider-neutral, aliased).
    bundle = build_reference_bundle_from_library(
        records_by_character,
        characters_in_frame=profile.characters_in_frame,
        repo_root=repo_root,
        roles_by_asset_id=profile.roles_by_asset_id,
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
        "reference_count_exact": sum(refs_by_char.values()) == len(profile.references),
        "reference_group_count": len(bundle.character_groups)
        == len(profile.characters_in_frame),
        "four_refs_per_character": all(
            refs_by_char[cid] == 4 for cid in profile.characters_in_frame
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

    lines.append("REFERENCE ASSET IDS")
    for spec in p.references:
        lines.append(f"  {spec.asset_id}")
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
    parser.add_argument("--profile", required=True, dest="profile_id")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--preview", action="store_true", help="Offline dry-run only.")
    group.add_argument("--generate", action="store_true", help="Live call (gated).")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--size", default=DEFAULT_SIZE)
    parser.add_argument("--quality", default=DEFAULT_QUALITY)
    return parser


def _default_repo_root() -> Path:
    return _REPO_ROOT


def _default_profiles_dir(repo_root: Path) -> Path:
    return repo_root / PROFILES_DIR_REL


def _run_orchestrate(
    profile_id: str, *, repo_root: Path, manifest_path: Path
) -> tuple[int, Optional[RunResult]]:
    try:
        profile = load_profile(profile_id, _default_profiles_dir(repo_root))
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


def run_preview(
    profile_id: str,
    *,
    repo_root: Optional[Path] = None,
    manifest_path: Optional[Path] = None,
    model: str = DEFAULT_MODEL,
    size: str = DEFAULT_SIZE,
    quality: str = DEFAULT_QUALITY,
) -> int:
    """Run the offline preview and print the deterministic report."""
    root = repo_root if repo_root is not None else _default_repo_root()
    manifest = (
        manifest_path if manifest_path is not None else default_manifest_path(root)
    )
    code, result = _run_orchestrate(
        profile_id, repo_root=root, manifest_path=manifest
    )
    if code != 0 or result is None:
        return code
    print(format_preview(result, model=model, size=size, quality=quality))
    return 0 if result.all_gates_pass else 1


def run_generate(
    profile_id: str,
    *,
    repo_root: Optional[Path] = None,
    manifest_path: Optional[Path] = None,
    model: str = DEFAULT_MODEL,
    size: str = DEFAULT_SIZE,
    quality: str = DEFAULT_QUALITY,
    output_root: Optional[Path] = None,
    provider_calls: Optional[list[int]] = None,
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
    code, result = _run_orchestrate(
        profile_id, repo_root=root, manifest_path=manifest
    )
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

    out_dir = (output_root if output_root is not None else OUTPUT_ROOT) / profile_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / _output_filename(profile_id)
    out_path.write_bytes(conditioned.payload)

    meta = {
        "profile_id": profile_id,
        "model": conditioned.model,
        "payload_sha256": conditioned.payload_sha256,
        "content_type": conditioned.content_type,
        "reference_bundle_hash": result.bundle.content_hash,
        "prompt_item_hash": result.prompt_item.content_hash,
        "final_prompt_hash": result.final_prompt_hash,
        "attachment_filenames": list(result.attachment_filenames),
    }
    meta_path = out_dir / f"{_output_filename(profile_id)}.json"
    meta_path.write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    print(f"GENERATED={out_path}")
    print("PROVIDER_CALLS=1")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.preview:
        return run_preview(
            args.profile_id,
            model=args.model,
            size=args.size,
            quality=args.quality,
        )
    return run_generate(
        args.profile_id,
        model=args.model,
        size=args.size,
        quality=args.quality,
    )


if __name__ == "__main__":
    sys.exit(main())
