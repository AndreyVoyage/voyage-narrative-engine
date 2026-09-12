#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""VisualPromptPackage -- the final OFFLINE artifact of the Companion visual
chain (Slice B). Deterministic text assembly only: no provider, no network, no
LLM, no Character Canon.

The prompt body has a FIXED section order::

    [REQUEST]
    [SCENE]
    [RECENT CONTEXT]
    [CHARACTER IDENTITY]
    [IDENTITY PRESERVATION]
    [IDENTITY NEGATIVE CONSTRAINTS]
    [REFERENCE GUIDANCE]

Every header is always emitted (``(none)`` when a section has no content) so the
layout -- and therefore the content hash -- is stable across calls. Reference
guidance names asset ids and roles ONLY: never a relative path, never an
absolute path, never bytes.

``[IDENTITY PRESERVATION]`` / ``[IDENTITY NEGATIVE CONSTRAINTS]`` (V1F) render
ALREADY-PINNED standing-identity text handed in by the caller (the exact
``PinnedGenerationSpec.standing_identity`` texts) -- this module never reads
Character Canon, a snapshot's standing_identity, or any source file itself.
Multiple sources for one category are concatenated in the caller-supplied
order, separated by a blank line; simple deterministic text concatenation,
never LLM synthesis. Absent/empty (legacy jobs and snapshots without any
standing identity) renders ``(none)``, exactly like every other optional
section in this module (``[SCENE]``, ``[RECENT CONTEXT]``, ``[REFERENCE
GUIDANCE]``).

This module deliberately does NOT contain: a SceneInterpretationArtifact, a
MediaPlan, the VNE PromptPackage chain, branch/supersession awareness, or any
Ren'Py concern. Slice C (a real provider call) consumes ``prompt_text`` +
``ReferenceBundle`` and is out of scope here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence

from .context import (
    REQUEST_KIND_CONTEXT,
    REQUEST_KIND_CUSTOM,
    VisualContext,
)
from .errors import VisualPromptError
from .hashing import content_hash
from .physical import render_physical_block
from .reference_model import ReferenceBundle

VISUAL_PROMPT_SCHEMA_VERSION = "companion_visual_prompt_package/0.1"

_SECTION_ORDER = (
    "[REQUEST]",
    "[SCENE]",
    "[RECENT CONTEXT]",
    "[CHARACTER IDENTITY]",
    "[IDENTITY PRESERVATION]",
    "[IDENTITY NEGATIVE CONSTRAINTS]",
    "[REFERENCE GUIDANCE]",
)

_NONE = "(none)"

_REFERENCE_GUIDANCE_NOTE = (
    "Treat the supplied reference images as the sole authority for this "
    "character's face, hair, build, and identity. Do not invent or alter "
    "identifying features. Match the physical identity block above."
)


@dataclass(frozen=True)
class VisualPromptPackage:
    schema_version: str
    character_id: str
    character_snapshot_version: str
    request_kind: str
    prompt_text: str
    visual_context_hash: str
    reference_bundle_hash: str
    content_hash: str = ""

    def semantic_payload(self) -> dict[str, Any]:
        # Fully determined by the inputs; no timestamps, no paths, no bytes.
        return {
            "characterId": self.character_id,
            "characterSnapshotVersion": self.character_snapshot_version,
            "requestKind": self.request_kind,
            "promptText": self.prompt_text,
            "visualContextHash": self.visual_context_hash,
            "referenceBundleHash": self.reference_bundle_hash,
        }

    def compute_hash(self) -> str:
        return content_hash(self.semantic_payload())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            **self.semantic_payload(),
            "contentHash": self.content_hash or self.compute_hash(),
        }


# ---------------------------------------------------------------------------
# section renderers
# ---------------------------------------------------------------------------
def _render_request(ctx: VisualContext) -> str:
    lines = [f"kind: {ctx.request_kind}"]
    if ctx.request_kind == REQUEST_KIND_CUSTOM:
        lines.append("Generate an image from the explicit description below.")
        lines.append(f"description: {ctx.explicit_description}")
    else:  # context
        lines.append(
            "Generate an image of the current moment from the scene and recent "
            "conversation below."
        )
        if ctx.explicit_description:
            lines.append(f"description: {ctx.explicit_description}")
    return "\n".join(lines)


def _render_scene(ctx: VisualContext) -> str:
    scene = ctx.scene
    if scene is None:
        return _NONE
    lines: list[str] = []
    for field in ("place", "time", "situation", "mood", "freeform"):
        value = getattr(scene, field, "")
        if value:
            lines.append(f"{field}: {value}")
    loc = scene.location
    if loc is not None and not loc.is_empty():
        if loc.identity:
            lines.append("location identity: " + "; ".join(loc.identity))
        if loc.fixed_features:
            lines.append("location fixed features: " + "; ".join(loc.fixed_features))
        if loc.palette:
            lines.append("location palette: " + "; ".join(loc.palette))
    return "\n".join(lines) if lines else _NONE


def _render_recent_context(ctx: VisualContext) -> str:
    if not ctx.recent_messages:
        return _NONE
    return "\n".join(f"{m.role}: {m.text}" for m in ctx.recent_messages)


def _render_character_identity(
    ctx: VisualContext, physical: Mapping[str, Any], alias: str
) -> str:
    header = f"character: {alias} (snapshot {ctx.character_snapshot_version})"
    block = render_physical_block(physical, alias)
    return f"{header}\n{block}" if block else header


def _render_identity_standing_texts(texts: Sequence[str]) -> str:
    """Deterministic concatenation of already-pinned standing-identity texts,
    in caller-supplied order. No LLM synthesis, no reordering, no dedup."""
    cleaned = [t for t in texts if t]
    return "\n\n".join(cleaned) if cleaned else _NONE


def _render_reference_guidance(bundle: ReferenceBundle) -> str:
    if not bundle.references:
        return _NONE
    lines = []
    for entry in bundle.references:
        roles = ", ".join(entry.roles) if entry.roles else "unspecified"
        lines.append(f"- {entry.asset_id} [roles: {roles}]")
    lines.append("")
    lines.append(_REFERENCE_GUIDANCE_NOTE)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# public builder
# ---------------------------------------------------------------------------
def build_visual_prompt(
    *,
    visual_context: VisualContext,
    reference_bundle: ReferenceBundle,
    physical: Optional[Mapping[str, Any]] = None,
    alias: Optional[str] = None,
    identity_preservation_texts: Sequence[str] = (),
    identity_negative_constraint_texts: Sequence[str] = (),
) -> VisualPromptPackage:
    """Assemble the deterministic ``VisualPromptPackage`` (offline).

    ``visual_context`` and ``reference_bundle`` MUST describe the same character
    and the same snapshot version -- the package binds one identity, one
    snapshot. ``physical`` defaults to an empty profile (weight, and indeed the
    whole block, may legitimately be absent).

    ``identity_preservation_texts`` / ``identity_negative_constraint_texts``
    (V1F) are the caller's ALREADY-PINNED standing-identity texts, in the exact
    order to render (multiple sources render in that order, joined by a blank
    line). Empty (the default) renders ``(none)`` -- this is the legacy /
    no-standing-identity behavior. This function does not read Canon, a
    snapshot, or any source file for these texts; the caller is fully
    responsible for having already pinned them.
    """
    if not isinstance(visual_context, VisualContext):
        raise VisualPromptError("visual_context must be a VisualContext")
    if not isinstance(reference_bundle, ReferenceBundle):
        raise VisualPromptError("reference_bundle must be a ReferenceBundle")

    if visual_context.character_id != reference_bundle.character_id:
        raise VisualPromptError(
            "character id mismatch: "
            f"{visual_context.character_id!r} vs {reference_bundle.character_id!r}"
        )
    if (
        visual_context.character_snapshot_version
        != reference_bundle.character_snapshot_version
    ):
        raise VisualPromptError(
            "snapshot version mismatch: "
            f"{visual_context.character_snapshot_version!r} vs "
            f"{reference_bundle.character_snapshot_version!r}"
        )
    if visual_context.request_kind not in (REQUEST_KIND_CUSTOM, REQUEST_KIND_CONTEXT):
        raise VisualPromptError(f"unknown request_kind {visual_context.request_kind!r}")
    if not reference_bundle.references:
        raise VisualPromptError("reference bundle carries no references")

    prof: Mapping[str, Any] = physical or {}
    resolved_alias = (alias or "").strip() or visual_context.character_id

    sections = {
        "[REQUEST]": _render_request(visual_context),
        "[SCENE]": _render_scene(visual_context),
        "[RECENT CONTEXT]": _render_recent_context(visual_context),
        "[CHARACTER IDENTITY]": _render_character_identity(
            visual_context, prof, resolved_alias
        ),
        "[IDENTITY PRESERVATION]": _render_identity_standing_texts(identity_preservation_texts),
        "[IDENTITY NEGATIVE CONSTRAINTS]": _render_identity_standing_texts(
            identity_negative_constraint_texts
        ),
        "[REFERENCE GUIDANCE]": _render_reference_guidance(reference_bundle),
    }

    blocks = [f"{header}\n{sections[header]}" for header in _SECTION_ORDER]
    prompt_text = "\n\n".join(blocks)

    pkg = VisualPromptPackage(
        schema_version=VISUAL_PROMPT_SCHEMA_VERSION,
        character_id=visual_context.character_id,
        character_snapshot_version=visual_context.character_snapshot_version,
        request_kind=visual_context.request_kind,
        prompt_text=prompt_text,
        visual_context_hash=visual_context.content_hash or visual_context.compute_hash(),
        reference_bundle_hash=reference_bundle.content_hash or reference_bundle.compute_hash(),
        content_hash="",
    )
    object.__setattr__(pkg, "content_hash", pkg.compute_hash())
    return pkg
