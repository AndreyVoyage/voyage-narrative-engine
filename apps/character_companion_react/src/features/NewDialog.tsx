import { useState } from "react";
import type { SceneField } from "../client/types.js";
import { SCENE_FIELDS } from "../client/types.js";
import {
  NewDialogDraft,
  applyRandomScenario,
  draftToInput,
  emptyDraft,
  setFreeform,
  setMode,
  setSceneField,
  setTitle,
} from "../app/newDialog.js";
import { useLocale } from "../i18n/react.js";
import type { TranslationKey } from "../i18n/index.js";

interface Props {
  busy: boolean;
  rollField: (field: SceneField) => Promise<string>;
  rollScenario: () => Promise<Record<SceneField, string>>;
  onCancel: () => void;
  onStart: (input: ReturnType<typeof draftToInput>) => void;
}

const FIELD_KEY: Record<SceneField, TranslationKey> = {
  place: "scene.place",
  time: "scene.time",
  situation: "scene.situation",
  mood: "scene.mood",
};

/** "New dialogue" — A. Ordinary conversation  |  B. Start from a scene. */
export function NewDialog({ busy, rollField, rollScenario, onCancel, onStart }: Props) {
  const { t } = useLocale();
  const [draft, setDraft] = useState<NewDialogDraft>(emptyDraft());

  async function diceAll() {
    setDraft((d) => applyRandomScenario(d, {} as Record<SceneField, string>)); // no-op guard
    const scenario = await rollScenario();
    setDraft((d) => applyRandomScenario(d, scenario));
  }
  async function diceOne(field: SceneField) {
    const value = await rollField(field);
    setDraft((d) => setSceneField(d, field, value));
  }

  return (
    <section className="new-dialog panel" aria-label={t("newDialog.title")}>
      <h2 className="panel-title">{t("newDialog.title")}</h2>

      <div className="mode-choice">
        <label>
          <input
            type="radio"
            name="dialog-mode"
            checked={draft.mode === "ordinary"}
            onChange={() => setDraft((d) => setMode(d, "ordinary"))}
          />
          {t("newDialog.modeOrdinary")}
        </label>
        <label>
          <input
            type="radio"
            name="dialog-mode"
            checked={draft.mode === "scene"}
            onChange={() => setDraft((d) => setMode(d, "scene"))}
          />
          {t("newDialog.modeScene")}
        </label>
      </div>

      <label className="field">
        <span>{t("newDialog.name")}</span>
        <input value={draft.title} onChange={(e) => setDraft((d) => setTitle(d, e.target.value))} />
      </label>

      {draft.mode === "scene" && (
        <div className="scene-fields">
          <div className="scene-fields-head">
            <span>{t("newDialog.scene")}</span>
            <button type="button" className="btn btn-sm" onClick={diceAll} disabled={busy}>
              {t("newDialog.randomScenario")}
            </button>
          </div>
          {SCENE_FIELDS.map((f) => (
            <label className="field" key={f}>
              <span>{t(FIELD_KEY[f])}</span>
              <span className="field-row">
                <input
                  value={draft.scene[f]}
                  onChange={(e) => setDraft((d) => setSceneField(d, f, e.target.value))}
                />
                <button type="button" className="btn btn-sm" onClick={() => diceOne(f)} disabled={busy}>🎲</button>
              </span>
            </label>
          ))}
          <label className="field">
            <span>{t("newDialog.describe")}</span>
            <textarea
              rows={3}
              value={draft.scene.freeform}
              onChange={(e) => setDraft((d) => setFreeform(d, e.target.value))}
            />
          </label>
        </div>
      )}

      <div className="new-dialog-actions">
        <button type="button" className="btn" onClick={onCancel}>{t("newDialog.cancel")}</button>
        <button type="button" className="btn btn-primary" disabled={busy} onClick={() => onStart(draftToInput(draft))}>
          {t("newDialog.start")}
        </button>
      </div>
    </section>
  );
}
