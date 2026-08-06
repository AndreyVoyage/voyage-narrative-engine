#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CIS Kira Pilot -- Slice 0 read-only source loader.

Deterministically loads and validates the frozen source snapshot for the
Kira pilot: P0 (six static psychology modules), P3 (``user`` relationship
baseline), P4 (the four ``AFFECT_REGULATION`` strategy states), ME-1/ME-2
memory event fixtures, and the frozen 4-module static baseline source set
(PD-10). Everything here is strictly read-only: no source file, persona
module, scenario file, or Git state is ever written or mutated, and no
``local_runs/`` output is produced -- that is a later slice's
responsibility.

Persona modules are read exclusively through the existing, unmodified N7
Persona Data Gateway (``services.persona_gateway.PersonaCatalog``); this
module never re-implements module hashing, allowlisting, or path
confinement for persona files, and never exposes a generic
"read arbitrary path" API. The only files read outside the Gateway are the
two fixed ME-1/ME-2 scenario JSON files and the static baseline builder
source file (``tools/aside_context_builder.py``), each confined to the
repo root via ``tools/cis_pilot/provenance.py``.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import MappingProxyType
from typing import Any, Dict, Optional, Tuple

from services.persona_gateway import PersonaCatalog, PersonaGatewayError
from services.persona_gateway.models import ModuleResult

from . import provenance
from .contracts import (
    ALLOWED_P4_STATES,
    BaselineSourceSet,
    MemoryEventSource,
    P0Snapshot,
    P3State,
    P4State,
    PilotSourceSnapshot,
    SourceArtifact,
)

# ---------------------------------------------------------------------------
# Fixed pilot scope (spec PD-1/PD-2/PD-3/PD-4/PD-5/PD-10)
# ---------------------------------------------------------------------------

CHARACTER_ID = "kira"

# One authorized baseline SHA for this Slice 0 implementation pass. A repo
# HEAD that no longer matches this value means the source has moved since
# authorization -- fail closed rather than silently loading a different
# snapshot.
AUTHORIZED_BASELINE_SHA = "afa64d3af14ad78366dc34cad68af3fb91f2423c"

P0_MODULE_IDS: Dict[str, str] = {
    "value_system": "psychology/VALUE_SYSTEM.json",
    "base": "psychology/BASE.json",
    "attachment": "psychology/ATTACHMENT.json",
    "defense_mechanisms": "psychology/DEFENSE_MECHANISMS.json",
    "ifs_parts": "psychology/IFS_PARTS.json",
    "odsc": "psychology/ODSC.json",
}

# Confirmed to exist and never included in P0Snapshot (spec PD-5): dynamic,
# not static core; base_style is never extracted from it.
ATTACHMENT_STYLE_DYNAMIC_MODULE_ID = "psychology/ATTACHMENT_STYLE_DYNAMIC.json"

P3_MODULE_ID = "relationships/MATRIX.json"
EXPECTED_P3_TRUST = 75
EXPECTED_P3_ATTRACTION = 85

P4_MODULE_ID = "psychology/AFFECT_REGULATION.json"

# AFFECT_REGULATION.json "strategies" key -> (arousal, anxiety), matching
# contracts.ALLOWED_P4_STATES's (arousal, anxiety) -> strategy mapping.
_P4_STRATEGY_KEY_TO_STATE: Dict[str, Tuple[str, str]] = {
    "high_arousal_low_anxiety": ("high", "low"),
    "high_arousal_high_anxiety": ("high", "high"),
    "low_arousal_high_anxiety": ("low", "high"),
    "low_arousal_low_anxiety": ("low", "low"),
}

BASELINE_MODULE_IDS: Dict[str, str] = {
    "identity": "core/IDENTITY.json",
    "speech_matrix": "speech/SPEECH_MATRIX.json",
}
BUILDER_RELATIVE_PATH = "tools/aside_context_builder.py"

# Frozen 4-module baseline call-chain markers (PD-10), confirmed by a
# read-only textual check of the unmodified builder source -- never
# executed, copied, or reimplemented here.
_EXPECTED_BUILDER_MARKERS: Tuple[str, ...] = (
    "def build_context(",
    "def _build_persona_block(",
    'persona_dir / "core" / "IDENTITY.json"',
    'persona_dir / "psychology" / "BASE.json"',
    'persona_dir / "speech" / "SPEECH_MATRIX.json"',
    'persona_dir / "relationships" / "MATRIX.json"',
)

# ME-1 (spec §6): scenarios/SCENARIO_008_HOME_EMBRACE.json,
# choice_points[0].branches[0].action.
ME1_SCENARIO_RELATIVE_PATH = "scenarios/SCENARIO_008_HOME_EMBRACE.json"
ME1_EVENT_ID = "SC_008"
ME1_JSON_PATH = "choice_points[0].branches[0].action"
ME1_EXPECTED_LITERAL_TEXT = "Падает ему на грудь. Плачет. Не объясняет."
ME1_NORMALIZED_TEXT = "Кира падает ему на грудь. Плачет. Не объясняет."

# ME-2 (spec §6): scenarios/SCENARIO_017_SERGEY_WRITES_AGAIN.v2.json,
# entry_beats[0].narration. Only the confirmed first sentence is stored as
# the fixture's literal_text (a second sentence may follow in the source).
ME2_SCENARIO_RELATIVE_PATH = "scenarios/SCENARIO_017_SERGEY_WRITES_AGAIN.v2.json"
ME2_EVENT_ID = "SC_017"
ME2_JSON_PATH = "entry_beats[0].narration"
ME2_EXPECTED_FIRST_SENTENCE = "Телефон загорается новым сообщением от Сергея."


class SourceLoaderError(RuntimeError):
    """Raised when the pilot source snapshot cannot be loaded and
    validated safely (missing source, drift from spec, or fixture
    mismatch). Always fail-closed -- never silently substitutes or
    invents a value."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_pilot_source_snapshot(repo_root: Optional[Path] = None) -> PilotSourceSnapshot:
    """Load and validate the complete frozen Slice 0 pilot source snapshot.

    Strictly read-only. Fails closed (raises ``SourceLoaderError`` or
    ``provenance.ProvenanceError``) on any missing source, drift from the
    approved spec values, fixture mismatch, or repo HEAD that no longer
    matches ``AUTHORIZED_BASELINE_SHA``.
    """
    root = _resolve_repo_root(repo_root)

    head_sha = provenance.get_head_sha(root)
    if head_sha != AUTHORIZED_BASELINE_SHA:
        raise SourceLoaderError(
            "BASELINE_MOVED_REQUIRES_OWNER_REVIEW: repo HEAD "
            f"{head_sha!r} does not match authorized Slice 0 baseline SHA "
            f"{AUTHORIZED_BASELINE_SHA!r}"
        )

    persona_root = root / "personas" / CHARACTER_ID
    if not persona_root.is_dir():
        raise SourceLoaderError(f"persona root not found: personas/{CHARACTER_ID}")

    try:
        catalog = PersonaCatalog(entries={CHARACTER_ID: persona_root})
    except PersonaGatewayError as exc:
        raise SourceLoaderError(
            f"failed to construct PersonaCatalog for {CHARACTER_ID!r}: {exc}"
        ) from exc

    p0_snapshot, p0_artifacts = _load_p0_snapshot(catalog)
    _confirm_attachment_style_dynamic_excluded(catalog)
    p3_state, p3_artifact = _load_p3_state(catalog)
    p4_strategy_map, _p4_artifact = _load_p4_strategy_map(catalog)
    me1 = _load_me1(root)
    me2 = _load_me2(root)
    _confirm_baseline_call_chain(root)
    baseline = _load_baseline_source_set(
        catalog,
        root,
        base_artifact=p0_artifacts["base"],
        matrix_artifact=p3_artifact,
        head_sha=head_sha,
    )

    return PilotSourceSnapshot(
        p0=p0_snapshot,
        p3=p3_state,
        p4_strategy_map=p4_strategy_map,
        me1=me1,
        me2=me2,
        baseline=baseline,
        repo_head_sha=head_sha,
    )


# ---------------------------------------------------------------------------
# P0
# ---------------------------------------------------------------------------


def _load_p0_snapshot(catalog: PersonaCatalog) -> Tuple[P0Snapshot, Dict[str, SourceArtifact]]:
    results: Dict[str, ModuleResult] = {}
    for name, module_id in P0_MODULE_IDS.items():
        try:
            results[name] = catalog.read_module(CHARACTER_ID, module_id)
        except PersonaGatewayError as exc:
            raise SourceLoaderError(f"failed to read P0 module {module_id!r}: {exc}") from exc

    value_system_data = results["value_system"].data
    if "core_values" not in value_system_data:
        raise SourceLoaderError(
            "P0 drift: psychology/VALUE_SYSTEM.json is missing required key 'core_values'"
        )

    base_data = results["base"].data
    if "core_conflict" not in base_data:
        raise SourceLoaderError(
            "P0 drift: psychology/BASE.json is missing required key 'core_conflict'"
        )

    artifacts = {
        name: _module_result_to_artifact(P0_MODULE_IDS[name], result, kind="p0_module")
        for name, result in results.items()
    }
    snapshot = P0Snapshot(
        value_system=artifacts["value_system"],
        base=artifacts["base"],
        attachment=artifacts["attachment"],
        defense_mechanisms=artifacts["defense_mechanisms"],
        ifs_parts=artifacts["ifs_parts"],
        odsc=artifacts["odsc"],
    )
    return snapshot, artifacts


def _confirm_attachment_style_dynamic_excluded(catalog: PersonaCatalog) -> None:
    """Confirm ``ATTACHMENT_STYLE_DYNAMIC.json`` exists with the expected
    structure, without ever including it in P0 or extracting ``base_style``
    from it (spec PD-5). The read result is intentionally discarded."""
    try:
        result = catalog.read_module(CHARACTER_ID, ATTACHMENT_STYLE_DYNAMIC_MODULE_ID)
    except PersonaGatewayError as exc:
        raise SourceLoaderError(
            f"failed to confirm excluded module {ATTACHMENT_STYLE_DYNAMIC_MODULE_ID!r}: {exc}"
        ) from exc

    if result.data.get("module_id") != "ATTACHMENT_STYLE_DYNAMIC":
        raise SourceLoaderError(
            "psychology/ATTACHMENT_STYLE_DYNAMIC.json has unexpected 'module_id' "
            f"{result.data.get('module_id')!r}; structural confirmation failed"
        )
    # Confirmed present and structurally as expected. Nothing from this
    # module is retained, returned, or included in any snapshot.


# ---------------------------------------------------------------------------
# P3
# ---------------------------------------------------------------------------


def _load_p3_state(catalog: PersonaCatalog) -> Tuple[P3State, SourceArtifact]:
    try:
        result = catalog.read_module(CHARACTER_ID, P3_MODULE_ID)
    except PersonaGatewayError as exc:
        raise SourceLoaderError(f"failed to read P3 module {P3_MODULE_ID!r}: {exc}") from exc

    relationships = result.data.get("relationships")
    if not isinstance(relationships, dict):
        raise SourceLoaderError("P3 drift: relationships/MATRIX.json missing 'relationships' object")

    user_entry = relationships.get("user")
    if not isinstance(user_entry, dict):
        raise SourceLoaderError("P3 drift: relationships/MATRIX.json missing 'relationships.user' object")

    for forbidden_key in ("resentment", "session_count", "attachment_style"):
        if forbidden_key in user_entry:
            raise SourceLoaderError(
                f"P3 drift: relationships.user unexpectedly contains {forbidden_key!r} "
                "(not a pilot-scope P3 field; must not be injected)"
            )

    trust = user_entry.get("trust")
    attraction = user_entry.get("attraction")
    if trust != EXPECTED_P3_TRUST:
        raise SourceLoaderError(
            f"P3 drift: expected relationships.user.trust == {EXPECTED_P3_TRUST}, got {trust!r}"
        )
    if attraction != EXPECTED_P3_ATTRACTION:
        raise SourceLoaderError(
            f"P3 drift: expected relationships.user.attraction == {EXPECTED_P3_ATTRACTION}, got {attraction!r}"
        )

    p3_state = P3State(trust=trust, attraction=attraction)
    artifact = _module_result_to_artifact(P3_MODULE_ID, result, kind="p3_module")
    return p3_state, artifact


# ---------------------------------------------------------------------------
# P4
# ---------------------------------------------------------------------------


def _load_p4_strategy_map(
    catalog: PersonaCatalog,
) -> Tuple[MappingProxyType, SourceArtifact]:
    try:
        result = catalog.read_module(CHARACTER_ID, P4_MODULE_ID)
    except PersonaGatewayError as exc:
        raise SourceLoaderError(f"failed to read P4 module {P4_MODULE_ID!r}: {exc}") from exc

    strategies = result.data.get("strategies")
    if not isinstance(strategies, dict):
        raise SourceLoaderError(
            "P4 drift: psychology/AFFECT_REGULATION.json missing 'strategies' object"
        )

    built: Dict[str, P4State] = {}
    for key, (arousal, anxiety) in _P4_STRATEGY_KEY_TO_STATE.items():
        entry = strategies.get(key)
        if not isinstance(entry, dict):
            raise SourceLoaderError(f"P4 drift: strategies is missing entry {key!r}")
        strategy_value = entry.get("strategy")
        expected_strategy = ALLOWED_P4_STATES[(arousal, anxiety)]
        if strategy_value != expected_strategy:
            raise SourceLoaderError(
                f"P4 drift for {key!r}: expected strategy {expected_strategy!r}, got {strategy_value!r}"
            )
        built[key] = P4State(arousal=arousal, anxiety=anxiety, strategy=strategy_value)

    p4_strategy_map = MappingProxyType(built)
    artifact = _module_result_to_artifact(P4_MODULE_ID, result, kind="p4_module")
    return p4_strategy_map, artifact


# ---------------------------------------------------------------------------
# ME-1 / ME-2
# ---------------------------------------------------------------------------


def _load_me1(repo_root: Path) -> MemoryEventSource:
    data = _read_scenario_json(repo_root / ME1_SCENARIO_RELATIVE_PATH)

    if data.get("id") != ME1_EVENT_ID:
        raise SourceLoaderError(
            f"ME-1 scenario id mismatch: expected {ME1_EVENT_ID!r}, got {data.get('id')!r}"
        )

    try:
        actual_text = data["choice_points"][0]["branches"][0]["action"]
    except (KeyError, IndexError, TypeError) as exc:
        raise SourceLoaderError(
            f"ME-1 JSON path {ME1_JSON_PATH} not found in {ME1_SCENARIO_RELATIVE_PATH}: {exc}"
        ) from exc

    if actual_text != ME1_EXPECTED_LITERAL_TEXT:
        raise SourceLoaderError(
            f"ME-1 literal text mismatch at {ME1_JSON_PATH}: "
            f"expected {ME1_EXPECTED_LITERAL_TEXT!r}, got {actual_text!r}"
        )

    artifact = provenance.build_source_artifact(
        repo_root,
        ME1_SCENARIO_RELATIVE_PATH,
        kind="memory_fixture",
        json_path=ME1_JSON_PATH,
    )
    return MemoryEventSource(
        event_id=ME1_EVENT_ID,
        scenario_repo_relative_path=artifact.repo_relative_path,
        json_path=ME1_JSON_PATH,
        literal_text=ME1_EXPECTED_LITERAL_TEXT,
        sha256=artifact.sha256,
        normalized_text=ME1_NORMALIZED_TEXT,
    )


def _load_me2(repo_root: Path) -> MemoryEventSource:
    data = _read_scenario_json(repo_root / ME2_SCENARIO_RELATIVE_PATH)

    if data.get("id") != ME2_EVENT_ID:
        raise SourceLoaderError(
            f"ME-2 scenario id mismatch: expected {ME2_EVENT_ID!r}, got {data.get('id')!r}"
        )

    try:
        actual_text = data["entry_beats"][0]["narration"]
    except (KeyError, IndexError, TypeError) as exc:
        raise SourceLoaderError(
            f"ME-2 JSON path {ME2_JSON_PATH} not found in {ME2_SCENARIO_RELATIVE_PATH}: {exc}"
        ) from exc

    if not isinstance(actual_text, str) or not actual_text.startswith(ME2_EXPECTED_FIRST_SENTENCE):
        raise SourceLoaderError(
            f"ME-2 literal text at {ME2_JSON_PATH} does not start with the confirmed first "
            f"sentence: expected prefix {ME2_EXPECTED_FIRST_SENTENCE!r}, got {actual_text!r}"
        )

    artifact = provenance.build_source_artifact(
        repo_root,
        ME2_SCENARIO_RELATIVE_PATH,
        kind="memory_fixture",
        json_path=ME2_JSON_PATH,
    )
    return MemoryEventSource(
        event_id=ME2_EVENT_ID,
        scenario_repo_relative_path=artifact.repo_relative_path,
        json_path=ME2_JSON_PATH,
        literal_text=ME2_EXPECTED_FIRST_SENTENCE,
        sha256=artifact.sha256,
        normalized_text=None,
    )


def _read_scenario_json(full_path: Path) -> Dict[str, Any]:
    if not full_path.is_file():
        raise SourceLoaderError(f"scenario source not found: {full_path.name}")
    raw = full_path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise SourceLoaderError(f"scenario source is not valid UTF-8: {full_path.name}: {exc}") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SourceLoaderError(f"scenario source is not valid JSON: {full_path.name}: {exc}") from exc
    if not isinstance(data, dict):
        raise SourceLoaderError(f"scenario source root must be a JSON object: {full_path.name}")
    return data


# ---------------------------------------------------------------------------
# Baseline (PD-10)
# ---------------------------------------------------------------------------


def _confirm_baseline_call_chain(repo_root: Path) -> None:
    """Read-only textual confirmation that the frozen builder source still
    contains the documented 4-module baseline call chain. Never executes,
    copies, or reimplements the builder."""
    full_path = repo_root / BUILDER_RELATIVE_PATH
    if not full_path.is_file():
        raise SourceLoaderError(f"baseline builder source not found: {BUILDER_RELATIVE_PATH}")
    try:
        text = full_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SourceLoaderError(f"cannot read baseline builder source: {exc}") from exc

    missing = [marker for marker in _EXPECTED_BUILDER_MARKERS if marker not in text]
    if missing:
        raise SourceLoaderError(
            f"baseline call chain markers missing from {BUILDER_RELATIVE_PATH}: {missing}"
        )


def _load_baseline_source_set(
    catalog: PersonaCatalog,
    repo_root: Path,
    *,
    base_artifact: SourceArtifact,
    matrix_artifact: SourceArtifact,
    head_sha: str,
) -> BaselineSourceSet:
    try:
        identity_result = catalog.read_module(CHARACTER_ID, BASELINE_MODULE_IDS["identity"])
        speech_result = catalog.read_module(CHARACTER_ID, BASELINE_MODULE_IDS["speech_matrix"])
    except PersonaGatewayError as exc:
        raise SourceLoaderError(f"failed to read baseline module: {exc}") from exc

    identity_artifact = _module_result_to_artifact(
        BASELINE_MODULE_IDS["identity"], identity_result, kind="baseline_module"
    )
    speech_artifact = _module_result_to_artifact(
        BASELINE_MODULE_IDS["speech_matrix"], speech_result, kind="baseline_module"
    )
    builder_artifact = provenance.build_source_artifact(
        repo_root, BUILDER_RELATIVE_PATH, kind="builder_source"
    )

    return BaselineSourceSet(
        identity=identity_artifact,
        base=base_artifact,
        speech_matrix=speech_artifact,
        matrix=matrix_artifact,
        builder_source=builder_artifact,
        baseline_git_sha=head_sha,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _module_result_to_artifact(module_id: str, result: ModuleResult, *, kind: str) -> SourceArtifact:
    return SourceArtifact(
        repo_relative_path=f"personas/{CHARACTER_ID}/{module_id}",
        sha256=result.provenance.content_hash,
        kind=kind,
        json_path=None,
        module_id=module_id,
    )


def _resolve_repo_root(repo_root: Optional[Path]) -> Path:
    if repo_root is not None:
        return Path(repo_root).resolve()
    # tools/cis_pilot/source_loader.py -> parents[2] is the repo root.
    return Path(__file__).resolve().parents[2]
