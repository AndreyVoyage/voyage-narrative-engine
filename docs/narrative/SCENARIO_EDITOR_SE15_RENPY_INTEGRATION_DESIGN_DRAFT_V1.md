# SCENARIO_EDITOR_SE15_RENPY_INTEGRATION_DESIGN_DRAFT_V1

**Status:** `TECHNICAL_DRAFT / IMPLEMENTATION_CANDIDATE`
**Date:** 2026-10-02
**Slice:** SE-1.5 — Ren'Py export integration bridge
**Package:** `services/scenario_authoring/renpy_integration.py`
**Source authority:** `00_DOCUMENT_INDEX.md` §7b (ASS / OrderedASS / Story Sequence /
Ren'Py exporter), `NARRATIVE_DECISIONS_v1.md` §18/§19, `NARRATIVE_ROADMAP.md` §14,
`SCENARIO_EDITOR_SE13_PROJECTION_DESIGN_DRAFT_V1.md`.

> This is a **technical implementation candidate for independent review**, not a
> ratified canonical contract. It introduces **no** new accepted-scene schema,
> **no** custom story runtime, and **no** independent Ren'Py exporter. It only
> connects the existing SE-1.3 projection to the existing NARRATIVE Ren'Py
> exporter. It does **not** ratify `DisplayPortionManifest` acceptance linkage,
> does **not** publish accepted truth, and does **not** write files.

---

## 1. Purpose and non-goals

SE-1.5 connects the Scenario Editor authoring pipeline to the EXISTING Ren'Py
export infrastructure, reusing engine-native functionality end to end.

Explicitly **out of scope** (later slices / not authorized): visual UI
(PySide6), canonical publication to `novel/game/`, Ren'Py SDK execution,
Character Lab import, media-byte copying/deduplication, and any gameplay/runtime
redesign.

---

## 2. Verified integration path

The bridge is a pure pass-through over the already-ratified chain:

```
Project
  -> validate_project(project)                          # existing integrity gate
  -> project_scenes(project, ProjectionConfig)          # SE-1.3 projection
  -> SceneBody (scene_body/1.0)
  -> build_ordered_ass(...)                             # existing acceptance -> ass/0.2
  -> OrderedASS
  -> StorySequence(scene_order, start_scene_id)         # vne_story_sequence/0.1
  -> build_ordered_project_candidate(...)               # existing Ren'Py exporter
  -> OrderedProjectCandidate (.rpy source)
```

No logic in this chain is reimplemented. The source `Project` is never mutated
(all authoring entities are frozen).

---

## 3. Integration API

```python
export_project_to_renpy(
    project: Project,
    config: ProjectionConfig,
    *,
    reading_mode: str,
    character_symbols: Mapping[str, str],
    registry_path: Path,
    repo_root: Path,
) -> RenpyExportResult
```

`RenpyExportResult` (frozen) exposes:

- `candidate` — the existing `OrderedProjectCandidate` (real exporter output);
- `ordered_ass_scenes` — the accepted `OrderedASS` scenes built by
  `build_ordered_ass`;
- `story_sequence` — the `StorySequence` (scene order + start scene);
- `portion_manifests` — the SE-1.3 `DisplayPortionManifest` technical-candidate
  sidecars (carried, not exported);
- `source` / `source_sha256` / `scene_ids` / `ass_ids` / `reading_mode` —
  convenience accessors over the candidate.

The bridge derives deterministic provenance per scene: `ass_id = ass_<scene_id>`,
`version = 1`, `source_ref = <project_id>/<scene_id>`,
`source_hash = compute_source_hash(SceneBody.to_dict())`.

Failures: bridge-level input/integrity violations raise
`ScenarioAuthoringValidationError`; exporter-level failures (unsupported reading
mode, missing character symbol, unresolved media, etc.) propagate unchanged from
the existing exporter, so the real exporter remains the authority.

---

## 4. Exporter input contract (actual, verified from source)

`tools/vne_to_renpy.build_ordered_project_candidate` accepts:

- `scenes: tuple[OrderedASS, ...]` — non-empty, unique `scene_id`/`ass_id`,
  positive `version`, 64-hex `content_hash`;
- `reading_mode: Literal["classic_vn", "psychological", "mind_reading"]`;
- `character_symbols: Mapping[str, str]` — `character_id -> Ren'Py Character
  symbol` (valid identifier, non-reserved);
- `registry_path: Path`, `repo_root: Path` — delegated to the existing
  `resolve_ordered_assets_for_renpy`;
- `story_sequence: Optional[StorySequence]` — when present, drives scene order
  and emits the `vne_story_start` entry label (exact batch coverage required).

The renderer consumes only `OrderedASS` (never `SceneBody`, legacy `ASS`, dict,
or duck-typed objects). The bridge supplies all of the above.

---

## 5. Supported authoring -> exported mappings

| Authoring element | OrderedASS / Ren'Py output |
|---|---|
| Utterance, 0 speakers | `TextEntry` NARRATIVE -> `narrator "..."` |
| Utterance, 1 speaker | `TextEntry` DIALOGUE -> `<symbol> "..."` |
| AuthoredChoice | `ChoiceEntry` -> `menu:` + `jump <target>` per option |
| Slide.background (asset_id) | `VisualChangeEvent` SET -> `show <image> as vne_scene_visual` |
| Card linear connection | explicit `next_target` -> `jump <entry/scene/end label>` |
| Card terminal (no connection) | `next_target = END` -> `jump <scene end label>` |
| Cross-scene connection | `SCENE` target -> `jump <scene start label>` |

The complete Utterance text is always the single authoritative value.

---

## 6. Choice and target behavior

- Each `AuthoredChoice` option resolves to a `ChoiceTarget` via its
  `target_connection_id`.
- Same-scene branch -> `ENTRY` target (first entry of the target card).
- Cross-scene branch -> `SCENE` target (only the target scene's start card), and
  only when the transition is declared in `supported_scene_transitions`.
- Linear continuation -> `next_target` on the card's last entry.
- All targets are exported as Ren'Py `jump` statements to deterministic
  generated labels (`vne_scene_<scene>_start`, `vne_scene_<scene>_entry_<id>`,
  `vne_scene_<scene>_end`).

---

## 7. Utterance / Display Portion handling (critical gate)

- The **complete** Utterance text is always projected and exported; the
  analytical/AI pipeline keeps the full authoritative value.
- Display Portions are **offsets into** the authoritative text, never a
  substitute. They are preserved in the `DisplayPortionManifest` technical
  candidate and carried through on `RenpyExportResult.portion_manifests`.
- Per-portion segmentation, per-portion speaker/portrait/emotion selection, and
  reader-controlled space/continue advancement are **not representable** in
  `scene_body/1.0`, `ass/0.2`, or the existing Ren'Py exporter. The bridge does
  **not** merge portions into one visible operation and claim full fidelity, and
  does **not** silently discard them: it reports the gap explicitly.

**Boundary (Owner-gated, not ratified here):** `ass/0.2` is unchanged;
`ass/0.3` is not invented; no sidecar is treated as accepted truth.

---

## 8. Media-resolution boundary

- Backgrounds must carry an `asset_id` (a `relative_path` background is
  unsupported and fails during projection).
- The existing `resolve_ordered_assets_for_renpy` resolves `asset_id` against the
  Visual Asset Registry (`registry_path`) and `repo_root`, performing physical /
  integrity / hash checks before emitting any `show` statement.
- Missing / unresolved media fails closed (`OrderedAssetResolutionError`); media
  never disappears silently.

---

## 9. Acceptance boundary

- Acceptance is `build_ordered_ass` (SceneBody -> ass/0.2), which fails closed if
  a projected body is not acceptance-complete.
- `AcceptanceLink` is **not** operational for this candidate and is **not**
  claimed. No formal acceptance/publication is performed; the bridge returns a
  candidate only. Canonical publication (`publish_ordered_project_candidate`)
  is a later, separately-authorized step.

---

## 10. Tested output

Focused tests `tests/unit/test_scenario_authoring_renpy_integration.py` cover
T01-T13 plus one real multi-Card vertical example (two scenes, background,
narration, dialogue, branch choice, linear continuation, cross-scene
transition), asserting actual generated `.rpy` source content and navigation
rather than only successful function returns.

---

## 11. Unresolved acceptance requirements

1. `DisplayPortionManifest` acceptance linkage remains unratified (SE-1.3
   technical candidate); per-portion Ren'Py presentation is not representable
   without an Owner-authorized `ass/0.2` extension or `ass/0.3`.
2. `character_symbols` derivation (character_id -> Ren'Py symbol) is caller-owned;
   a future UI layer must supply it explicitly.

---

## 12. Known limitations

- No Ren'Py SDK execution or lint is performed by this slice (SDK unavailable in
  this environment; reported, not installed).
- No canonical publication to `novel/game/ordered_ass_generated.rpy`.
- No media-byte copying or deduplication; only `asset_id` references resolve.
- Named emotion catalog remains unratified (opaque string).

---

## 13. Boundary before visual UI development

The bridge is UI-independent and pure. Visual UI (PySide6) must consume
`export_project_to_renpy` and the existing exporter/publication pipeline; it is
not started by this slice and must be authorized separately.
