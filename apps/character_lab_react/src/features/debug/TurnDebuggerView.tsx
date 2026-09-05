import { useEffect, useState } from "react";
import { useAppState } from "../../app/AppState";
import { TurnDebuggerPanel } from "../../components/devtools";
import { EmptyState, Inline, Panel } from "../../components/primitives";
import type { TurnDebugBundle, TurnSummary } from "../../client/types";

/** Explicitly developer/debug UI: pick a captured turn, then inspect its
 * context manifest (SELECTED/DELIVERED) and exact captured request. Never
 * exposes hidden reasoning -- `CharacterDebugClient` has nothing to expose. */
export function TurnDebuggerView() {
  const { state, debugClient } = useAppState();
  const sessionId = state.session?.sessionId ?? null;
  const [turns, setTurns] = useState<readonly TurnSummary[]>([]);
  const [selectedTurnId, setSelectedTurnId] = useState<string | null>(null);
  const [bundle, setBundle] = useState<TurnDebugBundle | null>(null);

  useEffect(() => {
    if (!sessionId) return;
    debugClient.listTurns(sessionId).then(setTurns);
  }, [debugClient, sessionId, state.messages.length]);

  useEffect(() => {
    if (!selectedTurnId) {
      setBundle(null);
      return;
    }
    debugClient.getTurnDebug(selectedTurnId).then(setBundle);
  }, [debugClient, selectedTurnId]);

  if (!sessionId) {
    return (
      <Panel>
        <EmptyState title="Сессия ещё не создана" />
      </Panel>
    );
  }

  return (
    <Panel>
      <Inline gap={2}>
        {turns.map((t) => (
          <button
            key={t.turnId}
            className="clab-btn"
            data-active={t.turnId === selectedTurnId ? "true" : "false"}
            onClick={() => setSelectedTurnId(t.turnId)}
          >
            {t.turnId.slice(0, 16)}…
          </button>
        ))}
        {turns.length === 0 && <span className="clab-form-field__label">Пока нет ходов.</span>}
      </Inline>
      <TurnDebuggerPanel bundle={bundle} />
    </Panel>
  );
}
