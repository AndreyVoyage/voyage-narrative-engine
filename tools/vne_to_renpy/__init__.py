#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""VNE -> Ren'Py adapter package public surface."""

from __future__ import annotations

from .visual_asset_consumer import resolve_media_asset_for_renpy
from .visual_statement_emitter import emit_visual_statement

__all__ = ["resolve_media_asset_for_renpy", "emit_visual_statement"]
