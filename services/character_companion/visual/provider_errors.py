#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bounded backend errors for the IMAGE_GENERATION provider boundary (Slice C).

Adapted from ``services/image_provider_boundary/errors.py`` in the VNE repo
(single root, config-before-network / transport / result split). Renamed to a
Companion ``ImageGeneration*`` prefix and given one extra member
(``ImageGenerationUnsupportedProviderError``) for the registry capability gate.

Error strings may carry logical provider / model / job identifiers. They MUST
NEVER carry a credential, an ``Authorization`` header, reference bytes, an
absolute local path, or a Character Canon path.
"""

from __future__ import annotations


class ImageGenerationError(RuntimeError):
    """Root of the Companion image-generation backend exception hierarchy.

    Carries a short, stable ``code`` for the job-failure record.
    """

    code = "image_generation_failed"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code


class ImageGenerationConfigurationError(ImageGenerationError):
    """A required input is missing / invalid BEFORE any network access:
    role unassigned, credential absent, no active local snapshot, bad size."""

    code = "image_generation_not_configured"


class ImageGenerationUnsupportedProviderError(ImageGenerationConfigurationError):
    """The resolved provider/model cannot serve this request per the Companion
    registry (model lacks IMAGE_GENERATION, or a conditioned request was made
    to a model whose reference-image capability is explicitly unsupported)."""

    code = "image_generation_unsupported_provider"


class ImageGenerationTransportError(ImageGenerationError):
    """HTTP / connection / JSON transport failure. Terminal: the adapter never
    retries and never issues a second generation."""

    code = "image_generation_transport_failed"


class ImageGenerationResultError(ImageGenerationError):
    """The provider response carried no single decodable in-band image
    (zero / many results, a URL-only result, malformed base64, empty bytes,
    or an unrecognised image format)."""

    code = "image_generation_result_invalid"
