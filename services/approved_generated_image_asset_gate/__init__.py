#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Approved Generated Image Asset Gate v0 (C4) -- public API.

A deterministic, immutable gate that decides whether an already-human-APPROVED
generated-image candidate may proceed to production asset handling (Safe
Import / Asset Registry).

Invariants:
- Human APPROVED is necessary but NOT sufficient for production import.
- The candidate's ``production_eligible`` is read verbatim and NEVER promoted.
- The gate never mutates the candidate or review, never writes Canon, never
  writes the Asset Registry, and never copies/imports image bytes.
- The gate performs no provider, LLM, or media generation.
"""

from __future__ import annotations

from .errors import AssetGateConfigurationError, AssetGateError
from .gate import evaluate_asset_gate
from .model import (
    SCHEMA_VERSION,
    AssetGateResult,
    BlockReason,
    GateVerdict,
)

__all__ = [
    "evaluate_asset_gate",
    "AssetGateResult",
    "GateVerdict",
    "BlockReason",
    "SCHEMA_VERSION",
    "AssetGateError",
    "AssetGateConfigurationError",
]