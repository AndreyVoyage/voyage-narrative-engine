import { useAppState } from "./AppState";
import { AppShell, InspectorPanel, MainPanel, Sidebar } from "../components/layout";
import { CharacterLabMark, InspectorIcon } from "../components/icons";
import { Card, Inline, Section, Stack } from "../components/primitives";
import { NAV_ITEMS, type FeatureKey } from "../navigation/navigation";
import { ChatView } from "../features/chat/ChatView";
import { CharacterView } from "../features/character/CharacterView";
import { MemoryView } from "../features/memory/MemoryView";
import { StateView } from "../features/state/StateView";
import { SceneView } from "../features/scene/SceneView";
import { TurnDebuggerView } from "../features/debug/TurnDebuggerView";

function renderFeature(mode: FeatureKey) {
  switch (mode) {
    case "chat":
      return <ChatView />;
    case "character":
      return <CharacterView />;
    case "memory":
      return <MemoryView />;
    case "state":
      return <StateView />;
    case "scene":
      return <SceneView />;
    case "turnDebugger":
      return <TurnDebuggerView />;
    default:
      return null;
  }
}

function Topbar() {
  const { state, setMode, setSidebarOpen, setInspectorOpen } = useAppState();
  return (
    <>
      <div className="clab-topbar__left">
        <button
          className="clab-btn clab-icon-btn"
          aria-label="Меню"
          aria-expanded={state.sidebarOpen}
          aria-controls="clab-app-sidebar"
          onClick={() => setSidebarOpen(!state.sidebarOpen)}
          data-narrow-only="true"
        >
          ☰
        </button>
        <div className="clab-brand">
          <CharacterLabMark className="clab-brand__mark" />
          Character Lab <span className="clab-brand__badge">REACT · FOUNDATION</span>
        </div>
      </div>
      <div className="clab-topbar__center">
        <nav className="clab-mode-nav">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.key}
              className="clab-mode-nav__item"
              data-tier={item.tier}
              data-active={state.mode === item.key ? "true" : "false"}
              onClick={() => {
                setMode(item.key);
                // Selecting a destination closes the narrow-width Sidebar
                // drawer; a no-op when it's already closed (desktop/medium).
                setSidebarOpen(false);
              }}
            >
              {item.label}
            </button>
          ))}
        </nav>
      </div>
      <div className="clab-topbar__right">
        <button
          className="clab-btn clab-icon-btn"
          aria-label="Инспектор"
          title="Инспектор"
          aria-expanded={state.inspectorOpen}
          aria-controls="clab-app-inspector"
          onClick={() => setInspectorOpen(!state.inspectorOpen)}
          data-medium-only="true"
        >
          <InspectorIcon />
        </button>
      </div>
    </>
  );
}

function CharacterAndVariantList() {
  const { state, selectVariant } = useAppState();
  return (
    <Stack gap={2}>
      <div className="clab-section__title">Персонажи</div>
      <ul className="clab-select-list">
        {state.characters.map((c) => (
          <li key={c.characterId} className="clab-select-list__item" data-active="true">
            {c.displayName}
          </li>
        ))}
      </ul>
      <ul className="clab-select-list" style={{ paddingLeft: "var(--clab-space-3)" }}>
        {state.variants.map((v) => (
          <li
            key={v.variantId}
            className="clab-select-list__item"
            data-active={v.variantId === state.session?.variantId ? "true" : "false"}
            data-disabled={v.implemented ? "false" : "true"}
            onClick={() => v.implemented && void selectVariant(v.variantId)}
          >
            {v.displayName}
            {!v.implemented && <div className="clab-select-list__sub">{v.status ?? "недоступно"}</div>}
          </li>
        ))}
      </ul>
    </Stack>
  );
}

function SessionsList() {
  const { state, startNewCleanTestSession } = useAppState();
  return (
    <Stack gap={2}>
      <div className="clab-section__title">Сессии</div>
      <button className="clab-btn clab-btn--primary" onClick={() => void startNewCleanTestSession()}>
        + Новая сессия
      </button>
      {state.session && (
        <ul className="clab-select-list">
          <li className="clab-select-list__item" data-active="true">
            {state.session.sessionId.slice(0, 24)}…
            <div className="clab-select-list__sub">{state.session.workspace.displayName}</div>
          </li>
        </ul>
      )}
    </Stack>
  );
}

function LoadedStateInspector() {
  const { state } = useAppState();
  return (
    <Stack gap={4}>
      <Section title="Загруженное состояние">
        <Card>
          <Stack gap={1}>
            <Inline gap={2}>
              <span className="clab-form-field__label">character</span>
              <span>kira</span>
            </Inline>
            <Inline gap={2}>
              <span className="clab-form-field__label">variant</span>
              <span>{state.session?.variantId ?? "—"}</span>
            </Inline>
            <Inline gap={2}>
              <span className="clab-form-field__label">workspace</span>
              <span>{state.session?.workspace.workspaceKind ?? "—"}</span>
            </Inline>
            <Inline gap={2}>
              <span className="clab-form-field__label">purpose</span>
              <span className="clab-badge clab-badge--ok">{state.session?.purpose ?? "—"}</span>
            </Inline>
            <Inline gap={2}>
              <span className="clab-form-field__label">транспорт</span>
              <span className="clab-badge">mock (dev)</span>
            </Inline>
          </Stack>
        </Card>
      </Section>
      {state.error && (
        <Section title="Ошибка">
          <Card>
            <span style={{ color: "var(--clab-danger)" }}>{state.error}</span>
          </Card>
        </Section>
      )}
    </Stack>
  );
}

export function App() {
  const { state, setSidebarOpen, setInspectorOpen } = useAppState();

  return (
    <AppShell
      topbar={<Topbar />}
      sidebar={
        <Sidebar>
          <CharacterAndVariantList />
          <SessionsList />
        </Sidebar>
      }
      main={<MainPanel>{renderFeature(state.mode)}</MainPanel>}
      inspector={
        <InspectorPanel>
          <LoadedStateInspector />
        </InspectorPanel>
      }
      sidebarOpen={state.sidebarOpen}
      inspectorOpen={state.inspectorOpen}
      onRequestCloseSidebar={() => setSidebarOpen(false)}
      onRequestCloseInspector={() => setInspectorOpen(false)}
    />
  );
}
