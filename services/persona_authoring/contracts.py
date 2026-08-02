#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PAC v0 domain contracts -- immutable value types, approval-level enum,
and deterministic ФМДР validation.

All models are ``@dataclass(frozen=True)`` containing only detached plain
data. They never hold mutable state, live references, open handles, or
provider objects.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Tuple

# ---------------------------------------------------------------------------
# Approval level
# ---------------------------------------------------------------------------


class PacApprovalLevel(Enum):
    """Three distinct human approval levels per N9 §8."""

    ACCEPT_DRAFT = "accept_draft"
    APPROVE_SCENE = "approve_scene"
    APPROVE_DATASET = "approve_dataset"


PAC_APPROVAL_LEVELS: Tuple[PacApprovalLevel, ...] = (
    PacApprovalLevel.ACCEPT_DRAFT,
    PacApprovalLevel.APPROVE_SCENE,
    PacApprovalLevel.APPROVE_DATASET,
)

# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PacRequest:
    """A single author generation request -- exactly one target persona.

    Fields match the canonical ``context`` and top-level metadata required
    by ``pac-training-example-v1``.
    """

    character_id: str
    """Target persona identifier (exactly one per request -- D3)."""

    level: str
    """Scene level, e.g. ``"U3-A"``, ``"U4"``."""

    situation: str
    """Free-text description of the scene situation."""

    author_instruction: str
    """Author instruction to the model, e.g. ``"сдержанная радость"``."""

    provider: str
    """Explicit provider: ``"mock"``, ``"local"``, or ``"cloud"``."""

    model: str
    """Explicit model identifier, e.g. ``"llama3"``, ``"gpt-4o-mini"``."""

    variant_count: int = 3
    """Must be exactly 2 or 3. Rejected otherwise before provider call."""


@dataclass(frozen=True)
class PacVariant:
    """One generated scene variant with validation result."""

    index: int
    """Zero-based variant index within the generation."""

    raw_text: str
    """Immutable raw provider output for this variant."""

    fmdr_valid: bool
    """Did deterministic ФМДР validation pass?"""

    thoughts: Optional[str] = None
    """Parsed мысли layer, or ``None`` when absent."""

    actions: Optional[str] = None
    """Parsed действия layer, or ``None`` when absent."""

    speech: Optional[str] = None
    """Parsed речь layer, or ``None`` when absent."""

    fmdr_error: Optional[str] = None
    """Validation error message when ``fmdr_valid`` is ``False``."""


@dataclass(frozen=True)
class PacGeneration:
    """The complete result of one generation request."""

    run_id: str
    """Stable unique run identifier (timestamp + uuid prefix)."""

    request: PacRequest
    """The original request that produced this generation."""

    variants: Tuple[PacVariant, ...]
    """Exactly 2 or 3 validated variants."""

    created_at: str
    """ISO-8601 UTC timestamp of generation."""

    canon_snapshot: dict
    """Gateway provenance snapshot (source_commit + modules)."""

    system_prompt: Optional[str] = None
    """The assembled system prompt sent to the provider (for audit)."""


# ---------------------------------------------------------------------------
# Approval event
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PacApprovalEvent:
    """Evidence of one explicit human approval action."""

    run_id: str
    """Which generation/run this approval applies to."""

    level: PacApprovalLevel
    """Which approval level was granted."""

    variant_index: Optional[int] = None
    """Which variant was selected (only for ACCEPT_DRAFT)."""

    example_id: Optional[str] = None
    """Stable unique ID for the dataset record (only for APPROVE_DATASET)."""

    approved_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    """ISO-8601 UTC timestamp of approval."""


# ---------------------------------------------------------------------------
# Training example (pac-training-example-v1)
# ---------------------------------------------------------------------------


_ALLOWED_PROVENANCE = frozenset(
    {"human-written", "human-edited", "model-raw-approved"}
)
_ALLOWED_PROVIDERS = frozenset({"local", "cloud", "mock"})


@dataclass(frozen=True)
class PacTrainingExample:
    """One ``pac-training-example-v1`` record ready for JSONL append.

    Every field matches the canonical schema defined in
    ``docs/narrative/PAC_TRAINING_DATASET_SCHEMA_v1.md`` §3.
    """

    example_id: str
    """Stable UUID v4."""

    created_at: str
    """ISO-8601 UTC."""

    character_id: str
    """Target persona identifier."""

    authoring_session_id: str
    """Session UUID v4 (shared across examples in one session)."""

    provider: str
    """``"local"`` or ``"cloud"``."""

    model: str
    """Model identifier."""

    canon_snapshot: dict
    """``source_commit`` + ``modules[]`` with hashes from Gateway."""

    context: dict
    """``level``, ``situation``, ``author_instruction``, ``fmdr_required``."""

    model_output_raw: str
    """Immutable raw provider output (never used as training target)."""

    approved_output: str
    """Human-approved text (only this goes to N8 training)."""

    provenance: str
    """``human-written``, ``human-edited``, or ``model-raw-approved``."""

    quality_status: str = "approved"
    """Only ``"approved"`` in v0 main dataset."""

    edit_metrics: dict = field(default_factory=lambda: {"was_edited": True})
    """v0 minimal metric."""

    gates: dict = field(
        default_factory=lambda: {
            "fmdr_valid": True,
            "speech_uniqueness_pass": True,
            "canon_reviewed_by_human": True,
        }
    )
    """Quality gates passed."""

    scene_id: Optional[str] = None
    """Optional scene identifier."""

    schema_version: str = "pac-training-example-v1"
    """Canonical schema identifier."""

    def to_dict(self) -> dict:
        """Serialize to the exact canonical JSONL structure."""
        return {
            "schema_version": self.schema_version,
            "example_id": self.example_id,
            "created_at": self.created_at,
            "character_id": self.character_id,
            "scene_id": self.scene_id,
            "authoring_session_id": self.authoring_session_id,
            "provider": self.provider,
            "model": self.model,
            "canon_snapshot": self.canon_snapshot,
            "context": self.context,
            "model_output_raw": self.model_output_raw,
            "approved_output": self.approved_output,
            "provenance": self.provenance,
            "quality_status": self.quality_status,
            "edit_metrics": self.edit_metrics,
            "gates": self.gates,
        }

    def validate_enum_values(self) -> list[str]:
        """Return a list of validation error messages (empty = valid)."""
        errors: list[str] = []
        if self.provenance not in _ALLOWED_PROVENANCE:
            errors.append(
                f"provenance must be one of {sorted(_ALLOWED_PROVENANCE)}, "
                f"got {self.provenance!r}"
            )
        if self.provider not in _ALLOWED_PROVIDERS:
            errors.append(
                f"provider must be one of {sorted(_ALLOWED_PROVIDERS)}, "
                f"got {self.provider!r}"
            )
        if self.quality_status != "approved":
            errors.append(
                f"quality_status must be 'approved' in v0, got {self.quality_status!r}"
            )
        if not self.model_output_raw:
            errors.append("model_output_raw must not be empty")
        if not self.approved_output:
            errors.append("approved_output must not be empty")
        try:
            uuid.UUID(self.example_id)
        except (ValueError, AttributeError):
            errors.append(f"example_id must be a valid UUID v4: {self.example_id!r}")
        try:
            uuid.UUID(self.authoring_session_id)
        except (ValueError, AttributeError):
            errors.append(
                f"authoring_session_id must be a valid UUID v4: "
                f"{self.authoring_session_id!r}"
            )
        return errors


# ---------------------------------------------------------------------------
# ФМДР deterministic validation
# ---------------------------------------------------------------------------

# Canonical ФМДР syntax per N9:
#   (Мысли: ...) → *Действия: ...* → «Речь: ...»
#
# Each layer is optional independently.  The canonical separator is " → ".
# We allow leading/trailing whitespace around separators and layers.
#
# Two formats are accepted:
#   A. Inline: (Мысли: text) *Действия: text* «Речь: text»
#   B. Header:  МЫСЛЬ:\ntext\n\nДЕЙСТВИЕ:\n*text*\n\nРЕЧЬ:\n«text»
#
# Variants allowed for each label:
#   Thought:  МЫСЛЬ / МЫСЛИ / THOUGHT / THOUGHTS  (case-insensitive)
#   Action:   ДЕЙСТВИЕ / ДЕЙСТВИЯ / ACTION / ACTIONS
#   Speech:   РЕЧЬ / SPEECH

_THOUGHT_LABEL = r"(?:МЫСЛ[ИЬ]|THOUGHTS?|мысли|мысль|thoughts?)"
_ACTION_LABEL = r"(?:ДЕЙСТВИ[ЕЯ]|ACTIONS?|действи[ея]|actions?)"
_SPEECH_LABEL = r"(?:РЕЧЬ|SPEECH|речь|speech)"

# Format A: inline parenthesized thoughts
_FMDR_THOUGHTS_INLINE_RE = re.compile(
    r"\(\s*" + _THOUGHT_LABEL + r"\s*:\s*(.*?)\s*\)",
    re.DOTALL | re.IGNORECASE,
)

# Format B: header-style МЫСЛЬ:\n... (content runs until next header or marker)
_FMDR_THOUGHTS_HEADER_RE = re.compile(
    r"(?:^|\n)\s*" + _THOUGHT_LABEL + r"\s*:\s*\n(.*?)(?=\n\s*(?:" + _ACTION_LABEL + r"|" + _SPEECH_LABEL + r")\s*:\s*\n|\n\s*\*|\n\s*«|\Z)",
    re.DOTALL | re.IGNORECASE,
)

# Format B: header-style ДЕЙСТВИЕ:\n*...* or *text*
_FMDR_ACTIONS_HEADER_RE = re.compile(
    r"(?:^|\n)\s*" + _ACTION_LABEL + r"\s*:\s*\n\s*\*\s*(.*?)\s*\*",
    re.DOTALL | re.IGNORECASE,
)

# Legacy inline actions: *Действия: ...* or just *...*
_FMDR_ACTIONS_INLINE_RE = re.compile(
    r"\*\s*(?:" + _ACTION_LABEL + r"\s*:\s*)?(.*?)\s*\*",
    re.DOTALL | re.IGNORECASE,
)

# Inline speech: «Речь: ...» or just «...»
_FMDR_SPEECH_RE = re.compile(
    r"«\s*(?:" + _SPEECH_LABEL + r"\s*:\s*)?(.*?)\s*»",
    re.DOTALL | re.IGNORECASE,
)

# Header speech: РЕЧЬ:\n«...» 
_FMDR_SPEECH_HEADER_RE = re.compile(
    r"(?:^|\n)\s*" + _SPEECH_LABEL + r"\s*:\s*\n\s*«\s*(.*?)\s*»",
    re.DOTALL | re.IGNORECASE,
)

# A minimal structural check: the text must contain at least one canonical layer.
_FMDR_MINIMAL_RE = re.compile(
    r"[\(（\*«]|\b(?:МЫСЛ[ИЬ]|ДЕЙСТВИ[ЕЯ]|РЕЧЬ|THOUGHTS?|ACTIONS?|SPEECH)\b",
    re.IGNORECASE,
)


def validate_fmdr(text: str) -> Tuple[bool, Optional[str], Optional[str], Optional[str], Optional[str]]:
    """Validate one variant against canonical ФМДР structure.

    Args:
        text: The raw provider output for a single variant.

    Returns:
        A tuple of ``(valid, thoughts, actions, speech, error)``.
        When ``valid`` is ``True``, ``error`` is ``None`` and at least one
        of ``thoughts``, ``actions``, ``speech`` is not ``None``.
        When ``valid`` is ``False``, the layer fields are ``None``.
    """
    if not isinstance(text, str) or not text.strip():
        return (False, None, None, None, "variant text is empty or not a string")

    stripped = text.strip()

    # Canon requires at least one layer to be present.
    if not _FMDR_MINIMAL_RE.search(stripped):
        return (
            False,
            None,
            None,
            None,
            "no ФМДР layer markers found: expected Мысль/Мысли/Thought:..., Действие/Action:..., or Речь/Speech:...",
        )

    # Try header-style thoughts first (МЫСЛЬ:\ntext...), then inline ((Мысли: text))
    thoughts_match = _FMDR_THOUGHTS_HEADER_RE.search(stripped)
    if thoughts_match:
        thoughts = thoughts_match.group(1).strip()
    else:
        thoughts_match = _FMDR_THOUGHTS_INLINE_RE.search(stripped)
        thoughts = thoughts_match.group(1).strip() if thoughts_match else None

    # Try header-style actions first (ДЕЙСТВИЕ:\n*text*), then inline
    actions_match = _FMDR_ACTIONS_HEADER_RE.search(stripped)
    if actions_match:
        actions = actions_match.group(1).strip()
    else:
        actions_match = _FMDR_ACTIONS_INLINE_RE.search(stripped)
        actions = actions_match.group(1).strip() if actions_match else None

    # Try header-style speech first (РЕЧЬ:\n«text»), then inline
    speech_match = _FMDR_SPEECH_HEADER_RE.search(stripped)
    if speech_match:
        speech = speech_match.group(1).strip()
    else:
        speech_match = _FMDR_SPEECH_RE.search(stripped)
        speech = speech_match.group(1).strip() if speech_match else None

    if thoughts is None and actions is None and speech is None:
        return (
            False,
            None,
            None,
            None,
            "no valid ФМДР layer parsed: check delimiters and labels",
        )

    # When both action and speech are present, thought is mandatory.
    if actions is not None and speech is not None and (thoughts is None or thoughts.strip() == ""):
        return (
            False,
            None,
            None,
            None,
            "ФМДР thought block is missing or empty: all three layers required when action and speech are present",
        )

    # All parsed layers found -- valid.
    return (True, thoughts, actions, speech, None)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def generate_run_id() -> str:
    """Produce a collision-safe run identifier (timestamp + uuid prefix)."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    short = uuid.uuid4().hex[:8]
    return f"{ts}-{short}"


def new_uuid() -> str:
    """Return a canonical UUID v4 string."""
    return str(uuid.uuid4())


def utc_now_iso() -> str:
    """Return current UTC time as ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()