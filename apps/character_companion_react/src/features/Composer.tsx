import { useState } from "react";
import { isSendableMessage } from "../app/companionState.js";
import type { TFunction } from "../i18n/react.js";

interface Props {
  sending: boolean;
  t: TFunction;
  onSend: (text: string) => void;
  onCreateImage: () => void;
  onContextFrame: () => void;
}

/**
 * Clean composer:  [ + ]  [ message input ]  [ 🎤 ]  [ send ]
 *
 * "+" menu — CREATE actions are active (image generation). ATTACH upload
 * actions and the microphone are shown honestly as unavailable: the Attachment
 * Security Gateway and the STT pipeline are not implemented, so no unsafe file
 * picker and no fake success. The microphone is NOT duplicated in the menu.
 */
export function Composer({ sending, t, onSend, onCreateImage, onContextFrame }: Props) {
  const [draft, setDraft] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);

  function submit(event: { preventDefault: () => void }) {
    event.preventDefault();
    if (!isSendableMessage(draft) || sending) return;
    onSend(draft.trim());
    setDraft("");
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

      <textarea
        className="composer-input"
        placeholder={t("composer.placeholder")}
        rows={2}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
      />

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
