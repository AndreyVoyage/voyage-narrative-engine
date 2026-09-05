/**
 * Minimum-sufficient RUNTIME structural checks for the React Character Lab
 * foundation's transport-neutral client layer.
 *
 * Runs entirely against the plain-TypeScript `client`/`mocks` files (no
 * `react` import anywhere in the dependency graph, and no Node built-ins
 * either, so it needs no `@types/node`), so it can be compiled and executed
 * with only the machine's existing global TypeScript compiler and Node.js --
 * no npm install, no network.
 *
 * Text-based checks (no HTTP concepts in the contract source, no imports
 * from Python internals) are run separately via plain `grep` -- see
 * `apps/character_lab_react/README.md` and the task's final report for the
 * exact commands and results.
 *
 * How to run (from `apps/character_lab_react/`, via the "structural-checks"
 * npm script, or manually):
 *   npx tsc --project tsconfig.checks.json
 *   node dist-checks/scripts/structural-checks.js
 *
 * Import specifiers below use an explicit ".js" extension (resolving to the
 * ".ts" source at typecheck time, per TypeScript's standard ESM+Node
 * convention) because package.json declares "type": "module" -- Node's
 * native ESM loader requires explicit extensions for relative imports, and
 * the compiler otherwise leaves these specifiers untouched in its output.
 */

import {
  ALL_SESSION_PURPOSES,
  SessionPurpose,
  SessionPurposeNotImplementedError,
  SUPPORTED_SESSION_PURPOSES,
  isSessionPurposeSupported,
} from "../src/client/types.js";
import { MockCharacterClient } from "../src/mocks/mockCharacterClient.js";
import { MockCharacterDebugClient } from "../src/mocks/mockCharacterDebugClient.js";

let passed = 0;
let failed = 0;

function check(name: string, condition: boolean) {
  if (condition) {
    passed += 1;
    console.log(`  ok  - ${name}`);
  } else {
    failed += 1;
    console.log(`FAIL  - ${name}`);
  }
}

async function checkAsync(name: string, fn: () => Promise<boolean>) {
  try {
    check(name, await fn());
  } catch (err) {
    failed += 1;
    console.log(`FAIL  - ${name} (threw: ${err instanceof Error ? err.message : String(err)})`);
  }
}

async function main() {
  console.log("Character Lab React foundation -- structural checks (runtime)\n");

  // 2. CharacterDebugClient is a genuinely separate object from
  //    CharacterClient -- distinct classes, distinct method surfaces.
  const client = new MockCharacterClient();
  const debugClient = new MockCharacterDebugClient();
  check(
    "2. MockCharacterDebugClient is a distinct class from MockCharacterClient",
    Object.getPrototypeOf(client) !== Object.getPrototypeOf(debugClient)
  );
  check(
    "2b. CharacterClient instance has no debug-only methods",
    !("listTurns" in client) && !("getTurnDebug" in client) && !("getContextManifest" in client)
  );
  check(
    "2c. CharacterDebugClient instance has no chat/session methods",
    !("sendMessage" in debugClient) && !("createSession" in debugClient)
  );

  // 3. SessionPurpose has exactly the four expected values.
  check(
    "3. SessionPurpose has exactly TESTING/AUTHORING/GAME_RUNTIME/COMPANION",
    ALL_SESSION_PURPOSES.length === 4 &&
      new Set(ALL_SESSION_PURPOSES).size === 4 &&
      ALL_SESSION_PURPOSES.includes(SessionPurpose.TESTING) &&
      ALL_SESSION_PURPOSES.includes(SessionPurpose.AUTHORING) &&
      ALL_SESSION_PURPOSES.includes(SessionPurpose.GAME_RUNTIME) &&
      ALL_SESSION_PURPOSES.includes(SessionPurpose.COMPANION)
  );

  // 4. mock supports TESTING (and only TESTING).
  check(
    "4. only TESTING is supported",
    isSessionPurposeSupported(SessionPurpose.TESTING) &&
      !isSessionPurposeSupported(SessionPurpose.AUTHORING) &&
      !isSessionPurposeSupported(SessionPurpose.GAME_RUNTIME) &&
      !isSessionPurposeSupported(SessionPurpose.COMPANION) &&
      SUPPORTED_SESSION_PURPOSES.length === 1
  );

  // 5. Experimental is unavailable.
  await checkAsync("5. EXPERIMENTAL variant is unavailable", async () => {
    const variants = await client.listVariants("kira");
    const experimental = variants.find((v) => v.variantId === "EXPERIMENTAL");
    return experimental !== undefined && experimental.implemented === false;
  });

  // 6. workspace ids are explicit -- create_session never silently creates one.
  await checkAsync("6. create_session rejects an unknown workspace id", async () => {
    try {
      await client.createSession("kira", "KIRA_BETA_V1_CURRENT", SessionPurpose.TESTING, "bogus-ws");
      return false;
    } catch {
      return true;
    }
  });
  await checkAsync("6b. unsupported purpose raises SessionPurposeNotImplementedError", async () => {
    const ws = await client.createTestWorkspace();
    try {
      await client.createSession("kira", "KIRA_BETA_V1_CURRENT", SessionPurpose.AUTHORING, ws.workspaceId);
      return false;
    } catch (err) {
      return err instanceof SessionPurposeNotImplementedError && err.purpose === SessionPurpose.AUTHORING;
    }
  });
  await checkAsync("6c. successful create_session adds no NEW workspace", async () => {
    const before = (await client.listWorkspaces()).length;
    const ws = await client.createTestWorkspace();
    await client.createSession("kira", "KIRA_BETA_V1_CURRENT", SessionPurpose.TESTING, ws.workspaceId);
    const afterCreateTestWorkspace = before + 1;
    const after = (await client.listWorkspaces()).length;
    return after === afterCreateTestWorkspace;
  });

  // 7. Memory/Runtime State use workspaceId (single-argument, not sessionId).
  check(
    "7. getMemory/getRuntimeState each take exactly one argument (workspaceId)",
    client.getMemory.length === 1 && client.getRuntimeState.length === 1
  );
  await checkAsync("7b. memory is workspace-scoped across two sessions", async () => {
    const ws = await client.createTestWorkspace();
    const s1 = await client.createSession("kira", "KIRA_BETA_V1_CURRENT", SessionPurpose.TESTING, ws.workspaceId);
    await client.sendMessage(s1.sessionId, "hello from s1");
    const s2 = await client.createSession("kira", "KIRA_BETA_V1_CURRENT", SessionPurpose.TESTING, ws.workspaceId);
    await client.sendMessage(s2.sessionId, "hello from s2");
    const memory = await client.getMemory(ws.workspaceId);
    const sessionIds = new Set(memory.events.map((e) => e.sessionId));
    return memory.eventCount === 4 && sessionIds.has(s1.sessionId) && sessionIds.has(s2.sessionId);
  });

  // 8. Scene uses sessionId.
  check(
    "8. getScene/setScene/clearScene are session-scoped by arity",
    client.getScene.length === 1 && client.setScene.length === 2 && client.clearScene.length === 1
  );

  // 9/10 (app shell nav destinations + debug-UI separation) pertain to the
  // .tsx layer, which cannot be executed without react/@types/react
  // installed -- verified by direct source review instead (see the task's
  // final report and docs/character_lab/REACT_CHARACTER_LAB_FOUNDATION_V1.md).

  console.log(`\n${passed} passed, ${failed} failed`);
  if (failed > 0) {
    throw new Error(`${failed} structural check(s) failed`);
  }
}

void main();
