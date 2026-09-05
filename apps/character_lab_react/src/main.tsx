import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./app/App";
import { AppStateProvider } from "./app/AppState";
import { MockCharacterClient } from "./mocks/mockCharacterClient";
import { MockCharacterDebugClient } from "./mocks/mockCharacterDebugClient";

import "./styles/tokens.css";
import "./styles/global.css";
import "./styles/layout.css";
import "./styles/components.css";

// Transport-neutral by construction: main.tsx is the ONLY place a concrete
// CharacterClient implementation is chosen. Swapping the mock for a future
// transport adapter never touches App.tsx or any feature/component code.
const client = new MockCharacterClient();
const debugClient = new MockCharacterDebugClient();

const container = document.getElementById("root");
if (!container) {
  throw new Error("#root element not found");
}

createRoot(container).render(
  <StrictMode>
    <AppStateProvider client={client} debugClient={debugClient}>
      <App />
    </AppStateProvider>
  </StrictMode>
);
