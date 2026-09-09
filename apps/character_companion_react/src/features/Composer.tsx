import { useState } from "react";
import { isSendableMessage } from "../app/companionState.js";
import {
  beginRewrite,
  canRestoreOriginal,
  forgetIfIdle,
  initialAssistantState,
  restoreOriginal,
  rewriteFailed,
  rewriteSucceeded,
  sourceDraftFor,
  type AssistantState,
} from "../app/composerAssistant.js";
import type { TFunction } from "../i18n/react.js";

export interface ComposerAssistant {
  /** true when a WRITING_ASSISTANT provider/model is configured for invocation */
  available: boolean;
  /** rewrite the given source draft; rejects with a bounded error code string */
  rewrite: (source: string) => Promise<string>;
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
 * Composer:  [ + ]  [ message ]  [ ✨ ]  [ 🎤 ]  [ Send ]
 *
 * ✨ = Writing Assistant. It rewrites the draft IN PLACE inside this same input;
 * it never opens a modal and never sends. The exact original draft can be
 * restored, and pressing ✨ again rewrites the original (not the last
 * suggestion). Attachment upload + the microphone stay honestly unavailable.
 */
export function Composer({ sending, t, assistant, onSend, onCreateImage, onContextFrame }: Props) {
  const [draft, setDraft] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);
  const [assist, setAssist] = useState<AssistantState>(initialAssistantState());

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
  const canAssist = assistantReady && isSendableMessage(draft) && !assist.running && !sending;

  async function runAssistant() {
    if (!assistant || !canAssist) return;
    const source = sourceDraftFor(assist, draft);
    setAssist((s) => beginRewrite(s, draft));
    try {
      const suggestion = await assistant.rewrite(source);
      setDraft(suggestion);                       // replace IN PLACE; still unsent
      setAssist((s) => rewriteSucceeded(s));
    } catch (e) {
      const code = e && typeof e === "object" && "code" in e ? String((e as { code: unknown }).code) : "assistant_failed";
      setAssist((s) => rewriteFailed(s, code));   // draft is left exactly as it was
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
        className="btn composer-icon composer-assist"
        disabled={!canAssist}
        title={assistantReady ? t("assistant.rewrite") : t("assistant.unavailable")}
        aria-label={t("assistant.rewrite")}
        onClick={runAssistant}
      >
        {assist.running ? "…" : "✨"}
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
