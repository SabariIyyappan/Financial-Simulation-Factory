export type EvaluationInput = {
  factory_run_id: string;
  candidate_id: string;
  scenario: string;
  release_version?: string;
  evaluation_window_start: string;
  evaluation_window_end: string;
  tests: {
    total: number;
    passed: number;
    failed: number;
    schema_valid: boolean;
    provider_truth_match: boolean;
  };
  docs_health?: {
    fields_present: boolean;
    schema_valid: boolean;
  } | null;
};

export type ScoreBreakdown = {
  correctness: number;
  reliability: number;
  latency: number;
  docs_health: number;
  observability: number;
  docs_health_note?: string;
};

export type EvaluationOutput = {
  factory_run_id: string;
  candidate_id: string;
  scenario: string;
  release_version?: string;
  score: number;
  decision: "PASS" | "FAIL";
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
  score_breakdown: ScoreBreakdown;
};

export type TelemetryEvidence = {
  p50_latency_ms: number;
  p95_latency_ms: number;
  error_rate: number;
  failed_provider: string | null;
  representative_trace_id: string | null;
  observability_complete: boolean;
  provider_errors: Record<string, number>;
  adapter_exceptions: number;
  spans_present: boolean;
  correlation_present: boolean;
};
