#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CIS Kira Pilot -- Slice 0 internal pilot data contracts.

These are internal pilot contracts (per
``CIS_KIRA_PILOT_SPECIFICATION_v0.1_2026-08-05.md`` §7), not a production
API and not a canonical schema. Every type here is an immutable value
object: construction performs no I/O, reads no environment variables, and
never touches the filesystem or network. Values are validated in
``__post_init__`` so that a constructed instance is always internally
consistent; building one from real source data is the read-only source
loader's job (``tools/cis_pilot/source_loader.py``), not this module's.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Optional

_HEX_DIGITS = frozenset("0123456789abcdef")


class ContractValidationError(ValueError):
    """Raised when a pilot contract is constructed with invalid data."""


def _require_hex_digest(value: str, field_name: str, *, expected_length: int) -> None:
    if not isinstance(value, str) or len(value) != expected_length or any(
        c not in _HEX_DIGITS for c in value
    ):
        raise ContractValidationError(
            f"{field_name} must be a {expected_length}-char lowercase hex digest, got {value!r}"
        )


def _require_repo_relative_posix_path(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ContractValidationError(f"{field_name} must be a non-empty string")
    if "\\" in value:
        raise ContractValidationError(f"{field_name} must use POSIX separators ('/'), got {value!r}")
    if value.startswith("/"):
        raise ContractValidationError(f"{field_name} must be relative, not absolute: {value!r}")
    parts = value.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise ContractValidationError(f"{field_name} must not contain empty/'.'/'..' segments: {value!r}")


def _require_plain_int_in_range(value: object, field_name: str, *, low: int, high: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ContractValidationError(f"{field_name} must be a plain int (bool is not accepted)")
    if not low <= value <= high:
        raise ContractValidationError(f"{field_name} must be within {low}..{high}, got {value}")


# ---------------------------------------------------------------------------
# SourceArtifact
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceArtifact:
    """A read-only reference to one hashed source file.

    ``repo_relative_path`` is always POSIX-normalized and repo-relative --
    never an absolute local filesystem path (matches the existing Gateway
    ``Provenance.source`` convention in ``services/persona_gateway``).
    """

    repo_relative_path: str
    sha256: str
    kind: str
    json_path: Optional[str] = None
    module_id: Optional[str] = None

    def __post_init__(self) -> None:
        _require_repo_relative_posix_path(self.repo_relative_path, "repo_relative_path")
        _require_hex_digest(self.sha256, "sha256", expected_length=64)
        if not isinstance(self.kind, str) or not self.kind:
            raise ContractValidationError("kind must be a non-empty string")
        if self.json_path is not None and not isinstance(self.json_path, str):
            raise ContractValidationError("json_path must be a string or None")
        if self.module_id is not None and not isinstance(self.module_id, str):
            raise ContractValidationError("module_id must be a string or None")


# ---------------------------------------------------------------------------
# P0Snapshot
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class P0Snapshot:
    """Read-only references to the six frozen P0 modules (spec PD-5).

    ``psychology/ATTACHMENT_STYLE_DYNAMIC.json`` is intentionally absent --
    it is excluded from P0 entirely (dynamic, not static core) and is never
    represented by this contract.
    """

    value_system: SourceArtifact
    base: SourceArtifact
    attachment: SourceArtifact
    defense_mechanisms: SourceArtifact
    ifs_parts: SourceArtifact
    odsc: SourceArtifact


# ---------------------------------------------------------------------------
# P3State
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class P3State:
    """Pilot-scope relationship state -- trust/attraction only (spec PD-3).

    Deliberately has no ``resentment``, ``session_count``, or
    ``attachment_style`` field: these are either not canon fields
    (``resentment``) or frozen-baseline/not-injected in the pilot.
    """

    trust: int
    attraction: int

    def __post_init__(self) -> None:
        _require_plain_int_in_range(self.trust, "trust", low=0, high=100)
        _require_plain_int_in_range(self.attraction, "attraction", low=0, high=100)


# ---------------------------------------------------------------------------
# P4State
# ---------------------------------------------------------------------------

# The only four (arousal, anxiety) -> strategy combinations actually
# present in personas/kira/psychology/AFFECT_REGULATION.json. Categorical
# only -- there is no numeric arousal/anxiety scale in the source, so none
# is invented here.
ALLOWED_P4_STATES: Mapping[tuple, str] = MappingProxyType(
    {
        ("high", "low"): "approach",
        ("high", "high"): "avoidance",
        ("low", "high"): "seeking_reassurance",
        ("low", "low"): "exploration",
    }
)


@dataclass(frozen=True)
class P4State:
    """One source-backed P4 arousal/anxiety/strategy combination.

    Only the four combinations actually present in
    ``psychology/AFFECT_REGULATION.json`` are accepted; any other
    arousal/anxiety/strategy triple is rejected at construction.
    """

    arousal: str
    anxiety: str
    strategy: str

    def __post_init__(self) -> None:
        key = (self.arousal, self.anxiety)
        expected_strategy = ALLOWED_P4_STATES.get(key)
        if expected_strategy is None:
            raise ContractValidationError(
                f"(arousal={self.arousal!r}, anxiety={self.anxiety!r}) is not a source-backed "
                f"P4 state; allowed combinations are {sorted(ALLOWED_P4_STATES)}"
            )
        if expected_strategy != self.strategy:
            raise ContractValidationError(
                f"(arousal={self.arousal!r}, anxiety={self.anxiety!r}) -> strategy must be "
                f"{expected_strategy!r}, got {self.strategy!r}"
            )


# ---------------------------------------------------------------------------
# MemoryEventSource
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MemoryEventSource:
    """Provenance for one atomic WORLD_EVENT memory fixture (ME-1 / ME-2).

    ``literal_text`` is the exact, unmodified source string found at
    ``json_path``. ``normalized_text`` -- when present -- is a lightly
    normalized variant (e.g. an explicitly restored subject) and is stored
    separately; it never replaces ``literal_text``.
    """

    event_id: str
    scenario_repo_relative_path: str
    json_path: str
    literal_text: str
    sha256: str
    normalized_text: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.event_id, str) or not self.event_id:
            raise ContractValidationError("event_id must be a non-empty string")
        _require_repo_relative_posix_path(
            self.scenario_repo_relative_path, "scenario_repo_relative_path"
        )
        if not isinstance(self.json_path, str) or not self.json_path:
            raise ContractValidationError("json_path must be a non-empty string")
        if not isinstance(self.literal_text, str) or not self.literal_text:
            raise ContractValidationError("literal_text must be a non-empty string")
        _require_hex_digest(self.sha256, "sha256", expected_length=64)
        if self.normalized_text is not None and not isinstance(self.normalized_text, str):
            raise ContractValidationError("normalized_text must be a string or None")


# ---------------------------------------------------------------------------
# BaselineSourceSet
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BaselineSourceSet:
    """Read-only references to the frozen 4-module static baseline (PD-10).

    ``builder_source`` references ``tools/aside_context_builder.py`` itself
    -- called unmodified by later slices, never copied or reimplemented.
    """

    identity: SourceArtifact
    base: SourceArtifact
    speech_matrix: SourceArtifact
    matrix: SourceArtifact
    builder_source: SourceArtifact
    baseline_git_sha: str

    def __post_init__(self) -> None:
        _require_hex_digest(self.baseline_git_sha, "baseline_git_sha", expected_length=40)


# ---------------------------------------------------------------------------
# PilotSourceSnapshot
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PilotSourceSnapshot:
    """The complete, aggregated Slice 0 read-only source snapshot.

    Contains only confirmed source references and frozen-baseline values --
    never LLM-generated memory, gate decisions, relationship deltas,
    evolution proposals, or generation output (those belong to later
    slices, out of Slice 0 scope).
    """

    p0: P0Snapshot
    p3: P3State
    p4_strategy_map: Mapping[str, P4State]
    me1: MemoryEventSource
    me2: MemoryEventSource
    baseline: BaselineSourceSet
    repo_head_sha: str

    def __post_init__(self) -> None:
        if not isinstance(self.p4_strategy_map, MappingProxyType):
            raise ContractValidationError(
                "p4_strategy_map must be an immutable Mapping (MappingProxyType)"
            )
        if len(self.p4_strategy_map) != len(ALLOWED_P4_STATES):
            raise ContractValidationError(
                f"p4_strategy_map must have exactly {len(ALLOWED_P4_STATES)} entries, "
                f"got {len(self.p4_strategy_map)}"
            )
        for value in self.p4_strategy_map.values():
            if not isinstance(value, P4State):
                raise ContractValidationError("p4_strategy_map values must be P4State instances")
        _require_hex_digest(self.repo_head_sha, "repo_head_sha", expected_length=40)
