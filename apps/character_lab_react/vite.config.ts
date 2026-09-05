import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Minimal Vite config: React plugin + a dev-only API proxy. This app talks
// to CharacterClient / CharacterDebugClient -- never fetch()/URLs directly
// from feature code (see src/client/httpCharacterClient.ts, the only file
// with HTTP-specific concepts).
//
// The proxy below is a CHARACTER LAB DEVELOPMENT CONVENIENCE only: it lets
// HttpCharacterClient call relative `/api/...` paths (avoiding CORS
// entirely) which Vite forwards to the local loopback Character Lab React
// server (tools/character_lab_react_server.py, fake provider only, started
// separately -- see that module and tools/start_character_lab_react.ps1).
// This is NOT a statement about the canonical Character Core platform
// transport, which remains undecided (OD-CHAR-PLATFORM-01(A)).
//
// Port 8787 is `character_lab_react_server.py`'s DEFAULT_PORT -- a fixed
// local dev convenience value, not a machine-specific path; keep both in
// sync if it ever changes.
export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8787",
        changeOrigin: false,
      },
    },
  },
});
