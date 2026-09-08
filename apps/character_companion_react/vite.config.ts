import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Companion is a SEPARATE app from Character Lab. Its pinned toolchain versions
// match the Lab app exactly (see package.json); run `npm ci` here once to
// populate node_modules, or reuse the Lab app's binaries (see README).
//
// Dev-only proxy: HttpCompanionClient calls relative `/api/companion/...`
// paths; Vite forwards them to the loopback Companion server
// (tools/character_companion_server.py, fake provider only, port 8788).
export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    proxy: {
      "/api": { target: "http://127.0.0.1:8788", changeOrigin: false },
    },
  },
});
