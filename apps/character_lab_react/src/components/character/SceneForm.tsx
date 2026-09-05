import { useState } from "react";
import type { SceneSummary, SetSceneInput } from "../../client/types";
import { FormField, FormGrid } from "../primitives/FormGrid";
import { Inline } from "../primitives/Inline";
import { Stack } from "../primitives/Stack";

export interface SceneFormProps {
  readonly scene: SceneSummary | null;
  readonly onSet: (input: SetSceneInput) => void;
  readonly onClear: () => void;
}

/**
 * Owner-authored situational Scene setup. Session-scoped, mock-only in this
 * foundation slice -- no real editing semantics against a backend yet.
 */
export function SceneForm({ scene, onSet, onClear }: SceneFormProps) {
  const [title, setTitle] = useState(scene?.title ?? "");
  const [location, setLocation] = useState(scene?.location ?? "");
  const [participants, setParticipants] = useState("");
  const [priorEvents, setPriorEvents] = useState("");
  const [currentSituation, setCurrentSituation] = useState("");

  function handleApply() {
    onSet({
      title,
      location,
      participants: participants.split("\n").map((s) => s.trim()).filter(Boolean),
      priorEvents: priorEvents.split("\n").map((s) => s.trim()).filter(Boolean),
      currentSituation,
    });
  }

  return (
    <Stack gap={4}>
      <FormGrid>
        <FormField label="Название">
          <input className="clab-input" value={title} onChange={(e) => setTitle(e.target.value)} />
        </FormField>
        <FormField label="Место">
          <input className="clab-input" value={location} onChange={(e) => setLocation(e.target.value)} />
        </FormField>
      </FormGrid>
      <FormField label="Участники (по одному в строке)">
        <textarea
          className="clab-textarea"
          value={participants}
          onChange={(e) => setParticipants(e.target.value)}
        />
      </FormField>
      <FormField label="Предыдущие события (по одному в строке)">
        <textarea
          className="clab-textarea"
          value={priorEvents}
          onChange={(e) => setPriorEvents(e.target.value)}
        />
      </FormField>
      <FormField label="Текущая ситуация">
        <textarea
          className="clab-textarea"
          value={currentSituation}
          onChange={(e) => setCurrentSituation(e.target.value)}
        />
      </FormField>
      <Inline gap={2}>
        <button className="clab-btn clab-btn--primary" onClick={handleApply}>
          Сохранить / применить
        </button>
        <button className="clab-btn" onClick={onClear}>
          Очистить
        </button>
        {scene?.active && <span className="clab-badge clab-badge--ok">сцена активна</span>}
      </Inline>
    </Stack>
  );
}
