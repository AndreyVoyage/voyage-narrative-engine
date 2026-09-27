"""AI-first character draft service public API."""

from .contracts import (
    AnalysisResult,
    CharacterDraftError,
    DraftContradiction,
    DraftQuestion,
    Readiness,
    TARGET_AREAS,
    parse_analysis_text,
)
from .draft_builder import build_semantic, parse_draft_text
from .provider import (
    ANALYSIS_SYSTEM_PROMPT,
    DRAFT_SYSTEM_PROMPT,
    DraftProviderConfig,
    ProviderCallable,
    make_llm_provider,
    scripted_provider,
)
from .service import CharacterDraftService, CharacterIdFactory, new_character_id

__all__ = [
    "AnalysisResult",
    "ANALYSIS_SYSTEM_PROMPT",
    "CharacterDraftError",
    "CharacterDraftService",
    "DRAFT_SYSTEM_PROMPT",
    "DraftContradiction",
    "DraftProviderConfig",
    "DraftQuestion",
    "ProviderCallable",
    "Readiness",
    "TARGET_AREAS",
    "build_semantic",
    "CharacterIdFactory",
    "new_character_id",
    "make_llm_provider",
    "parse_analysis_text",
    "parse_draft_text",
    "scripted_provider",
]
