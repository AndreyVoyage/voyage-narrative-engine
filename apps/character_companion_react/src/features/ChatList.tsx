import type { CompanionSession } from "../client/types.js";
import { portraitFor } from "../assets/portrait.js";
import { filterSessions } from "../app/companionState.js";
import { useLocale } from "../i18n/react.js";

interface Props {
  sessions: CompanionSession[];
  selectedSessionId: string | null;
  search: string;
  disabled: boolean;
  imageUrl: (resultRef: string) => string;
  onSearch: (value: string) => void;
  onSelect: (sessionId: string) => void;
  onNewDialog: () => void;
}

function sessionTitle(s: CompanionSession): string {
  return s.title || s.label;
}

/** Region B — multi-chat browser: cover/portrait fallback, title, preview,
 * last-activity, client-side search over title + preview. */
export function ChatList({
  sessions, selectedSessionId, search, disabled, imageUrl, onSearch, onSelect, onNewDialog,
}: Props) {
  const { t } = useLocale();
  const visible = filterSessions(sessions, search);
  return (
    <nav className="panel chat-list" aria-label={t("nav.dialogues")}>
      <div className="panel-head">
        <h2 className="panel-title">{t("nav.dialogues")}</h2>
        <button type="button" className="btn" onClick={onNewDialog} disabled={disabled}>
          {t("dialogues.new")}
        </button>
      </div>

      <input
        className="chat-search"
        type="search"
        placeholder={t("dialogues.search")}
        value={search}
        onChange={(e) => onSearch(e.target.value)}
      />

      {sessions.length === 0 ? (
        <p className="empty">{t("dialogues.empty")}</p>
      ) : visible.length === 0 ? (
        <p className="empty">{t("dialogues.noResults")}</p>
      ) : (
        <ul className="chat-cards">
          {visible.map((s) => (
            <li key={s.sessionId}>
              <button
                type="button"
                className={s.sessionId === selectedSessionId ? "chat-card chat-card-selected" : "chat-card"}
                onClick={() => onSelect(s.sessionId)}
              >
                <img
                  className="chat-card-cover"
                  src={s.sceneCoverRef ? imageUrl(s.sceneCoverRef) : portraitFor(s.characterId)}
                  alt=""
                />
                <span className="chat-card-body">
                  <span className="chat-card-title">{sessionTitle(s)}</span>
                  <span className="chat-card-preview">{s.lastMessagePreview || t("dialogues.previewEmpty")}</span>
                  <span className="chat-card-time">{s.updatedAt.replace("T", " ").split("+")[0]}</span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </nav>
  );
}
