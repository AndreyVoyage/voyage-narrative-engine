# React Character Lab Foundation v1

A new React + TypeScript client foundation at `apps/character_lab_react/`,
built on top of the already-committed `services/character_core/contract.py`
boundary. The existing vanilla Character Lab
(`services/character_lab/web/**`) is untouched and remains the operational
UI; this is foundation work for a future replacement, not a replacement
itself.

## Architecture this slice establishes

```
shared design primitives  (styles/, components/primitives/)
        v
character UI components   (components/character/: ChatPanel,
                            CharacterIdentityCard, SceneForm)
        v
Character Lab developer UI (components/devtools/: MemoryTable,
                            RuntimeStateGroups, TurnDebuggerPanel)
```

Character Lab is a developer/testing tool, not the future consumer Character
App. Memory Inspector, Runtime State, and Turn Debugger are explicitly
"developer/debug UI" (`components/devtools/`, `tier: "debug"` in
`navigation/navigation.ts`, styled with a distinct debug accent color) — kept
structurally separate from `components/character/`, so a future consumer
Character App can reuse the character-facing tier without inheriting
debugging tools. `features/*` is the only layer that composes both tiers per
navigation destination.

## Transport-neutral client contract

`src/client/characterClient.ts` (`CharacterClient`) and
`src/client/characterDebugClient.ts` (`CharacterDebugClient`) are the
TypeScript mirror of the committed `CharacterService` /
`CharacterDebugService` Python contract — same DTO shapes (camelCased), same
method surface, same explicit-workspace-ownership model
(`listWorkspaces` / `getWorkspace` / `createTestWorkspace` before
`createSession(..., workspaceId)` — never a silently-created workspace), same
scope split (`getMemory(workspaceId)` / `getRuntimeState(workspaceId)` are
workspace-scoped; `getScene` / `setScene` / `clearScene` are session-scoped).
No URL, `fetch`, HTTP status code, header, or REST path appears anywhere in
either interface — no transport is chosen in this slice.

`SessionPurpose` recognizes `TESTING` / `AUTHORING` / `GAME_RUNTIME` /
`COMPANION`; only `TESTING` is in `SUPPORTED_SESSION_PURPOSES`, and
`MockCharacterClient.createSession` throws
`SessionPurposeNotImplementedError` for the other three rather than mapping
them onto TESTING.

`MockCharacterClient` / `MockCharacterDebugClient`
(`src/mocks/`) are in-memory, deterministic implementations used so the UI
can be built and exercised before any transport is chosen. Their fixture
data (`src/mocks/mockData.ts`) is synthesized and clearly fake — no field is
copied from or derived from the real Accepted KIRA package
(`accepted/kira/source_candidate.json`); the mock package hash and package id
are obviously-fake placeholder strings, never the real acceptance hash.

## Design foundation

Plain CSS custom properties (`src/styles/tokens.css`) for spacing, radius,
typography scale, surface hierarchy, borders, and interactive states — no
Tailwind/Bootstrap/Material/shadcn/Radix. Page-level sizing (sidebar width,
inspector width, topbar height) lives ONLY in `styles/layout.css`'s
`.clab-app-shell*` rules and the `AppShell` component; feature components
compose `Panel` / `Stack` / `Inline` / `Card` / `FormGrid` /
`DataTableShell` / `EmptyState` and never hard-code a page-level dimension,
so a new form field or table row cannot break the overall layout.
`DataTableShell` specifically scrolls only horizontally and always grows
vertically with row count — the structural fix for the vanilla Character
Lab's earlier "current-state table collapses to a clipped sliver" defect;
nothing built on this shell can reproduce that bug.

Desktop-first three-region `AppShell` (sidebar / main / inspector), degrading
at two breakpoints: the inspector becomes a collapsible drawer at medium
width (≤1180px), and the sidebar becomes a collapsible drawer at narrow width
(≤820px) — the main content column never forces horizontal page overflow at
any width.

## App state

A single `useReducer` + one `React.Context` (`src/app/AppState.tsx`) — no
Redux/Zustand/MobX. Feature views (`src/features/*`) hold their own
feature-local `useState` for data fetched from the client (memory, runtime
state, scene, turns) rather than centralizing everything in the global
reducer.

## What is out of scope here (by design)

No real transport is chosen or built (no HTTP endpoint, no IPC). No editing
semantics against a real backend for Runtime State. No Narrative Editor
integration. `services/character_core/**`, `services/character_lab/**`
(including `service_adapter.py`), and the Python `CharacterService` contract
are unmodified by this slice — read-only inspection only.

## Dependency status

Bootstrapped and verified (see `apps/character_lab_react/README.md` for the
full record). Exact versions resolved from `registry.npmjs.org`'s `latest`
dist-tag and pinned in `package.json`: `react`/`react-dom` 19.2.8,
`vite` 8.2.2, `typescript` 7.0.2, `@types/react` 19.2.18,
`@types/react-dom` 19.2.7, `@vitejs/plugin-react` 6.1.1. `npm install`
succeeded with zero peer-dependency overrides and `npm audit` reports zero
vulnerabilities. The full app — including the `.tsx` layer — now typechecks
with the project's own local `typescript` (`npm run typecheck`) and builds
with `npm run build`; a loopback-only (`127.0.0.1`) `npm run dev` smoke
confirmed the app actually serves. One standard, minimal fix was required:
`src/vite-env.d.ts` (`/// <reference types="vite/client" />`) for the CSS
side-effect imports' ambient module declarations — the normal Vite+TS
scaffold requirement, not a scaffold defect.
