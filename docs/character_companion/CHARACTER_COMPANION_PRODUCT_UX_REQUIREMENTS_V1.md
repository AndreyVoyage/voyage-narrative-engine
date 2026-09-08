# Character Companion — Product / UX Requirements V1

**Status:** Canonical product/UX requirements record. Consolidates owner-accepted
product decisions taken after `CHARACTER_COMPANION_APP_MVP_V1` (commit `500257c`)
and `LOCAL_LLM_PROVIDER_V1` (commit `a8c6225`).

**This is not an implementation task or authorization.** It records direction. It
does **not** authorize building deferred features before **KIRA COMPANION MVP
READY**. See §35 (Anti-gate-creep).

Baseline: branch `feature/crp-mvp-v1`, HEAD `a8c62253190d027781f62f5f25324fc77711b7ea`.

---

## Status model

Every substantial requirement below carries exactly one classification:

| Status | Meaning |
|---|---|
| **ACCEPTED** | The owner has decided the product direction. Not necessarily first-release. |
| **FIRST_RELEASE** | Required before **KIRA COMPANION MVP READY**. |
| **DEFERRED** | Architecturally planned; **not** required before first release. |
| **OPEN_OWNER_DECISION** | Intentionally still undecided. Do not decide it. |

A future idea is **not** a first-release requirement unless it appears in §32.

---

## 1. Product identity — ACCEPTED

- Character Companion is a **user-facing application**.
- Character Lab remains a **separate** developer / operator / debug application.
  Companion never imports the Lab adapter/UI and never exposes debug, operator,
  workspace, memory-editor, or evolution surfaces.
- Character Core / Runtime is **independent of the visual client**. Clients talk
  to it only through the logical `CompanionService` / transport boundary
  (`CompanionClient` → `/api/companion/...` → `CompanionTransport` →
  `CompanionService` → `RuntimeService` / `RuntimeMemoryBackend`).
- Companion must remain **character-generic**. No character-specific application
  behavior is hardcoded.
- **KIRA** is the first accepted character, **not** an application architecture.
  KIRA-specific data lives only in the catalog entry / accepted package.
- Future accepted characters must be addable through a **catalog / registration**
  mechanism (Accepted Character Package → catalog registration → character
  appears in Companion) without rewriting the UI or Core.

---

## 2. Experience / themes — ACCEPTED

One functional Companion application supports **switchable experience presets**.

Accepted experience directions:

1. **Cinematic Companion** — primary style, to finish first.
2. **Literary Companion** — conceptually accepted second style; implementation
   may follow after Cinematic.

- The previous "Minimal" concept is **not** accepted as a separate final
  experience. The earlier Premium/Minimal split was too similar to be two
  distinct products.
- A **third experience is DEFERRED / OPEN_OWNER_DECISION**.

**Hard constraint:** presets affect **presentation only**. A preset must never
alter the Character Package, psychology, Runtime State, memory, relationship
state, epistemics, Scene semantics, or provider semantics.

---

## 3. Cinematic — primary desktop UX — ACCEPTED

Desktop normal mode has three accepted **semantic regions** (exact pixel layout
is design work):

- **LEFT** — character / navigation area.
- **CENTER** — the active conversation.
- **RIGHT** — character + scene/context visual wing (see §4).

---

## 4. Right visual wing — ACCEPTED

**Top — persistent character portrait.**

- Represents the **character**, not the current scene.
- Always available in Cinematic normal mode.
- Never automatically deleted.
- Generated scene images **never** replace or delete it automatically.
- Only the user may explicitly replace or remove it.
- When there is no scene image, the portrait may expand vertically down to the
  scene-parameter area.

**Below the portrait — optional scene / chat image.**

- Belongs to a **specific chat / scene**.
- May become the chat cover / thumbnail.
- May be generated from scenario / context.
- **Never** becomes source-of-truth for scene facts.
- **Never** auto-deletes older generated images; the user controls deletion.
- A future gallery may preserve multiple generated frames.

**Below the visual area — structured scene information:** location, time,
situation, mood. These may be empty / default when no scene is defined.

---

## 5. Scene image generation — ACCEPTED

Two distinct operations:

- **A. "Создать изображение…"** — the user explicitly describes the desired
  image (user-directed generation).
- **B. "Кадр по контексту"** — the system derives a visual-generation request
  from: the current Scene, relevant conversation context, participating
  characters, approved character visual references, and location references
  where available, via the **existing** visual generation pipeline.

- **Do not build a second visual pipeline** if a project mechanism already
  exists.
- A generated image is **visual interpretation only**. It must **not** write
  facts back into Scene / Memory / Runtime State automatically.

---

## 6. Asynchronous image generation — ACCEPTED

- Image generation **must not block** conversation. Chat stays fully usable
  while generation runs.
- Conceptual job states: **QUEUED → GENERATING → READY → FAILED**
  (optionally **CANCELLED** later).
- User-visible feedback: generation started / in progress / complete / failed.
- On completion, notify the user **without interrupting** chat.
- A generated image remains until the user explicitly deletes it.

---

## 7. New dialog flow — ACCEPTED

A new conversation can be created as:

- **A.** ordinary conversation, no scenario.
- **B.** conversation with a starting scene.

For a scene, support:

- free-form scenario description;
- editable structured fields: **location, time, situation, mood**.

AI may later help parse a free-form scenario into these fields, but the user
must always be able to **review and edit** them. No generated interpretation is
silently immutable.

---

## 8. Random scenario / dice — ACCEPTED

- **"🎲 Случайный сценарий"** is a supported product concept.
- Future UX may randomize: the whole scenario, or location / time / situation /
  mood individually.
- Random output must be **editable before starting**.
- The first deterministic version does **not** require an LLM if a local
  rule / library can produce scenarios.

---

## 9. Multiple chats with one character — ACCEPTED

- A single character can have **many separate chats**.
- Organization must support many KIRA conversations **without** collapsing into
  one endless transcript.
- Each chat may carry: title, created / last-activity, last-message preview,
  optional scene cover thumbnail, portrait fallback when no cover exists,
  generation status, unread status where applicable.

Classification:

- **FIRST_RELEASE** — basic multi-chat listing.
- **DEFERRED** — search, pinned, archive, tags, richer filters, gallery views.

---

## 10. Continuity / memory modes — ACCEPTED (target behavior, not yet implemented)

New chats must eventually distinguish:

- **A. Continue existing relationship / history** — "Продолжить текущую историю".
- **B. Start a separate isolated story / history** — "Начать отдельную историю".
- **C. Temporary / non-persistent test-like conversation** — "Временный чат".

Rules:

- User-facing terminology should avoid low-level words such as *workspace*
  unless necessary.
- A **Scene belongs to a specific conversation / history context**.
- Isolated stories must **not** silently contaminate the main relationship.
- Character personality / package remains the **same character** across modes.
- Long-term relationship memory may be shared **only within the intended
  continuity boundary**.

This whole UX is **accepted target behavior**, not a claim of current
implementation.

---

## 11. Focus mode — ACCEPTED

The active chat can expand to a distraction-free mode. Conceptual view options:

1. **BACKGROUND** — portrait / scene image as atmospheric background, chat
   overlaid and readable.
2. **SIDE GALLERY** — chat occupies most of the screen; a vertical visual
   gallery on the side (character portrait, current scene cover, generated
   contextual frames).
3. **CHAT ONLY** — no visual distraction.

The user can exit easily (button / Esc on desktop). Exact visual design belongs
to the Cinematic implementation pass.

---

## 12. Composer / attachments UX — ACCEPTED

Default composer stays clean:

`[ + ]  [ message field ]  [ microphone ]  [ send ]`

- The **microphone** beside the composer means **record a new voice message**.
- Do **not** duplicate "voice message" as a separate permanent shortcut under
  attachments.
- **"+"** opens the attachment / action menu:
  - **ATTACH:** Image · Document · Audio file · Video
  - **CREATE:** Create image… · Context frame

Distinctions (must be unambiguous in UI):

| Action | Meaning |
|---|---|
| Image | upload an existing image |
| Audio | upload an existing audio file |
| Video | upload an existing video file |
| Microphone | record the user's new voice message |
| Create image… | user-directed image generation |
| Context frame | automatic context-based image generation |

---

## 13. Multimodal attachments — ACCEPTED (direction) / DEFERRED (implementation)

- **ACCEPTED architectural direction.** **DEFERRED** beyond first release unless
  later explicitly promoted.
- A future character should be able to understand images, supported documents,
  audio, and video.
- Multimodal processing feeds **normalized content into the existing Character
  Runtime** — never a parallel personality / memory system.

---

## 14. Documents / book reading — ACCEPTED FUTURE DIRECTION (DEFERRED)

- Target document classes: PDF, TXT, Markdown, DOCX, EPUB.
- Use cases: discuss a document; read / discuss a book; discuss selected
  chapters; avoid spoilers beyond the user's reading progress; shared
  reading / library experience.
- **Large books must not be inserted whole into one provider prompt.**
- Target architecture: document → safe extraction → chunking / index → relevant
  retrieval → Character Runtime.
- Document knowledge must be **scoped**. Possible future scopes: this chat only;
  this history / continuity; saved character library.
- Document content is **not** automatically long-term personal memory.

---

## 15. Attachment security gateway — ACCEPTED and MANDATORY before arbitrary upload

**Never expose unrestricted file upload first and "secure it later."** Arbitrary
file upload is gated on this gateway existing.

Requirements:

- explicit format **allowlist**;
- verify real file **type / signature**, not extension only;
- maximum **byte size**;
- page / resolution / duration limits;
- decompression / archive-expansion limits; **ZIP-bomb** protection;
- **path-traversal** protection; safe internal filenames / IDs;
- no macro execution; no script execution; no shell execution;
- no automatic external-resource fetch from documents;
- isolate risky parsers where practical;
- optional Windows Defender / malware integration later;
- metadata / privacy handling where appropriate (e.g. EXIF / GPS stripping);
- **malformed inputs fail closed.**

**Prompt-injection rule:** text contained in documents / images / files is
**DATA**. It does **not** gain authority to override system instructions, access
API credentials, call privileged tools, modify Runtime State, create scheduler
jobs, alter memory policy, or execute code.

---

## 16. Voice messages (user) — ACCEPTED FUTURE FEATURE (DEFERRED)

- Flow: microphone → audio → STT → **textual canonical meaning** → existing
  Character Runtime.
- Message UI may show audio playback plus an optional transcript
  ("Показать текст").
- Do **not** create a separate "voice memory." Canonical conversational meaning
  remains text / transcription.

---

## 17. Character voice / TTS — ACCEPTED FUTURE FEATURE (DEFERRED)

- The character may answer with text and an **optional** synthesized voice.
- Voice identity lives in a presentation / media **VoiceProfile**, **not** as a
  mandatory psychological Character Package property.
- Potential settings: character voice on/off; auto-play voice; show text; speech
  rate.

---

## 18. Phone-call mode — DEFERRED

- Not required before first Companion release.
- UI must not architecturally prevent a future call button.
- A future mode needs: streaming STT; streaming / low-latency generation;
  streaming TTS; voice-activity / end-of-turn detection; interruption /
  barge-in; cancellation of current speech; latency handling.

---

## 19. Character video messages (outbound) — DEFERRED

- Not required for first release.
- A future outbound video may combine character visual identity + generated
  expression / motion + TTS + lip-sync / video generation.
- The message / attachment model must not make future video impossible.

---

## 20. Scheduler / "write to me later" — ACCEPTED PRODUCT DIRECTION

Example: *"Кира, напиши мне через час."*

- The LLM **must not** directly create arbitrary OS / background jobs.
- Target chain: conversation → schedule proposal / intent → **deterministic
  validator / scheduler** → durable scheduled action → trigger → Character
  Runtime → message → notification.
- UI should be able to display active scheduled actions, e.g.
  *"Кира напишет в 14:35" · [Изменить] [Отменить]*.
- Explicit scheduled messages are **higher priority** than autonomous character
  initiative.

---

## 21. Autonomous character initiative — DEFERRED

- Character-initiated messages **without** explicit user scheduling require a
  future **Initiative Policy**.
- That policy must include: frequency controls; quiet hours; user opt-in; rate
  limits; reason / basis; notification settings.
- **No unrestricted LLM background loop.**

---

## 22. Notifications — ACCEPTED

- Relevant for: scheduled character message; image-generation completed;
  possibly future character initiative; provider / model status where useful.
- A notification click should eventually open the relevant conversation.
- Prefer a platform-specific notification adapter.

---

## 23. Provider registry — ACCEPTED

- Companion supports **multiple interchangeable providers**.
- Target provider families: DeepSeek; OpenAI; Qwen / Alibaba-compatible; Local /
  Ollama; future compatible providers.
- **Do not architect the UI around a single provider.** (`COMPANION_PROVIDER`
  selection, currently `fake` | `local`, is the seed of this registry.)

---

## 24. Model roles — ACCEPTED

- Do not force one model to do every task. Conceptual roles: **main dialogue;
  vision / image understanding; image generation; speech-to-text;
  text-to-speech; realtime / phone; local fallback / alternative.**
- Each role may use a different provider / model.
- Normal chat data goes **only** to the provider selected for that role.
- **No silent cross-provider duplication.**

---

## 25. User API keys — ACCEPTED SECURITY REQUIREMENT

- The user may bring their own provider credentials.
- Secrets **must not** be stored in React `localStorage`, plaintext JSON, the
  conversation DB, chat history, prompts, logs, debug manifests, crash reports,
  or source control.
- Desktop target: local backend → **Windows secure credential storage / DPAPI**
  or an equivalent secure vault.
- The frontend must **not** receive the raw secret back after storage.
- UI exposes only status: Connected · Not connected · Replace · Remove · Test.
- **Never log secrets.**

---

## 26. Provider settings UX — ACCEPTED

- Settings should explain models in **user-facing terms**, not only raw
  technical IDs. Example framing: DeepSeek — strong character / dialogue
  reasoning; OpenAI — broad multimodal / image / speech ecosystem; Qwen —
  alternative compatible cloud family; Local — privacy / no per-token cloud
  billing, requires adequate local hardware / model.
- Exact provider / model recommendations are **changeable data**, not hardcoded
  forever into visual application code.

---

## 27. Cost / fallback safety — ACCEPTED

- **No automatic paid-cloud fallback by default.** If the local provider fails,
  do **not** silently use OpenAI / DeepSeek and incur cost. (Already true in
  `LOCAL_LLM_PROVIDER_V1`: `local` never degrades to `fake` or a remote
  provider; unknown modes are hard errors.)
- Future controls: warn on large context; usage / cost estimates; per-response
  limit; explicit fallback permission.

---

## 28. Local model — ACCEPTED

- A local provider already exists (`services/character_companion/local_provider.py`,
  loopback-only, no credentials, no retry, no cloud fallback).
- Future UX should support local-model configuration.
- **Known issue from the real smoke:** the KIRA Grounded request (~10k tokens)
  can exceed small default context windows such as 4096. Final-release work may
  require `LOCAL_LLM_NUM_CTX` (or equivalent model-context configuration) and a
  real KIRA-capable local model.
- Local mode is **not** permanently tied to one model name
  (`LOCAL_LLM_MODEL` is configuration; default `llama3` is only a default).

---

## 29. Mobile readiness — ACCEPTED ARCHITECTURAL REQUIREMENT

- **First release remains desktop / Windows-first.** Mobile app implementation
  is **DEFERRED**.
- Desktop architecture must **not block** a future mobile client:
  - the Companion / Core API is **client-independent**;
  - conversation identity does not depend on the device;
  - the Character Package does not depend on the platform;
  - attachment / message contracts should be portable;
  - appearance preferences allow platform-specific layouts;
  - secrets use a platform-specific secure-storage abstraction;
  - scheduler / notifications use a platform adapter;
  - **avoid public-contract dependence on absolute Windows filesystem paths.**

---

## 30. Mobile target direction — DEFERRED implementation, ACCEPTED direction

- Preferred first mobile architecture: **Mobile client → secure Companion API →
  Companion backend on the user's PC.** This permits a local RTX model on the
  PC with the phone as a lightweight client, sharing the same character /
  runtime / history.
- A synchronized / cloud backend is optional and separate.
- Potential client: React Native or an equivalent native / mobile client.
- **Do not implement mobile now.**

---

## 31. Cross-device continuity — ACCEPTED LONG-TERM REQUIREMENT

- The same character must **not** become a different identity merely because the
  user changes device.
- Future goal: desktop and mobile can access the same intended continuity /
  history.
- **Do not implement sync in the current desktop MVP** unless separately
  authorized.

---

## 32. FIRST_RELEASE — required scope

Before **KIRA COMPANION MVP READY**, at least the following are required
(**FIRST_RELEASE**):

1. Working Companion **desktop chat**.
2. **Accepted KIRA** as the catalog character (accepted package only).
3. **Multi-chat foundation** — basic multi-chat listing per character (§9).
4. **Scene / no-scene new-dialog UX** (§7 A and B).
5. **Scenario fields** — editable location / time / situation / mood, reviewable
   before start.
6. **Random-scenario foundation** — deterministic, if reasonably bounded (§8);
   no LLM requirement for the first version.
7. **Cinematic experience implementation** (§3, §4, §11).
8. **Switchable appearance infrastructure** sufficient to later add Literary
   without re-architecture (§2).
9. **Persistent character portrait** (§4).
10. **Optional scene image + async generation UX foundation** — job states and
    non-blocking feedback (§5, §6).
11. **Focus mode** (§11).
12. **Secure provider settings / credential-vault foundation** — DPAPI / secure
    vault; no secret to frontend; status-only UI (§25).
13. **Provider registry foundations as actually implemented / approved** —
    DeepSeek / OpenAI / registry seams, only to the extent implemented and
    approved (§23, §24).
14. **Local provider configuration incl. adequate context handling** —
    e.g. `LOCAL_LLM_NUM_CTX` or equivalent (§28).
15. **A real successful KIRA local / provider acceptance path** — at least one
    real end-to-end KIRA turn that completes successfully.
16. **Windows packaging.**
17. **Restart / history persistence** — sessions and transcripts survive
    backend and client restart (already true in the MVP).
18. **Bounded error handling** — provider failure returns a bounded error and
    never corrupts prior conversation (already true in the MVP).

Do **not** automatically add every future multimedia feature to this list.

---

## 33. DEFERRED — not required for first release

Explicitly **not** required before **KIRA COMPANION MVP READY**:

- full phone-call mode (§18);
- outbound generated character video messages (§19);
- unrestricted autonomous character initiative (§21);
- full book / library subsystem (§14);
- heavy video understanding (§13);
- mobile app implementation (§29, §30);
- cloud sync / backend (§31);
- a third / fourth visual experience (§2);
- full Literary implementation, if the release prioritizes Cinematic first (§2);
- sophisticated attachment ingestion beyond the explicitly authorized safe
  subset (§13, §15);
- LLM evolution proposer (the deterministic proposer stays the reference; no
  LLM proposer).

---

## 34. OPEN_OWNER_DECISION — remaining open choices

Recorded, **not** decided here:

- final Cinematic visual details;
- exact portrait / scene-image proportions;
- exact chat-list / chat-card appearance;
- the exact third experience preset, if any;
- final provider recommendation defaults;
- which multimedia capabilities, if any, are promoted into first release;
- final mobile visual design;
- final rules and naming/UX for **shared vs isolated continuity** (§10).

---

## 35. Anti-gate-creep

This document records **product direction**. It must **not** be read as
authorization to implement all deferred features before **KIRA COMPANION MVP
READY**. The **FIRST_RELEASE** and **DEFERRED** classifications are intentional
and binding: work toward first release is scoped by §32 only, and anything in
§33 requires separate authorization to start.
