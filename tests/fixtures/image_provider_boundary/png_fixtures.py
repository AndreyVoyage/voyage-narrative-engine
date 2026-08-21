#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministic in-memory fixtures for Image Provider Boundary v0 tests.

Offline only: these are plain byte constants decoded from base64. No network,
no filesystem I/O beyond importing this module, and no provider calls.
"""

from __future__ import annotations

import base64

# A minimal 1x1 transparent PNG (67 bytes when decoded). Used to verify the
# boundary decodes base64 image payloads into immutable GeneratedImage bytes
# with a stable SHA-256 digest. Its semantic content is irrelevant to the
# boundary (which hashes and preserves bytes verbatim).
_MINIMAL_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
    "+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)

MINIMAL_PNG_BYTES: bytes = base64.b64decode(_MINIMAL_PNG_B64)