#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exception hierarchy for Image Provider Boundary v0 (C1).

The boundary is a single-call, no-retry, no-fallback transport between the
deterministic A1->A6 authoring chain and ONE external image-generation call.

Design invariants reflected here:
- A missing credential or model raises BEFORE any network access.
- A transport/protocol/API failure surfaces as a terminal error; the module
  never retries and never performs a second generation.
"""

from __future__ import annotations


class ImageProviderError(Exception):
    """Root of the Image Provider Boundary exception hierarchy."""


class ImageProviderConfigurationError(ImageProviderError):
    """Raised when the boundary is invoked without the required input that
    must exist BEFORE any network call (credential or model)."""


class ImageProviderTransportError(ImageProviderError):
    """Raised for HTTP/connection/JSON/binary transport or protocol failures.

    Terminal: the boundary never retries and never issues a second
    generation, so this exception marks a failed (not retried) call."""


class ImageProviderResultError(ImageProviderError):
    """Raised when the provider returns no decodable image result."""