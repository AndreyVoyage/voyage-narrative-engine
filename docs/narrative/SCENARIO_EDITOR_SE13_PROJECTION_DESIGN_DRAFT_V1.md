# SCENARIO_EDITOR_SE13_PROJECTION_DESIGN_DRAFT_V1

**Status:** `TECHNICAL_DRAFT / IMPLEMENTATION_CANDIDATE`
**Date:** 2026-10-02
**Slice:** SE-1.3 — Deterministic Card-to-OrderedASS projection
**Package:** `services/scenario_authoring/projection.py`
**Source authority:** `NARRATIVE_DECISIONS_v1.md` §18 (`OD-SE-AUTHORING-MODEL-01`), §19
(`OD-SE-STORAGE-CONTRACT-01`), `NARRATIVE_ROADMAP.md` §14.10,
`SCENARIO_EDITOR_SE11_IDENTITY_STORAGE_DESIGN_DRAFT_V1.md` §C/§D.

> This is a **technical implementation candidate for independent review**, not a
> ratified canonical contract. It introduces **no** new accepted-scene schema and
> **no** custom story runtime. It does not modify `scene_body/1.0`, `ass/0.2`,
> `vne_story_sequence/0.1`, the Ren'Py exporter, or `model.py` / `persistence.py`.

---

## 1. Purpose and non-goals

SE-1.3 provides a **pure, deterministic projection boundary** from the ratified
authoring model (`Project → Connected Cards → Slides → Content Items /
Utterances → Display Portions`) into the existing `SceneBody` contract, which the
existing `build_ordered_ass` then projects to `OrderedASS` (`ass/0.2`).

The projection only flattens the author's **explicit** content order and the
author's **explicit** Card connections. It never synthesizes a story graph and
never invents implicit story order.

Explicitly **out of scope** (later slices): Ren'Py export integration (SE-1.5),
portable ZIP packaging (SE-1.4), media-file copying/deduplication, PySide6 UI,
Character Lab import, AI-provider integration, and any gameplay/runtime redesign.

---

## 2. Projection API

Public surface (re-exported from `services/scenario_authoring`):

```python
project_scenes(project: Project, config: ProjectionConfig) -> Projection
```

- `ProjectionConfig` — the explicit scene map the Card model deliberately does not
  own (`scenes: Tuple[SceneMembership, ...]` in deterministic scene order, plus
  `supported_scene_transitions`).
- `SceneMembership` — `scene_id`, ordered `card_ids`, `location_id`,
  `content_rating`, optional `scene_title`. Scene-level facts the Card model does
  not own are supplied here (no change to the ratified SE-1.1 model).
- `Projection` — `scene_bodies: Tuple[SceneBody, ...]` (one per scene, in scene
  order), `scene_order`, `start_scene_id`, and `portion_manifests`.

Errors: `ProjectionError` (missing/inconsistent target or ambiguous continuation)
and `UnsupportedProjectionError` (no accepted representation; fail closed).

No filesystem I/O, no UI, no network, no mutation of the source `Project`.

---

## 3. Authoring → accepted mappings

| Authoring element | SceneBody / OrderedASS representation |
|---|---|
| Utterance, 0 speakers | `TextEntry` `NARRATIVE`, `text = utterance.whole_text()` |
| Utterance, 1 speaker | `TextEntry` `DIALOGUE`, `character_id = speaker_ids[0]`, `text = whole_text()` |
| AuthoredChoice | `ChoiceEntry`; each option → explicit `ChoiceTarget` |
| Slide.background (asset_id) | `VisualChangeEvent` `SET` (leading entry of the slide) |
| Card linear connection | explicit `next_target` on the card's **last** entry |
| Card terminal (no connection) | explicit `next_target = END` |
| cross-scene connection | `SCENE` target (start card of the target scene only) |

The **complete Utterance text** is always the single authoritative value; Display
Portions are offsets into it and are never substituted for it.

---

## 4. Scene / Card membership rules

- A Card is an independent authoring container and is **not** automatically one
  scene. One accepted scene may contain multiple Cards.
- `ProjectionConfig.scenes` is the explicit, ordered scene map. Every project Card
  must appear in **exactly one** scene (full coverage, no duplicate membership).
- Scene order is deterministic (`ProjectionConfig.scenes` order). Within a scene,
  Cards are flattened in their `card_ids` order; within a Card, slides in order,
  background before the slide's items, items in order.

---

## 5. Connection resolution

`CardConnection` is the author's explicit edge. Two kinds are recognized:

- **Linear connection** (`choice_id is None`): at most one per Card; it names the
  card's single continuation.
- **Branch connection** (`choice_id` set): a destination for one authored choice.

Resolution rules (fail closed):

- A linear continuation within a scene must target the **immediately next** Card
  in scene order; any other same-scene target is rejected (implicit story order
  is not invented). It becomes `next_target = ENTRY(next_card_first_entry)`.
- A linear continuation across scenes must target the **start card** of the target
  scene and must be listed in `supported_scene_transitions`; it becomes
  `next_target = SCENE(target_scene)`.
- A choice option must carry `target_connection_id` resolving to a branch
  connection whose `choice_id` equals the choice; it becomes an `ENTRY` target
  (same scene) or `SCENE` target (cross-scene start card).
- A cross-scene target that is **not** the start card of the target scene is an
  unsupported cross-scene ENTRY target and is rejected.

---

## 6. Start Card handling

- `start_card_id` maps to exactly one scene (`start_scene_id`).
- `start_card_id` must be the **first** Card of its scene. A middle-of-scene Card
  is never treated as a valid start merely because its `scene_id` is known.

---

## 7. Deterministic validation

The same validated `Project` + `ProjectionConfig` always yields the same result.
The projection performs, in order:

1. `validate_project` (cross-object integrity) — dangling connections/options fail.
2. Scene-map resolution against the real Project Cards.
3. `start_card_id` start-position validation.
4. Per-Card structural analysis (entry ids are stable, derived from
   `card_id.slide_id.item_id` — never a list index).
5. Per-scene entry building + target resolution.
6. `validate_acceptance_complete` on every projected `SceneBody` (fail closed).

Entry ids are deterministic and stable: `"{card_id}.{slide_id}.{item_id}"` for
content items and `"{card_id}.{slide_id}.@bg"` for slide backgrounds.

---

## 8. Supported content

- narrative text (`Utterance`, 0 speakers);
- dialogue `Utterance` (exactly 1 speaker);
- authored reader choices (`AuthoredChoice` → `ChoiceEntry`);
- supported visual/background changes (`Slide.background` with `asset_id`);
- explicit linear continuation (Card linear connection);
- supported branch destinations (choice options);
- explicit ending (terminal Card → `next_target = END`).

---

## 9. Unsupported content (explicit error, never silent)

- `Utterance` with 2+ speakers (group-speaker presentation);
- `ContentItem` `MEDIA` (no media-type discriminator; audio/video unsupported);
- `Slide.background` with `relative_path` (no `asset_id`);
- content after a `CHOICE` item within one Card;
- a choice option without a resolvable branch connection;
- a branch connection not referenced by any option;
- a Card with no projectable content;
- multiple linear connections on one Card;
- a linear continuation to a non-adjacent same-scene Card;
- a cross-scene target that is not the target scene's start card;
- a cross-scene transition not declared in `supported_scene_transitions`.

Each of these raises `UnsupportedProjectionError` (or `ProjectionError`) and the
source `Project` is preserved unchanged.

---

## 10. Display Portion acceptance boundary

- The whole Utterance text is always projected into the `TextEntry` (recoverable).
- Per-portion segmentation, stable `portion_id`, order, and speaker
  portrait/emotion overrides are **not** representable in `SceneBody`/`ass/0.2`.
- They are preserved in a deterministic, hash-verifiable
  `DisplayPortionManifest` (`schema_id
  scenario_authoring_projection_display_portions/0.1`) sidecar in the `Projection`
  result. Its `content_hash` mirrors the repo canonical-JSON/SHA-256 convention.

**Boundary (Owner-gated alternatives, not silently ratified here):**

1. **A.** Keep the portion manifest as an out-of-band sidecar (this candidate's
   behavior) — no change to `ass/0.2`.
2. **B.** Later extend `ass/0.2` with an optional, hash-pinned portion record —
   requires explicit Owner authorization; **not done here**.
3. **C.** Introduce a new `ass/0.3` — **not authorized** and **not done here**.

The manifest is a **technical candidate** only: it is not published as accepted
truth, is not an `ass/0.2` extension, and no mutable/unverified sidecar is
presented as accepted publication truth. Immutable acceptance linkage
(`AcceptanceLink`) is **not** operational for this candidate and is **not**
claimed to be.

---

## 11. Compatibility with ASS / StorySequence

- Output `SceneBody` objects are exactly `scene_body/1.0` and pass
  `validate_acceptance_complete`; each can be fed to the existing
  `build_ordered_ass` to produce a valid `ass/0.2` (round-trips through
  `serialize_ordered_ass` / `parse_ordered_ass`).
- `Projection.scene_order` + `Projection.start_scene_id` are the exact inputs a
  later step can feed into `StorySequence` (`vne_story_sequence/0.1`); the
  projection itself does not build a StorySequence or a second graph.
- No canonical contract is modified.

---

## 12. Limitations and deferred SE-1.5 work

- No reachability/cycle analysis (consistent with `SceneBody` acceptance): a Card
  laid out but only reachable via a branch is not treated as "lost" — its content
  is still projected into the ordered flow.
- Media bytes are never read/copied; `asset_id` is validated syntactically only.
- Named emotion catalog remains unratified (kept as an opaque string).
- Ren'Py export of accepted portions and authored connections is **SE-1.5** and is
  not implemented here.

