/**
 * Focus Mode BACKGROUND source resolution + a presentation-only per-session
 * "use this image as my focus background" preference.
 *
 * IMPORTANT: choosing a focus background is a LOCAL VIEW preference. It never
 * touches Scene facts, the scene cover, Character Memory, Runtime State or the
 * Character Package — it is stored only in this browser, keyed by session id and
 * a stable image reference. If the referenced image later disappears (explicit
 * deletion), resolution silently falls back to the conversation cover and then
 * the identity portrait.
 *
 * This module is client-free and DOM-guarded so the headless structural checks
 * can exercise the priority logic directly.
 */

import { portraitFor } from "../assets/portrait.js";

export type FocusBackgroundKind = "selected" | "cover" | "portrait";

export interface FocusBackgroundResolution {
  /** CSS url() value / <img> src for the atmospheric background layer. */
  url: string;
  kind: FocusBackgroundKind;
}

export interface FocusBackgroundInputs {
  /** locally-selected generated image ref for this session, if any */
  selectedRef: string | null;
  /** generated image refs currently READY for this session */
  readyRefs: string[];
  /** current conversation cover as a ready-to-use URL, if any */
  coverUrl: string | null;
  /** resolves a stored image ref to a URL */
  imageUrl: (ref: string) => string;
  characterId: string | null;
}

/**
 * BACKGROUND priority:
 *   1. locally-selected focus image (only if that ref is still READY)
 *   2. current conversation cover
 *   3. KIRA identity portrait fallback
 */
export function resolveFocusBackground(input: FocusBackgroundInputs): FocusBackgroundResolution {
  if (input.selectedRef && input.readyRefs.includes(input.selectedRef)) {
    return { url: input.imageUrl(input.selectedRef), kind: "selected" };
  }
  if (input.coverUrl) {
    return { url: input.coverUrl, kind: "cover" };
  }
  return { url: portraitFor(input.characterId), kind: "portrait" };
}

// -- per-session local preference (presentation only) --------------------
export const FOCUS_BG_STORAGE_KEY = "companion.focusBackgroundBySession";

type Store = Record<string, string>; // sessionId -> image ref

function readStore(): Store {
  try {
    if (typeof window !== "undefined" && window.localStorage) {
      const raw = window.localStorage.getItem(FOCUS_BG_STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as unknown;
        if (parsed && typeof parsed === "object") return parsed as Store;
      }
    }
  } catch {
    /* ignore */
  }
  return {};
}

function writeStore(store: Store): void {
  try {
    if (typeof window !== "undefined" && window.localStorage) {
      window.localStorage.setItem(FOCUS_BG_STORAGE_KEY, JSON.stringify(store));
    }
  } catch {
    /* ignore */
  }
}

export function getFocusBackgroundRef(sessionId: string | null): string | null {
  if (!sessionId) return null;
  return readStore()[sessionId] ?? null;
}

export function setFocusBackgroundRef(sessionId: string, ref: string): void {
  const store = readStore();
  store[sessionId] = ref;
  writeStore(store);
}

export function clearFocusBackgroundRef(sessionId: string): void {
  const store = readStore();
  delete store[sessionId];
  writeStore(store);
}
