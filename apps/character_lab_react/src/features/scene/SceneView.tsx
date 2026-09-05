import { useEffect, useState } from "react";
import { useAppState } from "../../app/AppState";
import { SceneForm } from "../../components/character";
import { EmptyState, NotIntegratedNotice, Panel } from "../../components/primitives";
import type { SceneSummary, SetSceneInput } from "../../client/types";

/** Not yet transported in "local" (Desktop Integration v1) mode. */
export function SceneView() {
  const { state, client } = useAppState();
  const sessionId = state.session?.sessionId ?? null;
  const [scene, setSceneState] = useState<SceneSummary | null>(null);
  const notIntegrated = state.clientMode === "local";

  useEffect(() => {
    let cancelled = false;
    if (!sessionId || notIntegrated) return;
    client.getScene(sessionId).then((s) => {
      if (!cancelled) setSceneState(s);
    });
    return () => {
      cancelled = true;
    };
  }, [client, sessionId, notIntegrated]);

  if (notIntegrated) {
    return (
      <Panel>
        <NotIntegratedNotice capability="Сцена" />
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

  async function handleSet(input: SetSceneInput) {
    if (!sessionId) return;
    const updated = await client.setScene(sessionId, input);
    setSceneState(updated);
  }

  async function handleClear() {
    if (!sessionId) return;
    const updated = await client.clearScene(sessionId);
    setSceneState(updated);
  }

  return (
    <Panel>
      <SceneForm scene={scene} onSet={handleSet} onClear={handleClear} />
    </Panel>
  );
}
