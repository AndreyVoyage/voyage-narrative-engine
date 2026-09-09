/**
 * React binding for the built-in i18n. A single top-level provider holds the
 * active locale in React state, so changing the language re-renders the UI
 * immediately — no reload, no backend restart. The selected locale is persisted
 * per viewer in localStorage.
 */

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import {
  DEFAULT_LOCALE,
  errorText,
  loadLocale,
  saveLocale,
  translate,
  type TranslationKey,
  type UiLocale,
} from "./index.js";

export type TFunction = (key: TranslationKey, params?: Record<string, string | number>) => string;

interface LocaleContextValue {
  locale: UiLocale;
  setLocale: (locale: UiLocale) => void;
  t: TFunction;
  tError: (code: string | null | undefined) => string;
}

const LocaleContext = createContext<LocaleContextValue | null>(null);

export function LocaleProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<UiLocale>(() => loadLocale());

  const setLocale = useCallback((next: UiLocale) => {
    setLocaleState(next);
    saveLocale(next);
  }, []);

  const value = useMemo<LocaleContextValue>(
    () => ({
      locale,
      setLocale,
      t: (key, params) => translate(locale, key, params),
      tError: (code) => errorText(locale, code),
    }),
    [locale, setLocale],
  );

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useLocale(): LocaleContextValue {
  const ctx = useContext(LocaleContext);
  if (ctx) return ctx;
  // Defensive fallback if a component renders outside the provider (should not
  // happen in this app) — still returns a working translator.
  return {
    locale: DEFAULT_LOCALE,
    setLocale: () => undefined,
    t: (key, params) => translate(DEFAULT_LOCALE, key, params),
    tError: (code) => errorText(DEFAULT_LOCALE, code),
  };
}
