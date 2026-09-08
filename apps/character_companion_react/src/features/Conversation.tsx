import type { CompanionMessage, CompanionSession, ImageJob } from "../client/types.js";
import { anyImageJobActive } from "../app/companionState.js";
import { Composer } from "./Composer.js";

interface Props {
  session: CompanionSession | null;
  messages: CompanionMessage[];
  imageJobs: ImageJob[];
  sending: boolean;
  error: { code: string; message: string } | null;
  onSend: (text: string) => void;
  onRetry: () => void;
  onCreateImage: () => void;
  onContextFrame: () => void;
  onEnterFocus: () => void;
}

/** Center region — transcript + composer + a NON-BLOCKING image-job status
 * strip + bounded error. Chat stays usable while an image job runs. */
export function Conversation({
  session, messages, imageJobs, sending, error,
  onSend, onRetry, onCreateImage, onContextFrame, onEnterFocus,
}: Props) {
  if (!session) {
    return <section className="panel conversation"><p className="empty">Выберите или создайте диалог.</p></section>;
  }

  const lastJob = imageJobs[imageJobs.length - 1];
  const jobBusy = anyImageJobActive(imageJobs);
  const lastFailed = lastJob && lastJob.state === "FAILED";
  const lastReady = lastJob && lastJob.state === "READY";

  return (
    <section className="panel conversation" aria-label="Диалог">
      <header className="conversation-head">
        <span className="conversation-title">{session.title || session.label}</span>
        <button type="button" className="btn btn-sm" onClick={onEnterFocus}>Фокус-режим</button>
      </header>

      {(jobBusy || lastFailed || lastReady) && (
        <div className="job-strip" aria-live="polite">
          {jobBusy && "Создаём изображение…"}
          {!jobBusy && lastReady && "Изображение готово"}
          {!jobBusy && lastFailed && "Не удалось создать изображение"}
        </div>
      )}

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

      <Composer
        sending={sending}
        onSend={onSend}
        onCreateImage={onCreateImage}
        onContextFrame={onContextFrame}
      />
    </section>
  );
}
