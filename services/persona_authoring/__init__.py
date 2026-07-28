#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
N9 Persona Authoring Companion (PAC) v0 -- public API.

PAC is a local-first authoring assistant that reads character canon
through the existing Persona Gateway, generates 2-3 scene variants
in canonical ФМДР format via an explicit LLM provider, and accumulates
human-approved training examples through a strict three-level approval
state machine.

This package contains domain logic only. The thin CLI adapter lives at
``tools/pac_cli.py``. Runtime output is written under the gitignored
``local_runs/pac/`` directory.
"""

from __future__ import annotations

from .contracts import (
    PAC_APPROVAL_LEVELS,
    PacApprovalEvent,
    PacApprovalLevel,
    PacGeneration,
    PacRequest,
    PacTrainingExample,
    PacVariant,
    validate_fmdr,
)
from .errors import (
    PacApprovalError,
    PacCanonError,
    PacError,
    PacFmdrError,
    PacGatewayError,
    PacProviderError,
    PacSchemaError,
    PacStorageError,
)
from .eval import PacEvalProbe, PacEvalResult, PacEvalService
from .gateway_adapter import GatewayAdapter
from .service import PacService
from .storage import PacStorage

__all__ = [
    # Service
    "PacService",
    "PacStorage",
    "PacEvalService",
    "GatewayAdapter",
    # Contracts
    "PacRequest",
    "PacVariant",
    "PacGeneration",
    "PacApprovalLevel",
    "PacApprovalEvent",
    "PacTrainingExample",
    "PAC_APPROVAL_LEVELS",
    "validate_fmdr",
    # Eval
    "PacEvalProbe",
    "PacEvalResult",
    # Errors
    "PacError",
    "PacFmdrError",
    "PacApprovalError",
    "PacCanonError",
    "PacGatewayError",
    "PacProviderError",
    "PacSchemaError",
    "PacStorageError",
]