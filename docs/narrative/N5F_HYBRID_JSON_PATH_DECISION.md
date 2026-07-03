# N5F — Hybrid JSON Path Architecture Decision

> **Status:** DECISION RECORDED — docs-only, no code implemented.
> **Date:** 2026-06-27
> **Baseline:** `b53a0d1dca3e33cf1198ae0da3b2b866c8ea6a8f`
> **Related docs:** `NARRATIVE_ROADMAP.md`, `STORY_RUNTIME_CONTRACT.md`, `NARRATIVE_ARCHITECTURE.md`

## Context

N5A–N5D proved a complete vertical slice:

```text
SC_017.v2.json
  -> validate-v2
  -> story runtime
  -> preview / PX
  -> renpy-playable-v2
  -> novel/game/scenes_v2_generated.rpy
  -> reachable dev/test launcher
  -> static RenPy validation
```

The open question before Dev-edit was whether to switch RenPy to live JSON loading now or to keep the proven generate-ahead path as the MVP playable path.

## Decision

Adopt the **Hybrid JSON path**:

1. `scenarios/SCENARIO_*.v2.json` remains the **canonical source of truth**.
2. **Generate-ahead static `.rpy`** remains the **canonical MVP/release playable path**.
3. **Live JSON loading** is a **scoped future dev/edit/hot-reload foundation**, not an immediate replacement for the generate-ahead path.
4. Generated `.rpy` artifacts are **deterministic derived artifacts** and must not be manually edited.

## Current proven path

- **N5A** generated playable bridge: COMPLETE.
- **N5B** static generated-scene validation: COMPLETE.
- **N5D** reachable opt-in launcher: COMPLETE.
- SC_017 V2 is reachable via the dev/test menu item `SC_017 — V2 JSON-generated proof (dev/test)` → `jump sc_017_v2_start`.
- The hand-authored SC_017 path (`SC_017 — Сергей пишет снова` → `jump sc_017_start`) is preserved.
- The generated V2 scene does **not** replace the hand-authored `sc_017_start` path.

## Why not big-bang live JSON now

Live JSON loading inside RenPy is architecturally desirable but higher-risk. It requires:

- a RenPy-side JSON loader with packaging/distribution rules;
- a validation boundary at load time;
- a runtime state model mapping Python `player_state` to RenPy state;
- `beat_id`-level mapping and pause/resume semantics;
- safe write-back and hot-reload boundaries.

Switching the player release to this before it is mature would destabilize the already-proven generate-ahead path.

## Future live/dev JSON contract (minimum)

Before Dev-edit begins, design a scoped live/dev JSON contract covering:

- **Read path:** where JSON files are loaded from at runtime/dev time.
- **Validation boundary:** when and how schema validation runs.
- **State model:** how `story_runtime_v2` `player_state` maps to RenPy state.
- **beat_id mapping:** how a beat maps to a UI/edit target and resume point.
- **Write-back boundary:** only textual fields (`speech`/`action`/`thought`/`narration`/`emotion`) may be edited safely.
- **Hot-reload boundary:** what can reload without restart and how position is restored.
- **Source/generated separation:** JSON is the source; `.rpy` is derived; manual edits to `.rpy` are not preserved.
- **Failure behavior:** invalid JSON must fail safely without breaking the generate-ahead release path.

## Non-goals

- Live JSON loading is **not implemented** now.
- Dev-edit / hot-reload / write-back are **not implemented** now.
- Character Aside / Voice Layer / LLM Director remain N6 / future tracks.
- Mass migration of SC_003–SC_027 is **not done**.

## Consequences

- `NARRATIVE_ROADMAP.md` adds N5F and keeps N5-Dev after the live/dev JSON contract is designed.
- `STORY_RUNTIME_CONTRACT.md` distinguishes offline Python runtime, generated RenPy runtime, and future live/dev JSON runtime.
- `NARRATIVE_ARCHITECTURE.md` explicitly documents the generate-ahead MVP path and the deferred live/dev JSON path.

## Next planning step

Design the scoped live/dev JSON contract as a separate docs/branch task before any Dev-edit implementation.
