#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CRP R4 -- canonical Kira reconstruction run-plan (OFFLINE by default).

Composes already-built, already-tested CRP primitives into the FIRST
canonical Kira run-plan:

    load_a_projection(...)  (A-only evidence, Slice 10 freeze)
        -> exactly four RoleTasks, fixed order R1 -> R2 -> R3 -> R4
        -> full pre-provider plan validation (fail-closed, all four
           registry entries resolved before any role executes)
        -> run_reconstruction(...) (single existing entrypoint, exactly once)

R3 (Intimacy Profile Specialist) is a gated, optional role (CRP-OD-9); its
one RoleTask in this plan carries the exact activation authorization
``CRP-OD-R4-KIRA-R3-01`` (CRP-OD-R4-KIRA-R3-01: R3 is REQUIRED for the first
canonical Kira reconstruction). This module never authorizes R3 itself and
never invents a new authorization for R1/R2/R4.

Safe default (no ``--live``): load + validate the plan, print a JSON preflight
summary, exit. No provider construction, no credential read, no network.
``--live`` is required to reuse the existing ``crp_provider_adapter`` /
``llm_provider`` transport for a real provider call.

This module does not persist anything, does not call ``accept_candidate``,
and does not assign ``HUMAN_APPROVED``. ``run_reconstruction``'s pre-
acceptance return values are the boundary for this slice.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import math
import sys
from collections.abc import Mapping as MappingABC
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Tuple

# Tool bootstrap: resolve both the repo root (services.crp_authoring) and the
# tools directory (crp_provider_adapter / llm_provider) regardless of how this
# module is imported (mirrors tools/crp_r8_smoke_runner.py).
_REPO_ROOT = Path(__file__).resolve().parents[1]
_TOOLS_DIR = Path(__file__).resolve().parents[0]
for _p in (str(_REPO_ROOT), str(_TOOLS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from services.crp_authoring import (  # noqa: E402
    AuthoringProjection,
    CandidateCharacterPackage,
    CompileContext,
    CrpValidationError,
    ExecutorError,
    KnowledgeProfile,
    PERMISSIONS_BY_ROLE,
    RetrievalPolicy,
    RoleRegistry,
    RoleResult,
    RoleStatus,
    RoleTask,
    ValidationReport,
    compute_package_hash,
    load_a_projection,
    load_manifest,
    run_reconstruction,
)
from services.crp_authoring.auditor_checks import AuditPolicy  # noqa: E402
from services.crp_authoring.reconstruction_audit import ReconstructionAudit  # noqa: E402
from services.crp_authoring.registry import load_role_registry  # noqa: E402
from crp_provider_adapter import ProviderConfig, build_provider_callable  # noqa: E402
from llm_provider import LLMProviderError  # noqa: E402


# ---------------------------------------------------------------------------
# Canonical plan identity (frozen, deterministic -- CRP-OD-R4-KIRA-R3-01)
# ---------------------------------------------------------------------------

FIXTURE_ROOT = _REPO_ROOT / "tests" / "fixtures" / "crp_authoring" / "kira_dataset_freeze" / "v1"
MANIFEST_REL = "KIRA_DATASET_FREEZE.manifest.json"

ROLE_ORDER: Tuple[str, ...] = ("R1", "R2", "R3", "R4")
# R1 is pinned to v3 (CRP-OD-R4-KIRA-R1-V3-01, owner-approved quality
# correction). R2 v2 / R3 v1 / R4 v1 are unchanged.
ROLE_VERSIONS: Mapping[str, str] = {"R1": "v3", "R2": "v2", "R3": "v1", "R4": "v1"}
R3_ACTIVATION_AUTHORIZATION_REF = "CRP-OD-R4-KIRA-R3-01"
KIRA_RUN_ID = "kira-r4-canonical-run-1"
PROVIDER_CALL_BUDGET = 5

# Future --live provider path: reuses the already-live-smoked CRP provider
# config shape (crp_r8_smoke_runner.py). No secret value is ever stored here
# -- ``credential_env`` is a NAME only.
LIVE_PROVIDER_ID = "deepseek"
LIVE_MODEL = "deepseek-v4-pro"
LIVE_BASE_URL = "https://api.deepseek.com"
LIVE_CREDENTIAL_ENV = "DEEPSEEK_API_KEY"
LIVE_TIMEOUT_S = 180.0
LIVE_MAX_TOKENS = 8192

# Owner-approved role-scoped provider-options corrections (CRP R4). Two roles
# diverge from the shared default transport; every knob here is provider-facing
# only -- none of them touch a role prompt/schema, the RoleTask schema, the
# executor/orchestrator, or any result contract.
#
#   R1 v3: reconstruction output is legitimately larger than the shared 8192
#   completion budget, so R1 runs with a RAISED max_tokens AND provider
#   "thinking" disabled. (CRP-OD-R4-KIRA-R1-V3-01 raised the R1 budget
#   32768 -> 65536 alongside the v3 quality correction.)
#
#   R2 v2: the visible R2 JSON was legitimate, coherent, and non-repetitive but
#   truncated (finish_reason "length") only because provider reasoning consumed
#   most of the 8192 completion budget. R2 therefore runs with "thinking"
#   disabled and its max_tokens UNCHANGED at the default 8192 -- the R2 budget
#   is deliberately NOT raised.
#
# R3 v1 / R4 v1 and R8 keep the default transport unchanged (max_tokens 8192,
# thinking omitted).
LIVE_R1_MAX_TOKENS = 65536
LIVE_R1_EXTRA_PARAMS = {"thinking": {"type": "disabled"}}
LIVE_R2_MAX_TOKENS = 8192
LIVE_R2_EXTRA_PARAMS = {"thinking": {"type": "disabled"}}


# ---------------------------------------------------------------------------
# Plan assembly
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class KiraR4Plan:
    """A fully constructed and validated canonical Kira R4 run-plan."""

    run_id: str
    registry: RoleRegistry
    projection: AuthoringProjection
    role_tasks: Tuple[RoleTask, ...]
    profiles: Dict[str, KnowledgeProfile]
    compile_context: CompileContext
    audit_policy: AuditPolicy


def _build_role_task(
    role_id: str,
    registry: RoleRegistry,
    *,
    run_id: str,
    subject_id: str,
    evidence_snapshot_id: str,
    allowed_evidence_ids: Tuple[str, ...],
) -> RoleTask:
    version = ROLE_VERSIONS[role_id]
    entry = registry.get(role_id)
    display_name = entry.display_name if entry is not None else role_id
    permissions = tuple(p.value for p in PERMISSIONS_BY_ROLE[role_id])
    activation_ref = R3_ACTIVATION_AUTHORIZATION_REF if role_id == "R3" else None
    return RoleTask(
        task_id=f"{run_id}-{role_id.lower()}",
        role_id=role_id,
        role_version=version,
        subject_id=subject_id,
        run_id=run_id,
        evidence_snapshot_id=evidence_snapshot_id,
        allowed_evidence_ids=allowed_evidence_ids,
        allowed_prior_results=(),
        knowledge_profile_ref=f"profile-{role_id.lower()}",
        input_contract_version="role_task_v1",
        output_contract_version="role_result_v1",
        permissions=permissions,
        task_goal=(
            f"Execute {display_name} ({role_id} {version}) over the canonical "
            f"Kira A-projection evidence snapshot for run {run_id}."
        ),
        revision_round=0,
        activation_authorization_ref=activation_ref,
    )


def validate_role_plan(
    role_tasks: Tuple[RoleTask, ...],
    registry: RoleRegistry,
    *,
    subject_id: str,
    run_id: str,
    evidence_snapshot_id: str,
    allowed_evidence_ids: Tuple[str, ...],
) -> None:
    """Fail-closed validation of the COMPLETE plan, before any provider call.

    Resolves and verifies all four registry entries up front (so a wrong R4
    version is caught before R1/R2/R3 ever run) and enforces the exact
    ``role_id`` sequence, exact versions, shared subject/run/evidence-snapshot
    identity, evidence-id provenance, empty prior-result exposure, and R3's
    exact (and only R3's) activation authorization.
    """
    if not isinstance(role_tasks, tuple):
        raise CrpValidationError("role_tasks must be a tuple of RoleTask")

    actual_order = tuple(t.role_id for t in role_tasks if isinstance(t, RoleTask))
    if len(actual_order) != len(role_tasks) or actual_order != ROLE_ORDER:
        raise CrpValidationError(
            f"role plan sequence {actual_order!r} != required sequence {ROLE_ORDER!r}"
        )

    for task in role_tasks:
        expected_version = ROLE_VERSIONS[task.role_id]
        if task.role_version != expected_version:
            raise CrpValidationError(
                f"role {task.role_id!r} version {task.role_version!r} != "
                f"required {expected_version!r}"
            )

        entry = registry.get(task.role_id)
        if entry is None:
            raise CrpValidationError(f"registry has no entry for role_id {task.role_id!r}")
        if entry.status is not RoleStatus.ACTIVE:
            raise CrpValidationError(
                f"role {task.role_id!r} registry status {entry.status.value!r} is not ACTIVE"
            )
        # Exact (role_id, version) resolution, fail-closed (no latest-wins).
        registry.resolve(task.role_id, task.role_version)

        if task.subject_id != subject_id:
            raise CrpValidationError(
                f"role {task.role_id!r} subject_id {task.subject_id!r} != {subject_id!r}"
            )
        if task.run_id != run_id:
            raise CrpValidationError(
                f"role {task.role_id!r} run_id {task.run_id!r} != {run_id!r}"
            )
        if task.evidence_snapshot_id != evidence_snapshot_id:
            raise CrpValidationError(
                f"role {task.role_id!r} evidence_snapshot_id "
                f"{task.evidence_snapshot_id!r} != {evidence_snapshot_id!r}"
            )
        if task.allowed_evidence_ids != allowed_evidence_ids:
            raise CrpValidationError(
                f"role {task.role_id!r} allowed_evidence_ids does not match the "
                "A-projection evidence order"
            )
        if task.allowed_prior_results != ():
            raise CrpValidationError(
                f"role {task.role_id!r} allowed_prior_results must be empty for "
                "the canonical R4 plan"
            )

        if task.role_id == "R3":
            if task.activation_authorization_ref != R3_ACTIVATION_AUTHORIZATION_REF:
                raise CrpValidationError(
                    "R3 activation_authorization_ref must be exactly "
                    f"{R3_ACTIVATION_AUTHORIZATION_REF!r}, got "
                    f"{task.activation_authorization_ref!r}"
                )
        elif task.activation_authorization_ref is not None:
            raise CrpValidationError(
                f"role {task.role_id!r} must not carry an activation_authorization_ref"
            )


def build_kira_r4_plan(
    *,
    fixture_root: Path = FIXTURE_ROOT,
    manifest_rel: str = MANIFEST_REL,
    run_id: str = KIRA_RUN_ID,
) -> KiraR4Plan:
    """Load, construct, and fully validate the canonical Kira R4 plan.

    No provider call. Uses the existing ``load_a_projection`` A-only loader
    (never duplicates its parsing/materialization) and the existing declarative
    role registry loader.
    """
    registry = load_role_registry()
    projection = load_a_projection(Path(fixture_root), manifest_rel)
    manifest = load_manifest(Path(fixture_root), manifest_rel)
    forbidden_refs = tuple(manifest.get("knowledge_policy", {}).get("forbidden_refs", ()))

    allowed_evidence_ids = tuple(ev.source_id for ev in projection.evidence)
    allowed_source_types = tuple(sorted(
        {ev.source_type for ev in projection.evidence}, key=lambda s: s.value,
    ))

    role_tasks = tuple(
        _build_role_task(
            role_id, registry,
            run_id=run_id, subject_id=projection.subject_id,
            evidence_snapshot_id=projection.evidence_snapshot_id,
            allowed_evidence_ids=allowed_evidence_ids,
        )
        for role_id in ROLE_ORDER
    )

    profiles = {
        f"profile-{role_id.lower()}": KnowledgeProfile(
            profile_id=f"profile-{role_id.lower()}",
            role_id=role_id,
            version=ROLE_VERSIONS[role_id],
            allowed_kb_refs=(),
            allowed_source_types=allowed_source_types,
            forbidden_refs=forbidden_refs,
            retrieval_policy=RetrievalPolicy.EXACT_MODULAR_ONLY,
        )
        for role_id in ROLE_ORDER
    }

    compile_context = CompileContext(
        package_id=f"{run_id}-package",
        subject_id=projection.subject_id,
        package_version=0,
        source_snapshot_id=projection.evidence_snapshot_id,
        created_at=datetime.now(timezone.utc).replace(microsecond=0),
    )
    audit_policy = AuditPolicy(forbidden_refs=forbidden_refs)

    validate_role_plan(
        role_tasks, registry,
        subject_id=projection.subject_id, run_id=run_id,
        evidence_snapshot_id=projection.evidence_snapshot_id,
        allowed_evidence_ids=allowed_evidence_ids,
    )

    return KiraR4Plan(
        run_id=run_id, registry=registry, projection=projection,
        role_tasks=role_tasks, profiles=profiles,
        compile_context=compile_context, audit_policy=audit_policy,
    )


# ---------------------------------------------------------------------------
# Counting guard (max 5 provider attempts total: R1+R2+R3+R4+R8<=5)
# ---------------------------------------------------------------------------

@dataclass
class CountingGuard:
    """Wrap a provider callable so that at most ``max_calls`` invocations
    reach it. No retry, no fallback: attempt N+1 fails closed locally
    (never reaches the wrapped callable) once ``max_calls`` is spent."""

    provider_callable: Callable[[list], str]
    max_calls: int = PROVIDER_CALL_BUDGET
    attempts: int = field(default=0)

    def __call__(self, messages: list) -> str:
        if self.attempts >= self.max_calls:
            raise CrpValidationError(
                f"CountingGuard: provider_call_budget of {self.max_calls} "
                "exhausted; no retry, no fallback"
            )
        self.attempts += 1
        return self.provider_callable(messages)


# ---------------------------------------------------------------------------
# Role-scoped provider options (owner-approved CRP R4 corrections: R1 + R2)
#
# A single runner-local dispatcher routes each provider call to one of three
# already-built provider callables: the R1 override transport (raised
# max_tokens, thinking disabled) for R1 (v3), the R2 override transport
# (default max_tokens, thinking disabled) for R2 (v2), and the unchanged
# default transport for R3 v1 / R4 v1 and R8. The dispatcher is PURE routing:
# no counting, no retry, no fallback, no exception recovery. The one
# ``CountingGuard`` in ``execute_kira_r4_reconstruction`` still wraps this
# single dispatcher, so the global 5-call budget is unchanged and every
# provider call is counted exactly once regardless of which transport served
# it. RoleTask, the executor, and the orchestrator are untouched.
# ---------------------------------------------------------------------------

# The mandatory canonical ``current_task`` identity fields, in the exact order
# ``executor._assemble_messages`` emits them (READ-ONLY reference; the executor
# is never modified). The dispatcher accepts a ``current_task`` block only when
# its ``- <key>: <value>`` lines are EXACTLY these keys, in this order, each
# once, each with a non-empty value, and the block is closed by a ``task_goal:``
# terminator line.
_CANONICAL_CURRENT_TASK_FIELDS = ("task_id", "role_id", "role_version", "subject_id")


def _extract_current_task_role_id(messages) -> str | None:
    """Return the ``role_id`` of ONE complete, unambiguous canonical
    ``current_task:`` identity block -- exactly the structure
    ``executor._assemble_messages`` emits -- or ``None`` (fail closed to the
    default transport) for anything else.

    All of the following must hold; any deviation yields ``None``:

    * ``messages`` is a non-empty list whose every element is a dict whose
      ``role`` is ``"system"`` or ``"user"``;
    * exactly one element has ``role == "user"`` (a second/extra user message --
      even one whose ``content`` is not a string -- fails closed), and its
      ``content`` is a ``str``;
    * that content's first line is exactly ``current_task:``;
    * the lines immediately after it are ``- <key>: <value>`` entries whose
      keys are EXACTLY ``task_id, role_id, role_version, subject_id`` in that
      order, each once, each with a non-empty value;
    * that entry block is closed by a line starting ``task_goal:`` (the
      canonical terminator ``_assemble_messages`` writes).

    Duplicate / missing / reordered / conflicting / malformed identity fields,
    an un-terminated block, an ``current_task:`` / ``- role_id: R1`` fragment
    inside evidence or prose, additional/ambiguous user messages, or any
    non-canonical message structure all yield ``None``. Only ``role_id == "R1"``
    from a fully valid block selects the R1 override; R2/R3/R4 and R8 route to
    the default transport.
    """
    if not isinstance(messages, list) or not messages:
        return None

    user_contents = []
    for m in messages:
        if not isinstance(m, dict):
            return None
        role = m.get("role")
        if role == "user":
            user_contents.append(m.get("content"))
        elif role != "system":
            return None  # non-canonical message role -> fail closed
    if len(user_contents) != 1:
        return None  # zero, or additional/ambiguous, user messages -> fail closed
    content = user_contents[0]
    if not isinstance(content, str):
        return None  # non-string user content -> fail closed

    lines = content.split("\n")
    if lines[0] != "current_task:":
        return None  # current_task block not in its canonical leading location

    keys: list[str] = []
    values: dict[str, str] = {}
    terminated = False
    for raw in lines[1:]:
        if not raw.startswith("- "):
            terminated = raw.startswith("task_goal:")
            break
        key, sep, value = raw[2:].partition(": ")
        if sep != ": " or not key or not value:
            return None  # malformed identity line -> fail closed
        if key in values:
            return None  # duplicate / conflicting identity field -> fail closed
        keys.append(key)
        values[key] = value

    if not terminated:
        return None  # block never closed by a canonical task_goal: line
    if tuple(keys) != _CANONICAL_CURRENT_TASK_FIELDS:
        return None  # missing / extra / reordered identity fields -> fail closed

    return values["role_id"]


def _role_dispatch_provider_callable(
    r1_callable: Callable[[list], str],
    r2_callable: Callable[[list], str],
    default_callable: Callable[[list], str],
) -> Callable[[list], str]:
    """Wrap three already-built provider callables in ONE routing callable.

    Pure routing only -- no counting, no retry, no fallback, no exception
    handling. The role is recognised solely from the canonical ``current_task``
    identity block (independent of role_version): ``R1`` -> ``r1_callable`` and
    ``R2`` -> ``r2_callable``; every other call (R3/R4 and R8, which carry no
    R1/R2 current-task identity, plus any malformed / ambiguous / incomplete
    identity that yields no role) is sent to ``default_callable``.
    """
    if not (
        callable(r1_callable) and callable(r2_callable) and callable(default_callable)
    ):
        raise TypeError("all three provider callables must be callable")

    role_callables = {ROLE_ORDER[0]: r1_callable, ROLE_ORDER[1]: r2_callable}

    def dispatch(messages: list) -> str:
        role_id = _extract_current_task_role_id(messages)
        target = role_callables.get(role_id, default_callable)
        return target(messages)

    return dispatch


def build_live_provider_callable() -> Callable[[list], str]:
    """Build the ONE role-dispatching provider callable for a ``--live`` run.

    Three ``ProviderConfig`` objects are constructed through the existing
    ``build_provider_callable`` transport adapter; they are identical on every
    field except:

    * R1's ``max_tokens`` (65536 vs the default 8192) and its
      ``extra_params={"thinking": {"type": "disabled"}}``;
    * R2's ``extra_params={"thinking": {"type": "disabled"}}`` -- R2's
      ``max_tokens`` stays at the default 8192 and is NOT raised.

    No secret value is stored on any config (``credential_env`` is a NAME
    only). ``crp_provider_adapter`` / ``llm_provider`` are not modified:
    ``extra_params`` already forwards ``thinking`` into the outbound request.
    """
    default_config = ProviderConfig(
        provider_id=LIVE_PROVIDER_ID,
        model=LIVE_MODEL,
        base_url=LIVE_BASE_URL,
        credential_env=LIVE_CREDENTIAL_ENV,
        timeout_s=LIVE_TIMEOUT_S,
        max_tokens=LIVE_MAX_TOKENS,
        json_mode=True,
    )
    r1_config = ProviderConfig(
        provider_id=LIVE_PROVIDER_ID,
        model=LIVE_MODEL,
        base_url=LIVE_BASE_URL,
        credential_env=LIVE_CREDENTIAL_ENV,
        timeout_s=LIVE_TIMEOUT_S,
        max_tokens=LIVE_R1_MAX_TOKENS,
        json_mode=True,
        extra_params=LIVE_R1_EXTRA_PARAMS,
    )
    r2_config = ProviderConfig(
        provider_id=LIVE_PROVIDER_ID,
        model=LIVE_MODEL,
        base_url=LIVE_BASE_URL,
        credential_env=LIVE_CREDENTIAL_ENV,
        timeout_s=LIVE_TIMEOUT_S,
        max_tokens=LIVE_R2_MAX_TOKENS,
        json_mode=True,
        extra_params=LIVE_R2_EXTRA_PARAMS,
    )
    return _role_dispatch_provider_callable(
        build_provider_callable(r1_config),
        build_provider_callable(r2_config),
        build_provider_callable(default_config),
    )


# ---------------------------------------------------------------------------
# Execution (single run_reconstruction entrypoint)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class KiraR4RunResult:
    package: CandidateCharacterPackage
    audit: ReconstructionAudit
    validation_report: ValidationReport
    role_results: Tuple[RoleResult, ...]
    provider_attempts: int
    provider_call_budget: int


def execute_kira_r4_reconstruction(
    provider_callable: Callable[[list], str],
    plan: KiraR4Plan,
) -> KiraR4RunResult:
    """Run the plan through ``run_reconstruction`` exactly once.

    Re-validates the COMPLETE plan first (defense in depth: this must hold
    regardless of how ``plan`` was constructed, not only for plans produced by
    ``build_kira_r4_plan``), so an invalid plan fails closed before role #1's
    provider call, never partway through.
    """
    if not callable(provider_callable):
        raise TypeError("provider_callable is a required injected callable")

    allowed_evidence_ids = tuple(ev.source_id for ev in plan.projection.evidence)
    validate_role_plan(
        plan.role_tasks, plan.registry,
        subject_id=plan.projection.subject_id, run_id=plan.run_id,
        evidence_snapshot_id=plan.projection.evidence_snapshot_id,
        allowed_evidence_ids=allowed_evidence_ids,
    )

    guard = CountingGuard(provider_callable)
    package, audit, validation_report, role_results = run_reconstruction(
        subject_id=plan.projection.subject_id,
        run_id=plan.run_id,
        evidence_snapshot_id=plan.projection.evidence_snapshot_id,
        evidence=plan.projection.evidence,
        registry=plan.registry,
        profiles=plan.profiles,
        role_tasks=plan.role_tasks,
        provider_callable=guard,
        compile_context=plan.compile_context,
        audit_policy=plan.audit_policy,
        evidence_payloads=plan.projection.payloads,
    )
    return KiraR4RunResult(
        package=package,
        audit=audit,
        validation_report=validation_report,
        role_results=role_results,
        provider_attempts=guard.attempts,
        provider_call_budget=PROVIDER_CALL_BUDGET,
    )


# ---------------------------------------------------------------------------
# Full result capture (JSON transport/report envelope, not a new persistence
# domain model). A successful --live run must be fully recoverable from stdout
# alone -- everything a Python process holds only in memory disappears when it
# exits, and nothing here is written to the repository.
# ---------------------------------------------------------------------------

RESULT_ARTIFACT_TYPE = "CRP_KIRA_R4_LIVE_RECONSTRUCTION_RESULT"
RESULT_SCHEMA_VERSION = "1"


def _to_jsonable(value: Any) -> Any:
    """Deterministically convert a CRP result value into plain JSON-safe data.

    Reflection-based (``dataclasses.fields``), not a hand-enumerated field
    list, so no current or future public dataclass field can silently vanish
    from the capture. Handles exactly the shapes the result contracts
    actually use (dataclasses, Enums, datetimes, tuples/lists, mappings,
    JSON primitives, ``None``) and fails closed -- never ``repr(...)``, never
    ``str(...)`` -- on anything else, so an unserializable field or an
    ambiguous mapping key is caught here rather than silently dropped,
    collapsed, or corrupted.

    Two fail-closed boundaries, both required for a transport artifact that
    must survive process exit and external-file capture unambiguously:

    - a ``Mapping`` key that is not already a ``str`` is rejected (never
      coerced via ``str(k)``): ``{1: ...}`` and ``{"1": ...}`` must never
      silently collapse onto the same JSON key;
    - a ``float`` that is not finite (``NaN``/``Infinity``/``-Infinity``) is
      rejected: those are not valid interoperable strict JSON despite being
      accepted by ``json.dumps`` defaults.
    """
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"non-finite float {value!r} cannot be serialized to strict JSON")
        return value
    if isinstance(value, (str, int)):
        return value
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: _to_jsonable(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, MappingABC):
        converted: Dict[str, Any] = {}
        for k, v in value.items():
            if not isinstance(k, str):
                raise TypeError(
                    f"mapping key {k!r} of type {type(k)!r} is not a str; "
                    "refusing to coerce it (no str(k) fallback)"
                )
            converted[k] = _to_jsonable(v)
        return converted
    if isinstance(value, (tuple, list)):
        return [_to_jsonable(v) for v in value]
    raise TypeError(f"cannot serialize value of type {type(value)!r} to JSON-safe form")


# ---------------------------------------------------------------------------
# CLI (safe default: no --live => no provider construction, no credential read)
# ---------------------------------------------------------------------------

def _dry_run_summary(plan: KiraR4Plan) -> dict:
    return {
        "status": "PLAN_VALID_OFFLINE_DRY_RUN",
        "run_id": plan.run_id,
        "subject_id": plan.projection.subject_id,
        "evidence_snapshot_id": plan.projection.evidence_snapshot_id,
        "evidence_count": len(plan.projection.evidence),
        "role_order": list(ROLE_ORDER),
        "role_versions": dict(ROLE_VERSIONS),
        "r3_activation_authorization_ref": R3_ACTIVATION_AUTHORIZATION_REF,
        "provider_call_budget": PROVIDER_CALL_BUDGET,
    }


def build_result_envelope(plan: KiraR4Plan, result: KiraR4RunResult) -> dict:
    """Build the full, self-contained, JSON-safe recoverable result envelope.

    Contains the complete current public contract content of the returned
    ``CandidateCharacterPackage`` / ``ReconstructionAudit`` / ``ValidationReport``
    / ``RoleResult`` tuple, plus the canonical ``compute_package_hash`` and
    non-secret run/provider identification metadata. Never includes a
    credential value, an HTTP header, or raw provider transport internals --
    only the existing CRP result contracts.
    """
    return {
        "artifact_type": RESULT_ARTIFACT_TYPE,
        "schema_version": RESULT_SCHEMA_VERSION,
        "status": "RECONSTRUCTION_COMPLETE_PRE_ACCEPTANCE",
        "run_metadata": {
            "run_id": plan.run_id,
            "subject_id": plan.projection.subject_id,
            "evidence_snapshot_id": plan.projection.evidence_snapshot_id,
            "role_order": list(ROLE_ORDER),
            "role_versions": dict(ROLE_VERSIONS),
            "provider_id": LIVE_PROVIDER_ID,
            "model": LIVE_MODEL,
            "max_tokens": LIVE_MAX_TOKENS,
            "max_tokens_scope": "default",
            "role_provider_overrides": {
                "R1": dict(max_tokens=LIVE_R1_MAX_TOKENS, **LIVE_R1_EXTRA_PARAMS),
                "R2": dict(max_tokens=LIVE_R2_MAX_TOKENS, **LIVE_R2_EXTRA_PARAMS),
            },
            "timeout_s": LIVE_TIMEOUT_S,
            "credential_env_name": LIVE_CREDENTIAL_ENV,
        },
        "candidate_package": _to_jsonable(result.package),
        "candidate_package_hash": compute_package_hash(result.package),
        "reconstruction_audit": _to_jsonable(result.audit),
        "validation_report": _to_jsonable(result.validation_report),
        "role_results": [_to_jsonable(r) for r in result.role_results],
        "provider_attempts": result.provider_attempts,
        "provider_call_budget": result.provider_call_budget,
    }


# ---------------------------------------------------------------------------
# Provider transport observability (R3 HIGH -- diagnostic only).
#
# When a --live provider call fails closed with a non-"stop" finish_reason,
# llm_provider preserves the COMPLETE parsed provider response on the
# LLMProviderError as ``provider_diagnostic``. The canonical runner records it
# as exactly one structured JSON line on stderr (the existing stderr capture is
# the only capture mechanism -- no sidecar files) and then RE-RAISES the same
# exception unchanged. This is pure observability: the truncated response never
# becomes a RoleResult, is never parsed, repaired, returned, retried, or
# accepted as a Candidate. Provider RESPONSE data only -- no environment
# variable, HTTP header, Authorization value, or credential is read here.
# ---------------------------------------------------------------------------

PROVIDER_FAILURE_DIAGNOSTIC_ARTIFACT_TYPE = "CRP_PROVIDER_FAILURE_DIAGNOSTIC"
PROVIDER_FAILURE_DIAGNOSTIC_SCHEMA_VERSION = "1"
PROVIDER_FAILURE_DIAGNOSTIC_PREFIX = "CRP_PROVIDER_FAILURE_DIAGNOSTIC "


def _emit_provider_failure_diagnostic(exc: LLMProviderError, stream=None) -> bool:
    """Write one structured provider-failure diagnostic line to stderr.

    Returns ``True`` when ``exc`` carried a preserved provider response and a
    record was emitted, ``False`` (no output) otherwise. Strict JSON
    serialization: ``ensure_ascii=False``, ``allow_nan=False``, no repr/str
    fallback, and no truncation of ``message.content``, ``usage``, or
    ``reasoning_content``. The caller re-raises ``exc`` unchanged.
    """
    data = getattr(exc, "provider_diagnostic", None)
    if data is None:
        return False

    finish_reason = None
    if isinstance(data, MappingABC):
        choices = data.get("choices")
        if isinstance(choices, (list, tuple)) and choices and isinstance(choices[0], MappingABC):
            finish_reason = choices[0].get("finish_reason")

    record = {
        "artifact_type": PROVIDER_FAILURE_DIAGNOSTIC_ARTIFACT_TYPE,
        "schema_version": PROVIDER_FAILURE_DIAGNOSTIC_SCHEMA_VERSION,
        "finish_reason": finish_reason,
        "provider_response": data,
    }

    if stream is None:
        stream = sys.stderr
    stream.write(
        PROVIDER_FAILURE_DIAGNOSTIC_PREFIX
        + json.dumps(record, ensure_ascii=False, allow_nan=False)
        + "\n"
    )
    stream.flush()
    return True


# ---------------------------------------------------------------------------
# Provider-output parse-failure observability (diagnostic only).
#
# A --live provider call can return a well-formed string that still fails
# inside the executor's strict ``_parse_role_result`` (e.g. an unknown enum
# value). The executor attaches the EXACT original raw string to the SAME
# ``ExecutorError`` under ``raw_provider_output`` and re-raises it unchanged.
# The canonical runner records that raw output as exactly one structured JSON
# line on stderr (the existing stderr capture is the only mechanism -- no
# sidecar files) and then RE-RAISES the same exception unchanged. Pure
# observability: the raw output is never JSON-parsed for acceptance, repaired,
# turned into a RoleResult, returned, retried, or accepted as a Candidate.
# Provider RESPONSE data only -- no environment variable, HTTP header,
# Authorization value, or credential is read here.
# ---------------------------------------------------------------------------

PARSE_FAILURE_DIAGNOSTIC_ARTIFACT_TYPE = "CRP_PARSE_FAILURE_DIAGNOSTIC"
PARSE_FAILURE_DIAGNOSTIC_SCHEMA_VERSION = "1"
PARSE_FAILURE_DIAGNOSTIC_PREFIX = "CRP_PARSE_FAILURE_DIAGNOSTIC "


def _emit_parse_failure_diagnostic(exc: ExecutorError, stream=None) -> bool:
    """Write one structured parse-failure diagnostic line to stderr.

    Returns ``True`` when ``exc`` carried a preserved ``raw_provider_output``
    string and a record was emitted, ``False`` (no output) otherwise. Strict
    JSON serialization: ``ensure_ascii=False``, ``allow_nan=False``, no
    repr/str fallback for the raw output, and no truncation of
    ``raw_provider_output`` or ``error_message``. The raw provider output is
    never JSON-parsed, repaired, or turned into a RoleResult. The caller
    re-raises ``exc`` unchanged.
    """
    if not hasattr(exc, "raw_provider_output"):
        return False

    record = {
        "artifact_type": PARSE_FAILURE_DIAGNOSTIC_ARTIFACT_TYPE,
        "schema_version": PARSE_FAILURE_DIAGNOSTIC_SCHEMA_VERSION,
        "error_type": "ExecutorError",
        "error_message": str(exc),
        "raw_provider_output": exc.raw_provider_output,
    }

    if stream is None:
        stream = sys.stderr
    stream.write(
        PARSE_FAILURE_DIAGNOSTIC_PREFIX
        + json.dumps(record, ensure_ascii=False, allow_nan=False)
        + "\n"
    )
    stream.flush()
    return True


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="crp_kira_r4_runner",
        description=(
            "Canonical Kira R4 run-plan (R1 -> R2 -> R3 -> R4). Safe by "
            "default: prints a preflight summary and makes no provider call. "
            "Requires explicit --live for real provider execution."
        ),
    )
    parser.add_argument(
        "--live",
        action="store_true",
        dest="live",
        help="Execute the real provider path (DeepSeek). Consumes real provider calls.",
    )
    args = parser.parse_args(argv)

    plan = build_kira_r4_plan()

    if not args.live:
        print(json.dumps(_dry_run_summary(plan), ensure_ascii=False, indent=2, allow_nan=False))
        return 0

    provider_callable = build_live_provider_callable()
    try:
        result = execute_kira_r4_reconstruction(provider_callable, plan)
    except LLMProviderError as exc:
        # Provider transport observability only: record the preserved provider
        # response (if any) as one structured stderr line, then re-raise the
        # SAME fail-closed exception. No RoleResult, no R2, no retry, no
        # fallback, no partial-output recovery, no Candidate acceptance.
        _emit_provider_failure_diagnostic(exc)
        raise
    except ExecutorError as exc:
        # Provider-output parse-failure observability only: the provider
        # returned a string that failed the executor's strict
        # ``_parse_role_result``. If the EXACT raw string was preserved on the
        # exception, record it as one structured stderr line, then re-raise the
        # SAME fail-closed exception. No RoleResult, no R2, no retry, no
        # fallback, no repair, no partial-output recovery, no Candidate.
        _emit_parse_failure_diagnostic(exc)
        raise
    envelope = build_result_envelope(plan, result)
    print(json.dumps(envelope, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
