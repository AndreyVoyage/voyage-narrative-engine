/**
 * Character identity portrait resolver.
 *
 * The identity portrait is presentation data ONLY. It is distinct from a Scene
 * cover / generated Scene image, and no Scene-generated image can replace it --
 * feature code always calls `portraitFor(characterId)` for the portrait slot and
 * only ever uses `imageUrl(resultRef)` for Scene visuals.
 *
 * KIRA resolves to the owner-approved release portrait
 * (`KIRA_test02_bar_romance_v1_APPROVED.png`, byte-identical copy of the canon
 * asset, served from `public/`). Any other / future character falls back to the
 * neutral placeholder.
 */

import { PORTRAIT_PLACEHOLDER_DATA_URI } from "./portraitPlaceholder.js";

/** app-relative static paths under `public/` */
const RELEASE_PORTRAITS: Readonly<Record<string, string>> = {
  kira: "/characters/kira/KIRA_release_portrait_v1_APPROVED.png",
};

function key(characterId: string | null | undefined): string {
  return (characterId ?? "").trim().toLowerCase();
}

export function portraitFor(characterId: string | null | undefined): string {
  return RELEASE_PORTRAITS[key(characterId)] ?? PORTRAIT_PLACEHOLDER_DATA_URI;
}

/** True when a bound release portrait exists (i.e. not the fallback placeholder). */
export function hasReleasePortrait(characterId: string | null | undefined): boolean {
  return Object.prototype.hasOwnProperty.call(RELEASE_PORTRAITS, key(characterId));
}
