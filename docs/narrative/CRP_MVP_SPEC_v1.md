# CRP vNext — MVP SPECIFICATION (v1)

> **STATUS:** CANDIDATE_FOR_OWNER_RATIFICATION
> **IMPLEMENTATION:** NOT AUTHORIZED
> **Date:** 2026-08-16
> **Track:** CRP vNext MVP Specification
> **Companion document:** [`CRP_MVP_CONTRACTS_v1.md`](CRP_MVP_CONTRACTS_v1.md) — the conceptual schemas
> this spec builds on.
> **Baseline authority:** `CRP_VNEXT_ARCHITECTURE_RATIFICATION_v1.md` +
> `CRP_VNEXT_DECISION_REGISTER_v1.md` (CRP-OD-1…14, all `OWNER_RATIFIED`, integrated on `main` at
> `cedbf0a6f9bed13cc9e7dc464f12df1e93d9c865`).

This document is a **specification candidate**. It transforms the ratified CRP vNext architecture into a
concrete first MVP design. It does not, by itself, authorize any implementation, role-prompt writing,
KB rewrite, or Kira reconstruction execution. Where a ratified decision left a design parameter open
(decision register §F), this spec proposes a concrete, labeled **spec candidate** and explains why it does
not require a new owner decision — never by silently treating the choice as if it had already been
ratified.

---

## 1. Scope

CRP MVP proves that the pipeline can transform bounded source evidence into a
`CandidateCharacterPackage` (contracts doc §H) with:

- explicit provenance on every claim;
- explicit, non-numeric uncertainty (confidence axis, CRP-OD-8);
- preserved contradictions (CRP-OD-10);
- no unsupported facts (structurally rejected by the compiler);
- no automatic canon write (structurally forbidden, R8 check #10);
- independently auditable role outputs (R8);
- a stable, versioned boundary into CIS behavioral validation (contracts doc §J/K).

## 2. Non-goals (explicit)

- **Not** solving every future RKR capability — R3 (Intimacy Specialist) and R5 (Visual Observer) are
  **excluded from MVP execution** entirely (CRP-OD-11: `INACTIVE` in the registry for MVP).
- **Not** a Knowledge Router for arbitrary future roles — MVP uses direct `KnowledgeProfile` references,
  no shared router layer (D-RKR-14 stays open, unaffected — CRP MVP doesn't need one).
- **Not** a general role-selection mechanism (D-RKR-3 stays open) — MVP's execution graph is fixed by this
  spec, not dynamically selected.
- **Not** semantic/embeddings-based retrieval (matches D-RKR-6's own "modular first" recommendation and
  N7's embeddings-deferred precedent).
- **Not** canon-write tooling — CRP MVP stops at `HUMAN_APPROVED`; actual canon promotion is a separate,
  human-only process outside CRP's authority (CRP-OD-1/§20), not designed here.
- **Not** Kira reconstruction execution — §12 below is a **design**, explicitly not run by this task.
- **Not** a new orchestration framework — plain deterministic sequential/parallel execution is sufficient
  for five roles (matches architecture §25: "no new orchestration framework required").

## 3. MVP roles (ratified subset, CRP-OD-5 + CRP-OD-11)

| Role | Registry status | Execution type |
|---|---|---|
| R1 — Evidence Interviewer | `ACTIVE` | `LLM_ROLE` |
| R2 — Psychological Hypothesis Analyst | `ACTIVE` | `LLM_ROLE` |
| R4 — Voice Reconstruction Analyst | `ACTIVE` | `LLM_ROLE` |
| R6 — Deterministic Persona Compiler | `ACTIVE` | `DETERMINISTIC_FUNCTION` |
| R8 — Independent Evidence Auditor | `ACTIVE` | `LLM_ROLE` (with deterministic check scaffolding) |
| R3 — Optional Intimacy Profile Specialist | `INACTIVE` | out of MVP execution |
| R5 — Visual Observer | `INACTIVE` | out of MVP execution |
| R7 — Consistency Validator | not `ACTIVE` as a standalone role | `DETERMINISTIC_FUNCTION` (see §9 — runs as a library/function call, not an invoked LLM role) |

R7 is deliberately **not** modeled as a `RoleTask`/`RoleResult` cycle in MVP — CRP-OD-4 explicitly says it
is "not required to be an autonomous LLM role in MVP." MVP implements it as a deterministic validation
function invoked between R6's output and R8's input (see execution graph, §8).

## 4. Source Intake (deterministic, immutable)

Before R1 runs, a deterministic (non-LLM) intake process normalizes every raw source item into
`SourceEvidence` records (contracts doc §A) and freezes them into one `evidence_snapshot_id`. All roles in
one reconstruction run read exactly this snapshot — the reproducibility anchor. **Recommended: source
evidence is immutable after intake** (contracts doc §A invariant) — this is a spec candidate consistent
with CRP-OD-1's "immutable evidence snapshot" principle, not itself a separate owner decision.

## 5. Registry semantics (MVP candidate, CRP-OD-11 authority already ratified)

CRP-OD-11 fixed the *authority* semantics (no auto-discovery, no latest-wins, human-approved activation).
This spec proposes the MVP **candidate schema and physical layout** (contracts doc §F):

- **Spec candidate — physical format:** a single YAML registry file (matching the existing repo precedent
  `.voyage/roles.yaml` for dev-role registries), e.g. `roles/vnext/CRP_ROLE_REGISTRY_v1.yaml`. This is a
  file-format/path choice, not an architecture decision — explicitly not escalated to an owner gap
  (register §F item; task instruction: do not turn file paths into owner gaps).
- **Spec candidate — prompt location:** new vNext role contracts live under `roles/vnext/`, parallel to
  (not mixed with) the legacy `roles/ROLE_N_..._PROMPT.md` files, e.g.
  `roles/vnext/ROLE_1_EVIDENCE_INTERVIEWER_v1_PROMPT.md`. Resolves D-RKR-2's remaining implementation
  parameter as a spec default — implementation may deviate with a documented reason.
- **Spec candidate — rollback:** `DEPRECATED` entries are never deleted (contracts doc §F.1); "rollback" =
  a human-approved registry change re-activating a `DEPRECATED` version through the same
  `activation_gate` discipline as any other activation. No separate rollback command/tooling is required
  for MVP — activation and rollback are the same mechanism viewed from opposite directions. Resolves part
  of D-RKR-10's remaining parameter.
- **Spec candidate — hash chain:** each registry entry's `prompt_ref` target is content-hashed at
  activation time; the hash is stored alongside `activation_gate` so a later silent edit of the prompt
  file is detectable (R7 structural check). No full "hash chain" ledger beyond this single anchor point is
  required for MVP.

## 6. Knowledge routing (MVP candidate)

Per `KnowledgeProfile` (contracts doc §G):

- **Spec candidate — retrieval policy:** `EXACT_MODULAR_ONLY` for all five active roles in MVP. No
  semantic search.
- **Spec candidate — context budget:** a simple fixed per-role token/character ceiling (e.g., illustrative
  default: R1 gets the full snapshot up to a stated ceiling; R2/R4 get pre-filtered subsets per their
  `allowed_kb_refs`/`allowed_evidence_ids`). The exact numeric ceiling is left as an
  `IMPLEMENTATION_CHOICE_LATER` item (§13) — a specific number is an engineering tuning parameter, not an
  architecture decision.
- **Legacy KB:** per CRP-OD-14, **not** inherited by default. Each active role's `KnowledgeProfile` is
  authored fresh for CRP vNext; any legacy KB fragment reuse requires the compatibility+provenance review
  CRP-OD-14 mandates, recorded in `KnowledgeProfile.legacy_kb_reuse`.

## 7. PAC / Sandbox boundary (CRP-OD-12/13, applied exactly)

No adapter is built in this spec. Conceptually:

```
PAC memory      → explicit authorized export → SourceEvidence{source_type=PAC_EXPORTED}     → CRP
Sandbox/CES state → explicit owner-authorized immutable snapshot → SourceEvidence{source_type=SANDBOX_SNAPSHOT} → CRP
```

No CRP role ever performs a live PAC/Sandbox lookup. The only way either enters a reconstruction run is as
an already-materialized `SourceEvidence` record with the appropriate `source_type` (contracts doc §A.1),
carrying full provenance. The export/snapshot adapter's actual API is an `IMPLEMENTATION_CHOICE_LATER` /
`REQUIRES_RESEARCH` item (§13) — its *shape*, as it lands in CRP, is fully specified now.

## 8. Execution graph (MVP DAG)

```
                    SOURCE INTAKE (deterministic, immutable snapshot)
                                    │
                                    ▼
                    R1 — EVIDENCE INTERVIEWER (round 0)
                                    │  enriched/frozen snapshot + question-round budget
                        ┌───────────┴───────────┐
                        ▼                       ▼
                R2 — PSYCH HYPOTHESIS      R4 — VOICE RECONSTRUCTION
                     ANALYST                    ANALYST
                        └───────────┬───────────┘
                                    ▼
                    R6 — DETERMINISTIC PERSONA COMPILER
                                    ▼
                    CONSISTENCY VALIDATOR (R7 function, deterministic)
                                    ▼
                    R8 — INDEPENDENT EVIDENCE AUDITOR
                                    ▼
                        CandidateCharacterPackage (+ ReconstructionAudit)
                                    │
                         ┌──────────┴──────────┐
                         ▼                      ▼
                 human review          [optional, human-authorized]
                 (HUMAN_APPROVED /            CIS behavioral
                  REJECTED)                    validation
                                                    │
                                          discrepancy review
                                                    │
                                     bounded correction round (§9) — back to
                                     the specific role(s) implicated, then
                                     re-compile → re-validate → re-audit
```

**Parallel nodes:** R2 and R4 (both read-only over the same immutable snapshot + R1's clarifications; no
shared mutable state — matches architecture §17). R5 would be a third parallel branch if ever activated;
excluded for MVP. R3 would run after R2 (P3-coupled) if ever activated; excluded for MVP.

**Sequential dependency:** R1 → (R2 ‖ R4) → R6 → validator function → R8. R1 must complete (or explicitly
exhaust its stop rule, §10) before R2/R4 start, because R2/R4 may consume R1's clarifications.

## 9. Revision loop — exact MVP semantics (CRP-OD-6, clarified)

**"Maximum 2 correction rounds" means initial + two corrections — three pipeline executions maximum, not
two total executions.** This spec makes that explicit per the task's own instruction not to under-read the
owner's ratified budget:

| Round | Trigger | Scope |
|---|---|---|
| **Round 0** | Always | Full pipeline: R1 → (R2‖R4) → R6 → validator → R8 |
| **Round 1** | R8 verdict `FAIL` with a bounded `correction_requests` list, OR CIS `BehavioralValidationResult` discrepancies after a `HUMAN_APPROVED` package | Only the implicated role(s) re-run (targeted `RoleTask`s referencing `revision_round=1`), then R6 re-compiles, validator re-checks, R8 re-audits |
| **Round 2** | Round 1 still `FAIL`/unresolved discrepancies | Same pattern, `revision_round=2`, final bounded attempt |
| **After Round 2** | Still unresolved | `HUMAN_DECISION_REQUIRED` — run ends `INCONCLUSIVE` with the open defect list. No further autonomous round starts without an explicit new human decision (which would itself start a *new* run, not extend this one). |

R1 has its own, separate, smaller bounded loop (architecture §9): by default, **one question round per
return-loop entry** — this is not the same counter as the 2-round revision budget above; it bounds how
many times R1 alone may ask a follow-up round within a single revision round, not how many total revision
rounds exist.

**No autonomous infinite loops** — every loop entry requires the previous round's diff (R8's
`correction_requests` or CIS's `discrepancy_report`) as its bounded input; a round cannot start without a
concrete, evidence-linked reason.

## 10. R1 MVP contract — Evidence Interviewer

**Input:** evidence snapshot, current claim ledger, `ContradictionRecord`s, `unknowns` list from prior
rounds (empty on round 0).
**Output (`RoleResult`):** `QUESTION_PLAN` (claims, ranked: contradictions-to-clarify > identity-critical
gaps > material gaps), `SOURCE_GAPS`, new `SourceEvidence` from any authorized clarification answers,
`UNRESOLVED_GAPS`.

**R1 must NOT:**

- infer psychology (that is R2's domain — role-boundary violation, R8 check #5);
- create final character traits;
- resolve contradictions silently — R1 may only *propose* a clarifying question or flag
  `needs_interview=true` on a `ContradictionRecord`, never pick a side itself.

**Deterministic stop rule (spec candidate, resolving §37-#5's neighbor question for R1 specifically):**
R1 stops when **(a)** no identity-critical or material-severity gap remains unaddressed within its
question-round budget, **or (b)** remaining gaps are marked unanswerable from authorized
sources/input, **or (c)** the question-round budget (default: one round per return-loop entry) is
exhausted. Remaining gaps travel forward into the package as `UNKNOWN` — never silently filled.

## 11. R2 MVP contract — Psychological Hypothesis Analyst

Maps claims to CIS semantic layers **only where evidence justifies it** — never flattened:

| CIS layer | R2 may propose | Evidence bar |
|---|---|---|
| P0 (static core) | Stable dispositions | Highest bar — only from repeated/direct evidence |
| P1/P2 | Beliefs, fears/conflicts | `HYPOTHESIS`-typed, pending CIS |
| P3 | Relationship-specific states | Always per-counterpart, never globalized |
| P4 | Transient affect patterns | Labeled transient, never promoted to trait |
| P5 | Evolution hypotheses only | |

**Fields R2 may NEVER set directly:** any `claim.claim_type=FACT` without direct evidence backing (R6/R8
structurally reject this); any field in `voice_candidate` (R4's exclusive domain); anything in
`ContradictionRecord.resolution_status=RESOLVED_BY_EVIDENCE/OWNER_RESOLVED` (R2 may *propose* a
reconciliation hypothesis with both sides cited, never unilaterally close the record).

R2's output is `RoleClaim` evidence — never canon, never a runtime mutation. **Competing hypotheses are
encouraged**, not flattened into a single forced label (multiple `HYPOTHESIS` claims per question, each
with evidence + counterevidence).

## 12. R4 MVP contract — Voice Reconstruction Analyst

**Output** = a behaviorally testable speech model over a real corpus, dimensions drawn from (not all
required if evidence absent): lexicon, syntax, sentence length/rhythm, register, discourse habits, humor,
directness, hesitation, emotional speech shifts, taboo/avoidance patterns, address forms.

Every pattern carries a provenance label:

- `OBSERVED` — directly evidenced (with example `source_evidence_ids`);
- `INFERRED` — generalized from sparse corpus, marked lower certainty (`confidence=POSSIBLE` or lower);
- `GENERATED_RULE` — stylistic completion where the corpus is silent, must be flagged as constructed;
- `NEGATIVE_EXAMPLE` — anti-patterns (what the character does *not* say).

**Corpus floor (spec candidate for §37-#7's numeric gap):** MVP default = **15 real voice lines minimum**
per testable pattern category, matching the audit's own example figure (audit §12, "15–25"). Below this
floor for a given category, R4 emits `UNKNOWN_VOICE` for that category rather than a fabricated profile —
`UNKNOWN_VOICE` is a **valid, first-class** MVP output, not a failure. This number is explicitly a spec
default, adjustable by implementation without re-opening any owner decision (it does not touch any
CRP-OD).

## 13. R6 MVP contract — Deterministic Persona Compiler

**Not a creative LLM role.** Deterministic, `execution_type=DETERMINISTIC_FUNCTION`. Responsibilities:

- validate every incoming `RoleClaim` against the contracts doc §B invariants (reject unsupported/
  unmapped claims — an `INVALID` claim structurally cannot proceed);
- place claims into candidate modules by `target_module_or_layer`;
- preserve provenance (`provenance_manifest`, zero unmapped fields);
- preserve confidence (never averages, never upgrades);
- preserve contradictions (compiles both sides explicitly, never "corrects");
- assemble the `CandidateCharacterPackage` (contracts doc §H), `status=DRAFT`.

**R6 must never invent missing content.** A required field with only `INFERENCE`-level support is emitted
with its confidence tag intact, or as `UNKNOWN` — never silently upgraded to appear as `KNOWN`.

## 14. Consistency Validator (R7 function, CRP-OD-4)

Deterministic checks, machine-readable findings, run automatically between R6 and R8:

1. schema validity (against the persona schema this package targets);
2. duplicate claims (same assertion, same evidence, different `claim_id`);
3. unknown references (a `claim_id`/`source_evidence_id` cited but not resolvable);
4. provenance breaks (hash/lineage mismatch);
5. contradictory module placement (a claim placed in a module that conflicts with its own
   `claim_type`/layer tag — e.g. a P4-transient claim placed as a P0 stable module field);
6. forbidden direct canon state (any field that looks like it's writing toward a live canon path);
7. role-permission violations (a claim whose `role_id` producer lacked permission for its
   `target_module_or_layer`, per that role's `RoleRegistryEntry.permissions`);
8. unsupported field creation (a package field with no `provenance_manifest` entry);
9. missing required identity metadata (`subject_id`, `source_snapshot_id`, etc.);

Output feeds directly into `validation_results` (contracts doc §H) and gates whether the package may reach
`status=VALIDATED` before R8 runs.

## 15. R8 MVP contract — Independent Evidence Auditor

See contracts doc §I for the full `ReconstructionAudit` schema and the 10 mandatory checks. R8 is
independent — it reads the package + full evidence ledger, never the authoring sessions themselves.
Verdict enum: `PASS | FAIL | INCONCLUSIVE | BLOCKED` (matches the CIS judge-protocol pattern, per
architecture §16 — no different enum is required by any ratified or MVP source).

## 16. CandidateCharacterPackage (see contracts doc §H)

The MVP's central artifact. `HUMAN_APPROVED` status is explicitly **not** canon write — canon promotion
is a separate, deferred, human-only process outside this spec's scope (§2 non-goals).

## 17. CIS boundary (see contracts doc §J/K)

`CandidateCharacterPackage` → (only if `HUMAN_APPROVED`) → `BehavioralValidationRequest` → CIS → 
`BehavioralValidationResult` → discrepancy review → (only via a bounded revision round, §9) → new package
version. CIS internals are never referenced directly by CRP contracts — only the opaque
`probe_profile_ref` and versioned `adapter_version`.

## 18. Kira MVP benchmark — design only, NOT executed

Per CRP-OD-7, exactly:

- **AUTHORING INPUT (proposed categories, not file-selected):** raw scenario text fragments, speech lines,
  description fragments that simulate "heterogeneous owner material" — analogous to what a real
  reconstruction subject would provide, drawn only from material that does not itself require reading
  `personas/kira/**`.
- **HIDDEN EVALUATION REFERENCES:** existing `personas/kira/**` canon modules + CIS frozen probes/judge
  protocol. Never exposed to authoring roles.
- **Candidate output:** `Kira'` — lives entirely in a staging namespace, never overwrites existing Kira
  canon.
- **Leakage prevention:** every active role's `KnowledgeProfile.forbidden_refs` includes `personas/kira/**`
  by default during this benchmark; R8 check #9 (source leakage) audits zero canon-module hashes appear in
  `provenance_manifest`.
- **Comparison:** `Kira'` → CIS adapter → same probe families as canon Kira → blind evaluation, primary
  human judge, LLM judge optional/auxiliary/never-overriding (reuses the existing CIS judge-protocol
  pattern as-is, per architecture §21).

**This task does NOT select actual source files** — per instruction, since the exact authoring-input
corpus is not yet clearly authorized. That selection is future work, gated on its own authorization.
Numeric success thresholds are likewise **not set here** (§37-#18 remaining parameter, §13 below) —
proposing hard pass/fail numbers before any pilot run risks anchoring on an arbitrary bar; this is left as
`REQUIRES_RESEARCH`, informed by the first actual run's results.

---

## 19. Implementation parameter mapping

**Correction, stated plainly:** the decision register's §F, as currently on `main`, lists **20**
implementation parameters, not 17. Tracing the discrepancy: the first ratification session's report said
16; the owner-gap-closeout session added 5 new items and removed 1 (D-RKR-9, resolved to `CLOSED`) — net
16 − 1 + 5 = 20 — but that session's own summary line said "17," an arithmetic slip in that report, not a
change to the actual register content. This spec uses the authoritative register content (20 items,
verified by direct line count against `docs/narrative/CRP_VNEXT_DECISION_REGISTER_v1.md §F` on `main`) and
loses none of them.

| # | ID / description | Spec decision | Rationale | Blocks MVP spec? | Blocks MVP implementation? |
|---|---|---|---|---|---|
| 1 | R2 "sufficient evidence" threshold (§37-#5) | `SPEC_CAN_DECIDE_NOW` — see §11: no numeric threshold; qualitative rule is "a `FACT`-type claim requires ≥1 direct-class `source_type`; below that, claim_type must be `HYPOTHESIS`/`INFERENCE`, never `FACT`" | Follows directly from the already-ratified `RoleClaim` invariant (contracts §B); no new architecture judgment needed | NO | NO — resolved by this spec |
| 2 | R4 corpus floor + recognizability rubric (§37-#7) | `SPEC_CAN_DECIDE_NOW` for the floor (15 lines, §12); recognizability rubric = `REQUIRES_RESEARCH` (needs an actual PB-REC-style probe design, CIS-side) | Floor is a simple engineering default; rubric design depends on CIS probe mechanics outside this spec's authority | NO | Partially — floor resolved, rubric needed before R4 output can be behaviorally validated |
| 3 | R5 split decision (§37-#8) | `CAN_DEFER` — R5 excluded from MVP execution entirely (§2) | Not relevant until R5 is ever activated | NO | NO (N/A for MVP) |
| 4 | R6/R7/R8 module boundary (§37-#9) | `SPEC_CAN_DECIDE_NOW` — see §13–15: R6 compiles, validator function checks structure, R8 audits independently; boundary is the execution graph itself (§8) | Directly derivable from already-ratified role definitions | NO | NO — resolved by this spec |
| 5 | Canon-write mechanism/tooling (§37-#10) | `CAN_DEFER` — explicitly out of CRP MVP scope (§2, §16) | CRP MVP never performs this action; designing it is a separate future track | NO | NO (N/A — CRP MVP stops at `HUMAN_APPROVED`) |
| 6 | KB allowlist paths + context-budget numbers per role (§37-#13) | Paths: `SPEC_CAN_DECIDE_NOW` (fresh `KnowledgeProfile` per role, §6); numeric budget: `IMPLEMENTATION_CHOICE_LATER` | Paths follow from least-privilege principle; exact token ceiling is a tuning parameter | NO | Partially — exact numbers needed before implementation, not before spec |
| 7 | Cross-character leakage impl+test (§37-#14) | `IMPLEMENTATION_CHOICE_LATER` — design given (§6, §18 leakage prevention); test fixtures are implementation work | Design is spec-level; automated test coverage is engineering work | NO | YES |
| 8 | R8 fixed probe set + stale invalidation (§37-#16) | Stale-invalidation: `SPEC_CAN_DECIDE_NOW` (contracts §I — `package_hash` mismatch invalidates); fixed probe set: `REQUIRES_RESEARCH` (depends on CIS probe design, not CRP's authority) | Invalidation rule is a CRP-side contract choice; probe design belongs to CIS | NO | Partially |
| 9 | Kira benchmark success thresholds (§37-#18) | `REQUIRES_RESEARCH` — explicitly not set (§18) | Setting numeric bars before any pilot run risks arbitrary anchoring | NO | NO (only blocks benchmark *execution*, not MVP pipeline implementation) |
| 10 | `canon_state` enum (§D.2/§D.4) | `CAN_DEFER` | Out of CRP MVP scope — package `status` (contracts §H.1) already covers CRP's own lifecycle needs without it | NO | NO |
| 11 | Role-prompt location policy (D-RKR-2) | `SPEC_CAN_DECIDE_NOW` — `roles/vnext/` (§5) | File-path choice; explicitly not an owner gap per task instruction | NO | NO |
| 12 | Role/task selection mechanism (D-RKR-3) | `CAN_DEFER` — MVP uses its own fixed graph (§2, §8), no general selector needed | General cross-project question, not CRP-MVP-blocking | NO | NO |
| 13 | Search-order ratification (D-RKR-6) | `SPEC_CAN_DECIDE_NOW` — `EXACT_MODULAR_ONLY` (§6, contracts §G) | Matches D-RKR-6's own recommendation; no semantic search needed for 5 roles | NO | NO |
| 14 | Knowledge Router placement (D-RKR-14) | `CAN_DEFER` — MVP doesn't need a shared router (§2) | General cross-project question | NO | NO |
| 15 | General Knowledge Router provenance mechanism (D-RKR-15) | `CAN_DEFER` — CRP's own provenance need is met by `RoleResult.provenance_summary` (contracts §E) | CRP-specific need already satisfied; general mechanism is a separate future track | NO | NO |
| 16 | **(NEW)** Registry file format/schema/loader/cache/paths/hash anchor (D-CRP-11, §37-#12) | `SPEC_CAN_DECIDE_NOW` for format/paths/hash-anchor (§5); loader/cache implementation = `IMPLEMENTATION_CHOICE_LATER` | Format is a convention choice (YAML, matching repo precedent); loader code is engineering | NO | YES (loader/cache code) |
| 17 | **(NEW)** Rollback mechanism/tooling (D-CRP-11, D-RKR-10) | `SPEC_CAN_DECIDE_NOW` — reactivation-through-approval-gate design (§5) | No separate mechanism needed beyond the registry's own activation discipline | NO | NO |
| 18 | **(NEW)** PAC export/snapshot adapter — API, schema, auth carrier (D-CRP-12, D-RKR-11) | Shape: `SPEC_CAN_DECIDE_NOW` (`source_type=PAC_EXPORTED`, contracts §A.1); adapter code: `REQUIRES_RESEARCH` (depends on PAC's actual internals, not yet examined by this spec) | Contract-level shape doesn't require touching PAC internals; adapter implementation does | NO | YES |
| 19 | **(NEW)** Sandbox/CES snapshot adapter — API, schema, auth carrier, trigger mechanism (D-CRP-13, D-RKR-12) | Shape: `SPEC_CAN_DECIDE_NOW` (`source_type=SANDBOX_SNAPSHOT`); adapter code: `REQUIRES_RESEARCH` | Same reasoning as #18, for Sandbox/CES | NO | YES |
| 20 | **(NEW)** Legacy-KB migration inventory/compatibility-classification tooling (D-CRP-14) | `CAN_DEFER` | Non-destructive cleanup work (§20 below), not required for CRP MVP's own fresh knowledge profiles to function | NO | NO |

**Summary:** `SPEC_CAN_DECIDE_NOW`: 10 (items 1, 4, 6-paths, 8-invalidation, 11, 13, 16-format, 17, 18-shape,
19-shape — counting each split item once by its decided half). `IMPLEMENTATION_CHOICE_LATER`: 3 (items
6-numbers, 7, 16-loader). `REQUIRES_RESEARCH`: 4 (items 2-rubric, 8-probes, 9, 18/19-adapter-code, treated
as one research thread each). `CAN_DEFER`: 7 (items 3, 5, 10, 12, 14, 15, 20). None are lost; none require
a new owner decision.

## 20. Source-cleanup classification (4/4)

| # | Item (decision register §G) | Classification |
|---|---|---|
| 1 | 37 legacy `knowledge_base/` files not wired to any role prompt — non-destructive cleanup authorized | `CAN_DEFER` — not required for CRP MVP (fresh knowledge profiles don't touch legacy KB by default, CRP-OD-14); may proceed independently, any time, non-destructively |
| 2 | Stale cross-role version references (R1→R2 v1.2, etc.) | `LEGACY_ONLY` — concerns the legacy R1–R8 pipeline's own internal references, unrelated to CRP vNext's fresh contracts |
| 3 | `schemas/persona_schema_v3_2_VOYAGE.json` filename/title mismatch | `LEGACY_ONLY` — cosmetic, outside CRP MVP's scope entirely |
| 4 | `docs/06_KNOWLEDGE_BASE_GUIDE.md` layout mismatch | `LEGACY_ONLY` — describes the legacy KB layout, not CRP vNext's fresh knowledge profiles |

None are classified `BEFORE_MVP` — none block drafting or implementing the CRP MVP as specified here.

## 21. Owner gaps introduced by this spec

**None.** Every design choice in §5–§20 above was resolvable either directly from an already-ratified
CRP-OD, or as a file-path/format/numeric-tuning choice explicitly excluded from owner-gap status by task
instruction, or deferred/flagged as requiring engineering research rather than architecture judgment.

```
=== CRP MVP SPEC v1 — NEW OWNER GAP COUNTDOWN ===
(none)
NEW OWNER GAPS: 0
```

## 22. Failure / stop states (fail-closed)

| Condition | Behavior |
|---|---|
| Invalid source (fails intake normalization) | Rejected at intake; never enters the snapshot |
| Missing provenance on a claim | `RoleClaim` structurally `INVALID`; R6 refuses to compile it in |
| Malformed role output | `RoleResult.completion_status=BLOCKED`; orchestrator halts that role's contribution, does not guess |
| Unsupported claim | Rejected by R6 (contracts §B); never reaches the package |
| Contract version mismatch | `BLOCKED` for the orchestrator — no silent coercion |
| Contradiction unresolved at package assembly | Compiled explicitly as `OPEN`/`UNRESOLVED` — never silently dropped |
| Compiler (R6) rejection | Package stays `DRAFT`, correction round targets the rejected claims' source role |
| Validator (R7 function) failure | Package cannot reach `VALIDATED`; R8 does not run on an unvalidated package |
| R8 verdict `FAIL` | Bounded correction round (§9), max 2 |
| R8 verdict `BLOCKED` | Terminal for this package version — human intervention required, no autonomous round |
| Revision budget exhausted (2 rounds used, still failing) | `HUMAN_DECISION_REQUIRED`; run ends `INCONCLUSIVE` |

No condition above is silently continued past — every one produces an explicit, evidence-linked state.

## 23. File/storage model (specification only, no binding)

Conceptual separation, no implementation:

- **Immutable source snapshot** — its own namespace, content-hashed, never mixed with role outputs.
- **Role task/result artifacts** — per-run, per-role-invocation records, referencing the snapshot by id
  only.
- **Candidate packages** — versioned, lineage-linked, separate from both of the above.
- **Audit results** — one per audited package version, immutable once written.
- **Behavioral validation results** — CIS-side artifacts, referenced by id from the CRP side, never
  duplicated into CRP's own storage.

**Explicit prohibitions (unchanged from architecture §25, restated for MVP):** do not bind to SQLite; do
not create a second CIS memory storage; do not reuse LangGraph checkpoints as character data (orchestration
state is run metadata only, never persona/memory content).

## 24. MVP implementation acceptance criteria

Future implementation must prove, **offline, before any real Kira reconstruction is authorized:**

- [ ] immutable source snapshot mechanism works and is content-hash-verifiable;
- [ ] every promoted claim in a test package carries full provenance (`provenance_manifest` resolves for
      100% of fields);
- [ ] an unsupported claim is structurally rejected by R6, not merely flagged;
- [ ] a seeded contradiction survives compilation, validation, and audit without being silently dropped;
- [ ] role permissions are enforced — a role attempting to read outside its `allowed_evidence_ids`/
      `allowed_kb_refs` is blocked, not merely logged;
- [ ] R1, R2, R4 contracts validated against this spec (input/output shape, stop rules) with test
      fixtures;
- [ ] R6 cannot invent claims — a fixture test proves it refuses to fill an evidence gap;
- [ ] the deterministic consistency validator catches at least one seeded structural violation per check
      category (§14);
- [ ] R8 runs independently of the authoring session and produces one of the four defined verdicts on a
      test package;
- [ ] the revision loop enforces exactly 2 correction rounds maximum, then reaches
      `HUMAN_DECISION_REQUIRED` — verified with a fixture designed to never pass;
- [ ] PAC/Sandbox direct access is denied by construction — a test role attempting a live lookup fails
      closed;
- [ ] legacy KB is not auto-inherited — a fresh `KnowledgeProfile` with zero `allowed_kb_refs` pointing at
      legacy paths is the default, verified by fixture;
- [ ] a full test run produces a `CandidateCharacterPackage` reaching `AUDITED` status;
- [ ] no code path in the implementation writes toward `personas/`, `scenarios/`, or `core/` — verified by
      static check and/or R8's own check #10 firing correctly on a seeded attempt;
- [ ] the CIS adapter boundary (`BehavioralValidationRequest`/`Result`) is stable against at least one
      mock/stub CIS response, proving CRP does not need to know CIS internals to function.

---

## 25. Precedence and status (restated)

This spec candidate does not supersede any CRP-OD. If a future implementation effort finds an actual
contradiction between this spec and a ratified CRP-OD, the CRP-OD wins and this document must be revised
— it does not silently override ratified decisions. No such contradiction was found while drafting this
spec.

```
implementation authorized:  NO
role prompt writing:        NOT AUTHORIZED
KB rewrite:                 NOT AUTHORIZED
canon/persona mutation:     NOT AUTHORIZED
Kira reconstruction:        NOT EXECUTED, NOT AUTHORIZED
```

*End of spec. See `CRP_MVP_CONTRACTS_v1.md` for the field-level schemas referenced throughout.*
