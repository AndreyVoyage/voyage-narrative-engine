import { useEffect, useRef, useState } from "react";
import type { TFunction } from "../i18n/react.js";

interface Props {
  t: TFunction;
  hidden: boolean;
  onCopy: () => void;
  onToggleHidden: () => void;
}

/**
 * Subtle per-message ⋯ menu. V1 offers only presentation-safe actions:
 * "Копировать" and "Скрыть/Показать сообщение". There is deliberately NO
 * functional "Редактировать" — sent-message editing needs the supersession /
 * context-safety work in RECENT_TAIL_EDIT_SUPERSESSION_V1.
 */
export function MessageActions({ t, hidden, onCopy, onToggleHidden }: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    function onDoc(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    window.addEventListener("mousedown", onDoc);
    return () => window.removeEventListener("mousedown", onDoc);
  }, [open]);

  return (
    <div className="msg-actions" ref={ref}>
      <button
        type="button"
        className="msg-actions-trigger"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={t("message.actions")}
        onClick={() => setOpen((v) => !v)}
      >
        ⋯
      </button>
      {open && (
        <div className="msg-actions-menu" role="menu">
          <button type="button" role="menuitem" onClick={() => { setOpen(false); onCopy(); }}>
            {t("message.copy")}
          </button>
          <button type="button" role="menuitem" onClick={() => { setOpen(false); onToggleHidden(); }}>
            {hidden ? t("message.unhide") : t("message.hide")}
          </button>
        </div>
      )}
    </div>
  );
}
