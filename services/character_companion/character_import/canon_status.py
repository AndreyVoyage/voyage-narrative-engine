#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Canonical NCC status semantics.

Single source of truth for mapping a Character Canon ``status`` string to the
one boolean the Companion import needs: production eligibility.

* ``APPROVED_AS_CANON`` is the ONLY status that is production-approved.
* Every other known NCC status (and ``PENDING_APPROVAL``) is non-production.
* The legacy bare ``APPROVED`` string is KNOWN (so historical fixtures still
  parse) but must NEVER grant production eligibility.
* Any status outside the known set is UNKNOWN and fails closed at the reader.

Raw canonical status is preserved verbatim in the snapshot/provenance; this
module only derives the boolean. It never mutates status and never
special-cases a character.

Vendoring note: copied near-as-is from
``services/character_canon_bridge/status.py`` in the VNE repo.
"""

from __future__ import annotations

# Canonical NCC machine verdict vocabulary:
#   DRAFT, CANDIDATE, SUPERSEDED, REJECTED,
#   APPROVED_AS_TEST, APPROVED_AS_CANON, APPROVED_AS_LOCAL
# plus the pre-existing in-repo PENDING_APPROVAL and the legacy bare APPROVED.
KNOWN_CANON_STATUSES = frozenset(
    {
        "DRAFT",
        "CANDIDATE",
        "SUPERSEDED",
        "REJECTED",
        "APPROVED_AS_TEST",
        "APPROVED_AS_CANON",
        "APPROVED_AS_LOCAL",
        "PENDING_APPROVAL",
        # Legacy compatibility: historical fixtures used bare ``APPROVED``.
        # It is known (parses) but is never production-approved.
        "APPROVED",
    }
)

#: The ONLY status that yields production eligibility.
PRODUCTION_APPROVED_STATUSES = frozenset({"APPROVED_AS_CANON"})


def is_known_canon_status(status: str) -> bool:
    """Return True when ``status`` is a recognized Canon status string."""
    return status in KNOWN_CANON_STATUSES


def is_production_approved(status: str) -> bool:
    """Return True only for the canonical production-approved status.

    ``APPROVED_AS_CANON`` -> True; everything else -> False. A bare legacy
    ``APPROVED`` therefore never returns True.
    """
    return status in PRODUCTION_APPROVED_STATUSES
