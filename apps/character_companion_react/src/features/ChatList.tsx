import { useEffect, useRef, useState } from "react";
import type { CompanionSession } from "../client/types.js";
import { portraitFor } from "../assets/portrait.js";
import { displaySessionTitle, filterSessions, hiddenSessions, visibleSessions } from "../app/companionState.js";
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
  onRename: (sessionId: string, title: string) => void;
  onHideChat: (sessionId: string, hidden: boolean) => void;
}

function ChatMenu({ session, onRename, onHideChat }: {
  session: CompanionSession;
  onRename: (sessionId: string, title: string) => void;
  onHideChat: (sessionId: string, hidden: boolean) => void;
}) {
  const { t } = useLocale();
  const [open, setOpen] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [draft, setDraft] = useState(session.titleOverride ?? session.title ?? "");
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open && !renaming) return;
    function onDoc(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) { setOpen(false); setRenaming(false); }
    }
    window.addEventListener("mousedown", onDoc);
    return () => window.removeEventListener("mousedown", onDoc);
  }, [open, renaming]);

  function commit() {
    onRename(session.sessionId, draft.trim().slice(0, 120));
    setRenaming(false);
    setOpen(false);
  }

  return (
    <div className="chat-card-menu" ref={ref}>
      <button type="button" className="msg-actions-trigger" aria-haspopup="menu" aria-expanded={open}
              aria-label={t("chat.actions")} onClick={(e) => { e.stopPropagation(); setOpen((v) => !v); }}>
        ⋯
      </button>
      {open && !renaming && (
        <div className="msg-actions-menu" role="menu">
          <button type="button" role="menuitem" onClick={(e) => { e.stopPropagation(); setRenaming(true); }}>
            {t("chat.rename")}
          </button>
          <button type="button" role="menuitem" onClick={(e) => { e.stopPropagation(); onHideChat(session.sessionId, true); setOpen(false); }}>
            {t("chat.hide")}
          </button>
        </div>
      )}
      {renaming && (
        <div className="chat-rename" onClick={(e) => e.stopPropagation()}>
          <input
            autoFocus
            value={draft}
            maxLength={120}
            placeholder={t("chat.renamePlaceholder")}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") commit(); if (e.key === "Escape") setRenaming(false); }}
          />
          <button type="button" className="btn btn-sm" onClick={commit}>{t("chat.renameSave")}</button>
        </div>
      )}
    </div>
  );
}

/** Region B — multi-chat browser. `titleOverride` wins over the automatic
 * title; hidden conversations are moved to a collapsible "Скрытые" section with
 * a "Восстановить" action (nothing is deleted). */
export function ChatList({
  sessions, selectedSessionId, search, disabled, imageUrl,
  onSearch, onSelect, onNewDialog, onRename, onHideChat,
}: Props) {
  const { t } = useLocale();
  const [showHidden, setShowHidden] = useState(false);
  const normal = visibleSessions(sessions);
  const hidden = hiddenSessions(sessions);
  const visible = filterSessions(normal, search);

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

      {normal.length === 0 ? (
        <p className="empty">{t("dialogues.empty")}</p>
      ) : visible.length === 0 ? (
        <p className="empty">{t("dialogues.noResults")}</p>
      ) : (
        <ul className="chat-cards">
          {visible.map((s) => (
            <li key={s.sessionId} className="chat-card-row">
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
                  <span className="chat-card-title">{displaySessionTitle(s)}</span>
                  <span className="chat-card-preview">{s.lastMessagePreview || t("dialogues.previewEmpty")}</span>
                  <span className="chat-card-time">{s.updatedAt.replace("T", " ").split("+")[0]}</span>
                </span>
              </button>
              <ChatMenu session={s} onRename={onRename} onHideChat={onHideChat} />
            </li>
          ))}
        </ul>
      )}

      {hidden.length > 0 && (
        <div className="chat-hidden-section">
          <button type="button" className="btn btn-sm" onClick={() => setShowHidden((v) => !v)}>
            {t("chat.hiddenSection", { count: hidden.length })}
          </button>
          {showHidden && (
            <ul className="chat-cards chat-cards-hidden">
              {hidden.map((s) => (
                <li key={s.sessionId} className="chat-card-row">
                  <span className="chat-card chat-card-muted">{displaySessionTitle(s)}</span>
                  <button type="button" className="btn btn-sm" onClick={() => onHideChat(s.sessionId, false)}>
                    {t("chat.restore")}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </nav>
  );
}
