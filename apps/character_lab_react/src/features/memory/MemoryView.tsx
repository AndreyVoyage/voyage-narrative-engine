import { useEffect, useState } from "react";
import { useAppState } from "../../app/AppState";
import { MemoryTable } from "../../components/devtools";
import { EmptyState, Panel, Toolbar } from "../../components/primitives";
import type { MemorySummary } from "../../client/types";

/** Developer/debug view: causal-order runtime memory for the current
 * session's workspace (memory is workspace-scoped, not session-scoped). */
export function MemoryView() {
  const { state, client } = useAppState();
  const workspaceId = state.session?.workspace.workspaceId ?? null;
  const [memory, setMemory] = useState<MemorySummary | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (!workspaceId) return;
    client.getMemory(workspaceId).then((m) => {
      if (!cancelled) setMemory(m);
    });
    return () => {
      cancelled = true;
    };
  }, [client, workspaceId, state.messages.length]);

  if (!workspaceId) {
    return (
      <Panel>
        <EmptyState title="Рабочая область ещё не готова" />
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
      <MemoryTable events={memory?.events ?? []} />
    </Panel>
  );
}
