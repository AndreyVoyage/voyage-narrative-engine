#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Editor Application Service v1 -- application-layer error model.

A thin, UI-agnostic facade over the proven domain services. This module defines
the bounded application-level exception and the stable error categories used to
map expected domain failures into structured, UI-ready results. It never
reimplements domain semantics and never exposes raw stack traces as API results.
"""

from __future__ import annotations

# Stable application-level error categories.
OK = "OK"
NOT_FOUND = "NOT_FOUND"
INVALID_INPUT = "INVALID_INPUT"
VALIDATION_FAILED = "VALIDATION_FAILED"
ACCEPTED_IMMUTABLE = "ACCEPTED_IMMUTABLE"
ALREADY_EXISTS = "ALREADY_EXISTS"
VERSION_CONFLICT_OR_INVALID_VERSION = "VERSION_CONFLICT_OR_INVALID_VERSION"
PARTIAL_PROJECT_STATE = "PARTIAL_PROJECT_STATE"
IO_FAILURE = "IO_FAILURE"
INTERNAL_ERROR = "INTERNAL_ERROR"

ERROR_CODES = (
    OK,
    NOT_FOUND,
    INVALID_INPUT,
    VALIDATION_FAILED,
    ACCEPTED_IMMUTABLE,
    ALREADY_EXISTS,
    VERSION_CONFLICT_OR_INVALID_VERSION,
    PARTIAL_PROJECT_STATE,
    IO_FAILURE,
    INTERNAL_ERROR,
)


class EditorApplicationError(Exception):
    """Bounded application-layer exception carrying a stable ``code``.

    Raised for read-path failures (list/get) that cannot be expressed as a
    structured result. Expected mutation failures are instead returned as
    ``EditorOperationResult``; unexpected/internal failures may surface here.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
