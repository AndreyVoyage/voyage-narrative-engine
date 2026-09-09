/**
 * Pure helpers for the Settings panel. No React, no client, no secret handling
 * beyond "clear the input after submit". Structural checks exercise these.
 */

import { CompanionSettingsView, ProviderCardView } from "../client/types.js";

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
