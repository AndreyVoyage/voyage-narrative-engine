/**
 * Pure helpers for the Settings panel. No React, no client, no secret handling
 * beyond "clear the input after submit". Structural checks exercise these.
 */

import { CompanionSettingsView, ModelView, ProviderCardView } from "../client/types.js";
import type { TranslationKey } from "../i18n/index.js";

/** Canonical presentation order for the "models by task" section. */
export const MODEL_ROLE_ORDER = [
  "DIALOGUE", "VISION", "IMAGE_GENERATION", "VIDEO_GENERATION",
  "STT", "TTS", "REALTIME", "WRITING_ASSISTANT", "LOCAL_ALTERNATIVE",
] as const;

/** i18n key for a model-role display name (falls back to the raw id). */
export function roleLabelKey(role: string): TranslationKey {
  return (`role.${role}`) as TranslationKey;
}

/** i18n key for a role-readiness status. */
export function readinessLabelKey(readiness: string): TranslationKey {
  return (`readiness.${readiness}`) as TranslationKey;
}

/** Providers (by id) from the catalog that can serve a given role -- data-driven,
 * never a hardcoded `provider === "openai" && role === ...` check. */
export function providersForRole(view: CompanionSettingsView, role: string): ProviderCardView[] {
  return view.providers.filter((p) => p.supportedRoles.includes(role));
}

/** Models offered by one provider that satisfy a given role, filtered by the
 * model's own capability list. */
export function modelsForRole(card: ProviderCardView | undefined, role: string): ModelView[] {
  if (!card) return [];
  return card.models.filter((m) => {
    if (role === "LOCAL_ALTERNATIVE") {
      return m.capabilities.includes("DIALOGUE") && m.capabilities.includes("LOCAL");
    }
    return m.roles.includes(role);
  });
}

/** A configured media role is NOT the same as an implemented feature. */
export function roleIsConfiguredButNotImplemented(readiness: string, runtimeWired: boolean): boolean {
  return !runtimeWired && (readiness === "FUTURE_NOT_WIRED" || readiness === "CONFIGURED_CREDENTIAL_MISSING");
}

/** A secret input is single-use: after a successful submit it is cleared and
 * the raw value is never held again. */
export function secretDraftAfterSubmit(): string {
  return "";
}

export function providerStatusLabel(card: ProviderCardView): string {
  if (!card.credentialRequired) return "Готов";
  return card.connected ? "Подключено" : "Не подключено";
}

/** Which actions a provider card should offer. */
export function providerActions(card: ProviderCardView): string[] {
  if (!card.credentialRequired) return ["Проверить"];
  return card.connected ? ["Заменить ключ", "Удалить ключ", "Проверить"] : ["Подключить", "Проверить"];
}

export function roleIsRuntimeWired(view: CompanionSettingsView, role: string): boolean {
  return view.runtimeWiredRoles.includes(role);
}

export function localContextWarning(view: CompanionSettingsView): string | null {
  return view.local.numCtxWarning
    ? `Размер контекста меньше рекомендуемого (${view.local.kiraSafeHint}); ответ KIRA может обрезаться.`
    : null;
}

/** DIALOGUE operational context-budget presets (exact backend integer values). */
export const DIALOGUE_CONTEXT_BUDGET_PRESETS = [
  { value: 16384, label: "16K" },
  { value: 32768, label: "32K" },
  { value: 65536, label: "64K" },
  { value: 131072, label: "128K" },
] as const;

/** True only for an integer within the backend-advertised range. No clamp, no
 * rounding -- an out-of-range or non-integer value is simply invalid. */
export function isValidDialogueContextBudget(value: number, view: CompanionSettingsView): boolean {
  const b = view.dialogueContextBudget;
  return Number.isInteger(value) && value >= b.min && value <= b.max;
}

/** Auto cloud fallback must stay OFF by default. */
export function autoFallbackDefault(): boolean {
  return false;
}

/** Never render a raw secret. This asserts the shape the panel is allowed to read. */
export function safeProviderView(card: ProviderCardView): {
  displayName: string;
  status: string;
  maskedTail: string | null;
  model: string;
} {
  return {
    displayName: card.displayName,
    status: providerStatusLabel(card),
    maskedTail: card.maskedTail,      // "…abcd" hint only, never the key
    model: card.configuredModel,
  };
}
