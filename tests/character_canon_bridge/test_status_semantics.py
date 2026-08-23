#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""C5A status-semantics truth table tests.

Verifies the single shared status predicate maps the canonical NCC vocabulary:
APPROVED_AS_CANON is the only production-approved status; everything else
(including legacy bare APPROVED and PENDING_APPROVAL) is non-production;
unknown values fail closed at the bridge boundary.
"""

from __future__ import annotations

import pytest

from services.character_canon_bridge.status import (
    is_known_canon_status,
    is_production_approved,
)
from services.character_canon_bridge import (
    CanonStatusUnknownError,
    ProductionNotAllowedError,
    read_character_canon,
)

from .conftest import make_status


@pytest.mark.parametrize(
    "status",
    [
        "DRAFT",
        "CANDIDATE",
        "SUPERSEDED",
        "REJECTED",
        "APPROVED_AS_TEST",
        "APPROVED_AS_LOCAL",
        "PENDING_APPROVAL",
        "APPROVED",  # legacy bare form
    ],
)
def test_non_production_statuses_are_not_production_approved(status):
    assert is_production_approved(status) is False


def test_approved_as_canon_is_production_approved():
    assert is_production_approved("APPROVED_AS_CANON") is True


@pytest.mark.parametrize(
    "status,known",
    [
        ("DRAFT", True),
        ("CANDIDATE", True),
        ("SUPERSEDED", True),
        ("REJECTED", True),
        ("APPROVED_AS_TEST", True),
        ("APPROVED_AS_CANON", True),
        ("APPROVED_AS_LOCAL", True),
        ("PENDING_APPROVAL", True),
        ("APPROVED", True),  # legacy known but non-production
        ("SOME_FUTURE_STATUS", False),
    ],
)
def test_known_statuses(status, known):
    assert is_known_canon_status(status) is known


def test_unknown_status_fails_closed_in_bridge(canon_root):
    make_status(canon_root, "WEIRD", "SOME_FUTURE_STATUS")
    with pytest.raises(CanonStatusUnknownError):
        read_character_canon(canon_root, "WEIRD", "draft")


def test_bare_approved_known_but_blocked_from_production(canon_root):
    make_status(canon_root, "LEGACY_ONE", "APPROVED")
    # draft/authoring parse fine (legacy known)
    snap = read_character_canon(canon_root, "LEGACY_ONE", "draft")
    assert snap.status == "APPROVED"
    # production must refuse it (bare APPROVED never grants production)
    with pytest.raises(ProductionNotAllowedError):
        read_character_canon(canon_root, "LEGACY_ONE", "production")


def test_approved_as_test_known_but_blocked_from_production(canon_root):
    make_status(canon_root, "TEST_ONE", "APPROVED_AS_TEST")
    with pytest.raises(ProductionNotAllowedError):
        read_character_canon(canon_root, "TEST_ONE", "production")


def test_approved_as_local_known_but_blocked_from_production(canon_root):
    make_status(canon_root, "LOCAL_ONE", "APPROVED_AS_LOCAL")
    with pytest.raises(ProductionNotAllowedError):
        read_character_canon(canon_root, "LOCAL_ONE", "production")


def test_approved_as_canon_allows_production(canon_root):
    make_status(canon_root, "CANON_ONE", "APPROVED_AS_CANON")
    snap = read_character_canon(canon_root, "CANON_ONE", "production")
    assert snap.status == "APPROVED_AS_CANON"