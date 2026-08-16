# CRP vNext — DECISION REGISTER (v1)

> **Status:** ACTIVE DECISION REGISTER — IMPLEMENTATION NOT AUTHORIZED
> **Date:** 2026-08-16
> **Companion document:** [`CRP_VNEXT_ARCHITECTURE_RATIFICATION_v1.md`](CRP_VNEXT_ARCHITECTURE_RATIFICATION_v1.md)
> **ID namespace:** owner decisions in this track use `CRP-OD-1…10`, aliased to the owner's original
> shorthand `OD-1…OD-10`. This is distinct from the pre-existing `D-RKR-1…15` register
> (`AI_ROLES_AND_KNOWLEDGE_ROUTING_CONCEPT_v1.md §7`) and from the historical `§37` list
> (`RKR_R1_R8_ROLE_INTELLIGENCE_READONLY_AUDIT_2026-08-03.md §37`). No renumbering of either historical
> register has been performed.

---

## A. CRP-OD-1 … CRP-OD-10 — full entries

Each entry: ID · owner shorthand · status · date · decision · rationale/implication · historical
mappings · supersedes · does-not-authorize.

### CRP-OD-1 (OD-1) — vNext / Variant C direction

- **Status:** OWNER_RATIFIED · **Date:** 2026-08-16
- **Decision:** Controlled reconstruction is evidence-first, claim-level provenance, bounded AI roles as
  tools, immutable evidence snapshot, LLM analytical roles propose, mechanical invariants
  deterministic-first, independent R8 audit, human controls canon, no automatic canon writes. Legacy
  R1–R8 pipeline is reference/evidence only, not the vNext execution contract.
- **Rationale/implication:** Formalizes the base direction that the 2026-08-16 architecture synthesis
  adopted from audit §35/§10 (proposal-grade) pending exactly this ratification. Establishes "CRP vNext /
  Variant C" as a repository-authoritative name from this date (see ratification doc §1) — it was not one
  before.
- **Historical mappings:** §37-#1 (partial, via R4 authority split into OD-2), §37-#2 (closes: module-first
  vs monolith-first), §37-#4 (closes: R1 literary expansion non-canon), §37-#9 (partial, via OD-4),
  §37-#10 (closes: human approval/canon-write authority, cross-cutting). D-RKR-1 (partial — execution
  subset only, see OD-5), D-RKR-4 (partial, CRP-specific pipeline graph), D-RKR-9 (partial, principle
  only), D-RKR-13 (partial, CRP/Kira-specific), D-RKR-15 (partial, CRP-specific provenance requirement).
- **Supersedes:** the "no Variant C found" open question in the 2026-08-16 architecture doc §4.1.
- **Does NOT authorize:** any code, role prompt rewrite, router, compiler, or canon mutation.

### CRP-OD-2 (OD-2) — R4 authority

- **Status:** OWNER_RATIFIED · **Date:** 2026-08-16
- **Decision:** Legacy historical baseline = R4 v1.3. R4 v2.0 = `UNRATIFIED_REFERENCE`. Neither legacy
  v1.3 nor v2.0 automatically becomes the vNext contract. The vNext role/function **Voice Reconstruction
  Analyst** must receive its own future contract.
- **Rationale/implication:** Resolves the "R4 v1.3 vs v2.0" conflict identified in both RKR documents
  (`RKR_CHARACTER_RECONSTRUCTION_PIPELINE_VNEXT_ARCHITECTURE_2026-08-16.md §2.2.1`,
  audit §6.1/§17) — but only for authority/baseline purposes, not by writing a new R4 prompt. `AGENTS.md`'s
  role table (which still lists v1.3 without a deprecated marker) is now consistent with this ratified
  baseline; it is not, itself, amended by this document.
- **Historical mappings:** §37-#1 (closes the authority-baseline question only).
- **Supersedes:** the de-facto (unratified) treatment of v2.0 as current in `docs/CHECKPOINT_v2.0_APPLY_2026-06-29.md` / `docs/ANTI_TEMPLATE_PATCH_v1.0.md` for CRP vNext purposes specifically — those files are not rewritten and remain accurate for whatever legacy track they describe.
- **Does NOT authorize:** writing the new Voice Reconstruction Analyst contract, or amending `AGENTS.md`'s role table.

### CRP-OD-3 (OD-3) — R5 authority

- **Status:** OWNER_RATIFIED · **Date:** 2026-08-16
- **Decision:** vNext name = **VISUAL OBSERVER**. Permitted: observable appearance, clothing/style,
  posture, observable expression in a specific image, visual presentation cues, reference provenance.
  Forbidden: personality/morality/intelligence/psychological-diagnosis/sexuality-intimacy inference from
  appearance. Legacy term "Physiognomist" is not the vNext role name.
- **Rationale/implication:** Adopts the architecture doc's §13 recommendation for the naming half of the
  question; the optional split into a second role (`NONVERBAL_EXPRESSION_DIRECTOR`) proposed in the same
  section, and independently in the audit §33, is **not** ratified here — see §C, D-RKR/§37 mapping for
  §37-#8.
- **Historical mappings:** §37-#8 (partial — naming/boundary closes; split into two roles remains open).
- **Supersedes:** "Physiognomist" as a vNext role name. Does not rename the legacy prompt file.
- **Does NOT authorize:** renaming/moving `roles/ROLE_5_PERSONA_PHYSIOGNOMIST_v1.3_PROMPT.md`, or deciding
  the Visual Observer / Nonverbal Expression Director split.

### CRP-OD-4 (OD-4) — R7 authority

- **Status:** OWNER_RATIFIED · **Date:** 2026-08-16
- **Decision:** vNext responsibility = **CONSISTENCY VALIDATOR**, deterministic-first: schema consistency,
  terminology normalization, duplicate detection, provenance completeness, cross-module consistency,
  unsupported-claim detection, semantic/structural consistency checks where deterministically possible. R7
  must not invent or creatively "improve" persona content. R7 is not required to be an autonomous LLM role
  in MVP.
- **Rationale/implication:** Resolves the naming/status half of the architecture doc's OD-4 question
  (§15); whether R7 ships as a standalone role or folds entirely into the deterministic compiler/R8 is
  left as an implementation choice, consistent with "not required to be an autonomous LLM role in MVP."
- **Historical mappings:** §37-#9 (partial — deterministic-first status closes; exact fold-in-or-standalone mechanics remain open).
- **Supersedes:** legacy R7 "monolith→modules migration" as a *standing vNext pipeline stage* (it remains available as a migration tool for old artifacts only).
- **Does NOT authorize:** implementing the validator, or deciding its exact module boundary vs R6/R8.

### CRP-OD-5 (OD-5) — MVP role subset

- **Status:** OWNER_RATIFIED · **Date:** 2026-08-16
- **Decision:** CRP vNext MVP execution subset = **R1 + R2 + R4 + R6 + R8** (Evidence Interviewer,
  Psychological Hypothesis Analyst, Voice Reconstruction Analyst, Deterministic Persona Compiler,
  Independent Evidence Auditor). R3 = optional gated specialist. R5 = optional Visual Observer. R7 =
  deterministic support/validation stage. All 8 roles are not required for MVP.
- **Rationale/implication:** This decides the **execution** subset for a first controlled pilot. It does
  **not** decide **registry membership** — i.e. whether a future Role Registry (D-RKR-1) lists only these
  five roles or all eight (with R3/R5/R7 registered-but-conditional). Those are different questions; see
  §C mapping for D-RKR-1.
- **Historical mappings:** §37-#1 (n/a), directly matches the architecture doc's own §24/§27 OD-5.
- **Supersedes:** nothing (no prior ratified MVP subset existed).
- **Does NOT authorize:** implementing any of the five roles, or closing D-RKR-1's registry-membership question.

### CRP-OD-6 (OD-6) — revision budget

- **Status:** OWNER_RATIFIED · **Date:** 2026-08-16
- **Decision:** Maximum autonomous/bounded correction rounds = **2**. After two unsuccessful correction
  rounds: `HUMAN_DECISION_REQUIRED`. No infinite role loops, no autonomous endless reconstruction.
- **Rationale/implication:** Matches architecture doc §18's "MVP policy recommendation" verbatim, now
  ratified rather than merely recommended. R1's own question-round budget (§9: one round per return-loop
  entry by default) is a related but separate parameter, not itself re-ratified by this decision.
- **Historical mappings:** none of §37's 18 items name a revision-budget number explicitly; this closes a
  gap the historical register never quantified.
- **Supersedes:** nothing.
- **Does NOT authorize:** implementing the loop/budget-enforcement mechanism.

### CRP-OD-7 (OD-7) — Kira reconstruction benchmark

- **Status:** OWNER_RATIFIED · **Date:** 2026-08-16
- **Decision:** Strict split: **AUTHORING INPUT** vs **HIDDEN EVALUATION REFERENCES**. Roles must not
  receive full existing Kira canon merely to reproduce it. Output = candidate `Kira'`. Existing Kira canon
  is read-only / must not be overwritten. Behavioral validation: candidate `Kira'` → CIS → hidden
  evaluation.
- **Rationale/implication:** Chooses **Kira** as the first pilot fixture, which supersedes the audit §36
  recommendation of "a new small evidence-rich fictional fixture, not Nika [or any existing persona]" —
  that recommendation is superseded specifically on *which* character to use as pilot; its other
  content (seeded-defect methodology, success criteria shape) is not superseded and remains useful
  reference. Exact numeric success thresholds are not set by this decision (see §F).
- **Historical mappings:** §37-#18 (partial — fixture choice and split-authority close; success thresholds remain open).
- **Supersedes:** audit §36's fixture recommendation, on the fixture-choice point only.
- **Does NOT authorize:** running the benchmark, or defining the exact success-threshold numbers.

### CRP-OD-8 (OD-8) — confidence / uncertainty

- **Status:** OWNER_RATIFIED · **Date:** 2026-08-16
- **Decision:** Confidence vocabulary = **KNOWN / PROBABLE / POSSIBLE / UNKNOWN / CONTRADICTORY**. No
  fake numeric precision, no mechanical averaging. For composite conclusions, confidence cannot exceed the
  weakest *necessary* evidentiary link. Contradictory evidence must remain visible.
- **Rationale/implication:** Matches architecture doc §7 ("known / probable / possible / unknown /
  contradictory" + weakest-link propagation) verbatim, now ratified. **Important, per explicit owner
  correction during this ratification pass (2026-08-16):** this is ratified as a **prospective, standalone
  confidence axis** for CRP vNext. It is **not** a reconciliation against a pre-existing "§37.3 claim
  taxonomy" — no such taxonomy (three axes `source_type`/`claim_status`/`canon_state`, or a `claim_status`
  enum `VERIFIED/INFERRED/HYPOTHESIS/EXAMPLE/UNKNOWN/CONFLICTED`) was found anywhere in the accessible
  repository or handoff sources. Full detail in §D below.
- **Historical mappings:** §37-#3 (partial — confidence axis + source-class list close the architecture
  requirement; exact schema/serialization remains an implementation parameter, not a reconciliation
  against prior fact).
- **Supersedes:** nothing (no prior ratified confidence vocabulary existed).
- **Does NOT authorize:** any specific JSON/schema serialization of this vocabulary; does not redefine
  `claim_status` values used anywhere else in the codebase (none were found to redefine).

### CRP-OD-9 (OD-9) — R3

- **Status:** OWNER_RATIFIED · **Date:** 2026-08-16
- **Decision:** R3 is optional and explicitly gated. Requires: relevant use case; authorization/opt-in
  where required; sufficient direct evidence. Allowed outcomes: `SKIPPED_NOT_AUTHORIZED`,
  `SKIPPED_NOT_NEEDED`, `INSUFFICIENT_EVIDENCE`. Forbidden: inference from appearance; forced
  completeness; inference solely from attachment labels; model priors promoted as character facts.
- **Rationale/implication:** Matches architecture doc §11 and audit §16/§32 R3 gate design; now ratified
  rather than proposal-grade.
- **Historical mappings:** §37-#6 (closes: R3 opt-in/skip/forbidden inferences).
- **Supersedes:** legacy R3 prompt's mandatory-completeness behavior, for CRP vNext specifically (legacy prompt file itself is not edited).
- **Does NOT authorize:** implementing the gate/skip-contract logic.

### CRP-OD-10 (OD-10) — contradiction priority

- **Status:** OWNER_RATIFIED · **Date:** 2026-08-16
- **Decision:** `OWNER_DIRECT` outranks `MODEL_INFERENCE` for **promotion authority**. Higher-priority
  evidence does not delete conflicting evidence. If evidence materially conflicts: preserve contradiction,
  record both claims, do not silently average or "correct," require deterministic/human resolution
  according to scope. Canonical principle: **UNRESOLVED CONTRADICTION > SILENT CORRECTION.**
- **Rationale/implication:** Matches architecture doc §8 contradiction-register resolution priority
  (owner evidence > direct observation > testimony > inference, loser preserved) and audit §37-#11 verbatim
  in spirit; now ratified.
- **Historical mappings:** §37-#11 (closes: conflict priority / unresolved-over-silent-correction).
- **Supersedes:** legacy R6 behavior of "correcting" R3 against R2 on conflict (audit §19/§37-#2 area) — for CRP vNext specifically.
- **Does NOT authorize:** implementing the contradiction register or its resolution logic.

---

## B. §37 historical decision map (18/18)

Source: `RKR_R1_R8_ROLE_INTELLIGENCE_READONLY_AUDIT_2026-08-03.md`, §37 "Required Owner Decisions"
(verbatim numbered list, re-verified 2026-08-16: still exactly 18 items, no renumbering in source).

| §37_ID | ORIGINAL_DECISION (verbatim/faithful) | CURRENT_SOURCE_STATUS | MAPPED_OD | MAPPED_D-RKR | RATIFICATION_STATUS | RATIONALE | REMAINING_PARAMETER | NEXT_ACTION |
|---|---|---|---|---|---|---|---|---|
| 1 | Canonical R4 v1.3/v2.0/deprecation policy | Unresolved in audit; addressed at architecture level 2026-08-16 | OD-2 | D-RKR-2 (adjacent, not closed) | PARTIALLY_CLOSED_BY_OD | OD-2 sets baseline authority (v1.3) and reference status (v2.0), but does not deprecate v2.0 or write a new R4 contract | New R4 vNext contract; whether v2.0 content is salvaged into it | Draft Voice Reconstruction Analyst contract in future MVP spec |
| 2 | Deauthorize monolith-first R6, or change module-first decision | Module-first already the narrative-wide decision (`NARRATIVE_DECISIONS_v1.md §2`); R6 vNext restates it | OD-1 | — | CLOSED_BY_OD | OD-1 adopts architecture §14 (R6 = module-first, monolith derived) as ratified direction | none at direction level; compiler schema is implementation | Implementation parameter only |
| 3 | Claim taxonomy/source classes | Was only ever a one-line stub — no detailed taxonomy exists in any accessible source (verified 2026-08-16) | OD-8 | — | CLOSED_BY_OD (architecture level only) | OD-8 ratifies confidence axis; source classes taken from audit §12 evidence-flow text, not from a separate formal taxonomy doc | Exact schema/serialization/enum naming | See §D/§F below |
| 4 | R1 literary expansion as non-canon | Addressed at architecture level (§9) | OD-1, OD-5 | — | CLOSED_BY_OD | Architecture §9: legacy portrait becomes optional non-canon presentation artifact, never pipeline input; R1 confirmed in MVP | none at direction level | Implementation parameter only |
| 5 | R2 evidence threshold / allowed labels | Addressed directionally (§10); no numeric threshold set | OD-1, OD-8 | — | PARTIALLY_CLOSED_BY_OD | Claim-type taxonomy (HYPOTHESIS/INFERENCE/etc.) and confidence vocabulary ratified; exact "sufficient evidence" threshold for R2 not quantified | Numeric/qualitative threshold defining `SKIPPED_INSUFFICIENT_EVIDENCE` for R2 | MVP spec must define threshold |
| 6 | R3 opt-in/skip/forbidden inferences | Addressed directly | OD-9 | — | CLOSED_BY_OD | OD-9 is a direct, complete answer | none | Implementation parameter only |
| 7 | R4 corpus threshold / recognizability rubric | Direction set (§12); numeric floor only given as an example ("audit pilot used 15–25"), not ratified | OD-2, OD-5 | — | PARTIALLY_CLOSED_BY_OD | R4 included in MVP, `UNKNOWN_VOICE` contract concept adopted via OD-1; exact corpus floor number and recognizability rubric not ratified | Exact corpus floor; PB-REC-style recognizability rubric | MVP spec must define |
| 8 | Rename/split R5 and boundaries | Naming closed; split (Visual Observer + Nonverbal Expression Director) not decided | OD-3 | — | PARTIALLY_CLOSED_BY_OD | OD-3 ratifies name + hard no-inference boundary; does not decide whether to split into two roles | Whether to split into two roles/functions | Defer to MVP spec or later decision |
| 9 | R6/R7 deterministic status | Addressed directly | OD-1, OD-4, OD-5 | — | CLOSED_BY_OD | R6 = deterministic compiler (mandatory, MVP); R7 = deterministic-first consistency validator, not required standalone in MVP | Exact module boundary between R6/R7/R8 | Implementation parameter only |
| 10 | Human approval points / canon-write authority | Cross-cutting principle already independently ratified (RKR concept §3, CIS gates, N9 §8); restated by OD-1 | OD-1 | — | CLOSED_BY_OD | No automatic canon writes; human-only canon action, separate commit boundary | Exact canon-write mechanism/tooling | Implementation parameter only |
| 11 | Conflict priority: owner evidence > interpretation; unresolved over silent correction | Addressed directly | OD-10 | — | CLOSED_BY_OD | OD-10 is a direct, complete answer | none at policy level | Implementation of contradiction register |
| 12 | Role registry authority/version/hash/rollback | Not addressed by OD-1–10 (OD-5 only sets execution subset, not registry mechanics) | OD-5 (partial) | D-RKR-1, D-RKR-2, D-RKR-9, D-RKR-10 | STILL_OPEN_OWNER_DECISION | Execution subset ≠ registry membership/versioning/hash/rollback; see §C | Registry schema, versioning scheme, hash chain, rollback mechanism | Owner decision required before Role Registry implementation |
| 13 | KB profiles/forbidden sources/context budgets | Direction set (least privilege, bounded tools — OD-1); no concrete profile/budget values | OD-1 (partial) | D-RKR-5, D-RKR-6, D-RKR-7 | PARTIALLY_CLOSED_BY_OD | Architecture §19 gives a proposal-grade per-role KB table for CRP roles specifically, adopted as base direction, but exact paths/budgets not owner-ratified as fixed values | Exact KB paths per role; context budget numbers; modular-vs-semantic search order | MVP spec must finalize |
| 14 | Cross-character access policy | Direction set (immutable snapshot, bounded tools — OD-1; Kira leakage control — OD-7); no implementation/test | OD-1, OD-7 (partial) | D-RKR-13 | PARTIALLY_CLOSED_BY_OD | Policy direction (default-deny, per-character scope, default-deny `personas/kira/**` during benchmark) closed for CRP; general cross-project mechanism and any test/enforcement not built | Implementation + test of default-deny enforcement | Implementation parameter |
| 15 | PAC/Sandbox default-deny/provenance | Not addressed by OD-1–10 at all | none | D-RKR-11, D-RKR-12 | STILL_OPEN_OWNER_DECISION | Architecture §19 *recommends* PAC/Sandbox default-deny as proposal-grade text, but no OD ratifies it; `AI_ROLES_AND_KNOWLEDGE_ROUTING_CONCEPT_v1.md` guardrail #4 still explicitly requires "a separate decision (§7 D-RKR-11/12)" | Owner decision on PAC memory / Sandbox state read access for CRP roles | Owner decision required |
| 16 | R8 critical gates/fixed probes/stale invalidation | R8 role + 10-check minimum set ratified via inclusion in MVP; the fixed-probe/stale-invalidation mechanics are proposal-grade only | OD-1, OD-5 (partial) | — | PARTIALLY_CLOSED_BY_OD | R8 = Independent Evidence Auditor, mandatory in MVP, with the 10-check list from architecture §16 adopted as base direction; exact fixed-probe set and stale-hash invalidation rule not separately ratified | Fixed probe set; stale-audit invalidation rule; verdict-enum finalization | MVP spec / R8 contract |
| 17 | Legacy KB/guides cleanup authority | Not addressed by OD-1–10 | none | — | SOURCE_CLEANUP_ONLY | No OD grants or denies cleanup authority over the 37 legacy KB files or stale guides identified in the audit | Who is authorized to retire/rewrite legacy KB/guide files | Separate cleanup-authorization decision, out of CRP vNext scope |
| 18 | Pilot fixture/success thresholds/owner | Fixture choice + split authority closed (Kira, OD-7); numeric success thresholds not set | OD-7 | — | PARTIALLY_CLOSED_BY_OD | OD-7 chooses Kira and the authoring/hidden split; audit §36's generic success criteria (100% canon claims source+approval, 0 leakage, etc.) are reference, not re-ratified as Kira-specific numeric thresholds | Exact Kira-benchmark pass/fail thresholds | MVP spec / benchmark design |

**Count check:** 18/18 items mapped. `CLOSED_BY_OD`: 6 (#2, #4, #6, #9, #10, #11).
`PARTIALLY_CLOSED_BY_OD`: 8 (#1, #5, #7, #8, #13, #14, #16, #18). `STILL_OPEN_OWNER_DECISION`: 2 (#12, #15).
`SOURCE_CLEANUP_ONLY`: 1 (#17). `CLOSED_BY_OD` (architecture-level only, taxonomy caveat — tallied
separately, see note below): 1 (#3). Total: 6 + 8 + 2 + 1 + 1 = 18.

*Note on the count line above: item #3 is tallied separately from the other six `CLOSED_BY_OD` items
(#2, #4, #6, #9, #10, #11) because its closure is explicitly architecture-level-only per the taxonomy
correction in §D — flagging this so a future reader does not read it as full closure of "claim
taxonomy" in the detailed-schema sense the original §37 phrasing could suggest.*

---

## C. D-RKR historical decision map (15/15)

Source: `docs/narrative/AI_ROLES_AND_KNOWLEDGE_ROUTING_CONCEPT_v1.md §7` (verbatim, all still
`OWNER_DECISION_PENDING` as of last check prior to this ratification).

| D-RKR_ID | ORIGINAL_QUESTION (verbatim, translated) | MAPPED_§37 | MAPPED_OD | STATUS_AFTER_RATIFICATION | WHAT_IS_DECIDED | WHAT_REMAINS | BLOCKS_MVP_SPEC | BLOCKS_IMPLEMENTATION |
|---|---|---|---|---|---|---|---|---|
| D-RKR-1 | Which roles enter the first registry? | #12 | OD-5 (partial) | PARTIALLY_CLOSED | MVP **execution** subset = R1,R2,R4,R6,R8 | Whether the **registry** additionally lists R3,R5,R7 as registered-but-conditional/support entries | NO | YES (registry schema needs this) |
| D-RKR-2 | Where does the canonical role prompt live (`roles/` vs elsewhere)? | #1 (adjacent) | none | OPEN | — | Canonical prompt location policy for vNext roles (new contracts per OD-2/OD-3/OD-4) | NO | YES |
| D-RKR-3 | Who selects the role for a task: human / router / hybrid? | — | none | OPEN | — | Selection mechanism; CRP's own pipeline graph (architecture §17) is a fixed sequence, which sidesteps but does not answer the general question | NO | YES (for router, not for CRP's own fixed graph) |
| D-RKR-4 | Can one task invoke multiple roles sequentially? | — | OD-1 (partial, CRP-specific) | PARTIALLY_CLOSED | For CRP vNext specifically: yes — the ratified pipeline graph is parallel (R2‖R4‖R5) then sequential (→R6→R7→R8) | As a general cross-project question, still open | NO | NO (CRP-specific answer suffices for CRP) |
| D-RKR-5 | Knowledge profile per role (allowed directories/modules)? | #13 | OD-1 (partial) | PARTIALLY_CLOSED | Principle: bounded, least-privilege, default-deny (OD-1); architecture §19 gives a proposal-grade per-role table for CRP roles | Exact ratified paths/allowlist per role | YES | YES |
| D-RKR-6 | Semantic search or exact-modular-first? | #13 | none | OPEN | — | D-RKR-6's own text already recommends "modular first," but this is a recommendation, not an owner ratification | NO | YES |
| D-RKR-7 | How is context size bounded? | #13 | none | OPEN | — | Concrete budget mechanism/numbers | NO | YES |
| D-RKR-8 | How is role quality measured? | — | none | OPEN | — | Role-quality evaluation methodology (distinct from R8's package/evidence audit) | NO | NO (not MVP-blocking; R8 audits the package, not "role quality") |
| D-RKR-9 | How is a new role version approved? (recommended: proposal → human) | #12 | OD-1 (principle only) | PARTIALLY_CLOSED | Cross-cutting human-approval principle ratified (OD-1: human controls canon, no auto-writes) | Exact role-version-approval workflow | NO | YES |
| D-RKR-10 | How is rollback performed? | #12 | none | OPEN | — | Rollback mechanism | NO | YES |
| D-RKR-11 | Can a role read PAC session memory? (recommended: no by default) | #15 | none | OPEN | — | Owner ratification of the recommended default-deny posture | NO | YES |
| D-RKR-12 | Can a role read Sandbox state? (recommended: no by default) | #15 | none | OPEN | — | Owner ratification of the recommended default-deny posture | NO | YES |
| D-RKR-13 | How is cross-character knowledge leakage prevented? | #14 | OD-1, OD-7 (partial, CRP/Kira-specific) | PARTIALLY_CLOSED | Policy direction for CRP: immutable per-run evidence snapshot, default-deny `personas/kira/**` during Kira benchmark, R8 leakage check | General cross-project mechanism; implementation/test of the CRP-specific policy | NO | YES |
| D-RKR-14 | Where does the future Knowledge Router live? (recommended: thin layer over Gateway) | — | none | OPEN | — | Owner ratification of the recommended placement | NO | YES |
| D-RKR-15 | How is provenance of used context preserved? | #3 (adjacent) | OD-1 (partial, CRP-specific) | PARTIALLY_CLOSED | CRP-specific provenance requirement ratified conceptually (OD-1; architecture §26 `RoleTask`/`RoleResult` contracts carry `provenance_log_ref`) | General cross-project Knowledge Router provenance mechanism | NO | YES |

**Count check:** 15/15 items mapped. `CLOSED`: 0. `PARTIALLY_CLOSED`: 6 (D-RKR-1, D-RKR-4, D-RKR-5, D-RKR-9, D-RKR-13, D-RKR-15). `OPEN`: 9 (D-RKR-2, D-RKR-3, D-RKR-6, D-RKR-7, D-RKR-8, D-RKR-10, D-RKR-11, D-RKR-12, D-RKR-14). `SUPERSEDED`: 0. `DEFERRED`: 0. `IMPLEMENTATION_PARAMETER`: 0 (folded into PARTIALLY_CLOSED remainders above).

No D-RKR item is marked `CLOSED` merely because an OD is topically related — each `PARTIALLY_CLOSED` row
states exactly what is decided and exactly what remains, per the no-hand-waving requirement.

---

## D. Claim taxonomy reconciliation

### D.1 What was expected vs. what was found

The original reconciliation brief for this ratification pass expected an existing, detailed "§37.3 / CIS"
taxonomy: three axes (`source_type`, `claim_status`, `canon_state`), with `claim_status` values
`VERIFIED / INFERRED / HYPOTHESIS / EXAMPLE / UNKNOWN / CONFLICTED`, plus a CIS spec organized into
layers "A. Authoring / B. Runtime / C. Memory / D. Evolution / E. Canon Promo."

**Source verification result (2026-08-16): PRE-EXISTING §37.3 DETAILED TAXONOMY — NOT FOUND / NOT
DEFINED.**

Checked and confirmed absent from: `NARRATIVE_DECISIONS_v1.md`, `00_DOCUMENT_INDEX.md`,
`AI_ROLES_AND_KNOWLEDGE_ROUTING_CONCEPT_v1.md`, both RKR handoff documents, the CIS pilot codebase
(`tools/cis_pilot/*`, `tests/cis_pilot/*`), `STATUS.md`, `AGENTS.md`, `PAC_CHARACTER_EVOLUTION_KNOWLEDGE_CAPTURE_v1.md`,
and a repository-wide search for the literal strings `claim_status`, `§37.3`, and the individual enum
values. The historical §37 item #3 ("Claim taxonomy/source classes") is a one-line decision stub with no
attached definition — it names a requirement, not a schema. `canon_state` appears exactly once in the
whole tree, as an unrelated JSON field name in runtime scene state
(`AI_ROLES_AND_KNOWLEDGE_ROUTING_CONCEPT_v1.md`'s sibling doc `NARRATIVE_FUTURE_TRACKS_v1.md`), not as a
claim-provenance axis. No CIS spec document organized into "A. Authoring…E. Canon Promo" layers exists;
the CIS code's actual psychology layers are `P0…P5` (see architecture doc §10), an unrelated axis.

Per explicit owner instruction during this ratification pass: **this taxonomy is not treated as an
existing repository fact.** The terms `VERIFIED/INFERRED/HYPOTHESIS/EXAMPLE/CONFLICTED`, where they
appear only in the original task brief and not in an authoritative source, are recorded as
**`UNSUPPORTED_AS_PREEXISTING_REPO_TAXONOMY`** and are not ratified as historical fact.

### D.2 What is ratified instead (prospective, not reconciled against prior fact)

Two independent axes, ratified from OD-8 and from source classes actually evidenced in the RKR audit
(§12, evidence/provenance flow — `OWNER_DIRECT`, `MODEL_INFERENCE`, `MODEL_EXAMPLE`):

| AXIS | PURPOSE | ALLOWED_VALUES | WHO_SETS_IT | MUTABILITY | EXAMPLE | NOT_TO_BE_CONFUSED_WITH |
|---|---|---|---|---|---|---|
| `source_type` (provenance) | Records where a claim originated | `OWNER_DIRECT`, `MODEL_INFERENCE`, `MODEL_EXAMPLE`, plus other source classes as actually evidenced by future sources (not exhaustively enumerated here) | The producing role, at claim creation | Immutable once set (corrections are new records with supersedes-links, per architecture §5) | A claim tagged `OWNER_DIRECT` because the owner stated it verbatim in an interview | Confidence (a claim can be `OWNER_DIRECT` and still `CONTRADICTORY`) |
| `confidence` (OD-8) | Records epistemic strength of a claim | `KNOWN`, `PROBABLE`, `POSSIBLE`, `UNKNOWN`, `CONTRADICTORY` | The producing/reviewing role, re-evaluated as evidence changes | Mutable as new evidence arrives; composite confidence = weakest necessary link | A `MODEL_INFERENCE` claim corroborated by three independent sources may be `PROBABLE`, not automatically `POSSIBLE` | Source/provenance (see above); canon state (a `KNOWN` claim is not automatically canon) |
| `canon_state` | Whether a claim/field has been human-approved into canon | **NOT RATIFIED HERE.** Deferred — see §F | Human, via separate canon action (OD-1/§20) | N/A until defined | — | Confidence and provenance (independent axes; see ratification doc §5) |

`source_type` and `confidence` **must not** be collapsed into one axis. `OWNER_DIRECT ≠ KNOWN` by
definition; `MODEL_INFERENCE ≠ POSSIBLE` by definition.

### D.3 Legacy-to-vNext term mapping

| OLD_TERM | CANONICAL_AXIS | CANONICAL_VALUE | STATUS |
|---|---|---|---|
| `KNOWN` | confidence | `KNOWN` | EXACT (from OD-8) |
| `PROBABLE` | confidence | `PROBABLE` | EXACT (from OD-8) |
| `POSSIBLE` | confidence | `POSSIBLE` | EXACT (from OD-8) |
| `UNKNOWN` | confidence | `UNKNOWN` | EXACT (from OD-8) |
| `CONTRADICTORY` | confidence | `CONTRADICTORY` | EXACT (from OD-8) |
| `VERIFIED` | — | — | INVALID — not found in any authoritative source; not adopted |
| `INFERRED` | — | — | INVALID as a `claim_status` value — closest ratified concept is `source_type=MODEL_INFERENCE` (a different axis, not a status) |
| `HYPOTHESIS` | — | — | INVALID as a taxonomy-axis value here — `HYPOTHESIS` is a `claim_type` value in the architecture doc's RoleClaim schema (§6), a third, separate, **not-ratified-by-this-document** concept; not adopted into this taxonomy |
| `EXAMPLE` | source_type (partial analogue) | `MODEL_EXAMPLE` | APPROXIMATE — `EXAMPLE` alone was never defined; `MODEL_EXAMPLE` is the actually-evidenced source class it most resembles |
| `CONFLICTED` | — | — | INVALID as a taxonomy-axis value here — `CONTRADICTORY` (confidence) and the separate `ContradictionRecord` mechanism (architecture doc §8) cover this space; `CONFLICTED` itself is not adopted |
| `OWNER_DIRECT` | source_type | `OWNER_DIRECT` | EXACT (from audit §12) |
| `MODEL_INFERENCE` | source_type | `MODEL_INFERENCE` | EXACT (from audit §12) |
| `MODEL_EXAMPLE` | source_type | `MODEL_EXAMPLE` | EXACT (from audit §12) |

### D.4 Independence guarantees

- **`source_type` is independent:** YES — set once at claim creation, never overwritten by a confidence
  or canon-state change.
- **`canon_state` is independent:** YES (by principle, per OD-1/§20 human-only canon action) — though no
  enum is ratified yet, the *independence* of the future axis from the other two is ratified now, so that
  whoever defines the enum later cannot fold it back into confidence or provenance.
- **`UNKNOWN` collision:** resolved — `UNKNOWN` exists only on the `confidence` axis in this ratified
  model; it does not also appear as a `source_type` or (future) `canon_state` value.
- **`CONTRADICTORY`/`CONFLICTED` collision:** resolved — only `CONTRADICTORY` (confidence) is ratified;
  `CONFLICTED` is not adopted, avoiding the duplicate-meaning risk the original brief flagged.

### D.5 Owner-gap determination for this section

Per the taxonomy owner-gap rule: this reconciliation does **not** change the semantic content of OD-8 or
of any existing CIS invariant — it only clarifies that no prior detailed taxonomy existed to reconcile
against, and ratifies OD-8 plus the audit's existing source classes as a standalone two-axis model, with
canon_state explicitly deferred rather than invented.

**`OWNER_DECISION_REQUIRED: NO`** for the two-axis model itself (source_type, confidence) — this was
already resolved by the owner during this ratification pass (see instruction quoted in §D.1). Definition
of the `canon_state` enum remains a genuine future parameter (§F), not a blocker to this ratification.

---

## E. Unresolved items (owner gaps)

=== CRP vNEXT RATIFICATION OWNER GAP COUNTDOWN ===

- [G1] Role Registry authority: version/hash/rollback mechanics, and whether registry membership extends
  beyond the MVP execution subset to include R3/R5/R7 as registered-but-conditional. (§37-#12, D-RKR-1/2/9/10)
- [G2] PAC session memory read access for CRP roles — default-deny is recommended but not owner-ratified.
  (§37-#15, D-RKR-11)
- [G3] Sandbox state read access for CRP roles — default-deny is recommended but not owner-ratified.
  (§37-#15, D-RKR-12)
- [G4] Legacy KB/guides cleanup authority — no owner decision grants or denies who may retire/rewrite the
  37 legacy knowledge-base files or stale guides identified in the 2026-08-03 audit. (§37-#17)

**REMAINING OWNER GAPS: 4**

None of these four gaps blocks the truthfulness of this ratification — each is recorded honestly as
`STILL_OPEN_OWNER_DECISION` or `SOURCE_CLEANUP_ONLY` in §B/§C above, not silently closed. They **do**
block specific future work (Role Registry implementation for G1; any role touching PAC/Sandbox state for
G2/G3; any legacy-KB rewrite for G4), but they do not block ratifying OD-1–OD-10 or drafting a future MVP
specification that simply defers them.

---

## F. Implementation parameters (not owner gaps — engineering/spec work)

- Exact R2 "sufficient evidence" threshold defining `SKIPPED_INSUFFICIENT_EVIDENCE` (§37-#5).
- Exact R4 corpus floor number and PB-REC-style recognizability rubric (§37-#7).
- Whether R5 splits into Visual Observer + Nonverbal Expression Director, or stays unified (§37-#8).
- Exact module boundary between R6 (compiler) / R7 (validator) / R8 (auditor) (§37-#9).
- Exact canon-write mechanism/tooling that enforces "human-only, separate commit boundary" (§37-#10).
- Exact KB allowlist paths and context-budget numbers per role (§37-#13, D-RKR-5/6/7).
- Implementation and test of the default-deny cross-character/leakage policy (§37-#14, D-RKR-13).
- Fixed probe set and stale-audit invalidation rule for R8 (§37-#16).
- Exact numeric/qualitative Kira-benchmark success thresholds (§37-#18).
- `canon_state` enum definition (§D.2/§D.4) — deferred, not invented here.
- Canonical role-prompt location policy for new vNext contracts (D-RKR-2).
- Role/task selection mechanism beyond CRP's own fixed pipeline graph (D-RKR-3).
- Modular-vs-semantic search order ratification (D-RKR-6) — currently only a recommendation.
- Role-version-approval workflow specifics (D-RKR-9) — human-approval principle is ratified, workflow is not.
- Rollback mechanism (D-RKR-10).
- Knowledge Router placement ratification (D-RKR-14) — currently only a recommendation.
- General (non-CRP-specific) Knowledge Router context-provenance mechanism (D-RKR-15).

## G. Source-cleanup backlog

- 37 legacy `knowledge_base/` files not wired to any role prompt (audit §8–9) — cleanup/retirement
  authority not decided (§37-#17, gap G4).
- Stale cross-role version references (R1→R2 v1.2, R2→R3 v2.1, R3→R4 v1.1, R4→R5 v1.1, R5→R6 v2.0) —
  cosmetic, not corrected by this ratification.
- `schemas/persona_schema_v3_2_VOYAGE.json` filename/title mismatch (v3_2 vs "v3.1") — cosmetic, not
  corrected by this ratification.
- `docs/06_KNOWLEDGE_BASE_GUIDE.md` describes an author-based KB layout diverging from the actual
  role-based layout — not corrected by this ratification.

---

*End of decision register. See ratification document for the formal status summary, precedence rule, and
implementation-authorization boundary.*
