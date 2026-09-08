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

interface Props {
  busy: boolean;
  rollField: (field: SceneField) => Promise<string>;
  rollScenario: () => Promise<Record<SceneField, string>>;
  onCancel: () => void;
  onStart: (input: ReturnType<typeof draftToInput>) => void;
}

const FIELD_LABEL: Record<SceneField, string> = {
  place: "Место",
  time: "Время",
  situation: "Ситуация",
  mood: "Настроение",
};

/** "Новый диалог" — A. Обычный разговор  |  B. Начать со сцены. */
export function NewDialog({ busy, rollField, rollScenario, onCancel, onStart }: Props) {
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
    <section className="new-dialog panel" aria-label="Новый диалог">
      <h2 className="panel-title">Новый диалог</h2>

      <div className="mode-choice">
        <label>
          <input
            type="radio"
            name="dialog-mode"
            checked={draft.mode === "ordinary"}
            onChange={() => setDraft((d) => setMode(d, "ordinary"))}
          />
          Обычный разговор
        </label>
        <label>
          <input
            type="radio"
            name="dialog-mode"
            checked={draft.mode === "scene"}
            onChange={() => setDraft((d) => setMode(d, "scene"))}
          />
          Начать со сцены
        </label>
      </div>

      <label className="field">
        <span>Название (необязательно)</span>
        <input value={draft.title} onChange={(e) => setDraft((d) => setTitle(d, e.target.value))} />
      </label>

      {draft.mode === "scene" && (
        <div className="scene-fields">
          <div className="scene-fields-head">
            <span>Сцена</span>
            <button type="button" className="btn btn-sm" onClick={diceAll} disabled={busy}>
              🎲 Случайный сценарий
            </button>
          </div>
          {SCENE_FIELDS.map((f) => (
            <label className="field" key={f}>
              <span>{FIELD_LABEL[f]}</span>
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
            <span>Опишите обстоятельства</span>
            <textarea
              rows={3}
              value={draft.scene.freeform}
              onChange={(e) => setDraft((d) => setFreeform(d, e.target.value))}
            />
          </label>
        </div>
      )}

      <div className="new-dialog-actions">
        <button type="button" className="btn" onClick={onCancel}>Отмена</button>
        <button type="button" className="btn btn-primary" disabled={busy} onClick={() => onStart(draftToInput(draft))}>
          Начать
        </button>
      </div>
    </section>
  );
}
