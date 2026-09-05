import { useCallback, useEffect, useState } from "react";
import { useAppState } from "../../app/AppState";
import { RuntimeStateGroups } from "../../components/devtools";
import { EmptyState, Panel, Toolbar } from "../../components/primitives";
import type { RuntimeStateSummary } from "../../client/types";
import { StateEditor } from "./StateEditor";

/** Developer/debug view: Runtime State (FACT / RELATIONSHIP / PSYCHOLOGY),
 * workspace-scoped. In "local" mode this reads REAL state through
 * CharacterClient and edits it through SET / ADJUST / REMOVE -- never mock
 * data. */
export function StateView() {
  const { state, client } = useAppState();
  const workspaceId = state.selectedWorkspaceId;
  const [runtimeState, setRuntimeState] = useState<RuntimeStateSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    if (!workspaceId) {
      setRuntimeState(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setRuntimeState(await client.getRuntimeState(workspaceId));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [client, workspaceId]);

  useEffect(() => {
    void reload();
  }, [reload]);

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
        <EmptyState title="Ошибка состояния">Ошибка: {error}</EmptyState>
      </Panel>
    );
  }

  return (
    <Panel>
      <Toolbar>
        <div className="clab-form-field__label">
          Рабочая область: {workspaceId} · домены: {(runtimeState?.domainsActive ?? []).join(", ")}
        </div>
      </Toolbar>
      {loading && !runtimeState ? (
        <EmptyState title="Загрузка состояния…" />
      ) : (
        <RuntimeStateGroups current={runtimeState?.current ?? []} />
      )}
      <StateEditor
        client={client}
        workspaceId={workspaceId}
        current={runtimeState?.current ?? []}
        onChanged={reload}
      />
    </Panel>
  );
}
