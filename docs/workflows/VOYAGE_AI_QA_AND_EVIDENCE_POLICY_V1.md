# VOYAGE_AI_QA_AND_EVIDENCE_POLICY_V1

> Status: OWNER-RATIFIED
> Decision: OD-GOV-FAST-01
> Ratified: 2026-09-16

## 1. QA DECISION INPUTS

The independent-QA decision uses:

risk + semantic trigger + reversibility + test strength.

## 2. INDEPENDENT_AI_REVIEW_REQUIRED

For V1, independent AI review is REQUIRED for high-semantic changes including:

- serialization contract
- identity semantics
- hash/content binding
- persistence
- memory namespace
- state namespace / state isolation
- fallback / fail-closed behavior
- parser
- state machine
- migration
- security
- credentials
- network/provider behavior
- activation pointer
- public contract/API
- multi-module core logic
- business logic not fully encoded by deterministic tests

HIGH semantic trigger remains INDEPENDENT_AI_REVIEW_REQUIRED in V1 even if tests are strong.

R3 ALWAYS requires independent AI review + owner.

## 3. QA_NOT_NORMALLY_REQUIRED

Normally NO independent QA for:

- docs-only
- formatting
- mechanical rename
- test-only where product semantics are unchanged
- fixture-only where product semantics are unchanged
- small pure helper with strong deterministic tests
- isolated deterministic adapter with strongly tested contract

Any uncertainty MAY raise verification depth.

## 4. IMPLEMENTER / REVIEWER SELECTION

Implementation model/tool is selected per slice.

A task brief MAY explicitly designate a model/tool for that slice.

This governance policy does NOT permanently assign implementation to a specific vendor or model.

Independent reviewer/model/tool is selected per slice according to the required independence, task characteristics, availability, and owner/project constraints.

The reviewer MUST NOT be permanently bound by this policy to a specific vendor or model.

Where independence is required, the selected review arrangement MUST provide the independence required by the slice.

Different-model review MAY be used where the cost of missed semantic defects justifies it.

Do NOT claim different-model review is empirically superior in all cases.

## 5. ONE QA ROUND

For unchanged candidate content: maximum ONE independent QA round by default.

Do NOT perform QA-of-QA.

Do NOT rerun semantic QA merely because of human prose/report transcription errors.

## 6. EVIDENCE AUTHORITY

Authoritative machine evidence takes precedence over copied human prose.

Long SHA/OID values SHOULD NOT be manually transcribed through chat as the control input when a canonical evidence file is available.

Human report is explanatory. Machine artifact is authoritative for machine facts.

## 7. EVIDENCE REUSE

Evidence MAY be reused when relevant identity remains unchanged:

- candidate content
- required tests
- required fixtures
- dependency lock state
- policy
- scope
- risk / QA requirement
- relevant test environment

Report typo: does NOT invalidate evidence.

Chat typo: does NOT invalidate evidence if authorization still binds the correct artifact.

Unchanged QA artifact: MAY be reused.

Candidate change: invalidates relevant evidence.

Test/fixture change: invalidates test evidence.

Dependency change: invalidates relevant evidence.

Policy change: invalidates policy-dependent evidence.

Scope/risk/QA requirement change: invalidate as applicable.

## 8. FAILURE TAXONOMY

| Class | Evidence invalidated? | Tests rerun? | AI QA rerun? | Owner required? | New authorization? |
|---|---|---|---|---|---|
| CODE_DEFECT | yes | yes | per trigger | yes | yes |
| TEST_DEFECT | yes | yes | no (unless semantics) | maybe | maybe |
| QA_DEFECT | QA evidence invalidated | yes | yes | yes | yes |
| REPORT_TRANSCRIPTION_DEFECT | no (if machine evidence + candidate unchanged) | no | no | no | no |
| TOOLING_DEFECT | tool evidence invalidated | as affected | no | yes | maybe |
| ENVIRONMENT_DEFECT | environment-dependent evidence invalidated | as affected | no | maybe | no |
| SCOPE_DEFECT | scope-dependent evidence invalidated | no | no | yes | yes |
| STALE_STATE | yes (for affected slice) | no | no | yes | yes |
| PROMOTION_CONFLICT | no | no | no | yes | yes |
| AUTHORIZATION_STALE | yes (for affected slice) | no | no | yes | yes |
| AUTHORIZATION_RECONCILIATION | no (if semantics within intent) | no | no | yes (ratify) | yes (ratify) |

Important examples:

REPORT_TRANSCRIPTION_DEFECT: if machine evidence and candidate are unchanged → no tests, no QA, no new authorization (unless authorization itself is wrong).

AUTHORIZATION_RECONCILIATION: used when an executed mutation remains semantically within intent but differs from literal bounded wording, and requires owner ratification before the next mutation. Do NOT treat automatically as CODE_DEFECT.

## 9. STOP RULE

If required evidence cannot establish an unchanged candidate: STOP.

Do NOT assume reuse.

## 10. NO SILENT DOWNGRADE

Automation MAY raise verification depth.

V1 automation MUST NOT automatically lower a required semantic QA class.
