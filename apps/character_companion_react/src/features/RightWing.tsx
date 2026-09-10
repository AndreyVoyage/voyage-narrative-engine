import type { CompanionScene, ImageGenerationReadiness, ImageJob } from "../client/types.js";
import { portraitFor } from "../assets/portrait.js";
import { useLocale } from "../i18n/react.js";
import type { TranslationKey } from "../i18n/index.js";

interface Props {
  characterId: string | null;
  characterName: string;
  scene: CompanionScene | null;
  coverRef: string | null;
  imageUrl: (resultRef: string) => string;
  readyImages: ImageJob[];
  activeJob: ImageJob | null;
  imageReadiness: ImageGenerationReadiness | null;
  onMakeCover: (resultRef: string) => void;
  onMakeBackground: (resultRef: string) => void;
  onCreateImage: () => void;
  onContextFrame: () => void;
}

const READINESS_KEYS: readonly TranslationKey[] = [
  "image.readiness.ready",
  "image.readiness.roleUnassigned",
  "image.readiness.providerNotConfigured",
  "image.readiness.modelUnsupported",
  "image.readiness.credentialMissing",
  "image.readiness.referenceUnsupported",
  "image.readiness.unverifiedCapability",
  "image.readiness.activeSnapshotMissing",
];

function readinessKey(messageKey: string): TranslationKey {
  return (READINESS_KEYS as readonly string[]).includes(messageKey)
    ? (messageKey as TranslationKey)
    : "image.readiness.roleUnassigned";
}

/**
 * Cinematic right wing:  Portrait  →  Scene image / visual  →  Scene parameters.
 * Also the primary place the image-generation product actions + status live.
 */
export function RightWing({
  characterId, characterName, scene, coverRef, imageUrl, readyImages, activeJob,
  imageReadiness, onMakeCover, onMakeBackground, onCreateImage, onContextFrame,
}: Props) {
  const { t } = useLocale();
  const NOT_SET = t("scene.notSet");
  const shownImage = coverRef ?? readyImages[readyImages.length - 1]?.resultRef ?? null;
  const hasSceneImage = Boolean(shownImage);
  const notReady = Boolean(imageReadiness && !imageReadiness.ready);

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

      {notReady && imageReadiness && (
        <p className="wing-image-readiness wing-image-readiness-blocked" role="status">
          {t(readinessKey(imageReadiness.messageKey))}
        </p>
      )}
      {imageReadiness?.ready && imageReadiness.unverified && (
        <p className="wing-image-readiness wing-image-readiness-unverified">{t("image.unverified")}</p>
      )}

      {activeJob && (
        <p className="wing-job-status" aria-live="polite">
          {activeJob.state === "QUEUED" && t("image.statusQueued")}
          {activeJob.state === "GENERATING" && t("image.statusGenerating")}
          {activeJob.state === "FAILED" && t("image.statusFailed")}
        </p>
      )}

      {readyImages.length > 0 && (
        <div className="wing-gallery" aria-label={t("wing.gallery")}>
          {readyImages.map((j) => (
            <div key={j.jobId} className="wing-gallery-item">
              <button
                type="button"
                className={j.resultRef === coverRef ? "thumb thumb-cover" : "thumb"}
                title={j.resultRef === coverRef ? t("wing.currentCover") : t("wing.makeCover")}
                onClick={() => j.resultRef && onMakeCover(j.resultRef)}
              >
                <img src={j.resultRef ? imageUrl(j.resultRef) : ""} alt="" />
              </button>
              <div className="wing-gallery-actions">
                <button
                  type="button"
                  className="btn btn-sm"
                  onClick={() => j.resultRef && onMakeCover(j.resultRef)}
                >
                  {t("image.makeCover")}
                </button>
                <button
                  type="button"
                  className="btn btn-sm"
                  onClick={() => j.resultRef && onMakeBackground(j.resultRef)}
                >
                  {t("image.makeBackground")}
                </button>
              </div>
            </div>
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
