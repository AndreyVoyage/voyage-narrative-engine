# SCENARIO_CHARACTER_LIBRARY_AND_MULTI_ASSISTANT_V1

**Date:** 2026-10-01
**Type:** OWNER PRODUCT DESIGN ADDENDUM
**Status:** `OWNER_DISCUSSION_AGREED / AWAITING_CANONICAL_DOC_SYNC`
**Product:** Voyage Scenario Editor

**Purpose.** Record additional Owner-agreed Scenario Editor requirements that extend the product design
recorded in `SCENARIO_EDITOR_PRODUCT_DESIGN_DECISIONS_V1.md` and the corrective realignment in
`NARRATIVE_ROADMAP.md` §14.9.

> **This is a product-design transcription from the Owner handoff, not a newly ratified technical schema.**
> It does **not** create a second master roadmap, does **not** ratify a Character Library schema, does
> **not** ratify an AI provider contract, and does **not** authorize implementation.

---

## A. Unified Character Library

Scenario Editor has **one** project-level Character Library.

A character can be added through:

- **METHOD A:** Import from Character Lab.
- **METHOD B:** Manual creation inside Scenario Editor.

Both methods lead to a character available in the **same** project Character Library.

- Character Lab must **not** be required for manually creating a character in Scenario.
- Provenance and origin information are preserved.
- Importing a character must **not** automatically place that character inside the literary narrative.

## B. Distinct Character Concepts

Keep conceptually separate:

- **CHARACTER** — the project character.
- **CHARACTER MEDIA LIBRARY** — the character's portraits, expressions, references, photos, short
  videos and other media.
- **CHARACTER AI ASSISTANT** — an **OPTIONAL** AI-enabled capability associated with a character.

- A character may exist **without** AI.
- A character may be used only as a writing assistant, only as a participant in the work, in both roles
  through explicit author action, or remain unused.
- Importing `.vchar` must **not** automatically activate an external AI-provider connection.

## C. Character Media Library

Each character has a logical media library with:

- default avatar / primary portrait;
- additional portraits;
- expression images;
- live portraits (short videos);
- appearance references;
- additional photos and videos.

- The application manages actual file placement; the writer must **not** manually maintain Windows
  folders.
- The writer may add media to imported and manually created characters alike.
- Media ownership options: `PROJECT_LOCAL` / `SCENARIO_SHARED_LIBRARY` — the author chooses the
  appropriate scope.

When a speaker is assigned to an utterance:

- insert the default portrait when available;
- clicking the portrait opens that character's available media gallery;
- allow selection of another portrait/expression or optional live portrait;
- preserve the original media bytes;
- fit media non-destructively while maintaining aspect ratio;
- use the default portrait when no special expression was selected.

> Do **not** invent a fallback for missing default portraits without a separate design decision.

## D. Group Utterances

- One authored utterance may have multiple speakers.
- Each speaker may have an independent portrait and expression.
- The utterance itself contains **one** shared text.
- Display portraits side by side in a configurable grid.
- Do **not** physically stitch source photographs into a combined permanent image.

## E. Optional AI Configuration

- Manually created characters may acquire AI capability later.
- Multiple AI-enabled characters may use the same technical provider/model while preserving:
  - separate character identities;
  - separate character context;
  - individual writing behavior.
- Do **not** embed API keys or provider secrets in the portable Scenario project.
- Do **not** infer that the Character Lab package contains active provider credentials.

## F. Multi-Assistant Dialogue Workshop

Several AI-enabled characters must be available simultaneously in the same Dialogue Workshop. Other
characters may remain manual-only.

The writer:

1. Selects the current speaker.
2. Writes a line or requests AI assistance.
3. Edits the proposed text.
4. Chooses one or multiple recipients.
5. Explicitly sends the accepted line.
6. Receives separate draft reactions.
7. Reviews, edits and accepts selected responses.
8. Optionally forwards accepted material to another participant.

- No assistant needs to be disconnected merely to select another assistant.
- Unaccepted AI drafts must **never** automatically:
  - become part of the work;
  - become accepted events;
  - enter another character's accepted conversation context as if they had occurred.

## G. Multiple Recipient Modes

Support the conceptual requirement for:

- **INDEPENDENT REACTIONS:** one accepted utterance is sent to several selected assistants, each
  producing its own response.
- **SEQUENTIAL REACTIONS:** the writer accepts one response before passing the updated conversation to
  the next participant.

- Independent reactions as the default remain **RECOMMENDED**, **NOT OWNER-RATIFIED**.
- Do **not** silently freeze that default in a technical contract.
- No autonomous unlimited assistant-to-assistant conversation loop is required for 1.0.

## H. Utterance vs Display Portions

Preserve:

- **DW-01:** a long authored utterance may be split into reader-facing display portions at any editing
  stage.
- **DW-02:** portrait and expression can change per portion, inheriting the previous portion's emotion
  by default.
- **DW-03:** two synchronized Workshop presentations: Messenger and literary Play Script.

- An AI recipient receives the **COMPLETE** current author-accepted utterance with necessary context,
  **not** an arbitrary isolated display portion.
- Display portions exist for reader-facing Space-key progression.
- Do **not** fragment the semantic utterance merely because it is shown in several portions.

## I. Product and Storage Boundaries

- The imported character is usable without Character Lab running.
- Scenario-local media additions must **not** silently mutate the source Character Lab canon.
- The complete portable Scenario project must contain its necessary character data and media.
- Provider secrets must be excluded from portable project files.
- The writer always controls final literary acceptance.
- No new gameplay runtime or automatic narrative interpretation is required.

---

## Character Lab Export — Factual Boundary (evidence/status note)

> This is a concise evidence/status note, **not** a new Character Lab implementation contract.

Producer baseline reported by Character Lab:

- **Character Lab:** `fe6149a3ee80755a41963f98a93a17c88460a2fb`
- **VCP:** `ccade9e0ef943f63fec703b7ed5b436d7520324a`

Current portable format: **`.vchar` Container V1 / VCP Package V1**.

Six mandatory semantic domains:

- `core_identity`
- `psychology`
- `speech`
- `relationships`
- `visual_identity`
- `interaction_boundaries`

Optional: `intimacy`.

Current published Character Media V1:

- `PNG`
- `JPEG`
- `STATIC WEBP`

- **Primary Portrait:** optional, `0..1`.
- **Published Reference Library and Gallery images:** available when actually included.
- The exact package content is determined by its manifest and published AssetRefs.
- **MOTION** is a **STATIC** reference-image category.
- **Video/live portrait export from Character Lab:** `NOT IMPLEMENTED` in current Character Media V1.
- **Standardized named emotion catalog:** `NOT CONFIRMED`.

Therefore:

- Video and live portrait support remains a **Scenario PRODUCT REQUIREMENT**, not an already
  implemented Character Lab export capability.
- Use existing verified VCP contracts and readers during future Scenario import implementation.
- Do **not** invent a new export format.