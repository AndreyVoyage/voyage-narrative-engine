# VOYAGE_REVERSIBLE_FAST_LANE_V1

> Status: OWNER-RATIFIED
> Decision: OD-GOV-FAST-01
> Ratified: 2026-09-16
> Scope: Voyage development workflow governance
> Phase: PHASE 0

## Core principle

GREEN PATH MUST BE FAST.
RED PATH MUST BE SAFE.

Machine proves machine-decidable facts.
AI QA is semantic-triggered.
Owner decides intent, scope expansion and high-impact actions.

## Content classification

- **NORMATIVE NOW** — binding operational policy, effective from ratification.
- **DEFERRED** — recorded direction; NOT authorized for implementation.
- **FUTURE OPTIONAL AUTOMATION** — candidate tooling; requires a separate owner decision.

---

## 1. PURPOSE

Fast Lane reduces repeated owner stops without weakening fail-closed behavior.

Machine proves machine-decidable facts.
AI judges semantic uncertainty only where policy requires.
Owner retains human-only decisions.

## 2. ORDINARY FLOW

Canonical ordinary safe flow:

implementation
→ machine checks
→ focused / invariant tests
→ independent AI QA only when triggered
→ ONE conditional owner authorization
→ commit
→ verify candidate identity
→ FF-only integration
→ verify integration
→ normal non-force push
→ remote verification
→ CLOSED

Any mismatch: STOP.

Post-publication uncertainty: STOP_AND_OWNER.

## 3. OWNER-ONLY DECISIONS

Owner retains:

- intent/spec ratification
- scope expansion
- credentials/security decisions
- irreversible/destructive operations
- destructive migration
- production activation
- policy changes
- post-publication rollback
- recovery from uncertain publication
- ambiguous architectural trade-offs

Machine-verifiable facts do NOT require repeated owner approval.

## 4. RISK AND REVERSIBILITY

Risk (existing Voyage model):

- R0 — docs / trivial
- R1 — low
- R2 — medium
- R3 — high

Reversibility:

- REV-A — pure code / easily revertible
- REV-B — pointer / activation / feature flag
- REV-C — compatible schema/data transition
- REV-D — destructive / externally irreversible

Verification depth depends on: risk + reversibility + semantic trigger + test strength.

## 5. WORKTREE POLICY

- R0 docs-only: dedicated worktree OPTIONAL.
- R1 code: dedicated worktree default / RECOMMENDED.
- R2: dedicated worktree REQUIRED.
- R3: dedicated worktree REQUIRED.

Worktree isolation MUST NOT be removed merely to save commands.

## 6. MACHINE CHECKS

Machine-decidable examples (do NOT require repeated owner gates):

- exact branch / HEAD
- clean worktree / staged NONE
- exact authorized scope
- test result
- candidate identity
- FF integration result
- non-force push result
- remote ref identity

## 7. GIT CANDIDATE IDENTITY

Uncommitted candidate identity MUST NOT use `HEAD^{tree}` — HEAD describes only committed content.

Future machine identity uses:

temporary Git index → candidate_tree_oid.

Raw working-tree SHA256 is NOT authoritative commit identity when Git EOL normalization applies.

A readable changed-path manifest remains REQUIRED for scope/audit.

> DEFERRED: PHASE 0 MAY still use existing bounded evidence procedures. The future candidate identity helper is NOT implemented or authorized by this document.

## 8. EOL / WORKING TREE VS GIT BLOB

Working-tree bytes MAY legitimately differ from Git blob bytes.

Do NOT force committed Git blobs to match checkout/raw working-tree SHA when Git normalization applies.

Repository EOL policy changes require a separate bounded decision/slice.

## 9. PROMOTION POLICY

Normal promotion:

commit → verify → FF-only → verify → normal NON-FORCE push → post-push remote verification.

- No force.
- No force-with-lease in normal Fast Lane.
- No automatic post-publication rollback in V1.
- Before publication: failure normally means STOP, not rollback.
- After publication uncertainty: STOP_AND_OWNER.
- Pre-push ls-remote is NOT required as a correctness gate.
- Post-push remote verification IS required.

## 10. CHECKED-OUT TARGET BRANCH SAFETY

When a target branch is checked out in a worktree, perform FF inside its owning worktree through `git merge --ff-only`.

Do NOT use `git update-ref` against a branch checked out in another worktree.

## 11. TEST POLICY

Keep current clean test policy:

- PYTHONDONTWRITEBYTECODE=1
- and where applicable: -p no:cacheprovider

Use: focused explicit tests + known affected regression suites + fast invariant layer.

Do NOT adopt yet (DEFERRED):

- pytest-testmon
- pytest --lf / --ff workflow
- test-result cache
- complex dependency graph
- coverage-based selection

## 12. FULL REGRESSION POLICY

- If full regression is cheap: running every slice is acceptable.
- If expensive: run for R2, core changes, config changes, dependency changes, pre-release, Fast Lane failures, and periodic validation.

## 13. FAIL_TO_PASS

For defect fixes: a new regression test SHOULD fail on base and pass on candidate when practically possible.

For new functionality: base failure is NOT mandatory.

## 14. CORE INVARIANT DIRECTION

Two classes:

- GLOBAL_ALWAYS
- DOMAIN_ALWAYS_WHEN_IMPLEMENTED / AFFECTED_ONLY

GLOBAL / CROSS-CUTTING invariant families:

- deterministic content identity
- no silent fallback
- fail closed on invalid metadata
- no provider when forbidden
- no production path in tests

DOMAIN invariant families:

- package identity binding
- session pin immutability
- serialization roundtrip
- memory namespace isolation
- state namespace isolation
- invalid state-machine transitions rejected
- idempotence of safe operations

This document defines DIRECTION. It does NOT claim all invariant tests already exist.

## 15. FAST LANE PHASES

- PHASE 0 — process-only governance. No new reusable automation required.
- PHASE 0.25 — candidate identity helper (temporary index → candidate_tree_oid → candidate evidence). NOT YET AUTHORIZED FOR IMPLEMENTATION.
- PHASE 0.5 — read-only promotion verifier (GO / NO-GO / STOP_WITH_REASON). NOT YET AUTHORIZED FOR IMPLEMENTATION.
- PHASE 1 — only after 5–10 real measured slices and demonstrated ROI.

## 16. COMPLEXITY CEILING

Do NOT build: Kubernetes, Bazel, OPA, GitOps, merge queue, daemon, network service, dashboard.

Prefer stdlib Python for any future small helper.

Early Fast Lane MAY have: candidate helper + at most ONE additional reusable tool, without a new owner decision.

## 17. CIRCUIT BREAKER

One real Fast Lane process failure in an operation class:

→ suspend automated/fast handling for that class
→ owner review
→ explicit re-enable

Do NOT use fake statistical thresholds (e.g. "2 failures / 30 days" or "10 clean runs → automatic loosening").

## 18. METRICS

For the next 5–10 slices capture minimal metrics:

slice_id, risk, rev_class, semantic_trigger, changed_file_count,
implementation_minutes, test_minutes, qa_minutes, owner_gate_count, promotion_minutes,
test_reruns, qa_reruns, failure_type, rollback_used, fast_lane_outcome.

No dashboard.

## 19. RESEARCH STATUS

Fast Lane research phase is CLOSED.

Do NOT trigger new broad Fast Lane research unless a concrete unresolved technical contradiction appears.

Future optimization decisions SHOULD use project metrics.

## 20. S8B2 PILOT

S8B2_CHARACTER_DEFINITION_MEMORY_STATE_NAMESPACE_V1 is the intended first real Phase 0 Fast Lane pilot after this governance slice is fully integrated/published.

Because it affects persistence, memory namespace, state namespace, and state isolation, independent AI review remains REQUIRED.

The concrete reviewer/model/tool will be selected in the S8B2 slice brief.
