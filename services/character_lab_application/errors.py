#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Character Lab Application Service v1 -- application-layer error model.

A thin, UI-agnostic facade over ``services.character_canon_bridge`` and the
local session model. Mirrors ``services.editor_application.errors``: expected
failures map into a stable, structured category instead of surfacing a raw
traceback to the UI boundary.
"""

from __future__ import annotations

OK = "OK"
NOT_FOUND = "NOT_FOUND"
INVALID_INPUT = "INVALID_INPUT"
CANON_UNAVAILABLE = "CANON_UNAVAILABLE"
INTERNAL_ERROR = "INTERNAL_ERROR"
CRP_VALIDATION_FAILED = "CRP_VALIDATION_FAILED"

ERROR_CODES = (
    OK,
    NOT_FOUND,
    INVALID_INPUT,
    CANON_UNAVAILABLE,
    INTERNAL_ERROR,
    CRP_VALIDATION_FAILED,
)


class CharacterLabApplicationError(Exception):
    """Bounded application-layer exception carrying a stable ``code``."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
