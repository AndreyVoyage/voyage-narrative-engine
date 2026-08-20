#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exception hierarchy for Location Canon v0.

Mirrors the domain-level error style of ``services/ass/errors.py``:
small, transport-independent, named exceptions. Messages never carry raw
content or absolute local filesystem paths.
"""

from __future__ import annotations


class LocationCanonError(Exception):
    """Root of the Location Canon exception hierarchy."""


class LocationCanonSourceError(LocationCanonError):
    """Raised when the canonical source file is missing/unreadable, is not
    valid JSON, or fails structural validation."""


class LocationCanonValidationError(LocationCanonError):
    """Raised when a source payload is structurally unsound: missing or
    malformed ``location_id``, wrong ``schema_version``, non-object identity,
    or malformed ``fixed_features``."""


class LocationNotFoundError(LocationCanonError):
    """Raised when a requested ``location_id`` has no canonical entry."""