import type { CompanionMessage, CompanionSession, ImageJob } from "../client/types.js";
import { anyImageJobActive } from "../app/companionState.js";
import { useLocale } from "../i18n/react.js";
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
  const { t, tError } = useLocale();

  if (!session) {
    return <section className="panel conversation"><p className="empty">{t("conversation.choosePrompt")}</p></section>;
  }

  const lastJob = imageJobs[imageJobs.length - 1];
  const jobBusy = anyImageJobActive(imageJobs);
  const lastFailed = lastJob && lastJob.state === "FAILED";
  const lastReady = lastJob && lastJob.state === "READY";

  return (
    <section className="panel conversation" aria-label={t("nav.dialogues")}>
      <header className="conversation-head">
        <span className="conversation-title">{session.title || session.label}</span>
        <button type="button" className="btn btn-sm" onClick={onEnterFocus}>{t("conversation.focusMode")}</button>
      </header>

      {(jobBusy || lastFailed || lastReady) && (
        <div className="job-strip" aria-live="polite">
          {jobBusy && t("job.generating")}
          {!jobBusy && lastReady && t("job.ready")}
          {!jobBusy && lastFailed && t("job.failed")}
        </div>
      )}

      <ol className="transcript">
        {messages.map((m, i) => (
          <li key={m.seq ?? i} className={m.role === "user" ? "msg msg-user" : "msg msg-character"}>
            <span className="msg-role">{m.role === "user" ? t("conversation.you") : t("conversation.character")}</span>
            <span className="msg-text">{m.text}</span>
          </li>
        ))}
        {messages.length === 0 && <li className="empty">{t("conversation.empty")}</li>}
      </ol>

      {error && (
        <div className="error" role="alert">
          <span>{tError(error.code)}</span>
          <button type="button" className="btn" onClick={onRetry}>{t("conversation.retry")}</button>
        </div>
      )}

      <Composer
        sending={sending}
        t={t}
        onSend={onSend}
        onCreateImage={onCreateImage}
        onContextFrame={onContextFrame}
      />
    </section>
  );
}
