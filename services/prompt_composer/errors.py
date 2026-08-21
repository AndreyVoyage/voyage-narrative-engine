#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exception hierarchy for Prompt Composer v0.

The composer performs NO provider call, NO LLM call, NO creative inference,
and NO media generation. These errors describe deterministic composition
validation failures.
"""

from __future__ import annotations


class PromptComposerError(Exception):
    """Root of the Prompt Composer exception hierarchy."""


class PromptComposerValidationError(PromptComposerError):
    """Raised when scene_id / interpretation-hash / production-eligibility
    consistency fails, or when a visual item frame references an unknown
    Character Canon anchor."""