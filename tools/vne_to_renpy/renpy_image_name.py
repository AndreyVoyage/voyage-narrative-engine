#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ren'Py image-name transform (thin adapter).

Re-exports the pure, generic ``renpy_image_name_from_relative_path`` transform
from the production media asset binding service. This module is pure Python and
must never ``import renpy`` or modify any ``.rpy`` file.
"""

from __future__ import annotations

from services.production_media_asset_binding.resolver import (
    renpy_image_name_from_relative_path,
)

__all__ = ["renpy_image_name_from_relative_path"]