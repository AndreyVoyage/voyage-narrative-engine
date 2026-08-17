#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CRP MVP S2B-part-1 -- deterministic R4 voice-pattern label-fidelity validation.

``VoicePatternLabel`` (CRP_MVP_SPEC_v1.md §12) is a fourth, INDEPENDENT axis
specific to R4 voice-reconstruction output. These checks enforce the exact
label-fidelity rules resolved in:
``CRP_MVP_S2B_PROMPT_AUTHORING_PREFLIGHT_2026-08-17.md`` §6.5.

Enforced rules (deterministic only -- no semantic personality inference, no
LLM, no claim rewriting, no label invention):

- R4-scoping: ``voice_pattern_label`` may only be carried by a claim whose
  ``role_id == "R4"`` AND whose ``target_module_or_layer`` is a ``voice.*``
  dimension. Any other combination is a violation (the field is R4-specific).
- ``OBSERVED``        -> at least one direct-evidence ``source_type`` in
                         ``source_type_summary``.
- ``INFERRED``        -> ``confidence`` in {POSSIBLE, UNKNOWN}.
- ``GENERATED_RULE``  -> ``source_type_summary`` contains ``MODEL_EXAMPLE``
                         AND ``confidence`` in {POSSIBLE, UNKNOWN}. It is
                         NEVER re-mapped to ``source_type``, ``confidence``,
                         canon fact, or ``MODEL_INFERENCE``.
- ``NEGATIVE_EXAMPLE``-> ``claim_type != FACT``.

Axes stay independent: ``source_type`` (provenance), ``confidence``
(epistemic strength), ``claim_type`` (general claim semantic type), and
``voice_pattern_label`` (R4-specific voice pattern) are never collapsed here.

No provider, no network, no canon/PAC/Sandbox access, no legacy-KB import.
"""

from __future__ import annotations

from typing import Tuple

from .contracts import (
    DIRECT_SOURCE_TYPES,
    ClaimType,
    Confidence,
    RoleClaim,
    SourceType,
    VoicePatternLabel,
)


def voice_label_violations(claims: Tuple[RoleClaim, ...]) -> tuple[str, ...]:
    """Return deterministic R4 voice-label fidelity violation descriptions.

    Returns an empty tuple when every ``voice_pattern_label`` in ``claims`` is
    faithful to its resolved rule. Raises ``TypeError`` for non-``RoleClaim``
    input (fail-closed, never a silent guess).

    A claim with ``voice_pattern_label is None`` is ignored (the field is
    optional and additive; absence is always valid for non-R4 claims and for
    R4 claims that do not carry a voice-pattern label).
    """
    if not isinstance(claims, tuple):
        raise TypeError("claims must be a tuple of RoleClaim")

    violations: list[str] = []
    for claim in claims:
        if not isinstance(claim, RoleClaim):
            raise TypeError("claims must contain RoleClaim instances")

        label = claim.voice_pattern_label
        if label is None:
            continue

        # -- R4-scoping: the label is R4-specific and voice-specific. ------
        if claim.role_id != "R4":
            violations.append(
                f"claim {claim.claim_id!r} carries voice_pattern_label "
                f"{label.value!r} but role_id is {claim.role_id!r}, not R4"
            )
        if not claim.target_module_or_layer.strip().startswith("voice."):
            violations.append(
                f"claim {claim.claim_id!r} carries voice_pattern_label "
                f"{label.value!r} but targets {claim.target_module_or_layer!r}, "
                "not a voice.* dimension"
            )

        # -- Per-label fidelity -------------------------------------------
        if label is VoicePatternLabel.OBSERVED:
            if not any(t in DIRECT_SOURCE_TYPES for t in claim.source_type_summary):
                violations.append(
                    f"claim {claim.claim_id!r} is OBSERVED but has no "
                    "direct-evidence source_type in source_type_summary"
                )

        elif label is VoicePatternLabel.INFERRED:
            if claim.confidence not in (Confidence.POSSIBLE, Confidence.UNKNOWN):
                violations.append(
                    f"claim {claim.claim_id!r} is INFERRED but confidence is "
                    f"{claim.confidence.value!r}, not POSSIBLE/UNKNOWN"
                )

        elif label is VoicePatternLabel.GENERATED_RULE:
            if SourceType.MODEL_EXAMPLE not in claim.source_type_summary:
                violations.append(
                    f"claim {claim.claim_id!r} is GENERATED_RULE but "
                    "source_type_summary lacks MODEL_EXAMPLE"
                )
            if claim.confidence not in (Confidence.POSSIBLE, Confidence.UNKNOWN):
                violations.append(
                    f"claim {claim.claim_id!r} is GENERATED_RULE but confidence "
                    f"is {claim.confidence.value!r}, not POSSIBLE/UNKNOWN"
                )

        elif label is VoicePatternLabel.NEGATIVE_EXAMPLE:
            if claim.claim_type is ClaimType.FACT:
                violations.append(
                    f"claim {claim.claim_id!r} is NEGATIVE_EXAMPLE but "
                    "claim_type is FACT (an anti-pattern cannot be a FACT)"
                )

    return tuple(violations)