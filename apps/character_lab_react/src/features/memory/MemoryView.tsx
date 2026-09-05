import { useCallback, useEffect, useState } from "react";
import { useAppState } from "../../app/AppState";
import { MemoryTable } from "../../components/devtools";
import { EmptyState, Panel, Toolbar } from "../../components/primitives";
import type { MemorySummary } from "../../client/types";

/** Developer/debug view: causal-order runtime memory for the SELECTED
 * workspace (memory is workspace-scoped, not session-scoped). In "local"
 * (Desktop Integration) mode this reads REAL memory through CharacterClient --
 * never mock data. */
export function MemoryView() {
  const { state, client } = useAppState();
  const workspaceId = state.selectedWorkspaceId;
  const [memory, setMemory] = useState<MemorySummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    if (!workspaceId) {
      setMemory(null);
      return;
    }
    setLoading(true);
    setError(null);
    setMemory(null);
    try {
      setMemory(await client.getMemory(workspaceId));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [client, workspaceId]);

  useEffect(() => {
    void reload();
  }, [reload, state.messages.length]);

  if (!workspaceId) {
    return (
      <Panel>
        <EmptyState title="Рабочая область ещё не готова" />
      </Panel>
    );
  }

  if (error) {
    return (
      <Panel>
        <EmptyState title="Ошибка памяти">Ошибка: {error}</EmptyState>
      </Panel>
    );
  }

  return (
    <Panel>
      <Toolbar>
        <div className="clab-form-field__label">
          Рабочая область: {workspaceId} · порядок: {memory?.causalOrder ?? "seq"} · событий:{" "}
          {memory?.eventCount ?? 0}
        </div>
      </Toolbar>
      {loading && !memory ? (
        <EmptyState title="Загрузка памяти…" />
      ) : (
        <MemoryTable events={memory?.events ?? []} />
      )}
    </Panel>
  );
}
