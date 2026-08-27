#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VNE -> Ren'Py visual statement emitter v0 (pure, generic).

Converts an already-resolved production asset plus an EXPLICIT statement kind
into exactly one Ren'Py visual source line.

Statement semantics are always explicit and generic. The kind (``scene`` /
``show``) is supplied by the caller and is NEVER inferred from Registry
category, ``asset_id``, ``media_item_id``, ``character_id``, ``relative_path``,
filename, or any per-asset / per-character identity.

This module is pure Python: no file I/O, no Registry access, no binding
construction, no MediaPlan / scene-JSON access, no ``import renpy``, no
persistence, no mutation, no KIRA-specific behavior.
"""

from __future__ import annotations

from services.production_media_asset_binding import ResolvedAsset

__all__ = [
    "emit_visual_statement",
    "SUPPORTED_STATEMENT_KINDS",
    "VisualStatementError",
]

# The only Ren'Py visual statement kinds this v0 emits. Both place an image on
# the default layer with default lifecycle; no ``with`` / ``at`` / ``onlayer``
# / ``zorder`` / ``behind`` / ``hide`` is ever added.
SUPPORTED_STATEMENT_KINDS = ("scene", "show")

_IMAGE_EXTENSION_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp")


class VisualStatementError(ValueError):
    """Raised when a visual statement cannot be emitted. Fails closed."""


def emit_visual_statement(
    resolved_asset: ResolvedAsset,
    *,
    statement_kind: str,
) -> list[str]:
    """Return exactly one unindented Ren'Py visual source line.

    ``statement_kind`` must be passed explicitly and be one of
    ``SUPPORTED_STATEMENT_KINDS``. The resolved asset's ``renpy_image_name``
    is used verbatim as the image name and must already be a clean Ren'Py
    automatic-image name (space-separated components, no path separator, no
    file extension). Anything else fails closed.
    """
    if not isinstance(resolved_asset, ResolvedAsset):
        raise VisualStatementError("resolved_asset must be a ResolvedAsset instance")

    if statement_kind not in SUPPORTED_STATEMENT_KINDS:
        raise VisualStatementError(
            "unsupported statement_kind {!r}; expected one of {}".format(
                statement_kind, SUPPORTED_STATEMENT_KINDS
            )
        )

    image_name = resolved_asset.renpy_image_name
    if not isinstance(image_name, str) or image_name.strip() == "":
        raise VisualStatementError(
            "renpy_image_name must be a non-empty, non-whitespace string"
        )
    if "/" in image_name or "\\" in image_name:
        raise VisualStatementError("renpy_image_name must not contain a path separator")
    if image_name.lower().endswith(_IMAGE_EXTENSION_SUFFIXES):
        raise VisualStatementError(
            "renpy_image_name must not carry an image file extension"
        )

    return ["{} {}".format(statement_kind, image_name)]
