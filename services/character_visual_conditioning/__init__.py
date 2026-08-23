#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Character Visual Reference Conditioning v0 (C3) -- public API.

Binds an explicit frozen visual-reference selection read from Character Canon
(READ ONLY) to a single reference-conditioned image-generation input, adjacent
to the C1 image provider boundary.

This package performs NO Canon writes, NO provider/LLM calls in this task,
and NO media generation. The provider-adjacent transport, when invoked with an
explicit model + credential + reference images, performs EXACTLY ONE
image-edit request with no retry, no fallback, and no second fetch.
"""

from __future__ import annotations

from .errors import (
    CharacterVisualConditioningError,
    ProviderInputConfigurationError,
    ProviderInputResultError,
    ProviderInputTransportError,
    ReferenceBinaryError,
    ReferenceSelectionError,
)
from .hashing import compute_content_hash
from .model import (
    SET_SCHEMA_VERSION,
    ConditionedImage,
    VisualReference,
    VisualReferenceSet,
)
from .provider import (
    EDIT_ENDPOINT_PATH,
    ReferenceImageInput,
    generate_conditioned_image,
    reference_inputs_from_set,
)
from .selection import (
    build_visual_reference_set,
    validate_reference_set_integrity,
)

__all__ = [
    "build_visual_reference_set",
    "validate_reference_set_integrity",
    "generate_conditioned_image",
    "reference_inputs_from_set",
    "compute_content_hash",
    "SET_SCHEMA_VERSION",
    "EDIT_ENDPOINT_PATH",
    "VisualReference",
    "VisualReferenceSet",
    "ConditionedImage",
    "ReferenceImageInput",
    "CharacterVisualConditioningError",
    "ReferenceSelectionError",
    "ReferenceBinaryError",
    "ProviderInputConfigurationError",
    "ProviderInputTransportError",
    "ProviderInputResultError",
]