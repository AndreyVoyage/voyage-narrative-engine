import { useEffect } from "react";
import type { CharacterPublicProfile, ProfileMedia } from "../client/types.js";
import { portraitFor } from "../assets/portrait.js";
import { useLocale } from "../i18n/react.js";

interface Props {
  open: boolean;
  characterId: string | null;
  profile: CharacterPublicProfile | null;
  loading: boolean;
  imageUrl: (resultRef: string) => string;
  onClose: () => void;
}

/** Transport-safe media ref -> a URL the browser can load.
 *  "characters/…" is a curated static public asset; "images/…" is a served
 *  generated image. Anything else is refused (renders nothing). */
function mediaUrl(ref: string, imageUrl: (r: string) => string): string | null {
  if (ref.startsWith("characters/")) return "/" + ref;
  if (ref.startsWith("images/")) return imageUrl(ref);
  return null;
}

function MediaTile({
  item,
  imageUrl,
}: {
  item: ProfileMedia;
  imageUrl: (r: string) => string;
}) {
  const { t } = useLocale();
  const src = mediaUrl(item.sourceRef, imageUrl);
  if (!src) return null;
  const poster = item.thumbnailRef ? mediaUrl(item.thumbnailRef, imageUrl) : null;
  if (item.mediaType === "video") {
    return (
      <figure className="profile-media-tile profile-media-video">
        <video
          className="profile-media-el"
          src={src}
          poster={poster ?? undefined}
          controls
          preload="none"
          aria-label={item.title ?? t("profile.playVideo")}
        />
        {item.title && <figcaption className="profile-media-cap">{item.title}</figcaption>}
      </figure>
    );
  }
  return (
    <figure className="profile-media-tile profile-media-image">
      <img className="profile-media-el" src={src} alt={item.title ?? ""} loading="lazy" />
      {item.title && <figcaption className="profile-media-cap">{item.title}</figcaption>}
    </figure>
  );
}

/**
 * Right-side character detail drawer. Overlays the app; the app behind it stays
 * mounted and is dimmed + blurred by the backdrop. Opening / closing never
 * touches chat, session, memory, selected character, or any image job.
 */
export function CharacterProfileDrawer({
  open,
  characterId,
  profile,
  loading,
  imageUrl,
  onClose,
}: Props) {
  const { t } = useLocale();

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const heroPrimary =
    profile?.media.find((m) => m.mediaId === profile.primaryMediaId && m.mediaType === "image") ??
    profile?.media.find((m) => m.mediaType === "image") ??
    null;
  const heroUrl =
    (heroPrimary && mediaUrl(heroPrimary.sourceRef, imageUrl)) || portraitFor(characterId);

  const longParagraphs = (profile?.longDescription ?? "")
    .split(/\n\s*\n/)
    .map((p) => p.trim())
    .filter(Boolean);

  return (
    <div className="profile-backdrop" onClick={onClose}>
      <aside
        className="profile-drawer"
        role="dialog"
        aria-modal="true"
        aria-label={t("profile.dialogAria")}
        onClick={(e) => e.stopPropagation()}
      >
        <button type="button" className="profile-close" onClick={onClose} aria-label={t("profile.close")}>
          ✕
        </button>

        {loading && !profile ? (
          <p className="empty">{t("app.loading")}</p>
        ) : profile ? (
          <div className="profile-body">
            <div
              className="profile-hero"
              style={{ backgroundImage: `url(${heroUrl})` }}
              role="img"
              aria-label={t("focus.portraitAlt", { name: profile.displayName })}
            />
            <h2 className="profile-name">{profile.displayName}</h2>

            {profile.shortDescription && (
              <p className="profile-short">{profile.shortDescription}</p>
            )}

            {profile.isFallback && (
              <p className="profile-fallback-note">{t("profile.aboutFallback")}</p>
            )}

            {longParagraphs.length > 0 && (
              <div className="profile-long">
                {longParagraphs.map((p, i) => (
                  <p key={i}>{p}</p>
                ))}
              </div>
            )}

            {profile.sections.length > 0 && (
              <div className="profile-sections">
                {profile.sections.map((s) => (
                  <section key={s.sectionId} className="profile-section">
                    <h3 className="profile-section-title">{s.title}</h3>
                    {s.body && <p className="profile-section-body">{s.body}</p>}
                  </section>
                ))}
              </div>
            )}

            <div className="profile-media">
              <h3 className="profile-media-title">{t("profile.mediaTitle")}</h3>
              {profile.media.length === 0 ? (
                <p className="profile-media-empty">{t("profile.mediaEmpty")}</p>
              ) : (
                <div className="profile-media-grid">
                  {profile.media.map((m) => (
                    <MediaTile key={m.mediaId} item={m} imageUrl={imageUrl} />
                  ))}
                </div>
              )}
            </div>
          </div>
        ) : (
          <p className="empty">{t("error.unknown")}</p>
        )}
      </aside>
    </div>
  );
}
