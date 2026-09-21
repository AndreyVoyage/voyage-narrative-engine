#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CRP -- R3 (Intimacy / Sexology Specialist) relevance boundary.

Deterministic, explicit-signal-only relevance detection for whether R3 is a
plausible candidate role for a given subject's evidence set. This module
NEVER authorizes R3 execution: ``RoleTask.__post_init__`` (role_task.py,
``GATED_OPTIONAL_ROLES``) remains the sole, unweakened authorization gate --
every R3 ``RoleTask`` still requires a caller-supplied, non-empty
``activation_authorization_ref`` regardless of anything this module returns.

Detection reads only explicit, caller-attached ``SourceEvidence.metadata``
markers -- never free-text content inference, never ``speaker_or_author``,
never any appearance/gender/attractiveness-shaped field (no such field exists
on ``SourceEvidence`` for this module to read). A future free-form/LLM-based
classifier is explicitly out of scope for V1 (CRP_MAINLINE_CONSOLIDATION_V1
Part 10): when no explicit marker is present, the result is NOT_RELEVANT, not
an invented judgment.

Recognized explicit ``SourceEvidence.metadata`` keys (all optional; a caller
supplies whichever apply):

- ``domain`` / ``domains``: a string or iterable of strings; "intimacy" or
  "sexuality" (case-insensitive) marks that evidence as intimacy-domain.
- ``explicit_sexual_trait``: ``True`` marks an authored sexual trait.
- ``explicit_intimacy_boundary``: ``True`` marks an authored sexual/intimacy
  boundary or preference.
- ``intimacy_relationship_content``: ``True`` marks intimacy-related
  relational/motivational content.
- ``owner_requested_domains``: a string or iterable of strings; "intimacy" or
  "sexuality" marks an explicit owner request for that characterization.
- ``intimacy_signal``: the literal string ``"AMBIGUOUS"`` marks evidence the
  caller flagged as an uncertain/partial intimacy signal (contributes to
  ``INSUFFICIENT_EVIDENCE`` only when no stronger explicit marker exists).

Stdlib-only. No provider, no network, no canon access.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Tuple

from .contracts import SourceEvidence
from .errors import CrpValidationError

# ---------------------------------------------------------------------------
# Result vocabulary
# ---------------------------------------------------------------------------


class R3RelevanceStatus(Enum):
    NOT_RELEVANT = "NOT_RELEVANT"
    RELEVANT_REQUIRES_AUTHORIZATION = "RELEVANT_REQUIRES_AUTHORIZATION"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


EXPLICIT_INTIMACY_DOMAIN_INPUT = "EXPLICIT_INTIMACY_DOMAIN_INPUT"
EXPLICIT_SEXUAL_TRAIT = "EXPLICIT_SEXUAL_TRAIT"
EXPLICIT_INTIMACY_BOUNDARY = "EXPLICIT_INTIMACY_BOUNDARY"
EXPLICIT_INTIMACY_RELATIONSHIP_CONTENT = "EXPLICIT_INTIMACY_RELATIONSHIP_CONTENT"
EXPLICIT_OWNER_REQUEST = "EXPLICIT_OWNER_REQUEST"
EXISTING_INTIMACY_EVIDENCE = "EXISTING_INTIMACY_EVIDENCE"
AMBIGUOUS_INTIMACY_SIGNAL = "AMBIGUOUS_INTIMACY_SIGNAL"
NO_INTIMACY_SIGNAL_FOUND = "NO_INTIMACY_SIGNAL_FOUND"

_INTIMACY_DOMAIN_TOKENS = frozenset({"intimacy", "sexuality"})


@dataclass(frozen=True)
class R3RelevanceResult:
    """Structured, auditable outcome of relevance detection.

    This result is data only. It carries no authorization capability: nothing
    in this module or in this result type can construct or supply an
    ``activation_authorization_ref``. Authorization remains a separate,
    explicit, human-driven action performed elsewhere (CRP-OD-9).
    """

    status: R3RelevanceStatus
    evidence_refs: Tuple[str, ...]
    reason_codes: Tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.status, R3RelevanceStatus):
            raise CrpValidationError("status must be an R3RelevanceStatus")
        if not isinstance(self.evidence_refs, tuple) or any(
            not isinstance(r, str) or not r.strip() for r in self.evidence_refs
        ):
            raise CrpValidationError("evidence_refs must be a tuple of non-empty strings")
        if not isinstance(self.reason_codes, tuple) or any(
            not isinstance(r, str) or not r.strip() for r in self.reason_codes
        ):
            raise CrpValidationError("reason_codes must be a tuple of non-empty strings")


def _normalize_domain_tokens(*raw_values: Any) -> frozenset:
    tokens: set = set()
    for raw in raw_values:
        if raw is None:
            continue
        if isinstance(raw, str):
            candidates: Iterable[Any] = (raw,)
        elif isinstance(raw, (list, tuple, set, frozenset)):
            candidates = raw
        else:
            continue
        for candidate in candidates:
            if isinstance(candidate, str) and candidate.strip():
                tokens.add(candidate.strip().lower())
    return frozenset(tokens)


def evaluate_r3_relevance(evidence: Iterable[SourceEvidence]) -> R3RelevanceResult:
    """Evaluate whether R3 is a plausible candidate role for this evidence set.

    Reads only explicit ``SourceEvidence.metadata`` markers (see module
    docstring). Never inspects ``speaker_or_author`` or any other field as an
    appearance/gender/attractiveness proxy -- no such field exists on
    ``SourceEvidence`` for this function to read, so that category of
    inference is structurally impossible here, not merely policy-forbidden.

    Returns ``RELEVANT_REQUIRES_AUTHORIZATION`` when at least one explicit
    marker is found (relevance alone; this NEVER authorizes execution).
    Returns ``INSUFFICIENT_EVIDENCE`` when the only signal found is an
    explicit caller-flagged ambiguous marker and no stronger explicit marker
    exists. Returns ``NOT_RELEVANT`` when no recognized explicit marker is
    present at all -- the default, per CRP_MAINLINE_CONSOLIDATION_V1 Part C.
    """
    evidence = tuple(evidence)
    for item in evidence:
        if not isinstance(item, SourceEvidence):
            raise CrpValidationError("evaluate_r3_relevance requires SourceEvidence items")

    relevant_refs: list = []
    reason_codes: set = set()
    ambiguous_refs: list = []

    for item in evidence:
        md = item.metadata
        found = False

        domains = _normalize_domain_tokens(md.get("domain"), md.get("domains"))
        if domains & _INTIMACY_DOMAIN_TOKENS:
            reason_codes.add(EXISTING_INTIMACY_EVIDENCE)
            reason_codes.add(EXPLICIT_INTIMACY_DOMAIN_INPUT)
            found = True

        if md.get("explicit_sexual_trait") is True:
            reason_codes.add(EXPLICIT_SEXUAL_TRAIT)
            found = True

        if md.get("explicit_intimacy_boundary") is True:
            reason_codes.add(EXPLICIT_INTIMACY_BOUNDARY)
            found = True

        if md.get("intimacy_relationship_content") is True:
            reason_codes.add(EXPLICIT_INTIMACY_RELATIONSHIP_CONTENT)
            found = True

        owner_domains = _normalize_domain_tokens(md.get("owner_requested_domains"))
        if owner_domains & _INTIMACY_DOMAIN_TOKENS:
            reason_codes.add(EXPLICIT_OWNER_REQUEST)
            found = True

        if found:
            relevant_refs.append(item.source_id)
        elif str(md.get("intimacy_signal", "")).strip().upper() == "AMBIGUOUS":
            ambiguous_refs.append(item.source_id)

    if relevant_refs:
        return R3RelevanceResult(
            status=R3RelevanceStatus.RELEVANT_REQUIRES_AUTHORIZATION,
            evidence_refs=tuple(relevant_refs),
            reason_codes=tuple(sorted(reason_codes)),
        )
    if ambiguous_refs:
        return R3RelevanceResult(
            status=R3RelevanceStatus.INSUFFICIENT_EVIDENCE,
            evidence_refs=tuple(ambiguous_refs),
            reason_codes=(AMBIGUOUS_INTIMACY_SIGNAL,),
        )
    return R3RelevanceResult(
        status=R3RelevanceStatus.NOT_RELEVANT,
        evidence_refs=(),
        reason_codes=(NO_INTIMACY_SIGNAL_FOUND,),
    )
