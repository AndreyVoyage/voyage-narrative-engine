import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./app/App";
import { AppStateProvider, type ClientMode } from "./app/AppState";
import type { CharacterClient } from "./client/characterClient";
import { HttpCharacterClient } from "./client/httpCharacterClient";
import { MockCharacterClient } from "./mocks/mockCharacterClient";
import { MockCharacterDebugClient } from "./mocks/mockCharacterDebugClient";

import "./styles/tokens.css";
import "./styles/global.css";
import "./styles/layout.css";
import "./styles/components.css";

// Transport-neutral by construction: main.tsx is the ONLY place a concrete
// CharacterClient implementation is chosen, based on VITE_CHARACTER_CLIENT
// ("mock" (default) or "local" -- see .env.local-core / "npm run dev:local").
// Swapping the client never touches App.tsx or any feature/component code.
//
// CharacterDebugClient stays MockCharacterDebugClient in BOTH modes for this
// slice -- Desktop Integration v1 does not transport Turn Debugger data;
// wiring a live debug client is explicitly deferred.
const clientMode: ClientMode = import.meta.env.VITE_CHARACTER_CLIENT === "local" ? "local" : "mock";

const client: CharacterClient = clientMode === "local" ? new HttpCharacterClient() : new MockCharacterClient();
const debugClient = new MockCharacterDebugClient();

const container = document.getElementById("root");
if (!container) {
  throw new Error("#root element not found");
}

createRoot(container).render(
  <StrictMode>
    <AppStateProvider client={client} debugClient={debugClient} clientMode={clientMode}>
      <App />
    </AppStateProvider>
  </StrictMode>
);
