import { useEffect, useState } from "react";
import { useAppState } from "../../app/AppState";
import { SceneForm } from "../../components/character";
import { EmptyState, Panel } from "../../components/primitives";
import type { SceneSummary, SetSceneInput } from "../../client/types";

export function SceneView() {
  const { state, client } = useAppState();
  const sessionId = state.session?.sessionId ?? null;
  const [scene, setSceneState] = useState<SceneSummary | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (!sessionId) return;
    client.getScene(sessionId).then((s) => {
      if (!cancelled) setSceneState(s);
    });
    return () => {
      cancelled = true;
    };
  }, [client, sessionId]);

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
