# Chat Control and Composer Assistant V1

Status: FIRST_RELEASE. Everyday conversation controls that never change what the
character remembers.

## CORE INVARIANT

**UI HISTORY  ≠  ACTIVE CHARACTER MEMORY  ≠  LONG-TERM MEMORY.**

Hiding a chat or a message, or renaming a chat, touches only durable
*presentation* metadata in the Companion session registry
(`companion_sessions.json`). No Memory event is deleted, updated or filtered
from Runtime retrieval; Runtime State, Consolidated Memory, Relationship,
Psychology, the Character Package and Scene facts are untouched.
`services/character_runtime/**` and `services/character_core/**` are not
modified.

## 1. Writing Assistant (`WRITING_ASSISTANT` model role)

Added additively to the generic model-role system from
`MEDIA_PROVIDERS_AND_MODEL_ROLES_V1` (`ALL_ROLES`, `ROLE_DISPLAY_ORDER`). It is
an **application utility role**, served by any DIALOGUE-capable provider/model,
and is **NOT** in `RUNTIME_WIRED_ROLES`. Localized: Помощник написания /
Writing Assistant / Asistente de escritura / 写作助手 / Assistente de escrita.

`services/character_companion/writing_assistant.py` `rewrite_draft(draft, …)`:

- resolves **only** the explicitly configured `WRITING_ASSISTANT`
  provider/model through `_factory_for(role=WRITING_ASSISTANT)` and the existing
  secure credential vault. No silent fallback to DIALOGUE / DeepSeek / Local;
  no automatic retry (one call).
- unconfigured → bounded `assistant_not_configured`
  ("Настройте модель «Помощник написания» в настройках.").
- sends the provider a fixed `[system, user(draft)]` pair — **never**
  conversation history, the Character Package, KIRA memory, Scene, Relationship
  or Psychology. It works only from the current draft (privacy + it cannot
  become a second character runtime).
- system prompt: fix spelling/grammar, improve readability, preserve meaning and
  approximate tone, **reply in the draft's own language, do not translate, do
  not answer the message, do not role-play or speak as a character, do not
  invent facts, return message text only.**

Endpoint: `POST /api/companion/writing-assistant/rewrite`
`{ "draft", "localeHint"? } → { "suggestion", "provider", "model" }`.

Backend tests prove a rewrite creates no Memory event, no Runtime State file,
and no session-registry change, and that the provider payload never contains
history or package identifiers.

### Composer UX contract

`[ + ]  [ message ]  [ ✨ ]  [ 🎤 ]  [ Send ]`

- `✨` enabled only when the draft has non-whitespace text **and**
  `WRITING_ASSISTANT` is configured for invocation.
- The suggestion replaces the text **in place** inside the same normal composer
  input. **No modal.** The message stays unsent; only the normal Send sends it.
  Assistant results are never auto-sent.
- Before the first rewrite the exact original draft is kept in ephemeral
  composer state (`src/app/composerAssistant.ts`); "Вернуть исходный текст"
  restores it exactly. Drafts are never persisted, never written to history.
- Pressing `✨` again regenerates from the **original** source draft, not a
  previous suggestion (`sourceDraftFor`), to avoid semantic drift. Manual edits
  are never overwritten except by an explicit new `✨`.
- On failure the current/original draft is left exactly as it was; a bounded
  localized message is shown.

## 2. Message action menu (`⋯`)

`src/features/MessageActions.tsx`. For user and character messages:
**Копировать** (exact visible text → `navigator.clipboard`, no backend, no
telemetry, no memory effect) and **Скрыть / Показать сообщение**. There is
deliberately **no** functional "Редактировать" — see the next-slice contract.

## 3. Hide message — presentation only

Binds to the stable Memory-event **`seq`** (already the message DTO identifier;
the underlying event identity is unchanged). `set_message_visibility` adds/removes
the seq in `presentation.hiddenMessageIds`. The event log is byte-identical
afterwards; `get_messages` still returns every message (the UI filters via
`visibleMessages`); Runtime retrieval is never filtered. Hidden messages are
omitted consistently in normal Conversation and in all three Focus layouts
(BACKGROUND / SIDE_GALLERY / CHAT_ONLY). Recovery: a per-conversation
"Показать скрытые (N)" toggle, and per-message "Показать сообщение". Hiding is
never irreversible from the UI.

## 4. Hide chat + rename

Conversation `⋯` menu: **Переименовать**, **Скрыть диалог**.

- `rename_session` stores `presentation.titleOverride` (trimmed, ≤120 chars, no
  AI). Empty clears it — the automatic label is used. `displaySessionTitle`
  prefers the override, else the existing title/label.
- `set_session_visibility` sets `presentation.hidden`. The session row, full
  history, generated media, cover and every Runtime effect remain exactly as
  before — nothing is physically deleted. Hidden chats leave the normal list and
  appear in a collapsible **"Скрытые (N)"** section with **Восстановить**.

## 5. Privacy wording

Hide is **presentation privacy, not secure erasure**. UI labels are
"Скрыть сообщение / Скрыть диалог / Восстановить" — never "Безвозвратно
удалить", and nothing implies disk data is destroyed. App PIN, biometric
unlock, privacy mode, secure local-data deletion, account auth and cloud sync
are out of scope; the architecture stays compatible with them.

## 6. Durable presentation metadata

Stored additively per session as
`row["presentation"] = { titleOverride, hidden, hiddenMessageIds }` in the
existing `companion_sessions.json`. No new database. Legacy rows without a
`presentation` key load unchanged (defaults: no override, not hidden, no hidden
messages). Existing `DIALOGUE` provider/model and all prior settings survive
with no migration.

## 7. Generated media / context (unchanged)

Image generation behaviour is not changed. A future "Кадр по контексту" is
intended to use **active character context**, not merely visible UI messages —
so a hidden message may still influence future context-derived media. That is
intentional and is different from edit/supersession semantics.

---

# NEXT SLICE CONTRACT — `RECENT_TAIL_EDIT_SUPERSESSION_V1`

Not implemented here. Editing an **already-sent** message is deferred to this
slice. It must NOT `UPDATE` or `DELETE` an old Memory event, truncate the
ledger, branch history or rewrite Consolidated Memory. Intended shape:

1. the old immutable event remains;
2. a **supersession** metadata/event records that a later version exists;
3. a new user message/version is appended;
4. the previous downstream character response becomes **inactive for the active
   branch** (not deleted);
5. a new character response is generated;
6. long-term / approved / consolidated memory is **never silently rewritten**.

### Conservative edit-eligibility rule (to be enforced by that slice)

An ordinary edit is allowed only for a **bounded recent user tail** that has not
crossed a durable-memory safety boundary. Any message that already affected
durable approved / consolidated state must not be silently rewritten. The exact
eligibility mechanism (how far back, how the boundary is detected) belongs to
`RECENT_TAIL_EDIT_SUPERSESSION_V1`.
