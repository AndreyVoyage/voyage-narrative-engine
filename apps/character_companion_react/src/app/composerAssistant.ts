/**
 * Ephemeral composer Writing-Assistant state — pure, no React, no client.
 *
 * The assistant NEVER auto-sends and NEVER shows a modal: a suggestion simply
 * replaces the text in the normal composer input, the message stays unsent, and
 * the exact original draft can be restored. "Generate again" always rewrites the
 * ORIGINAL source draft (not a previous suggestion) to avoid semantic drift.
 * Nothing here is persisted — drafts never reach Character Memory or history.
 */

export interface AssistantState {
  /** the user's exact draft captured before the first rewrite of this run */
  originalDraft: string | null;
  /** true while a rewrite request is in flight */
  running: boolean;
  /** bounded error code from the last failed attempt, if any */
  error: string | null;
}

export function initialAssistantState(): AssistantState {
  return { originalDraft: null, running: false, error: null };
}

/** Begin a rewrite: remember the original draft once, mark running. */
export function beginRewrite(state: AssistantState, currentDraft: string): AssistantState {
  return {
    originalDraft: state.originalDraft ?? currentDraft,
    running: true,
    error: null,
  };
}

/** The text to send to the assistant: always the original source draft so
 * repeated ✨ presses do not compound edits. */
export function sourceDraftFor(state: AssistantState, currentDraft: string): string {
  return state.originalDraft ?? currentDraft;
}

/** A suggestion arrived — stop running; keep the remembered original so undo and
 * "generate again" still work. The caller replaces the composer text. */
export function rewriteSucceeded(state: AssistantState): AssistantState {
  return { ...state, running: false, error: null };
}

/** A rewrite failed — stop running, record the code. The caller keeps the
 * current/original draft in the composer (never clears it). */
export function rewriteFailed(state: AssistantState, code: string): AssistantState {
  return { ...state, running: false, error: code || "assistant_failed" };
}

export function canRestoreOriginal(state: AssistantState, currentDraft: string): boolean {
  return state.originalDraft !== null && state.originalDraft !== currentDraft;
}

/** Undo back to the exact original draft and forget the run. */
export function restoreOriginal(state: AssistantState): { state: AssistantState; draft: string } {
  return { state: initialAssistantState(), draft: state.originalDraft ?? "" };
}

/** The user edited the field manually with nothing pending — drop the run so a
 * later ✨ treats the new text as a fresh original. */
export function forgetIfIdle(state: AssistantState): AssistantState {
  if (state.running) return state;
  return initialAssistantState();
}
