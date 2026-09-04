# Character Core Release Boundary v1

Ratified decisions this slice implements as code:

- **OD-CHAR-PLATFORM-01(A)** — Character Core is architecturally independent
  from React/UI. Character Lab, Narrative Editor, and a future Character App
  are clients of the same logical `CharacterService` contract
  (`services/character_core/contract.py`). The contract is transport-neutral:
  no HTTP, IPC, or browser concepts appear in it. No transport is selected as
  canonical here — the local/direct adapter below is one of several possible
  future transports (direct/local, IPC, localhost HTTP, remote HTTP,
  test/mock), not the chosen one.
- **OD-CHAR-EMBED-01(A)** — a tested Core release may later be embedded
  directly inside a local application (e.g. Narrative Editor). Architectural
  independence does not require a separately installed service; this slice
  creates no external-service dependency and does not extract Core into
  another repository.
- **OD-CHAR-CORE-RELEASE-01(A)** — Character Core, Character Package, and
  Runtime/User Data have independent versions and are never bundled together.

## Package layout

```
services/character_core/
    contract.py   # SessionPurpose, DTOs, CharacterService, CharacterDebugService
    release.py    # CoreReleaseInfo, release-boundary classification
```

`contract.py` and `release.py` are standard-library only and must never
import `services.character_lab` or `services.character_runtime` (enforced by
`tests/character_core/test_contract.py`). No existing runtime module was
moved.

## SessionPurpose

`TESTING`, `AUTHORING`, `GAME_RUNTIME`, `COMPANION` are all *recognized*
architectural purposes. Only `TESTING` has a working implementation in v1
(`services/character_lab/service_adapter.py`); the other three are reserved
vocabulary with explicitly deferred semantics. Requesting a session for one
of them raises `SessionPurposeNotImplementedError` — never a silent fallback
to TESTING.

## Release metadata

`CoreReleaseInfo` (built by `release.build_core_release_info(...)`) carries
`core_version` (currently `0.1.0-dev`) and `contract_version` as
*independent* fields — the code deliberately does not conflate them with a
Character Package's `package_version` (KIRA is currently `package_version=0`,
tracked entirely separately in `accepted/kira/ACCEPTANCE.json`). `core_version`
is not called `1.0.0` merely because this boundary now exists — there is no
built/tested release yet. `source_commit` is optional and never hard-coded; a
future build step may supply it.

## Release-boundary classification

`release.CHARACTER_CORE_RELEASE_BOUNDARY` (a `ReleaseBoundary`) makes the
Core/Package/Runtime-data separation machine-testable, not just documented:

| Eligible for a Core release | Never eligible |
|---|---|
| runtime mechanism/code | accepted character package payloads |
| service contract | KIRA-specific package claims |
| context/policy mechanisms | runtime memory database |
| release metadata | `runtime_state.sqlite3` |
| | workspace data, sessions, Scene session files |
| | turn captures, user data |

Classification is exhaustive: an uncategorized `ReleaseArtifactCategory`
raises rather than defaulting to "includable". This is a descriptor only — no
build/package pipeline exists yet.

## Local Character Lab adapter (proof of contract)

`services/character_lab/service_adapter.py` implements `CharacterService`
(`CharacterLabServiceAdapter`) and `CharacterDebugService`
(`CharacterLabDebugAdapter`, a separate object — developer observability is
never part of the normal chat interface) directly over an existing
`CharacterLabApp` instance. Dependency direction:

```
Character Lab adapter  →  Character Core contract  →  existing Character Lab / runtime services
```

`services/character_core` never imports Character Lab. The adapter supports
only `SessionPurpose.TESTING`, using the existing Clean Test / Normal
workspace model; it does not generalize workspace semantics for
AUTHORING / GAME_RUNTIME / COMPANION, which remain deferred. It reimplements
no runtime, memory, Runtime State, Scene, or TurnCapture logic — every method
is a thin DTO translation over the existing `CharacterLabApp` / `TurnCapture`
calls.

**Workspace ownership is explicit, not implicit.** `CharacterService` exposes
`list_workspaces()`, `get_workspace(workspace_id)`, and
`create_test_workspace()`; `create_session(character_id, variant_id, purpose,
workspace_id)` requires an *already-existing* `workspace_id` and never
creates one itself — a caller wanting a fresh Clean Test calls
`create_test_workspace()` first. This lets multiple sessions share one
workspace (e.g. cross-session memory testing), matching the existing
Character Lab UI's own model, where the operator explicitly picks or creates
a workspace rather than getting a new one per session. `NORMAL` is visible
through `list_workspaces()` and addressable by id, but is never
auto-selected, and no data is ever copied between workspaces.

Scope follows the existing Character Lab semantics exactly: `get_memory` and
`get_runtime_state` take a `workspace_id` (memory and Runtime State are
workspace-scoped — every session sharing a workspace shares them), while
`get_scene` / `set_scene` / `clear_scene` take a `session_id` (Scene remains
session-scoped).

## What did not change

`KIRA_BETA_V1_CURRENT`, `KIRA_GROUNDED_V2`, runtime memory, Runtime State
(`FACT` / `RELATIONSHIP` / `PSYCHOLOGY`), Scene, `TurnCapture`, and the
Accepted KIRA package are all behaviorally unchanged — this slice adds a
boundary and one adapter around the existing implementation, nothing inside
it. No database schema changed, no provider prompt changed, no HTTP/IPC
transport was built.
