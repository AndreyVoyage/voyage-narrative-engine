"""AI-first character draft orchestration: analysis, interview, draft build.

The service is offline and provider-agnostic: the provider is injected as a
plain callable.  It never approves, publishes, designates, or exports anything;
it only produces a validated ``CharacterSemantic`` ready for DRAFT persistence.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable

from services.character_authoring import CharacterSemantic

from .contracts import AnalysisResult, CharacterDraftError, Readiness, parse_analysis_text
from .draft_builder import build_semantic, parse_draft_text
from .provider import ANALYSIS_SYSTEM_PROMPT, DRAFT_SYSTEM_PROMPT, ProviderCallable


CharacterIdFactory = Callable[[], str]


def new_character_id() -> str:
    """Generate an opaque, stable, ASCII-safe character identity.

    OD-LAB-CHARACTER-ID-01: character_id represents stable CHARACTER IDENTITY
    and MUST NOT be derived from display name, description, or any semantic
    content.  Initial version/revision stay "v1"/"r1", scoped beneath this
    unique character identity.
    """
    return "char_" + uuid.uuid4().hex


class CharacterDraftService:
    """Stateful AI-first creation flow: analyze -> interview -> build Draft."""

    DEFAULT_MAX_ROUNDS = 8

    def __init__(
        self,
        provider: ProviderCallable,
        *,
        max_rounds: int = DEFAULT_MAX_ROUNDS,
        character_id_factory: CharacterIdFactory | None = None,
    ) -> None:
        self._provider = provider
        self._max_rounds = max_rounds
        self._character_id_factory = character_id_factory or new_character_id
        self._display_name = ""
        self._description = ""
        self._history: list[dict[str, str]] = []
        self._rounds = 0
        self._analysis: AnalysisResult | None = None

    @property
    def display_name(self) -> str:
        return self._display_name

    @property
    def description(self) -> str:
        return self._description

    @property
    def analysis(self) -> AnalysisResult | None:
        return self._analysis

    def analyze(self, display_name: str, description: str) -> AnalysisResult:
        if not isinstance(display_name, str) or not display_name.strip():
            raise CharacterDraftError("character name must be a non-empty string")
        if not isinstance(description, str) or not description.strip():
            raise CharacterDraftError("character description must be a non-empty string")
        self._display_name = display_name.strip()
        self._description = description.strip()
        self._history = [{"role": "user", "content": self._description}]
        self._rounds = 0
        self._analysis = self._run_analysis()
        return self._analysis

    def answer(self, text: str) -> AnalysisResult:
        if self._analysis is None:
            raise CharacterDraftError("call analyze() before answer()")
        if not isinstance(text, str) or not text.strip():
            raise CharacterDraftError("answer must be a non-empty string")
        if self._analysis.readiness is Readiness.READY_FOR_DRAFT:
            return self._analysis
        if self._rounds >= self._max_rounds:
            raise CharacterDraftError(
                "too many interview rounds; build the draft now or start over"
            )
        self._history.append(
            {
                "role": "assistant",
                "content": json.dumps(self._analysis.to_dict(), ensure_ascii=False),
            }
        )
        self._history.append({"role": "user", "content": text.strip()})
        self._analysis = self._run_analysis()
        return self._analysis

    def build_draft(self, *, force: bool = False) -> CharacterSemantic:
        if self._analysis is None:
            raise CharacterDraftError("call analyze() before build_draft()")
        if self._analysis.readiness is not Readiness.READY_FOR_DRAFT and not force:
            raise CharacterDraftError(
                "character is not ready for a draft; answer more questions or "
                "force a draft"
            )
        self._history.append(
            {
                "role": "assistant",
                "content": json.dumps(self._analysis.to_dict(), ensure_ascii=False),
            }
        )
        text = self._provider(self._history, DRAFT_SYSTEM_PROMPT)
        semantic = parse_draft_text(text)
        return build_semantic(semantic, display_name=self._display_name)

    def create_character_id(self) -> str:
        """Return a fresh opaque character identity via the injected factory."""
        return self._character_id_factory()

    def _run_analysis(self) -> AnalysisResult:
        self._rounds += 1
        text = self._provider(self._history, ANALYSIS_SYSTEM_PROMPT)
        return parse_analysis_text(text)


__all__ = ["CharacterDraftService", "CharacterIdFactory", "new_character_id"]
