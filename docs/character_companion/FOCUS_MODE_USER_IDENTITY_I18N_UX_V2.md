# Focus Mode V2 · Participant Identity · Local User Profile · UI i18n — UX contract

Status: FIRST_RELEASE (presentation / client only). No Character Runtime, Memory,
provider, Character Package, epistemics, evolution or credential-storage change.

## 1. Focus Mode — three modes, all production-quality

The three concepts are unchanged: `BACKGROUND`, `SIDE_GALLERY`, `CHAT_ONLY`
(`src/app/appearance.ts` `FOCUS_LAYOUTS`). No new modes.

All three render one **centered conversation canvas** (`.focus-canvas`,
`max-width: var(--focus-canvas-max)` ≈ 1040 px, `margin: 0 auto`, comfortable
gutters). Messages stay left/right differentiated but never drift to the physical
screen edges on wide monitors; on narrow desktop widths there is no horizontal
scroll. The composer is aligned to the same canvas.

### BACKGROUND
Primary cinematic experience. Background source priority
(`src/app/focusBackground.ts` `resolveFocusBackground`):

1. locally-selected focus image for this session (only while that ref is still a
   READY generated image);
2. current conversation cover;
3. KIRA identity portrait fallback.

Rendered fullscreen with `transform: scale`, mild `blur`, and a readability
**scrim** (`.focus-bg-scrim`): a horizontal gradient that darkens the edges plus
a vertical gradient that darkens harder beneath the message column. Message
surfaces are semi-opaque (`--focus-msg-surface`). **Source pixels are never
modified** — only CSS.

"Set as background" (`focus.gallery.makeBackground`) is a **local view
preference** stored per session in `localStorage`
(`companion.focusBackgroundBySession`). It never writes Scene facts, the scene
cover, Character Memory, Runtime State or the Character Package. If the
referenced image is later deleted, resolution silently falls back to
cover → portrait.

### SIDE_GALLERY
Left visual rail + centered chat. Rail contents
(`src/app/focusGallery.ts` `buildFocusGallery`): identity portrait (always
first) → distinct scene cover → every READY generated image, de-duplicated.
Controls: `←` / index counter `N / M` / `→`, plus a thumbnail strip. For a
generated image the rail offers **"Set as cover"** (reuses the existing explicit
`client.setSceneCover` action) and **"Set as background"** (local preference).
Selecting an image as background does not make it factual.

### CHAT_ONLY
No background image, no rail — just the centered canvas with participant
identity. The cleanest long-reading mode.

## 2. Participant identity

Shown per **speaker group**, not per message. Consecutive messages from the same
speaker share one identity header (`[avatar] Name`).

- Character: approved KIRA portrait (`portraitFor(characterId)` →
  `/characters/kira/KIRA_release_portrait_v1_APPROVED.png`), display name "Кира".
  A generated Scene image never replaces the participant avatar.
- User: local profile display name + a neutral initials chip
  (`userProfileInitials`). No large avatar next to every message.

## 3. Local User Profile V1 (`src/app/userProfile.ts`)

`LocalUserProfile = { displayName, avatarKind, avatarRef, locale }`.

- Presentation only. Persisted in `localStorage`
  (`companion.localUserProfile`). **Never** written to the Character Package,
  Runtime State, Character Memory, Relationship or Psychology.
- Default `displayName` is empty and renders as the localized "Пользователь" /
  "User" label; editable in Settings → Профиль.
- `avatarKind: "image"` is reserved for a future safe profile-photo flow
  (Attachment Security Gateway) and is **not selectable** — no `<input
  type=file>` anywhere. UI shows "Фото профиля — скоро".
- Shape is account-shaped so a future `AccountProfile` can replace or
  synchronize it without any change to Focus Mode message rendering. No login,
  password, email, cloud account, sync or remote identity in this slice.

## 4. Polished scrolling

- Narrow (8 px), rounded, subdued custom scrollbars via `::-webkit-scrollbar*`
  and `scrollbar-width` / `scrollbar-color`, themed with CSS variables
  (`--c-scroll-*`). Scrollbars are never fully hidden.
- Conversation scroll: a new message auto-follows only when the reader is
  already near the bottom; while reading history the view is not forced down.
  A compact "↓ Новые сообщения" affordance appears otherwise. History / layout
  changes jump without animation.

## 5. Built-in UI internationalization (`src/i18n/`)

- No package. `index.ts` (React-free core) + `ru/en/es/zhCN/pt` dictionaries +
  `react.tsx` (`LocaleProvider` / `useLocale`). Stable dot-keys; components call
  `t("key")`, never inline `locale === "ru" ? …`.
- Locales: `ru` (default), `en`, `es`, `zh-CN`, `pt`. Selector in Settings →
  Профиль → "Язык интерфейса"; changing it updates the UI immediately (React
  state) and persists to `localStorage` (`companion.uiLocale`). No backend
  restart.
- Translated: application chrome only (navigation, Characters, Dialogues, New
  dialog, Search, Settings, provider settings, role/scene-field labels, random
  scenario, Focus mode, gallery, composer, empty states, image-job states,
  common provider/config errors, Local Profile, attachment "coming soon"
  labels).
- **Never** translated: user messages, character replies, Character Package
  claims, Scene content, provider response text. Changing UI language does not
  retroactively translate conversation history.
- **UI language ≠ character-response language.** The Grounded prompt is
  untouched; KIRA is not forced to English because the interface is English. A
  separate conversation-language preference may be added later.
- Backend error contracts are unchanged: stable error **codes** are mapped to
  localized text (`errorText`); unknown codes fall back to a safe localized
  generic message. Stack traces are never surfaced.

## 6. Not in this slice

Real image/video generation providers/models
(`MEDIA_PROVIDERS_AND_MODEL_ROLES_V1`), any NSFW provider, arbitrary file
upload, Literary full UI, phone calls, TTS, STT, macOS/Linux credential vaults,
LLM Evolution Proposer, account/auth systems.
