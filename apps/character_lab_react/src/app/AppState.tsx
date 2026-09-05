import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useReducer,
  type PropsWithChildren,
} from "react";

import type { CharacterClient } from "../client/characterClient";
import type { CharacterDebugClient } from "../client/characterDebugClient";
import {
  SessionPurpose,
  type CapabilitySet,
  type CharacterSession,
  type CharacterSummary,
  type CharacterVariantSummary,
  type WorkspaceSummary,
} from "../client/types";
import type { FeatureKey } from "../navigation/navigation";
import { DEFAULT_FEATURE } from "../navigation/navigation";

const DEFAULT_CHARACTER_ID = "kira";
const DEFAULT_VARIANT_ID = "KIRA_BETA_V1_CURRENT";

/** Which concrete `CharacterClient` `main.tsx` chose for this session:
 * "mock" (`MockCharacterClient`, no backend) or "local" (`HttpCharacterClient`
 * over the local loopback Desktop Integration v1 server). Fixed for the
 * lifetime of the app -- set once at startup, never toggled at runtime.
 * Feature views that are not yet transported in "local" mode (Memory,
 * Runtime State, Scene, Turn Debugger) read this to show an honest
 * "not integrated" state instead of silently continuing to show mock data
 * under what would look like a live view. */
export type ClientMode = "mock" | "local";

export interface ChatMessage {
  readonly id: string;
  readonly role: "user" | "character" | "system";
  readonly text: string;
  readonly turnId?: string;
}

interface AppState {
  readonly clientMode: ClientMode;
  readonly mode: FeatureKey;
  readonly sidebarOpen: boolean;
  readonly inspectorOpen: boolean;
  readonly loading: boolean;
  readonly error: string | null;
  readonly characters: readonly CharacterSummary[];
  readonly variants: readonly CharacterVariantSummary[];
  readonly workspaces: readonly WorkspaceSummary[];
  /** The workspace the NEXT session/adjust action targets. Chosen explicitly
   * (dropdown, or "create new Clean Test") -- never inferred silently. */
  readonly selectedWorkspaceId: string | null;
  readonly capabilities: CapabilitySet | null;
  readonly session: CharacterSession | null;
  readonly messages: readonly ChatMessage[];
}

const initialState: Omit<AppState, "clientMode"> = {
  mode: DEFAULT_FEATURE,
  sidebarOpen: false,
  inspectorOpen: false,
  loading: true,
  error: null,
  characters: [],
  variants: [],
  workspaces: [],
  selectedWorkspaceId: null,
  capabilities: null,
  session: null,
  messages: [],
};

type Action =
  | { type: "SET_MODE"; mode: FeatureKey }
  | { type: "SET_SIDEBAR_OPEN"; open: boolean }
  | { type: "SET_INSPECTOR_OPEN"; open: boolean }
  | { type: "SET_LOADING"; loading: boolean }
  | { type: "SET_ERROR"; error: string | null }
  | {
      type: "CATALOG_LOADED";
      characters: readonly CharacterSummary[];
      variants: readonly CharacterVariantSummary[];
      workspaces: readonly WorkspaceSummary[];
      capabilities: CapabilitySet;
    }
  | { type: "WORKSPACE_REGISTERED"; workspace: WorkspaceSummary }
  | { type: "WORKSPACE_SELECTED"; workspaceId: string }
  | { type: "SESSION_READY"; session: CharacterSession }
  | { type: "MESSAGE_APPENDED"; message: ChatMessage }
  | { type: "MESSAGES_CLEARED" };

function reducer(state: AppState, action: Action): AppState {
  switch (action.type) {
    case "SET_MODE":
      return { ...state, mode: action.mode };
    case "SET_SIDEBAR_OPEN":
      return { ...state, sidebarOpen: action.open };
    case "SET_INSPECTOR_OPEN":
      return { ...state, inspectorOpen: action.open };
    case "SET_LOADING":
      return { ...state, loading: action.loading };
    case "SET_ERROR":
      return { ...state, error: action.error };
    case "CATALOG_LOADED":
      return {
        ...state,
        characters: action.characters,
        variants: action.variants,
        workspaces: action.workspaces,
        capabilities: action.capabilities,
      };
    case "WORKSPACE_REGISTERED": {
      const exists = state.workspaces.some((w) => w.workspaceId === action.workspace.workspaceId);
      const workspaces = exists
        ? state.workspaces.map((w) => (w.workspaceId === action.workspace.workspaceId ? action.workspace : w))
        : [...state.workspaces, action.workspace];
      return { ...state, workspaces, selectedWorkspaceId: action.workspace.workspaceId };
    }
    case "WORKSPACE_SELECTED":
      return { ...state, selectedWorkspaceId: action.workspaceId };
    case "SESSION_READY":
      return { ...state, session: action.session, messages: [] };
    case "MESSAGE_APPENDED":
      return { ...state, messages: [...state.messages, action.message] };
    case "MESSAGES_CLEARED":
      return { ...state, messages: [] };
    default:
      return state;
  }
}

let messageIdCounter = 0;
function nextMessageId(): string {
  messageIdCounter += 1;
  return `msg-${messageIdCounter}`;
}

export interface AppApi {
  readonly state: AppState;
  readonly client: CharacterClient;
  readonly debugClient: CharacterDebugClient;
  setMode(mode: FeatureKey): void;
  setSidebarOpen(open: boolean): void;
  setInspectorOpen(open: boolean): void;
  /** Choose which already-known workspace the NEXT session targets. Local
   * UI selection only -- no backend call, no session created. */
  selectWorkspace(workspaceId: string): void;
  /** Create a fresh, isolated Clean Test workspace and select it. Does NOT
   * create a session -- `createSession()` is a separate, explicit step. */
  createCleanTestWorkspace(): Promise<void>;
  /** Create a NEW TESTING session for `variantId` (defaults to the current
   * session's variant, or the app default) in `state.selectedWorkspaceId`
   * (creating a fresh Clean Test first only if nothing is selected yet --
   * e.g. on first load). The session is never given a silently-created
   * workspace when one is already selected. */
  createSession(variantId?: string): Promise<void>;
  sendMessage(text: string): Promise<void>;
}

const AppContext = createContext<AppApi | null>(null);

export interface AppStateProviderProps {
  readonly client: CharacterClient;
  readonly debugClient: CharacterDebugClient;
  readonly clientMode: ClientMode;
}

export function AppStateProvider({
  client,
  debugClient,
  clientMode,
  children,
}: PropsWithChildren<AppStateProviderProps>) {
  const [state, dispatch] = useReducer(
    reducer,
    clientMode,
    (mode): AppState => ({ ...initialState, clientMode: mode })
  );

  const createSession = useCallback(
    async (variantId?: string) => {
      const effectiveVariantId = variantId ?? state.session?.variantId ?? DEFAULT_VARIANT_ID;
      dispatch({ type: "SET_ERROR", error: null });
      try {
        let workspaceId = state.selectedWorkspaceId;
        if (!workspaceId) {
          // Only on first load / if nothing is selected yet -- an explicit
          // create-then-use, never a silent side effect of session creation.
          const created = await client.createTestWorkspace();
          dispatch({ type: "WORKSPACE_REGISTERED", workspace: created });
          workspaceId = created.workspaceId;
        }
        const session = await client.createSession(
          DEFAULT_CHARACTER_ID,
          effectiveVariantId,
          SessionPurpose.TESTING,
          workspaceId
        );
        dispatch({ type: "SESSION_READY", session });
      } catch (err) {
        dispatch({ type: "SET_ERROR", error: err instanceof Error ? err.message : String(err) });
      }
    },
    [client, state.session, state.selectedWorkspaceId]
  );

  useEffect(() => {
    let cancelled = false;
    async function load() {
      dispatch({ type: "SET_LOADING", loading: true });
      try {
        const [characters, variants, workspaces, capabilities] = await Promise.all([
          client.listCharacters(),
          client.listVariants(DEFAULT_CHARACTER_ID),
          client.listWorkspaces(),
          client.capabilities(DEFAULT_CHARACTER_ID),
        ]);
        if (cancelled) return;
        dispatch({ type: "CATALOG_LOADED", characters, variants, workspaces, capabilities });
        await createSession(DEFAULT_VARIANT_ID);
      } catch (err) {
        if (!cancelled) {
          dispatch({ type: "SET_ERROR", error: err instanceof Error ? err.message : String(err) });
        }
      } finally {
        if (!cancelled) dispatch({ type: "SET_LOADING", loading: false });
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [client]);

  const selectWorkspace = useCallback((workspaceId: string) => {
    dispatch({ type: "WORKSPACE_SELECTED", workspaceId });
  }, []);

  const createCleanTestWorkspace = useCallback(async () => {
    dispatch({ type: "SET_ERROR", error: null });
    try {
      const created = await client.createTestWorkspace();
      dispatch({ type: "WORKSPACE_REGISTERED", workspace: created });
    } catch (err) {
      dispatch({ type: "SET_ERROR", error: err instanceof Error ? err.message : String(err) });
    }
  }, [client]);

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || !state.session) return;
      dispatch({ type: "MESSAGE_APPENDED", message: { id: nextMessageId(), role: "user", text: trimmed } });
      try {
        const turn = await client.sendMessage(state.session.sessionId, trimmed);
        dispatch({
          type: "MESSAGE_APPENDED",
          message: { id: nextMessageId(), role: "character", text: turn.response, turnId: turn.turnId },
        });
      } catch (err) {
        dispatch({
          type: "MESSAGE_APPENDED",
          message: {
            id: nextMessageId(),
            role: "system",
            text: `Ошибка: ${err instanceof Error ? err.message : String(err)}`,
          },
        });
      }
    },
    [client, state.session]
  );

  const api = useMemo<AppApi>(
    () => ({
      state,
      client,
      debugClient,
      setMode: (mode) => dispatch({ type: "SET_MODE", mode }),
      setSidebarOpen: (open) => dispatch({ type: "SET_SIDEBAR_OPEN", open }),
      setInspectorOpen: (open) => dispatch({ type: "SET_INSPECTOR_OPEN", open }),
      selectWorkspace,
      createCleanTestWorkspace,
      createSession,
      sendMessage,
    }),
    [state, client, debugClient, selectWorkspace, createCleanTestWorkspace, createSession, sendMessage]
  );

  return <AppContext.Provider value={api}>{children}</AppContext.Provider>;
}

export function useAppState(): AppApi {
  const ctx = useContext(AppContext);
  if (!ctx) {
    throw new Error("useAppState must be used within an AppStateProvider");
  }
  return ctx;
}
