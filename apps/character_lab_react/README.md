# Character Lab (React foundation)

A **foundation-only** React + TypeScript client for Character Lab, built
against the already-committed `services/character_core/contract.py` /
`services/character_lab/service_adapter.py` boundary. It does **not** replace
the existing vanilla Character Lab (`services/character_lab/web/**`), which
remains untouched and fully operational.

## Status: bootstrapped and verified

Dependencies are installed and pinned. `npm run typecheck`, `npm run build`,
and `npm run dev` (loopback) all pass against the real toolchain below.

## Dependency versions

Resolved from `registry.npmjs.org`'s `latest` dist-tag at bootstrap time and
pinned exactly (no ranges) in `package.json` — do not assume these stay
current; re-resolve deliberately if they ever need to change:

| package | version | role |
|---|---|---|
| `react` | 19.2.8 | runtime |
| `react-dom` | 19.2.8 | runtime |
| `vite` | 8.2.2 | dev server / bundler |
| `typescript` | 7.0.2 | typechecking |
| `@types/react` | 19.2.18 | types |
| `@types/react-dom` | 19.2.7 | types |
| `@vitejs/plugin-react` | 6.1.1 | Vite React plugin |

`npm install` completed with zero peer-dependency conflicts (no `--force`,
no `--legacy-peer-deps` needed). `npm audit` (both `--omit=dev` and full)
reports **0 vulnerabilities**.

## Scripts

```
npm run dev             # Vite dev server (bind loopback explicitly for a
                         # local check: npm run dev -- --host 127.0.0.1)
npm run build           # production build -> dist/ (gitignored, never commit)
npm run typecheck       # tsc -p tsconfig.app.json && tsc -p tsconfig.node.json
npm run structural-checks   # compiles + runs scripts/structural-checks.ts
npm run check           # typecheck + structural-checks
```

## What was verified

- `npm run typecheck` — **PASS**, zero errors, across the entire `src/` tree
  (all `.ts` and `.tsx`, including JSX) plus `vite.config.ts`.
- `npm run structural-checks` — **12/12 passed** (session-purpose vocabulary,
  TESTING-only mock support, Experimental unavailable, explicit-workspace-id
  session creation with no silent workspace creation, memory/runtime-state
  workspace-scoping — including a real cross-session memory test — and
  session-scoped Scene, by both arity and behavior).
- `npm run build` — **PASS**, 54 modules transformed, output under `dist/`.
- `npm run dev -- --host 127.0.0.1 --port <port> --strictPort` — dev server
  bound to `127.0.0.1` only (confirmed via `netstat`, no LAN exposure),
  served `index.html` and transformed `src/main.tsx` with HTTP 200, then
  stopped cleanly.
- `grep` scans confirm: no `fetch()`/HTTP/`localhost` concept in
  `src/client/*.ts` outside of doc comments explaining the constraint; zero
  imports of `services.character_lab`, `services.character_runtime`, or any
  `.sqlite3` reference anywhere under `src/`.

The one fix required beyond the original scaffold: `src/vite-env.d.ts`
(`/// <reference types="vite/client" />`), the standard Vite+TypeScript
convention needed for the CSS side-effect imports in `main.tsx` to have
ambient module declarations. No component was redesigned; no TypeScript
strictness was loosened; no `any`/`@ts-ignore`/`@ts-nocheck` was introduced.

## Structure

```
src/
  client/       transport-neutral CharacterClient / CharacterDebugClient
                interfaces + DTOs (mirrors services/character_core/contract.py)
  mocks/        MockCharacterClient / MockCharacterDebugClient + fixture data
                (no real Accepted Package data anywhere in here)
  styles/       design tokens + layout primitives + component styles (plain CSS)
  components/
    primitives/ layout-only building blocks (Panel, Section, Toolbar, Stack,
                Inline, Card, DataTableShell, FormGrid, EmptyState)
    layout/     AppShell + Sidebar/MainPanel/InspectorPanel region wrappers
    character/  reusable "character UI" (ChatPanel, CharacterIdentityCard,
                SceneForm) -- the tier a future consumer Character App could
                plausibly reuse
    devtools/   developer/debug UI only (MemoryTable, RuntimeStateGroups,
                TurnDebuggerPanel) -- never imported by components/character
  features/     one view per nav destination, composing the tiers above
  navigation/   the six nav destinations + their character/debug tier
  app/          AppState (React context + reducer) and App (shell composition)
  main.tsx      the ONLY place a concrete CharacterClient is chosen (mock, here)
scripts/
  structural-checks.ts   dependency-free runtime checks over client/mocks
                         (compiled + run directly with the local toolchain)
```

## No direct Python coupling

No file under `src/` imports or encodes `services.character_lab.*`,
`services.character_runtime.*`, a filesystem path, a SQLite filename, or a
`localhost` URL. `CharacterClient` / `CharacterDebugClient` are Promise-based
interfaces with no HTTP concept anywhere in them; swapping the mock for a
real transport adapter later only touches `main.tsx`.

## Not yet done (intentionally out of scope)

No real transport (HTTP/IPC) is chosen or implemented. No backend
integration. No Narrative Editor integration. No consumer Character App. No
editing semantics against a real backend for Runtime State. `services/**`
remains untouched.
