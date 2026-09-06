/**
 * Minimum-sufficient RUNTIME structural checks for the React Character Lab
 * foundation's transport-neutral client layer.
 *
 * Runs entirely against the plain-TypeScript `client`/`mocks` files and (as
 * of the REACT_RELATIONSHIP_STATE_KEY_PAYLOAD_FIX_V1 regression, check 16)
 * `react`'s `createElement` -- a real dependency already installed for the
 * app itself, called directly (never rendered), so no jsdom/renderer/DOM and
 * no Node built-ins are needed either (so it still needs no `@types/node`),
 * and it can be compiled and executed with only the machine's existing
 * global TypeScript compiler and Node.js -- no npm install, no network.
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
  NotIntegratedInTransportError,
  SessionPurpose,
  SessionPurposeNotImplementedError,
  SUPPORTED_SESSION_PURPOSES,
  isSessionPurposeSupported,
} from "../src/client/types.js";
import { createElement } from "react";
import { MockCharacterClient } from "../src/mocks/mockCharacterClient.js";
import { MockCharacterDebugClient } from "../src/mocks/mockCharacterDebugClient.js";
import { HttpCharacterClient } from "../src/client/httpCharacterClient.js";
import { parseDeltaInput } from "../src/features/state/stateInput.js";

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

  // --- Desktop Integration v1 (HttpCharacterClient / local loopback) ---

  // 13. HttpCharacterClient is a genuinely separate concrete class from
  //     MockCharacterClient -- Desktop Integration v1 adds a new transport,
  //     it does not repurpose or wrap the mock's in-memory implementation.
  const httpClient = new HttpCharacterClient();
  check(
    "13. HttpCharacterClient is a distinct class from MockCharacterClient",
    Object.getPrototypeOf(httpClient) !== Object.getPrototypeOf(client)
  );
  check(
    "13b. HttpCharacterClient implements the full CharacterClient method surface",
    typeof httpClient.listCharacters === "function" &&
      typeof httpClient.getCharacter === "function" &&
      typeof httpClient.listVariants === "function" &&
      typeof httpClient.capabilities === "function" &&
      typeof httpClient.listWorkspaces === "function" &&
      typeof httpClient.getWorkspace === "function" &&
      typeof httpClient.createTestWorkspace === "function" &&
      typeof httpClient.createSession === "function" &&
      typeof httpClient.getSession === "function" &&
      typeof httpClient.sendMessage === "function" &&
      typeof httpClient.getMemory === "function" &&
      typeof httpClient.getRuntimeState === "function" &&
      typeof httpClient.setRuntimeState === "function" &&
      typeof httpClient.adjustRuntimeState === "function" &&
      typeof httpClient.removeRuntimeState === "function" &&
      typeof httpClient.getScene === "function" &&
      typeof httpClient.setScene === "function" &&
      typeof httpClient.clearScene === "function"
  );

  // 14. Scene is the only remaining capability not transported in Desktop
  //     Integration v1. It rejects with a clear typed error IMMEDIATELY --
  //     never a network call, never a fabricated successful result. Run with
  //     no server listening on 127.0.0.1:8787 to prove no network call
  //     happens: a fetch attempt would reject with a connection error, not
  //     resolve to this specific typed error.
  await checkAsync(
    "14. getScene/setScene/clearScene reject with NotIntegratedInTransportError (no fake data, no network call)",
    async () => {
      try {
        await httpClient.getScene("bogus-session-no-server-listening");
        return false;
      } catch (err) {
        if (!(err instanceof NotIntegratedInTransportError) || err.capability !== "scene") return false;
      }
      try {
        await httpClient.setScene("bogus-session-no-server-listening", { location: "x" });
        return false;
      } catch (err) {
        if (!(err instanceof NotIntegratedInTransportError) || err.capability !== "scene") return false;
      }
      try {
        await httpClient.clearScene("bogus-session-no-server-listening");
        return false;
      } catch (err) {
        return err instanceof NotIntegratedInTransportError && err.capability === "scene";
      }
    }
  );

  // 15. Runtime State delta normalization: a redundant leading "+" is
  //     normalized exactly as the existing Character Lab does ("+10" -> "10"),
  //     in ONE shared helper used by both RELATIONSHIP and PSYCHOLOGY. It does
  //     not weaken backend canonical validation -- it only fixes the + sign.
  check(
    "15. delta input normalizes a redundant leading '+' (+10 -> 10) and rejects non-integers",
    parseDeltaInput("+10") === 10 &&
      parseDeltaInput("10") === 10 &&
      parseDeltaInput("-15") === -15 &&
      parseDeltaInput("  +10  ") === 10 &&
      parseDeltaInput("abc") === null &&
      parseDeltaInput("") === null &&
      parseDeltaInput("10.5") === null
  );

  // 16. REGRESSION (REACT_RELATIONSHIP_STATE_KEY_PAYLOAD_FIX_V1): the actual
  //     production defect was `StateEditor.tsx`'s `NumericEditor` declaring a
  //     component prop literally named `key` -- React's reserved
  //     reconciliation attribute, which it strips from `props` before the
  //     component ever sees it. `<NumericEditor key={relationshipKey} .../>`
  //     therefore delivered `key === undefined` at the mutation call sites
  //     even though the displayed computed key ("andrey.trust") was correct,
  //     producing the exact symptom: "'key' must be a non-empty string" from
  //     `react_transport.py`'s `_require_str_field`. The fix renamed the data
  //     prop to `stateKey`. This check proves the underlying mechanism
  //     generically (any component prop named exactly `key` is swallowed by
  //     React and never reaches `props`), using the project's own `react`
  //     dependency -- no jsdom/renderer/new test framework needed, since
  //     `createElement` never invokes the component function.
  check(
    "16. a prop literally named 'key' never reaches props (the exact StateEditor.tsx defect class)",
    (() => {
      // React reserves `key` for reconciliation: it's moved to `element.key`,
      // and `element.props.key` is left as a non-enumerable warning-getter
      // that always resolves to `undefined` -- so `const { key } = props`
      // (exactly what the old `NumericEditor({ ..., key })` destructure did)
      // silently yields `undefined`, never the passed value. Muting
      // console.error here only suppresses React's own dev warning about
      // this access; it does not affect the assertion.
      const originalConsoleError = console.error;
      console.error = () => {};
      let propsKey: unknown;
      let propsHasEnumerableKey: boolean;
      try {
        const el = createElement("div", { key: "andrey.trust", stateKey: "andrey.trust", domain: "RELATIONSHIP" });
        propsKey = el.props.key;
        propsHasEnumerableKey = Object.keys(el.props).includes("key");
        return (
          el.key === "andrey.trust" &&
          propsKey === undefined &&
          !propsHasEnumerableKey &&
          (el.props as any).stateKey === "andrey.trust"
        );
      } finally {
        console.error = originalConsoleError;
      }
    })()
  );

  // 17. Client-level regression for the actual payloads the fix must produce
  //     (`StateEditor` -> `CharacterClient` -> `HttpCharacterClient` -> JSON
  //     body), intercepting `fetch` so no real network call happens.
  const originalFetch = globalThis.fetch;
  let lastRequest: { path: string; body: any } | null = null;
  function fakeResponse(body: unknown): Response {
    const text = JSON.stringify(body);
    return {
      ok: true,
      status: 200,
      statusText: "OK",
      text: async () => text,
    } as unknown as Response;
  }
  (globalThis as any).fetch = async (path: string, init?: RequestInit) => {
    const body = init?.body ? JSON.parse(String(init.body)) : {};
    lastRequest = { path, body };
    return fakeResponse({
      domain: body.domain ?? "RELATIONSHIP",
      key: body.key ?? "",
      value: body.value ?? "0",
      valueInt: typeof body.value === "string" && /^-?\d+$/.test(body.value) ? Number(body.value) : null,
      sourceKind: "runtime_state_edit",
      sourceRef: body.sourceRef ?? null,
      seq: 1,
    });
  };
  try {
    await checkAsync("17. RELATIONSHIP SET sends domain=RELATIONSHIP key=andrey.trust value=30", async () => {
      await httpClient.setRuntimeState("ws-1", "RELATIONSHIP", "andrey.trust", "30");
      return (
        lastRequest?.path === "/api/runtime-state/set" &&
        lastRequest.body.workspaceId === "ws-1" &&
        lastRequest.body.domain === "RELATIONSHIP" &&
        lastRequest.body.key === "andrey.trust" &&
        lastRequest.body.value === "30"
      );
    });
    await checkAsync(
      "17b. RELATIONSHIP ADJUST normalizes '+10' -> 10 and sends key=andrey.trust delta=10",
      async () => {
        const delta = parseDeltaInput("+10");
        if (delta === null) return false;
        await httpClient.adjustRuntimeState("ws-1", "RELATIONSHIP", "andrey.trust", delta);
        return (
          lastRequest?.path === "/api/runtime-state/adjust" &&
          lastRequest.body.domain === "RELATIONSHIP" &&
          lastRequest.body.key === "andrey.trust" &&
          lastRequest.body.delta === 10
        );
      }
    );
    await checkAsync("17c. RELATIONSHIP REMOVE sends key=andrey.trust", async () => {
      await httpClient.removeRuntimeState("ws-1", "RELATIONSHIP", "andrey.trust");
      return (
        lastRequest?.path === "/api/runtime-state/remove" &&
        lastRequest.body.domain === "RELATIONSHIP" &&
        lastRequest.body.key === "andrey.trust"
      );
    });
    await checkAsync("17d. PSYCHOLOGY SET sends domain=PSYCHOLOGY key=stress (canonical key is the dimension itself)", async () => {
      await httpClient.setRuntimeState("ws-1", "PSYCHOLOGY", "stress", "5");
      return (
        lastRequest?.path === "/api/runtime-state/set" &&
        lastRequest.body.domain === "PSYCHOLOGY" &&
        lastRequest.body.key === "stress"
      );
    });
    await checkAsync("17e. FACT SET is unaffected: sends domain=FACT key=current.test_status", async () => {
      await httpClient.setRuntimeState("ws-1", "FACT", "current.test_status", "react-state-smoke");
      return (
        lastRequest?.path === "/api/runtime-state/set" &&
        lastRequest.body.domain === "FACT" &&
        lastRequest.body.key === "current.test_status" &&
        lastRequest.body.value === "react-state-smoke"
      );
    });
  } finally {
    globalThis.fetch = originalFetch;
  }

  // --- Consolidated Memory operator UI (REACT_CONSOLIDATED_MEMORY_OPERATOR_UI_V1) ---

  // 18. Both concrete clients expose the operator-driven consolidated-memory
  //     surface; the UI (MemoryView) only ever calls through this interface.
  const memoryOps = [
    "listMemoryEvents",
    "listMemoryPromotionCandidates",
    "proposeMemoryPromotion",
    "decideMemoryPromotion",
    "listConsolidatedMemory",
    "createConsolidatedMemoryRelation",
  ] as const;
  check(
    "18. Mock + Http clients both expose all 6 consolidated-memory operations",
    memoryOps.every(
      (m) =>
        typeof (client as any)[m] === "function" &&
        typeof (httpClient as any)[m] === "function"
    )
  );

  // 18b. Mock end-to-end: backend-style eligibility gate, verbatim candidate,
  //      explicit APPROVE/REJECT, exact dedupe, no automatic promotion. (The
  //      Python backend stays authoritative in "local" mode; the mock only
  //      mirrors externally-visible behavior for offline UI development.)
  await checkAsync(
    "18b. mock: only eligible USER_STATED promotes; APPROVE creates a record; REJECT does not; exact dupe blocked",
    async () => {
      const mc = new MockCharacterClient();
      const wsId = (await mc.listWorkspaces())[0].workspaceId;
      const s = await mc.createSession("kira", "KIRA_BETA_V1_CURRENT", SessionPurpose.TESTING, wsId);
      await mc.sendMessage(s.sessionId, "Я терпеть не могу шумные вечеринки.");
      const evs = (await mc.listMemoryEvents(wsId)).events;
      const userEvt = evs.find((e) => e.eventType === "USER_MESSAGE")!;
      const charEvt = evs.find((e) => e.eventType === "CHARACTER_MESSAGE")!;
      if (!userEvt.eligibleForPromotion) return false;
      if (charEvt.eligibleForPromotion || !charEvt.ineligibilityReason) return false;
      // a character utterance can never be promoted
      let charRejected = false;
      try {
        await mc.proposeMemoryPromotion(wsId, charEvt.eventId, "SEMANTIC");
      } catch {
        charRejected = true;
      }
      if (!charRejected) return false;

      const cand = await mc.proposeMemoryPromotion(wsId, userEvt.eventId, "SEMANTIC");
      if (cand.decisionStatus !== "PENDING" || cand.epistemicKind !== "USER_REPORT") return false;
      if (cand.meaning !== "Я терпеть не могу шумные вечеринки.") return false; // verbatim
      if ((await mc.listConsolidatedMemory(wsId)).length !== 0) return false; // candidate != record
      const decided = await mc.decideMemoryPromotion(wsId, cand.candidateId, "APPROVE");
      if (decided.decisionStatus !== "APPROVED") return false;
      const recs1 = await mc.listConsolidatedMemory(wsId);
      if (recs1.length !== 1 || recs1[0].status !== "ACTIVE" || recs1[0].epistemicKind !== "USER_REPORT")
        return false;

      // exact (normalized) duplicate is blocked at APPROVE
      await mc.sendMessage(s.sessionId, "  Я  ТЕРПЕТЬ  не могу шумные вечеринки. ");
      const dupUserEvts = (await mc.listMemoryEvents(wsId)).events.filter(
        (e) => e.eventType === "USER_MESSAGE"
      );
      const dupEvt = dupUserEvts[dupUserEvts.length - 1];
      const dupCand = await mc.proposeMemoryPromotion(wsId, dupEvt.eventId, "SEMANTIC");
      let dupBlocked = false;
      try {
        await mc.decideMemoryPromotion(wsId, dupCand.candidateId, "APPROVE");
      } catch {
        dupBlocked = true;
      }
      if (!dupBlocked || (await mc.listConsolidatedMemory(wsId)).length !== 1) return false;

      // REJECT creates no record and is final
      await mc.sendMessage(s.sessionId, "Совсем другое утверждение.");
      const rejUserEvts = (await mc.listMemoryEvents(wsId)).events.filter(
        (e) => e.eventType === "USER_MESSAGE"
      );
      const rejEvt = rejUserEvts[rejUserEvts.length - 1];
      const rejCand = await mc.proposeMemoryPromotion(wsId, rejEvt.eventId, "EPISODIC");
      const rej = await mc.decideMemoryPromotion(wsId, rejCand.candidateId, "REJECT");
      if (rej.decisionStatus !== "REJECTED") return false;
      if ((await mc.listConsolidatedMemory(wsId)).length !== 1) return false;
      let secondDecisionBlocked = false;
      try {
        await mc.decideMemoryPromotion(wsId, rejCand.candidateId, "APPROVE");
      } catch {
        secondDecisionBlocked = true;
      }
      return secondDecisionBlocked;
    }
  );

  // 18c. Mock standalone relations mirror the accepted backend derivation.
  await checkAsync(
    "18c. mock: SUPERSEDES -> target derived SUPERSEDED; CONFLICTS_WITH -> both active + flagged; self/missing rejected",
    async () => {
      const mc = new MockCharacterClient();
      const wsId = (await mc.listWorkspaces())[0].workspaceId;
      const s = await mc.createSession("kira", "KIRA_BETA_V1_CURRENT", SessionPurpose.TESTING, wsId);
      async function approve(text: string): Promise<string> {
        await mc.sendMessage(s.sessionId, text);
        const userEvts = (await mc.listMemoryEvents(wsId)).events.filter(
          (e) => e.eventType === "USER_MESSAGE"
        );
        const evt = userEvts[userEvts.length - 1];
        const c = await mc.proposeMemoryPromotion(wsId, evt.eventId, "SEMANTIC");
        await mc.decideMemoryPromotion(wsId, c.candidateId, "APPROVE");
        const recs = await mc.listConsolidatedMemory(wsId);
        return recs[recs.length - 1].recordId;
      }
      const oldId = await approve("Я родился в Москве.");
      const newId = await approve("Нет, я родился в Туле.");
      await mc.createConsolidatedMemoryRelation(wsId, newId, oldId, "SUPERSEDES");
      let recs = await mc.listConsolidatedMemory(wsId);
      const oldRec = recs.find((r) => r.recordId === oldId)!;
      const newRec = recs.find((r) => r.recordId === newId)!;
      if (oldRec.status !== "SUPERSEDED" || oldRec.supersededByRecordId !== newId) return false;
      if (newRec.status !== "ACTIVE") return false;
      if (oldRec.meaning !== "Я родился в Москве.") return false; // never rewritten

      const aId = await approve("У меня есть кот.");
      const bId = await approve("У меня нет животных.");
      await mc.createConsolidatedMemoryRelation(wsId, aId, bId, "CONFLICTS_WITH");
      recs = await mc.listConsolidatedMemory(wsId);
      const aRec = recs.find((r) => r.recordId === aId)!;
      const bRec = recs.find((r) => r.recordId === bId)!;
      if (aRec.status !== "ACTIVE" || bRec.status !== "ACTIVE") return false;
      if (!aRec.conflictRecordIds.includes(bId) || !bRec.conflictRecordIds.includes(aId)) return false;

      let selfRejected = false;
      try {
        await mc.createConsolidatedMemoryRelation(wsId, aId, aId, "SUPERSEDES");
      } catch {
        selfRejected = true;
      }
      let missingRejected = false;
      try {
        await mc.createConsolidatedMemoryRelation(wsId, aId, "memrec-nope", "SUPERSEDES");
      } catch {
        missingRejected = true;
      }
      return selfRejected && missingRejected;
    }
  );

  // 18d. Consolidated memory is workspace-scoped: a fresh Clean Test never
  //      sees another workspace's approved records.
  await checkAsync("18d. mock: consolidated memory is isolated per workspace", async () => {
    const mc = new MockCharacterClient();
    const wsA = (await mc.listWorkspaces())[0].workspaceId;
    const s = await mc.createSession("kira", "KIRA_BETA_V1_CURRENT", SessionPurpose.TESTING, wsA);
    await mc.sendMessage(s.sessionId, "Факт только для рабочей области A.");
    const evt = (await mc.listMemoryEvents(wsA)).events.find((e) => e.eventType === "USER_MESSAGE")!;
    const c = await mc.proposeMemoryPromotion(wsA, evt.eventId, "SEMANTIC");
    await mc.decideMemoryPromotion(wsA, c.candidateId, "APPROVE");
    if ((await mc.listConsolidatedMemory(wsA)).length !== 1) return false;
    const wsB = await mc.createTestWorkspace();
    return (await mc.listConsolidatedMemory(wsB.workspaceId)).length === 0;
  });

  // 18e. HttpCharacterClient routes every consolidated-memory call to a
  //      relative /api/... path with the expected method + JSON body.
  const originalFetch2 = globalThis.fetch;
  interface SeenReq { path: string; method: string; body: Record<string, unknown> }
  const reqLog: SeenReq[] = [];
  (globalThis as any).fetch = async (path: string, init?: RequestInit) => {
    reqLog.push({
      path,
      method: (init?.method ?? "GET").toUpperCase(),
      body: init?.body ? JSON.parse(String(init.body)) : {},
    });
    return {
      ok: true,
      status: 200,
      statusText: "OK",
      text: async () =>
        JSON.stringify({ events: [], candidates: [], records: [], workspaceId: "w", causalOrder: "seq" }),
    } as unknown as Response;
  };
  try {
    await checkAsync("18e. HttpCharacterClient consolidated-memory calls use relative /api/... routes", async () => {
      reqLog.length = 0;
      await httpClient.listMemoryEvents("ws-1");
      await httpClient.listMemoryPromotionCandidates("ws-1");
      await httpClient.listConsolidatedMemory("ws-1");
      await httpClient.proposeMemoryPromotion("ws-1", "evt-1", "SEMANTIC");
      await httpClient.decideMemoryPromotion("ws-1", "cand-1", "APPROVE");
      await httpClient.createConsolidatedMemoryRelation("ws-1", "rec-a", "rec-b", "SUPERSEDES");
      const [ev, ca, co, pr, de, re] = reqLog;
      return (
        ev.path === "/api/workspaces/ws-1/memory/events" && ev.method === "GET" &&
        ca.path === "/api/workspaces/ws-1/memory/candidates" && ca.method === "GET" &&
        co.path === "/api/workspaces/ws-1/memory/consolidated" && co.method === "GET" &&
        pr.path === "/api/memory/candidates" && pr.method === "POST" &&
        pr.body.workspaceId === "ws-1" && pr.body.sourceEventId === "evt-1" &&
        pr.body.memoryKind === "SEMANTIC" &&
        de.path === "/api/memory/candidates/decision" && de.method === "POST" &&
        de.body.candidateId === "cand-1" && de.body.decision === "APPROVE" &&
        re.path === "/api/memory/relations" && re.method === "POST" &&
        re.body.fromRecordId === "rec-a" && re.body.toRecordId === "rec-b" &&
        re.body.relationType === "SUPERSEDES"
      );
    });
  } finally {
    globalThis.fetch = originalFetch2;
  }

  console.log(`\n${passed} passed, ${failed} failed`);
  if (failed > 0) {
    throw new Error(`${failed} structural check(s) failed`);
  }
}

void main();
