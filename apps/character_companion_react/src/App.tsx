import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from "react";
import { CharacterList } from "./features/CharacterList.js";
import { ChatList } from "./features/ChatList.js";
import { Conversation } from "./features/Conversation.js";
import { NewDialog } from "./features/NewDialog.js";
import { RightWing } from "./features/RightWing.js";
import { FocusMode } from "./features/FocusMode.js";
import { SettingsPanel } from "./features/SettingsPanel.js";
import { HttpCompanionClient } from "./client/httpCompanionClient.js";
import { MockCompanionClient } from "./mocks/mockCompanionClient.js";
import { CompanionClient, CompanionClientError, ImageJobKind, SceneField } from "./client/types.js";
import {
  anyImageJobActive,
  companionReducer,
  initialCompanionState,
} from "./app/companionState.js";
import { loadAppearance, rememberFocusLayout, type FocusLayout } from "./app/appearance.js";
import { draftToInput } from "./app/newDialog.js";

const client: CompanionClient =
  import.meta.env.MODE === "mock" ? new MockCompanionClient() : new HttpCompanionClient();

const IMAGE_FILE_BASE = "/api/companion/image-file/";
const imageUrl = (resultRef: string) => IMAGE_FILE_BASE + encodeURIComponent(resultRef);

function errorOf(e: unknown): { code: string; message: string } {
  if (e instanceof CompanionClientError) return { code: e.code, message: e.message };
  return { code: "unexpected", message: "Непредвиденная ошибка." };
}

export function App() {
  const appearance = useMemo(loadAppearance, []);
  const [state, dispatch] = useReducer(companionReducer, appearance.focusModeLayout, initialCompanionState);
  const [showNewDialog, setShowNewDialog] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const pollRef = useRef<number | null>(null);

  // ---- loaders -------------------------------------------------------
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
    client.listImageJobs(sessionId).then((jobs) => dispatch({ type: "imageJobsLoaded", jobs })).catch(() => undefined);
  }, []);

  // ---- image-job polling (non-blocking; never gates the chat) -------
  useEffect(() => {
    if (pollRef.current) window.clearInterval(pollRef.current);
    if (!state.selectedSessionId) return;
    const sid = state.selectedSessionId;
    pollRef.current = window.setInterval(() => {
      client.listImageJobs(sid).then((jobs) => dispatch({ type: "imageJobsLoaded", jobs })).catch(() => undefined);
    }, 700);
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
    };
  }, [state.selectedSessionId]);

  // ---- selection --------------------------------------------------
  function selectCharacter(characterId: string) {
    setShowNewDialog(false);
    dispatch({ type: "selectCharacter", characterId });
    loadSessions(characterId);
  }
  function selectSession(sessionId: string) {
    setShowNewDialog(false);
    dispatch({ type: "selectSession", sessionId });
    loadMessages(sessionId);
  }

  function startDialog(input: ReturnType<typeof draftToInput>) {
    if (!state.selectedCharacterId) return;
    dispatch({ type: "loadStart", scope: "sessions" });
    client
      .createSession(state.selectedCharacterId, input)
      .then((session) => {
        setShowNewDialog(false);
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

  function createImageJob(kind: ImageJobKind) {
    const sessionId = state.selectedSessionId;
    if (!sessionId) return;
    const prompt = kind === "custom" ? (window.prompt("Опишите изображение") ?? "").trim() : "";
    if (kind === "custom" && !prompt) return;
    client
      .createImageJob(sessionId, kind, kind === "custom" ? prompt : undefined)
      .then((job) => dispatch({ type: "imageJobCreated", job }))
      .catch((e) => dispatch({ type: "sendFailed", ...errorOf(e) }));
  }

  function makeCover(resultRef: string) {
    const sessionId = state.selectedSessionId;
    if (!sessionId) return;
    client
      .setSceneCover(sessionId, resultRef)
      .then((session) => dispatch({ type: "sessionUpdated", session }))
      .catch((e) => dispatch({ type: "sendFailed", ...errorOf(e) }));
  }

  function setFocusLayout(layout: FocusLayout) {
    rememberFocusLayout(layout);
    dispatch({ type: "focusSetLayout", layout });
  }

  const selectedSession =
    state.sessions.find((s) => s.sessionId === state.selectedSessionId) ?? null;
  const characterName =
    state.characters.find((c) => c.characterId === state.selectedCharacterId)?.displayName ?? "";
  const readyImages = state.imageJobs.filter((j) => j.state === "READY" && j.resultRef);
  const activeJob = state.imageJobs.find((j) => j.state === "QUEUED" || j.state === "GENERATING") ?? null;
  const coverUrl = selectedSession?.sceneCoverRef
    ? imageUrl(selectedSession.sceneCoverRef)
    : readyImages.length
      ? imageUrl(readyImages[readyImages.length - 1].resultRef as string)
      : null;

  if (state.focusActive && selectedSession) {
    return (
      <FocusMode
        layout={state.focusLayout}
        messages={state.messages}
        sending={state.loading === "sending"}
        coverUrl={coverUrl}
        readyImages={readyImages}
        imageUrl={imageUrl}
        onSetLayout={setFocusLayout}
        onSend={send}
        onCreateImage={() => createImageJob("custom")}
        onContextFrame={() => createImageJob("context")}
        onExit={() => dispatch({ type: "focusExit" })}
      />
    );
  }

  return (
    <div className="app">
      <header className="app-bar">
        <span>Companion · Cinematic</span>
        {state.loading !== "idle" && <span className="hint">Загрузка…</span>}
        {anyImageJobActive(state.imageJobs) && <span className="hint">Изображение создаётся…</span>}
        <button type="button" className="btn btn-sm app-bar-settings" onClick={() => setShowSettings(true)}>
          Настройки
        </button>
      </header>

      {showSettings && (
        <div className="settings-overlay">
          <SettingsPanel client={client} onClose={() => setShowSettings(false)} />
        </div>
      )}

      <main className="columns">
        <CharacterList
          characters={state.characters}
          selectedCharacterId={state.selectedCharacterId}
          onSelect={selectCharacter}
        />
        <ChatList
          sessions={state.sessions}
          selectedSessionId={state.selectedSessionId}
          search={state.search}
          disabled={!state.selectedCharacterId}
          imageUrl={imageUrl}
          onSearch={(value) => dispatch({ type: "setSearch", value })}
          onSelect={selectSession}
          onNewDialog={() => setShowNewDialog(true)}
        />

        {showNewDialog && state.selectedCharacterId ? (
          <NewDialog
            busy={state.loading === "sessions"}
            rollField={(f: SceneField) => client.randomScenario({ field: f }).then((r) => r.value ?? "")}
            rollScenario={() => client.randomScenario().then((r) => r.scenario ?? ({} as Record<SceneField, string>))}
            onCancel={() => setShowNewDialog(false)}
            onStart={startDialog}
          />
        ) : (
          <Conversation
            session={selectedSession}
            messages={state.messages}
            imageJobs={state.imageJobs}
            sending={state.loading === "sending"}
            error={state.error}
            onSend={send}
            onRetry={retry}
            onCreateImage={() => createImageJob("custom")}
            onContextFrame={() => createImageJob("context")}
            onEnterFocus={() => dispatch({ type: "focusEnter" })}
          />
        )}

        <RightWing
          characterName={characterName}
          scene={selectedSession?.scene ?? null}
          coverRef={selectedSession?.sceneCoverRef ?? null}
          imageUrl={imageUrl}
          readyImages={readyImages}
          activeJob={activeJob}
          onMakeCover={makeCover}
          onCreateImage={() => createImageJob("custom")}
          onContextFrame={() => createImageJob("context")}
        />
      </main>
    </div>
  );
}
