#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exception hierarchy for Approved Generated Image Asset Gate v0 (C4).

C4 evaluates whether an already-human-APPROVED generated-image candidate may
proceed to production asset handling (Safe Import / Asset Registry). It never
mutates the candidate, review, Canon, or production eligibility, and never
performs provider/LLM/media I/O.
"""

from __future__ import annotations


class AssetGateError(Exception):
    """Root of the Approved Generated Image Asset Gate hierarchy."""


class AssetGateConfigurationError(AssetGateError):
    """Raised when required gate inputs (candidate/review) are invalid or
    missing BEFORE any evaluation."""