import { useEffect, useState } from "react";
import { useAppState } from "../../app/AppState";
import { RuntimeStateGroups } from "../../components/devtools";
import { EmptyState, NotIntegratedNotice, Panel, Toolbar } from "../../components/primitives";
import type { RuntimeStateSummary } from "../../client/types";

/** Developer/debug view: Runtime State (FACT / RELATIONSHIP / PSYCHOLOGY),
 * workspace-scoped. Real SET/ADJUST/REMOVE editing is deferred past this
 * foundation slice -- see the mock client for the in-memory shape. Not yet
 * transported in "local" (Desktop Integration v1) mode. */
export function StateView() {
  const { state, client } = useAppState();
  const workspaceId = state.session?.workspace.workspaceId ?? null;
  const [runtimeState, setRuntimeState] = useState<RuntimeStateSummary | null>(null);
  const notIntegrated = state.clientMode === "local";

  useEffect(() => {
    let cancelled = false;
    if (!workspaceId || notIntegrated) return;
    client.getRuntimeState(workspaceId).then((s) => {
      if (!cancelled) setRuntimeState(s);
    });
    return () => {
      cancelled = true;
    };
  }, [client, workspaceId, notIntegrated]);

  if (notIntegrated) {
    return (
      <Panel>
        <NotIntegratedNotice capability="Состояние" />
      </Panel>
    );
  }

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
          Рабочая область: {workspaceId} · домены: {(runtimeState?.domainsActive ?? []).join(", ")}
        </div>
      </Toolbar>
      <RuntimeStateGroups current={runtimeState?.current ?? []} />
    </Panel>
  );
}
