#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Live smoke for Image Provider Boundary v0 (C1). SKIPS BY DEFAULT.

This test performs the single authorized authoring image-generation smoke
(KIRA / yoga_hall / media item kira_yoga_hall_pilot_image_01) using the
owner-ratified fact only. It is gated behind BOTH:

    IMAGE_PROVIDER_LIVE_SMOKE_ENABLED=1

and the pre-gate conditions (model + credential present, see module source).

NO retry, NO fallback, NO second image. A billing/access/organization error is
a terminal LIVE_SMOKE_FAILED_NO_RETRY outcome — this test raises rather than
retrying. Offline runs always skip (0 provider calls).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from services.image_provider_boundary import (  # noqa: E402
    GeneratedImage,
    generate_image,
)

OWNER_RATIFIED_FACT = "KIRA находится в yoga_hall и разминается на беговой дорожке."
MEDIA_ITEM_ID = "kira_yoga_hall_pilot_image_01"

# The C1 live smoke has no hardcoded model default. The operator supplies it.
SMOKE_MODEL_ENV = "IMAGE_PROVIDER_LIVE_SMOKE_MODEL"
# Generated binary is written OUTSIDE the repository.
OUTPUT_DIR = Path(
    "C:/DEV/Narrative/LOCAL_STORAGE/generated_media_smokes/"
    "IMAGE_PROVIDER_BOUNDARY_V0_C1"
)


def _enabled() -> bool:
    return os.environ.get("IMAGE_PROVIDER_LIVE_SMOKE_ENABLED", "").strip() == "1"


def _model() -> str:
    return os.environ.get(SMOKE_MODEL_ENV, "").strip()


@pytest.mark.skipif(
    not _enabled(),
    reason="live image-generation smoke disabled by default (0 provider calls)",
)
def test_image_provider_boundary_live_smoke_v0():
    model = _model()
    if not model:
        pytest.fail(
            f"SMOKE_ENABLED but {SMOKE_MODEL_ENV} not set: "
            "live smoke model is a required runtime parameter"
        )

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        pytest.fail(
            "SMOKE_ENABLED but OPENAI_API_KEY absent: "
            "C1_BLOCKED_AT_LIVE_GATE_MISSING_CREDENTIAL"
        )

    # EXACTLY ONE generation. No retry, no fallback, no second image.
    result: GeneratedImage = generate_image(
        OWNER_RATIFIED_FACT,
        model=model,
        api_key=api_key,
    )

    assert isinstance(result, GeneratedImage)
    assert result.model == model
    assert len(result.payload) > 0
    assert len(result.payload_sha256) == 64

    # Write the binary OUTSIDE the repository (LOCAL_STORAGE only).
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"{MEDIA_ITEM_ID}.png"
    out_path.write_bytes(result.payload)

    # Strictly informative; never prints the credential or any secret.
    print(f"[live-smoke] {MEDIA_ITEM_ID} bytes={len(result.payload)} "
          f"sha256={result.payload_sha256} path={out_path}")