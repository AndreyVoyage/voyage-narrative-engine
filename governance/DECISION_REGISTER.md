# Owner Decision Register

> **Purpose.** Canonical index of owner-ratified governance decisions for the
> Narrative / VNE engineering and authoring-development scope.
> New decisions are added exactly once, in order, with a stable `OD-*` ID.

| Decision ID | Title | Status | Date |
|---|---|---|---|
| OD-GOV-RISK-01 | Risk & Verification Policy v1 | OWNER-RATIFIED | 2026-08-20 |
| OD-GOV-BRANCH-01 | Branch Lineage, Task Batching & Publication Freshness Policy v1 | OWNER-RATIFIED | 2026-09-18 |

## OD-GOV-RISK-01 — Risk & Verification Policy v1

- **Status:** OWNER-RATIFIED
- **Scope:** All NARRATIVE / VNE engineering and authoring-development tasks.
- **Core rule:** RISK ASSESSMENT IS MANDATORY. INDEPENDENT AUDIT IS RISK-TRIGGERED.
- **Canonical source:** `governance/RISK_VERIFICATION_POLICY_v1.md`

## OD-GOV-BRANCH-01 — Branch Lineage, Task Batching & Publication Freshness Policy v1

- **Status:** OWNER-RATIFIED
- **Scope:** All NARRATIVE / VNE engineering task branches, worktrees, and
  publication to an authoritative integration ref.
- **Core rule:** Anti-microslice batching; split only on a real contract
  boundary; every significant task branch/worktree can declare its base
  target/SHA and return target; STOP on architectural divergence rather than
  auto-integrating a superseded candidate; a fresh pre-push remote
  observation is required only when publication authorization depends on an
  expected target OID.
- **Canonical source:** `governance/BRANCH_LINEAGE_AND_TASK_BATCHING_POLICY_v1.md`
- **Note:** the operational branch/worktree registry and generated branch
  map required by this decision are not yet built; that is the next bounded
  task, `VOYAGE_BRANCH_WORKTREE_REGISTRY_V1`.