# Character Memory + Evolution Semantics v1 — PROPOSAL

Status: **PROPOSAL.** Baseline commit:
`ced7a857ab77b593b2e126b59cab583101294099`.

Scope: define a minimal, coherent, implementable v1 semantic model for
selective memory, numeric Relationship/Psychology meaning, safe state
evolution, and behavioral influence — grounded in what the repository
actually does today.

---

## 0. Owner-accepted decisions (OD-MEM-EVO-01..12 = A)

The owner accepted decisions **OD-MEM-EVO-01 .. OD-MEM-EVO-12**, all option
**A**, matching this document's recommendations, with one wording
correction recorded here:

- **Evolution v1 is `structured / rule-produced EvolutionCandidate` →
  validation → human approval → state mutation.** The candidate producer in
  v1 is a **deterministic rule**, not an LLM. An LLM proposer is **deferred**.
  Earlier draft phrasing that paired "model-proposed" with
  "deterministic / no-LLM" was contradictory; the canonical v1 decision is
  the rule-produced candidate + human approval, and §7 below is read with
  that correction.
- OD-MEM-EVO-05 band names are **`VERY_LOW / LOW / MID / HIGH / VERY_HIGH`**
  (generic magnitude bands — never "negative" / "positive"), thresholds
  `-100..-60 / -59..-20 / -19..19 / 20..59 / 60..100`.
- OD-MEM-EVO-04: Relationship/Psychology dimensions are
  **character-package-declared**; Core provides only schema, validation,
  band interpretation, and the rendering mechanism.
- OD-MEM-EVO-06: provider-facing rendering carries **value + generic band +
  dimension-specific meaning** (meaning supplied by the package).
- OD-MEM-EVO-07: **MISSING ≠ 0**, permanently; `0` has no universal meaning.
- OD-MEM-EVO-08 (forgetting/decay), OD-MEM-EVO-09 (1 event → 1 record),
  OD-MEM-EVO-10 (raw-context bound: ≤20 events **and** ≤6000 chars),
  OD-MEM-EVO-11 (`EVOLUTION_APPROVED` provenance for approved evolution only;
  Consolidated Memory is not a Runtime State source kind),
  OD-MEM-EVO-12 (behavioral tests use pre-registered directional rubrics) —
  all accepted as written.

A separate slice
(`DIMENSION_SEMANTICS_BEHAVIOR_RENDERING_FOUNDATION_V1`) implements the
generic dimension schema, the band interpreter, the semantic renderer, and a
bounded Grounded-v2 rendering hook. Consolidated Memory and EvolutionCandidate
themselves are **not** implemented in that slice.

---

## 1. Current Implemented Reality

Stated as fact from the code, separating **IMPLEMENTED TODAY** from what is
merely absent.

### 1.1 Message / event memory — IMPLEMENTED

- `services/character_runtime/memory.py` → `runtime_memory.sqlite3`,
  one DB per workspace root, table `runtime_events`.
- Fields: `event_id`, `subject_id`, `session_id`, `event_type`, `meaning`,
  `created_at`, `seq` (monotonic causal write order), `provenance` (nullable).
- **Append-only.** No row is deleted; `event_id` / `meaning` are never
  rewritten. Duplicate `event_id` fails closed.
- `event_type` is a free string; in practice exactly `USER_MESSAGE` and
  `CHARACTER_MESSAGE` (written by both policies' `persist()`).
- Two read orders: `load_events` = legacy `ORDER BY created_at, event_id`
  (Beta v1 depends on this, OD-CL-02); `load_events_causal` =
  `ORDER BY seq` (observability + Grounded v2).

### 1.2 Summaries — NOT IMPLEMENTED, NOT SCHEMA-SUPPORTED

No summary table, column, artifact, or code path exists in
`services/character_runtime` or `services/character_lab`. (`summaries` /
`message_parts` / `canonical_snapshots` appear only in the separate legacy
VNE narrative CRP docs under `docs/narrative/` and `docs/1x_*` — a different
subsystem, explicitly out of scope here.)

### 1.3 Canonical snapshots — NOT IMPLEMENTED, NOT SCHEMA-SUPPORTED

Same as 1.2. Current Runtime State is *derived on read* from the append-only
ledger; it is not snapshotted or persisted as a separate object.

### 1.4 Provenance values — IMPLEMENTED (exactly four)

`services/character_lab/provenance.py`:

| Value | Meaning | Grounding treatment |
|---|---|---|
| `USER_STATED` | the user said it — **not** "objectively true" | Grounded v2 surfaces these, seq-ordered, under an explicit "со слов собеседника — не установленные факты" header |
| `CHARACTER_UTTERANCE` | the model/character said it | **never** surfaced as factual grounding; retained only as audit trail |
| `SCENE_SETUP` | owner-authored situational input | Scene is session-scoped, rendered as its own additive block; never durable memory |
| `LEGACY_UNCLASSIFIED` | pre-provenance row (stored `NULL` / unknown) | surfaced honestly; never rewritten to a stronger claim; never established grounding |

`is_established_fact(...)` returns `False` for every category, always.
`NULL`/unknown is surfaced (never persisted) as `LEGACY_UNCLASSIFIED`.
Dialogue turns may persist only `USER_STATED` and `CHARACTER_UTTERANCE`.

### 1.5 Current factual-grounding rules — IMPLEMENTED

- **Beta v1** (`BetaV1CurrentPolicy`): ignores provenance entirely; renders
  every prior-session memory line verbatim as `- [event_type] meaning`.
  Frozen legacy behavior (OD-CL-02) — do not change.
- **Grounded v2** (`GroundedV2Policy.select_memory`): includes an event
  **only if** `normalize(provenance) == USER_STATED`; sorts by `seq`;
  renders under `ПАМЯТЬ / MEMORY (со слов собеседника — не установленные
  факты)` with line prefix `- [со слов собеседника] `.
  `CHARACTER_UTTERANCE`, `LEGACY_UNCLASSIFIED`, and `NULL` are excluded
  from grounding.
- `SCENE_SETUP`: only via an active session Scene, as a separate system
  block; never merged into durable-memory grounding.

### 1.6 State domains — IMPLEMENTED

`services/character_runtime/state.py` → `runtime_state.sqlite3` (own DB per
workspace, `runtime_memory.sqlite3` untouched). Append-only
`runtime_state_events` ledger; current state derived (last `SET` per
`domain+key` wins; `REMOVE` ⇒ absent).

| Domain | Value | Key format | Extra |
|---|---|---|---|
| `FACT` | arbitrary non-empty text | free | — |
| `RELATIONSHIP` | canonical integer, **[-100, 100]** | `^[a-z0-9_]+\.[a-z0-9_]+$` (`subject.dimension`) | supports `ADJUST` (delta) |
| `PSYCHOLOGY` | canonical integer, **[-100, 100]** | `^[a-z0-9_]+$` (`dimension`) | supports `ADJUST` (delta) |

- Absence of a numeric key = **UNKNOWN / NOT INITIALIZED**, deliberately
  distinct from `0`. `ADJUST` on an uninitialized key fails deterministically.
- Out-of-range `SET`/`ADJUST` is **rejected, never clamped**.

### 1.7 Automatic state evolution — NOT IMPLEMENTED

- `ACTIVE_SOURCE_KINDS = (SOURCE_OPERATOR_CONFIRMED,)` — the only way a state
  fact is ever created or changed is an explicit deterministic operator
  action (`record_set` / `record_adjust` / `record_remove`).
- `CharacterLabApp.runtime_state()` returns `automatic_promotion: False`,
  `automatic_evolution: False`.
- Tests assert memory/scene/model do not evolve numeric state and that
  loading the Accepted Package creates no evolution state.

### 1.8 Behavioral effect today — IMPLEMENTED (minimal)

Grounded v2 injects **raw current values only**, as `- key: value` lines
under RU headers, with the footer: *"текущие подтверждённые оператором
значения времени выполнения (шкала -100..+100). Это не неизменный канон
персонажа."* No semantic band, no interpretation text, no character-specific
expression mapping. Beta v1 ignores state completely.

### 1.9 Portability today — IMPLEMENTED (by omission)

No KIRA-specific dimension is hard-coded in Core or runtime. Dimension names
are free strings validated only by `[a-z0-9_]` regex. Capabilities are
backend-resolved flags. There is no dimension-definition schema and no
per-dimension metadata anywhere.

---

## 2. Memory V1 Proposal

**One Memory system, three logical layers, two physical stores.** Do not
build a second memory engine.

| Layer | What it is | Persistence | v1 change |
|---|---|---|---|
| **EVENT LOG** | raw causal conversation/events, provenance-preserving | existing `runtime_events` (append-only) | **none** — keep byte-compatible |
| **WORKING CONTEXT** | the bounded material a single turn selects | ephemeral — the policy's `AssemblyManifest`, never a new truth object | add an **explicit bound** (see §2.1) |
| **CONSOLIDATED MEMORY** | compact, persistent, long-term memory derived from *eligible* events | **new** append-only store, source-ref-preserving (see §2.2) | **new** |

This three-layer model is **recommended**: the EVENT LOG and WORKING CONTEXT
already exist and are sound; only CONSOLIDATED MEMORY is genuinely new, and
it is additive (never edits the event log).

### 2.1 Working context bound (gap fix)

`GroundedV2Policy.select_memory` currently returns **all** `USER_STATED`
events with no cap. v1 adds a deterministic bound: keep at most the last
`N` `USER_STATED` events (and/or a max character budget), newest by `seq`.
`N` / budget is a config value, not magic — owner sets it (Decision 11).
Consolidated memory (below) is what preserves older material.

### 2.2 Consolidated memory store

- New append-only table (its own file, e.g. `consolidated_memory.sqlite3`,
  or a new table in the state DB — implementation detail for the build
  slice). Never writes `runtime_events`, never writes the Accepted Package.
- One consolidated record carries: `record_id`, `subject_id`,
  `workspace`-scope, a short normalized `label` (subject + predicate-ish),
  free-text `value`, `provenance` (always `USER_STATED` in v1),
  `source_event_ids` (≥1), `first_seen_seq`, `last_seen_seq`,
  `seen_count`, `session_ids`, `status`
  (`ACTIVE` / `SUPERSEDED` / `CONTRADICTED` / `RETIRED`),
  `supersedes` / `superseded_by` / `contradicts` refs, `approved_by`,
  `approved_at`.
- **Auditable by construction:** every consolidated record points back to
  the exact events it came from.

### 2.3 Promotion flow (bounded, not "the LLM decides")

```
event  →  eligibility predicate (deterministic)  →  MemoryPromotionCandidate
       →  dedupe / supersede / contradiction check  →  human approval  →  consolidated record
```

**v1 eligibility predicate (deterministic, all must hold):**

1. `provenance == USER_STATED` — hard gate. `CHARACTER_UTTERANCE`,
   `SCENE_SETUP`, `LEGACY_UNCLASSIFIED`, `NULL` are never eligible.
2. content passes a trivial-utterance filter (min length; not a
   greeting/farewell/acknowledgement from a small stoplist).
3. **novelty** — not already an `ACTIVE` consolidated record with the same
   normalized `label`+`value`.
4. **recurrence OR explicit mark** — either the same normalized content
   appears in ≥ 2 distinct sessions, **or** an operator explicitly marks the
   event for promotion.

Candidates are generated deterministically and persisted; **nothing is
consolidated without human approval in v1** (mirrors the
`OPERATOR_CONFIRMED`-only state model). Rejected candidates are retained.

**Deferred, named explicitly:** emotional-significance scoring, privacy /
sensitivity classification, LLM salience ranking, temporal-persistence
heuristics. These are real factors but are not needed to validate the model.

---

## 3. Truth / Provenance Rules

Preserve the established invariant: **STORED ≠ FACTUAL TRUTH.**

| Category | May be remembered as | May be consolidated as | Never |
|---|---|---|---|
| `USER_STATED` | "the user said X (session S, date D)" | a **user-reported** fact, provenance + source refs retained | silently accepted as objective external fact; used to edit the package |
| `CHARACTER_UTTERANCE` | "the character said X" (audit trail only) | — (never) | a user fact; an external fact; factual grounding; an evolution trigger for "the character believes X" |
| `SCENE_SETUP` | active-Scene situational context | — (never; session-scoped) | durable memory; canon |
| `LEGACY_UNCLASSIFIED` / `NULL` | shown honestly in the inspector | — (never) | promoted to a stronger claim |

- The **Accepted Character Package remains the only character canon** and is
  never written by memory, consolidation, or evolution.
- A character's own generated utterance does **not** become a factual memory
  merely because it was stored.

---

## 4. Consolidation / Summarization

### 4.1 What summarization must do

Compress multiple `USER_STATED` events **about the same subject/label** into
one consolidated record, **retaining every `source_event_id`**, the
provenance label, and first/last `seq`.

### 4.2 What summarization must NOT do

- rewrite or extend the Character Package;
- silently upgrade an uncertain statement into a fact (provenance stays
  `USER_STATED`; wording stays hedged if the source was hedged);
- erase or collapse provenance;
- turn a hallucinated `CHARACTER_UTTERANCE` into truth (it is never an input).

### 4.3 v1 recommendation: verbatim-first

Start with **1 eligible event → 1 candidate → 1 consolidated record**
(verbatim `value`, no abstraction) plus dedupe/supersede. Multi-event
deterministic merging (still no LLM, still refs-retained) is a small
follow-up if the owner wants it (Decision 10). **No LLM summarization in
v1.**

### 4.4 Auditability

Every consolidated record is reconstructable from its `source_event_ids`
against the immutable event log. The Memory Inspector shows both layers and
the links between them.

---

## 5. Relationship Semantics

Current shape: `RELATIONSHIP`, key `subject.dimension`, range `-100..100`,
missing = UNKNOWN.

### 5.1 MISSING ≠ 0 (permanent)

- **MISSING** = "never assessed / not established." Must stay distinct from
  any stored value. (Already true in code; make it a ratified rule.)
- **`0`** = an *explicitly set* neutral/baseline midpoint — meaningful
  **only** for a dimension whose definition declares `0` as its neutral
  anchor. Not a universal "no relationship" sentinel.

### 5.2 Dimension-definition schema (recommended)

Each Relationship dimension a character uses is described by metadata:

| Field | Meaning |
|---|---|
| `id` | matches `[a-z0-9_]+` |
| `label` | human-readable name |
| `description` | what this dimension tracks |
| `negative_anchor` / `neutral_anchor` / `positive_anchor` | text describing each pole and the midpoint |
| `behavioral_interpretation` | **generic** description of what high/low implies for behavior (the *package* refines expression — §8) |
| `update_policy` | who/what may change it; v1 = `OPERATOR_CONFIRMED` only |
| `default_step` / `max_step` | delta sizing for evolution (§7) |
| `bands` (optional override) | per-dimension band thresholds |

### 5.3 Interpretable bands

Default 5-band split with a symmetric neutral deadzone:

| Band | Range |
|---|---|
| `very_negative` | `[-100, -60]` |
| `negative` | `(-60, -20]` |
| `neutral` | `(-20, 20)` |
| `positive` | `[20, 60)` |
| `very_positive` | `[60, 100]` |

Justification: an even, symmetric split that treats a small band around the
midpoint as "no strong signal." Thresholds live in the dimension definition
(or the default table) and are trivially changeable. **Not** "40 = 40%
trust" — the number is an ordinal position on a defined scale, nothing more.

### 5.4 Where dimensions come from

**Character-package-defined**, validated against the Core-provided schema
shape. Core does **not** hard-code `trust` or any KIRA relationship. Core MAY
ship a small *optional* common vocabulary (e.g. `trust`, `closeness`,
`tension`) that a package can adopt or ignore.

---

## 6. Psychology Semantics

Current shape: `PSYCHOLOGY`, key `dimension`, range `-100..100`, missing =
UNKNOWN.

### 6.1 Distinction from Relationship (verified against code)

- **RELATIONSHIP** = a directed state **toward another subject** — the key
  regex requires `subject.dimension`.
- **PSYCHOLOGY** = the character's **own internal current state** — the key
  regex is a bare `dimension`, no subject.

This matches the existing key formats exactly; adopt it as the definition.

### 6.2 Schema

Same per-dimension definition schema as §5.2 (minus the subject concept).
Same default bands as §5.3, overridable per dimension. `MISSING ≠ 0` applies
identically.

### 6.3 Where dimensions come from

**Controlled combination:** Core provides the schema and a small optional
common vocabulary (e.g. `stress`, `confidence`, `mood_valence`, `arousal`);
the **Character Package declares which dimensions it activates** and may add
its own. Runtime-created ad-hoc dimensions (today's free-string typing) are
an operator *testing* affordance, not the intended authoring path —
recommend package-declared + Core-schema-validated as the supported model.

---

## 7. Evolution Model

Current: state mutation is `OPERATOR_CONFIRMED` only. Do **not** jump to
unrestricted model-written state.

### 7.1 v1 mode (OD-MEM-EVO-03 = A): **structured / rule-produced `EvolutionCandidate` → validation → human approval → state mutation**

The candidate producer in v1 is a **deterministic rule**, never an LLM, and
never unrestricted model-written state. Fully-automatic (no-approval)
apply and an LLM proposer are both **deferred**. (Earlier draft phrasing
that labelled this "model-proposed" is corrected by §0.)

### 7.2 Flow

```
turn / event
  → EvolutionCandidate  (persisted, append-only, NEVER auto-applied)
       { trigger_ref, proposed_deltas:[(domain,key,delta,rationale)], proposer, status }
  → validation           (range: current+Σdelta ∈ [-100,100]; key format;
                           dimension declared by package; |delta| ≤ dimension.max_step)
  → human approve / reject
  → on approve: apply via EXISTING record_adjust, with a NEW source_kind
       EVOLUTION_APPROVED  (added to ACTIVE_SOURCE_KINDS)
```

Rejected candidates are retained for audit. Application produces an ordinary
`ADJUST` ledger event, so history shows the accumulation
(e.g. `20 → 25 → 30`) with no hidden accumulator.

### 7.3 Explicit answers

| Question | v1 answer |
|---|---|
| what may trigger a delta | a per-dimension `evolution_policy` **declared in the Character Package** (e.g. "sustained supportive user behavior over a turn window") — never a bare global rule |
| who proposes | a deterministic rule (`proposer = "deterministic_rule:<id>"`) in v1; an LLM proposer (`"model_v1"`) is deferred |
| who validates | Core (range / key / dimension / step-size checks) |
| who applies | operator approval → existing `record_adjust` path |
| range handling | reject if out of `[-100,100]`, **never clamp** (unchanged) |
| delta size | from the dimension definition (`default_step`, `max_step`) — justified per dimension, not magic |
| conflicting triggers, same turn | deltas per key are summed into one proposed candidate; validation rejects an out-of-range sum; operator sees the combined proposal |
| repeated events accumulate | each approved candidate = a separate `ADJUST` event; the ledger is the accumulator |

### 7.4 Where "compliment ⇒ trust +5" lives

In the **Character Package** (`evolution_policy` per dimension) — it is
character-specific and configurable. Core never defines it. Core validates
and applies within the schema's guardrails.

---

## 8. Behavioral Influence

### 8.1 Rendering model

```
numeric value
  → (Core)     semantic band + generic behavioral_interpretation text
  → (Package)  character-specific expression guidance for that band
  → (LLM)      dialogue produced within those constraints
```

### 8.2 Boundary

| Layer | Responsibility |
|---|---|
| **Core** | interpret (number → band) and deliver band + generic meaning; no character phrasing |
| **Character Package** | define how *this* character expresses `high trust` / `low trust` / `high stress` / … per band |
| **LLM / runtime** | produce wording within the delivered constraints |

Core must **not** invent KIRA's behavior. The generic
`behavioral_interpretation` in a dimension definition is a neutral
description ("high values indicate the character treats X as reliable"),
not dialogue.

### 8.3 Numeric value visibility in the provider prompt — **recommend C (both)**

Send **number + band**, e.g. `- andrey.trust: 72 (very_positive)`, keeping
the existing "не неизменный канон" footer.

- the **number** preserves exact auditability and byte-level
  reproducibility of a captured request (SELECTED/DELIVERED evidence);
- the **band** gives the model a stable interpretation so behavior does not
  drift on every ±1 change;
- raw-only (A) forces the model to invent a scale; band-only (B) discards
  audit precision.

---

## 9. Validation Plan

### 9.1 Memory tests (deterministic, no provider)

1. trivial/chitchat event is **not** eligible for consolidation;
2. a durable `USER_STATED` fact **is** eligible (after recurrence or
   explicit mark);
3. the same fact repeated does **not** create a second consolidated record
   (`seen_count` increments; `last_seen_seq` updates);
4. a corrected fact creates a new record with `supersedes` set; the prior
   record becomes `SUPERSEDED` (retained);
5. a `CHARACTER_UTTERANCE` (incl. a hallucination) is **never** eligible and
   never appears as factual memory;
6. a consolidated record is visible in a **new session in the same
   workspace**;
7. a different Clean Test workspace sees **none** of it (isolation);
8. working-context selection is **bounded** (≤ N events / char budget);
9. a consolidated record still lists all its `source_event_ids` after
   compression (provenance preserved).

### 9.2 Relationship behavioral test

Same character + package + prompt + memory + scene; vary only
`subject.trust` **LOW** vs **HIGH**. Expect a measurable directional
difference under a **pre-registered rubric** (e.g. warmth/hedging markers,
willingness to disclose, response stance) — **not** exact wording.

### 9.3 Psychology behavioral test

Same setup; vary only `stress` **LOW** vs **HIGH**. Expect a measurable
directional difference under a pre-registered rubric (e.g. terseness,
agitation markers, self-regulation language).

### 9.4 Live provider A/B — DESIGNED, NOT RUN

Hold input, package, memory, scene constant; vary exactly one of `trust` or
`stress` (one LOW run, one HIGH run). Evaluate whether the response moves in
the intended direction under the §9.2/§9.3 rubric. Small (2 calls per
dimension). **No provider calls in this task.**

---

## 10. Portability

A second character reuses the **same Core** with:

- its own **package-declared** Relationship dimension set (+ optional band
  overrides);
- its own **package-declared** Psychology dimension set;
- its own **per-band expression guidance** (§8.2);
- its own **`evolution_policy`** per dimension (§7.4).

Required Core code changes for character #2: **none** — Core only gains the
dimension-definition *schema* and the candidate/consolidation *framework*,
both fully parameterized by the package. No `if character == "kira"` anywhere,
consistent with today's capability-flag design.

---

## 11. Recommended V1 Implementation Boundary

### IMPLEMENT NEXT

- **Dimension-definition schema** (Core) + package-declared Relationship /
  Psychology dimension sets + validation.
- **Semantic bands** (Core default table + per-dimension override) and
  **prompt rendering** of `number + band + generic interpretation` in
  Grounded v2 (keep the existing footer).
- **Consolidated-memory store** (new, append-only, `source_event_ids`
  retained) with deterministic **eligibility**, **dedupe**, **supersede**,
  and **contradiction flags**.
- **MemoryPromotionCandidate** artifact + **human approval** → consolidated
  record.
- **EvolutionCandidate** artifact + validation + **human approval** +
  new `EVOLUTION_APPROVED` source kind; application reuses `record_adjust`.
- **Bounded working-context** selection for Grounded v2 (explicit N / char
  budget).
- The §9.1 memory tests and the §9.2 / §9.3 LOW-vs-HIGH behavioral tests.

### DEFER

- fully automatic (no-approval) evolution;
- per-dimension deterministic auto-apply rules (option A) — revisit after B;
- LLM salience scoring; LLM multi-event summarization;
- forgetting / decay / TTL;
- graph memory; embeddings / vector retrieval;
- autonomous long-term rewrite / self-editing memory;
- emotional-significance and privacy/sensitivity scoring;
- `MODEL_HYPOTHESIS` / model-proposed evolution (`proposer = "model_v1"`).

---

## 12. Owner Decisions Required

1. Approve the three-layer / two-store memory model (event log unchanged +
   new append-only consolidated store), or specify an alternative.
2. **[ACCEPTED — OD-MEM-EVO-03 = A]** v1 evolution = structured / rule-produced
   `EvolutionCandidate` + validation + human approval; no auto-apply, LLM
   proposer deferred.
3. Approve adding `EVOLUTION_APPROVED` (and, if consolidation writes state,
   `CONSOLIDATION_APPROVED`) to `ACTIVE_SOURCE_KINDS`.
4. Approve **dimension definitions living in the Character Package**
   (character-specific), with a Core-provided schema and only a *small
   optional* Core common vocabulary (no mandatory dimensions).
5. Approve the default band thresholds (`-60 / -20 / 20 / 60`) and the
   five band names, or specify alternatives.
6. Approve **numeric visibility = both number + band** in the provider
   prompt.
7. Ratify **MISSING ≠ 0** permanently, and `0` = explicit neutral only where
   a dimension's definition declares it.
8. Approve **deferring forgetting / decay entirely** for v1.
9. Approve **deterministic (no-LLM) candidate generation** for both
   consolidation and evolution in v1; LLM proposers deferred.
10. Decide whether v1 consolidation is **verbatim-only** (1 event → 1
    record) or may **deterministically merge** same-label events (refs still
    retained).
11. Set the **working-context bound** for Grounded v2 (max `USER_STATED`
    events and/or character budget).
12. Confirm behavioral tests may assert a **pre-registered rubric / measurable
    proxy** and a **direction**, not exact wording.
