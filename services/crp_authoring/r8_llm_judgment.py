#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CRP MVP Slice 7A -- R8 LLM judgment component + deterministic wrapper composition (OFFLINE).

Implements ONLY the LLM-owned semantic surface of the R8 audit, per the
authoritative taxonomy (CRP_PRE_KIRA_TRUST_GATES_BROAD_CORE_ARCHITECTURE_PREFLIGHT §3.2):

- #5 role-boundary violations -- the PROSE/SEMANTIC half (HYBRID);
- #6 module/layer placement judgment (LLM_JUDGMENT);
- #7 missing evidence / UNKNOWN coverage judgment (LLM_JUDGMENT).

Deterministic checks (Slice 6) are NOT re-decided here. The LLM may only ADD
findings/severity; the non-overridable deterministic hard gates (leakage #9,
canon-write #10) cannot be cleared by any LLM result.

R8 independence boundary: input is the compiled ``CandidateCharacterPackage`` +
the permitted ``SourceEvidence`` ledger + the deterministic audit from Slice 6.
No raw RoleResult, no chain-of-thought, no hidden evaluation, no accepted Kira
benchmark, no runtime state, no canon access, no credential/provider internals.

R8 does NOT run through the generic ``execute_role_task`` RoleTask/RoleResult
cycle: it is an auditor producing audit findings, not a role producing
RoleClaims. A dedicated offline runner is provided here, using the existing
injected ``provider_callable`` shape (``list -> str``) without touching the
generic executor or provider transport. Because this is not the generic
role-execution path, R8 remains INACTIVE in the role registry -- there is no
falsely-activated generic-executor capability.

No provider, no network, no canon, no hidden benchmark, no mutation of inputs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Optional, Tuple

from .auditor_checks import AuditPolicy, run_deterministic_audit
from .candidate_package import CandidateCharacterPackage
from .contracts import SourceEvidence
from .errors import CrpValidationError
from .reconstruction_audit import (
    AuditCheckClassification,
    AuditCheckOutcome,
    AuditCheckResult,
    AuditFinding,
    AuditVerdict,
    ReconstructionAudit,
    compose_verdict,
    resolve_final_verdict,
)

# Provider callable shape (mirrors executor.py's injected-callable contract,
# but defined locally so this module has no executor coupling).
ProviderCallable = Callable[[list], str]

R8_ROLE_ID = "R8"
R8_ROLE_VERSION = "v1"

# The three LLM-owned semantic check IDs (closed set; parser rejects any other).
CHECK_ROLE_BOUNDARY_SEMANTIC = "R8_ROLE_BOUNDARY_SEMANTIC"   # #5 semantic half (HYBRID)
CHECK_MODULE_PLACEMENT = "R8_MODULE_PLACEMENT"               # #6 (LLM_JUDGMENT)
CHECK_UNKNOWN_COVERAGE = "R8_UNKNOWN_COVERAGE"               # #7 (LLM_JUDGMENT)

_SEMANTIC_CHECK_IDS = (
    CHECK_ROLE_BOUNDARY_SEMANTIC,
    CHECK_MODULE_PLACEMENT,
    CHECK_UNKNOWN_COVERAGE,
)

_CHECK_CLASSIFICATION = {
    CHECK_ROLE_BOUNDARY_SEMANTIC: AuditCheckClassification.HYBRID,
    CHECK_MODULE_PLACEMENT: AuditCheckClassification.LLM_JUDGMENT,
    CHECK_UNKNOWN_COVERAGE: AuditCheckClassification.LLM_JUDGMENT,
}

_R8_PROMPT_PATH = "roles/vnext/ROLE_8_INDEPENDENT_EVIDENCE_AUDITOR_v1_PROMPT.md"


@dataclass(frozen=True)
class R8SemanticFinding:
    """One LLM-emitted semantic audit finding, optionally pinned to existing ids."""

    check_id: str
    message: str
    claim_id: Optional[str] = None
    evidence_ids: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _req(self.check_id, "check_id")
        _req(self.message, "message")
        if self.claim_id is not None:
            _req(self.claim_id, "claim_id")
        if not isinstance(self.evidence_ids, tuple):
            raise CrpValidationError("evidence_ids must be a tuple")
        object.__setattr__(self, "evidence_ids", tuple(self.evidence_ids))


@dataclass(frozen=True)
class R8SemanticCheckResult:
    """One LLM-judgment check result (exact check_id, outcome, findings)."""

    check_id: str
    outcome: AuditCheckOutcome
    findings: Tuple[R8SemanticFinding, ...]

    def __post_init__(self) -> None:
        if self.check_id not in _SEMANTIC_CHECK_IDS:
            raise CrpValidationError(f"unknown semantic check id {self.check_id!r}")
        if not isinstance(self.outcome, AuditCheckOutcome):
            raise CrpValidationError("outcome must be an AuditCheckOutcome")
        if self.outcome is AuditCheckOutcome.BLOCKED:
            # Hard BLOCKED belongs to deterministic gates only; an LLM may not
            # declare one.
            raise CrpValidationError("LLM check outcome may not be BLOCKED")
        if not isinstance(self.findings, tuple):
            raise CrpValidationError("findings must be a tuple")
        for f in self.findings:
            if not isinstance(f, R8SemanticFinding):
                raise CrpValidationError("findings must contain R8SemanticFinding instances")
        object.__setattr__(self, "findings", tuple(self.findings))


@dataclass(frozen=True)
class R8LlmJudgment:
    """The typed parsed result of the R8 LLM semantic judgment."""

    package_id: str
    subject_id: str
    role_id: str
    role_version: str
    checks: Tuple[R8SemanticCheckResult, ...]
    narrative: str

    def __post_init__(self) -> None:
        _req(self.package_id, "package_id")
        _req(self.subject_id, "subject_id")
        _req(self.role_id, "role_id")
        _req(self.role_version, "role_version")
        if not isinstance(self.checks, tuple):
            raise CrpValidationError("checks must be a tuple")
        if not isinstance(self.narrative, str):
            raise CrpValidationError("narrative must be a string")
        object.__setattr__(self, "checks", tuple(self.checks))


# ---------------------------------------------------------------
# Model return parsing (fail-closed)
# ---------------------------------------------------------------

_R8_LLM_JSON_KEYS = frozenset({
    "package_id", "subject_id", "role_id", "role_version",
    "checks", "narrative",
})
_CHECK_JSON_KEYS = frozenset({"check_id", "outcome", "findings"})
_FINDING_JSON_KEYS = frozenset({"check_id", "message", "claim_id", "evidence_ids"})


def parse_r8_llm_result(
    raw: str,
    package: CandidateCharacterPackage,
    evidence: Tuple[SourceEvidence, ...],
) -> R8LlmJudgment:
    """Strictly parse the LLM's structured judgment, validating every exact-
    bound returned field against current input metadata (fail-closed).

    Rejects: invalid JSON, non-object top level, unknown fields, wrong
    package/subject/role identity, wrong role_version, unknown/duplicate/missing
    check ids, BLOCKED LLM outcome, invalid outcome enum, and any referenced
    claim_id/evidence_id not present in the package/ledger.
    """
    text = raw.strip()
    if not text:
        raise CrpValidationError("R8 provider returned empty output")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise CrpValidationError(f"R8 provider output is not valid JSON: {exc}") from None
    if not isinstance(data, dict):
        raise CrpValidationError("R8 provider output must be a JSON object")

    unknown = set(data.keys()) - _R8_LLM_JSON_KEYS
    if unknown:
        raise CrpValidationError(f"R8 provider output has unknown fields: {sorted(unknown)}")

    # --- exact-bound echo validation ------------------------------------
    if data.get("role_id") != R8_ROLE_ID:
        raise CrpValidationError(f"R8 role_id mismatch: {data.get('role_id')!r}")
    if data.get("role_version") != R8_ROLE_VERSION:
        raise CrpValidationError(f"R8 role_version mismatch: {data.get('role_version')!r}")
    if data.get("package_id") != package.package_id:
        raise CrpValidationError("R8 package_id mismatch")
    if data.get("subject_id") != package.subject_id:
        raise CrpValidationError("R8 subject_id mismatch")

    checks_data = data.get("checks")
    if not isinstance(checks_data, list) or len(checks_data) != 3:
        raise CrpValidationError("R8 output must contain exactly the three semantic checks")

    claim_ids = {c.claim_id for c in package.claims}
    evidence_ids = {ev.source_id for ev in evidence if isinstance(ev, SourceEvidence)}

    seen: set = set()
    checks: list = []
    for cd in checks_data:
        if not isinstance(cd, dict):
            raise CrpValidationError("each R8 check must be an object")
        unknown = set(cd.keys()) - _CHECK_JSON_KEYS
        if unknown:
            raise CrpValidationError(f"R8 check has unknown fields: {sorted(unknown)}")
        check_id = cd.get("check_id")
        if check_id not in _SEMANTIC_CHECK_IDS:
            raise CrpValidationError(f"unknown R8 semantic check id {check_id!r}")
        if check_id in seen:
            raise CrpValidationError(f"duplicate R8 semantic check id {check_id!r}")
        seen.add(check_id)
        outcome = _decode_outcome(cd.get("outcome"))
        findings = _parse_findings(cd.get("findings"), check_id, claim_ids, evidence_ids)
        checks.append(R8SemanticCheckResult(check_id, outcome, findings))

    missing = set(_SEMANTIC_CHECK_IDS) - seen
    if missing:
        raise CrpValidationError(f"R8 output missing required semantic checks: {sorted(missing)}")

    return R8LlmJudgment(
        package_id=data["package_id"],
        subject_id=data["subject_id"],
        role_id=data["role_id"],
        role_version=data["role_version"],
        checks=tuple(checks),
        narrative=data.get("narrative", ""),
    )


def _parse_findings(raw_findings, check_id, claim_ids, evidence_ids):
    if raw_findings is None:
        return ()
    if not isinstance(raw_findings, list):
        raise CrpValidationError("R8 findings must be a list")
    findings: list = []
    for fd in raw_findings:
        if not isinstance(fd, dict):
            raise CrpValidationError("each R8 finding must be an object")
        unknown = set(fd.keys()) - _FINDING_JSON_KEYS
        if unknown:
            raise CrpValidationError(f"R8 finding has unknown fields: {sorted(unknown)}")
        claim_id = fd.get("claim_id")
        if claim_id is not None:
            if claim_id not in claim_ids:
                raise CrpValidationError(f"R8 finding references unknown claim_id {claim_id!r}")
        evidence_ids_raw = fd.get("evidence_ids", [])
        if not isinstance(evidence_ids_raw, list):
            raise CrpValidationError("R8 finding evidence_ids must be a list")
        for ev_id in evidence_ids_raw:
            if ev_id not in evidence_ids:
                raise CrpValidationError(f"R8 finding references unknown evidence_id {ev_id!r}")
        findings.append(R8SemanticFinding(
            check_id=check_id,
            message=_required(fd.get("message"), "message"),
            claim_id=claim_id,
            evidence_ids=tuple(evidence_ids_raw),
        ))
    return tuple(findings)


def _decode_outcome(value) -> AuditCheckOutcome:
    if not isinstance(value, str):
        raise CrpValidationError("R8 outcome must be a string")
    try:
        return AuditCheckOutcome(value)
    except ValueError:
        raise CrpValidationError(f"unknown R8 outcome {value!r}") from None


# ---------------------------------------------------------------
# Prompt rendering (input minimization)
# ---------------------------------------------------------------

def render_r8_messages(
    package: CandidateCharacterPackage,
    evidence: Tuple[SourceEvidence, ...],
    deterministic_audit: ReconstructionAudit,
) -> list:
    """Render the R8 LLM input as system (prompt file) + user (bounded data).

    Exposes every exact-bound field the model must later echo or cite, plus the
    standalone deterministic audit summary. No hidden benchmark, no raw
    RoleResults, no credentials.
    """
    prompt_text = _load_prompt_text()
    user = _render_data_block(package, evidence, deterministic_audit)
    return [
        {"role": "system", "content": prompt_text},
        {"role": "user", "content": user},
    ]


def _render_data_block(package, evidence, deterministic_audit) -> str:
    lines: list = []
    lines.append("AUDIT_IDENTITY")
    lines.append(f"- package_id: {package.package_id}")
    lines.append(f"- subject_id: {package.subject_id}")
    lines.append(f"- package_version: {package.package_version}")
    lines.append(f"- source_snapshot_id: {package.source_snapshot_id}")
    lines.append(f"- role_id: {R8_ROLE_ID}")
    lines.append(f"- role_version: {R8_ROLE_VERSION}")

    lines.append("PACKAGE_CLAIMS")
    for claim in package.claims:
        lines.append(
            f"- {claim.claim_id} role={claim.role_id} type={claim.claim_type.value} "
            f"target={claim.target_module_or_layer} confidence={claim.confidence.value} "
            f"text={claim.claim!r} evidence={list(claim.source_evidence_ids)}"
        )
    lines.append("PACKAGE_UNKNOWNS")
    for u in package.unknowns:
        lines.append(f"- {u!r}")
    lines.append("PACKAGE_CONTRADICTIONS")
    for record in package.contradictions:
        lines.append(
            f"- {record.contradiction_id} claim_ids={list(record.claim_ids)} "
            f"resolution={record.resolution_status.value}"
        )

    lines.append("EVIDENCE_LEDGER")
    for ev in evidence:
        if isinstance(ev, SourceEvidence):
            lines.append(
                f"- {ev.source_id} type={ev.source_type.value} "
                f"subject={ev.subject_id} content_ref={ev.content_ref}"
            )

    lines.append("DETERMINISTIC_AUDIT_SUMMARY")
    lines.append(f"- verdict: {deterministic_audit.verdict.value}")
    for check in deterministic_audit.checks:
        lines.append(f"- {check.check}: {check.outcome.value}")
        for f in check.findings:
            lines.append(f"    - {f.message}")

    return "\n".join(lines)


def _load_prompt_text() -> str:
    repo_root = Path(__file__).resolve().parents[2]
    candidate = (repo_root / _R8_PROMPT_PATH).resolve()
    if not candidate.is_file():
        raise CrpValidationError(f"R8 prompt file not found: {_R8_PROMPT_PATH!r}")
    return candidate.read_text(encoding="utf-8")


# ---------------------------------------------------------------
# Composition + offline runner
# ---------------------------------------------------------------

def compose_final_audit(
    deterministic_audit: ReconstructionAudit,
    judgment: R8LlmJudgment,
) -> ReconstructionAudit:
    """Combine deterministic Slice-6 findings with parsed LLM semantic findings.

    Only ADDITIVE: LLM checks are appended as non-hard-blocker entries; the
    deterministic verdict may be worsened, never upgraded. A deterministic
    BLOCKED stays BLOCKED (``resolve_final_verdict``).
    """
    if not isinstance(deterministic_audit, ReconstructionAudit):
        raise TypeError("deterministic_audit must be a ReconstructionAudit")
    if not isinstance(judgment, R8LlmJudgment):
        raise TypeError("judgment must be an R8LlmJudgment")

    llm_checks: list = []
    for jc in judgment.checks:
        findings = tuple(
            AuditFinding(jc.check_id, "error", _fmt_finding(jv))
            for jv in jc.findings
        )
        llm_checks.append(AuditCheckResult(
            check=jc.check_id,
            classification=_CHECK_CLASSIFICATION[jc.check_id],
            outcome=jc.outcome,
            findings=findings,
            hard_blocker=False,
        ))

    llm_verdict = compose_verdict(tuple(llm_checks))
    final_verdict = resolve_final_verdict(deterministic_audit.verdict, llm_verdict)
    combined_checks = deterministic_audit.checks + tuple(llm_checks)
    combined_defects = deterministic_audit.defects + tuple(
        f for c in llm_checks for f in c.findings
        if c.outcome is not AuditCheckOutcome.PASS
    )

    return ReconstructionAudit(
        audit_id=deterministic_audit.audit_id,
        package_id=deterministic_audit.package_id,
        package_hash=deterministic_audit.package_hash,
        auditor_role_version=deterministic_audit.auditor_role_version,
        evidence_snapshot_id=deterministic_audit.evidence_snapshot_id,
        checks=combined_checks,
        verdict=final_verdict,
        defects=combined_defects,
        correction_requests=deterministic_audit.correction_requests,
        created_at=deterministic_audit.created_at,
        judgment_provider_ref=deterministic_audit.judgment_provider_ref,
    )


def run_r8_analysis(
    package: CandidateCharacterPackage,
    evidence: Tuple[SourceEvidence, ...],
    provider_callable: ProviderCallable,
    *,
    forbidden_refs: Tuple[str, ...] = (),
) -> ReconstructionAudit:
    """Offline R8 composition: deterministic audit -> (skip if BLOCKED) -> LLM
    judgment -> parse -> compose. Fail-fast on a deterministic hard blocker.
    """
    if not isinstance(package, CandidateCharacterPackage):
        raise TypeError("package must be a CandidateCharacterPackage")
    if not isinstance(evidence, tuple):
        raise TypeError("evidence must be a tuple")
    if not callable(provider_callable):
        raise TypeError("provider_callable is a required injected callable")

    deterministic_audit = run_deterministic_audit(
        package, evidence, AuditPolicy(forbidden_refs=tuple(forbidden_refs)),
    )
    if deterministic_audit.verdict is AuditVerdict.BLOCKED:
        # Hard gate fail-fast: never invoke the LLM; verdict is final and
        # non-overridable.
        return deterministic_audit

    messages = render_r8_messages(package, evidence, deterministic_audit)
    raw = provider_callable(messages)
    if not isinstance(raw, str):
        raise CrpValidationError("provider_callable must return a string")

    judgment = parse_r8_llm_result(raw, package, evidence)
    return compose_final_audit(deterministic_audit, judgment)


def _fmt_finding(finding: R8SemanticFinding) -> str:
    refs = ""
    if finding.claim_id is not None or finding.evidence_ids:
        refs = f" (claim={finding.claim_id}, evidence={list(finding.evidence_ids)})"
    return f"{finding.message}{refs}"


def _req(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise CrpValidationError(f"{field_name} must be a non-empty string")


def _required(value, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CrpValidationError(f"missing or empty required field {field_name!r}")
    return value