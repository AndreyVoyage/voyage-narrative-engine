#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CIS Kira Pilot -- Slice 4 result package assembly.

Assembles the final per-run result package (plan §4/§10/§12): raw
per-sample generations, the seeded blind package with labels hidden
(randomization key kept SEPARATE), deterministic checks, a human judge
sheet skeleton, the final outcome, and the provenance manifest.

TD-14 (owner decision) placement notes:

* ``ProvenanceManifest`` is slice-local, defined HERE (not in
  ``provenance.py``), and REUSES the existing Slice 0 provenance
  primitives (``SourceArtifact`` contract, ``sha256_file``,
  ``get_head_sha``, ``build_source_artifact`` -- via the
  ``PilotSourceSnapshot`` produced by the source loader). No competing
  provenance infrastructure is created.
* ``generate_run_id()`` / ``utc_now_iso()`` are S4-local utilities in this
  module (``contracts.py`` is outside the Slice 4 write-set and is never
  touched).

Determinism discipline (plan §12/§13):

* VOLATILE fields: ``run_id`` and ``timestamp`` only (here and inside the
  manifest). Two fresh runs are never byte-identical by design.
* Everything else is the DETERMINISTIC payload: same frozen sources + same
  probe fixtures + same mock provider + same seed => identical
  ``deterministic_payload()``.
* All paths are repo-relative POSIX (enforced by the Slice 0
  ``SourceArtifact`` contract); no absolute machine path ever appears.

This module performs no file I/O of its own: persistence happens only
through ``storage.py`` (``persist_result_package``). Importing this module
creates nothing.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from random import Random
from types import MappingProxyType
from typing import Any, Dict, Mapping, Optional, Tuple

from .contracts import ContractValidationError, PilotSourceSnapshot, SourceArtifact
from .storage import CisPilotStorage


# ---------------------------------------------------------------------------
# S4-local run identity helpers (TD-14: live here, contracts.py untouched)
# ---------------------------------------------------------------------------


def utc_now_iso() -> str:
    """Current UTC time as an ISO-8601 string with a ``Z`` suffix."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def generate_run_id() -> str:
    """A fresh run id: UTC timestamp + uuid4 prefix (plan §12 pattern).

    VOLATILE by design -- reproducibility is anchored in the seed and the
    deterministic payload, never in run-id reuse.
    """
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{uuid.uuid4().hex[:8]}"


# ---------------------------------------------------------------------------
# ProbeSampleRecord
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProbeSampleRecord:
    """One tagged raw generation (plan §8 step 6).

    Tagged by ``probe_id`` / ``mode`` / ``state`` / ``arm`` /
    ``sample_index``. ``state`` and ``arm`` are ``None`` when a mode has no
    A/B state or no arm split (e.g. the PB-MEM chain trace). Never carries
    a run id, so the deterministic payload stays comparable across runs.
    """

    probe_id: str
    mode: str
    state: Optional[str]
    arm: Optional[str]
    sample_index: int
    generation: str
    tags: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_non_empty_str(self.probe_id, "probe_id")
        _require_non_empty_str(self.mode, "mode")
        if self.state is not None:
            _require_non_empty_str(self.state, "state")
        if self.arm is not None:
            _require_non_empty_str(self.arm, "arm")
        if isinstance(self.sample_index, bool) or not isinstance(self.sample_index, int):
            raise ContractValidationError("sample_index must be a plain int")
        if self.sample_index < 0:
            raise ContractValidationError("sample_index must be >= 0")
        if not isinstance(self.generation, str):
            raise ContractValidationError("generation must be a string")
        if not isinstance(self.tags, tuple):
            raise ContractValidationError("tags must be a tuple")
        for tag in self.tags:
            _require_non_empty_str(tag, "tag")

    def sample_key(self) -> Tuple[str, Optional[str], Optional[str], int]:
        """The resume/dedup identity of this sample."""
        return (self.probe_id, self.state, self.arm, self.sample_index)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "probe_id": self.probe_id,
            "mode": self.mode,
            "state": self.state,
            "arm": self.arm,
            "sample_index": self.sample_index,
            "generation": self.generation,
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ProbeSampleRecord":
        """Rebuild one record from its ``to_dict`` form (fail closed)."""
        if not isinstance(data, Mapping):
            raise ContractValidationError("sample record must be a mapping")
        try:
            return cls(
                probe_id=data["probe_id"],
                mode=data["mode"],
                state=data.get("state"),
                arm=data.get("arm"),
                sample_index=data["sample_index"],
                generation=data["generation"],
                tags=tuple(data.get("tags") or ()),
            )
        except KeyError as exc:
            raise ContractValidationError(f"sample record missing field: {exc}") from None


# ---------------------------------------------------------------------------
# ProvenanceManifest (slice-local per TD-14; reuses Slice 0 primitives)
# ---------------------------------------------------------------------------


def collect_source_artifacts(snapshot: PilotSourceSnapshot) -> Tuple[SourceArtifact, ...]:
    """Collect every hashed source artifact of the frozen pilot snapshot.

    Pure assembly from the Slice 0 ``PilotSourceSnapshot`` -- P0 x6, the
    frozen baseline source set (PD-10), and the ME-1/ME-2 memory fixtures
    (converted to ``SourceArtifact`` carrying their exact JSON paths).
    De-duplicated by repo-relative path; order is deterministic (sorted).
    """
    if not isinstance(snapshot, PilotSourceSnapshot):
        raise ContractValidationError("snapshot must be a PilotSourceSnapshot instance")
    by_path: Dict[str, SourceArtifact] = {}
    for artifact in (
        snapshot.p0.value_system,
        snapshot.p0.base,
        snapshot.p0.attachment,
        snapshot.p0.defense_mechanisms,
        snapshot.p0.ifs_parts,
        snapshot.p0.odsc,
        snapshot.baseline.identity,
        snapshot.baseline.speech_matrix,
        snapshot.baseline.builder_source,
    ):
        by_path[artifact.repo_relative_path] = artifact
    # The frozen P3 module (relationships/MATRIX.json) is part of the
    # baseline source set; P4 (AFFECT_REGULATION) is represented through the
    # validated strategy map -- its raw module bytes are read and hashed by
    # the Slice 0 loader during snapshot construction.
    by_path[snapshot.baseline.matrix.repo_relative_path] = snapshot.baseline.matrix
    for memory_source in (snapshot.me1, snapshot.me2):
        artifact = SourceArtifact(
            repo_relative_path=memory_source.scenario_repo_relative_path,
            sha256=memory_source.sha256,
            kind="memory_fixture",
            json_path=memory_source.json_path,
        )
        by_path[artifact.repo_relative_path] = artifact
    return tuple(by_path[path] for path in sorted(by_path))


@dataclass(frozen=True)
class ProvenanceManifest:
    """One run's provenance manifest (plan §12).

    Slice-local (TD-14). ``run_id`` and ``timestamp`` are VOLATILE; every
    other field is part of the deterministic payload. ``params`` is stored
    as an immutable mapping.
    """

    run_id: str
    timestamp: str
    repo_head_sha: str
    source_artifacts: Tuple[SourceArtifact, ...]
    probe_set_version: str
    probe_set_sha256: str
    provider: str
    model: str
    params: Mapping[str, Any]
    per_sample_refs: Tuple[ProbeSampleRecord, ...]

    def __post_init__(self) -> None:
        _require_non_empty_str(self.run_id, "run_id")
        _require_non_empty_str(self.timestamp, "timestamp")
        _require_hex(self.repo_head_sha, "repo_head_sha", 40)
        if not isinstance(self.source_artifacts, tuple) or not self.source_artifacts:
            raise ContractValidationError("source_artifacts must be a non-empty tuple")
        for artifact in self.source_artifacts:
            if not isinstance(artifact, SourceArtifact):
                raise ContractValidationError("source_artifacts must be SourceArtifact instances")
        _require_non_empty_str(self.probe_set_version, "probe_set_version")
        _require_hex(self.probe_set_sha256, "probe_set_sha256", 64)
        _require_non_empty_str(self.provider, "provider")
        _require_non_empty_str(self.model, "model")
        if not isinstance(self.params, Mapping):
            raise ContractValidationError("params must be a mapping")
        object.__setattr__(self, "params", MappingProxyType(dict(self.params)))
        if not isinstance(self.per_sample_refs, tuple):
            raise ContractValidationError("per_sample_refs must be a tuple")
        for ref in self.per_sample_refs:
            if not isinstance(ref, ProbeSampleRecord):
                raise ContractValidationError("per_sample_refs must be ProbeSampleRecord instances")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "repo_head_sha": self.repo_head_sha,
            "source_artifacts": [
                {
                    "repo_relative_path": a.repo_relative_path,
                    "sha256": a.sha256,
                    "kind": a.kind,
                    "json_path": a.json_path,
                    "module_id": a.module_id,
                }
                for a in self.source_artifacts
            ],
            "probe_set_version": self.probe_set_version,
            "probe_set_sha256": self.probe_set_sha256,
            "provider": self.provider,
            "model": self.model,
            "params": {key: self.params[key] for key in sorted(self.params)},
            "per_sample_refs": [ref.to_dict() for ref in self.per_sample_refs],
        }

    def deterministic_payload(self) -> Dict[str, Any]:
        """The manifest minus its VOLATILE fields (``run_id``/``timestamp``)."""
        payload = self.to_dict()
        del payload["run_id"]
        del payload["timestamp"]
        return payload


# ---------------------------------------------------------------------------
# Blind package (labels hidden; randomization key SEPARATE)
# ---------------------------------------------------------------------------


def build_blind_package(
    samples: Tuple[ProbeSampleRecord, ...], *, seed: int
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Seeded-shuffle blind package + separate randomization key.

    The blind package shown to a judge contains ONLY blind ids and raw
    generations -- never ``probe_id``, ``state``, ``arm``, ``character_id``
    or any other label (plan §10, spec §15). The mapping back to the labels
    lives exclusively in the returned randomization key, which is persisted
    to a SEPARATE file. Reproducibility: same samples + same seed => same
    shuffle (plan §12).
    """
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ContractValidationError("seed must be a plain int")
    order = list(range(len(samples)))
    Random(seed).shuffle(order)

    blind_items = []
    mapping = []
    for blind_index, sample_index in enumerate(order):
        sample = samples[sample_index]
        blind_id = f"blind-{blind_index:04d}"
        blind_items.append({"blind_id": blind_id, "generation": sample.generation})
        mapping.append(
            {
                "blind_id": blind_id,
                "probe_id": sample.probe_id,
                "mode": sample.mode,
                "state": sample.state,
                "arm": sample.arm,
                "sample_index": sample.sample_index,
            }
        )

    blind_package = {
        "kind": "cis_pilot_blind_package",
        "labels_hidden": True,
        "item_count": len(blind_items),
        "items": blind_items,
        "note": (
            "Labels (probe_id/state/arm/character identity) are intentionally "
            "absent; the mapping lives ONLY in the separately stored "
            "randomization key."
        ),
    }
    randomization_key = {
        "kind": "cis_pilot_randomization_key",
        "seed": seed,
        "mapping": mapping,
        "note": (
            "SEPARATE from the blind package by design (spec §15 blind "
            "discipline); never show to the judge."
        ),
    }
    return blind_package, randomization_key


def build_human_judge_sheet(blind_package: Mapping[str, Any], *, mode: str) -> Dict[str, Any]:
    """Human judge sheet skeleton (TD-4: flat JSON, one record per blind
    item, free verdict fields, no leading questions)."""
    if not isinstance(blind_package, Mapping):
        raise ContractValidationError("blind_package must be a mapping")
    items = blind_package.get("items")
    if not isinstance(items, list):
        raise ContractValidationError("blind_package must carry an items list")
    return {
        "kind": "cis_pilot_human_judge_sheet",
        "mode": mode,
        "status": "PENDING_HUMAN_REVIEW",
        "instructions": [
            "Judge each item blind; do not ask which character or state produced it.",
            "No leading questions are included by design.",
            "For PB-LEAK items: an auto PASS is never final -- human confirmation required.",
        ],
        "items": [
            {"blind_id": item["blind_id"], "verdict": "", "notes": ""} for item in items
        ],
    }


# ---------------------------------------------------------------------------
# ResultPackage
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResultPackage:
    """The complete per-run result package (plan §4/§12).

    VOLATILE: ``run_id``, ``timestamp`` (and the same two fields inside
    ``manifest``). Everything else is deterministic given the same frozen
    sources, probe fixtures, mock provider, and seed.
    """

    run_id: str
    timestamp: str
    mode: str
    sub_mode: Optional[str]
    probe_set_version: str
    probe_set_sha256: str
    fixture_identity: str
    manifest: ProvenanceManifest
    baseline_source_identity: Mapping[str, Any]
    initial_p3: Optional[Mapping[str, Any]]
    initial_p4: Optional[Mapping[str, Any]]
    samples: Tuple[ProbeSampleRecord, ...]
    memory_trace: Tuple[Mapping[str, Any], ...] = ()
    relationship_decisions: Tuple[Mapping[str, Any], ...] = ()
    evolution_proposal: Optional[Mapping[str, Any]] = None
    leak_results: Tuple[Mapping[str, Any], ...] = ()
    final_outcome: Mapping[str, Any] = field(default_factory=dict)
    deterministic_checks: Mapping[str, Any] = field(default_factory=dict)
    blind_package: Mapping[str, Any] = field(default_factory=dict)
    randomization_key: Mapping[str, Any] = field(default_factory=dict)
    judge_sheet: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty_str(self.run_id, "run_id")
        _require_non_empty_str(self.timestamp, "timestamp")
        _require_non_empty_str(self.mode, "mode")
        if self.sub_mode is not None:
            _require_non_empty_str(self.sub_mode, "sub_mode")
        _require_non_empty_str(self.probe_set_version, "probe_set_version")
        _require_hex(self.probe_set_sha256, "probe_set_sha256", 64)
        _require_non_empty_str(self.fixture_identity, "fixture_identity")
        if not isinstance(self.manifest, ProvenanceManifest):
            raise ContractValidationError("manifest must be a ProvenanceManifest instance")
        if not isinstance(self.samples, tuple):
            raise ContractValidationError("samples must be a tuple")
        for sample in self.samples:
            if not isinstance(sample, ProbeSampleRecord):
                raise ContractValidationError("samples must be ProbeSampleRecord instances")
        for name in (
            "baseline_source_identity",
            "final_outcome",
            "deterministic_checks",
            "blind_package",
            "randomization_key",
            "judge_sheet",
        ):
            value = getattr(self, name)
            if not isinstance(value, Mapping):
                raise ContractValidationError(f"{name} must be a mapping")
            object.__setattr__(self, name, MappingProxyType(dict(value)))
        for name in ("initial_p3", "initial_p4", "evolution_proposal"):
            value = getattr(self, name)
            if value is not None:
                if not isinstance(value, Mapping):
                    raise ContractValidationError(f"{name} must be a mapping or None")
                object.__setattr__(self, name, MappingProxyType(dict(value)))
        for name in ("memory_trace", "relationship_decisions", "leak_results"):
            value = getattr(self, name)
            if not isinstance(value, tuple):
                raise ContractValidationError(f"{name} must be a tuple")
            object.__setattr__(
                self, name, tuple(MappingProxyType(dict(entry)) for entry in value)
            )

    def to_dict(self) -> Dict[str, Any]:
        """Full JSON-ready serialization (repo-relative POSIX paths only)."""
        return {
            "kind": "cis_pilot_result_package",
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "mode": self.mode,
            "sub_mode": self.sub_mode,
            "probe_set_version": self.probe_set_version,
            "probe_set_sha256": self.probe_set_sha256,
            "fixture_identity": self.fixture_identity,
            "provenance": self.manifest.to_dict(),
            "baseline_source_identity": dict(self.baseline_source_identity),
            "initial_p3": dict(self.initial_p3) if self.initial_p3 is not None else None,
            "initial_p4": dict(self.initial_p4) if self.initial_p4 is not None else None,
            "samples": [sample.to_dict() for sample in self.samples],
            "memory_trace": [dict(entry) for entry in self.memory_trace],
            "relationship_decisions": [dict(entry) for entry in self.relationship_decisions],
            "evolution_proposal": (
                dict(self.evolution_proposal) if self.evolution_proposal is not None else None
            ),
            "leak_results": [dict(entry) for entry in self.leak_results],
            "final_outcome": dict(self.final_outcome),
            "deterministic_checks": dict(self.deterministic_checks),
            "blind_package": dict(self.blind_package),
            "randomization_key": dict(self.randomization_key),
            "judge_sheet": dict(self.judge_sheet),
        }

    def deterministic_payload(self) -> Dict[str, Any]:
        """The package minus every VOLATILE field (``run_id``/``timestamp``
        at the top level and inside the manifest). Used by reproducibility
        tests: same inputs => identical payload."""
        payload = self.to_dict()
        del payload["run_id"]
        del payload["timestamp"]
        payload["provenance"] = self.manifest.deterministic_payload()
        return payload


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------


def assemble_result_package(
    *,
    run_id: str,
    timestamp: str,
    mode: str,
    sub_mode: Optional[str],
    probe_set_version: str,
    probe_set_sha256: str,
    fixture_identity: str,
    snapshot: PilotSourceSnapshot,
    provider_metadata: Mapping[str, Any],
    initial_p3: Optional[Mapping[str, Any]],
    initial_p4: Optional[Mapping[str, Any]],
    samples: Tuple[ProbeSampleRecord, ...],
    memory_trace: Tuple[Mapping[str, Any], ...] = (),
    relationship_decisions: Tuple[Mapping[str, Any], ...] = (),
    evolution_proposal: Optional[Mapping[str, Any]] = None,
    leak_results: Tuple[Mapping[str, Any], ...] = (),
    final_outcome: Optional[Mapping[str, Any]] = None,
    seed: int,
) -> ResultPackage:
    """Assemble one complete ``ResultPackage`` (plan §12 sections populated).

    Builds the manifest from the frozen snapshot (reusing Slice 0 provenance
    primitives per TD-14), the seeded blind package + separate randomization
    key, the human judge sheet skeleton, and the deterministic checks block.
    No file I/O; persistence is ``persist_result_package``.
    """
    if not isinstance(provider_metadata, Mapping):
        raise ContractValidationError("provider_metadata must be a mapping")
    for key in ("provider", "model", "params"):
        if key not in provider_metadata:
            raise ContractValidationError(f"provider_metadata missing {key!r}")

    manifest = ProvenanceManifest(
        run_id=run_id,
        timestamp=timestamp,
        repo_head_sha=snapshot.repo_head_sha,
        source_artifacts=collect_source_artifacts(snapshot),
        probe_set_version=probe_set_version,
        probe_set_sha256=probe_set_sha256,
        provider=str(provider_metadata["provider"]),
        model=str(provider_metadata["model"]),
        params=dict(provider_metadata["params"]),
        per_sample_refs=tuple(samples),
    )

    blind_package, randomization_key = build_blind_package(tuple(samples), seed=seed)
    judge_sheet = build_human_judge_sheet(blind_package, mode=mode)

    deterministic_checks = {
        "blind_labels_hidden": _blind_labels_hidden(blind_package),
        "blind_item_count": blind_package["item_count"],
        "sample_count": len(samples),
        "leak_auto_fail_count": sum(
            1 for entry in leak_results if entry.get("auto_verdict") == "FAIL"
        ),
        "leak_human_review_pending_count": sum(
            1 for entry in leak_results if entry.get("human_review_required")
        ),
    }

    return ResultPackage(
        run_id=run_id,
        timestamp=timestamp,
        mode=mode,
        sub_mode=sub_mode,
        probe_set_version=probe_set_version,
        probe_set_sha256=probe_set_sha256,
        fixture_identity=fixture_identity,
        manifest=manifest,
        baseline_source_identity=_baseline_source_identity(snapshot),
        initial_p3=initial_p3,
        initial_p4=initial_p4,
        samples=tuple(samples),
        memory_trace=tuple(memory_trace),
        relationship_decisions=tuple(relationship_decisions),
        evolution_proposal=evolution_proposal,
        leak_results=tuple(leak_results),
        final_outcome=dict(final_outcome or {}),
        deterministic_checks=deterministic_checks,
        blind_package=blind_package,
        randomization_key=randomization_key,
        judge_sheet=judge_sheet,
    )


def persist_result_package(
    storage: CisPilotStorage, package: ResultPackage
) -> Dict[str, str]:
    """Persist the package under ``local_runs/cis_pilot/`` (plan §5 tree).

    Writes (all fail-if-exists; the randomization key is a SEPARATE file
    from the blind package per spec §15):

    * ``results/<run_id>/result_package.json``
    * ``blind/<run_id>/package.json``
    * ``blind/<run_id>/randomization_key.json``
    * ``judge_sheets/<run_id>/human_judge_sheet.json``
    * ``provenance/<run_id>/manifest.json``

    Returns the written repo-root-relative POSIX paths.
    """
    if not isinstance(storage, CisPilotStorage):
        raise ContractValidationError("storage must be a CisPilotStorage instance")
    if not isinstance(package, ResultPackage):
        raise ContractValidationError("package must be a ResultPackage instance")

    run_id = package.run_id
    targets = {
        "result_package": (f"results/{run_id}/result_package.json", package.to_dict()),
        "blind_package": (f"blind/{run_id}/package.json", dict(package.blind_package)),
        "randomization_key": (
            f"blind/{run_id}/randomization_key.json",
            dict(package.randomization_key),
        ),
        "judge_sheet": (f"judge_sheets/{run_id}/human_judge_sheet.json", dict(package.judge_sheet)),
        "provenance_manifest": (f"provenance/{run_id}/manifest.json", package.manifest.to_dict()),
    }
    written: Dict[str, str] = {}
    for name, (relative, payload) in targets.items():
        path = storage.write_json(relative, payload)
        written[name] = path.name and relative  # keep the confined relative path
    return written


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _baseline_source_identity(snapshot: PilotSourceSnapshot) -> Dict[str, Any]:
    baseline = snapshot.baseline
    return {
        "baseline_git_sha": baseline.baseline_git_sha,
        "modules": {
            name: {
                "repo_relative_path": artifact.repo_relative_path,
                "sha256": artifact.sha256,
            }
            for name, artifact in (
                ("identity", baseline.identity),
                ("base", baseline.base),
                ("speech_matrix", baseline.speech_matrix),
                ("matrix", baseline.matrix),
                ("builder_source", baseline.builder_source),
            )
        },
    }


def _blind_labels_hidden(blind_package: Mapping[str, Any]) -> bool:
    """Deterministic check: no label field anywhere in the blind package."""
    forbidden = ("probe_id", "state", "arm", "character_id", "target_character")

    def scan(value: Any) -> bool:
        if isinstance(value, Mapping):
            for key, sub in value.items():
                if key in forbidden:
                    return False
                if not scan(sub):
                    return False
        elif isinstance(value, (list, tuple)):
            return all(scan(sub) for sub in value)
        return True

    return scan(blind_package)


def _require_non_empty_str(value: Any, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ContractValidationError(f"{field_name} must be a non-empty string")


def _require_hex(value: Any, field_name: str, length: int) -> None:
    if (
        not isinstance(value, str)
        or len(value) != length
        or any(c not in "0123456789abcdef" for c in value)
    ):
        raise ContractValidationError(
            f"{field_name} must be a {length}-char lowercase hex string, got {value!r}"
        )
