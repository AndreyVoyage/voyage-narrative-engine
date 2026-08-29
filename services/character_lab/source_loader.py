#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Character Lab accepted-source loader (repo-controlled, read-only).

Reads the frozen exact accepted source Candidate materialized alongside the
acceptance artifact, rehydrates it through the existing candidate-rehydration
path, and hands it to the existing ``load_accepted_character`` acceptance/hash
gate. This module never writes under ``accepted/**`` and never performs
acceptance validation itself.
"""

from __future__ import annotations

import json
from pathlib import Path

from services.character_runtime import CharacterRuntimeError, SourceLoader
from services.crp_authoring.candidate_package import CandidateCharacterPackage
from services.crp_authoring.candidate_rehydration import rehydrate_candidate_package

SOURCE_CANDIDATE_FILENAME = "source_candidate.json"
DEFAULT_ACCEPTANCE_ROOT = Path(__file__).resolve().parents[2] / "accepted"


def build_repo_source_loader(acceptance_root=None) -> SourceLoader:
    """Return a ``SourceLoader`` that rehydrates ``accepted/<id>/source_candidate.json``.

    The artifact is a bare ``candidate_package`` object (the exact accepted
    Candidate extracted from the one-time materialization step). Rehydration
    goes through ``rehydrate_candidate_package``; acceptance/hash verification
    remains the responsibility of ``load_accepted_character``.
    """
    root = Path(acceptance_root) if acceptance_root is not None else DEFAULT_ACCEPTANCE_ROOT

    def loader(subject_id: str) -> CandidateCharacterPackage:
        if not isinstance(subject_id, str) or not subject_id.strip():
            raise CharacterRuntimeError("subject_id must be a non-empty string")
        path = root / subject_id / SOURCE_CANDIDATE_FILENAME
        if not path.exists():
            raise CharacterRuntimeError(
                f"accepted source candidate artifact not found for subject "
                f"{subject_id!r}: {path}"
            )
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CharacterRuntimeError(
                f"accepted source candidate is not valid JSON: {exc}"
            ) from exc
        package = rehydrate_candidate_package(data)
        if package.subject_id != subject_id:
            raise CharacterRuntimeError(
                f"source subject {package.subject_id!r} != requested {subject_id!r}"
            )
        return package

    return loader
