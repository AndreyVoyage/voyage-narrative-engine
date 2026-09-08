/**
 * Pure "Новый диалог" draft state — no React, no client. The user picks
 * `ordinary` or `scene`; for a scene they edit the four structured fields plus
 * a free-form description. Both free-form and structured values are stored;
 * there is NO automatic semantic reconciliation. The user's structured values
 * are authoritative.
 */

import { CompanionScene, NewDialogInput, SCENE_FIELDS, SceneField, emptyScene, sceneHasAny } from "../client/types.js";

export type DialogMode = "ordinary" | "scene";

export interface NewDialogDraft {
  mode: DialogMode;
  title: string;
  scene: CompanionScene;
}

export function emptyDraft(): NewDialogDraft {
  return { mode: "ordinary", title: "", scene: emptyScene() };
}

export function setMode(draft: NewDialogDraft, mode: DialogMode): NewDialogDraft {
  return { ...draft, mode };
}

export function setTitle(draft: NewDialogDraft, title: string): NewDialogDraft {
  return { ...draft, title };
}

export function setSceneField(draft: NewDialogDraft, field: SceneField, value: string): NewDialogDraft {
  return { ...draft, scene: { ...draft.scene, [field]: value } };
}

export function setFreeform(draft: NewDialogDraft, freeform: string): NewDialogDraft {
  return { ...draft, scene: { ...draft.scene, freeform } };
}

export function applyRandomScenario(draft: NewDialogDraft, scenario: Record<SceneField, string>): NewDialogDraft {
  const scene = { ...draft.scene };
  for (const f of SCENE_FIELDS) scene[f] = scenario[f] ?? scene[f];
  return { ...draft, scene };
}

/** Build the `createSession` input. An ordinary dialog carries no scene. */
export function draftToInput(draft: NewDialogDraft): NewDialogInput {
  const input: NewDialogInput = {};
  if (draft.title.trim()) input.title = draft.title.trim();
  if (draft.mode === "scene" && sceneHasAny(draft.scene)) input.scene = draft.scene;
  return input;
}
