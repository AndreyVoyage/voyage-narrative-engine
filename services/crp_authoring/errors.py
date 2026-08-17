#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CRP MVP S0 -- fail-closed error types.

Small, distinct error types for the evidence-ledger foundation so callers and
tests can distinguish structural contract violations from logic-level
unsupported-claim rejections. No provider, no network, no canon access.
"""

from __future__ import annotations


class CrpError(RuntimeError):
    """Base fail-closed error for the CRP authoring domain."""


class CrpValidationError(CrpError):
    """A contract value is structurally invalid (wrong type, empty required
    field, invalid enum, broken linkage). Raised at construction/validation
    time and never silently corrected."""


class UnsupportedClaimError(CrpError):
    """A claim fails the evidence-legitimacy rule (e.g. a FACT claim whose
    supporting evidence is solely inference/example). The claim must not reach
    an accepted/promotable state; it is rejected, never silently downgraded."""