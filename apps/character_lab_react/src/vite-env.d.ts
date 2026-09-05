/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Explicit Character Client selection for this app only:
   *  - "mock" (default when unset) -- MockCharacterClient, no backend needed;
   *  - "local" -- HttpCharacterClient over the local loopback Character Lab
   *    React server (see tools/character_lab_react_server.py), via Vite's
   *    dev proxy. Set by `.env.local-core` under the `local-core` mode
   *    (`npm run dev:local`) -- never a machine-specific absolute path. */
  readonly VITE_CHARACTER_CLIENT?: "mock" | "local";
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
