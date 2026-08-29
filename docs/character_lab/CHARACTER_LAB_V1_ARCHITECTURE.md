# Character Lab V1 Architecture

Status: DOCUMENTATION BASELINE (read-only). No production implementation in this
task. CURRENT describes the repository as it exists today; RATIFIED TARGET and
PLANNED describe accepted direction only.

---

## 1. Purpose

Character Lab is a local developer/test/observability shell over:

- a CRP Accepted Character;
- the Character Runtime;
- Runtime Memory;
- the Provider adapter.

Its job is to let the operator:

- load an accepted CRP character;
- talk to that character through Character Runtime;
- inspect exactly which character/package is loaded;
- inspect runtime memory live;
- prepare scene context before dialogue;
- prove what data was actually selected and delivered to the provider;
- inspect exact provider request/response artifacts per turn;
- observe runtime writes;
- debug character behavior without pretending to expose hidden reasoning.

Character Lab is NOT:

- a Ren'Py UI;
- a CRP authoring UI;
- an Accepted Package editor;
- a replacement runtime;
- a second source of character truth;
- a hidden-thinking system.

---

## 2. Architectural principles

- **Accepted character seed immutable.** The accepted package is never rewritten
  by runtime or by Character Lab.
- **Runtime state separate.** Memory/events live apart from the package seed.
- **UI does not contain character personality logic.** Personality truth comes
  only from the loaded accepted package; the UI projects it.
- **Provider credentials backend-only.** Secrets never reach the frontend.
- **Character Lab projections derive from runtime artifacts.** The UI renders
  what the runtime produced, not a parallel UI-side copy.
- **Evidence before presentation.** Show only what the runtime can prove.
- **No unsupported diagnostic claims.** Do not convert stored state, intent, or
  model self-report into "the model used X" claims.
- **One observable runtime chain.** There is no second chat, no hidden-thinking
  chain, no Character Decision Layer.
- **Clean Test default.** Test conversation must not silently contaminate
  long-lived character memory.
- **Variants do not rewrite characters.** A variant changes runtime/context/
  memory policy, never the accepted package.

---

## 3. Current accepted-character model

```
CandidateCharacterPackage (status = DRAFT)
        +
AcceptanceRecord (decision = HUMAN_APPROVED, exact package-hash binding)
        |
        v
load_accepted_character()          # services/character_runtime/runtime.py
        |
        v
AcceptedCharacter                  # frozen: subject_id + package + hash + acceptance_id
        |
        v
RuntimeSession                     # accepted + memory backend + session_id
```

Important facts (CURRENT):

- The Accepted Character Package is NOT a separately rewritten package. The
  source object remains a `CandidateCharacterPackage` whose `status` stays
  `DRAFT`.
- Human ACCEPT is represented by a detached `AcceptanceRecord` bound fail-closed
  to the exact package hash. Acceptance does NOT rewrite Candidate status.
- Runtime loads an `AcceptedCharacter` only after acceptance + hash verification
  succeed. A DRAFT-only source (no acceptance record) is never a runtime
  character.

Recommended UI terminology (avoid inventing a false second artifact):

- `Candidate (DRAFT)` — the source package, status DRAFT.
- `Accepted KIRA` — the subject that has a binding acceptance record.
- `Acceptance Record` — the detached record over the exact DRAFT Candidate hash.
- `Loaded Character` — the `AcceptedCharacter` instance in the runtime session.
- `Runtime Session` — the live session over memory + accepted package.
- `Variant` — a named runtime/context/memory policy (see §5).
- `Runtime Memory` — durable runtime events, separate from the package.
- `Scene` — owner-authored session-scoped situational input (see §11).

---

## 4. Current KIRA runtime baseline

`KIRA_BETA_V1_CURRENT` is the preserved current runtime policy. It is a baseline
description, not an endorsement.

Current behavioral characteristics (verified against `tools/kira_chat_cli.py`
and `services/character_runtime/`):

- The accepted package is loaded and hash-verified through the acceptance gate.
- The current chat system prompt primarily includes role instruction,
  `subject_id`, `package_id`, `package_version`, package `status`,
  `source_candidate_hash`, and prior-session runtime memory events.
- The full package claim content (psychology, identity/biography, behavior,
  relationships, boundaries, voice, unknowns) is NOT currently proven to be
  injected into the provider request by the current chat path.
- Package metadata is included.
- Prior-session runtime memory is included.
- Model utterances (`CHARACTER_MESSAGE`) are persisted and can re-enter future
  context.
- Legacy memory ordering (`ORDER BY created_at, event_id`) is preserved for
  baseline reproducibility.

Therefore: **PACKAGE LOADED does not imply PACKAGE CONTENT DELIVERED TO MODEL.**
This distinction is a core reason for Character Lab.

---

## 5. Character Variant model

A Variant is:

```
same Accepted Character
+
named/versioned runtime/context/memory policy
```

V1 variants:

- `KIRA_BETA_V1_CURRENT` — IMPLEMENTED BASELINE (preserved historical behavior).
- `KIRA_GROUNDED_V2` — PLANNED.
- `EXPERIMENTAL` — PLANNED.

A Variant must NOT:

- alter the package;
- alter acceptance;
- become a new reconstruction;
- consume Hidden-B;
- silently replace another variant.

Conceptual `RuntimePolicy` responsibilities (contract only, no implementation
specified here):

- `assemble_context(...)`
- `select_memory(...)`
- `persist(...)`

---

## 6. Character Lab V1 information flow

Target flow (one observable chain):

```
Character Lab UI
        |
        v
Local Character Lab backend/service
        |
        +--> Accepted Character load gate
        |
        +--> Variant policy
        |
        +--> Workspace / Runtime Memory
        |
        +--> Scene
        |
        v
Context Assembly
        |
        v
Provider-boundary capture            # exact request body/hash
        |
        v
Provider
        |
        v
Response capture
        |
        v
Runtime event persistence
        |
        v
Updated UI projections
```

---

## 7. Thin backend service boundary

Advisor recommendation: a new thin Character Lab application-service layer should
**compose** existing modules rather than reimplementing them:

- `services.character_runtime`
- acceptance loading (`services/crp_authoring/acceptance_store.py`)
- `RuntimeMemoryBackend` (`services/character_runtime/memory.py`)
- the provider callable (injected `Callable[[list], str]`)

Conceptual target names (TARGET only, do NOT claim they exist):

- `services/character_lab/runtime_service.py`
- `tools/character_lab_server.py`

The frontend must NOT perform:

- package hashing;
- acceptance loading;
- candidate rehydration;
- DB access;
- provider calls;
- secret handling.

---

## 8. Package immutability

Current mechanical protection (verified):

- frozen dataclasses (`CandidateCharacterPackage`, `AcceptedCharacter`,
  `RuntimeEvent`);
- immutable nested structures (`MappingProxyType`, tuples);
- fail-closed acceptance hash verification on load.

Target additional Character Lab invariants:

- Character Lab has no accepted-package writer path.
- No acceptance writer is imported into the Character Lab runtime path.
- Accepted hash is recorded at load.
- Session-close verification may confirm the source is unchanged.
- Export may re-verify source artifact identity.

Per-turn re-hashing is not required when the frozen object plus boundary
controls are sufficient.

---

## 9. Canonical accepted source artifact

Records OD-CL-01 (ACCEPTED).

CURRENT:

- KIRA source bytes for rehydration depend on an external local artifact:
  `C:\DEV\Narrative\LOCAL_STORAGE\crp_r4_live_runs\RUN_015.stdout.json`.
- `accepted/kira/ACCEPTANCE.json` is committed, but the full source Candidate
  bytes are not currently materialized alongside the acceptance artifact.

RATIFIED TARGET (NOT implemented in this documentation task):

- Materialize a frozen immutable copy of the exact accepted source Candidate
  alongside the acceptance material.

Conceptual target:

```
accepted/kira/
    ACCEPTANCE.json
    source_candidate.json        # exact filename may be finalized later
```

Invariants:

- copied source content must represent the exact accepted Candidate;
- `compute_package_hash` must remain exactly
  `e26f83dafa26e61af82f29b654b592300c8f3f7bd295d07bd4d2b6527ae3eebd`;
- Candidate status remains DRAFT;
- human acceptance remains a detached `AcceptanceRecord`;
- no package content is rewritten;
- no Hidden-B information may enter the artifact;
- no runtime memory may enter the artifact.

---

## 10. Workspace model

- `CLEAN TEST` — default; isolated memory root; safe for experiments.
- `NORMAL / LONG-LIVED` — persistent personal KIRA history; explicit switch
  required.

Recommended minimal architecture: separate runtime memory root/directory per
workspace rather than complex workspace columns.

Conceptual:

```
<userdata>/character_lab/workspaces/
    normal/
    tests/<test_id>/
```

---

## 11. Scene model

Minimal Scene:

- `scene_id`
- `title`
- `location`
- `participants`
- `prior_events`
- `current_situation`

A Scene is:

- session-scoped;
- owner-authored situational input;
- distinct from package truth;
- not automatically durable memory.

A Scene must NOT add: emotions, attraction, character decisions, chosen actions,
or pre-scripted replies. Those are not inputs.

---

## 12. Local application shell

Ratified V1 direction:

- Python local backend;
- lightweight HTML/CSS/JavaScript frontend;
- `127.0.0.1` only;
- Edge/Chrome App Mode;
- PowerShell launcher.

Desired experience: one dedicated Character Lab window; no normal tabs, no
normal address bar, no normal browser chrome.

Browser App Mode is the V1 default. PyWebView is a fallback only if lifecycle/
app-window handling proves unreliable. Tauri/Electron is deferred.

---

## 13. V1 scope

MUST HAVE:

- launcher/application shell;
- mouse character selection;
- Variant selection;
- Loaded State;
- Chat;
- session list / new session;
- Clean Test workspace;
- Character Inspector;
- Scene Setup;
- live Memory Inspector;
- minimal provenance;
- stable causal event sequence for observation;
- exact Context Snapshot;
- provider/model attribution;
- Turn Debugger;
- package read-only enforcement;
- honest diagnostics.

---

## 14. Explicitly deferred

- second KIRA chat;
- hidden-thinking chat;
- chain-of-thought UI;
- Decision Layer;
- emotion engine;
- relationship evolution engine;
- Compare;
- automated Test Runs;
- Fork/Replay;
- Package Diff;
- Context Diff;
- graph visualizations;
- automatic hallucination score;
- automatic truth promotion;
- advanced analytics;
- Ren'Py integration;
- native binary packaging.

---

## 15. Implementation slices

Target order only; no implementation in this task.

SLICE 1:

- backend boundary;
- RuntimePolicy baseline extraction;
- exact provider request/response capture;
- append-only turn artifacts;
- reproducibility identity.

SLICE 2:

- application shell;
- Chat;
- Loaded State;
- Character Inspector;
- Turn Debugger;
- provider attribution.

SLICE 3:

- Memory Inspector;
- provenance metadata;
- stable sequence;
- Clean Test workspace;
- Scene Setup.
