#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Plain-data models for Image Provider Boundary v0 (C1).

``GeneratedImage`` is the immutable result of exactly one explicit generation
call. It carries the raw binary payload (PNG/JPEG/WEBP bytes), its SHA-256
digest, the reported content type, and the model identifier used.

The boundary never guesses the provider identity; the provider base URL, the
model identifier, and the API credential are explicit call inputs (or come
from the single owner-ratified environment variable OPENAI_API_KEY).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class GeneratedImage:
    """One immutable, deterministic representation of a generated image.

    - ``payload`` is the raw binary bytes (decode-only; never mutated).
    - ``payload_sha256`` is a stable content digest used for identity.
    - ``content_type`` is the provider-reported MIME type.
    - ``model`` is the explicit runtime model identifier for the call.
    """

    payload: bytes
    payload_sha256: str
    content_type: str
    model: str

    @classmethod
    def from_bytes(
        cls,
        *,
        payload: bytes,
        content_type: str,
        model: str,
    ) -> "GeneratedImage":
        if not isinstance(payload, bytes):
            raise TypeError("payload must be bytes")
        if len(payload) == 0:
            raise ValueError("payload must be non-empty")
        digest = hashlib.sha256(payload).hexdigest()
        return cls(
            payload=payload,
            payload_sha256=digest,
            content_type=content_type,
            model=model,
        )

    def to_dict(self) -> dict:
        """Serializable (non-binary) summary; never includes the image bytes."""
        return {
            "payload_sha256": self.payload_sha256,
            "payload_byte_length": len(self.payload),
            "content_type": self.content_type,
            "model": self.model,
        }


# Known image MIME types accepted by the boundary. Other content types are
# preserved verbatim (the boundary does not re-encode or reinterpret bytes).
SUPPORTED_IMAGE_CONTENT_TYPES = (
    "image/png",
    "image/jpeg",
    "image/webp",
)