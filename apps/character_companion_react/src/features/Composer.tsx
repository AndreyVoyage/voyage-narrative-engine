import { useState } from "react";
import { isSendableMessage } from "../app/companionState.js";

interface Props {
  sending: boolean;
  onSend: (text: string) => void;
  onCreateImage: () => void;
  onContextFrame: () => void;
}

/**
 * Clean composer:  [ + ]  [ Написать сообщение… ]  [ 🎤 ]  [ Отправить ]
 *
 * "+" menu — CREATE actions are active (image generation). ATTACH upload
 * actions and the microphone are shown honestly as unavailable: the Attachment
 * Security Gateway and the STT pipeline are not implemented, so no unsafe file
 * picker and no fake success. The microphone is NOT duplicated in the menu.
 */
export function Composer({ sending, onSend, onCreateImage, onContextFrame }: Props) {
  const [draft, setDraft] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);

  function submit(event: { preventDefault: () => void }) {
    event.preventDefault();
    if (!isSendableMessage(draft) || sending) return;
    onSend(draft.trim());
    setDraft("");
  }

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
            <p className="composer-menu-group">Создать</p>
            <button type="button" role="menuitem" onClick={() => { setMenuOpen(false); onCreateImage(); }}>
              Создать изображение…
            </button>
            <button type="button" role="menuitem" onClick={() => { setMenuOpen(false); onContextFrame(); }}>
              Кадр по контексту
            </button>
            <p className="composer-menu-group">Прикрепить</p>
            <button type="button" role="menuitem" disabled title="Скоро — нужен модуль безопасной загрузки файлов">Изображение · Скоро</button>
            <button type="button" role="menuitem" disabled title="Скоро — нужен модуль безопасной загрузки файлов">Документ · Скоро</button>
            <button type="button" role="menuitem" disabled title="Скоро — нужен модуль безопасной загрузки файлов">Аудио · Скоро</button>
            <button type="button" role="menuitem" disabled title="Скоро — нужен модуль безопасной загрузки файлов">Видео · Скоро</button>
          </div>
        )}
      </div>

      <textarea
        className="composer-input"
        placeholder="Написать сообщение…"
        rows={2}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
      />

      <button
        type="button"
        className="btn composer-icon"
        disabled
        title="Записать голосовое сообщение · Скоро"
      >
        🎤
      </button>

      <button type="submit" className="btn btn-primary" disabled={sending || !isSendableMessage(draft)}>
        {sending ? "…" : "Отправить"}
      </button>
    </form>
  );
}
