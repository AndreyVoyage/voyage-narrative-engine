import { useEffect, useRef, useState } from "react";
import type { ImageGenerationReadiness } from "../client/types.js";
import { useLocale } from "../i18n/react.js";
import type { TranslationKey } from "../i18n/index.js";

interface Props {
  readiness: ImageGenerationReadiness | null;
  busy: boolean;
  onSubmit: (description: string) => void;
  onCancel: () => void;
  onOpenSettings: () => void;
}

/** Backend readiness messageKey -> a real dictionary key (fail safe to a generic one). */
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

function readinessKey(messageKey: string | undefined): TranslationKey {
  return (READINESS_KEYS as readonly string[]).includes(messageKey ?? "")
    ? (messageKey as TranslationKey)
    : "image.readiness.roleUnassigned";
}

/**
 * Companion-native "Создать изображение" dialog. Replaces the old
 * window.prompt(). One multiline description, Create / Cancel. Real generation
 * only happens on explicit Create, and only when IMAGE_GENERATION is ready.
 */
export function CreateImageDialog({ readiness, busy, onSubmit, onCancel, onOpenSettings }: Props) {
  const { t } = useLocale();
  const [description, setDescription] = useState("");
  const areaRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    areaRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCancel();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onCancel]);

  const ready = readiness?.ready === true;
  const canSubmit = ready && description.trim().length > 0 && !busy;

  return (
    <div className="modal-backdrop" onClick={onCancel}>
      <div
        className="modal image-create-dialog"
        role="dialog"
        aria-modal="true"
        aria-label={t("image.createTitle")}
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="modal-title">{t("image.createTitle")}</h2>

        {!ready && readiness && (
          <div className="image-readiness image-readiness-blocked" role="status">
            <span>{t(readinessKey(readiness.messageKey))}</span>
            <button type="button" className="btn btn-sm" onClick={onOpenSettings}>
              {t("image.openSettings")}
            </button>
          </div>
        )}
        {ready && readiness?.unverified && (
          <p className="image-readiness image-readiness-unverified">{t("image.unverified")}</p>
        )}

        <textarea
          ref={areaRef}
          className="image-create-input"
          rows={4}
          placeholder={t("image.description")}
          value={description}
          disabled={!ready || busy}
          onChange={(e) => setDescription(e.target.value)}
        />

        <div className="modal-actions">
          <button type="button" className="btn" onClick={onCancel}>
            {t("image.cancel")}
          </button>
          <button
            type="button"
            className="btn btn-primary"
            disabled={!canSubmit}
            onClick={() => onSubmit(description.trim())}
          >
            {t("image.createSubmit")}
          </button>
        </div>
      </div>
    </div>
  );
}
