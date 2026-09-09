/**
 * Local User Profile — presentation only.
 *
 * This describes how the *local* viewer appears in the UI (Focus Mode identity,
 * composer side). It is NOT identity, authentication or account state and it is
 * NEVER written to the Character Package, Runtime State, Character Memory,
 * Relationship or Psychology. It lives entirely in this browser via
 * localStorage.
 *
 * Shape is deliberately account-shaped so a future `AccountProfile` can replace
 * or synchronize `LocalUserProfile` without any change to message rendering:
 * consumers only read `{ displayName, avatarKind, avatarRef }`.
 */

import { normalizeLocale, type UiLocale } from "../i18n/index.js";

/** `placeholder` → neutral initials chip. `image` is reserved for a future
 * safe profile-photo flow (Attachment Security Gateway) and is not selectable
 * yet — no file picker exists. */
export type AvatarKind = "placeholder" | "image";

export interface LocalUserProfile {
  displayName: string;
  avatarKind: AvatarKind;
  /** Only meaningful when avatarKind === "image"; always null for now. */
  avatarRef: string | null;
  locale: UiLocale;
}

export const DEFAULT_USER_PROFILE: LocalUserProfile = {
  displayName: "",
  avatarKind: "placeholder",
  avatarRef: null,
  locale: "ru",
};

const MAX_NAME = 40;

export function normalizeUserProfile(input: unknown): LocalUserProfile {
  const raw = (input ?? {}) as Partial<Record<keyof LocalUserProfile, unknown>>;
  const name = typeof raw.displayName === "string" ? raw.displayName.trim().slice(0, MAX_NAME) : "";
  const avatarKind: AvatarKind = raw.avatarKind === "image" ? "image" : "placeholder";
  return {
    displayName: name,
    avatarKind,
    // image avatars are not wired yet — never hydrate a ref
    avatarRef: null,
    locale: normalizeLocale(raw.locale),
  };
}

/** Name actually shown, falling back to the localized default label. */
export function resolveDisplayName(profile: LocalUserProfile, fallback: string): string {
  return profile.displayName.trim() || fallback;
}

/** 1–2 letter initials chip for the placeholder avatar. */
export function userProfileInitials(profile: LocalUserProfile, fallback: string): string {
  const source = profile.displayName.trim() || fallback;
  const parts = source.split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "•";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

// -- serialization (pure; unit-tested headlessly) -----------------------
export function serializeUserProfile(profile: LocalUserProfile): string {
  const normalized = normalizeUserProfile(profile);
  return JSON.stringify(normalized);
}

export function parseUserProfile(raw: string | null | undefined): LocalUserProfile {
  if (!raw) return { ...DEFAULT_USER_PROFILE };
  try {
    return normalizeUserProfile(JSON.parse(raw));
  } catch {
    return { ...DEFAULT_USER_PROFILE };
  }
}

// -- per-viewer persistence -------------------------------------------
export const USER_PROFILE_STORAGE_KEY = "companion.localUserProfile";

export function loadUserProfile(): LocalUserProfile {
  try {
    if (typeof window !== "undefined" && window.localStorage) {
      return parseUserProfile(window.localStorage.getItem(USER_PROFILE_STORAGE_KEY));
    }
  } catch {
    /* private mode / disabled storage */
  }
  return { ...DEFAULT_USER_PROFILE };
}

export function saveUserProfile(profile: LocalUserProfile): LocalUserProfile {
  const normalized = normalizeUserProfile(profile);
  try {
    if (typeof window !== "undefined" && window.localStorage) {
      window.localStorage.setItem(USER_PROFILE_STORAGE_KEY, serializeUserProfile(normalized));
    }
  } catch {
    /* ignore */
  }
  return normalized;
}
