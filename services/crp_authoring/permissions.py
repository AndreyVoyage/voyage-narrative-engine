#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CRP MVP S2A -- deterministic least-privilege permission model.

A closed, minimal set of permission verbs mechanically encoding the already-
ratified per-role write boundaries (CRP_MVP_SPEC_v1.md §10-12). No LLM
judgment: ROLE_PERMISSION_VIOLATION is resolved as a structural check that
reuses S1's ``classify_target`` (single source of truth for module/layer
family) and S0's ``claim_type``.

No provider, no network, no canon/PAC/Sandbox access, no legacy-KB import.
"""

from __future__ import annotations

from enum import Enum
from typing import Tuple

from .compiler import classify_target
from .contracts import ClaimType, RoleClaim


class Permission(Enum):
    """Least-privilege verb vocabulary (closed set)."""

    READ_SOURCE_EVIDENCE = "READ_SOURCE_EVIDENCE"
    READ_PRIOR_ROLE_RESULTS = "READ_PRIOR_ROLE_RESULTS"
    EMIT_SOURCE_EVIDENCE = "EMIT_SOURCE_EVIDENCE"
    EMIT_QUESTION_PLAN = "EMIT_QUESTION_PLAN"
    EMIT_CLAIMS_UNKNOWN = "EMIT_CLAIMS_UNKNOWN"
    EMIT_CLAIMS_PSYCHOLOGY = "EMIT_CLAIMS_PSYCHOLOGY"
    EMIT_CLAIMS_VOICE = "EMIT_CLAIMS_VOICE"
    EMIT_CLAIMS_INTIMACY = "EMIT_CLAIMS_INTIMACY"
    EMIT_CLAIMS_IDENTITY_BIOGRAPHY = "EMIT_CLAIMS_IDENTITY_BIOGRAPHY"
    EMIT_CLAIMS_BEHAVIOR = "EMIT_CLAIMS_BEHAVIOR"
    EMIT_CLAIMS_RELATIONSHIPS = "EMIT_CLAIMS_RELATIONSHIPS"
    EMIT_CLAIMS_BOUNDARIES = "EMIT_CLAIMS_BOUNDARIES"
    EMIT_CLAIMS_SEED_MEMORY = "EMIT_CLAIMS_SEED_MEMORY"


# Canonical per-role permission sets (mechanical encoding of ratified §10-12).
PERMISSIONS_BY_ROLE: dict[str, frozenset[Permission]] = {
    "R1": frozenset({
        Permission.READ_SOURCE_EVIDENCE,
        Permission.EMIT_SOURCE_EVIDENCE,
        Permission.EMIT_QUESTION_PLAN,
        Permission.EMIT_CLAIMS_UNKNOWN,
        # Slice 5: direct-evidence broad-core structuring (no behavior, no
        # psychological inference).
        Permission.EMIT_CLAIMS_IDENTITY_BIOGRAPHY,
        Permission.EMIT_CLAIMS_RELATIONSHIPS,
        Permission.EMIT_CLAIMS_BOUNDARIES,
        Permission.EMIT_CLAIMS_SEED_MEMORY,
    }),
    "R2": frozenset({
        Permission.READ_SOURCE_EVIDENCE,
        Permission.READ_PRIOR_ROLE_RESULTS,
        Permission.EMIT_CLAIMS_PSYCHOLOGY,
        # Slice 5: first-class behavior + initial relational-state
        # interpretation (no direct identity/biography, no seed memory, no
        # boundaries extraction).
        Permission.EMIT_CLAIMS_BEHAVIOR,
        Permission.EMIT_CLAIMS_RELATIONSHIPS,
    }),
    "R4": frozenset({
        Permission.READ_SOURCE_EVIDENCE,
        Permission.READ_PRIOR_ROLE_RESULTS,
        Permission.EMIT_CLAIMS_VOICE,
    }),
    "R3": frozenset({
        Permission.READ_SOURCE_EVIDENCE,
        Permission.READ_PRIOR_ROLE_RESULTS,
        Permission.EMIT_CLAIMS_INTIMACY,
    }),
}


_FAMILY_EMIT_PERMISSION = {
    "psychology": Permission.EMIT_CLAIMS_PSYCHOLOGY,
    "voice": Permission.EMIT_CLAIMS_VOICE,
    "intimacy": Permission.EMIT_CLAIMS_INTIMACY,
    "identity_biography": Permission.EMIT_CLAIMS_IDENTITY_BIOGRAPHY,
    "behavior": Permission.EMIT_CLAIMS_BEHAVIOR,
    "relationships": Permission.EMIT_CLAIMS_RELATIONSHIPS,
    "boundaries": Permission.EMIT_CLAIMS_BOUNDARIES,
    "seed_memory": Permission.EMIT_CLAIMS_SEED_MEMORY,
}


def permission_violations(
    claims: Tuple[RoleClaim, ...],
    permissions: frozenset[Permission],
) -> tuple[str, ...]:
    """Return ROLE_PERMISSION_VIOLATION descriptions for claims the given
    permission set may not emit.

    - A ``claim_type=UNKNOWN`` claim requires ``EMIT_CLAIMS_UNKNOWN``.
    - A non-UNKNOWN claim's target family (``psychology``/``voice`` via the
      shared ``classify_target``) requires the matching emit permission
      (``EMIT_CLAIMS_PSYCHOLOGY`` / ``EMIT_CLAIMS_VOICE``).

    Pure and deterministic; an empty result means no violation. A claim whose
    target cannot be classified raises ``CompilerError`` (fail-closed, never a
    silent guess).
    """
    violations: list[str] = []
    for claim in claims:
        if not isinstance(claim, RoleClaim):
            raise TypeError("claims must contain RoleClaim instances")
        if claim.claim_type == ClaimType.UNKNOWN:
            if Permission.EMIT_CLAIMS_UNKNOWN not in permissions:
                violations.append(
                    f"claim {claim.claim_id!r} is claim_type=UNKNOWN but "
                    f"role lacks EMIT_CLAIMS_UNKNOWN"
                )
            continue
        family, _key = classify_target(claim.target_module_or_layer)
        required = _FAMILY_EMIT_PERMISSION[family]
        if required not in permissions:
            violations.append(
                f"claim {claim.claim_id!r} targets {family!r} but role lacks "
                f"{required.value}"
            )
    return tuple(violations)