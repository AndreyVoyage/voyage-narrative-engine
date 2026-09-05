import { useEffect, useState } from "react";
import { useAppState } from "../../app/AppState";
import { TurnDebuggerPanel } from "../../components/devtools";
import { EmptyState, Inline, NotIntegratedNotice, Panel } from "../../components/primitives";
import type { TurnDebugBundle, TurnSummary } from "../../client/types";

/** Explicitly developer/debug UI: pick a captured turn, then inspect its
 * context manifest (SELECTED/DELIVERED) and exact captured request. Never
 * exposes hidden reasoning -- `CharacterDebugClient` has nothing to expose.
 *
 * `CharacterDebugClient` stays `MockCharacterDebugClient` in every client
 * mode for this slice -- Turn Debugger is explicitly deferred, not
 * transported. In "local" (Desktop Integration v1) mode this view shows the
 * same honest "not integrated" notice as Memory/State/Scene rather than
 * silently displaying mock turns next to a live chat session. */
export function TurnDebuggerView() {
  const { state, debugClient } = useAppState();
  const sessionId = state.session?.sessionId ?? null;
  const [turns, setTurns] = useState<readonly TurnSummary[]>([]);
  const [selectedTurnId, setSelectedTurnId] = useState<string | null>(null);
  const [bundle, setBundle] = useState<TurnDebugBundle | null>(null);
  const notIntegrated = state.clientMode === "local";

  useEffect(() => {
    if (!sessionId || notIntegrated) return;
    debugClient.listTurns(sessionId).then(setTurns);
  }, [debugClient, sessionId, notIntegrated, state.messages.length]);

  useEffect(() => {
    if (!selectedTurnId || notIntegrated) {
      setBundle(null);
      return;
    }
    debugClient.getTurnDebug(selectedTurnId).then(setBundle);
  }, [debugClient, selectedTurnId, notIntegrated]);

  if (notIntegrated) {
    return (
      <Panel>
        <NotIntegratedNotice capability="Turn Debugger" />
      </Panel>
    );
  }

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
