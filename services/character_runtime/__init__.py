#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Character runtime package (minimal provider-independent Runtime/CIS surface).

CRP creates the character; Runtime lets the character live. This package loads
accepted CRP character packages through the acceptance gate and manages durable
runtime memory that never rewrites the accepted package.
"""

from .consolidated_memory import (
    ConsolidatedMemoryBackend,
    ConsolidatedMemoryError,
    ConsolidatedMemoryRecord,
    MemoryPromotionCandidate,
    MemoryPromotionDecision,
    MemoryRelation,
)
from .memory import RuntimeEvent, RuntimeMemoryBackend, RuntimeMemoryError
from .runtime import (
    AcceptedCharacter,
    CharacterRuntimeError,
    RuntimeSession,
    SourceLoader,
    load_accepted_character,
    start_session,
)

__all__ = [
    "RuntimeEvent",
    "RuntimeMemoryBackend",
    "RuntimeMemoryError",
    "ConsolidatedMemoryBackend",
    "ConsolidatedMemoryError",
    "ConsolidatedMemoryRecord",
    "MemoryPromotionCandidate",
    "MemoryPromotionDecision",
    "MemoryRelation",
    "AcceptedCharacter",
    "CharacterRuntimeError",
    "RuntimeSession",
    "SourceLoader",
    "load_accepted_character",
    "start_session",
]
