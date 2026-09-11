import { createContext, useContext, useEffect, useLayoutEffect, useRef, useState } from "react";
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

/** App-level image-create ownership reaches both normal and Focus composers
 * without adding image-job state to either presentation wrapper. */
export const ImageActionsDisabledContext = createContext(false);

interface Props {
  sending: boolean;
  t: TFunction;
  assistant?: ComposerAssistant;
  /** The current conversation session. Every co-author run is owned by the
   *  session it started in; a result that arrives after the user switched
   *  sessions (even with the SAME Composer still mounted) is discarded. */
  sessionId: string | null;
  /** Controlled current-session draft, owned above the view-mode tree swap. */
  draft: string;
  /** Update the current session's draft (co-author results route through here too). */
  onDraftChange: (next: string) => void;
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
export function Composer({ sending, t, assistant, sessionId, draft, onDraftChange, onSend, onCreateImage, onContextFrame }: Props) {
  const [menuOpen, setMenuOpen] = useState(false);
  const imageActionsDisabled = useContext(ImageActionsDisabledContext);
  const [assist, setAssist] = useState<AssistantState>(initialAssistantState());
  // Always-current view of the controlled draft for the async late-response guard.
  const draftRef = useRef(draft);
  draftRef.current = draft;
  // Always-current session identity for the same-instance session-switch guard.
  const sessionRef = useRef(sessionId);
  sessionRef.current = sessionId;
  // Alive flag: a co-author promise that resolves after this Composer has been
  // unmounted (e.g. the user entered/left Focus Mode) must NOT write into the
  // now-lifted, possibly different-session draft.
  const aliveRef = useRef(true);
  useEffect(() => () => { aliveRef.current = false; }, []);
  // The one co-author run this Composer currently owns: its runId AND the
  // session it started in. Cleared on a session switch so a late A-result can
  // never land in B — even when the same Composer instance stays mounted and
  // A's and B's drafts happen to be identical (e.g. both empty).
  const runRef = useRef<{ id: number; sid: string | null } | null>(null);
  const prevSessionRef = useRef(sessionId);
  useEffect(() => {
    if (prevSessionRef.current === sessionId) return;
    prevSessionRef.current = sessionId;
    runRef.current = null;                         // abandon any in-flight run
    setAssist(initialAssistantState());            // B never inherits A's running/error/restore UI
  }, [sessionId]);
  // Auto-grow the textarea to its content (typing OR a programmatic draft change
  // from COMPOSE / EXPAND / restore-original), capped by the CSS max-height
  // beyond which it scrolls internally. Keyed on `draft` so it reacts to every
  // change of the controlled value.
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  useLayoutEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";                       // shrink-to-fit before measuring
    const border = el.offsetHeight - el.clientHeight;
    el.style.height = `${el.scrollHeight + border}px`;
  }, [draft]);

  function submit(event: { preventDefault: () => void }) {
    event.preventDefault();
    if (!isSendableMessage(draft) || sending) return;
    // The owner (App) clears this session's draft only on a SUCCESSFUL send, so
    // a failed send never loses the user's text.
    onSend(draft.trim());
    setAssist(initialAssistantState());
  }

  function editDraft(value: string) {
    onDraftChange(value);
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

  // A late result may touch draft / assist state ONLY if this Composer is still
  // mounted AND still on the session that started the run AND this run is still
  // the one the Composer owns (a session switch nulls runRef). Text equality
  // alone never establishes session identity.
  function runIsCurrent(runId: number, requestSessionId: string | null): boolean {
    const r = runRef.current;
    return aliveRef.current
      && r !== null
      && r.id === runId
      && r.sid === requestSessionId
      && sessionRef.current === requestSessionId;
  }

  async function runAssistant() {
    if (!assistant || !canAssist) return;
    const requestSessionId = sessionId;
    const started = beginRun(assist, draft);
    const runId = started.runId;
    const source = started.snapshot;
    runRef.current = { id: runId, sid: requestSessionId };
    setAssist(started);
    try {
      const suggestion = await assistant.suggest(source);
      if (!runIsCurrent(runId, requestSessionId)) return;   // unmounted / session switched / superseded
      if (draftRef.current === source) {
        setAssist((s) => runSucceeded(s, runId));
        onDraftChange(suggestion);                  // replace IN PLACE; still unsent
      } else {
        setAssist((s) => runDiscarded(s, runId));   // user typed while waiting — keep their text
      }
    } catch (e) {
      if (!runIsCurrent(runId, requestSessionId)) return;   // stale completion — do not touch state
      const code = e && typeof e === "object" && "code" in e ? String((e as { code: unknown }).code) : "assistant_failed";
      setAssist((s) => runFailed(s, runId, code));   // draft is left exactly as it was
    }
  }

  function undoAssistant() {
    const { state, draft: original } = restoreOriginal(assist);
    setAssist(state);
    onDraftChange(original);
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
            <button type="button" role="menuitem" disabled={imageActionsDisabled} onClick={() => { setMenuOpen(false); onCreateImage(); }}>
              {t("composer.createImage")}
            </button>
            <button type="button" role="menuitem" disabled={imageActionsDisabled} onClick={() => { setMenuOpen(false); onContextFrame(); }}>
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
          ref={textareaRef}
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
