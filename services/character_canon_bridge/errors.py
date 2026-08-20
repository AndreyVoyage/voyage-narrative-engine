#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exception hierarchy for Character Canon Read Bridge v0.

All exceptions are read-side only: the bridge never writes to Character
Canon. Messages carry stable logical identifiers only, never absolute
machine paths and never Canon content.
"""

from __future__ import annotations


class CharacterCanonBridgeError(Exception):
    """Root of the Character Canon Read Bridge exception hierarchy."""


class CanonRootMissingError(CharacterCanonBridgeError):
    """Raised when the supplied Character Canon root does not exist."""


class CharacterNotFoundError(CharacterCanonBridgeError):
    """Raised when the requested character has no authoritative Canon entry."""


class AmbiguousCharacterError(CharacterCanonBridgeError):
    """Raised when a character cannot be resolved unambiguously."""


class CanonFormatError(CharacterCanonBridgeError):
    """Raised when the authoritative Canon metadata is missing or malformed."""


class CanonStatusUnknownError(CharacterCanonBridgeError):
    """Raised when the Canon status is missing or not a known machine value."""


class ReferencePathSafetyError(CharacterCanonBridgeError):
    """Raised when a Canon reference path is absolute, traverses, or escapes
    the Canon root."""


class ProductionNotAllowedError(CharacterCanonBridgeError):
    """Raised when a production read is requested but the character's Canon
    status does not permit production use (e.g. PENDING_APPROVAL)."""


class UnsupportedUsageContextError(CharacterCanonBridgeError):
    """Raised when the usage_context is not a supported enumerated value."""