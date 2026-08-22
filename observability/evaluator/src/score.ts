import type { EvaluationInput, EvaluationOutput, ScoreBreakdown, TelemetryEvidence } from "./types.js";

const REQUIRED_SPANS = [
  "api_guardian.product_snapshot",
  "provider.catalog",
  "provider.pricing",
  "provider.availability",
];

function percentile(values: number[], p: number): number {
  if (values.length === 0) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const index = Math.ceil((p / 100) * sorted.length) - 1;
  return sorted[Math.max(0, index)] ?? 0;
}

export function scoreCorrectness(input: EvaluationInput): { points: number; passed: boolean } {
  const { tests } = input;
  let points = 0;

  if (tests.schema_valid) points += 20;
  if (tests.failed === 0 && tests.passed === tests.total) points += 10;
  if (tests.provider_truth_match) points += 10;

  const passed = tests.schema_valid && tests.failed === 0 && tests.provider_truth_match;
  return { points, passed };
}

export function scoreReliability(evidence: TelemetryEvidence): { points: number; passed: boolean } {
  let points = 0;
  const errorRateOk = evidence.error_rate < 0.01;
  const noAdapterExceptions = evidence.adapter_exceptions === 0;

  if (errorRateOk) points += 10;
  if (noAdapterExceptions) points += 10;

  return { points, passed: errorRateOk && noAdapterExceptions };
}

export function scoreLatency(p95Ms: number): number {
  if (p95Ms <= 1600) return 20;
  if (p95Ms <= 2200) return 10;
  return 0;
}

export function scoreDocsHealth(
  docsHealth: EvaluationInput["docs_health"]
): { points: number; note?: string } {
  if (!docsHealth) {
    return { points: 0, note: "not_supplied" };
  }
  let points = 0;
  if (docsHealth.fields_present) points += 5;
  if (docsHealth.schema_valid) points += 5;
  return { points };
}

export function scoreObservability(evidence: TelemetryEvidence): number {
  let points = 0;
  if (evidence.spans_present) points += 5;
  if (evidence.correlation_present) points += 5;
  return points;
}

export function buildFailureReason(
  input: EvaluationInput,
  breakdown: ScoreBreakdown,
  evidence: TelemetryEvidence,
  correctnessPassed: boolean,
  reliabilityPassed: boolean,
  totalScore: number
): string | null {
  if (correctnessPassed && reliabilityPassed && totalScore >= 90) {
    return null;
  }

  if (!correctnessPassed) {
    if (!input.tests.schema_valid) {
      return "Product Snapshot normalized schema validation failed.";
    }
    if (input.tests.failed > 0) {
      return `Integration test suite failed: ${input.tests.failed}/${input.tests.total} tests failed.`;
    }
    if (!input.tests.provider_truth_match) {
      return "Provider truth comparison failed; normalized snapshot does not match provider responses.";
    }
  }

  if (!reliabilityPassed) {
    if (evidence.failed_provider) {
      return `Product Snapshot reliability failed. Errors are concentrated in provider.${evidence.failed_provider}. Representative trace shows adapter/schema failure after provider version changed.`;
    }
    return `Product Snapshot reliability failed. Error rate ${(evidence.error_rate * 100).toFixed(1)}% exceeds 1% threshold.`;
  }

  if (breakdown.latency === 0) {
    return "Product Snapshot correctness passed, but p95 latency exceeded 2.2s. Provider spans were healthy and individually stable; trace waterfall shows independent provider calls serialized.";
  }

  if (totalScore < 90) {
    return `Candidate score ${totalScore} is below release threshold of 90.`;
  }

  return "Candidate failed one or more objective gates.";
}

export function evaluateTelemetryError(input: EvaluationInput, reason: string): EvaluationOutput {
  return {
    factory_run_id: input.factory_run_id,
    candidate_id: input.candidate_id,
    scenario: input.scenario,
    release_version: input.release_version,
    score: 0,
    decision: "ERROR",
    correctness_status: "FAIL",
    tests_passed: input.tests.passed,
    tests_failed: input.tests.failed,
    p50_latency_ms: 0,
    p95_latency_ms: 0,
    error_rate: 0,
    failed_provider: null,
    failure_reason: reason,
    representative_trace_id: null,
    evaluation_window_start: input.evaluation_window_start,
    evaluation_window_end: input.evaluation_window_end,
    observability_complete: false,
    score_breakdown: {
      correctness: 0,
      reliability: 0,
      latency: 0,
      docs_health: 0,
      observability: 0,
      docs_health_note: "telemetry_unavailable",
    },
  };
}

export function evaluateCandidate(
  input: EvaluationInput,
  evidence: TelemetryEvidence
): EvaluationOutput {
  const correctness = scoreCorrectness(input);
  const reliability = scoreReliability(evidence);
  const latencyPoints = scoreLatency(evidence.p95_latency_ms);
  const docs = scoreDocsHealth(input.docs_health);
  const observabilityPoints = scoreObservability(evidence);

  const breakdown: ScoreBreakdown = {
    correctness: correctness.points,
    reliability: reliability.points,
    latency: latencyPoints,
    docs_health: docs.points,
    observability: observabilityPoints,
    ...(docs.note ? { docs_health_note: docs.note } : {}),
  };

  const totalScore =
    breakdown.correctness +
    breakdown.reliability +
    breakdown.latency +
    breakdown.docs_health +
    breakdown.observability;

  const decision =
    correctness.passed && reliability.passed && totalScore >= 90 ? "PASS" : "FAIL";

  const failureReason = buildFailureReason(
    input,
    breakdown,
    evidence,
    correctness.passed,
    reliability.passed,
    totalScore
  );

  return {
    factory_run_id: input.factory_run_id,
    candidate_id: input.candidate_id,
    scenario: input.scenario,
    release_version: input.release_version,
    score: totalScore,
    decision,
    correctness_status: correctness.passed ? "PASS" : "FAIL",
    tests_passed: input.tests.passed,
    tests_failed: input.tests.failed,
    p50_latency_ms: Math.round(evidence.p50_latency_ms),
    p95_latency_ms: Math.round(evidence.p95_latency_ms),
    error_rate: evidence.error_rate,
    failed_provider: evidence.failed_provider,
    failure_reason: failureReason,
    representative_trace_id: evidence.representative_trace_id,
    evaluation_window_start: input.evaluation_window_start,
    evaluation_window_end: input.evaluation_window_end,
    observability_complete: evidence.observability_complete,
    score_breakdown: breakdown,
  };
}

export function spansPresentInTrace(spanNames: Set<string>): boolean {
  return REQUIRED_SPANS.every((name) => spanNames.has(name));
}
