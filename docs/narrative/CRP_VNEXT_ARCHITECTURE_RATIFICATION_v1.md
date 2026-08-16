# CRP vNext — ARCHITECTURE RATIFICATION (v1)

> **Status:** OWNER-RATIFIED DIRECTION — IMPLEMENTATION NOT AUTHORIZED
> **Date:** 2026-08-16
> **Track:** CRP vNext (Character Reconstruction Pipeline), successor direction to legacy R1–R8
> **Companion document:** [`CRP_VNEXT_DECISION_REGISTER_v1.md`](CRP_VNEXT_DECISION_REGISTER_v1.md) — full §37 / D-RKR mapping, taxonomy, owner-gap countdown.
> **Source authority:** owner acceptance communicated 2026-08-16, formalizing the proposal in
> `RKR_CHARACTER_RECONSTRUCTION_PIPELINE_VNEXT_ARCHITECTURE_2026-08-16.md` (`LOCAL_STORAGE/handoffs/`).

---

## 0. What this document is

This document formally ratifies **CRP-OD-1 … CRP-OD-10** (owner shorthand: **OD-1 … OD-10**) — ten
owner decisions accepted on 2026-08-16 that establish the direction for the Character Reconstruction
Pipeline vNext. It does **not** ratify an MVP specification, does **not** authorize implementation, and
does **not** close the pre-existing `D-RKR-1…15` register or all eighteen `§37` historical decisions —
those are mapped item-by-item in the companion decision register, and most remain open or only
partially closed.

Do not read acceptance of OD-1–OD-10 as "all historical RKR decisions closed." They are not.

---

## 1. "CRP vNext / Variant C" — formal establishment

**Before 2026-08-16**, no "Variant C" document existed as repository authority. The 2026-08-16
architecture synthesis searched the repository and `LOCAL_STORAGE/handoffs` explicitly and found no
such document (case-sensitive and case-insensitive); it flagged the missing ratification as its own
**OD-1** and adopted the audit's §35/§10 proposal as the base direction pending owner confirmation.
"Variant C" existed only as conversation-level/working shorthand before that date — never as ratified
architecture.

**As of 2026-08-16**, the owner has accepted that base direction. This document is the act of
ratification. From this date forward, **"CRP vNext / Variant C"** formally denotes:

- evidence-first reconstruction (claim-level provenance, immutable evidence snapshot);
- bounded AI roles as tools, not autonomous authors;
- LLM analytical roles **propose**; mechanical invariants are **deterministic-first**;
- independent R8 audit before any human review;
- human controls canon; **no automatic canon writes**.

The legacy R1–R8 pipeline (`roles/ROLE_1…8_*`) is **reference/evidence only** — it is not the vNext
execution contract, and is not deprecated or deleted by this ratification (see §6).

---

## 2. CRP-OD-1 … CRP-OD-10 (owner shorthand: OD-1 … OD-10)

Full rationale/implication text lives in the decision register. Summary:

| ID | Owner shorthand | Decision |
|---|---|---|
| CRP-OD-1 | OD-1 | vNext / Variant C direction ratified as described in §1 above. Legacy R1–R8 = reference only. |
| CRP-OD-2 | OD-2 | R4 legacy baseline = **v1.3**. R4 v2.0 = **UNRATIFIED_REFERENCE** (not deprecated, not promoted). vNext role **Voice Reconstruction Analyst** requires its own future contract. |
| CRP-OD-3 | OD-3 | R5 vNext name/function = **VISUAL OBSERVER**. Permitted: observable appearance, clothing/style, posture, observable expression in a specific image, presentation cues, reference provenance. Forbidden: personality/morality/intelligence/psychological-diagnosis/sexuality inference from appearance. Legacy name "Physiognomist" is not the vNext role name. |
| CRP-OD-4 | OD-4 | R7 vNext responsibility = **CONSISTENCY VALIDATOR**, deterministic-first (schema consistency, terminology normalization, duplicate detection, provenance completeness, cross-module consistency, unsupported-claim detection). R7 must not invent or "improve" persona content. Not required to be an autonomous LLM role in MVP. |
| CRP-OD-5 | OD-5 | CRP vNext MVP **execution** subset = **R1 + R2 + R4 + R6 + R8** (Evidence Interviewer, Psychological Hypothesis Analyst, Voice Reconstruction Analyst, Deterministic Persona Compiler, Independent Evidence Auditor). R3 = optional gated specialist. R5 = optional Visual Observer. R7 = deterministic support/validation stage. All 8 roles are **not** required for MVP. This is an execution-subset decision, not a registry-membership decision — see decision register §37/D-RKR-1 mapping. |
| CRP-OD-6 | OD-6 | Maximum autonomous/bounded correction rounds = **2**. After two unsuccessful correction rounds: `HUMAN_DECISION_REQUIRED`. No infinite role loops, no autonomous endless reconstruction. |
| CRP-OD-7 | OD-7 | Kira reconstruction benchmark uses a strict split: **AUTHORING INPUT** vs **HIDDEN EVALUATION REFERENCES**. Roles must not receive full existing Kira canon merely to reproduce it. Output = candidate `Kira'`. Existing Kira canon is read-only and must not be overwritten. Behavioral validation: candidate `Kira'` → CIS → hidden evaluation. |
| CRP-OD-8 | OD-8 | Confidence/uncertainty vocabulary = **KNOWN / PROBABLE / POSSIBLE / UNKNOWN / CONTRADICTORY**. No fake numeric precision, no mechanical averaging. Composite-conclusion confidence cannot exceed the weakest *necessary* evidentiary link. Contradictory evidence must remain visible. See decision register §D for full taxonomy reconciliation (this vocabulary is a **confidence axis**, kept separate from source/provenance and from canon state — see §5 below). |
| CRP-OD-9 | OD-9 | R3 is **optional and explicitly gated**: requires relevant use case, authorization/opt-in where required, sufficient direct evidence. Allowed outcomes: `SKIPPED_NOT_AUTHORIZED`, `SKIPPED_NOT_NEEDED`, `INSUFFICIENT_EVIDENCE`. Forbidden: inference from appearance, forced completeness, inference solely from attachment labels, model priors promoted as character facts. |
| CRP-OD-10 | OD-10 | `OWNER_DIRECT` outranks `MODEL_INFERENCE` for **promotion authority**. Higher-priority evidence does **not** delete conflicting evidence — material conflicts are preserved, both claims recorded, never silently averaged or "corrected." Canonical principle: **UNRESOLVED CONTRADICTION > SILENT CORRECTION.** |

---

## 3. CRP authoring positioning (CIS boundary)

CRP vNext belongs to the **CIS Authoring** side of the pipeline. It produces a
**CANDIDATE_CHARACTER_PACKAGE** — not runtime memory, not canon.

```
CRP Authoring
  → candidate semantic character package
  → CIS behavioral validation
  → human review
  → separate canon promotion (human-only, out of CRP's authority)
```

CRP vNext must **not**:

- become CIS runtime;
- become character memory persistence;
- directly mutate any live persona/relationship/memory state at runtime;
- write canon automatically;
- bind to Ren'Py/Aside SQLite internals;
- create a second character-memory system alongside existing runtime memory.

This boundary is unchanged from the source architecture doc (`RKR_CHARACTER_RECONSTRUCTION_PIPELINE_VNEXT_ARCHITECTURE_2026-08-16.md` §20–21) and is ratified as-is; no new CIS layer names are introduced by this ratification (see decision register §D for why the previously expected "A. Authoring / B. Runtime / C. Memory / D. Evolution / E. Canon Promo" layer set was not used — it was not found in any accessible source).

---

## 4. R1–R8 vNext role summary (as ratified)

| Role | vNext name | MVP status (OD-5) | Key boundary |
|---|---|---|---|
| R1 | Evidence Interviewer | **Included** | No psychology invention; literary portrait is non-canon presentation only |
| R2 | Psychological Hypothesis Analyst | **Included** | Competing hypotheses only; CIS verifies; never flattens into permanent trait |
| R3 | Optional Intimacy Profile Specialist | Optional, gated (OD-9) | No inference from appearance; no forced completeness |
| R4 | Voice Reconstruction Analyst | **Included** | Corpus-based; `OBSERVED/INFERRED/GENERATED/NEGATIVE` pattern labels; new contract required (OD-2) |
| R5 | Visual Observer | Optional | Observation only; zero psychology/morality/intelligence/sexuality inference from appearance |
| R6 | Deterministic Persona Compiler | **Included** | Invents nothing; module-first; contradictions compiled explicitly, never "corrected" |
| R7 | Consistency Validator | Deterministic support stage | Never invents/improves content; not required as standalone LLM role in MVP |
| R8 | Independent Evidence Auditor | **Included** | Reads package + evidence ledger, not authoring sessions; mandatory checks incl. canon-write attempt = immediate FAIL/BLOCKED |

---

## 5. Confidence vs. provenance vs. canon state — kept separate

Ratified as three **independent** concepts (full taxonomy table in the decision register):

- **Provenance / source_type** — where a claim came from (e.g. `OWNER_DIRECT`, `MODEL_INFERENCE`,
  `MODEL_EXAMPLE`, and the other source classes evidenced in the RKR audit's evidence/provenance flow).
  Set once, at claim creation. Not a confidence judgment.
- **Confidence (OD-8)** — `KNOWN / PROBABLE / POSSIBLE / UNKNOWN / CONTRADICTORY`. An epistemic-strength
  judgment, independent of who/what produced the claim. `OWNER_DIRECT` does **not** mean `KNOWN` by
  definition, and `MODEL_INFERENCE` does **not** mean `POSSIBLE` by definition — a direct owner
  statement can still be `CONTRADICTORY` if it conflicts with other evidence; a model inference can be
  `PROBABLE` if strongly corroborated.
- **Canon state** — whether a claim/field has been human-approved into canon. Independent of both of the
  above; an `OWNER_DIRECT` claim is not automatically canon, an inferred claim is not automatically
  rejected, and canon promotion remains human-controlled per OD-1/§20. **No specific canon-state enum is
  ratified by this document** — see decision register §E/§F, this is recorded as an open implementation
  parameter, not invented here.

---

## 6. Precedence

Repository authority order (unchanged, per `AGENTS.md` §"Источники правды" and
`docs/narrative/00_DOCUMENT_INDEX.md`):

1. `AGENTS.md` — root authority.
2. `NARRATIVE_DECISIONS_v1.md` — canonical for the specific product/architecture questions in its own
   list (§1–§9). CRP vNext is a new track not in that list, so it does not conflict with it.
3. **This ratification + the companion decision register** — canonical for the CRP vNext direction
   questions (OD-1–OD-10) as of 2026-08-16.
4. Active specifications (none yet exist for CRP vNext — MVP spec is future work).
5. `RKR_CHARACTER_RECONSTRUCTION_PIPELINE_VNEXT_ARCHITECTURE_2026-08-16.md` and
   `RKR_R1_R8_ROLE_INTELLIGENCE_READONLY_AUDIT_2026-08-03.md` — evidence/reference, superseded only on
   the specific points OD-1–OD-10 decide; everything else in those documents stands as proposal-grade
   reference, not owner authority.
6. Legacy role prompts (`roles/ROLE_1…8_*`) — historical/reference artifacts for the legacy pipeline;
   remain usable for historical analysis, **not** globally deprecated by this ratification (no owner
   decision says so).

If a ratified OD directly conflicts with an older proposal-grade statement in the two RKR documents, the
older statement is **superseded only on that specific point** — nothing else in those documents is
rewritten or invalidated.

---

## 7. Implementation authorization — explicit boundary

**RATIFICATION ≠ IMPLEMENTATION AUTHORIZATION.**

| | Status |
|---|---|
| CRP vNext / Variant C direction | OWNER_RATIFIED |
| OD-1 … OD-10 | OWNER_RATIFIED |
| MVP specification | **NOT YET RATIFIED** |
| MVP implementation | **NOT AUTHORIZED** |
| Kira reconstruction execution | **NOT AUTHORIZED** |
| Role prompt rewrites / router code / compiler code / schema implementation | **NOT AUTHORIZED** |
| Canon mutation of any kind | **NOT AUTHORIZED** |

Allowed next step: draft an MVP specification/preflight document in a **separate** worktree/branch, itself
subject to owner review before any implementation branch is opened.

---

## 8. See also

- [`CRP_VNEXT_DECISION_REGISTER_v1.md`](CRP_VNEXT_DECISION_REGISTER_v1.md) — full OD entries, §37
  (1–18) mapping, D-RKR (1–15) mapping, taxonomy reconciliation, owner-gap countdown, implementation
  parameters, cleanup backlog.
- `RKR_CHARACTER_RECONSTRUCTION_PIPELINE_VNEXT_ARCHITECTURE_2026-08-16.md` (`LOCAL_STORAGE/handoffs/`) —
  source architecture proposal.
- `RKR_R1_R8_ROLE_INTELLIGENCE_READONLY_AUDIT_2026-08-03.md` (`LOCAL_STORAGE/handoffs/`) — source audit,
  §37 "Required Owner Decisions."
- `docs/narrative/AI_ROLES_AND_KNOWLEDGE_ROUTING_CONCEPT_v1.md` — source of D-RKR-1…15.
