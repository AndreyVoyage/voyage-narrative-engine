#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CRP MVP S1 -- R6 deterministic Persona Compiler (NON-CREATIVE).

Mechanical assembly only: copy already-constructed ``RoleClaim`` fields into a
``CandidateCharacterPackage`` at ``DRAFT``. R6 never invents claims, never
infers facts, never raises confidence, never deletes conflicting claims, never
silently resolves contradictions, never mutates canon/PAC/Sandbox/CIS state.

Its only transform is deterministic module/layer placement using the claim's
already-set ``target_module_or_layer`` (a SAFE_SPECIFICATION_CHOICE string
convention, not new semantic content):

* ``"psychology.P{0..5}"`` -> ``psychology_candidate[Pn]``
* ``"voice.<dimension>"``  -> ``voice_candidate[dimension]``
* anything else -> FAIL CLOSED (CompilerError): R6 never guesses a placement.

Reuses S0's ``reject_unsupported_claim`` and ``check_contradiction_integrity``
(import, not reimplementation -- defense in depth, single source of truth).
Standard library only; no provider, no network, no canon/PAC/Sandbox access.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Tuple

from .candidate_package import CandidateCharacterPackage, PackageStatus
from .contracts import ContradictionRecord, RoleClaim
from .errors import CrpError
from .validation import check_contradiction_integrity, reject_unsupported_claim


class CompilerError(CrpError):
    """Fail-closed R6 error: an input claim cannot be deterministically placed
    (missing/invalid target) or is structurally unsupported. Never guessed."""


PSYCHOLOGY_TAGS = frozenset({"P0", "P1", "P2", "P3", "P4", "P5"})


def classify_target(target: str) -> Tuple[str, str]:
    """Deterministically classify a claim's ``target_module_or_layer`` into a
    ``(family, key)`` pair via the ratified string convention.

    Returns ``("psychology", "Pn")``, ``("voice", "<dimension>")``, or
    ``("intimacy", "<dimension>")``.
    Raises ``CompilerError`` when the target is absent, invalid, or does not
    match any family prefix -- R6 never guesses a placement.
    """
    if not isinstance(target, str) or not target.strip():
        raise CompilerError("claim has an empty target_module_or_layer; R6 cannot place it")

    t = target.strip()
    if t.startswith("psychology."):
        tag = t[len("psychology."):]
        if tag not in PSYCHOLOGY_TAGS:
            raise CompilerError(
                f"claim target {target!r} is an invalid psychology tag "
                f"(expected one of {sorted(PSYCHOLOGY_TAGS)})"
            )
        return ("psychology", tag)

    if t.startswith("voice."):
        dimension = t[len("voice."):]
        if not dimension:
            raise CompilerError(f"claim target {target!r} has an empty voice dimension")
        return ("voice", dimension)

    if t.startswith("intimacy."):
        dimension = t[len("intimacy."):]
        if not dimension:
            raise CompilerError(f"claim target {target!r} has an empty intimacy dimension")
        return ("intimacy", dimension)

    raise CompilerError(
        f"claim target {target!r} is unmappable: must be 'psychology.P{{0..5}}' "
        "'voice.<dimension>', or 'intimacy.<dimension>'; R6 does not auto-classify"
    )


@dataclass(frozen=True)
class CompileContext:
    """Package-level identity inputs for one R6 compile call."""

    package_id: str
    subject_id: str
    package_version: int
    source_snapshot_id: str
    created_at: datetime


def compile_candidate_package(
    context: CompileContext,
    claims: Tuple[RoleClaim, ...],
    contradictions: Tuple[ContradictionRecord, ...],
) -> CandidateCharacterPackage:
    """Assemble a ``CandidateCharacterPackage`` (status=DRAFT) mechanically.

    - Rejects unsupported claims via ``reject_unsupported_claim`` first
      (fail-closed; a ``FACT`` claim with inference-only evidence raises).
    - Places each claim into ``psychology_candidate`` / ``voice_candidate`` by
      its deterministic ``target_module_or_layer``; an unmappable target raises
      and no package is produced (never silently dropped).
    - Copies every ``ContradictionRecord`` verbatim (both ``claim_ids`` intact)
      after ``check_contradiction_integrity``; never averages, never picks a
      winner, never sets ``resolution_status``.
    - Builds the ``provenance_manifest`` (target -> claim_id tuple) purely from
      the placed claims. ``role_result_refs=()`` and ``audit_result=None`` are
      legitimately empty at this slice.
    """
    if not isinstance(claims, tuple):
        raise CompilerError("claims must be a tuple of RoleClaim")
    if not isinstance(contradictions, tuple):
        raise CompilerError("contradictions must be a tuple of ContradictionRecord")

    psychology: Dict[str, List[RoleClaim]] = {}
    voice: Dict[str, List[RoleClaim]] = {}
    intimacy: Dict[str, List[RoleClaim]] = {}
    provenance: Dict[str, List[str]] = {}

    for claim in claims:
        if not isinstance(claim, RoleClaim):
            raise CompilerError("claims must contain RoleClaim instances")
        reject_unsupported_claim(claim)

        family, key = classify_target(claim.target_module_or_layer)
        if family == "psychology":
            bucket = psychology
        elif family == "voice":
            bucket = voice
        else:
            bucket = intimacy
        bucket.setdefault(key, []).append(claim)
        provenance.setdefault(claim.target_module_or_layer.strip(), []).append(claim.claim_id)

    for record in contradictions:
        if not isinstance(record, ContradictionRecord):
            raise CompilerError("contradictions must contain ContradictionRecord instances")
        check_contradiction_integrity(record)

    return CandidateCharacterPackage(
        package_id=context.package_id,
        subject_id=context.subject_id,
        package_version=context.package_version,
        source_snapshot_id=context.source_snapshot_id,
        role_result_refs=(),
        claims=tuple(claims),
        contradictions=tuple(contradictions),
        unknowns=(),
        psychology_candidate={k: tuple(v) for k, v in psychology.items()},
        voice_candidate={k: tuple(v) for k, v in voice.items()},
        intimacy_candidate={k: tuple(v) for k, v in intimacy.items()},
        validation_results={},
        audit_result=None,
        provenance_manifest={k: tuple(v) for k, v in provenance.items()},
        created_at=context.created_at,
        status=PackageStatus.DRAFT,
    )