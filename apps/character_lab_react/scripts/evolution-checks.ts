import { HttpCharacterClient, HttpTransportError } from "../src/client/httpCharacterClient.js";
import { MockCharacterClient } from "../src/mocks/mockCharacterClient.js";
import { NotIntegratedInTransportError } from "../src/client/types.js";

function assert(value: unknown, message: string): asserts value {
  if (!value) throw new Error(message);
}

async function main() {
  const original = globalThis.fetch;
  const calls: {path: string; body: any; method: string}[] = [];
  globalThis.fetch = async (input, init) => {
    calls.push({path: String(input), body: init?.body ? JSON.parse(String(init.body)) : null, method: init?.method ?? "GET"});
    return new Response(JSON.stringify(init?.method === "POST" ? {candidate_id: "c1"} : {candidates: [{candidate_id: "c1", status: "PENDING"}]}));
  };
  try {
    const client = new HttpCharacterClient();
    const rows = await client.listEvolutionCandidates("workspace / one");
    assert(rows[0].status === "PENDING", "list must preserve authoritative status");
    await client.createEvolutionCandidate("ws-a", {domain: "PSYCHOLOGY", key: "stress", operation: "ADJUST", proposedDelta: -10, reason: "review", basisEventIds: ["event-1"], confidence: 0.7, timescale: "SLOW"});
    for (const decision of ["APPROVE", "REJECT"] as const) {
      await client.decideEvolutionCandidate("ws-a", "c1", decision, "operator-1", "verified");
    }
    assert(calls[0].path === "/api/workspaces/workspace%20%2F%20one/evolution/candidates" && calls[0].method === "GET", "workspace encoding");
    assert(calls[1].path === "/api/evolution/candidates" && calls[1].body.proposedDelta === -10 && !('proposedValue' in calls[1].body), "proposal delta payload");
    assert(calls[1].body.workspaceId === "ws-a" && calls[1].body.basisEventIds[0] === "event-1", "proposal scope and basis");
    for (const [index, decision] of [[2, "APPROVE"], [3, "REJECT"]] as const) {
      const call = calls[index];
      assert(call.path === "/api/evolution/candidates/decision" && call.method === "POST", "decision endpoint");
      assert(call.body.decision === decision && call.body.decidedBy === "operator-1" && call.body.reason === "verified" && call.body.workspaceId === "ws-a" && call.body.candidateId === "c1", "explicit decision attribution and scope");
    }
    for (const status of [400, 404, 409]) {
      globalThis.fetch = async () => new Response(JSON.stringify({error: {code: "evolution_conflict", message: "already decided"}}), {status});
      try { await client.decideEvolutionCandidate("ws-a", "c1", "APPROVE", "operator-1"); throw new Error("expected rejection"); }
      catch (err) { assert(err instanceof HttpTransportError && err.status === status, "HTTP failures must propagate"); }
    }
    try { await new MockCharacterClient().listEvolutionCandidates("ws-a"); throw new Error("expected unavailable mock"); }
    catch (err) { assert(err instanceof NotIntegratedInTransportError, "mock must not invent durable candidates"); }
    console.log("Evolution client: payload, scope, approval/rejection, HTTP errors and mock checks passed");
  } finally {
    globalThis.fetch = original;
  }
}
void main();
