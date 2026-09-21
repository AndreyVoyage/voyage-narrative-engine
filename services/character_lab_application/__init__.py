#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Character Lab Application Service v1 -- public API.

A thin, UI-agnostic application/facade layer over the read-only Character
Canon bridge plus a local, offline session model. No UI components, no
desktop-wrapper choice, no new Character Canon parsing, no provider/network
call anywhere in this package.
"""

from __future__ import annotations

from .config import CharacterLabApplicationConfig
from .errors import (
    CANON_UNAVAILABLE,
    INTERNAL_ERROR,
    INVALID_INPUT,
    NOT_FOUND,
    OK,
    CharacterLabApplicationError,
)
from .results import (
    CharacterInspectorDetail,
    CharacterSummary,
    CharacterVersionSummary,
    LabSession,
    Message,
)
from .service import CharacterLabApplicationService

__all__ = [
    "CharacterLabApplicationService",
    "CharacterLabApplicationConfig",
    "CharacterLabApplicationError",
    # Results / DTOs
    "CharacterSummary",
    "CharacterVersionSummary",
    "CharacterInspectorDetail",
    "Message",
    "LabSession",
    # Error categories
    "OK",
    "NOT_FOUND",
    "INVALID_INPUT",
    "CANON_UNAVAILABLE",
    "INTERNAL_ERROR",
]
