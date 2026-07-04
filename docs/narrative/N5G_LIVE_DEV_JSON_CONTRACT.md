# N5G — Live/Dev JSON Contract

> **Status:** CONTRACT + read-only mock tooling (N5H) implemented.
> **Implementation:** PARTIAL — `tools/live_dev_json_loader.py` implements read-path inspection, validation reuse, address mapping, state mapping summary, and reload-safety classification. The full live/dev runtime (RenPy loader, write-back, hot-reload, Dev-edit) is NOT IMPLEMENTED.
> **Date:** 2026-06-27
> **Baseline:** `4f13f3b80e4d4be458b049be4fd15bed502636e9`
> **N5I sync:** mock/dev loader status added.
> **Related docs:** `N5F_HYBRID_JSON_PATH_DECISION.md`, `NARRATIVE_ROADMAP.md`, `STORY_RUNTIME_CONTRACT.md`, `NARRATIVE_ARCHITECTURE.md`

## Context

N5F adopted the **Hybrid JSON path**:

- `scenarios/SCENARIO_*.v2.json` remains the canonical source of truth.
- Generate-ahead `.rpy` remains the canonical MVP/release playable path.
- Live JSON loading is a scoped future dev/edit/hot-reload foundation.
- Dev-edit must not begin until this contract is designed.

The current proven vertical slice is:

```text
SC_017.v2.json
  -> validate-v2
  -> story runtime
  -> preview / PX
  -> renpy-playable-v2
  -> novel/game/scenes_v2_generated.rpy
  -> reachable dev/test launcher
  -> static RenPy validation
  -> mock/dev loader inspect/reload-check (N5H)
```

N5H added external read-only mock/dev loader tooling (`tools/live_dev_json_loader.py`, `tests/test_live_dev_json_loader.py`, `rn_workflow.py live-dev-inspect`, `rn_workflow.py live-dev-reload-check`).

Neither RenPy live JSON loading, write-back, hot-reload, nor Dev-edit is implemented.

## Scope

The live/dev JSON path is **dev-only** infrastructure.

- It is **not** the release path.
- It does **not** replace the generate-ahead `.rpy` path.
- It does **not** replace the hand-authored SC_017 path.
- It is a future foundation for Dev-edit and hot-reload.
- It must **fail closed** and keep the release/player path safe.

## Read path

- **Primary dev read source:** `scenarios/SCENARIO_*.v2.json`.
- A future isolated dev export or cache directory may be introduced for testing without touching authoring files.
- **Release builds must not depend on direct live JSON reads.**
- The generated `.rpy` artifact remains the release fallback.

## Validation boundary

- Full schema validation must run **outside RenPy** before a scene is handed to the live/dev loader.
- The RenPy-side loader may run only lightweight structural checks (e.g., required keys, label collisions, known scene id).
- **Invalid JSON must refuse to load the dev scene.**
- **Invalid JSON must not break the existing generated release/playable path.**
- Validation errors must be visible to the developer and must not be silently ignored.

## Runtime state mapping

The Python `story_runtime_v2.py` state maps to generated RenPy state as follows:

| Python runtime state | Generated RenPy state | Notes |
|---|---|---|
| `completed_scenes` | `v2_completed_scenes` | set of completion flags |
| `flags` | `v2_flags` | set of active flags |
| `character_states` | `v2_levels` | character id -> state string |
| `relationships` | `v2_relationships` | pair id -> relationship string |
| `settings` | future optional `v2_settings` | not materialized in generated `.rpy` today |
| `history` | future optional `v2_history` | not materialized in generated `.rpy` today |

Current gaps:

- Generated RenPy state does not materialize `settings`.
- Generated RenPy state does not materialize `history`.
- The Python runtime uses full state model; the generated RenPy artifact carries only the minimal playable state needed for the SC_017 proof.

## Beat and branch mapping

The live/dev path address model is:

- `scene_id`
- `choice_point id`
- `branch id`
- `beat_id`

Rules:

- `beat_id` is the stable edit and resume anchor.
- The current generated RenPy labels are scene/branch based (e.g., `sc_017_v2_1a`).
- The future live/dev path needs beat-level addressing and resume.
- Branch choice must be resumable after a safe text-only reload.

## Write-back boundary

Safe editable fields (text-only):

- `narration`
- `speech`
- `action`
- `thought`
- `emotion` (if the schema permits it as a textual/metadata field)

Forbidden or high-risk fields:

- `beat_id`
- `type`
- `speaker`
- `pov`
- `thought_visibility`
- `option_text`
- `effects`
- `next`
- `prerequisites`
- `flags_required`
- `completion_flag`
- branch structure
- choice point ids
- relationship/effect mutations

Rules:

- Generated `.rpy` must never become the source of truth.
- Manual edits to generated `.rpy` are not canonical and may be overwritten on regeneration.
- JSON edits must validate before they become usable.

## Hot-reload boundary

Safe reload cases:

- Text-only changes within existing `beat_id`s.
- No branch structure change.
- No effect, prerequisite, or flag change.
- No id change.

Unsafe reload cases:

- Added or removed beats.
- Changed `beat_id`s.
- Changed branch ids.
- Changed effects.
- Changed prerequisites.
- Changed completion flags.
- Changed choice structure.

Unsafe reload requires:

- Scene restart, or
- Regeneration of `.rpy`, or
- Explicit future migration handling.

## Failure behavior

- The dev loader must **fail closed**.
- The release path remains the generated `.rpy`.
- Invalid JSON must not break the player release path.
- A loader failure must not mutate RenPy state.
- A loader failure must show a developer-visible diagnostic.

## Non-goals

- Live JSON loader implementation is **not** part of N5G.
- Dev-edit implementation is **not** part of N5G.
- Hot-reload implementation is **not** part of N5G.
- Schema changes are **not** part of N5G.
- Scenario changes are **not** part of N5G.
- Mass migration of SC_003–SC_027 is **not** part of N5G.
- Character Aside, Voice Layer, and LLM Director remain future tracks.

## Consequences

- N5H completed the external read-only mock/dev loader tooling. It implements parts of this contract at the Python-tooling level and is **not** a RenPy runtime loader.
- Dev-edit remains blocked until the full live/dev runtime foundation (live JSON read inside RenPy or equivalent runtime, write-back, hot-reload) is implemented.
- The next possible phase after N5H is further planning/implementation of the full live/dev JSON runtime, not immediate Dev-edit.
- The generate-ahead release path remains stable and validated.
