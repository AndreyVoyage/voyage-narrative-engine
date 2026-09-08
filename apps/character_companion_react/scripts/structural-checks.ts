/**
 * Minimum-sufficient RUNTIME structural checks for the Character Companion
 * client layer. Compiles and runs with only a global TypeScript compiler and
 * Node.js -- no npm install, no DOM, no React, no network.
 *
 *   tsc --project tsconfig.checks.json
 *   node dist-checks/scripts/structural-checks.js
 *
 * Text-based checks (no HTTP concepts outside httpCompanionClient, no imports
 * from the Character Lab app, no debug/operator surface) are run separately via
 * grep -- see the task report.
 */

import {
  CompanionClient,
  CompanionClientError,
} from "../src/client/types.js";
import { HttpCompanionClient } from "../src/client/httpCompanionClient.js";
import { MockCompanionClient } from "../src/mocks/mockCompanionClient.js";
import {
  companionReducer,
  initialCompanionState,
  isSendableMessage,
} from "../src/app/companionState.js";

// Node global -- declared locally so the check compiles with a bare global
// TypeScript (no @types/node, matching the Character Lab structural checks).
declare const process: { exit(code: number): never };

function assert(cond: unknown, message: string): asserts cond {
  if (!cond) throw new Error(message);
}

let passed = 0;
function ok(label: string): void {
  passed += 1;
  console.log(`  ok  - ${label}`);
}

async function main(): Promise<void> {
  console.log("Character Companion -- structural checks (runtime)\n");

  // 30 -- character list is a real client operation returning entries
  const mock = new MockCompanionClient();
  const chars = await mock.listCharacters();
  assert(chars.length === 1 && chars[0].characterId === "kira", "kira in catalog");
  ok("30. listCharacters returns available characters");

  // 31 + 32 -- session list + new-session action exist and persist per instance
  assert((await mock.listSessions("kira")).length === 0, "no sessions yet");
  const session = await mock.createSession("kira");
  assert(session.purpose === "COMPANION", "created session is COMPANION purpose");
  const sessions = await mock.listSessions("kira");
  assert(sessions.length === 1 && sessions[0].sessionId === session.sessionId, "session listed");
  ok("31. listSessions exists and is per-character");
  ok("32. createSession action exists");

  // 33 -- chat history is a normalized user/character message array
  assert((await mock.getMessages(session.sessionId)).length === 0, "empty history");
  const turn = await mock.sendMessage(session.sessionId, "Привет.");
  assert(
    turn.messages.map((m) => m.role).join(",") === "user,character",
    "history has one user + one character turn in causal order",
  );
  const seqs = turn.messages.map((m) => m.seq ?? -1);
  assert(seqs[0] < seqs[1], "messages are causally ordered by seq");
  ok("33. chat history renders as ordered user/character turns");

  // 34 -- the composer path goes through CompanionClient, not fetch
  const client: CompanionClient = mock;
  assert(typeof client.sendMessage === "function", "sendMessage is the composer path");
  const httpSrc = HttpCompanionClient.toString();
  assert(httpSrc.includes("sendMessage"), "HttpCompanionClient implements sendMessage");
  ok("34. composer sends through CompanionClient");

  // 35 -- loading + error state exist in the pure state machine
  const loading = companionReducer(initialCompanionState, { type: "loadStart", scope: "messages" });
  assert(loading.loading === "messages" && loading.error === null, "loading state");
  const errored = companionReducer(loading, { type: "loadFailed", code: "backend_unavailable", message: "Нет подключения" });
  assert(errored.error?.code === "backend_unavailable" && errored.loading === "idle", "error state");
  ok("35. bounded loading + error states exist");

  // 36 -- no Character Lab debug surface leaks into the client contract
  const contractSrc = [MockCompanionClient.toString(), httpSrc].join("\n").toLowerCase();
  for (const forbidden of ["manifest", "evolution", "runtime_state", "runtimestate", "debug", "workspace", "epistemic"]) {
    assert(!contractSrc.includes(forbidden), `client contract free of '${forbidden}'`);
  }
  ok("36. no Character Lab debug/operator surface in the client");

  // 37 -- switching character clears stale selected session + transcript
  let s = companionReducer(initialCompanionState, { type: "charactersLoaded", characters: chars });
  s = companionReducer(s, { type: "selectCharacter", characterId: "kira" });
  s = companionReducer(s, { type: "sessionsLoaded", sessions });
  s = companionReducer(s, { type: "selectSession", sessionId: session.sessionId });
  s = companionReducer(s, { type: "messagesLoaded", messages: turn.messages });
  assert(s.messages.length === 2 && s.selectedSessionId === session.sessionId, "state primed");
  const switched = companionReducer(s, { type: "selectCharacter", characterId: "other" });
  assert(
    switched.selectedSessionId === null && switched.messages.length === 0 && switched.sessions.length === 0,
    "character switch clears session + transcript + session list",
  );
  ok("37. switching character clears stale session/history");

  // 38 -- switching session clears the transcript pending a reload
  const reselSame = companionReducer(s, { type: "selectSession", sessionId: session.sessionId });
  assert(reselSame === s, "re-selecting the same session is a no-op");
  const reselOther = companionReducer(s, { type: "selectSession", sessionId: "cmp-other" });
  assert(reselOther.selectedSessionId === "cmp-other" && reselOther.messages.length === 0, "session switch clears until reload");
  const reloaded = companionReducer(reselOther, { type: "messagesLoaded", messages: [] });
  assert(reloaded.loading === "idle", "reload lands");
  ok("38. switching session reloads history");

  // 39 + 40 -- a failed send shows a bounded error and KEEPS prior messages
  const sending = companionReducer(s, { type: "sendStart" });
  assert(sending.loading === "sending", "send in flight");
  const failed = companionReducer(sending, { type: "sendFailed", code: "provider_failed", message: "Сбой" });
  assert(failed.error?.code === "provider_failed", "bounded error surfaced");
  assert(failed.messages.length === 2 && failed.messages === s.messages, "prior transcript preserved after failed send");
  ok("39. failed send shows a bounded error");
  ok("40. previously persisted messages remain after a failed send");

  // composer guard + error type
  assert(!isSendableMessage("   ") && isSendableMessage("hi"), "blank messages are not sendable");
  assert(new CompanionClientError(404, "unknown_session", "x").code === "unknown_session", "typed client error");
  ok("composer rejects blank input; typed client errors");

  // the mock's simulated failure must not corrupt history
  const m2 = new MockCompanionClient();
  const sess2 = await m2.createSession("kira");
  await m2.sendMessage(sess2.sessionId, "one");
  m2.failSendOnce();
  let threw = false;
  try {
    await m2.sendMessage(sess2.sessionId, "two");
  } catch (e) {
    threw = e instanceof CompanionClientError && e.code === "provider_failed";
  }
  assert(threw, "simulated failure raised a bounded error");
  assert((await m2.getMessages(sess2.sessionId)).length === 2, "history intact after failed send");
  ok("mock failure path leaves history intact");

  console.log(`\n${passed} passed, 0 failed`);
}

main().catch((err) => {
  console.error("\nFAILED:", err instanceof Error ? err.message : err);
  process.exit(1);
});
