#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Production Scene Image Generation v1 -- the first real-Canon application
service entry point for conditioned image generation.

This module contains NO domain logic of its own. It is a thin orchestrator
over already-existing, already-tested services:

    services.character_canon_bridge.read_character_canon(usage_context="production")
    -> services.character_visual_conditioning.build_reference_bundle(...)
    -> services.character_visual_conditioning.validate_reference_bundle_integrity(...)
    -> services.character_visual_conditioning.generate_conditioned_image_from_bundle(...)

It performs NO reference hashing, NO reference-library logic, NO bundle
construction, and NO provider transport of its own -- all of that already
exists and is reused unchanged.

Nothing here is character-specific: ``character_id`` is an opaque caller
argument, resolved the same way for every character. Scene/prompt text
composition (services.scene_interpretation / services.mediaplan /
services.prompt_composer) is an orthogonal, already-solved concern and stays
the caller's responsibility -- this service accepts an already-composed
``prompt`` string, exactly like the existing provider seam does. Widening
this into a scene-authoring orchestrator is explicitly out of scope for this
slice; see docs/workflows for the corresponding preflight record.

``canon_root`` is always an explicit caller-supplied argument. This module
never hardcodes a Character Canon path and never mutates Character Canon.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Sequence

from services.character_canon_bridge import read_character_canon
from services.character_visual_conditioning import (
    ConditionedImage,
    build_reference_bundle,
    generate_conditioned_image_from_bundle,
    validate_reference_bundle_integrity,
)

__all__ = [
    "PRODUCTION_USAGE_CONTEXT",
    "ProductionSceneImageRequest",
    "ProductionSceneImageResult",
    "generate_production_scene_image",
]

PRODUCTION_USAGE_CONTEXT = "production"

ProviderCall = Callable[..., ConditionedImage]


@dataclass(frozen=True)
class ProductionSceneImageRequest:
    """The minimal input contract for one conditioned scene-image operation.

    Fields are exactly what the existing downstream services require and
    nothing more:

    canon_root:
        Explicit external Character Canon root (never hardcoded by this
        module or its caller's caller).
    character_id:
        The single character to condition on for this request. Resolved
        through the real Character Canon bridge in production mode; no
        synthetic snapshot, no Package V1, no copied assets.
    prompt:
        Already-composed prompt text (e.g. from services.prompt_composer).
        This service does not compose or interpret scene text.
    model:
        Provider model identifier, passed straight through to the existing
        provider seam.
    scene_preset:
        Optional Canon scene-preset key for this character (maps to the
        existing ``scene_preset_by_character`` bundle-builder argument).
    reference_keys:
        Optional explicit subset of this character's frozen Canon reference
        keys (maps to the existing ``reference_keys_by_character`` argument).
    api_key, base_url, size, quality, timeout_s:
        Passed straight through to the existing provider seam only when
        explicitly supplied; omitted fields use that seam's own defaults so
        this module never duplicates or drifts from them.
    """

    canon_root: Path
    character_id: str
    prompt: str
    model: str
    scene_preset: Optional[str] = None
    reference_keys: Optional[Sequence[str]] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    size: Optional[str] = None
    quality: Optional[str] = None
    timeout_s: Optional[float] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "canon_root", Path(self.canon_root))
        if not isinstance(self.character_id, str) or not self.character_id.strip():
            raise ValueError("character_id must be a non-empty string")
        if not isinstance(self.prompt, str) or not self.prompt.strip():
            raise ValueError("prompt must be a non-empty string")
        if not isinstance(self.model, str) or not self.model.strip():
            raise ValueError("model must be a non-empty string")
        if self.reference_keys is not None:
            object.__setattr__(self, "reference_keys", tuple(self.reference_keys))


@dataclass(frozen=True)
class ProductionSceneImageResult:
    """The result of one successful conditioned scene-image operation."""

    conditioned_image: ConditionedImage
    character_id: str
    canon_content_hash: str
    reference_bundle_content_hash: str


def generate_production_scene_image(
    request: ProductionSceneImageRequest,
    *,
    provider_call: ProviderCall = generate_conditioned_image_from_bundle,
) -> ProductionSceneImageResult:
    """Resolve REAL approved Character Canon and produce one conditioned image.

    Fail-closed, in order, before any provider call:
      1. ``read_character_canon(canon_root, character_id, "production")`` --
         raises (character_canon_bridge errors) on a missing/invalid canon
         root, a missing character, or a canon status that is not
         ``APPROVED_AS_CANON``.
      2. ``build_reference_bundle([snapshot], characters_in_frame=[character_id],
         canon_root=canon_root, ...)`` -- raises (character_visual_conditioning
         errors) on missing/empty/unsafe reference files.
      3. ``validate_reference_bundle_integrity(bundle)`` -- re-hashes and
         re-verifies every reference's bytes; raises on any mismatch.

    Only after all three succeed is ``provider_call`` invoked exactly once.
    ``provider_call`` defaults to the real provider seam and is an explicit,
    injectable parameter so tests can replace it with a call-count-tracking
    stub -- it is never monkeypatched implicitly.
    """

    snapshot = read_character_canon(
        request.canon_root, request.character_id, PRODUCTION_USAGE_CONTEXT
    )

    scene_preset_by_character = (
        {request.character_id: request.scene_preset}
        if request.scene_preset is not None
        else None
    )
    reference_keys_by_character = (
        {request.character_id: request.reference_keys}
        if request.reference_keys is not None
        else None
    )

    bundle = build_reference_bundle(
        (snapshot,),
        characters_in_frame=(request.character_id,),
        canon_root=request.canon_root,
        scene_preset_by_character=scene_preset_by_character,
        reference_keys_by_character=reference_keys_by_character,
    )
    validate_reference_bundle_integrity(bundle)

    provider_kwargs = {
        "prompt": request.prompt,
        "reference_bundle": bundle,
        "model": request.model,
    }
    if request.api_key is not None:
        provider_kwargs["api_key"] = request.api_key
    if request.base_url is not None:
        provider_kwargs["base_url"] = request.base_url
    if request.size is not None:
        provider_kwargs["size"] = request.size
    if request.quality is not None:
        provider_kwargs["quality"] = request.quality
    if request.timeout_s is not None:
        provider_kwargs["timeout_s"] = request.timeout_s

    conditioned_image = provider_call(**provider_kwargs)

    return ProductionSceneImageResult(
        conditioned_image=conditioned_image,
        character_id=request.character_id,
        canon_content_hash=snapshot.content_hash,
        reference_bundle_content_hash=bundle.content_hash,
    )
