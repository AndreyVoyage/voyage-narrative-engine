#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PAC v0 domain errors.

All exceptions inherit from ``PacError`` so callers can catch all
PAC-level problems with a single base class.
"""

from __future__ import annotations


class PacError(RuntimeError):
    """Base for all PAC-specific errors."""


class PacFmdrError(PacError):
    """ФМДР validation failure -- malformed or missing layers."""


class PacApprovalError(PacError):
    """Invalid approval transition or missing prerequisite."""


class PacCanonError(PacError):
    """Attempted write to canon or forbidden read path."""


class PacGatewayError(PacError):
    """Persona Gateway returned an error or unexpected data."""


class PacProviderError(PacError):
    """LLM provider returned an error or was misconfigured."""


class PacSchemaError(PacError):
    """Dataset record failed JSON Schema validation."""


class PacStorageError(PacError):
    """Filesystem persistence error (I/O, path traversal, duplicate)."""