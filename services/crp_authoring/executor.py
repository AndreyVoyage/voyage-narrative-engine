#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CRP MVP S2A -- bounded offline role executor.

``execute_role_task`` executes exactly one ``RoleTask``, returns exactly one
``RoleResult``, and never chains roles, retries, or falls back. It is
completely provider-agnostic: ``provider_callable`` is a REQUIRED injected
callable (no default, no lazy import, no service locator) because the generic
architecture-boundary test forbids any ``tools.llm_provider`` import -- even
inside a function body.

Fail-closed rejections (empty/malformed/unknown-field/wrong-role/wrong-version/
unsupported-claim/unknown-evidence/permission-violation) all raise
``ExecutorError`` with zero retry and zero fallback.

No canon/PAC/Sandbox access, no legacy-KB fetch, no network, no storage.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Tuple

from .contracts import (
    ClaimStatus,
    ClaimType,
    Confidence,
    ContradictionRecord,
    ResolutionStatus,
    RoleClaim,
    Severity,
    SourceEvidence,
    SourceType,
    VoicePatternLabel,
)
from .dataset_freeze import canonical_json_sha256
from .errors import CrpError
from .knowledge_profile import KnowledgeProfile, forbidden_ref_violation
from .permissions import Permission, permission_violations
from .registry import RoleRegistry, RoleStatus
from .role_task import CompletionStatus, RoleResult, RoleTask
from .validation import reject_unsupported_claim
from .voice_rules import voice_label_violations

# Provider callable shape: takes assembled messages, returns a string (the
# model's raw output to parse). A future CLI adapter will forward this to
# tools.llm_provider.complete; S2A's own executor never imports it.
ProviderCallable = Callable[[list], str]

_ROLE_RESULT_JSON_KEYS = frozenset({
    "task_id", "role_id", "role_version", "completion_status",
    "claims", "unknowns", "contradictions", "provenance_summary",
    "requests_for_more_evidence", "warnings", "questions_for_r1",
    "new_source_evidence",
})
_ROLE_CLAIM_JSON_KEYS = frozenset({
    "claim_id", "subject_id", "role_id", "claim", "claim_type",
    "source_evidence_ids", "source_type_summary", "confidence",
    "rationale_summary", "status", "target_module_or_layer",
    "counterevidence_ids", "contradiction_ids", "revision_round",
    "voice_pattern_label",
})
class ExecutorError(CrpError):
    """Fail-closed role-executor error. Never retried, never repaired."""


def execute_role_task(
    task: RoleTask,
    registry: RoleRegistry,
    profiles: dict,
    provider_callable: ProviderCallable,
    evidence: Tuple[SourceEvidence, ...],
    prior_results: Tuple[RoleResult, ...] = (),
    *,
    evidence_payloads: Mapping[str, Mapping[str, Any]],
) -> RoleResult:
    """Execute one bounded role task and return one validated RoleResult.

    ``evidence_payloads`` is a REQUIRED provider-bound input supplying the
    substantive, owner-authored facts keyed by ``source_id``. Metadata-only
    provider fallback is forbidden: an explicit ``None`` or a missing payload
    for any task-authorized evidence item raises BEFORE any provider invocation.
    """
    if not isinstance(task, RoleTask):
        raise ExecutorError("task must be a RoleTask instance")
    if not isinstance(registry, RoleRegistry):
        raise ExecutorError("registry must be a RoleRegistry instance")
    if not callable(provider_callable):
        raise ExecutorError("provider_callable is a required injected callable")
    if evidence_payloads is None:
        raise ExecutorError("evidence_payloads is a required provider-bound input")

    # --- revision_round guard (defense in depth; also validated at construction)
    if task.revision_round < 0 or task.revision_round > 2:
        raise ExecutorError("revision_round must be within 0..2")

    # --- resolve registry entry; reject absent or non-ACTIVE ---
    entry = registry.get(task.role_id)
    if entry is None:
        raise ExecutorError(f"role_id {task.role_id!r} is not in the registry")
    if entry.status is not RoleStatus.ACTIVE:
        raise ExecutorError(f"role_id {task.role_id!r} is not ACTIVE (status={entry.status.value})")

    # --- exact version match (never "latest") ---
    if task.role_version != entry.version:
        raise ExecutorError(
            f"role_version {task.role_version!r} != registry version {entry.version!r}"
        )

    # --- task permissions must be a subset of the registry entry's permissions ---
    task_permissions = _decode_permissions(task.permissions)
    for perm in task_permissions:
        if perm not in entry.permissions:
            raise ExecutorError(
                f"RoleTask grants permission {perm.value!r} not declared for "
                f"role {task.role_id!r} (least-privilege violation)"
            )

    # --- assemble only allowed evidence (never a wider set) ---
    evidence_by_id = {ev.source_id: ev for ev in evidence if isinstance(ev, SourceEvidence)}
    allowed_evidence: list = []
    for ev_id in task.allowed_evidence_ids:
        ev = evidence_by_id.get(ev_id)
        if ev is None:
            raise ExecutorError(
                f"allowed_evidence_ids references unknown SourceEvidence {ev_id!r}"
            )
        allowed_evidence.append(ev)

    # --- assemble only allowed prior results ---
    prior_by_task = {r.task_id: r for r in prior_results if isinstance(r, RoleResult)}
    allowed_prior: list = []
    for task_id in task.allowed_prior_results:
        if task_id not in prior_by_task:
            raise ExecutorError(
                f"allowed_prior_results references unknown task_id {task_id!r}"
            )
        allowed_prior.append(prior_by_task[task_id])

    # --- load KnowledgeProfile ---
    profile = profiles.get(task.knowledge_profile_ref)
    if not isinstance(profile, KnowledgeProfile):
        raise ExecutorError(
            f"knowledge_profile_ref {task.knowledge_profile_ref!r} has no KnowledgeProfile"
        )
    if profile.role_id != task.role_id:
        raise ExecutorError(
            f"KnowledgeProfile.role_id {profile.role_id!r} != task role_id {task.role_id!r}"
        )
    # Enforce allowed_source_types: evidence outside the profile is a violation.
    for ev in allowed_evidence:
        if ev.source_type not in profile.allowed_source_types:
            raise ExecutorError(
                f"evidence {ev.source_id!r} source_type {ev.source_type.value!r} "
                "is not in the role's KnowledgeProfile allowed_source_types"
            )
        # Enforce forbidden_refs (GAP-2): a forbidden origin reference is a
        # deterministic, fail-closed rejection BEFORE any prompt assembly or
        # provider invocation. Only the structured content_ref is matched.
        matched = forbidden_ref_violation(ev.content_ref, profile.forbidden_refs)
        if matched is not None:
            raise ExecutorError(
                f"evidence {ev.source_id!r} content_ref matches forbidden ref "
                f"pattern {matched!r}"
            )

    # --- substantive evidence binding (fail-closed, before provider) --------
    bound_payloads = _bind_allowed_payloads(allowed_evidence, evidence_payloads)

    # --- build context messages and invoke the injected provider ---
    prompt_text = _load_prompt_text(entry.prompt_ref)
    messages = _assemble_messages(
        task, allowed_evidence, allowed_prior,
        prompt_text=prompt_text, evidence_payloads=bound_payloads,
    )
    raw = provider_callable(messages)
    if not isinstance(raw, str):
        raise ExecutorError("provider_callable must return a string")

    # --- parse + validate the structured RoleResult (fail-closed, strict) ---
    # Fail-closed observability seam: the provider already returned a string,
    # but strict parsing of it can still fail (unknown enum value, unknown
    # field, wrong type, ...). When it does, attach the EXACT original raw
    # string to the SAME ExecutorError instance under a stable attribute and
    # re-raise it unchanged -- no repair, no reinterpretation, no RoleResult,
    # no retry, no fallback. All existing validation semantics are preserved.
    try:
        result = _parse_role_result(raw)
    except ExecutorError as exc:
        if not hasattr(exc, "raw_provider_output"):
            exc.raw_provider_output = raw
        raise

    if result.task_id != task.task_id:
        raise ExecutorError(f"result task_id {result.task_id!r} != task.task_id {task.task_id!r}")
    if result.role_id != task.role_id:
        raise ExecutorError(f"result role_id {result.role_id!r} != task role_id {task.role_id!r}")
    if result.role_version != task.role_version:
        raise ExecutorError(
            f"result role_version {result.role_version!r} != task role_version {task.role_version!r}"
        )

    # --- out-of-scope output rejection ---
    for claim in result.claims:
        if claim.subject_id != task.subject_id:
            raise ExecutorError(
                f"claim {claim.claim_id!r} subject_id {claim.subject_id!r} "
                f"!= task subject_id {task.subject_id!r}"
            )
        if claim.role_id != task.role_id:
            raise ExecutorError(
                f"claim {claim.claim_id!r} role_id {claim.role_id!r} "
                f"!= task role_id {task.role_id!r}"
            )
        reject_unsupported_claim(claim)
        for ev_id in claim.source_evidence_ids:
            if ev_id not in task.allowed_evidence_ids:
                raise ExecutorError(
                    f"claim {claim.claim_id!r} references evidence {ev_id!r} "
                    "outside the task's allowed_evidence_ids"
                )
    # R1's new_source_evidence requires EMIT_SOURCE_EVIDENCE; it must also
    # match the task subject.
    if result.new_source_evidence:
        if Permission.EMIT_SOURCE_EVIDENCE not in task_permissions:
            raise ExecutorError(
                "result carries new_source_evidence but role lacks EMIT_SOURCE_EVIDENCE"
            )
        for ev in result.new_source_evidence:
            if ev.subject_id != task.subject_id:
                raise ExecutorError(
                    f"new_source_evidence {ev.source_id!r} subject_id != task subject_id"
                )

    # --- permission violation on emitted claims (single source of truth) ---
    violations = permission_violations(result.claims, entry.permissions)
    if violations:
        raise ExecutorError("ROLE_PERMISSION_VIOLATION: " + "; ".join(violations))

    # --- R4 voice-pattern label fidelity (wired fail-closed for EVERY result) ---
    # ``voice_label_violations`` is the single source of truth for the R4
    # ``voice_pattern_label`` invariants (OBSERVED / INFERRED / GENERATED_RULE /
    # NEGATIVE_EXAMPLE fidelity) and for the R4-scoping rule that a non-R4 role
    # must not silently carry a voice_pattern_label. It runs for every
    # RoleResult (not just R4) AFTER parsing and BEFORE the result is returned
    # downstream toward the Candidate; a violation raises a deterministic
    # ``ExecutorError`` with zero retry, fallback, auto-correction, or label
    # rewriting.
    voice_violations = voice_label_violations(result.claims)
    if voice_violations:
        raise ExecutorError("VOICE_LABEL_VIOLATION: " + "; ".join(voice_violations))

    # --- R1 canonical post-parse quality gate (role- AND version-scoped) ---
    # Owner-approved CRP R4 correction (CRP-OD-R4-KIRA-R1-V3-01). Runs only for
    # an R1 RoleTask at version v3 OR v4 (v4 receives the SAME quality/
    # provenance gate as v3 -- no bypass, no weakening), at the exact seam
    # AFTER _parse_role_result and all existing canonical executor checks and
    # BEFORE returning the RoleResult. It never touches R1 v2, R2, R3, R4, or
    # R8 semantics; it never retries, falls back, mutates the RoleResult,
    # repairs provider output, or synthesizes provenance -- a violation raises a
    # deterministic ``ExecutorError`` before this call returns (so, in the
    # orchestrator, an R1 violation aborts before R2 ever starts).
    if task.role_id == "R1" and task.role_version in ("v3", "v4"):
        _enforce_r1_v3_quality_gate(task, result)

    return result


# ---------------------------------------------------------------------------
# R1 v3 canonical post-parse quality gate (CRP-OD-R4-KIRA-R1-V3-01)
# ---------------------------------------------------------------------------


def _enforce_r1_v3_quality_gate(task: RoleTask, result: RoleResult) -> None:
    """Fail-closed truthful-evidence-accounting gate for R1 v3 and v4.

    The caller invokes this solely when ``task.role_id == 'R1'`` and
    ``task.role_version in ('v3', 'v4')``; it must never be reached for R1 v2,
    R2, R3, R4, or R8. It verifies exactly two properties and raises ``ExecutorError``
    (deterministic, no retry, no fallback, no mutation, no repair, no
    synthesis) on any violation:

    A. CLAIM COVERAGE -- the union of ``claim.source_evidence_ids`` across every
       parsed claim must equal ``set(task.allowed_evidence_ids)`` exactly. A
       missing authorized source id fails closed here. An id *outside*
       ``allowed_evidence_ids`` is already rejected by the canonical per-claim
       check in ``execute_role_task``; the equality assertion below only
       re-confirms it and never weakens that upstream rule.

    B. PROVENANCE SUMMARY CONSISTENCY -- the existing ``provenance_summary``
       object must carry a ``sources_used`` id list whose set equals that same
       actual claim-level evidence set exactly. A missing / extra / non-string
       / malformed ``sources_used`` fails closed.
    """
    allowed_ids = set(task.allowed_evidence_ids)

    actual_claim_evidence_ids: set = set()
    for claim in result.claims:
        actual_claim_evidence_ids.update(claim.source_evidence_ids)

    missing = allowed_ids - actual_claim_evidence_ids
    if missing:
        raise ExecutorError(
            "R1_V3_CLAIM_COVERAGE_INCOMPLETE: authorized evidence "
            f"{sorted(missing)} is not cited by any R1 v3 claim "
            "(union of claims[].source_evidence_ids must equal allowed_evidence_ids)"
        )
    if actual_claim_evidence_ids != allowed_ids:
        # Defense in depth: an id outside allowed_evidence_ids should already
        # have failed the canonical per-claim allowed-evidence check above.
        raise ExecutorError(
            "R1_V3_CLAIM_COVERAGE_MISMATCH: claim-level evidence set "
            f"{sorted(actual_claim_evidence_ids)} != allowed_evidence_ids "
            f"{sorted(allowed_ids)}"
        )

    prov = result.provenance_summary
    if not isinstance(prov, Mapping):
        raise ExecutorError(
            "R1_V3_PROVENANCE_SUMMARY_INVALID: provenance_summary must be a JSON "
            "object carrying a 'sources_used' id list"
        )
    represented = prov.get("sources_used")
    if not isinstance(represented, (list, tuple)):
        raise ExecutorError(
            "R1_V3_PROVENANCE_SUMMARY_INVALID: provenance_summary.sources_used "
            "must be a list of authorized source ids"
        )
    for sid in represented:
        if not isinstance(sid, str) or not sid.strip():
            raise ExecutorError(
                "R1_V3_PROVENANCE_SUMMARY_INVALID: provenance_summary.sources_used "
                f"contains a non-string id {sid!r}"
            )
    represented_set = set(represented)
    if represented_set != actual_claim_evidence_ids:
        raise ExecutorError(
            "R1_V3_PROVENANCE_SUMMARY_MISMATCH: provenance_summary.sources_used "
            f"{sorted(represented_set)} != actual claim-level evidence set "
            f"{sorted(actual_claim_evidence_ids)}"
        )


# ---------------------------------------------------------------------------
# Provider output parsing (strict JSON -> RoleResult)
# ---------------------------------------------------------------------------


def _decode_permissions(raw_permissions) -> frozenset:
    perms = set()
    for value in raw_permissions:
        try:
            perms.add(Permission(value))
        except ValueError:
            raise ExecutorError(f"unknown permission verb {value!r}")
    return frozenset(perms)


def _parse_role_result(raw: str) -> RoleResult:
    """Strictly parse a provider string into a validated RoleResult.

    Rejects empty output, non-object top level, unknown top-level keys,
    unknown claim keys, unknown enum values, and wrong-typed fields -- no
    silent coercion, no retry.
    """
    text = raw.strip()
    if not text:
        raise ExecutorError("provider returned empty output")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ExecutorError(f"provider output is not valid JSON: {exc}") from None
    if not isinstance(data, dict):
        raise ExecutorError("provider output must be a JSON object")

    unknown = set(data.keys()) - _ROLE_RESULT_JSON_KEYS
    if unknown:
        raise ExecutorError(f"provider output has unknown RoleResult fields: {sorted(unknown)}")

    claims_data = data.get("claims", [])
    if not isinstance(claims_data, list):
        raise ExecutorError("'claims' must be a list")

    claims = tuple(_parse_claim(c) for c in claims_data)
    contradictions = tuple(_parse_contradiction(c) for c in data.get("contradictions", []))
    new_evidence = tuple(_parse_source_evidence(e) for e in data.get("new_source_evidence", []))

    completion_status = _enum(CompletionStatus, data.get("completion_status"), "completion_status")

    return RoleResult(
        task_id=_required_str(data, "task_id"),
        role_id=_required_str(data, "role_id"),
        role_version=_required_str(data, "role_version"),
        completion_status=completion_status,
        claims=claims,
        unknowns=tuple(data.get("unknowns", [])),
        contradictions=contradictions,
        provenance_summary=data["provenance_summary"],
        requests_for_more_evidence=tuple(data.get("requests_for_more_evidence", [])),
        warnings=tuple(data.get("warnings", [])),
        questions_for_r1=tuple(data.get("questions_for_r1", [])),
        new_source_evidence=new_evidence,
    )


def _parse_claim(c) -> RoleClaim:
    if not isinstance(c, dict):
        raise ExecutorError("each claim must be a JSON object")
    unknown = set(c.keys()) - _ROLE_CLAIM_JSON_KEYS
    if unknown:
        raise ExecutorError(f"claim has unknown fields: {sorted(unknown)}")

    source_type_summary = tuple(
        _enum(SourceType, v, "source_type_summary") for v in c.get("source_type_summary", [])
    )
    raw_label = c.get("voice_pattern_label")
    voice_pattern_label = (
        _enum(VoicePatternLabel, raw_label, "voice_pattern_label")
        if raw_label is not None else None
    )
    return RoleClaim(
        claim_id=_required_str(c, "claim_id"),
        subject_id=_required_str(c, "subject_id"),
        role_id=_required_str(c, "role_id"),
        claim=_required_str(c, "claim"),
        claim_type=_enum(ClaimType, c.get("claim_type"), "claim_type"),
        source_evidence_ids=tuple(c.get("source_evidence_ids", [])),
        source_type_summary=source_type_summary,
        confidence=_enum(Confidence, c.get("confidence"), "confidence"),
        rationale_summary=_required_str(c, "rationale_summary"),
        status=_enum(ClaimStatus, c.get("status"), "status"),
        target_module_or_layer=_required_str(c, "target_module_or_layer"),
        voice_pattern_label=voice_pattern_label,
    )


def _parse_contradiction(c) -> ContradictionRecord:
    if not isinstance(c, dict):
        raise ExecutorError("each contradiction must be a JSON object")
    return ContradictionRecord(
        contradiction_id=_required_str(c, "contradiction_id"),
        subject_id=_required_str(c, "subject_id"),
        claim_ids=tuple(c.get("claim_ids", [])),
        source_evidence_ids=tuple(c.get("source_evidence_ids", [])),
        description=_required_str(c, "description"),
        severity=_enum(Severity, c.get("severity"), "severity"),
        resolution_status=_enum(ResolutionStatus, c.get("resolution_status"), "resolution_status"),
        requires_human=bool(c.get("requires_human", False)),
        created_by=_required_str(c, "created_by"),
    )


def _parse_source_evidence(e) -> SourceEvidence:
    if not isinstance(e, dict):
        raise ExecutorError("each new_source_evidence entry must be a JSON object")
    return SourceEvidence(
        source_id=_required_str(e, "source_id"),
        subject_id=_required_str(e, "subject_id"),
        source_type=_enum(SourceType, e.get("source_type"), "source_type"),
        content_ref=_required_str(e, "content_ref"),
        provenance=_required_str(e, "provenance"),
        intake_timestamp=_iso_datetime(e),
        content_hash=_required_str(e, "content_hash"),
        evidence_snapshot_id=_required_str(e, "evidence_snapshot_id"),
    )


def _load_prompt_text(prompt_ref: str) -> str:
    """Safely load the exact vNext prompt file identified by ``prompt_ref``.

    Fail-closed path policy:
    - absolute refs rejected;
    - ``..`` traversal components rejected;
    - the resolved path must remain under the allowed ``roles/vnext/`` root;
    - the target must be a regular file;
    - content is read explicitly as UTF-8.

    No lookup fallback, no "latest", no auto-discovery. Loads the exact
    registry-selected prompt path only.
    """
    if not isinstance(prompt_ref, str) or not prompt_ref.strip():
        raise ExecutorError("prompt_ref must be a non-empty string")

    ref = prompt_ref.strip()
    if Path(ref).is_absolute():
        raise ExecutorError(f"prompt_ref must be a relative path: {ref!r}")

    pure = Path(ref)
    if ".." in pure.parts:
        raise ExecutorError(f"prompt_ref must not contain path traversal: {ref!r}")

    repo_root = Path(__file__).resolve().parents[2]
    allowed_root = (repo_root / "roles" / "vnext").resolve()
    candidate = (repo_root / pure).resolve()

    try:
        candidate.relative_to(allowed_root)
    except ValueError:
        raise ExecutorError(
            f"prompt_ref {ref!r} resolves outside the allowed roles/vnext root"
        ) from None

    if not candidate.is_file():
        raise ExecutorError(f"prompt_ref does not reference a regular file: {ref!r}")

    return candidate.read_text(encoding="utf-8")


def _assemble_messages(task, evidence, prior, *, prompt_text: str,
                       evidence_payloads) -> list:
    """Build the provider payload from the exact prompt plus bounded context.

    The loaded vNext prompt file text is injected verbatim as a ``system``
    message (never rewritten, never searched/discovered); the bounded
    task/evidence/prior context remains a single ``user`` message. Each visible
    evidence item renders its substantive, hash-bound payload so the model
    receives the actual owner-authored facts (metadata-only is never emitted).
    """
    lines = [
        "current_task:",
        f"- task_id: {task.task_id}",
        f"- role_id: {task.role_id}",
        f"- role_version: {task.role_version}",
        f"- subject_id: {task.subject_id}",
        f"task_goal: {task.task_goal}",
    ]
    lines.append("allowed_evidence:")
    for ev in evidence:
        lines.append(f"- {ev.source_id}: {ev.content_ref}")
        payload = evidence_payloads[ev.source_id]
        lines.append(f"  source_id: {ev.source_id}")
        lines.append(f"  content_ref: {ev.content_ref}")
        lines.append(f"  content_hash: {ev.content_hash}")
        lines.append(f"  substantive_payload: {_render_payload(payload)}")
    lines.append("allowed_prior_results:")
    for r in prior:
        lines.append(f"- {r.task_id}")
    return [
        {"role": "system", "content": prompt_text},
        {"role": "user", "content": "\n".join(lines)},
    ]


def _bind_allowed_payloads(allowed_evidence, evidence_payloads):
    """Fail-closed hash-binding of substantive payloads for allowed evidence.

    Always returns a ``source_id -> payload`` mapping in allowed-evidence order,
    raising ``ExecutorError`` before any provider invocation if
    ``evidence_payloads`` is ``None``/not a mapping, or if a payload is missing
    or its ``facts`` hash does not equal the matching ``SourceEvidence.content_hash``.
    """
    if evidence_payloads is None:
        raise ExecutorError("evidence_payloads is required for provider-bound execution")
    if not isinstance(evidence_payloads, Mapping):
        raise ExecutorError("evidence_payloads must be a mapping keyed by source_id")
    return {ev.source_id: _bound_payload(ev, evidence_payloads) for ev in allowed_evidence}


def _bound_payload(ev: SourceEvidence, evidence_payloads: Mapping) -> Mapping:
    """Fail-closed: bind one substantive payload to its SourceEvidence.

    Rejects a missing payload, a payload without a valid ``facts`` list, or a
    ``facts`` value whose canonical JSON SHA-256 differs from
    ``SourceEvidence.content_hash``. No metadata-only fallback, no silent omit.
    """
    payload = evidence_payloads.get(ev.source_id)
    if not isinstance(payload, Mapping):
        raise ExecutorError(
            f"evidence_payloads has no substantive payload for {ev.source_id!r}"
        )
    facts = payload.get("facts")
    if not isinstance(facts, (list, tuple)):
        raise ExecutorError(
            f"evidence payload {ev.source_id!r} has no valid 'facts' list"
        )
    recomputed = canonical_json_sha256(facts)
    if recomputed != ev.content_hash:
        raise ExecutorError(
            f"evidence payload {ev.source_id!r} facts hash {recomputed!r} "
            f"!= SourceEvidence.content_hash {ev.content_hash!r}"
        )
    return payload


def _render_payload(payload: Mapping) -> str:
    """Deterministic canonical-JSON serialization of a substantive payload."""
    return json.dumps(
        dict(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def _required_str(data, key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ExecutorError(f"missing or empty required string field {key!r}")
    return value


def _enum(cls, value, field: str):
    if not isinstance(value, str):
        raise ExecutorError(f"{field!r} must be a string")
    try:
        return cls(value)
    except ValueError:
        raise ExecutorError(
            f"{field!r} has unknown value {value!r} for {cls.__name__}"
        ) from None


def _iso_datetime(e) -> Any:
    from datetime import datetime
    value = _required_str(e, "intake_timestamp")
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        raise ExecutorError(f"intake_timestamp {value!r} is not a valid ISO-8601 datetime") from None