/**
 * Pure Companion UI state machine -- no React, no DOM, no HTTP. The `.tsx`
 * screens are thin wrappers around `useReducer(companionReducer, ...)`, and the
 * structural checks exercise this reducer headlessly.
 *
 * Rules enforced here:
 * - switching character clears the stale selected session AND its messages;
 * - switching session clears messages until the reload lands;
 * - a failed send sets a bounded error and KEEPS the previously loaded
 *   messages (never wipes the transcript).
 */

import { CompanionCharacter, CompanionMessage, CompanionSession } from "../client/types.js";

export interface CompanionState {
  characters: CompanionCharacter[];
  selectedCharacterId: string | null;
  sessions: CompanionSession[];
  selectedSessionId: string | null;
  messages: CompanionMessage[];
  loading: "idle" | "characters" | "sessions" | "messages" | "sending";
  error: { code: string; message: string } | null;
}

export const initialCompanionState: CompanionState = {
  characters: [],
  selectedCharacterId: null,
  sessions: [],
  selectedSessionId: null,
  messages: [],
  loading: "idle",
  error: null,
};

export type CompanionAction =
  | { type: "loadStart"; scope: CompanionState["loading"] }
  | { type: "loadFailed"; code: string; message: string }
  | { type: "charactersLoaded"; characters: CompanionCharacter[] }
  | { type: "selectCharacter"; characterId: string }
  | { type: "sessionsLoaded"; sessions: CompanionSession[] }
  | { type: "selectSession"; sessionId: string }
  | { type: "sessionCreated"; session: CompanionSession }
  | { type: "messagesLoaded"; messages: CompanionMessage[] }
  | { type: "sendStart" }
  | { type: "sendSucceeded"; messages: CompanionMessage[] }
  | { type: "sendFailed"; code: string; message: string };

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
      // stale session + transcript must not survive a character switch
      return {
        ...state,
        selectedCharacterId: action.characterId,
        sessions: [],
        selectedSessionId: null,
        messages: [],
        error: null,
      };
    case "sessionsLoaded":
      return { ...state, loading: "idle", sessions: action.sessions };
    case "selectSession":
      if (action.sessionId === state.selectedSessionId) return state;
      return { ...state, selectedSessionId: action.sessionId, messages: [], error: null };
    case "sessionCreated":
      return {
        ...state,
        loading: "idle",
        sessions: [...state.sessions, action.session],
        selectedSessionId: action.session.sessionId,
        messages: [],
        error: null,
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
    default:
      return state;
  }
}

/** The composer rejects blank input before any client call. */
export function isSendableMessage(text: string): boolean {
  return text.trim().length > 0;
}
