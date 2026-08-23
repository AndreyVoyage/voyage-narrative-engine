#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exception hierarchy for Character Visual Reference Conditioning v0 (C3).

C3 binds an explicit frozen visual-reference selection (from Character Canon,
read-only) to image-generation input adjacent to the image provider boundary.
It performs ZERO Canon writes, ZERO provider/LLM calls, and ZERO media
generation in this task.
"""

from __future__ import annotations


class CharacterVisualConditioningError(Exception):
    """Root of the Character Visual Reference Conditioning hierarchy."""


class ReferenceSelectionError(CharacterVisualConditioningError):
    """Raised when the active visual-reference selection cannot be made
    deterministically from the Character Canon snapshot."""


class ReferenceBinaryError(CharacterVisualConditioningError):
    """Raised when a selected reference file is missing, empty, or has an
    unsupported image format (read-only; the file is never modified)."""


class ProviderInputConfigurationError(CharacterVisualConditioningError):
    """Raised when a conditioned provider request is missing a required input
    (model, prompt, or reference images) BEFORE any network access."""


class ProviderInputTransportError(CharacterVisualConditioningError):
    """Raised for HTTP/connection/JSON/binary transport or protocol failures.

    Terminal: the request is never retried and never issues a second fetch."""


class ProviderInputResultError(CharacterVisualConditioningError):
    """Raised when the provider returns no single decodable in-band image."""