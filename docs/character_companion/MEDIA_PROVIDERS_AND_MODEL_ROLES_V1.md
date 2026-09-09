# Media Providers and Model Roles V1 — configuration contract

Status: FIRST_RELEASE (configuration foundation). This slice configures
providers / models / capabilities. It performs **no** real image, video,
vision, speech or realtime operation, and it does not change Character Runtime
prompt construction. `DIALOGUE` behaviour is unchanged.

## Roles

Canonical roles (`services/character_companion/provider_registry.py` `ALL_ROLES`,
presentation order `ROLE_DISPLAY_ORDER`):

`DIALOGUE`, `VISION`, `IMAGE_GENERATION`, `VIDEO_GENERATION` (added additively),
`STT`, `TTS`, `REALTIME`, `LOCAL_ALTERNATIVE`.

`RUNTIME_WIRED_ROLES = ("DIALOGUE",)` — only DIALOGUE is routed at
`RuntimeService.turn`. Every media role is metadata consumed by *future*
adapters; the UI never presents one as an implemented feature.

Localized display names (all five UI locales): `role.<ROLE>` keys — Диалог /
Анализ изображений / Генерация изображений / Генерация видео / Распознавание
речи / Голос персонажа / Звонки · Realtime / Локальная модель.

## Provider registry — capability-driven catalog

`ProviderEntry` now owns a tuple of `ModelEntry` records. Each `ModelEntry` has:

- `capabilities` — from `DIALOGUE, VISION, IMAGE_GENERATION, VIDEO_GENERATION,
  STT, TTS, REALTIME, IMAGE_TO_IMAGE, CHARACTER_REFERENCE, LOCAL, CLOUD`;
  capability → role via `_CAP_TO_ROLE`.
- `status` — `available` | `unverified` | `deprecated`. Media models whose exact
  capabilities are not verified against current provider docs are
  **`unverified`**, never guessed as working.
- `content_policy_profile` — neutral: `STANDARD_ONLY`,
  `PROVIDER_POLICY_DEPENDENT`, `LOCAL_MODEL_POLICY`, `UNKNOWN` (default). The
  shipped catalog asserts **no** "provider X allows adult content" claim.
- optional media facts (`supports_reference_image`, `supports_image_to_image`,
  `supports_character_reference`, `supports_video`, `max_duration_seconds`) —
  `None` means UNKNOWN and is never fabricated.

`ProviderEntry.supported_roles`, `.capabilities`, `.model_catalog` are all
**derived** from the model list (backward-compatible id list preserved).

Existing providers preserved: `deepseek`, `openai`, `qwen`, `local`, `fake`.
No entry deleted. Media capabilities advertised only where a justified model
entry exists (e.g. `openai/gpt-image-1` → IMAGE_GENERATION, `unverified`;
`openai/sora-2` → VIDEO_GENERATION, `unverified`; `local/llava` → VISION,
`unverified`).

## Credentials

Credential belongs to the **provider**, not the role or model. One vault entry
(`credentials.py`) serves every role assigned to that provider. Role
assignments (`companion_settings.json`) carry `providerId` + `modelId` only —
never a secret. A cloud credential is **not** required to *save* a role; it is
required only when a future operation actually invokes the provider.

## Role assignment & validation

`SettingsStore.set_role` (authoritative catalog):

1. provider must exist;
2. provider must support the role (`unsupported_role`);
3. model must exist in that provider's catalog (`unknown_model`);
4. the model's capabilities must satisfy the role (`unsupported_model_role`);
5. empty `modelId` → first catalog model that supports the role.

Changing one role never mutates another. Old settings files load unchanged;
absent media roles simply default to unconfigured — no migration.

## Resolver (no provider call)

`provider_resolution.resolve_role_config(role, settings, vault)` returns
resolution **metadata only** — `providerId`, `modelId`, `providerConnected`,
`maskedTail`, `capabilities`, `contentPolicyProfile`, `modelStatus`,
`readiness`. It builds no executable media adapter, exposes no raw credential,
and performs **no** cross-provider fallback: the result reflects exactly the one
stored assignment. `CompanionService.resolve_media_role` /
`GET /api/companion/settings/resolve/<role>` expose it.

Readiness values: `READY` (DIALOGUE, credential satisfied),
`CONFIGURED_CREDENTIAL_MISSING`, `NOT_CONFIGURED`, `UNSUPPORTED` (stale pair),
`FUTURE_NOT_WIRED` (configured media role — connector arrives in a later slice).

`GET /api/companion/settings` now also returns `roleCatalog` (per-role
resolution + `providerIds`), `roleDisplayOrder`, and per-provider `models` +
`capabilities`.

## Settings UI

New **"Модели по задачам"** section: one row per role with a data-driven
provider `<select>` (catalog-filtered) + model `<select>` (capability-filtered)
+ a readiness / "Активно в рантайме" badge, plus a per-row
"Подключение будет выполнено на следующем этапе" line for configured media
roles. Provider cards keep their credential controls and gain a compact
capability-chip summary. A localized note —
"Доступность моделей зависит от провайдера и может меняться." — sits under the
section. No hardcoded model ids or `provider === "openai"` checks in React; no
raw key rendered; no file input.

## Not in this slice

Real image/video/vision/STT/TTS/realtime execution, `CompanionImageGenerator`
wiring, OpenAI Images / visual sibling repo, ComfyUI / Stable Diffusion, remote
catalog auto-fetch, a universal "NSFW mode" switch, any adult-content provider
selection or integration. `IMAGE_GENERATION` is now a first-class role but
"Создать изображение…" / "Кадр по контексту" still do **not** call it.

## ADULT_MEDIA_PROVIDER_RESEARCH_REQUIRED: YES

The registry can now carry policy-related capability metadata
(`contentPolicyProfile`, `supports_*`) but ships **provider-policy neutral**.
Selecting or integrating any adult-capable image/video provider must be a
separate task done against **current** provider API terms and content policies
(these change frequently). That is expected and is **not** a blocker for this
configuration layer.
