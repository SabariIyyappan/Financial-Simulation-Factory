// Mirrors port/blueprints/*.json. If you change a blueprint, change this too.

export const CANDIDATE_STATES = [
  "DETECTED",
  "INVESTIGATING",
  "PLANNED",
  "IMPLEMENTED",
  "EVALUATING",
  "REJECTED",
  "READY_FOR_APPROVAL",
  "APPROVED",
  "RELEASED",
] as const;

export type CandidateState = (typeof CANDIDATE_STATES)[number];

export type Decision = "PASS" | "FAIL";

export type Scenario =
  | "baseline-v1"
  | "optimized-v1"
  | "pricing-v2-break"
  | "pricing-v2-repaired";

export interface FactoryRunInput {
  runId: string;
  serviceId: string;
  scenario: Scenario;
  triggerReason: "manual" | "latency_regression" | "provider_schema_break" | "signoz_alert";
  status: "running" | "awaiting_approval" | "released" | "failed";
  startedAt: string;
  finishedAt?: string;
  incidentReason?: string;
  retryCount?: number;
}

export interface CandidateInput {
  candidateId: string;
  runId: string;
  parentCandidateId?: string;
  hypothesis?: string;
  commitRef?: string;
  status: CandidateState;
  score?: number;
  decision?: Decision | "PENDING";
}

// Matches Person B's evaluation-output contract (Contract D) field-for-field, so an
// evaluator response can be handed straight to recordEvaluation.
export interface EvaluationOutput {
  factory_run_id: string;
  candidate_id: string;
  scenario: string;
  release_version?: string;
  score: number;
  decision: Decision;
  correctness_status: "PASS" | "FAIL";
  tests_passed: number;
  tests_failed: number;
  p50_latency_ms: number;
  p95_latency_ms: number;
  error_rate: number;
  failed_provider: string | null;
  failure_reason: string | null;
  representative_trace_id: string | null;
  evaluation_window_start: string;
  evaluation_window_end: string;
  observability_complete: boolean;
}
