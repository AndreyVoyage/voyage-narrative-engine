# Character Companion (MVP v1)

End-user chat client for accepted characters. **Separate application** from
Character Lab (the developer/operator/debug client). No final visual design yet
— the UI is a minimal neutral functional scaffold pending the owner's design
direction.

## Architecture

```
apps/character_companion_react  (this app)
    -> CompanionClient            (src/client, transport-neutral)
    -> /api/companion/... (HTTP)  (dev: Vite proxy -> loopback server)
    -> tools/character_companion_server.py
    -> services/character_companion (CompanionTransport -> CompanionService)
    -> RuntimeService.turn + RuntimeMemoryBackend   (unchanged)
```

Only five operations: list characters, list sessions, create session, get
messages, send message. No debug / operator / workspace / memory / evolution
surface.

## Toolchain

This app has **no `node_modules` of its own** and requires **no `npm install`**.
It reuses the already-installed toolchain in `../character_lab_react/node_modules`
(same pinned versions, aliased in `vite.config.ts` / `tsconfig`).

Run its scripts with the sibling's binaries, e.g. from this directory:

```
../character_lab_react/node_modules/.bin/tsc --project tsconfig.checks.json
node dist-checks/scripts/structural-checks.js
```

`npm run structural-checks` also works if a global `tsc` + `node` are on PATH
(the structural check imports no React and no Node types).

## Local run (fake provider)

```
# terminal 1 -- backend (loopback, deterministic fake provider)
python tools/character_companion_server.py --data-root .companion-dev-data --port 8788

# terminal 2 -- dev client against that backend
../character_lab_react/node_modules/.bin/vite            # http://127.0.0.1:5173
# or, with no backend, an in-memory mock:
../character_lab_react/node_modules/.bin/vite --mode mock
```

Zero external network. Zero live provider calls.
