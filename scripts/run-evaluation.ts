#!/usr/bin/env tsx
// Produces the evaluation artifact Person B's fitness calculator consumes.
// This is Contract C in docs/plan/MASTER_PLAN.md section 7 — Person A owns producing it,
// Person B owns combining it with SigNoz telemetry into the candidate score.
//
//   tsx scripts/run-evaluation.ts --run RUN-001 --candidate BASELINE --scenario baseline-v1
//
// Deliberately does NOT assert on latency — latency is proven from SigNoz telemetry by
// Person B, never from wall-clock assertions here (CLAUDE.md rule 6).

import { spawnSync } from "node:child_process";
import { writeFileSync, globSync } from "node:fs";

interface Args {
  run: string;
  candidate: string;
  scenario: string;
  releaseVersion: string;
  productId: string;
  requests: number;
  appUrl: string;
  out: string;
}

function parseArgs(): Args {
  const argv = process.argv.slice(2);
  const get = (flag: string, fallback: string) => {
    const i = argv.indexOf(`--${flag}`);
    return i >= 0 && argv[i + 1] ? argv[i + 1] : fallback;
  };
  return {
    run: get("run", "RUN-LOCAL"),
    candidate: get("candidate", "CANDIDATE-LOCAL"),
    scenario: get("scenario", "baseline-v1"),
    releaseVersion: get("release", "v0-baseline"),
    productId: get("product", "sku-123"),
    requests: Number(get("requests", "5")),
    appUrl: get("app-url", process.env.APP_URL ?? "http://localhost:3000"),
    out: get("out", "evaluation-input.json"),
  };
}

const args = parseArgs();
const evaluationWindowStart = new Date().toISOString();

// --- 1. Deterministic test suite ---
console.log("running test suite...");
// Spawn node directly rather than going through `npm test` — Node refuses to exec .cmd
// shims without a shell on Windows, which silently yields an empty result instead of a
// test report.
const testFiles = globSync("packages/*/src/**/*.test.ts");
if (testFiles.length === 0) {
  console.error("WARNING: no test files matched — the correctness gate has nothing to verify.");
}
const testRun = spawnSync(process.execPath, ["--import", "tsx", "--test", ...testFiles], {
  encoding: "utf-8",
});
const testOutput = `${testRun.stdout ?? ""}${testRun.stderr ?? ""}`;

// node:test reports counts as "# pass N" (TAP) or "ℹ pass N" (spec reporter) depending on
// the runner. Sum across blocks, since each spawned batch prints its own summary.
function sumCounts(label: "pass" | "fail"): number | null {
  const matches = [...testOutput.matchAll(new RegExp(`^[#ℹ]\\s*${label} (\\d+)$`, "gm"))];
  if (matches.length === 0) return null;
  return matches.reduce((total, m) => total + Number(m[1]), 0);
}

const parsedPassed = sumCounts("pass");
const parsedFailed = sumCounts("fail");

if (parsedPassed === null) {
  console.error(
    "WARNING: could not parse test counts from runner output — reporting suite as failed rather than reporting a false zero."
  );
}

// A suite whose results we cannot read is not a passing suite. Never let an unparsed
// run masquerade as "0 failures" — Person B's correctness gate depends on this number.
const testsPassed = parsedPassed ?? 0;
const testsFailed = parsedFailed ?? (testRun.status === 0 && parsedPassed !== null ? 0 : 1);

// --- 2. Exercise the live endpoint to generate telemetry + check provider truth ---
console.log(`issuing ${args.requests} snapshot requests against ${args.appUrl}...`);
let schemaValid = true;
let providerTruthMatch = true;
let lastFailure: unknown = null;
let succeeded = 0;

for (let i = 0; i < args.requests; i++) {
  const url = `${args.appUrl}/api/snapshot?productId=${args.productId}&factoryRunId=${args.run}&candidateId=${args.candidate}&scenario=${args.scenario}&releaseVersion=${args.releaseVersion}`;
  try {
    const res = await fetch(url);
    const body = await res.json();
    if (!body.ok) {
      schemaValid = false;
      lastFailure = body.failure;
      continue;
    }
    succeeded++;
    // Provider truth: the snapshot's price must match the fixture the mock serves,
    // regardless of which schema version the provider used to express it.
    const s = body.snapshot;
    if (args.productId === "sku-123" && s.price?.amount !== 129.99) {
      providerTruthMatch = false;
    }
  } catch (err) {
    schemaValid = false;
    lastFailure = String(err);
  }
}

const evaluationWindowEnd = new Date().toISOString();

// Shape is frozen by Contract C — matches observability/contracts/evaluation-input.example.json.
// Person B's evaluator reads this directly, so field names and nesting are not ours to
// change unilaterally.
const artifact = {
  factory_run_id: args.run,
  candidate_id: args.candidate,
  scenario: args.scenario,
  release_version: args.releaseVersion,
  evaluation_window_start: evaluationWindowStart,
  evaluation_window_end: evaluationWindowEnd,
  tests: {
    total: testsPassed + testsFailed,
    passed: testsPassed,
    failed: testsFailed,
    schema_valid: schemaValid,
    provider_truth_match: providerTruthMatch,
  },
  // Person C supplies this when Bright Data docs evidence is part of the run; the
  // evaluator scores 0/10 for docs health and notes "not_supplied" when it stays null.
  docs_health: null,
};

writeFileSync(args.out, JSON.stringify(artifact, null, 2));
console.log(`\nwrote ${args.out}`);
console.log(JSON.stringify(artifact, null, 2));

// Not part of the contract — printed only so a human running this can see why
// schema_valid flipped without digging through the app logs.
if (!schemaValid) {
  console.log(`\nlocal diagnostic (not sent to evaluator):`);
  console.log(`  requests succeeded: ${succeeded}/${args.requests}`);
  console.log(`  last failure: ${JSON.stringify(lastFailure)}`);
}

console.log(`\nPOST this to Person B's evaluator: ${process.env.EVALUATOR_URL ?? "http://localhost:8090/evaluate"}`);
