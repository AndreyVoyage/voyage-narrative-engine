#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Provider-neutral request/result contracts for the IMAGE_GENERATION boundary.

``GeneratedImage`` is adapted from ``services/image_provider_boundary/model.py``
in the VNE repo (immutable payload + SHA-256 + content type + model). The
``ImageGenerationRequest`` is Companion-owned: it names the visual identity
(character id + local snapshot version), the exact prompt text, and the
resolved provider/model -- it never carries a credential, an absolute path, a
Canon path, Memory, raw session history, or a Character Package. Reference
bytes are NOT duplicated here; they travel in the already-validated
:class:`~services.character_companion.visual.reference_model.ReferenceBundle`.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Optional

# request kinds understood by the adapter's router
ENDPOINT_TEXT = "text"                # POST <base>/v1/images/generations
ENDPOINT_CONDITIONED = "conditioned"  # POST <base>/v1/images/edits (multipart)

DEFAULT_SIZE = "1024x1024"

#: content types the downstream Companion gallery can already serve.
SUPPORTED_IMAGE_CONTENT_TYPES = ("image/png", "image/jpeg", "image/webp")

CONTENT_TYPE_TO_EXTENSION = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
}

#: magic-byte format key (png/jpg/webp) -> supported content type
IMAGE_FORMAT_KEY_TO_CONTENT_TYPE = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "webp": "image/webp",
}


@dataclass(frozen=True)
class ImageGenerationRequest:
    """One provider-neutral image request. Provider-specific transport shaping
    (JSON vs multipart, endpoint path, headers) happens later in the adapter."""

    character_id: str
    character_snapshot_version: str
    prompt_text: str
    provider_id: str
    model_id: str
    endpoint_kind: str = ENDPOINT_TEXT
    size: str = DEFAULT_SIZE
    quality: Optional[str] = None

    def to_dict(self) -> dict:
        # non-secret summary; safe to log / attach to job provenance.
        return {
            "characterId": self.character_id,
            "characterSnapshotVersion": self.character_snapshot_version,
            "providerId": self.provider_id,
            "modelId": self.model_id,
            "endpointKind": self.endpoint_kind,
            "size": self.size,
            "quality": self.quality,
            "promptChars": len(self.prompt_text),
        }


@dataclass(frozen=True)
class GeneratedImage:
    """Immutable result of exactly one explicit generation call.

    ``payload`` is raw image bytes (decode-only, never mutated / re-encoded).
    Never place ``payload`` in a repr / error / UI-facing metadata blob -- use
    :meth:`to_dict`.
    """

    payload: bytes
    payload_sha256: str
    content_type: str
    model: str

    @classmethod
    def from_bytes(cls, *, payload: bytes, content_type: str, model: str) -> "GeneratedImage":
        if not isinstance(payload, bytes):
            raise TypeError("payload must be bytes")
        if not payload:
            raise ValueError("payload must be non-empty")
        return cls(
            payload=payload,
            payload_sha256=hashlib.sha256(payload).hexdigest(),
            content_type=content_type,
            model=model,
        )

    def to_dict(self) -> dict:
        return {
            "payloadSha256": self.payload_sha256,
            "payloadByteLength": len(self.payload),
            "contentType": self.content_type,
            "model": self.model,
        }
