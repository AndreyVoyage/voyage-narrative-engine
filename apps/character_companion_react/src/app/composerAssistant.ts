/**
 * Ephemeral composer Co-Author state — pure, no React, no client.
 *
 * The co-author NEVER auto-sends and NEVER shows a modal: a suggestion simply
 * replaces the text in the normal composer input and the message stays unsent.
 *
 * Two local UI intents, derived only from composer emptiness (the backend
 * derives the authoritative COMPOSE/EXPAND mode itself — the frontend never
 * sends a mode):
 *   - snapshot === ""  → COMPOSE (propose a new user message)
 *   - snapshot !== ""  → EXPAND  (enrich the current draft)
 *
 * Each run captures the CURRENT composer text as its semantic source, so
 * pressing ✨ again after a suggestion enriches the now-visible text (it does
 * NOT forever re-use the first-ever draft). A late response is applied only
 * when it belongs to the latest run AND the composer is still byte-identical to
 * that run's snapshot — otherwise the user's newer typing is preserved.
 *
 * Nothing here is persisted — drafts never reach Character Memory or history.
 */

export type CoAuthorMode = "COMPOSE" | "EXPAND";

export interface AssistantState {
  /** true while a co-author request is in flight */
  running: boolean;
  /** id of the in-flight (or most recently started) run; monotonic */
  runId: number;
  /** exact composer text captured when the current run started */
  snapshot: string;
  /** local UI intent for the current run (never sent to the backend) */
  mode: CoAuthorMode;
  /** the non-empty original draft to offer "restore" after a successful EXPAND;
   *  null after COMPOSE or when there is nothing to restore */
  restorable: string | null;
  /** bounded error code from the last failed run, if any */
  error: string | null;
}

export function initialAssistantState(): AssistantState {
  return { running: false, runId: 0, snapshot: "", mode: "COMPOSE", restorable: null, error: null };
}

/** Local UI intent for a given composer draft (label + restore behaviour only). */
export function draftMode(draft: string): CoAuthorMode {
  return draft.trim() === "" ? "COMPOSE" : "EXPAND";
}

/** Begin a run from the CURRENT composer draft. Allocates the next runId and
 *  snapshots the exact current text. */
export function beginRun(state: AssistantState, currentDraft: string): AssistantState {
  return {
    running: true,
    runId: state.runId + 1,
    snapshot: currentDraft,
    mode: draftMode(currentDraft),
    restorable: null,
    error: null,
  };
}

/** True only if a suggestion for `runId` may be applied: it is still the latest
 *  run AND the composer has not changed since the run started. */
export function canApply(state: AssistantState, runId: number, currentDraft: string): boolean {
  return state.running && state.runId === runId && currentDraft === state.snapshot;
}

/** A suggestion for `runId` was accepted (the caller replaces the composer text).
 *  Keeps the snapshot as the restorable original only for EXPAND. */
export function runSucceeded(state: AssistantState, runId: number): AssistantState {
  if (state.runId !== runId) return state; // a newer run owns the state now
  return {
    ...state,
    running: false,
    error: null,
    restorable: state.mode === "EXPAND" ? state.snapshot : null,
  };
}

/** A suggestion for `runId` was discarded (stale run, or the user edited the
 *  composer while waiting). The composer is left exactly as the user left it. */
export function runDiscarded(state: AssistantState, runId: number): AssistantState {
  if (state.runId !== runId) return state;
  return { ...state, running: false };
}

/** A run for `runId` failed — stop running, record the code, leave the draft. */
export function runFailed(state: AssistantState, runId: number, code: string): AssistantState {
  if (state.runId !== runId) return state;
  return { ...state, running: false, error: code || "assistant_failed" };
}

/** Only meaningful after a successful EXPAND: an original non-empty draft that
 *  differs from what is now in the composer can be restored. Never true for a
 *  COMPOSE run (its "original" was an empty composer). */
export function canRestoreOriginal(state: AssistantState, currentDraft: string): boolean {
  return state.restorable !== null && state.restorable !== currentDraft;
}

/** Undo back to the exact original draft of the last EXPAND and forget the run
 *  (the runId counter is preserved so no stale response can ever re-apply). */
export function restoreOriginal(state: AssistantState): { state: AssistantState; draft: string } {
  return { state: { ...initialAssistantState(), runId: state.runId }, draft: state.restorable ?? "" };
}

/** The user edited the field manually with nothing running — drop the run so a
 *  later ✨ treats the new text as a fresh source and no stale restore lingers. */
export function forgetIfIdle(state: AssistantState): AssistantState {
  if (state.running) return state;
  return { ...initialAssistantState(), runId: state.runId };
}
