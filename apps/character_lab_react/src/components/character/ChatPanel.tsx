import { useState } from "react";
import type { ChatMessage } from "../../app/AppState";
import { EmptyState } from "../primitives/EmptyState";

export interface ChatPanelProps {
  readonly messages: readonly ChatMessage[];
  readonly disabled?: boolean;
  readonly onSend: (text: string) => void;
}

/**
 * A reusable character-facing conversation view: message history + input
 * composer. Deliberately free of any developer/debug affordance (no request
 * hash, no manifest, no provenance) -- those live in `components/devtools`
 * instead, so a future consumer Character App can reuse this component
 * without inheriting debugging tools.
 */
export function ChatPanel({ messages, disabled, onSend }: ChatPanelProps) {
  const [draft, setDraft] = useState("");

  function handleSend() {
    if (!draft.trim()) return;
    onSend(draft);
    setDraft("");
  }

  return (
    <div className="clab-stack clab-gap-3" style={{ minHeight: "60vh" }}>
      <div className="clab-chat-messages">
        {messages.length === 0 && (
          <EmptyState title="Пока нет сообщений">
            Начните разговор, отправив первое сообщение ниже.
          </EmptyState>
        )}
        {messages.map((m) => (
          <div key={m.id} className="clab-chat-bubble" data-role={m.role}>
            {m.text}
          </div>
        ))}
      </div>
      <div className="clab-inline clab-gap-2">
        <textarea
          className="clab-textarea"
          placeholder="Написать сообщение..."
          value={draft}
          disabled={disabled}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
          rows={2}
          style={{ flex: "1 1 auto" }}
        />
        <button className="clab-btn clab-btn--primary" disabled={disabled} onClick={handleSend}>
          Отправить
        </button>
      </div>
    </div>
  );
}
