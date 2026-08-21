#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prompt Composer v0 -- public API.

Exposes the deterministic, provider-neutral PromptPackage/PromptItem models
plus the ``build_prompt_package`` builder. This package performs NO provider
call, NO LLM call, NO creative inference, NO media generation, and never
modifies upstream ASS / Location Canon / Character Canon bridge /
SceneInterpretation / MediaPlan production code.
"""

from __future__ import annotations

from .builder import PROMPT_PACKAGE_SCHEMA_VERSION, build_prompt_package
from .errors import (
    PromptComposerError,
    PromptComposerValidationError,
)
from .hashing import compute_content_hash
from .model import PromptItem, PromptPackage

__all__ = [
    "build_prompt_package",
    "PROMPT_PACKAGE_SCHEMA_VERSION",
    "PromptPackage",
    "PromptItem",
    "compute_content_hash",
    "PromptComposerError",
    "PromptComposerValidationError",
]