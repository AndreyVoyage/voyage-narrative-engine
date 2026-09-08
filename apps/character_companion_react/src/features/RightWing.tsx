import type { CompanionScene, ImageJob } from "../client/types.js";
import { PORTRAIT_PLACEHOLDER_DATA_URI } from "../assets/portraitPlaceholder.js";

interface Props {
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

const NOT_SET = "Не задано";

/**
 * Cinematic right wing:  Portrait  →  Scene image / visual  →  Scene parameters.
 * With no scene image the portrait expands to fill the visual area.
 */
export function RightWing({
  characterName, scene, coverRef, imageUrl, readyImages, activeJob,
  onMakeCover, onCreateImage, onContextFrame,
}: Props) {
  const shownImage = coverRef ?? readyImages[readyImages.length - 1]?.resultRef ?? null;
  const hasSceneImage = Boolean(shownImage);

  return (
    <aside className="wing" aria-label="Персонаж и сцена">
      <div className={hasSceneImage ? "wing-portrait" : "wing-portrait wing-portrait-expanded"}>
        <img src={PORTRAIT_PLACEHOLDER_DATA_URI} alt={`Портрет: ${characterName}`} />
      </div>

      {hasSceneImage && shownImage && (
        <div className="wing-scene-image">
          <img src={imageUrl(shownImage)} alt="Изображение сцены" />
        </div>
      )}

      <div className="wing-image-actions">
        <button type="button" className="btn btn-sm" onClick={onCreateImage}>Создать изображение…</button>
        <button type="button" className="btn btn-sm" onClick={onContextFrame}>Кадр по контексту</button>
      </div>

      {activeJob && (
        <p className="wing-job-status" aria-live="polite">
          {activeJob.state === "QUEUED" && "Изображение поставлено в очередь"}
          {activeJob.state === "GENERATING" && "Создаём изображение…"}
        </p>
      )}

      {readyImages.length > 0 && (
        <div className="wing-gallery" aria-label="Галерея">
          {readyImages.map((j) => (
            <button
              key={j.jobId}
              type="button"
              className={j.resultRef === coverRef ? "thumb thumb-cover" : "thumb"}
              title={j.resultRef === coverRef ? "Текущая обложка" : "Сделать обложкой диалога"}
              onClick={() => j.resultRef && onMakeCover(j.resultRef)}
            >
              <img src={j.resultRef ? imageUrl(j.resultRef) : ""} alt="Кадр" />
            </button>
          ))}
        </div>
      )}

      <dl className="scene-params">
        <div><dt>📍 Место</dt><dd>{scene?.place || NOT_SET}</dd></div>
        <div><dt>🕒 Время</dt><dd>{scene?.time || NOT_SET}</dd></div>
        <div><dt>💬 Ситуация</dt><dd>{scene?.situation || (scene ? NOT_SET : "Обычный разговор")}</dd></div>
        <div><dt>♡ Настроение</dt><dd>{scene?.mood || NOT_SET}</dd></div>
      </dl>
    </aside>
  );
}
