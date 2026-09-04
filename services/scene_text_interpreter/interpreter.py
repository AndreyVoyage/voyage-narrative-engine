#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scene Text Interpreter v0 -- top-level orchestration.

    build_interpreter_input(raw_scene_text, repo_root)
        -> closed allowlists (VNE-owned character + location alias tables,
           controlled scene-tag vocabulary)

    interpret_scene_text(raw_scene_text, repo_root, proposer)
        -> proposer.propose(input)              [UNTRUSTED]
        -> validate_and_build_plan(...)         [DETERMINISTIC, fail closed]
        -> frozen SceneStillPlan (status = "DRAFT")

No provider call, no network, no NCC read, no Canon mutation. The plan is an
authoring DRAFT and never represents accepted scene state.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .aliases import load_character_roster, load_location_roster
from .model import InterpreterInput, ProposedInterpretation, SceneStillPlan
from .proposer import SceneTextProposer
from .validation import validate_and_build_plan
from .vocab import SCENE_TAG_VOCAB_V0


def build_interpreter_input(
    raw_scene_text: str,
    *,
    repo_root: Path,
    min_characters_in_frame: int = 2,
    max_characters_in_frame: int = 2,
    still_candidate_count: int = 3,
) -> InterpreterInput:
    """Assemble the closed allowlists handed to the untrusted proposer."""
    return InterpreterInput(
        raw_scene_text=raw_scene_text,
        allowed_characters=load_character_roster(Path(repo_root)),
        allowed_locations=load_location_roster(Path(repo_root)),
        allowed_scene_tags=SCENE_TAG_VOCAB_V0,
        min_characters_in_frame=min_characters_in_frame,
        max_characters_in_frame=max_characters_in_frame,
        still_candidate_count=still_candidate_count,
    )


def _interpreter_meta(proposer: SceneTextProposer) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "provider": str(getattr(proposer, "provider", "unknown")),
        "model": str(getattr(proposer, "model", "unknown")),
        "mock": bool(getattr(proposer, "mock", True)),
    }
    # Optional, non-secret audit metadata a proposer may expose after propose().
    raw_sha = getattr(proposer, "raw_response_sha256", None)
    if isinstance(raw_sha, str) and raw_sha:
        meta["raw_response_sha256"] = raw_sha
    return meta


def interpret_scene_text(
    raw_scene_text: str,
    *,
    repo_root: Path,
    proposer: SceneTextProposer,
    min_characters_in_frame: int = 2,
    max_characters_in_frame: int = 2,
    still_candidate_count: int = 3,
) -> SceneStillPlan:
    """Interpret ordinary scene prose into a validated, frozen SceneStillPlan."""
    inp = build_interpreter_input(
        raw_scene_text,
        repo_root=repo_root,
        min_characters_in_frame=min_characters_in_frame,
        max_characters_in_frame=max_characters_in_frame,
        still_candidate_count=still_candidate_count,
    )
    proposal = proposer.propose(inp)
    if not isinstance(proposal, ProposedInterpretation):
        # A proposer may also hand back a raw dict; normalize once, still untrusted.
        proposal = ProposedInterpretation.from_dict(proposal)
    return validate_and_build_plan(
        proposal, inp, repo_root=Path(repo_root), interpreter_meta=_interpreter_meta(proposer)
    )
