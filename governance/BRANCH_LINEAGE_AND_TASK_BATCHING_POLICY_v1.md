# Branch Lineage, Task Batching & Publication Freshness Policy v1

> **Decision ID:** OD-GOV-BRANCH-01
> **Status:** OWNER-RATIFIED
> **Date:** 2026-09-18
> **Scope:** All NARRATIVE / VNE engineering task branches, worktrees, and
> publication to an authoritative integration ref.
> **Canonical.** Registered once in `governance/DECISION_REGISTER.md`.
> Complements, and does not replace or weaken,
> `governance/RISK_VERIFICATION_POLICY_v1.md`.

---

## 0. Provenance

This policy formalizes a locally recorded improvement batch
(`docs/workflows/VOYAGE_FRAMEWORK_UPDATE_BATCH_2026_09_BRANCH_AND_FAST_LANE_LESSONS_V1.md`,
recorded 2026-09-18 in the `vne-crp-mvp-v1` worktree) after reconciling it
against this repository's actual current governance surface. That source
file lives in a now-architecturally-superseded worktree, remains untracked
there, and carries no authority itself -- only this document and its
`DECISION_REGISTER.md` entry are canonical.

**Reconciliation note.** The source batch's own "already covered by
existing policy" section referenced `VOYAGE_REVERSIBLE_FAST_LANE_V1`,
`VOYAGE_AI_QA_AND_EVIDENCE_POLICY_V1`, and `VOYAGE_FAST_LANE_JOURNAL_V1`.
None of those three documents exist anywhere on this architecture line
(verified: `docs/workflows/` here contains only
`CONTEXT_RETIREMENT_PROTOCOL.md`). Their content is therefore neither
confirmed nor contradicted by this document -- only
`governance/RISK_VERIFICATION_POLICY_v1.md` is treated as this line's
existing canonical policy, and nothing below conflicts with it. This
document's own drafting is itself a live instance of the lesson recorded in
§12: source material built against one architecture line needed
reconciliation, not blind adoption, once read against the current one.

---

## 1. Anti-microslice batching (Core)

When one task's scope is already understood and its checks are
deterministic: one preflight → one owner decision → one bounded mutation →
one final verification → one commit/publication. Do not split into
separate slices merely for procedural formality.

## 2. Split only on a real boundary (Core)

Create separate implementation slices only for a real reason: an
architectural contract boundary, a materially different risk class,
genuinely unknown scope, a provider/network boundary, a migration, runtime
activation, or a next step that genuinely depends on the previous result.
Do not split by default.

## 3. Whole-script fail-closed execution (Core)

Mutation/publication scripts whose safety depends on STOP/throw semantics
(e.g. PowerShell `.ps1`) must be authored, validated, and run as a whole.
Do not execute such a script line-by-line interactively -- a later,
separately pasted command can still run after an earlier one has already
thrown.

## 4. Ignore-aware file evidence (Core)

Plain `git status` is not sufficient evidence for ignored/untracked files.
For exact local-file allowlists, combine as needed: direct filesystem
existence checks, `git ls-files`, `git check-ignore`, and explicit
hashes/sizes. Do not assume an ignored untracked file will necessarily
appear as `??`.

## 5. Branch lineage guard (Core)

Every significant task branch/worktree should be able to declare its base
target, exact base SHA, and intended return/integration target, and the
framework should be able to cheaply answer: *"Is this task's base still
valid relative to its declared integration target?"* This requirement is
canonical as of this document; the operational registry that answers it
repository-wide is explicitly deferred (§9).

## 6. Architectural divergence rule (Core)

If lineage shows a task's base and its intended integration target now
belong to materially different architecture lines, STOP normal
integration. Do not automatically cherry-pick, rebase, or resurrect the old
candidate. Perform architecture reconciliation first.

## 7. Superseded candidate rule (Core)

A technically correct, tested, independently reviewed commit may still
become obsolete if its architecture line is superseded. Retain it as
design evidence / implementation reference / test knowledge; do not
automatically integrate it into the new architecture.

## 8. Pre-push remote freshness for authoritative publication (Core)

A fresh pre-push `git ls-remote` of the target ref is **not** required
before every push. It **is** required specifically when: publication
targets an authoritative integration branch/ref (e.g. `refs/heads/main`),
**and** authorization depends on an expected target/base OID. In that
case, observe the target ref immediately before mutation/push; if the
observed OID differs from the authorized expected OID, `STOP_AND_OWNER` --
do not fetch, pull, rebase, or reconcile automatically. This complements,
and does not replace, mandatory post-push remote verification.

## 9. Global branch/worktree registry capability (Core -- requirement only, not yet built)

Voyage should maintain global awareness of active development topology,
not only the currently executing task. Required conceptual metadata per
branch/worktree: `branch`, `worktree`, `base_target`, `base_sha`,
`return_target`, `depends_on`, `integration_policy`, `lifecycle_status`,
`current_position`. This requirement is canonical as of this document.
Building and populating the actual registry, and generating a branch map
from it, is explicitly **out of scope here** and is the next bounded task,
`VOYAGE_BRANCH_WORKTREE_REGISTRY_V1`. Do not delete, prune, reset, or check
out other branches/worktrees to satisfy this section outside that task.

## 10. Governance update batching (Core)

Do not create a separate governance commit for every small wording or
metadata correction. Accumulate low-risk documentation deltas into
coherent update batches unless immediate correctness requires otherwise.
This document is itself one such batch.

---

## 11. NARRATIVE project-profile overlay

These apply the Core mechanisms above specifically to this project's
engineering workflow (services/tools/tests development). They are
project-specific thresholds/applications, not universal Voyage law, and
must not be hardcoded into generic Core.

**11.1 Development model.** GitHub-Flow-style task branches plus
trunk-based freshness discipline. Do not introduce a permanent
GitFlow-style `develop` / `release/*` / `hotfix/*` hierarchy unless a
future requirement explicitly justifies it.

**11.2 Task branch metadata.** Significant task branches should record:
`branch`, `worktree`, `base_branch`, `base_sha`, `return_target`,
`depends_on`, `integration_policy`, `status`.

**11.3 Generated branch map.** This project should be able to generate a
human-readable development topology (child branches marked
INTEGRATED / SUPERSEDED / ACTIVE, return target, base, lineage
CURRENT / STALE / DIVERGED), derived from Git/worktree facts plus registry
metadata -- never manually maintained as the sole authority. Not populated
by this document (§9).

**11.4 R2/R3 freshness requirement.** Before substantial R2/R3
implementation mutation, a lineage/freshness check (§5) against the
declared integration target is required. Reuse the evidence while target
SHA, task base, and dependency state are unchanged and no significant
development pause or parallel advancement occurred; re-check when those
facts change.

**11.5 Stacked branches only for real dependencies.** Use a stacked branch
only when an unfinished task B genuinely depends on an unfinished task A.
Not for organizational convenience.

**11.6 Lifecycle vocabulary.** `ACTIVE`, `READY_TO_REVIEW`,
`READY_TO_INTEGRATE`, `INTEGRATED`, `SUPERSEDED`, `ABANDONED`. Successful
integration makes the associated worktree a cleanup candidate -- no
destructive cleanup is implied automatically.

---

## 12. Case evidence

**Case 1 -- KIRA canonical-home cleanup.** One logically coherent cleanup
was fragmented across too many micro-slices (V1A…V1E). Lesson:
process-driven microslicing slowed delivery without meaningful safety
gain. → §1, §2.

**Case 2 -- KIRA visual-binding S1.** Commit
`46464d3a3ef759a7d0b73263129880683087a1c1` was technically correct, tested,
and independently reviewed, but belonged to an obsolete architectural
line -- the authoritative integration target had already replaced the
entire subsystem it was built against (`character_companion` /
`character_runtime` / `crp_authoring` → `character_visual_conditioning` /
`reference_library` / `character_canon_bridge`, etc.). The candidate could
not safely integrate and became design/reference evidence instead. Root
cause: the isolated worktree remained internally healthy, but nothing
tracked whether its integration target was still current. → §5, §6, §7,
§9.

---

## 13. Core vs. project-profile principle

The mechanism belongs to Voyage Core (§1–§10). Project-specific
thresholds/frequency belong to the project profile (§11).

Example: Core says *"task lineage can be checked against its declared
integration target"* (§5); this project's profile says *"R2/R3 substantial
mutation requires that check"* (§11.4). Do not hardcode "R2/R3" or "main"
into generic Core.
