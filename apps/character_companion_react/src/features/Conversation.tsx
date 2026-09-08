import { useState } from "react";
import type { CompanionMessage } from "../client/types.js";
import { isSendableMessage } from "../app/companionState.js";

interface Props {
  messages: CompanionMessage[];
  sending: boolean;
  active: boolean;
  error: { code: string; message: string } | null;
  onSend: (text: string) => void;
  onRetry: () => void;
}

/** Regions C + D + E -- transcript, composer, and bounded connection/error state. */
export function Conversation({ messages, sending, active, error, onSend, onRetry }: Props) {
  const [draft, setDraft] = useState("");

  function submit(event: { preventDefault: () => void }) {
    event.preventDefault();
    if (!isSendableMessage(draft) || sending) return;
    onSend(draft.trim());
    setDraft("");
  }

  if (!active) {
    return <section className="panel conversation"><p className="empty">Выберите или создайте диалог.</p></section>;
  }

  return (
    <section className="panel conversation" aria-label="Диалог">
      <ol className="transcript">
        {messages.map((m, i) => (
          <li key={m.seq ?? i} className={m.role === "user" ? "msg msg-user" : "msg msg-character"}>
            <span className="msg-role">{m.role === "user" ? "Вы" : "Персонаж"}</span>
            <span className="msg-text">{m.text}</span>
          </li>
        ))}
        {messages.length === 0 && <li className="empty">Сообщений пока нет.</li>}
      </ol>

      {error && (
        <div className="error" role="alert">
          <span>{error.message}</span>
          <button type="button" className="btn" onClick={onRetry}>Повторить</button>
        </div>
      )}

      <form className="composer" onSubmit={submit}>
        <textarea
          className="composer-input"
          placeholder="Сообщение"
          value={draft}
          rows={2}
          onChange={(e) => setDraft(e.target.value)}
        />
        <button type="submit" className="btn" disabled={sending || !isSendableMessage(draft)}>
          {sending ? "…" : "Отправить"}
        </button>
      </form>
    </section>
  );
}
