import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from "react";
import { CharacterList } from "./features/CharacterList.js";
import { CharacterProfileDrawer } from "./features/CharacterProfileDrawer.js";
import { ChatList } from "./features/ChatList.js";
import { CreateImageDialog } from "./features/CreateImageDialog.js";
import { Conversation } from "./features/Conversation.js";
import { NewDialog } from "./features/NewDialog.js";
import { RightWing } from "./features/RightWing.js";
import { FocusMode } from "./features/FocusMode.js";
import { SettingsPanel } from "./features/SettingsPanel.js";
import { HttpCompanionClient } from "./client/httpCompanionClient.js";
import { MockCompanionClient } from "./mocks/mockCompanionClient.js";
import {
  CharacterPublicProfile,
  CompanionClient,
  CompanionClientError,
  ImageGenerationReadiness,
  ImageJobKind,
  SceneField,
} from "./client/types.js";
import {
  anyImageJobActive,
  companionReducer,
  initialCompanionState,
} from "./app/companionState.js";
import { loadAppearance, rememberFocusLayout, type FocusLayout } from "./app/appearance.js";
import { draftToInput } from "./app/newDialog.js";
import { setFocusBackgroundRef } from "./app/focusBackground.js";
import { loadUserProfile, saveUserProfile, type LocalUserProfile } from "./app/userProfile.js";
import { useLocale } from "./i18n/react.js";
import type { ComposerAssistant } from "./features/Composer.js";

const client: CompanionClient =
  import.meta.env.MODE === "mock" ? new MockCompanionClient() : new HttpCompanionClient();

const IMAGE_FILE_BASE = "/api/companion/image-file/";
const imageUrl = (resultRef: string) => IMAGE_FILE_BASE + encodeURIComponent(resultRef);

function errorOf(e: unknown): { code: string; message: string } {
  if (e instanceof CompanionClientError) return { code: e.code, message: e.message };
  return { code: "unexpected", message: "unexpected" };
}

export function App() {
  const { t, locale, setLocale } = useLocale();
  const appearance = useMemo(loadAppearance, []);
  const [state, dispatch] = useReducer(companionReducer, appearance.focusModeLayout, initialCompanionState);
  const [showNewDialog, setShowNewDialog] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  // Public-profile drawer — presentation only. Opening it never changes the
  // selected character, the session, chat messages, memory, or any image job.
  const [profileCharId, setProfileCharId] = useState<string | null>(null);
  const [profile, setProfile] = useState<CharacterPublicProfile | null>(null);
  const [profileLoading, setProfileLoading] = useState(false);
  // IMAGE_GENERATION product wiring — readiness is provider-call-free.
  const [imageReadiness, setImageReadiness] = useState<ImageGenerationReadiness | null>(null);
  const [showCreateImage, setShowCreateImage] = useState(false);
  const [release, setRelease] = useState<import("./client/types.js").ReleaseInfo | null>(null);
  const [userProfile, setUserProfile] = useState<LocalUserProfile>(loadUserProfile);
  const [assistantReady, setAssistantReady] = useState(false);
  const pollRef = useRef<number | null>(null);

  // Unsent composer drafts, keyed by session id, IN MEMORY ONLY (no backend, no
  // localStorage). Owned here so switching view / entering or leaving Focus Mode
  // — which remounts the Composer — never discards the current session's draft.
  const [sessionDrafts, setSessionDrafts] = useState<Record<string, string>>({});
  const composerDraft = state.selectedSessionId ? (sessionDrafts[state.selectedSessionId] ?? "") : "";
  const setComposerDraft = useCallback((next: string) => {
    const sid = state.selectedSessionId;
    if (!sid) return;
    setSessionDrafts((d) => (d[sid] === next ? d : { ...d, [sid]: next }));
  }, [state.selectedSessionId]);

  const refreshAssistantReady = useCallback(() => {
    // The co-author follows the ONE authoritative text model: the DIALOGUE role.
    // There is no separate WRITING_ASSISTANT readiness any more.
    client.getSettings()
      .then((view) => {
        const dialogue = view.roleCatalog.find((r) => r.role === "DIALOGUE");
        setAssistantReady(dialogue?.readiness === "READY");
      })
      .catch(() => setAssistantReady(false));
  }, []);
  useEffect(refreshAssistantReady, [refreshAssistantReady]);

  const assistant: ComposerAssistant = useMemo(() => ({
    available: assistantReady,
    suggest: async (source: string) => {
      // "" -> COMPOSE, non-empty -> EXPAND (the backend derives the mode).
      const res = await client.suggestDraft(source, {
        localeHint: locale,
        sessionId: state.selectedSessionId || null,
      });
      return res.suggestion;
    },
  }), [assistantReady, locale, state.selectedSessionId]);

  // one-time reconcile: honour a locale that was only stored on the profile
  useEffect(() => {
    if (userProfile.locale !== locale) setLocale(userProfile.locale);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const updateProfile = useCallback((next: LocalUserProfile) => {
    setUserProfile(saveUserProfile(next));
  }, []);

  // ---- loaders -------------------------------------------------------
  useEffect(() => {
    dispatch({ type: "loadStart", scope: "characters" });
    client
      .listCharacters()
      .then((characters) => dispatch({ type: "charactersLoaded", characters }))
      .catch((e) => dispatch({ type: "loadFailed", ...errorOf(e) }));
    client.getReleaseInfo().then(setRelease).catch(() => undefined);
  }, []);

  const providerNeedsConfig = release?.mode === "release" && release.dialogueProvider === "fake";

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

  // ---- image-generation readiness (provider-call-free) -----------
  const refreshImageReadiness = useCallback((characterId: string | null) => {
    if (!characterId) {
      setImageReadiness(null);
      return;
    }
    client
      .imageGenerationReadiness(characterId)
      .then(setImageReadiness)
      .catch(() => setImageReadiness(null));
  }, []);

  // ---- selection --------------------------------------------------
  function selectCharacter(characterId: string) {
    setShowNewDialog(false);
    dispatch({ type: "selectCharacter", characterId });
    loadSessions(characterId);
    refreshImageReadiness(characterId);
  }
  function selectSession(sessionId: string) {
    setShowNewDialog(false);
    dispatch({ type: "selectSession", sessionId });
    loadMessages(sessionId);
  }

  // ---- public profile drawer (no selection / session / memory side effects) --
  function openProfile(characterId: string) {
    setProfileCharId(characterId);
    setProfile(null);
    setProfileLoading(true);
    client
      .getCharacterProfile(characterId)
      .then((p) => setProfile(p))
      .catch(() => setProfile(null))
      .finally(() => setProfileLoading(false));
  }
  function closeProfile() {
    setProfileCharId(null);
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
      .then((turn) => {
        dispatch({ type: "sendSucceeded", messages: turn.messages });
        // clear ONLY this session's unsent draft, and ONLY on success — a
        // failed send must never lose the user's text.
        setSessionDrafts((d) => {
          if (!(sessionId in d)) return d;
          const next = { ...d };
          delete next[sessionId];
          return next;
        });
      })
      .catch((e) => dispatch({ type: "sendFailed", ...errorOf(e) }));
  }

  function retry() {
    if (state.selectedSessionId) loadMessages(state.selectedSessionId);
    else if (state.selectedCharacterId) loadSessions(state.selectedCharacterId);
  }

  // Explicit user action only. "custom" opens the Companion-native dialog;
  // "context" uses the existing bounded context-frame path. Neither generates
  // anything until the user confirms, and both are guarded by readiness.
  function createImageJob(kind: ImageJobKind) {
    if (!state.selectedSessionId) return;
    if (kind === "custom") {
      setShowCreateImage(true);
      return;
    }
    if (imageReadiness && !imageReadiness.ready) {
      dispatch({ type: "sendFailed", code: "image_generation_not_configured", message: imageReadiness.messageKey });
      return;
    }
    submitImageJob("context");
  }

  function submitImageJob(kind: ImageJobKind, description?: string) {
    const sessionId = state.selectedSessionId;
    if (!sessionId) return;
    if (kind === "custom" && !(description && description.trim())) return;
    client
      .createImageJob(sessionId, kind, kind === "custom" ? description!.trim() : undefined)
      .then((job) => {
        setShowCreateImage(false);
        dispatch({ type: "imageJobCreated", job });
      })
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

  // BACKGROUND != COVER: this is the existing local, presentation-only Focus
  // background preference. No regeneration, no Scene / Memory / cover write.
  function makeBackground(resultRef: string) {
    if (state.selectedSessionId) setFocusBackgroundRef(state.selectedSessionId, resultRef);
  }

  function setFocusLayout(layout: FocusLayout) {
    rememberFocusLayout(layout);
    dispatch({ type: "focusSetLayout", layout });
  }

  // ---- presentation controls (durable metadata; never touch Character Memory)
  function hideMessage(seq: number, hidden: boolean) {
    const sessionId = state.selectedSessionId;
    if (!sessionId) return;
    client
      .setMessageHidden(sessionId, seq, hidden)
      .then((session) => dispatch({ type: "sessionUpdated", session }))
      .catch((e) => dispatch({ type: "sendFailed", ...errorOf(e) }));
  }
  function renameChat(sessionId: string, title: string) {
    client
      .renameSession(sessionId, title)
      .then((session) => dispatch({ type: "sessionUpdated", session }))
      .catch((e) => dispatch({ type: "loadFailed", ...errorOf(e) }));
  }
  function hideChat(sessionId: string, hidden: boolean) {
    client
      .setSessionHidden(sessionId, hidden)
      .then((session) => {
        dispatch({ type: "sessionUpdated", session });
        if (hidden && sessionId === state.selectedSessionId) dispatch({ type: "selectSession", sessionId: "" });
      })
      .catch((e) => dispatch({ type: "loadFailed", ...errorOf(e) }));
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

  const createImageDialog = showCreateImage ? (
    <CreateImageDialog
      readiness={imageReadiness}
      busy={anyImageJobActive(state.imageJobs)}
      onSubmit={(description) => submitImageJob("custom", description)}
      onCancel={() => setShowCreateImage(false)}
      onOpenSettings={() => { setShowCreateImage(false); setShowSettings(true); }}
    />
  ) : null;

  if (state.focusActive && selectedSession) {
    return (
      <>
      {createImageDialog}
      <FocusMode
        layout={state.focusLayout}
        characterId={state.selectedCharacterId}
        characterName={characterName}
        sessionId={selectedSession.sessionId}
        messages={state.messages}
        hiddenMessageIds={selectedSession.hiddenMessageIds ?? []}
        sending={state.loading === "sending"}
        assistant={assistant}
        draft={composerDraft}
        onDraftChange={setComposerDraft}
        coverUrl={coverUrl}
        coverRef={selectedSession.sceneCoverRef ?? null}
        readyImages={readyImages}
        imageUrl={imageUrl}
        userProfile={userProfile}
        t={t}
        onSetLayout={setFocusLayout}
        onSend={send}
        onCreateImage={() => createImageJob("custom")}
        onContextFrame={() => createImageJob("context")}
        onExit={() => dispatch({ type: "focusExit" })}
        onMakeCover={makeCover}
      />
      </>
    );
  }

  return (
    <div className="app">
      <header className="app-bar">
        <span>{release ? release.release.name : t("app.brandFallback")}</span>
        {providerNeedsConfig && (
          <button type="button" className="hint app-bar-config-needed" onClick={() => setShowSettings(true)}>
            {t("app.providerNeedsConfig")}
          </button>
        )}
        {state.loading !== "idle" && <span className="hint">{t("app.loading")}</span>}
        {anyImageJobActive(state.imageJobs) && <span className="hint">{t("app.imageWorking")}</span>}
        <button type="button" className="btn btn-sm app-bar-settings" onClick={() => setShowSettings(true)}>
          {t("app.settings")}
        </button>
      </header>

      {showSettings && (
        <div className="settings-overlay">
          <SettingsPanel
            client={client}
            profile={userProfile}
            onProfileChange={updateProfile}
            onClose={() => {
              setShowSettings(false);
              refreshAssistantReady();
              refreshImageReadiness(state.selectedCharacterId);
            }}
          />
        </div>
      )}

      {createImageDialog}

      <main className="columns">
        <CharacterList
          characters={state.characters}
          selectedCharacterId={state.selectedCharacterId}
          onSelect={selectCharacter}
          onOpenProfile={openProfile}
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
          onRename={renameChat}
          onHideChat={hideChat}
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
            assistant={assistant}
            sessionId={state.selectedSessionId || null}
            draft={composerDraft}
            onDraftChange={setComposerDraft}
            onSend={send}
            onRetry={retry}
            onCreateImage={() => createImageJob("custom")}
            onContextFrame={() => createImageJob("context")}
            onEnterFocus={() => dispatch({ type: "focusEnter" })}
            onHideMessage={hideMessage}
          />
        )}

        <RightWing
          characterId={state.selectedCharacterId}
          characterName={characterName}
          scene={selectedSession?.scene ?? null}
          coverRef={selectedSession?.sceneCoverRef ?? null}
          imageUrl={imageUrl}
          readyImages={readyImages}
          activeJob={activeJob}
          imageReadiness={imageReadiness}
          onMakeCover={makeCover}
          onMakeBackground={makeBackground}
          onCreateImage={() => createImageJob("custom")}
          onContextFrame={() => createImageJob("context")}
        />
      </main>

      <CharacterProfileDrawer
        open={profileCharId !== null}
        characterId={profileCharId}
        profile={profile}
        loading={profileLoading}
        imageUrl={imageUrl}
        onClose={closeProfile}
      />
    </div>
  );
}
