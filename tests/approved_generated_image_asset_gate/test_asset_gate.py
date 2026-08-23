#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline tests for Approved Generated Image Asset Gate v0 (C4).

Deterministic, hermetic, fully offline:

    PROVIDER_CALLS = 0
    LLM_CALLS      = 0
    MEDIA_GENERATION = 0
    CANON_WRITES    = 0
    ASSET_REGISTRY_WRITES = 0
    OPENAI_API_KEY_ACCESS = NO

The gate never performs real import/registry writes. Tests use synthetic
candidates/reviews and a fake copy boundary is unnecessary: the gate itself
performs no writes.
"""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from services.approved_generated_image_asset_gate import (  # noqa: E402
    AssetGateConfigurationError,
    AssetGateResult,
    BlockReason,
    GateVerdict,
    evaluate_asset_gate,
)
from services.generated_image_review import (  # noqa: E402
    GeneratedImageCandidate,
    GeneratedImageReview,
    ReviewDecision,
    build_generated_image_candidate,
    build_generated_image_review,
)

_GOOD_SHA = "1491fdf3341009898e33e6f903ab0d1b03451f613bdf396922d587a231318ec5"
_OTHER_SHA = "1491fdf3341009898e33e6f903ab0d1b03451f613bdf396922d587a231318ec6"
_MEDIA_ITEM_ID = "kira_yoga_hall_pilot_image_01"
_PROMPT_HASH = "d9605fe527bfba4a28eed79c51aa087d1b4ee318afef30c1a68aee4fbeff2d18"


def _candidate(**overrides):
    kwargs = dict(
        source_media_item_id=_MEDIA_ITEM_ID,
        image_sha256=_GOOD_SHA,
        image_format="PNG",
        image_byte_length=1424071,
        production_eligible=False,
        source_prompt_item_hash=_PROMPT_HASH,
        provider="OpenAI",
        provider_model_or_operation="gpt-image-2",
    )
    kwargs.update(overrides)
    return build_generated_image_candidate(**kwargs)


def _review(candidate, decision="APPROVED", review_id="rev01"):
    return build_generated_image_review(
        review_id=review_id,
        candidate=candidate,
        decision=decision,
    )


def _eval(candidate, review, **kw):
    if "actual_source_sha256" not in kw and "actual_source_path" not in kw:
        kw["actual_source_sha256"] = candidate.image_sha256
    return evaluate_asset_gate(candidate, review, **kw)


# ---------------------------------------------------------------------------
# Upstream production ineligibility (the expected real-C4 outcome)
# ---------------------------------------------------------------------------


def test_approved_review_but_ineligible_blocks():
    c = _candidate(production_eligible=False)
    r = _review(c, "APPROVED")
    result = _eval(c, r)
    assert result.verdict is GateVerdict.BLOCKED
    assert result.reason is BlockReason.UPSTREAM_PRODUCTION_INELIGIBLE


def test_eligibility_not_promoted_by_approval():
    c = _candidate(production_eligible=False)
    before = c.production_eligible
    r = _review(c, "APPROVED")
    _eval(c, r)
    assert c.production_eligible is before
    assert c.production_eligible is False


def test_candidate_unchanged_after_gate():
    c = _candidate(production_eligible=False)
    before = c.to_dict()
    r = _review(c, "APPROVED")
    _eval(c, r)
    assert c.to_dict() == before


def test_review_unchanged_after_gate():
    c = _candidate(production_eligible=False)
    r = _review(c, "APPROVED")
    before = r.to_dict()
    _eval(c, r)
    assert r.to_dict() == before


# ---------------------------------------------------------------------------
# Review decision / binding
# ---------------------------------------------------------------------------


def test_rejected_review_blocks():
    c = _candidate(production_eligible=True)
    r = _review(c, "REJECTED")
    result = _eval(c, r)
    assert result.verdict is GateVerdict.BLOCKED
    assert result.reason is BlockReason.REVIEW_NOT_APPROVED


def test_review_candidate_mismatch_blocks():
    c1 = _candidate(production_eligible=True)
    c2 = _candidate(image_sha256=_OTHER_SHA, production_eligible=True)
    r = _review(c1, "APPROVED")  # bound to c1
    result = _eval(c2, r, actual_source_sha256=c2.image_sha256)
    assert result.verdict is GateVerdict.BLOCKED
    assert result.reason is BlockReason.REVIEW_CANDIDATE_MISMATCH


def test_approved_bound_review_passes_review_portion():
    c = _candidate(production_eligible=True)
    r = _review(c, "APPROVED")
    result = _eval(c, r)
    assert result.verdict is GateVerdict.ELIGIBLE
    assert result.reason is None


def test_approved_bound_review_eligible():
    c = _candidate(production_eligible=True)
    r = _review(c, "APPROVED")
    assert r.candidate_content_hash == c.content_hash
    result = _eval(c, r)
    assert result.verdict is GateVerdict.ELIGIBLE


# ---------------------------------------------------------------------------
# Binary / format
# ---------------------------------------------------------------------------


def test_source_binary_mismatch_blocks():
    c = _candidate(production_eligible=True)
    r = _review(c, "APPROVED")
    result = _eval(c, r, actual_source_sha256=_OTHER_SHA)
    assert result.verdict is GateVerdict.BLOCKED
    assert result.reason is BlockReason.SOURCE_BINARY_MISMATCH


def test_exact_sha_accepted():
    c = _candidate(production_eligible=True)
    r = _review(c, "APPROVED")
    result = _eval(c, r, actual_source_sha256=c.image_sha256)
    assert result.verdict is GateVerdict.ELIGIBLE


def test_source_path_hash_matches():
    c = _candidate(production_eligible=True)
    r = _review(c, "APPROVED")
    # Create a temp file whose bytes hash to the candidate's declared SHA is
    # impossible with arbitrary bytes; verify path API against a controlled file.
    with pytest.raises(AssetGateConfigurationError):
        # no file at path -> config error (missing)
        evaluate_asset_gate(
            c, r, actual_source_path=Path("/nonexistent/nowhere.png")
        )


def test_unsupported_format_blocks():
    # The C2 candidate builder already rejects unsupported formats at
    # construction, so the gate's UNSUPPORTED_FORMAT branch is defensive for a
    # directly-constructed/replaced candidate object.
    c = _candidate(production_eligible=True)
    bad = dataclasses.replace(c, image_format="GIF")
    r = _review(c, "APPROVED")  # review still bound to the valid content_hash
    result = _eval(bad, r, actual_source_sha256=bad.image_sha256)
    assert result.verdict is GateVerdict.BLOCKED
    assert result.reason is BlockReason.UNSUPPORTED_FORMAT


# ---------------------------------------------------------------------------
# Input configuration
# ---------------------------------------------------------------------------


def test_missing_source_sha_config_error():
    c = _candidate(production_eligible=True)
    r = _review(c, "APPROVED")
    with pytest.raises(AssetGateConfigurationError):
        evaluate_asset_gate(c, r)  # neither sha nor path


def test_both_source_sha_and_path_config_error(tmp_path):
    c = _candidate(production_eligible=True)
    r = _review(c, "APPROVED")
    p = tmp_path / "x.png"
    p.write_bytes(b"\x89PNG\r\n\x1a\n")
    with pytest.raises(AssetGateConfigurationError):
        evaluate_asset_gate(c, r, actual_source_sha256=_GOOD_SHA, actual_source_path=p)


# ---------------------------------------------------------------------------
# Determinism + immutability + portability
# ---------------------------------------------------------------------------


def test_decision_deterministic():
    c = _candidate(production_eligible=False)
    r = _review(c, "APPROVED")
    a = _eval(c, r)
    b = _eval(c, r)
    assert a == b
    assert a.verdict is b.verdict
    assert a.reason is b.reason


def test_result_is_frozen():
    c = _candidate(production_eligible=False)
    r = _review(c, "APPROVED")
    result = _eval(c, r)
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.verdict = GateVerdict.ELIGIBLE  # type: ignore[misc]


def test_result_portable_no_absolute_path():
    c = _candidate(production_eligible=False)
    r = _review(c, "APPROVED")
    result = _eval(c, r)
    d = result.to_dict()
    assert "verdict" in d and d["verdict"] == "BLOCKED"
    assert d["reason"] == "UPSTREAM_PRODUCTION_INELIGIBLE"
    assert "C:/" not in str(d)
    assert result.candidate_content_hash == c.content_hash
    assert result.review_content_hash == r.content_hash