#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CRP MVP Slice 7B-G -- minimal R8 live-smoke glue runner (OFFLINE).

Joins two already-committed halves into the single frozen future live call path:

    frozen synthetic smoke input
        -> deterministic R8 precheck (inside ``run_r8_analysis``; fail-fast on BLOCKED)
        -> existing ``build_provider_callable`` (deepseek / deepseek-v4-pro)
        -> existing ``run_r8_analysis`` (with a one-shot guarded provider)
        -> typed ``R8SmokeResult`` (unambiguous one-shot accounting)

This is a controlled VALIDATION / SMOKE entrypoint only. It is NOT the future
orchestrator, NOT a generic R8 layer, NOT a runtime subsystem, NOT a Kira
runner, and it does NOT activate R8 in the role registry.

Provider accounting invariants (load-bearing):

- at most ONE provider invocation per run (one-shot guard; second call fails
  closed locally);
- no retry, no fallback provider/model;
- a pre-call deterministic BLOCKED consumes NO attempt (provider never invoked);
- once the provider callable is invoked the attempt is consumed, regardless of
  transport / timeout / parse / identity / composition failure;
- ``provider_path_pass`` (transport/parse/composition succeeded) is kept
  DISTINCT from ``audit_content_outcome`` (the final audit verdict, which may
  legitimately be FAIL/INCONCLUSIVE).

No provider, no network, no credential-value read, no canon/PAC/Sandbox access.
The live callable is provided only through ``run_r8_live_smoke()`` and is never
invoked by any offline test or by this module at import time.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional, Tuple

# Tool bootstrap: resolve both the repo root (services.crp_authoring) and the
# tools directory (crp_provider_adapter / llm_provider) regardless of how this
# module is imported.
_REPO_ROOT = Path(__file__).resolve().parents[1]
_TOOLS_DIR = Path(__file__).resolve().parents[0]
for _p in (str(_REPO_ROOT), str(_TOOLS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from services.crp_authoring.candidate_package import (  # noqa: E402
    CandidateCharacterPackage,
    PackageStatus,
)
from services.crp_authoring.contracts import (  # noqa: E402
    ClaimStatus,
    ClaimType,
    Confidence,
    RoleClaim,
    SourceEvidence,
    SourceType,
)
from services.crp_authoring.errors import CrpValidationError  # noqa: E402
from services.crp_authoring.reconstruction_audit import AuditVerdict  # noqa: E402
from services.crp_authoring.r8_llm_judgment import run_r8_analysis  # noqa: E402
from crp_provider_adapter import (  # noqa: E402
    ProviderConfig,
    build_provider_callable,
)
from llm_provider import LLMProviderError  # noqa: E402


# ---------------------------------------------------------------------------
# Frozen smoke identity (must match Slice 7B preflight manifest)
# ---------------------------------------------------------------------------

SMOKE_ID = "R8-SMOKE-001"
PACKAGE_ID = "pkg-001"
SUBJECT_ID = "char-subject-1"
SOURCE_SNAPSHOT_ID = "snapshot-1"
EVIDENCE_ID = "se-001"
CLAIM_ID = "c1"

# Frozen provider configuration (name-only credential reference; no secret).
SMOKE_PROVIDER_ID = "deepseek"
SMOKE_MODEL = "deepseek-v4-pro"
SMOKE_BASE_URL = "https://api.deepseek.com"
SMOKE_CREDENTIAL_ENV = "DEEPSEEK_API_KEY"
SMOKE_TIMEOUT_S = 60.0
SMOKE_MAX_TOKENS = 1200


# ---------------------------------------------------------------------------
# Synthetic smoke input (deterministic, non-Kira, no RoleResult)
# ---------------------------------------------------------------------------

def make_r8_smoke_package() -> CandidateCharacterPackage:
    """Deterministically build the frozen minimal package (one clean FACT claim)."""
    claim = RoleClaim(
        claim_id=CLAIM_ID,
        subject_id=SUBJECT_ID,
        role_id="R1",
        claim="Subject explicitly prefers calm, low-stimulation environments.",
        claim_type=ClaimType.FACT,
        source_evidence_ids=(EVIDENCE_ID,),
        source_type_summary=(SourceType.OWNER_DIRECT,),
        confidence=Confidence.KNOWN,
        rationale_summary="Owner stated directly.",
        status=ClaimStatus.PROPOSED,
        target_module_or_layer="psychology.P0",
    )
    return CandidateCharacterPackage(
        package_id=PACKAGE_ID,
        subject_id=SUBJECT_ID,
        package_version=0,
        source_snapshot_id=SOURCE_SNAPSHOT_ID,
        role_result_refs=(),
        claims=(claim,),
        contradictions=(),
        unknowns=(),
        psychology_candidate={"P0": (claim,)},
        voice_candidate={},
        validation_results={},
        audit_result=None,
        provenance_manifest={"psychology.P0": (CLAIM_ID,)},
        created_at=datetime.now(timezone.utc).replace(microsecond=0),
        status=PackageStatus.DRAFT,
    )


def make_r8_smoke_evidence() -> Tuple[SourceEvidence, ...]:
    """Deterministically build the frozen permitted evidence ledger (clean)."""
    return (
        SourceEvidence(
            source_id=EVIDENCE_ID,
            subject_id=SUBJECT_ID,
            source_type=SourceType.OWNER_DIRECT,
            content_ref="ref://raw/001",
            provenance="synthetic-smoke",
            intake_timestamp=datetime.now(timezone.utc).replace(microsecond=0),
            content_hash="a" * 64,
            evidence_snapshot_id=SOURCE_SNAPSHOT_ID,
        ),
    )


def make_r8_smoke_provider_config() -> ProviderConfig:
    """Return the frozen one-shot provider configuration (no secret value)."""
    return ProviderConfig(
        provider_id=SMOKE_PROVIDER_ID,
        model=SMOKE_MODEL,
        base_url=SMOKE_BASE_URL,
        credential_env=SMOKE_CREDENTIAL_ENV,
        timeout_s=SMOKE_TIMEOUT_S,
        max_tokens=SMOKE_MAX_TOKENS,
    )


# ---------------------------------------------------------------------------
# One-shot guard
# ---------------------------------------------------------------------------

@dataclass
class OneShotGuard:
    """Wrap a provider callable so that at most one invocation is possible.

    ``attempts`` is observable; a second invocation raises fail-closed locally
    (never reaches the underlying provider). The one successful invocation (if
    any) marks the attempt consumed.
    """

    provider_callable: Callable[[list], str]

    attempts: int = 0

    def __call__(self, messages: list) -> str:
        if self.attempts >= 1:
            raise CrpValidationError(
                "one-shot provider guard: a second provider invocation is forbidden"
            )
        self.attempts += 1
        return self.provider_callable(messages)


# ---------------------------------------------------------------------------
# Typed result
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class R8SmokeResult:
    smoke_id: str
    package_id: str
    subject_id: str
    provider_id: str
    model: str
    provider_attempts: int
    attempt_consumed: bool
    provider_path_pass: bool
    audit_content_outcome: Optional[str]
    final_audit_verdict: Optional[str]
    error_stage: Optional[str]
    message: str


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_r8_smoke(
    provider_callable: Callable[[list], str],
    *,
    forbidden_refs: Tuple[str, ...] = (),
) -> R8SmokeResult:
    """Run the frozen synthetic smoke through the one-shot guarded R8 path.

    ``provider_callable`` is the injected provider (a fake in tests; the real
    ``build_provider_callable(...)`` for the future live call).
    """
    if not callable(provider_callable):
        raise TypeError("provider_callable is a required injected callable")

    package = make_r8_smoke_package()
    evidence = make_r8_smoke_evidence()
    guard = OneShotGuard(provider_callable)

    base = dict(
        smoke_id=SMOKE_ID,
        package_id=PACKAGE_ID,
        subject_id=SUBJECT_ID,
        provider_id=SMOKE_PROVIDER_ID,
        model=SMOKE_MODEL,
        provider_attempts=0,
        attempt_consumed=False,
        provider_path_pass=False,
        audit_content_outcome=None,
        final_audit_verdict=None,
        error_stage=None,
        message="",
    )

    def _result(**overrides) -> R8SmokeResult:
        merged = dict(base)
        merged.update(overrides)
        return R8SmokeResult(**merged)

    try:
        audit = run_r8_analysis(package, evidence, guard, forbidden_refs=tuple(forbidden_refs))
    except LLMProviderError as exc:
        # Provider was invoked (guard.attempts == 1) and raised; attempt consumed.
        return _result(
            provider_attempts=guard.attempts,
            attempt_consumed=guard.attempts >= 1,
            error_stage="provider",
            message=f"provider failure: {exc}",
        )
    except CrpValidationError as exc:
        # Parse or exact-bound validation failure (post-provider). Attempt consumed
        # if the provider was reached.
        return _result(
            provider_attempts=guard.attempts,
            attempt_consumed=guard.attempts >= 1,
            error_stage="parse_or_validation",
            message=f"R8 result failure: {exc}",
        )
    except Exception as exc:  # defensive fail-closed
        return _result(
            provider_attempts=guard.attempts,
            attempt_consumed=guard.attempts >= 1,
            error_stage="composition",
            message=f"composition failure: {exc}",
        )

    if audit.verdict is AuditVerdict.BLOCKED:
        # Deterministic hard gate blocked BEFORE the provider (fail-fast); no
        # attempt consumed.
        return _result(
            provider_attempts=0,
            attempt_consumed=False,
            provider_path_pass=False,
            error_stage="deterministic_block",
            final_audit_verdict=audit.verdict.value,
            message="deterministic hard gate blocked before provider",
        )

    return _result(
        provider_attempts=guard.attempts,
        attempt_consumed=guard.attempts >= 1,
        provider_path_pass=guard.attempts == 1,
        audit_content_outcome=audit.verdict.value,
        final_audit_verdict=audit.verdict.value,
        message="smoke completed",
    )


def run_r8_live_smoke() -> R8SmokeResult:
    """Frozen future LIVE one-shot path. NOT invoked by any offline test.

    This composes ``build_provider_callable(make_r8_smoke_provider_config())``
    with ``run_r8_smoke``. It performs a REAL provider call and therefore
    requires explicit owner authorization (R4) before it is ever invoked.
    """
    config = make_r8_smoke_provider_config()
    provider_callable = build_provider_callable(config)
    return run_r8_smoke(provider_callable)