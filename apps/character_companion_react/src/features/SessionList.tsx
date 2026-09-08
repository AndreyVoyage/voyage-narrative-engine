import type { CompanionSession } from "../client/types.js";

interface Props {
  sessions: CompanionSession[];
  selectedSessionId: string | null;
  disabled: boolean;
  onSelect: (sessionId: string) => void;
  onCreate: () => void;
}

/** Region B -- durable session list + new-conversation action. */
export function SessionList({ sessions, selectedSessionId, disabled, onSelect, onCreate }: Props) {
  return (
    <nav className="panel" aria-label="Диалоги">
      <div className="panel-head">
        <h2 className="panel-title">Диалоги</h2>
        <button type="button" className="btn" onClick={onCreate} disabled={disabled}>
          Новый диалог
        </button>
      </div>
      {sessions.length === 0 ? (
        <p className="empty">Диалогов пока нет.</p>
      ) : (
        <ul className="list">
          {sessions.map((s) => (
            <li key={s.sessionId}>
              <button
                type="button"
                className={s.sessionId === selectedSessionId ? "row row-selected" : "row"}
                onClick={() => onSelect(s.sessionId)}
              >
                {s.label}
              </button>
            </li>
          ))}
        </ul>
      )}
    </nav>
  );
}
