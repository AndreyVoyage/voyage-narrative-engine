# CRP MVP — CONCEPTUAL CONTRACTS (v1)

> **STATUS:** OWNER_RATIFIED_SPECIFICATION_CONTRACTS
> **RATIFICATION_DATE:** 2026-08-16
> **IMPLEMENTATION:** NOT AUTHORIZED
> **Date drafted:** 2026-08-16
> **Track:** CRP vNext MVP Specification
> **Companion document:** [`CRP_MVP_SPEC_v1.md`](CRP_MVP_SPEC_v1.md) — ratified alongside this document as
> `OWNER_RATIFIED_SPECIFICATION`.
> **Authority:** derives from `CRP_VNEXT_ARCHITECTURE_RATIFICATION_v1.md` and
> `CRP_VNEXT_DECISION_REGISTER_v1.md` (CRP-OD-1…14, all `OWNER_RATIFIED`, on `main` as of `cedbf0a…`).
> This document does not reopen any ratified decision. Where it fills a gap left open by design
> (§37/D-RKR "implementation parameter" items), the resolution is now ratified specification content,
> confirmed by independent review (`CRP_MVP_SPEC_V1_OWNER_RATIFICATION_REVIEW_2026-08-16.md`) to contain
> zero true owner-level decisions — not a new fact silently substituted for owner judgment.

These are **conceptual schemas** — field lists and invariants, not executable JSON Schema. No project
convention currently mandates JSON Schema for narrative decision documents (`docs/narrative/*` uses
prose + Markdown tables throughout, e.g. `PAC_TRAINING_DATASET_SCHEMA_v1.md`), so this document follows
that convention. Executable schema, and any implementation field beyond what is needed to record this
ratification, remain deferred to a separately-authorized implementation effort — ratifying these contracts
as specification content does not convert them into executable schema.

---

## A. SourceEvidence

**Purpose.** The atomic, immutable record of one piece of raw evidence about a subject character.
Nothing enters the reconstruction pipeline except as a `SourceEvidence` record or a `RoleClaim` derived
from one. Never mixed with role-derived inference (see §B).

**Required fields:**

| Field | Type | Notes |
|---|---|---|
| `source_id` | string | Stable unique id — content hash of raw reference + intake sequence number |
| `subject_id` | string | The character this evidence concerns |
| `source_type` | enum | See §A.1 below |
| `content_ref` | string | Reference to the raw payload (stored once, content-hashed; never duplicated inline) |
| `provenance` | string | Origin reference (file/chat/export/PAC export/Sandbox snapshot), capture context |
| `intake_timestamp` | datetime | When intake happened (always known) |
| `content_hash` | string | Hash of the raw payload, for immutability verification |
| `evidence_snapshot_id` | string | Which immutable snapshot this record belongs to (§ "Source Intake") |

**Optional fields:**

| Field | Type | Notes |
|---|---|---|
| `speaker_or_author` | string | Who said/wrote it, if relevant and known |
| `source_timestamp` | datetime | When the content was originally produced, if known (distinct from `intake_timestamp`) |
| `confidence` | enum | Intake-level confidence in the **source itself** (not in any downstream claim) — same 5-level vocabulary as §"Confidence axis" below, used here only to flag e.g. a garbled/uncertain transcript |
| `restrictions` | string[] | Privacy/use restrictions, if applicable (feeds Knowledge Profile deny-list) |
| `metadata` | object | Free-form, non-authoritative annotations |

**Invariants:**

- Immutable after intake. **Recommended: YES** (matches architecture doc §5 and the general immutable-
  evidence-snapshot principle in OD-1). Corrections are new `SourceEvidence` records with an explicit
  `supersedes_source_id` link (added to `metadata`), never in-place edits.
- `source_id` never reused, even across corrections.
- Raw payload stored once; every consumer receives a reference, never a duplicated copy (least-privilege
  routing needs single-copy content to enforce allowlists).

**Producer:** the deterministic Source Intake process (not an LLM role).
**Consumer:** R1 (full snapshot), R2/R4 (filtered subset per Knowledge Profile), R6 (via claim references
only, not raw evidence), R8 (full evidence ledger for independent audit).
**Forbidden:** any role treating `SourceEvidence` as directly editable; any role fabricating a
`SourceEvidence` record to back an otherwise-unsupported claim.
**Versioning:** immutable individual records; the snapshot they belong to is versioned as a whole (see
`evidence_snapshot_id`).

### A.1 `source_type` — MVP vocabulary

Per CRP-OD-8's ratified guidance (register §D: `source_type` is the provenance axis, distinct from
confidence) and the RKR architecture doc §5 (`source_type` field), the MVP vocabulary combines the two
kinds of source classes actually evidenced in ratified sources — plus classes required by ratified
access policy (OD-12/OD-13):

| Value | Meaning | Ratified basis |
|---|---|---|
| `OWNER_DIRECT` | Owner stated this directly (interview answer, explicit correction, direct fact) | Audit §12, CRP-OD-10 |
| `DIRECT_QUOTE` | Verbatim quoted text from a source document/transcript | Architecture §5 `source_type` enum (`speech_sample`) |
| `OBSERVATION` | Directly observed behavior/appearance/visual detail in a specific source | Architecture §5 (`visual_observation`) |
| `SELF_REPORT` | Subject describing themselves, in-character or as reported | Architecture §5 (`interview`, `conversation`) |
| `THIRD_PARTY_REPORT` | Someone else describing the subject | Architecture §5 (`relationship_evidence`) |
| `SCENARIO_EVIDENCE` | Extracted from existing scenario/canon text | Architecture §5 (`scenario_evidence`) |
| `MODEL_INFERENCE` | An AI role's inference/generalization, not a direct source | Audit §12, CRP-OD-10 |
| `MODEL_EXAMPLE` | An AI-generated example/completion, explicitly not observed | Audit §12 |
| `PAC_EXPORTED` | Arrived via the explicit PAC-memory export path (CRP-OD-12) | CRP-OD-12 — this is the *only* legitimate way PAC-derived content enters CRP |
| `SANDBOX_SNAPSHOT` | Arrived via the explicit Sandbox/CES immutable-snapshot export path (CRP-OD-13) | CRP-OD-13 — the *only* legitimate way Sandbox-derived content enters CRP |
| `OTHER` | Explicitly-justified source class not covered above, with `metadata.other_source_type_reason` required | Architecture §5 allows an open `other` value |

This is a **spec candidate vocabulary**, not a closed enum ratified by any OD — new values may be added by
future spec revision if a source type is needed that doesn't fit. `source_type` is **never** used to
express confidence (see independence rule, decision register §D.4): `PAC_EXPORTED` and `SANDBOX_SNAPSHOT`
say nothing about how certain the content is — a snapshot-exported claim still gets its own `confidence`
value independently.

---

## B. RoleClaim

**Purpose.** The atomic unit of role-derived inference/assertion, always traceable to evidence.

**Required fields:**

| Field | Type | Notes |
|---|---|---|
| `claim_id` | string | Stable unique id |
| `subject_id` | string | Character this claim concerns |
| `role_id` | string | Producing role (`R1`…`R8`) |
| `claim` | string / structured value | The assertion itself |
| `claim_type` | enum | `FACT \| OBSERVATION \| SELF_REPORT \| THIRD_PARTY_REPORT \| BEHAVIORAL_EVIDENCE \| HYPOTHESIS \| INFERENCE \| CONTRADICTION \| UNKNOWN` (architecture doc §6, unchanged) |
| `source_evidence_ids` | string[] | **Mandatory, non-empty** for any claim not `claim_type=UNKNOWN` |
| `source_type_summary` | enum(s) | Provenance inherited/aggregated from `source_evidence_ids` (see §A.1) |
| `confidence` | enum | See "Confidence axis" below — **mandatory** |
| `rationale_summary` | string | Concise, auditable, 1–3 sentences — **never** hidden chain-of-thought |
| `status` | enum | `PROPOSED \| SUPPORTED \| CONTESTED \| INSUFFICIENT_EVIDENCE \| REJECTED_BY_AUDIT \| OWNER_RESOLVED` (architecture doc §6, unchanged) |
| `target_module_or_layer` | string | Where this claim is destined in the candidate package (e.g. `psychology.P2`, `voice.lexicon`) |

**Optional fields:**

| Field | Type | Notes |
|---|---|---|
| `counterevidence_ids` | string[] | `evidence_ids`/`claim_ids` that oppose this claim |
| `contradiction_ids` | string[] | Links to `ContradictionRecord`s this claim participates in |
| `revision_round` | integer | Which correction round produced/last-touched this claim (0 = initial) |

**Invariants:**

- A claim with `claim_type=FACT` **requires** direct evidence (`source_type` drawn from `OWNER_DIRECT`,
  `DIRECT_QUOTE`, `OBSERVATION`, `SELF_REPORT`, `THIRD_PARTY_REPORT`, `SCENARIO_EVIDENCE` — never solely
  `MODEL_INFERENCE`/`MODEL_EXAMPLE`). An **unsupported claim is INVALID** and must be rejected by R6
  (compiler) before it can enter the package.
- `rationale_summary` must never contain or reference hidden reasoning traces — it is the auditable
  "why," not a transcript of the role's internal process.
- Every `claim_id` referenced anywhere in the eventual `CandidateCharacterPackage` must resolve to a real
  `RoleClaim` with a non-empty `source_evidence_ids` chain (except `UNKNOWN`-type claims, which document
  an evidence *gap*, not an assertion).

**Producer:** R1 (evidence/gap claims), R2 (psychology hypotheses), R4 (voice patterns). R6 does **not**
produce `RoleClaim`s — it only consumes and compiles them (see §H).
**Consumer:** R6 (compiler), R7 (consistency checks), R8 (audit).
**Forbidden:** any role editing another role's `RoleClaim` in place; a claim silently changing
`source_evidence_ids` after creation (corrections are new claims with `metadata.supersedes_claim_id`).
**Versioning:** claims are immutable once created within a run; a correction round produces new claims,
never edits to old ones — old claims remain in the ledger for audit lineage.

### B.1 Confidence axis (CRP-OD-8, ratified)

`KNOWN | PROBABLE | POSSIBLE | UNKNOWN | CONTRADICTORY` — no numeric percentages, no mechanical
averaging.

- **Who may assign it:** the producing role at claim creation; may be revised by the same role or by R7/R8
  flagging misuse (see R8 check "confidence misuse"), never silently by R6.
- **When it may change:** only across a new revision round, when new evidence or a new claim justifies
  re-evaluation — never retroactively rewritten on the same claim record (a confidence change means a new
  claim version, per the immutability invariant above).
- **Weakest-necessary-evidence rule:** a composite conclusion (e.g. a package field drawing on multiple
  claims) inherits the **lowest** confidence among its *necessary* supporting claims — not an average, not
  the highest, not the most recent.
- **Relationship to `ContradictionRecord`:** a claim's confidence becoming `CONTRADICTORY` is a *trigger*
  for opening or updating a `ContradictionRecord` (§C), not a substitute for one — `CONTRADICTORY`
  confidence without a linked `ContradictionRecord` is a defect R7/R8 must catch.
- `canon_state` is explicitly **not** defined here (decision register §D.2/§D.4) — this axis is confidence
  only, independent of both provenance (`source_type`) and any future canon-promotion state.

---

## C. ContradictionRecord

**Purpose.** Preserve, never silently resolve, materially conflicting evidence/claims (CRP-OD-10).

**Required fields:**

| Field | Type | Notes |
|---|---|---|
| `contradiction_id` | string | Stable unique id |
| `subject_id` | string | Character this concerns |
| `claim_ids` | string[] | The conflicting claims (≥2) |
| `source_evidence_ids` | string[] | Evidence per side, preserved |
| `description` | string | Plain statement of the conflict (e.g. "source A says X, source B says not-X") |
| `severity` | enum | `COSMETIC \| MATERIAL \| IDENTITY_CRITICAL` (architecture doc §8) |
| `resolution_status` | enum | `OPEN \| RESOLVED_BY_EVIDENCE \| OWNER_RESOLVED \| UNRESOLVED` (architecture doc §8) |
| `requires_human` | boolean | e.g. owner-fact vs. third-party-report conflicts |
| `created_by` | string | `role_id` or `system` (deterministic compiler/validator) that first detected it |

**Optional fields:**

| Field | Type | Notes |
|---|---|---|
| `resolvable_by_role` | string | `R1` (clarify by interview) \| `R2` (competing-hypothesis framing) \| `none` |
| `needs_interview` | boolean | Whether R1 should draft a clarifying question |
| `preferred_for_promotion` | string (`claim_id`) | Which side, if any, currently outranks for **promotion authority only** — see invariant below |
| `resolution_basis` | string | Why `preferred_for_promotion` was set, if set |

**Invariants:**

- **`preferred_for_promotion` never deletes the other side.** Per CRP-OD-10: `OWNER_DIRECT` outranks
  `MODEL_INFERENCE` for promotion authority, but the losing claim's record is preserved unchanged, still
  linked, still visible in the package's contradiction register.
- The pipeline **never silently chooses** — a `ContradictionRecord` reaching `RESOLVED_BY_EVIDENCE` must
  cite the exact evidence basis; reaching `OWNER_RESOLVED` requires a human decision reference.
- R6 (compiler) compiles contradictions **explicitly** into the package (both sides + status) — it never
  "corrects" one side away. R8 audits that no contradiction was dropped or silently resolved (mandatory
  check, see §I).
- Resolution priority when a choice is forced at assembly time (CRP-OD-10, architecture §8): owner
  evidence > direct observation > testimony > inference — and even then the losing side remains in the
  register, never removed.

**Producer:** any role or deterministic stage that detects a conflict (R1 gap analysis, R2 competing
hypotheses, R6/R7 structural detection).
**Consumer:** R6 (compiles into package), R7 (checks none dropped), R8 (audits preservation), R1 (may
receive `needs_interview=true` records as new question-plan input).
**Forbidden:** deleting or silently mutating a `ContradictionRecord`'s `claim_ids`; setting
`resolution_status=RESOLVED_BY_EVIDENCE` without evidence citation.
**Versioning:** status transitions are appended, not overwritten — keep a `status_history` in `metadata`
if implementation needs an audit trail (spec candidate, not mandatory field).

---

## D. RoleTask

**Purpose.** The bounded, least-privilege-enforcing unit of work handed to a role for one pipeline stage.

**Required fields:**

| Field | Type | Notes |
|---|---|---|
| `task_id` | string | Stable unique id |
| `role_id` | string | `R1`, `R2`, `R4`, `R6`, or `R8` for MVP (R3/R5 excluded — see spec §"MVP scope") |
| `role_version` | string | Exact registry-resolved version (never "latest") |
| `subject_id` | string | Character this task concerns |
| `run_id` | string | The reconstruction run this task belongs to |
| `evidence_snapshot_id` | string | Which immutable evidence snapshot this task may read |
| `allowed_evidence_ids` | string[] | Explicit allowlist within the snapshot (least privilege — may be the full snapshot for R1, a filtered subset for R2/R4 per Knowledge Profile) |
| `allowed_prior_results` | string[] (`task_id`s) | Which earlier `RoleResult`s this role may see (e.g. R4 may see R1's clarifications, never R2's psychology drafts — architecture §19) |
| `knowledge_profile_ref` | string | Which `KnowledgeProfile` (§G) governs this task |
| `input_contract_version` | string | Version of the `RoleTask` schema itself |
| `output_contract_version` | string | Expected `RoleResult` schema version |
| `permissions` | object | Explicit write scope (e.g. R1: new `SourceEvidence` via intake + question plans; R2: `RoleClaim` only) |
| `task_goal` | string | What this invocation is for (e.g. "initial reconstruction," "correction round 1 — resolve R8 defect list") |
| `revision_round` | integer | 0 = initial, 1/2 = correction rounds (CRP-OD-6) |

**Optional fields:**

| Field | Type | Notes |
|---|---|---|
| `stop_conditions` | object | Role-specific bounded-loop rules (e.g. R1's question-round budget — see spec §"R1 MVP contract") |
| `deadline_policy` | string | If a wall-clock/budget limit applies |

**Invariants:**

- `allowed_evidence_ids` and `allowed_prior_results` are **enforced allowlists**, not documentation — a
  role receiving a `RoleTask` must not be handed any evidence/result outside these lists (this is what
  makes least privilege actually enforceable, not just described).
- `permissions` must never grant a role write access to canon, another character's evidence/claims, or
  PAC/Sandbox live state (CRP-OD-12/13).
- `revision_round` may never exceed 2 (CRP-OD-6) without an explicit `HUMAN_DECISION_REQUIRED` gate having
  been passed first.

**Producer:** the deterministic orchestrator (not an LLM role — matches "no new orchestration framework,"
architecture §25).
**Consumer:** the target role.
**Forbidden:** a role task that omits `allowed_evidence_ids` (implying unrestricted access); silent
widening of permissions between revision rounds.
**Versioning:** `input_contract_version` bumped on any breaking field change; old versions remain valid for
in-flight runs.

---

## E. RoleResult

**Purpose.** What a role hands back after executing a `RoleTask`.

**Required fields:**

| Field | Type | Notes |
|---|---|---|
| `task_id` | string | Back-reference to the `RoleTask` |
| `role_id` | string | |
| `role_version` | string | |
| `completion_status` | enum | `COMPLETE \| INSUFFICIENT_EVIDENCE \| BLOCKED \| NEEDS_CLARIFICATION` |
| `claims` | `RoleClaim[]` | May be empty if `completion_status != COMPLETE` |
| `unknowns` | object[] | Explicit gap descriptions — first-class, not a failure |
| `contradictions` | `ContradictionRecord[]` (new or updated) | |
| `provenance_summary` | object | What evidence/prior results this role actually used (audit trail, not just what it was allowed to use) |

**Optional fields:**

| Field | Type | Notes |
|---|---|---|
| `requests_for_more_evidence` | object[] | Feeds R1's question plan on the next allowed round |
| `warnings` | string[] | Non-fatal issues the role wants surfaced (e.g. "corpus below recommended floor but above hard minimum") |
| `questions_for_r1` | object[] | R2/R4/R8 → R1 gap-request channel (architecture §26 `RoleResult`) |

**Invariants:**

- **No role is forced to produce complete character data.** `INSUFFICIENT_EVIDENCE` is always a valid,
  first-class result — never penalized in favor of a fabricated claim.
- `BLOCKED` is reserved for integrity failures (e.g. `allowed_evidence_ids` resolution failure, permission
  violation detected mid-task) — distinct from `INSUFFICIENT_EVIDENCE` (a content gap, not an integrity
  fault).
- `provenance_summary` must be populated even on `INSUFFICIENT_EVIDENCE`/`BLOCKED` results — provenance of
  *attempted* access matters for audit regardless of outcome.

**Producer:** the executing role.
**Consumer:** the orchestrator (routes `claims`/`contradictions` onward), R1 (for `questions_for_r1`), R6
(consumes `claims` from R2/R4 only, never raw `RoleResult` objects), R8 (full `RoleResult` history for
audit).
**Forbidden:** a `COMPLETE` result containing claims that violate the `RoleClaim` invariants (§B) — this
must be structurally impossible to accept downstream, not just discouraged.
**Versioning:** `output_contract_version` must match what the `RoleTask` requested; a mismatch is a
`BLOCKED` condition for the orchestrator, not a silent coercion.

---

## F. RoleRegistryEntry

**Purpose.** MVP candidate schema for the Role Registry ratified at the authority/activation level by
CRP-OD-11. This document proposes the **field-level schema**; CRP-OD-11 already fixed the *semantics*
(no auto-discovery, no latest-wins, human-approved activation) — this section does not reopen that.

**Required fields:**

| Field | Type | Notes |
|---|---|---|
| `role_id` | string | `R1`…`R8` (registry may list all 8; MVP marks only 5 `ACTIVE`) |
| `display_name` | string | e.g. "Evidence Interviewer" |
| `version` | string | Exact version string |
| `status` | enum | See §F.1 |
| `execution_type` | enum | `LLM_ROLE \| DETERMINISTIC_FUNCTION` |
| `prompt_ref` | string | Pointer to the role's prompt/spec artifact — location policy is a spec candidate, see spec doc §"Registry semantics" |
| `knowledge_profile_ref` | string | Pointer to this role's `KnowledgeProfile` (§G) |
| `input_contract_ref` | string | Pointer to the `RoleTask` schema version this role expects |
| `output_contract_ref` | string | Pointer to the `RoleResult` schema version this role produces |
| `permissions` | object | Declared write scope, mirrored into every `RoleTask` for this role |
| `activation_gate` | string | Human-approval reference required before this version becomes usable |

**Optional fields:**

| Field | Type | Notes |
|---|---|---|
| `predecessor_version` | string | For rollback/lineage — see spec-candidate rollback design |
| `deprecation_note` | string | If `status=DEPRECATED` |

### F.1 `status` — MVP candidate enum

| Value | Meaning |
|---|---|
| `ACTIVE` | Human-approved, currently invokable in MVP execution — R1, R2, R4, R6, R8 only |
| `INACTIVE` | Registered/known but not currently invokable (R3, R5 for MVP — per CRP-OD-11) |
| `REFERENCE` | Legacy role kept for historical/reference purposes only, never invoked (legacy R1–R8 prompts, `LEGACY_REFERENCE` per CRP-OD-14) |
| `DEPRECATED` | Formerly `ACTIVE`, explicitly retired by human decision, superseded by a newer version |

**Invariants:**

- No entry transitions to `ACTIVE` without `activation_gate` populated (evaluation + human approval, per
  CRP-OD-11 — no automatic promotion).
- Exactly one `version` per `role_id` may be `ACTIVE` at a time; prior `ACTIVE` versions become
  `DEPRECATED` on human-approved transition, never deleted (rollback = re-activating a `DEPRECATED`
  version via the same human-approval gate, not a destructive undo).

**Producer:** human-approved registry maintenance process (not automated).
**Consumer:** the orchestrator (resolves `role_id` → exact `ACTIVE` entry before creating any `RoleTask`).
**Forbidden:** the orchestrator invoking any role whose registry status is not `ACTIVE`; filesystem
auto-discovery populating this registry.
**Versioning:** the registry itself is versioned as a whole artifact (not per-entry), so a full history of
who-was-active-when is reconstructable.

---

## G. KnowledgeProfile

**Purpose.** Least-privilege, per-role knowledge routing (D-RKR-5, refined by CRP-OD-14: legacy KB is
**not** auto-inherited).

**Required fields:**

| Field | Type | Notes |
|---|---|---|
| `profile_id` | string | |
| `role_id` | string | |
| `version` | string | |
| `allowed_kb_refs` | string[] | Explicit allowlist of knowledge-base paths/modules — **defined fresh per vNext role**, never defaulted from legacy `knowledge_base/R1…R6` (CRP-OD-14) |
| `allowed_source_types` | string[] | Subset of §A.1's `source_type` vocabulary this role may consume |
| `forbidden_refs` | string[] | Explicit deny-list (e.g. `personas/kira/**` during the Kira benchmark, other characters' evidence by default) |
| `retrieval_policy` | enum | `EXACT_MODULAR_ONLY` for MVP (see spec candidate below) |

**Optional fields:**

| Field | Type | Notes |
|---|---|---|
| `budget_policy_ref` | string | Context-budget rule reference (spec candidate, see spec doc) |
| `legacy_kb_reuse` | object[] | If any legacy KB fragment is explicitly reused, records the compatibility+provenance review that authorized it (CRP-OD-14 requirement) |

**Invariants:**

- Whole-KB access is forbidden — `allowed_kb_refs` must be a bounded, explicit list, never a wildcard over
  all of `knowledge_base/`.
- `forbidden_refs` always includes cross-character canon by default (least privilege, per-character
  scope) unless explicitly and narrowly overridden with a recorded justification.
- Any entry in `allowed_kb_refs` pointing at legacy `knowledge_base/` content must carry a
  `legacy_kb_reuse` record — absence of one for a legacy path is a structural defect (R7 check).

**Producer:** human-approved profile authoring (same activation discipline as the registry).
**Consumer:** the orchestrator (builds `RoleTask.allowed_evidence_ids`/`allowed_kb_refs` from this),
R8 (audits actual usage against the profile).
**Forbidden:** semantic/embeddings-based retrieval for MVP (matches N7's embeddings-deferred precedent
and D-RKR-6's own "modular first" recommendation) — `retrieval_policy=EXACT_MODULAR_ONLY` is the MVP
default; semantic retrieval is out of scope until a future spec revision.
**Versioning:** profile version bumped whenever `allowed_kb_refs`/`forbidden_refs` change; a `RoleTask`
always pins the exact profile version it was built from.

---

## H. CandidateCharacterPackage

**Purpose.** The central MVP artifact — the output of the whole pipeline, never canon.

**Required fields:**

| Field | Type | Notes |
|---|---|---|
| `package_id` | string | |
| `subject_id` | string | |
| `package_version` | integer | Increments per revision round (0 = initial) |
| `source_snapshot_id` | string | Which immutable evidence snapshot this package was built from |
| `role_result_refs` | string[] (`task_id`s) | Every `RoleResult` that contributed |
| `claims` | `RoleClaim[]` | All claims that made it into the package (accepted, not rejected) |
| `contradictions` | `ContradictionRecord[]` | Full register, including unresolved ones |
| `unknowns` | object[] | Explicit gaps, carried forward from role results |
| `psychology_candidate` | object | Claims placed into P0–P5-tagged modules (never flattened — architecture §10) |
| `voice_candidate` | object | Claims placed into voice/speech modules, `OBSERVED/INFERRED/GENERATED_RULE/NEGATIVE_EXAMPLE`-labeled |
| `validation_results` | object | Output of the R7 consistency-validator function (§I) |
| `audit_result` | `ReconstructionAudit` (§I ref) | R8's independent verdict |
| `provenance_manifest` | object | Field → claim_id(s) → evidence_id(s) → content-hash chain, machine-checkable, zero unmapped fields |
| `created_at` | datetime | |
| `status` | enum | See §H.1 |

**Optional fields:**

| Field | Type | Notes |
|---|---|---|
| `lineage` | string (`package_id`) | Parent package, if this is a revision-round output |
| `behavioral_validation_refs` | string[] | Links to `BehavioralValidationResult`s (§K), if any CIS validation has run |

### H.1 `status` — lifecycle enum

`DRAFT → VALIDATED (R7 passed) → AUDITED (R8 verdict recorded) → HUMAN_APPROVED → REJECTED (terminal, any
stage)`

**Invariant, explicit and load-bearing:** `HUMAN_APPROVED` is **not** equivalent to canon write.
`HUMAN_APPROVED` means a human has approved this package for the *next* step (e.g. CIS behavioral
validation, or eventual canon-promotion consideration) — actual canon promotion is a **separate**,
human-only action outside CRP's authority entirely (CRP-OD-1/§20; the exact canon-write mechanism is an
explicitly deferred implementation parameter — see spec doc). CRP never performs that action itself.

**Invariants:**

- `provenance_manifest` must resolve for **every** field in `psychology_candidate`/`voice_candidate` — a
  field with no resolvable claim chain is a compiler defect (R6 must refuse to emit it, or emit it
  explicitly as `UNKNOWN`).
- R6 (the deterministic compiler) may **never** add a claim that didn't already exist in `role_result_refs`
  — it assembles, it does not invent.
- Contradictions are compiled **as-is** — both sides, current `resolution_status` — never collapsed.

**Producer:** R6 (deterministic compiler) creates `DRAFT`; the consistency-validator function transitions
to `VALIDATED`; R8 transitions to `AUDITED`; a human transitions to `HUMAN_APPROVED`/`REJECTED`.
**Consumer:** R8 (audits), human reviewer, CIS adapter (§J, only after `HUMAN_APPROVED`).
**Forbidden:** any automated process setting `status=HUMAN_APPROVED`; any write path from this artifact
toward `personas/`, `scenarios/`, `core/`, or any live runtime/canon store (R8 check #10, §I — immediate
`FAIL`/`BLOCKED` on detection).
**Versioning:** `package_version` + `lineage` give full revision-round history; packages are never deleted,
only superseded.

---

## I. ReconstructionAudit

**Purpose.** R8's independent verdict artifact — the control, not part of authoring.

**Required fields:**

| Field | Type | Notes |
|---|---|---|
| `audit_id` | string | |
| `package_id` | string | |
| `package_hash` | string | Content hash of the exact package version audited (stale-invalidation anchor) |
| `auditor_role_version` | string | Exact R8 version used |
| `checks` | object[10] | One entry per mandatory check below, each `{check_name, result, findings[]}` |
| `verdict` | enum | `PASS \| FAIL \| INCONCLUSIVE \| BLOCKED` |
| `defects` | object[] | Structured, evidence-linked defect list (feeds correction rounds) |
| `correction_requests` | object[] | Which role(s)/stage(s) should re-run, and why |

**The 10 mandatory MVP checks** (architecture doc §16, adopted verbatim, `1` re-numbered from `#8` for the
MVP's smaller role set):

1. Provenance completeness (every field → claim → evidence chain resolves)
2. Unsupported assertions (`FACT`-grade claims without direct evidence)
3. Contradiction preservation (none dropped/silently resolved)
4. Confidence misuse (`INFERENCE`/`MODEL_INFERENCE`-sourced content rendered as `KNOWN`)
5. Role-boundary violations (e.g. R2 asserting voice patterns, R1 asserting psychology)
6. Module/layer placement errors (e.g. a single-observation claim placed as a stable P0 trait)
7. Missing evidence coverage (declared `UNKNOWN`s vs. actual source gaps — consistency check)
8. Schema completeness (against the persona schema this package targets)
9. Source leakage / hidden-eval leakage (forbidden sources in authoring context — critical during the
   Kira benchmark, §"Kira MVP benchmark design")
10. Canon-write attempt (any write path toward `personas/`, `scenarios/`, `core/`, or live runtime state
    → **immediate `FAIL`/`BLOCKED`**, non-negotiable)

**Invariants:**

- `verdict=FAIL` = defects found with sufficient evidence to describe them.
- `verdict=INCONCLUSIVE` = audit evidence itself incomplete (R8 could not fully evaluate — distinct from
  the package having defects).
- `verdict=BLOCKED` = integrity violation (hash mismatch against `package_hash`, evidence-ledger
  corruption, leakage detected) — terminal for this package version, requires human intervention before
  any further round.
- **Stale-audit invalidation rule (spec candidate for §37-#16's open item):** if `package_hash` no longer
  matches the current package content, the audit is automatically stale and its `verdict` may not be relied
  upon for any downstream gate (e.g. cannot authorize `HUMAN_APPROVED`) until re-audited.
- R8 never reads authoring-session internals — only the package + full evidence ledger (independence
  invariant, unchanged from architecture §16/§19).

**Producer:** R8.
**Consumer:** human reviewer, the orchestrator (routes `correction_requests` into the next `RoleTask`
batch, bounded by CRP-OD-6's 2-round limit).
**Forbidden:** R8 producing claims or editing the package; any correction round proceeding without a
`correction_requests` list to bound its scope.
**Versioning:** one `ReconstructionAudit` per audited `package_version`; never edited after creation
(re-audit produces a new record).

---

## J. BehavioralValidationRequest

**Purpose.** The stable, versioned boundary from CRP into CIS — CRP knows nothing about CIS internals
(`probe_runner`, `memory_gate`, harness details), per architecture doc §21.

**Required fields:**

| Field | Type | Notes |
|---|---|---|
| `request_id` | string | |
| `subject_id` | string | |
| `package_id` | string | |
| `package_version` | integer | |
| `package_hash` | string | Anchors the request to an exact, `HUMAN_APPROVED` package snapshot |
| `adapter_version` | string | Version of the CRP↔CIS adapter contract itself |
| `semantic_modules_needed` | string[] | Which package modules (`psychology_candidate`, `voice_candidate`, …) this validation run needs |
| `probe_profile_ref` | string | Which CIS probe/evaluation family to run — opaque to CRP, CIS-defined |
| `provenance_ref` | string | Back-reference to `provenance_manifest`, so CIS discrepancies can cite exact claims |
| `authorization_ref` | string | Human authorization for running this validation (CRP MVP never triggers CIS automatically) |

**Invariants:**

- Only a `HUMAN_APPROVED` package may be the subject of a request — CRP must refuse to build a request
  from a `DRAFT`/`VALIDATED`/`AUDITED`-only package.
- CRP does not know or care how `probe_profile_ref` is executed — the adapter contract is the only
  coupling point, versioned on both ends (architecture §21).

**Producer:** a human-authorized CRP-side process (never autonomous).
**Consumer:** the CIS adapter (external to CRP's own contracts, referenced but not defined here).
**Forbidden:** CRP embedding any CIS-internal identifiers (probe IDs, harness paths) directly into its own
contracts — only the opaque `probe_profile_ref`.
**Versioning:** `adapter_version` must be checked compatible by both sides before a request is accepted.

---

## K. BehavioralValidationResult

**Purpose.** What comes back from CIS — evidence for revision, never an automatic editor of the candidate.

**Required fields:**

| Field | Type | Notes |
|---|---|---|
| `request_id` | string | |
| `validation_run_id` | string | |
| `package_id` | string | |
| `package_version` | integer | |
| `probe_results` | object[] | Per-probe-family outcomes (opaque structure, CIS-defined) |
| `discrepancy_report` | `BehavioralDiscrepancy[]` | See §K.1 |
| `aggregate_status` | enum | Reuses CIS's own owner-frozen judge-protocol verdict states (not redefined here) |
| `evidence_refs` | string[] | Links back into CRP's `provenance_manifest` where discrepancies implicate specific claims |

### K.1 `BehavioralDiscrepancy` (per-item shape)

| Field | Type | Notes |
|---|---|---|
| `discrepancy_id` | string | |
| `dimension` | enum | `PSYCHOLOGY_MISMATCH \| VOICE_MISMATCH \| RELATIONSHIP_MISMATCH \| MEMORY_BEHAVIOR_MISMATCH \| UNKNOWN_UNCOVERED_BEHAVIOR \| UNEXPECTED_LEAKAGE \| CONTRADICTION_MANIFESTATION` |
| `claim_id` | string (optional) | If traceable to a specific candidate claim |
| `expected_vs_observed` | string | Plain description |
| `severity` | enum | Mirrors `ContradictionRecord.severity` (`COSMETIC \| MATERIAL \| IDENTITY_CRITICAL`) for consistency |

**Invariants:**

- A `BehavioralValidationResult` is **evidence**, not a mutation instruction. It **never** auto-rewrites
  the candidate package. A discrepancy becomes new input to a *new* revision round (bounded by CRP-OD-6,
  same 2-round limit as authoring-side corrections) or a human review decision — it does not bypass either.
- `UNEXPECTED_LEAKAGE` findings are treated as **critical** regardless of stated severity — they trigger
  the same non-negotiable stop as R8's canon-write-attempt check (§I check 10).

**Producer:** CIS (external to CRP).
**Consumer:** the human reviewer, and — only via a new bounded revision round — R1/R2/R4 (as new
`requests_for_more_evidence`-equivalent input).
**Forbidden:** any automated pipeline consuming this result and directly editing `CandidateCharacterPackage`
fields.
**Versioning:** one result per `validation_run_id`; re-running validation produces a new result, old ones
retained for audit trail.

---

*End of contracts document. See `CRP_MVP_SPEC_v1.md` for the execution graph, revision-loop semantics,
per-role MVP contracts, and acceptance criteria that tie these contracts together.*
