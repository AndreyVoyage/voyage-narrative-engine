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

export interface ChatMessage {
  readonly id: string;
  readonly role: "user" | "character" | "system";
  readonly text: string;
  readonly turnId?: string;
}

interface AppState {
  readonly mode: FeatureKey;
  readonly sidebarOpen: boolean;
  readonly inspectorOpen: boolean;
  readonly loading: boolean;
  readonly error: string | null;
  readonly characters: readonly CharacterSummary[];
  readonly variants: readonly CharacterVariantSummary[];
  readonly workspaces: readonly WorkspaceSummary[];
  readonly capabilities: CapabilitySet | null;
  readonly session: CharacterSession | null;
  readonly messages: readonly ChatMessage[];
}

const initialState: AppState = {
  mode: DEFAULT_FEATURE,
  sidebarOpen: false,
  inspectorOpen: false,
  loading: true,
  error: null,
  characters: [],
  variants: [],
  workspaces: [],
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
  selectVariant(variantId: string): Promise<void>;
  startNewCleanTestSession(): Promise<void>;
  sendMessage(text: string): Promise<void>;
}

const AppContext = createContext<AppApi | null>(null);

export interface AppStateProviderProps {
  readonly client: CharacterClient;
  readonly debugClient: CharacterDebugClient;
}

export function AppStateProvider({
  client,
  debugClient,
  children,
}: PropsWithChildren<AppStateProviderProps>) {
  const [state, dispatch] = useReducer(reducer, initialState);

  const bootstrapSession = useCallback(
    async (variantId: string) => {
      const workspace = await client.createTestWorkspace();
      const session = await client.createSession(
        DEFAULT_CHARACTER_ID,
        variantId,
        SessionPurpose.TESTING,
        workspace.workspaceId
      );
      dispatch({ type: "SESSION_READY", session });
    },
    [client]
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
        await bootstrapSession(DEFAULT_VARIANT_ID);
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
  }, [client, bootstrapSession]);

  const selectVariant = useCallback(
    async (variantId: string) => {
      dispatch({ type: "SET_ERROR", error: null });
      try {
        await bootstrapSession(variantId);
      } catch (err) {
        dispatch({ type: "SET_ERROR", error: err instanceof Error ? err.message : String(err) });
      }
    },
    [bootstrapSession]
  );

  const startNewCleanTestSession = useCallback(async () => {
    const variantId = state.session?.variantId ?? DEFAULT_VARIANT_ID;
    await selectVariant(variantId);
  }, [selectVariant, state.session]);

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
      selectVariant,
      startNewCleanTestSession,
      sendMessage,
    }),
    [state, client, debugClient, selectVariant, startNewCleanTestSession, sendMessage]
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
