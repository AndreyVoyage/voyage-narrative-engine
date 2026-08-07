#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CIS Kira Pilot -- Slice 1 CIS-arm context assembly.

Builds the CIS-arm assembled context (P0 + P3 + P4 + an explicitly absent
event/memory layer) as a structured, layer-distinguishable object, and
renders it into the same ``list[dict[str, str]]`` provider-message shape
produced by ``baseline_adapter.py`` / ``tools.aside_context_builder.build_context()``,
for judge-side symmetry (spec §16).

This module never reads a file, never calls a provider, never mutates its
inputs, and never imports ``baseline_adapter.py`` or
``tools.aside_context_builder`` -- the two arms are separate,
non-converging code paths by construction (spec §16 causal-control
requirement; plan §7). Depends only on ``tools/cis_pilot/contracts.py``
(Slice 0), unmodified.

The event/memory layer (WORLD_EVENT -> PERCEPTION -> INTERPRETATION ->
MEMORY) is Slice 2+ and is never invoked or approximated here: it is
always represented by the explicit absence marker ``None``, never
collapsed into P0/P3/P4, and never confused with an objective event
(CIS-Q6).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict

from .contracts import ContractValidationError, P0Snapshot, P3State, P4State


@dataclass(frozen=True)
class CisContextLayers:
    """The CIS-arm assembled context, kept as distinct, non-collapsed layers.

    ``memory_layer`` is always ``None`` in Slice 1 -- the event/memory
    pipeline is Slice 2+ and has no representation here beyond this
    explicit absence marker.
    """

    p0: P0Snapshot
    p3: P3State
    p4: P4State
    memory_layer: None
    scene_question: str

    def __post_init__(self) -> None:
        if not isinstance(self.p0, P0Snapshot):
            raise ContractValidationError("p0 must be a P0Snapshot instance")
        if not isinstance(self.p3, P3State):
            raise ContractValidationError("p3 must be a P3State instance")
        if not isinstance(self.p4, P4State):
            raise ContractValidationError("p4 must be a P4State instance")
        if self.memory_layer is not None:
            raise ContractValidationError(
                "memory_layer must be None in Slice 1 (event/memory pipeline is Slice 2+)"
            )
        if not isinstance(self.scene_question, str) or not self.scene_question.strip():
            raise ContractValidationError("scene_question must be a non-empty string")


def assemble_cis_context(
    p0: P0Snapshot,
    p3: P3State,
    p4: P4State,
    scene_question: str,
) -> CisContextLayers:
    """Pure, deterministic CIS-arm context assembly.

    Never reads a file, never calls a provider, never mutates ``p0``/``p3``/
    ``p4`` (all three are already-frozen dataclasses). The event/memory
    layer is always absent (``None``) -- Slice 1 performs no WORLD_EVENT ->
    PERCEPTION -> INTERPRETATION -> MEMORY transformation (that is Slice 2+).
    Structurally allows a combined P3+P4 change (both parameters are always
    present together) without running any probe/experiment -- Slice 1's
    task is to assemble structure, not to execute T3-COMBINED.
    """
    return CisContextLayers(
        p0=p0, p3=p3, p4=p4, memory_layer=None, scene_question=scene_question
    )


def render_cis_messages(context: CisContextLayers) -> list[dict[str, str]]:
    """Render ``CisContextLayers`` into provider messages.

    Same ``list[dict[str, str]]`` shape as
    ``baseline_adapter.build_baseline_messages`` /
    ``tools.aside_context_builder.build_context``, for judge-side symmetry
    (spec §16). Deterministic: stable field order (``sort_keys=True``), no
    timestamps, no randomness, no provider/model fields, no run IDs, no
    absolute machine paths (only the already repo-relative
    ``SourceArtifact.repo_relative_path`` values are used). The four layers
    remain textually separated (joined by a blank line) so each stays
    independently identifiable rather than collapsed into one blob.
    """
    system_content = "\n\n".join(
        [
            _render_p0_block(context.p0),
            _render_p3_block(context.p3),
            _render_p4_block(context.p4),
            _render_memory_block(),
        ]
    )
    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": context.scene_question.strip()},
    ]


def _render_p0_block(p0: P0Snapshot) -> str:
    modules: Dict[str, Dict[str, str]] = {
        name: {"path": artifact.repo_relative_path, "sha256": artifact.sha256}
        for name, artifact in (
            ("value_system", p0.value_system),
            ("base", p0.base),
            ("attachment", p0.attachment),
            ("defense_mechanisms", p0.defense_mechanisms),
            ("ifs_parts", p0.ifs_parts),
            ("odsc", p0.odsc),
        )
    }
    return (
        "P0 core psychological anchors (frozen, read-only, source-referenced "
        "-- not inlined in Slice 1):\n" + _stable_json(modules)
    )


def _render_p3_block(p3: P3State) -> str:
    return "P3 relationship state (pilot-scope, user):\n" + _stable_json(
        {"trust": p3.trust, "attraction": p3.attraction}
    )


def _render_p4_block(p4: P4State) -> str:
    return "P4 transient regulation state (pilot-scope):\n" + _stable_json(
        {"arousal": p4.arousal, "anxiety": p4.anxiety, "strategy": p4.strategy}
    )


def _render_memory_block() -> str:
    return (
        "Event/memory layer: absent in this slice (WORLD_EVENT -> PERCEPTION -> "
        "INTERPRETATION -> MEMORY is Slice 2+; not invoked, not approximated)."
    )


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)
