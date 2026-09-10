import { useRef, useState } from "react";
import { isSendableMessage } from "../app/companionState.js";
import {
  beginRun,
  canRestoreOriginal,
  draftMode,
  forgetIfIdle,
  initialAssistantState,
  restoreOriginal,
  runDiscarded,
  runFailed,
  runSucceeded,
  type AssistantState,
} from "../app/composerAssistant.js";
import type { TFunction } from "../i18n/react.js";

export interface ComposerAssistant {
  /** true when the authoritative DIALOGUE text model is configured/ready */
  available: boolean;
  /** co-author the given source draft ("" = COMPOSE, non-empty = EXPAND — the
   *  backend derives the mode). Rejects with a bounded error code string. */
  suggest: (source: string) => Promise<string>;
}

interface Props {
  sending: boolean;
  t: TFunction;
  assistant?: ComposerAssistant;
  onSend: (text: string) => void;
  onCreateImage: () => void;
  onContextFrame: () => void;
}

/**
 * Composer:  [ + ]  [ message ]  [ ✨ Сочинить / ✨ Развить ]  [ 🎤 ]  [ Send ]
 *
 * ✨ = contextual Co-Author. On an empty composer it COMPOSES a proposed user
 * message; on a non-empty draft it EXPANDS it. It writes the result IN PLACE
 * into this same input, never opens a modal and NEVER sends — only the human
 * pressing Send can send. A late suggestion is dropped if the user typed while
 * waiting. Attachment upload + the microphone stay honestly unavailable.
 */
export function Composer({ sending, t, assistant, onSend, onCreateImage, onContextFrame }: Props) {
  const [draft, setDraft] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);
  const [assist, setAssist] = useState<AssistantState>(initialAssistantState());
  // Always-current view of the composer text for the async late-response guard.
  const draftRef = useRef(draft);
  draftRef.current = draft;

  function submit(event: { preventDefault: () => void }) {
    event.preventDefault();
    if (!isSendableMessage(draft) || sending) return;
    onSend(draft.trim());
    setDraft("");
    setAssist(initialAssistantState());
  }

  function editDraft(value: string) {
    setDraft(value);
    setAssist((s) => forgetIfIdle(s));
  }

  const assistantReady = Boolean(assistant?.available);
  // The co-author works with an EMPTY composer (COMPOSE); only Send needs a
  // sendable draft. Single-flight: no new run while one is running.
  const canAssist = assistantReady && !assist.running && !sending;
  const coAuthorLabel = assist.running
    ? t("assistant.working")
    : draftMode(draft) === "COMPOSE"
      ? t("assistant.compose")
      : t("assistant.expand");

  async function runAssistant() {
    if (!assistant || !canAssist) return;
    const started = beginRun(assist, draft);
    const runId = started.runId;
    const source = started.snapshot;
    setAssist(started);
    try {
      const suggestion = await assistant.suggest(source);
      if (draftRef.current === source) {
        setAssist((s) => runSucceeded(s, runId));
        setDraft(suggestion);                       // replace IN PLACE; still unsent
      } else {
        setAssist((s) => runDiscarded(s, runId));   // user typed while waiting — keep their text
      }
    } catch (e) {
      const code = e && typeof e === "object" && "code" in e ? String((e as { code: unknown }).code) : "assistant_failed";
      setAssist((s) => runFailed(s, runId, code));   // draft is left exactly as it was
    }
  }

  function undoAssistant() {
    const { state, draft: original } = restoreOriginal(assist);
    setAssist(state);
    setDraft(original);
  }

  const soon = t("composer.attachSoonTitle");

  return (
    <form className="composer" onSubmit={submit}>
      <div className="composer-plus">
        <button
          type="button"
          className="btn composer-icon"
          aria-haspopup="menu"
          aria-expanded={menuOpen}
          onClick={() => setMenuOpen((v) => !v)}
        >
          +
        </button>
        {menuOpen && (
          <div className="composer-menu" role="menu">
            <p className="composer-menu-group">{t("composer.menuCreate")}</p>
            <button type="button" role="menuitem" onClick={() => { setMenuOpen(false); onCreateImage(); }}>
              {t("composer.createImage")}
            </button>
            <button type="button" role="menuitem" onClick={() => { setMenuOpen(false); onContextFrame(); }}>
              {t("composer.contextFrame")}
            </button>
            <p className="composer-menu-group">{t("composer.menuAttach")}</p>
            <button type="button" role="menuitem" disabled title={soon}>{t("composer.attachImage")}</button>
            <button type="button" role="menuitem" disabled title={soon}>{t("composer.attachDocument")}</button>
            <button type="button" role="menuitem" disabled title={soon}>{t("composer.attachAudio")}</button>
            <button type="button" role="menuitem" disabled title={soon}>{t("composer.attachVideo")}</button>
          </div>
        )}
      </div>

      <div className="composer-field">
        <textarea
          className="composer-input"
          placeholder={t("composer.placeholder")}
          rows={2}
          value={draft}
          onChange={(e) => editDraft(e.target.value)}
        />
        {(assist.running || canRestoreOriginal(assist, draft) || assist.error) && (
          <div className="composer-assist-bar" aria-live="polite">
            {assist.running && <span className="hint">{t("assistant.working")}</span>}
            {!assist.running && assist.error && (
              <span className="hint composer-assist-error">
                {assist.error === "assistant_not_configured"
                  ? t("assistant.unavailable")
                  : t("assistant.failed")}
              </span>
            )}
            {!assist.running && canRestoreOriginal(assist, draft) && (
              <button type="button" className="btn btn-sm" onClick={undoAssistant}>
                {t("assistant.restoreOriginal")}
              </button>
            )}
          </div>
        )}
      </div>

      <button
        type="button"
        className="btn composer-assist"
        disabled={!canAssist}
        title={assistantReady ? coAuthorLabel : t("assistant.unavailable")}
        aria-label={assistantReady ? `${t("assistant.coauthor")}: ${coAuthorLabel}` : t("assistant.unavailable")}
        onClick={runAssistant}
      >
        {assist.running ? "…" : `✨ ${coAuthorLabel}`}
      </button>

      <button
        type="button"
        className="btn composer-icon"
        disabled
        title={t("composer.recordVoice")}
      >
        🎤
      </button>

      <button type="submit" className="btn btn-primary" disabled={sending || !isSendableMessage(draft)}>
        {sending ? t("composer.sending") : t("composer.send")}
      </button>
    </form>
  );
}
