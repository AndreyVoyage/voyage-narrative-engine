import { useEffect } from "react";
import type { CompanionMessage, ImageJob } from "../client/types.js";
import type { FocusLayout } from "../app/appearance.js";
import { FOCUS_LAYOUTS, nextFocusLayout } from "../app/appearance.js";
import { PORTRAIT_PLACEHOLDER_DATA_URI } from "../assets/portraitPlaceholder.js";
import { Composer } from "./Composer.js";

interface Props {
  layout: FocusLayout;
  messages: CompanionMessage[];
  sending: boolean;
  coverUrl: string | null;
  readyImages: ImageJob[];
  imageUrl: (resultRef: string) => string;
  onSetLayout: (layout: FocusLayout) => void;
  onSend: (text: string) => void;
  onCreateImage: () => void;
  onContextFrame: () => void;
  onExit: () => void;
}

const LAYOUT_LABEL: Record<FocusLayout, string> = {
  background: "Фон",
  side_gallery: "Галерея сбоку",
  chat_only: "Только чат",
};

/** Distraction-free mode. BACKGROUND / SIDE_GALLERY / CHAT_ONLY. Esc exits. */
export function FocusMode(props: Props) {
  const { layout, messages, sending, coverUrl, readyImages, imageUrl, onSetLayout, onExit } = props;

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onExit();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onExit]);

  const bg = layout === "background" && coverUrl ? { backgroundImage: `url(${coverUrl})` } : undefined;

  return (
    <div className={`focus focus-${layout}`} style={bg}>
      <header className="focus-bar">
        <div className="focus-layouts" role="tablist" aria-label="Режим фокуса">
          {FOCUS_LAYOUTS.map((l) => (
            <button
              key={l}
              type="button"
              role="tab"
              aria-selected={l === layout}
              className={l === layout ? "btn btn-sm btn-active" : "btn btn-sm"}
              onClick={() => onSetLayout(l)}
            >
              {LAYOUT_LABEL[l]}
            </button>
          ))}
          <button type="button" className="btn btn-sm" onClick={() => onSetLayout(nextFocusLayout(layout))}>
            Сменить вид
          </button>
        </div>
        <button type="button" className="btn btn-sm" onClick={onExit}>Выйти (Esc)</button>
      </header>

      <div className="focus-body">
        {layout === "side_gallery" && (
          <aside className="focus-gallery">
            <img src={PORTRAIT_PLACEHOLDER_DATA_URI} alt="Портрет" />
            {coverUrl && <img src={coverUrl} alt="Обложка" />}
            {readyImages.map((j) => (
              <img key={j.jobId} src={j.resultRef ? imageUrl(j.resultRef) : ""} alt="Кадр" />
            ))}
          </aside>
        )}
        <div className="focus-chat">
          <ol className="transcript">
            {messages.map((m, i) => (
              <li key={m.seq ?? i} className={m.role === "user" ? "msg msg-user" : "msg msg-character"}>
                <span className="msg-text">{m.text}</span>
              </li>
            ))}
          </ol>
          <Composer
            sending={sending}
            onSend={props.onSend}
            onCreateImage={props.onCreateImage}
            onContextFrame={props.onContextFrame}
          />
        </div>
      </div>
    </div>
  );
}
