#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exception hierarchy for MediaPlan v0.

The slice performs NO generation, NO provider calls, and NO prompt
composition. These errors describe plan-contract validation failures when
assembling the deterministic MediaPlan.
"""

from __future__ import annotations


class MediaPlanError(Exception):
    """Root of the MediaPlan exception hierarchy."""


class MediaPlanValidationError(MediaPlanError):
    """Raised when a media item is malformed: unknown media kind, invalid or
    duplicate item id, invalid characters_in_frame, or a payload that is not
    JSON-compatible."""


class UnknownMediaKindError(MediaPlanValidationError):
    """Raised when a media item uses an unsupported media kind."""