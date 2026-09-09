#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Exception hierarchy for the offline Companion visual-preparation chain.

Single root; messages carry stable logical identifiers only -- never absolute
machine paths, Canon paths, raw asset bytes, or credentials.
"""

from __future__ import annotations


class VisualPipelineError(Exception):
    """Root of the Companion visual-preparation exception hierarchy."""


class VisualContextError(VisualPipelineError):
    """The bounded VisualContext input is structurally invalid or out of bounds."""


class ReferenceSelectionError(VisualPipelineError):
    """Deterministic reference selection could not produce a usable set, or an
    explicit asset id is unknown to the active local snapshot."""


class ReferenceBundleError(VisualPipelineError):
    """A selected reference failed a fail-closed integrity check (path safety /
    existence / SHA-256 / byte length / magic-byte format)."""


class VisualPromptError(VisualPipelineError):
    """The VisualContext and ReferenceBundle do not agree, or the prompt could
    not be assembled deterministically."""
