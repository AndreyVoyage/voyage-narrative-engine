import { useCallback, useEffect, useReducer } from "react";
import { CharacterList } from "./features/CharacterList.js";
import { SessionList } from "./features/SessionList.js";
import { Conversation } from "./features/Conversation.js";
import { HttpCompanionClient } from "./client/httpCompanionClient.js";
import { MockCompanionClient } from "./mocks/mockCompanionClient.js";
import { CompanionClient, CompanionClientError } from "./client/types.js";
import { companionReducer, initialCompanionState } from "./app/companionState.js";

// Transport-neutral: feature code only ever sees `CompanionClient`. The mock is
// used when the app is served without a backend (Vite `local` mode is not set).
const client: CompanionClient =
  import.meta.env.MODE === "mock" ? new MockCompanionClient() : new HttpCompanionClient();

function errorOf(e: unknown): { code: string; message: string } {
  if (e instanceof CompanionClientError) return { code: e.code, message: e.message };
  return { code: "unexpected", message: "Непредвиденная ошибка." };
}

export function App() {
  const [state, dispatch] = useReducer(companionReducer, initialCompanionState);

  useEffect(() => {
    dispatch({ type: "loadStart", scope: "characters" });
    client
      .listCharacters()
      .then((characters) => dispatch({ type: "charactersLoaded", characters }))
      .catch((e) => dispatch({ type: "loadFailed", ...errorOf(e) }));
  }, []);

  const loadSessions = useCallback((characterId: string) => {
    dispatch({ type: "loadStart", scope: "sessions" });
    client
      .listSessions(characterId)
      .then((sessions) => dispatch({ type: "sessionsLoaded", sessions }))
      .catch((e) => dispatch({ type: "loadFailed", ...errorOf(e) }));
  }, []);

  const loadMessages = useCallback((sessionId: string) => {
    dispatch({ type: "loadStart", scope: "messages" });
    client
      .getMessages(sessionId)
      .then((messages) => dispatch({ type: "messagesLoaded", messages }))
      .catch((e) => dispatch({ type: "loadFailed", ...errorOf(e) }));
  }, []);

  function selectCharacter(characterId: string) {
    dispatch({ type: "selectCharacter", characterId });
    loadSessions(characterId);
  }

  function selectSession(sessionId: string) {
    dispatch({ type: "selectSession", sessionId });
    loadMessages(sessionId);
  }

  function createSession() {
    if (!state.selectedCharacterId) return;
    dispatch({ type: "loadStart", scope: "sessions" });
    client
      .createSession(state.selectedCharacterId)
      .then((session) => {
        dispatch({ type: "sessionCreated", session });
        loadMessages(session.sessionId);
      })
      .catch((e) => dispatch({ type: "loadFailed", ...errorOf(e) }));
  }

  function send(text: string) {
    const sessionId = state.selectedSessionId;
    if (!sessionId) return;
    dispatch({ type: "sendStart" });
    client
      .sendMessage(sessionId, text)
      .then((turn) => dispatch({ type: "sendSucceeded", messages: turn.messages }))
      .catch((e) => dispatch({ type: "sendFailed", ...errorOf(e) }));
  }

  function retry() {
    if (state.selectedSessionId) loadMessages(state.selectedSessionId);
    else if (state.selectedCharacterId) loadSessions(state.selectedCharacterId);
  }

  return (
    <div className="app">
      <header className="app-bar">
        <span>Companion</span>
        {state.loading !== "idle" && <span className="hint">Загрузка…</span>}
      </header>
      <main className="columns">
        <CharacterList
          characters={state.characters}
          selectedCharacterId={state.selectedCharacterId}
          onSelect={selectCharacter}
        />
        <SessionList
          sessions={state.sessions}
          selectedSessionId={state.selectedSessionId}
          disabled={!state.selectedCharacterId}
          onSelect={selectSession}
          onCreate={createSession}
        />
        <Conversation
          messages={state.messages}
          sending={state.loading === "sending"}
          active={state.selectedSessionId !== null}
          error={state.error}
          onSend={send}
          onRetry={retry}
        />
      </main>
    </div>
  );
}
