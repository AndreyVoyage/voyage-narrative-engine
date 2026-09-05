import { useAppState } from "../../app/AppState";
import { ChatPanel } from "../../components/character";
import { Panel } from "../../components/primitives";

/** Foundation Chat view: selected character/variant/session header, message
 * history, and a composer. `sendMessage` goes through `CharacterClient`
 * (mock in this slice) -- no real LLM call. */
export function ChatView() {
  const { state, sendMessage } = useAppState();
  const { session, messages } = state;

  return (
    <Panel>
      <div className="clab-toolbar">
        <div>
          <div style={{ fontWeight: 600 }}>
            {session ? `KIRA · ${session.variantId}` : "Сессия ещё не создана"}
          </div>
          <div className="clab-form-field__label">
            {session ? `session: ${session.sessionId.slice(0, 24)}…` : ""}
          </div>
        </div>
      </div>
      <ChatPanel messages={messages} disabled={!session} onSend={sendMessage} />
    </Panel>
  );
}
