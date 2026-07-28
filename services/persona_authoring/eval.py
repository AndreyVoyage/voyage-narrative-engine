#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PAC v0 minimal evaluation contour.

Implements the fixed 36-probe eval set with human calibration and
min-per-turn scoring per N9 v1.2 §10.  No LLM judge in v0.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .errors import PacError
from .storage import PacStorage

# Canonical probe counts
PROBE_COUNT = 36
PROBES_PER_CATEGORY = 12
REQUIRED_CATEGORIES = frozenset({"A", "B", "C"})


@dataclass(frozen=True)
class PacEvalProbe:
    """One fixed evaluation probe per N9 §10."""

    probe_id: str
    probe_version: str
    character_id: str
    category: str  # "A", "B", or "C"
    scene_context: str
    point_in_time: str
    prompt: str
    required_gateway_sources: tuple[str, ...]
    expected_character_signals: str
    forbidden_claims: str
    fmdr_requirements: str
    human_rubric: str
    judge_rubric: str


@dataclass(frozen=True)
class PacEvalResult:
    """Result of running the probe set."""

    run_id: str
    probe_set_version: str
    provider: str
    model: str
    character_id: str
    per_probe_results: tuple[dict[str, Any], ...]
    per_turn_scores: tuple[dict[str, Any], ...]
    aggregate_score: dict[str, Any]
    calibration: Optional[dict[str, Any]] = None


class PacEvalService:
    """v0 evaluation service -- fixed probes, no LLM judge."""

    def __init__(
        self,
        storage: PacStorage,
        probe_dir: Optional[Path] = None,
    ) -> None:
        self._storage = storage
        self._probe_dir = probe_dir or Path("tests/persona_authoring/probes")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_probes(self, character_id: Optional[str] = None) -> list[PacEvalProbe]:
        """Load and validate exactly 36 probes from the tracked probe directory.

        Args:
            character_id: Optional filter. When provided, only probes for
                          that character are returned.

        Returns:
            Exactly 36 ``PacEvalProbe`` instances (or fewer when filtered).

        Raises:
            PacError: When probe count, categories, or IDs are invalid.
        """
        if not self._probe_dir.is_dir():
            raise PacError(f"probe directory not found: {self._probe_dir}")

        probes: list[PacEvalProbe] = []
        seen_ids: set[str] = set()

        for probe_file in sorted(self._probe_dir.glob("*.json")):
            data = json.loads(probe_file.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise PacError(f"probe file must be a JSON object: {probe_file}")

            # Support single probes and grouped arrays.
            items = data.get("probes", [data]) if "probes" in data else [data]
            for item in items:
                probe = PacEvalProbe(
                    probe_id=item["probe_id"],
                    probe_version=item["probe_version"],
                    character_id=item["character_id"],
                    category=item["category"],
                    scene_context=item["scene_context"],
                    point_in_time=item["point_in_time"],
                    prompt=item["prompt"],
                    required_gateway_sources=tuple(
                        item.get("required_gateway_sources", [])
                    ),
                    expected_character_signals=item["expected_character_signals"],
                    forbidden_claims=item["forbidden_claims"],
                    fmdr_requirements=item["fmdr_requirements"],
                    human_rubric=item["human_rubric"],
                    judge_rubric=item["judge_rubric"],
                )

                if probe.probe_id in seen_ids:
                    raise PacError(f"duplicate probe_id: {probe.probe_id!r}")
                seen_ids.add(probe.probe_id)

                if probe.category not in REQUIRED_CATEGORIES:
                    raise PacError(
                        f"invalid category {probe.category!r} in probe "
                        f"{probe.probe_id!r}"
                    )

                if character_id and probe.character_id != character_id:
                    continue

                probes.append(probe)

        # Validate counts (when not filtered by character).
        if character_id is None:
            if len(probes) != PROBE_COUNT:
                raise PacError(
                    f"expected exactly {PROBE_COUNT} probes, got {len(probes)}"
                )

            category_counts: dict[str, int] = {}
            for p in probes:
                category_counts[p.category] = category_counts.get(p.category, 0) + 1

            for cat in REQUIRED_CATEGORIES:
                count = category_counts.get(cat, 0)
                if count != PROBES_PER_CATEGORY:
                    raise PacError(
                        f"category {cat!r}: expected {PROBES_PER_CATEGORY} probes, "
                        f"got {count}"
                    )

        return probes

    def validate_probe_set(
        self, probes: list[PacEvalProbe]
    ) -> dict[str, Any]:
        """Return validation metadata for a probe set."""
        return {
            "probe_count": len(probes),
            "probe_ids": [p.probe_id for p in probes],
            "probe_set_version": probes[0].probe_version if probes else "unknown",
            "categories": {
                cat: sum(1 for p in probes if p.category == cat)
                for cat in REQUIRED_CATEGORIES
            },
        }

    def build_eval_result(
        self,
        run_id: str,
        probes: list[PacEvalProbe],
        per_probe_results: list[dict[str, Any]],
        provider: str,
        model: str,
        character_id: str,
        calibration: Optional[dict[str, Any]] = None,
    ) -> PacEvalResult:
        """Assemble eval results with min-per-turn aggregation.

        ``per_probe_results``: One dict per probe containing at minimum:
            ``{"probe_id": str, "score": float, "notes": str}``
        """
        turn_scores = []
        for r in per_probe_results:
            turn_scores.append(
                {
                    "probe_id": r.get("probe_id", "unknown"),
                    "score": r.get("score", 0.0),
                    "notes": r.get("notes", ""),
                }
            )

        scores = [s["score"] for s in turn_scores]
        min_score = min(scores) if scores else 0.0
        avg_score = sum(scores) / len(scores) if scores else 0.0

        aggregate = {
            "min_per_turn": min_score,
            "average": avg_score,
            "total_probes": len(probes),
            "scores": scores,
        }

        return PacEvalResult(
            run_id=run_id,
            probe_set_version=probes[0].probe_version if probes else "unknown",
            provider=provider,
            model=model,
            character_id=character_id,
            per_probe_results=tuple(per_probe_results),
            per_turn_scores=tuple(turn_scores),
            aggregate_score=aggregate,
            calibration=calibration,
        )

    def save_eval_results(self, result: PacEvalResult) -> Path:
        """Persist eval results to storage."""
        data = {
            "run_id": result.run_id,
            "probe_set_version": result.probe_set_version,
            "provider": result.provider,
            "model": result.model,
            "character_id": result.character_id,
            "per_probe_results": list(result.per_probe_results),
            "per_turn_scores": list(result.per_turn_scores),
            "aggregate_score": result.aggregate_score,
            "calibration": result.calibration,
        }
        return self._storage.save_eval_results(result.run_id, data)

    def save_calibration(
        self, run_id: str, calibration: dict[str, Any]
    ) -> Path:
        """Persist manual calibration evidence."""
        return self._storage.save_calibration(run_id, calibration)