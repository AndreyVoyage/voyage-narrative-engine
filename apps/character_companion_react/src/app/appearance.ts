/**
 * Presentation-only appearance abstraction. No backend / psychology / memory
 * dependency — this only selects which renderer + focus layout the UI uses, and
 * remembers the last focus layout per viewer via localStorage.
 *
 * CINEMATIC is the implemented experience. LITERARY is an accepted future
 * preset and is intentionally NOT selectable yet (no broken mode exposed).
 */

export const EXPERIENCE_PRESETS = ["cinematic", "literary"] as const;
export type ExperiencePreset = (typeof EXPERIENCE_PRESETS)[number];

export const IMPLEMENTED_EXPERIENCES: ExperiencePreset[] = ["cinematic"];

export function isExperienceImplemented(preset: ExperiencePreset): boolean {
  return IMPLEMENTED_EXPERIENCES.includes(preset);
}

export const FOCUS_LAYOUTS = ["background", "side_gallery", "chat_only"] as const;
export type FocusLayout = (typeof FOCUS_LAYOUTS)[number];

export interface AppearanceProfile {
  experiencePreset: ExperiencePreset; // always "cinematic" in this release
  focusModeLayout: FocusLayout;
}

export const DEFAULT_APPEARANCE: AppearanceProfile = {
  experiencePreset: "cinematic",
  focusModeLayout: "background",
};

const FOCUS_KEY = "companion.focusModeLayout";

export function loadAppearance(): AppearanceProfile {
  let focus: FocusLayout = DEFAULT_APPEARANCE.focusModeLayout;
  try {
    const raw = window.localStorage.getItem(FOCUS_KEY);
    if (raw && (FOCUS_LAYOUTS as readonly string[]).includes(raw)) {
      focus = raw as FocusLayout;
    }
  } catch {
    /* private mode / disabled storage — fall back to default */
  }
  return { ...DEFAULT_APPEARANCE, focusModeLayout: focus };
}

export function rememberFocusLayout(layout: FocusLayout): void {
  try {
    window.localStorage.setItem(FOCUS_KEY, layout);
  } catch {
    /* ignore */
  }
}

export function nextFocusLayout(current: FocusLayout): FocusLayout {
  const i = FOCUS_LAYOUTS.indexOf(current);
  return FOCUS_LAYOUTS[(i + 1) % FOCUS_LAYOUTS.length];
}
