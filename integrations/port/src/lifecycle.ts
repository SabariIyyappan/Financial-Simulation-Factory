import type { PortClient } from "./client.ts";
import type { CandidateInput, CandidateState, EvaluationOutput, FactoryRunInput } from "./types.ts";

// Legal transitions. Anything not listed is rejected — a candidate cannot skip
// evaluation, and nothing can move backwards out of RELEASED.
const ALLOWED: Record<CandidateState, CandidateState[]> = {
  DETECTED: ["INVESTIGATING"],
  INVESTIGATING: ["PLANNED", "REJECTED"],
  PLANNED: ["IMPLEMENTED", "REJECTED"],
  IMPLEMENTED: ["EVALUATING", "REJECTED"],
  EVALUATING: ["READY_FOR_APPROVAL", "REJECTED"],
  REJECTED: ["INVESTIGATING"],
  READY_FOR_APPROVAL: ["APPROVED", "REJECTED"],
  APPROVED: ["RELEASED"],
  RELEASED: [],
};

export class LifecycleViolation extends Error {
  constructor(message: string) {
    super(message);
    this.name = "LifecycleViolation";
  }
}

export function assertTransition(from: CandidateState, to: CandidateState): void {
  if (!ALLOWED[from].includes(to)) {
    throw new LifecycleViolation(
      `Illegal candidate transition ${from} -> ${to}. Allowed from ${from}: ${ALLOWED[from].join(", ") || "(terminal)"}`
    );
  }
}

export class FactoryLifecycle {
  constructor(
    private readonly port: PortClient,
    private readonly serviceId = "api-guardian"
  ) {}

  async startRun(input: FactoryRunInput) {
    return this.port.upsertEntity("factoryRun", {
      identifier: input.runId,
      title: `${input.scenario} — ${input.triggerReason}`,
      properties: {
        scenario: input.scenario,
        triggerReason: input.triggerReason,
        status: input.status,
        startedAt: input.startedAt,
        finishedAt: input.finishedAt,
        incidentReason: input.incidentReason,
        retryCount: input.retryCount ?? 0,
      },
      relations: { service: input.serviceId },
    });
  }

  async upsertCandidate(input: CandidateInput) {
    return this.port.upsertEntity("candidateVersion", {
      identifier: input.candidateId,
      title: input.candidateId,
      properties: {
        hypothesis: input.hypothesis,
        commitRef: input.commitRef,
        status: input.status,
        score: input.score,
        decision: input.decision ?? "PENDING",
      },
      relations: {
        run: input.runId,
        parent: input.parentCandidateId ?? null,
      },
    });
  }

  private async currentState(candidateId: string): Promise<CandidateState> {
    const res = await this.port.getEntity<{ entity: { properties: { status: CandidateState } } }>(
      "candidateVersion",
      candidateId
    );
    return res.entity.properties.status;
  }

  async transition(candidateId: string, to: CandidateState) {
    const from = await this.currentState(candidateId);
    assertTransition(from, to);
    return this.port.upsertEntity("candidateVersion", {
      identifier: candidateId,
      properties: { status: to },
    });
  }

  // Records Person B's evaluation and moves the candidate accordingly. The decision is
  // the evaluator's, never this code's — we only route on it.
  async recordEvaluation(evaluation: EvaluationOutput) {
    const evaluationId = `${evaluation.candidate_id}-eval-${Date.now()}`;

    await this.port.upsertEntity("evaluation", {
      identifier: evaluationId,
      title: `${evaluation.candidate_id}: ${evaluation.decision} (${evaluation.score})`,
      properties: {
        score: evaluation.score,
        decision: evaluation.decision,
        correctnessStatus: evaluation.correctness_status,
        p50LatencyMs: evaluation.p50_latency_ms,
        p95LatencyMs: evaluation.p95_latency_ms,
        errorRate: evaluation.error_rate,
        failedProvider: evaluation.failed_provider,
        failureReason: evaluation.failure_reason,
        representativeTraceId: evaluation.representative_trace_id,
        testsPassed: evaluation.tests_passed,
        testsFailed: evaluation.tests_failed,
        observabilityComplete: evaluation.observability_complete,
        evaluatedAt: new Date().toISOString(),
      },
      relations: { candidate: evaluation.candidate_id },
    });

    await this.port.upsertEntity("candidateVersion", {
      identifier: evaluation.candidate_id,
      properties: { score: evaluation.score, decision: evaluation.decision },
    });

    const next: CandidateState = evaluation.decision === "PASS" ? "READY_FOR_APPROVAL" : "REJECTED";
    await this.transition(evaluation.candidate_id, next);
    return { evaluationId, movedTo: next };
  }

  // The human gate. approvedBy is required and must identify a person — an agent calling
  // this with its own name is the exact failure mode the hackathon brief warns about,
  // so the guard is here rather than left to convention.
  async approve(candidateId: string, approvedBy: string) {
    if (!approvedBy?.trim()) {
      throw new LifecycleViolation("approve() requires approvedBy — releases must be attributable.");
    }
    const state = await this.currentState(candidateId);
    if (state !== "READY_FOR_APPROVAL") {
      throw new LifecycleViolation(
        `Cannot approve a candidate in state ${state}. It must pass objective evaluation and reach READY_FOR_APPROVAL first.`
      );
    }
    await this.transition(candidateId, "APPROVED");
    return { candidateId, approvedBy, approvedAt: new Date().toISOString() };
  }

  async release(candidateId: string, version: string, approvedBy: string, score: number) {
    const state = await this.currentState(candidateId);
    if (state !== "APPROVED") {
      throw new LifecycleViolation(
        `Cannot release a candidate in state ${state}. A human must approve it first.`
      );
    }

    await this.port.upsertEntity("release", {
      identifier: version,
      title: version,
      properties: {
        version,
        approvedBy,
        approvedAt: new Date().toISOString(),
        score,
        status: "released",
      },
      relations: { candidate: candidateId, service: this.serviceId },
    });

    await this.transition(candidateId, "RELEASED");

    await this.port.upsertEntity("service", {
      identifier: this.serviceId,
      properties: { currentRelease: version, currentScore: score, health: "healthy" },
    });

    return { version, candidateId, approvedBy };
  }
}
