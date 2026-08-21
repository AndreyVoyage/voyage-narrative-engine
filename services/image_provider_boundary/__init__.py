#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Image Provider Boundary v0 (C1) -- public API.

A single-call, no-retry, no-fallback transport between the deterministic
A1->A6 authoring chain and exactly one external image-generation request.

Provider ratified for C1: OpenAI Images endpoint via OPENAI_API_KEY.

The model identifier is a REQUIRED explicit runtime parameter (no hardcoded
default). This boundary performs NO call unless model + credential are
explicitly supplied, performs EXACTLY ONE generation per call, and refuses
URL results (which would require a forbidden second fetch).
"""

from __future__ import annotations

from .client import (
    API_ENDPOINT_PATH,
    DEFAULT_BASE_URL,
    DEFAULT_TIMEOUT_S,
    generate_image,
)
from .errors import (
    ImageProviderConfigurationError,
    ImageProviderError,
    ImageProviderResultError,
    ImageProviderTransportError,
)
from .model import GeneratedImage, SUPPORTED_IMAGE_CONTENT_TYPES

__all__ = [
    "generate_image",
    "GeneratedImage",
    "SUPPORTED_IMAGE_CONTENT_TYPES",
    "DEFAULT_BASE_URL",
    "DEFAULT_TIMEOUT_S",
    "API_ENDPOINT_PATH",
    "ImageProviderError",
    "ImageProviderConfigurationError",
    "ImageProviderTransportError",
    "ImageProviderResultError",
]