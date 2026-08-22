import { test, describe } from "node:test";
import assert from "node:assert/strict";
import { assertTransition, LifecycleViolation, FactoryLifecycle } from "./lifecycle.ts";
import type { PortClient } from "./client.ts";
import type { CandidateState, EvaluationOutput } from "./types.ts";

describe("assertTransition", () => {
  test("allows the normal happy path", () => {
    const path: CandidateState[] = [
      "DETECTED",
      "INVESTIGATING",
      "PLANNED",
      "IMPLEMENTED",
      "EVALUATING",
      "READY_FOR_APPROVAL",
      "APPROVED",
      "RELEASED",
    ];
    for (let i = 0; i < path.length - 1; i++) {
      assert.doesNotThrow(() => assertTransition(path[i], path[i + 1]));
    }
  });

  test("refuses to skip evaluation on the way to approval", () => {
    assert.throws(() => assertTransition("IMPLEMENTED", "READY_FOR_APPROVAL"), LifecycleViolation);
  });

  test("refuses to jump straight to RELEASED", () => {
    assert.throws(() => assertTransition("READY_FOR_APPROVAL", "RELEASED"), LifecycleViolation);
  });

  test("RELEASED is terminal", () => {
    assert.throws(() => assertTransition("RELEASED", "INVESTIGATING"), LifecycleViolation);
  });

  test("a rejected candidate can be reworked", () => {
    assert.doesNotThrow(() => assertTransition("REJECTED", "INVESTIGATING"));
  });
});

// Minimal fake so the guards can be tested without a live Port workspace.
function fakePort(state: CandidateState) {
  const calls: Array<{ blueprint: string; entity: unknown }> = [];
  const client = {
    async getEntity() {
      return { entity: { properties: { status: state } } };
    },
    async upsertEntity(blueprint: string, entity: unknown) {
      calls.push({ blueprint, entity });
      return {};
    },
  } as unknown as PortClient;
  return { client, calls };
}

describe("human approval gate", () => {
  test("rejects approval with no approver named", async () => {
    const { client } = fakePort("READY_FOR_APPROVAL");
    const lifecycle = new FactoryLifecycle(client);
    await assert.rejects(() => lifecycle.approve("CANDIDATE-1", "  "), LifecycleViolation);
  });

  test("rejects approval of a candidate that has not passed evaluation", async () => {
    const { client } = fakePort("IMPLEMENTED");
    const lifecycle = new FactoryLifecycle(client);
    await assert.rejects(() => lifecycle.approve("CANDIDATE-1", "kenil"), LifecycleViolation);
  });

  test("allows approval once objectively passed", async () => {
    const { client } = fakePort("READY_FOR_APPROVAL");
    const lifecycle = new FactoryLifecycle(client);
    const result = await lifecycle.approve("CANDIDATE-1", "kenil");
    assert.equal(result.approvedBy, "kenil");
  });

  test("refuses to release without human approval", async () => {
    const { client } = fakePort("READY_FOR_APPROVAL");
    const lifecycle = new FactoryLifecycle(client);
    await assert.rejects(
      () => lifecycle.release("CANDIDATE-1", "v1-optimized", "kenil", 92),
      LifecycleViolation
    );
  });
});

describe("recordEvaluation routes on the evaluator's decision", () => {
  const base: EvaluationOutput = {
    factory_run_id: "RUN-001",
    candidate_id: "CANDIDATE-1",
    scenario: "baseline-v1",
    score: 70,
    decision: "FAIL",
    correctness_status: "PASS",
    tests_passed: 8,
    tests_failed: 0,
    p50_latency_ms: 2680,
    p95_latency_ms: 2750,
    error_rate: 0,
    failed_provider: null,
    failure_reason: "p95 latency exceeded 2.2s",
    representative_trace_id: "abc123",
    evaluation_window_start: "2026-08-22T20:00:00.000Z",
    evaluation_window_end: "2026-08-22T20:05:00.000Z",
    observability_complete: true,
  };

  test("a FAIL sends the candidate to REJECTED", async () => {
    const { client } = fakePort("EVALUATING");
    const lifecycle = new FactoryLifecycle(client);
    const result = await lifecycle.recordEvaluation(base);
    assert.equal(result.movedTo, "REJECTED");
  });

  test("a PASS sends the candidate to READY_FOR_APPROVAL, not APPROVED", async () => {
    const { client } = fakePort("EVALUATING");
    const lifecycle = new FactoryLifecycle(client);
    const result = await lifecycle.recordEvaluation({ ...base, decision: "PASS", score: 92 });
    // Critical: passing the fitness gate makes a candidate eligible for a human to
    // approve. It must never approve itself.
    assert.equal(result.movedTo, "READY_FOR_APPROVAL");
  });
});
