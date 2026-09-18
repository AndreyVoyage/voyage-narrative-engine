#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Production Scene Image Generation v1 -- public API.

The first production-grade application-service entry point that resolves a
character through the REAL Character Canon bridge (never a synthetic
snapshot, never Package V1, never copied assets) and produces one
reference-conditioned image via the existing character_visual_conditioning
provider seam. Callable as normal Python application code by editor UI,
future automation, or a future CLI -- not itself a CLI or UI.
"""

from __future__ import annotations

from .service import (
    PRODUCTION_USAGE_CONTEXT,
    ProductionSceneImageRequest,
    ProductionSceneImageResult,
    generate_production_scene_image,
)

__all__ = [
    "PRODUCTION_USAGE_CONTEXT",
    "ProductionSceneImageRequest",
    "ProductionSceneImageResult",
    "generate_production_scene_image",
]
