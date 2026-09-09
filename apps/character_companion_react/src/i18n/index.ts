/**
 * Lightweight built-in UI internationalization — no dependency, no package.
 *
 * Scope: APPLICATION CHROME ONLY. Conversation messages, character replies,
 * Scene content and provider output are never routed through `translate()`.
 * Changing the UI locale never rewrites conversation history and never changes
 * the character-response language or the Grounded prompt.
 *
 * This module is React-free so the headless structural checks can import it
 * directly. The React binding lives in `./react.tsx`.
 */

import { ru, type TranslationKey } from "./ru.js";
import { en } from "./en.js";
import { es } from "./es.js";
import { zhCN } from "./zhCN.js";
import { pt } from "./pt.js";

export type { TranslationKey } from "./ru.js";

export const UI_LOCALES = ["ru", "en", "es", "zh-CN", "pt"] as const;
export type UiLocale = (typeof UI_LOCALES)[number];

export const DEFAULT_LOCALE: UiLocale = "ru";

/** Native-name labels for the language selector. */
export const LOCALE_LABELS: Record<UiLocale, string> = {
  ru: "Русский",
  en: "English",
  es: "Español",
  "zh-CN": "简体中文",
  pt: "Português",
};

const DICTS: Record<UiLocale, Record<TranslationKey, string>> = {
  ru,
  en,
  es,
  "zh-CN": zhCN,
  pt,
};

export function isUiLocale(value: unknown): value is UiLocale {
  return typeof value === "string" && (UI_LOCALES as readonly string[]).includes(value);
}

/** Coerce anything (stored value, `navigator.language`, …) to a supported locale. */
export function normalizeLocale(value: unknown): UiLocale {
  if (isUiLocale(value)) return value;
  if (typeof value === "string") {
    const lower = value.toLowerCase();
    if (lower.startsWith("zh")) return "zh-CN";
    const short = lower.split(/[-_]/)[0];
    if (isUiLocale(short)) return short;
  }
  return DEFAULT_LOCALE;
}

type Params = Record<string, string | number>;

function interpolate(template: string, params?: Params): string {
  if (!params) return template;
  return template.replace(/\{(\w+)\}/g, (whole, name: string) =>
    Object.prototype.hasOwnProperty.call(params, name) ? String(params[name]) : whole,
  );
}

/**
 * Resolve one UI string. Falls back locale → Russian → the raw key, so a missing
 * translation degrades to a readable label instead of blank text.
 */
export function translate(locale: UiLocale, key: TranslationKey, params?: Params): string {
  const dict = DICTS[locale] ?? ru;
  const template = dict[key] ?? ru[key] ?? key;
  return interpolate(template, params);
}

/** Stable backend error codes → localized frontend text. Unknown codes get a
 * safe generic message; stack traces are never surfaced. */
const ERROR_CODE_KEYS: Record<string, TranslationKey> = {
  provider_not_configured: "error.provider_not_configured",
  missing_credential: "error.missing_credential",
  provider_failed: "error.provider_failed",
  provider_unavailable: "error.provider_unavailable",
  generator_unavailable: "error.generator_unavailable",
  backend_unavailable: "error.backend_unavailable",
  empty_message: "error.empty_message",
  assistant_not_configured: "error.assistant_not_configured",
  assistant_failed: "error.assistant_failed",
};

export function errorText(locale: UiLocale, code: string | null | undefined): string {
  const key: TranslationKey | undefined = code ? ERROR_CODE_KEYS[code] : undefined;
  return translate(locale, key ?? "error.unknown");
}

// -- locale persistence (per viewer, presentation-only) -------------------
export const LOCALE_STORAGE_KEY = "companion.uiLocale";

export function loadLocale(): UiLocale {
  try {
    if (typeof window !== "undefined" && window.localStorage) {
      const raw = window.localStorage.getItem(LOCALE_STORAGE_KEY);
      if (raw) return normalizeLocale(raw);
    }
  } catch {
    /* private mode / disabled storage */
  }
  return DEFAULT_LOCALE;
}

export function saveLocale(locale: UiLocale): void {
  try {
    if (typeof window !== "undefined" && window.localStorage) {
      window.localStorage.setItem(LOCALE_STORAGE_KEY, locale);
    }
  } catch {
    /* ignore */
  }
}
