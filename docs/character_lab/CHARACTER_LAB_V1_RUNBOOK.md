# Character Lab V1 Runbook

Status: DOCUMENTATION BASELINE (read-only). This is a DESIGN + OPERATOR runbook.
Labels distinguish CURRENT (exists today) from TARGET V1 / PLANNED (accepted
direction, not yet implemented). Do not assume an unimplemented command or
screen exists.

---

## 1. Current interaction method

CURRENT:

`tools/kira_chat_cli.py` is the existing terminal interaction baseline. It
represents the behavior preserved as `KIRA_BETA_V1_CURRENT`.

Character Lab UI is NOT implemented yet.

---

## 2. Target launch experience

TARGET V1: one PowerShell launcher starts:

1. Character Lab local backend;
2. waits for health;
3. opens Edge/Chrome in App Mode;
4. provides a dedicated Character Lab window;
5. shuts the backend down cleanly when the application closes.

Conceptual launcher: `tools/start_character_lab.ps1` (do NOT claim the file
exists).

Backend binds `127.0.0.1` only. The frontend never receives provider secrets.

---

## 3. Default workspace

Records OD-CL-03 (ACCEPTED).

On launch: Workspace = `CLEAN TEST`.

`Normal / Long-lived` must be selected explicitly.

- Clean Test: isolated memory; isolated history; safe for experiments.
- Normal: persistent long-lived KIRA memory; explicit deliberate switch.

No per-message confirmation is required.

---

## 4. Main UI workspace

Approved high-level layout:

LEFT:

- Characters
- Variants
- Sessions
- workspace selector

CENTER:

- Chat
- selected session
- message input
- Scene indicator where relevant

RIGHT:

- Loaded State
- context-sensitive inspector
- Turn details when a reply is selected

---

## 5. V1 modes

Main working modes (exactly these):

- CHAT
- SCENE
- CHARACTER
- MEMORY
- TURN DEBUGGER

Diagnostics may be a small persistent/utility panel rather than a separate major
workspace.

Future only:

- COMPARE
- TEST RUNS

---

## 6. Character selection workflow

TARGET: click KIRA.

Backend resolves:

- `character_id`
- `AcceptanceRecord`
- accepted source hash
- runtime package hash
- hash match
- Variant
- workspace
- memory
- session
- provider/model
- context capture state
- package write state

Loaded State example:

```
KIRA                        LOADED
Acceptance                  HUMAN_APPROVED
Accepted source hash        e26f83...
Loaded package hash         e26f83...
Hash match                  YES
Variant                     KIRA_BETA_V1_CURRENT
Workspace                   CLEAN TEST
Session                     ...
Provider                    DeepSeek
Model                       deepseek-v4-pro
Context Capture             ACTIVE
Package Write Access        LOCKED
```

Important: Loaded State does NOT imply full package content was delivered to the
model.

---

## 7. Character Inspector

TARGET: read-only projection of the actual loaded package.

Possible groups:

- Identity / Biography
- Psychology
- Behavior
- Relationships
- Boundaries
- Intimacy
- Voice
- Contradictions
- Unknowns

The header shows the exact accepted source hash. Values must derive from loaded
package data, not a separate UI copy.

---

## 8. Scene Setup workflow

TARGET minimal form:

- Title
- Location
- Participants
- Prior events
- Current situation

Example:

```
Title:
Party test

Location:
Вечеринка

Participants:
Andrey
Kira
Sergey

Prior events:
Андрей и Кира пришли вместе.

Current situation:
Сергей подходит к Кире и приглашает её танцевать.
```

Do NOT specify: Kira's emotion, attraction, intention, decision, action, or
reply.

Scene is session-scoped. It does not automatically become long-lived memory.

---

## 9. Chat workflow

TARGET:

1. select character;
2. select variant;
3. confirm workspace;
4. optionally create Scene;
5. start/new session;
6. send user message;
7. backend assembles context;
8. exact provider request is captured;
9. provider is called;
10. response is captured;
11. runtime writes occur;
12. Memory Inspector refreshes;
13. user may click the response to open Turn Debugger.

---

## 10. Memory workflow

TARGET: Memory Inspector shows:

- sequence
- timestamp
- session
- event type
- provenance
- meaning
- persisted state
- whether mechanically proven delivered in a selected turn where available

Important visual semantics:

- `USER_STATED` means "user said this."
- `CHARACTER_UTTERANCE` means "KIRA/model said this."
- Neither automatically means "this is objectively true."
- `LEGACY_UNCLASSIFIED`: historic pre-provenance row.

Do not backfill false provenance.

---

## 11. Turn Debugger workflow

Click a KIRA response to open. Show:

- TURN ID
- CHARACTER
- VARIANT
- WORKSPACE
- SESSION
- ACCEPTED SOURCE HASH
- STORED / LOADED / SELECTED / DELIVERED status where applicable

REQUEST:

- raw captured provider request
- hash

MANIFEST:

- package segments
- scene segments
- memory event IDs
- dialogue history
- user input

PROVIDER:

- requested provider/model/config
- attempts
- response status

OUTPUT:

- provider response
- finish reason if captured

PERSISTENCE:

- new runtime event IDs
- provenance
- sequence

PACKAGE:

- unchanged invariant

Keep a visible distinction between `PROVEN` and `ANALYSIS / NON-AUTHORITATIVE`.

---

## 12. Clean Test workflow

TARGET: New Clean Test:

- new isolated workspace memory root;
- no inherited Normal long-lived memory;
- selected accepted character unchanged;
- selected Variant unchanged;
- new clean session;
- optional Scene;
- exact turn artifacts stored under the test workspace.

Reset Clean Test may delete/reset the isolated test workspace only. It must
never reset Normal memory implicitly.

---

## 13. Long-lived memory workflow

Switching to Normal is explicit.

The UI should clearly indicate: `LONG-LIVED MEMORY`.

Messages/events in this workspace contribute to persistent character history.

Do not ask for confirmation on every message.

---

## 14. Beta v1 warning

`KIRA_BETA_V1_CURRENT` is intentionally preserved as the current historical
runtime behavior.

It may:

- receive package metadata without full package claims;
- receive prior model-generated dialogue as history;
- preserve legacy memory ordering;
- improvise unsupported details.

Character Lab is initially meant to make these behaviors observable. It is not
meant to silently repair them.

---

## 15. Future Grounded v2

PLANNED only. Same Accepted KIRA, different runtime policy.

Potential future areas:

- explicit UNKNOWN discipline;
- provenance-aware memory selection;
- causal sequence ordering;
- package-claim selection;
- safer treatment of `CHARACTER_UTTERANCE`.

Do not specify implementation yet.

---

## 16. Deferred workflows

No V1 workflows for:

- second chat;
- hidden thoughts;
- Decision Layer;
- Compare;
- Test Runs;
- Replay/Fork;
- automatic hallucination scoring.

---

## 17. Operator truth rules

1. "Stored" does not mean "delivered."
2. "Loaded package" does not mean "package content was in the prompt."
3. "KIRA said X" does not mean "X is true."
4. "User said X" does not automatically mean "X is world truth."
5. Scene truth is not package truth.
6. Only exact captured provider-request evidence can establish DELIVERED.
7. Character Lab must never display hidden reasoning as fact.
