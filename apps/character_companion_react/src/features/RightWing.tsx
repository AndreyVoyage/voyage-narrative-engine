import type { CompanionScene, ImageJob } from "../client/types.js";
import { portraitFor } from "../assets/portrait.js";
import { useLocale } from "../i18n/react.js";

interface Props {
  characterId: string | null;
  characterName: string;
  scene: CompanionScene | null;
  coverRef: string | null;
  imageUrl: (resultRef: string) => string;
  readyImages: ImageJob[];
  activeJob: ImageJob | null;
  onMakeCover: (resultRef: string) => void;
  onCreateImage: () => void;
  onContextFrame: () => void;
}

/**
 * Cinematic right wing:  Portrait  →  Scene image / visual  →  Scene parameters.
 * With no scene image the portrait expands to fill the visual area.
 */
export function RightWing({
  characterId, characterName, scene, coverRef, imageUrl, readyImages, activeJob,
  onMakeCover, onCreateImage, onContextFrame,
}: Props) {
  const { t } = useLocale();
  const NOT_SET = t("scene.notSet");
  const shownImage = coverRef ?? readyImages[readyImages.length - 1]?.resultRef ?? null;
  const hasSceneImage = Boolean(shownImage);

  return (
    <aside className="wing" aria-label={t("wing.header")}>
      {/* identity portrait -- never replaced by a Scene/generated image */}
      <div className={hasSceneImage ? "wing-portrait" : "wing-portrait wing-portrait-expanded"}>
        <img src={portraitFor(characterId)} alt={t("focus.portraitAlt", { name: characterName })} />
      </div>

      {hasSceneImage && shownImage && (
        <div className="wing-scene-image">
          <img src={imageUrl(shownImage)} alt={t("wing.sceneImageAlt")} />
        </div>
      )}

      <div className="wing-image-actions">
        <button type="button" className="btn btn-sm" onClick={onCreateImage}>{t("wing.createImage")}</button>
        <button type="button" className="btn btn-sm" onClick={onContextFrame}>{t("wing.contextFrame")}</button>
      </div>

      {activeJob && (
        <p className="wing-job-status" aria-live="polite">
          {activeJob.state === "QUEUED" && t("job.queued")}
          {activeJob.state === "GENERATING" && t("job.generating")}
        </p>
      )}

      {readyImages.length > 0 && (
        <div className="wing-gallery" aria-label={t("wing.gallery")}>
          {readyImages.map((j) => (
            <button
              key={j.jobId}
              type="button"
              className={j.resultRef === coverRef ? "thumb thumb-cover" : "thumb"}
              title={j.resultRef === coverRef ? t("wing.currentCover") : t("wing.makeCover")}
              onClick={() => j.resultRef && onMakeCover(j.resultRef)}
            >
              <img src={j.resultRef ? imageUrl(j.resultRef) : ""} alt="" />
            </button>
          ))}
        </div>
      )}

      <dl className="scene-params">
        <div><dt>📍 {t("scene.place")}</dt><dd>{scene?.place || NOT_SET}</dd></div>
        <div><dt>🕒 {t("scene.time")}</dt><dd>{scene?.time || NOT_SET}</dd></div>
        <div><dt>💬 {t("scene.situation")}</dt><dd>{scene?.situation || (scene ? NOT_SET : t("scene.ordinaryConversation"))}</dd></div>
        <div><dt>♡ {t("scene.mood")}</dt><dd>{scene?.mood || NOT_SET}</dd></div>
      </dl>
    </aside>
  );
}
