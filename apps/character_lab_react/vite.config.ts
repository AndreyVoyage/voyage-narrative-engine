import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Minimal Vite config: React plugin only. No backend transport, no proxy,
// no dev-server API assumptions -- this app talks to CharacterClient /
// CharacterDebugClient (currently the mock implementations), never a URL.
export default defineConfig({
  plugins: [react()],
});
