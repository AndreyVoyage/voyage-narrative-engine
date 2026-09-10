import { useState } from "react";
import type { CompanionMessage, CompanionSession, ImageJob } from "../client/types.js";
import { anyImageJobActive, hiddenMessageCount, visibleMessages } from "../app/companionState.js";
import { useLocale } from "../i18n/react.js";
import { Composer, type ComposerAssistant } from "./Composer.js";
import { MessageActions } from "./MessageActions.js";

interface Props {
  session: CompanionSession | null;
  messages: CompanionMessage[];
  imageJobs: ImageJob[];
  sending: boolean;
  error: { code: string; message: string } | null;
  assistant?: ComposerAssistant;
  /** Current session identity — every co-author run is owned by its session. */
  sessionId: string | null;
  /** Controlled current-session composer draft (owned by App, per session). */
  draft: string;
  onDraftChange: (next: string) => void;
  onSend: (text: string) => void;
  onRetry: () => void;
  onCreateImage: () => void;
  onContextFrame: () => void;
  onEnterFocus: () => void;
  onHideMessage: (seq: number, hidden: boolean) => void;
}

async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

/** Center region — transcript + composer + a NON-BLOCKING image-job status
 * strip + bounded error. Chat stays usable while an image job runs. */
export function Conversation({
  session, messages, imageJobs, sending, error, assistant, sessionId, draft, onDraftChange,
  onSend, onRetry, onCreateImage, onContextFrame, onEnterFocus, onHideMessage,
}: Props) {
  const { t, tError } = useLocale();
  const [showHidden, setShowHidden] = useState(false);
  const [copied, setCopied] = useState(false);

  if (!session) {
    return <section className="panel conversation"><p className="empty">{t("conversation.choosePrompt")}</p></section>;
  }

  const lastJob = imageJobs[imageJobs.length - 1];
  const jobBusy = anyImageJobActive(imageJobs);
  const lastFailed = lastJob && lastJob.state === "FAILED";
  const lastReady = lastJob && lastJob.state === "READY";
  const hiddenIds = session.hiddenMessageIds;
  const shown = visibleMessages(messages, hiddenIds, showHidden);
  const hiddenN = hiddenMessageCount(messages, hiddenIds);

  async function onCopy(text: string) {
    if (await copyText(text)) {
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    }
  }

  return (
    <section className="panel conversation" aria-label={t("nav.dialogues")}>
      <header className="conversation-head">
        <span className="conversation-title">{session.titleOverride || session.title || session.label}</span>
        <button type="button" className="btn btn-sm" onClick={onEnterFocus}>{t("conversation.focusMode")}</button>
      </header>

      {(jobBusy || lastFailed || lastReady) && (
        <div className="job-strip" aria-live="polite">
          {jobBusy && t("job.generating")}
          {!jobBusy && lastReady && t("job.ready")}
          {!jobBusy && lastFailed && t("job.failed")}
        </div>
      )}

      {hiddenN > 0 && (
        <button type="button" className="btn btn-sm chat-hidden-toggle" onClick={() => setShowHidden((v) => !v)}>
          {showHidden ? t("message.hideHidden") : t("message.showHidden", { count: hiddenN })}
        </button>
      )}
      {copied && <p className="hint" role="status">{t("message.copied")}</p>}

      <ol className="transcript">
        {shown.map((m, i) => {
          const isHidden = m.seq !== null && (hiddenIds ?? []).includes(m.seq);
          return (
            <li key={m.seq ?? i}
                className={`${m.role === "user" ? "msg msg-user" : "msg msg-character"}${isHidden ? " msg-hidden" : ""}`}>
              <span className="msg-role">{m.role === "user" ? t("conversation.you") : t("conversation.character")}</span>
              <span className="msg-text">{m.text}</span>
              {m.seq !== null && (
                <MessageActions
                  t={t}
                  hidden={isHidden}
                  onCopy={() => onCopy(m.text)}
                  onToggleHidden={() => onHideMessage(m.seq as number, !isHidden)}
                />
              )}
            </li>
          );
        })}
        {shown.length === 0 && <li className="empty">{t("conversation.empty")}</li>}
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
        assistant={assistant}
        sessionId={sessionId}
        draft={draft}
        onDraftChange={onDraftChange}
        onSend={onSend}
        onCreateImage={onCreateImage}
        onContextFrame={onContextFrame}
      />
    </section>
  );
}
