/**
 * Pure builder for the SIDE_GALLERY rail contents. No React, no client.
 *
 * The rail is a bounded per-conversation gallery, NOT a media-library
 * subsystem:
 *   - the KIRA identity portrait (always first);
 *   - the current scene cover, only if it is a distinct image;
 *   - every READY generated image for the current session.
 * Duplicates (the cover also being one of the ready images) are collapsed.
 */

export type FocusGalleryItemKind = "portrait" | "cover" | "generated";

export interface FocusGalleryItem {
  key: string;
  src: string;
  kind: FocusGalleryItemKind;
  /** stable image ref for generated items (used by cover/background actions) */
  resultRef: string | null;
}

export interface FocusGalleryInputs {
  portraitUrl: string;
  coverRef: string | null;
  readyRefs: string[];
  imageUrl: (ref: string) => string;
}

export function buildFocusGallery(input: FocusGalleryInputs): FocusGalleryItem[] {
  const items: FocusGalleryItem[] = [
    { key: "portrait", src: input.portraitUrl, kind: "portrait", resultRef: null },
  ];

  const readySet = new Set(input.readyRefs);
  if (input.coverRef && !readySet.has(input.coverRef)) {
    items.push({
      key: `cover:${input.coverRef}`,
      src: input.imageUrl(input.coverRef),
      kind: "cover",
      resultRef: input.coverRef,
    });
  }

  const seen = new Set<string>();
  for (const ref of input.readyRefs) {
    if (!ref || seen.has(ref)) continue;
    seen.add(ref);
    items.push({
      key: `gen:${ref}`,
      src: input.imageUrl(ref),
      kind: "generated",
      resultRef: ref,
    });
  }
  return items;
}

/** Clamp a gallery index into range (wrapping), tolerating an empty list. */
export function clampGalleryIndex(index: number, total: number): number {
  if (total <= 0) return 0;
  return ((index % total) + total) % total;
}
