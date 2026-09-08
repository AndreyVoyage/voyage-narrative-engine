/**
 * Pure Companion UI state machine — no React, no DOM, no HTTP. The `.tsx`
 * screens are thin wrappers around `useReducer(companionReducer, ...)`, and the
 * structural checks exercise this reducer headlessly.
 *
 * Rules enforced here:
 * - switching character clears the stale selected session AND its messages;
 * - switching session clears messages until the reload lands;
 * - a failed send sets a bounded error and KEEPS previously loaded messages;
 * - image-generation jobs are tracked separately and NEVER gate `loading`
 *   (chat stays usable while a job runs);
 * - Focus Mode is a presentation flag; it never touches runtime state.
 */

import { CompanionCharacter, CompanionMessage, CompanionSession, ImageJob } from "../client/types.js";
import { FocusLayout } from "./appearance.js";

export interface CompanionState {
  characters: CompanionCharacter[];
  selectedCharacterId: string | null;
  sessions: CompanionSession[];
  selectedSessionId: string | null;
  messages: CompanionMessage[];
  imageJobs: ImageJob[]; // for the selected session
  search: string;
  loading: "idle" | "characters" | "sessions" | "messages" | "sending";
  error: { code: string; message: string } | null;
  focusActive: boolean;
  focusLayout: FocusLayout;
}

export function initialCompanionState(focusLayout: FocusLayout): CompanionState {
  return {
    characters: [],
    selectedCharacterId: null,
    sessions: [],
    selectedSessionId: null,
    messages: [],
    imageJobs: [],
    search: "",
    loading: "idle",
    error: null,
    focusActive: false,
    focusLayout,
  };
}

export type CompanionAction =
  | { type: "loadStart"; scope: CompanionState["loading"] }
  | { type: "loadFailed"; code: string; message: string }
  | { type: "charactersLoaded"; characters: CompanionCharacter[] }
  | { type: "selectCharacter"; characterId: string }
  | { type: "sessionsLoaded"; sessions: CompanionSession[] }
  | { type: "selectSession"; sessionId: string }
  | { type: "sessionCreated"; session: CompanionSession }
  | { type: "sessionUpdated"; session: CompanionSession }
  | { type: "messagesLoaded"; messages: CompanionMessage[] }
  | { type: "sendStart" }
  | { type: "sendSucceeded"; messages: CompanionMessage[] }
  | { type: "sendFailed"; code: string; message: string }
  | { type: "imageJobsLoaded"; jobs: ImageJob[] }
  | { type: "imageJobCreated"; job: ImageJob }
  | { type: "setSearch"; value: string }
  | { type: "focusEnter" }
  | { type: "focusExit" }
  | { type: "focusSetLayout"; layout: FocusLayout }
  | { type: "dismissError" };

export function companionReducer(state: CompanionState, action: CompanionAction): CompanionState {
  switch (action.type) {
    case "loadStart":
      return { ...state, loading: action.scope, error: null };
    case "loadFailed":
      return { ...state, loading: "idle", error: { code: action.code, message: action.message } };
    case "charactersLoaded":
      return { ...state, loading: "idle", characters: action.characters };
    case "selectCharacter":
      if (action.characterId === state.selectedCharacterId) return state;
      return {
        ...state,
        selectedCharacterId: action.characterId,
        sessions: [],
        selectedSessionId: null,
        messages: [],
        imageJobs: [],
        search: "",
        error: null,
        focusActive: false,
      };
    case "sessionsLoaded":
      return { ...state, loading: "idle", sessions: action.sessions };
    case "selectSession":
      if (action.sessionId === state.selectedSessionId) return state;
      return { ...state, selectedSessionId: action.sessionId, messages: [], imageJobs: [], error: null };
    case "sessionCreated":
      return {
        ...state,
        loading: "idle",
        sessions: [action.session, ...state.sessions],
        selectedSessionId: action.session.sessionId,
        messages: [],
        imageJobs: [],
        error: null,
      };
    case "sessionUpdated":
      return {
        ...state,
        sessions: state.sessions.map((s) =>
          s.sessionId === action.session.sessionId ? action.session : s,
        ),
      };
    case "messagesLoaded":
      return { ...state, loading: "idle", messages: action.messages };
    case "sendStart":
      return { ...state, loading: "sending", error: null };
    case "sendSucceeded":
      return { ...state, loading: "idle", messages: action.messages };
    case "sendFailed":
      // keep the transcript that was already on screen
      return { ...state, loading: "idle", error: { code: action.code, message: action.message } };
    case "imageJobsLoaded":
      // never touches `loading` — image jobs must not block the chat
      return { ...state, imageJobs: action.jobs };
    case "imageJobCreated":
      return { ...state, imageJobs: [...state.imageJobs.filter((j) => j.jobId !== action.job.jobId), action.job] };
    case "setSearch":
      return { ...state, search: action.value };
    case "focusEnter":
      return { ...state, focusActive: true };
    case "focusExit":
      return { ...state, focusActive: false };
    case "focusSetLayout":
      return { ...state, focusLayout: action.layout };
    case "dismissError":
      return { ...state, error: null };
    default:
      return state;
  }
}

/** The composer rejects blank input before any client call. */
export function isSendableMessage(text: string): boolean {
  return text.trim().length > 0;
}

/** Client-side chat filter over title + last-message preview (no full-text index). */
export function filterSessions(sessions: CompanionSession[], query: string): CompanionSession[] {
  const q = query.trim().toLowerCase();
  if (!q) return sessions;
  return sessions.filter((s) => {
    const hay = `${s.title} ${s.label} ${s.lastMessagePreview}`.toLowerCase();
    return hay.includes(q);
  });
}

export function anyImageJobActive(jobs: ImageJob[]): boolean {
  return jobs.some((j) => j.state === "QUEUED" || j.state === "GENERATING");
}
