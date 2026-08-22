import express from "express";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { evaluateCandidate } from "./score.js";
import { SigNozClient } from "./signoz-client.js";
import type { EvaluationInput, EvaluationOutput } from "./types.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const client = new SigNozClient();

const evaluatedKeys = new Set<string>();

function cacheKey(input: EvaluationInput): string {
  return `${input.factory_run_id}:${input.candidate_id}:${input.evaluation_window_start}`;
}

async function runEvaluation(input: EvaluationInput): Promise<EvaluationOutput> {
  const evidence = await client.collectEvidence(input);
  return evaluateCandidate(input, evidence);
}

export function createApp(): express.Express {
  const app = express();
  app.use(express.json());

  app.get("/health", (_req, res) => {
    res.json({ status: "ok", service: "api-guardian-evaluator" });
  });

  app.get("/contracts/evaluation-input", (_req, res) => {
    const path = join(__dirname, "../../contracts/evaluation-input.example.json");
    res.type("json").send(readFileSync(path, "utf8"));
  });

  app.get("/contracts/evaluation-output", (_req, res) => {
    const path = join(__dirname, "../../contracts/evaluation-output.example.json");
    res.type("json").send(readFileSync(path, "utf8"));
  });

  app.post("/evaluate", async (req, res) => {
    try {
      const input = req.body as EvaluationInput;
      const key = cacheKey(input);

      if (evaluatedKeys.has(key)) {
        res.setHeader("X-Evaluation-Idempotent", "true");
      } else {
        evaluatedKeys.add(key);
      }

      const output = await runEvaluation(input);
      res.json(output);
    } catch (error) {
      res.status(500).json({
        error: error instanceof Error ? error.message : "Evaluation failed",
      });
    }
  });

  app.post("/evaluate/scenarios", async (_req, res) => {
    const now = Date.now();
    const windowStart = new Date(now - 15 * 60 * 1000).toISOString();
    const windowEnd = new Date(now + 60_000).toISOString();

    const scenarios: Array<{
      name: string;
      input: EvaluationInput;
      expected_decision: "PASS" | "FAIL";
    }> = [
      {
        name: "baseline-v1",
        expected_decision: "FAIL",
        input: {
          factory_run_id: "RUN-001",
          candidate_id: "BASELINE",
          scenario: "baseline-v1",
          release_version: "v0-baseline",
          evaluation_window_start: windowStart,
          evaluation_window_end: windowEnd,
          tests: {
            total: 12,
            passed: 12,
            failed: 0,
            schema_valid: true,
            provider_truth_match: true,
          },
        },
      },
      {
        name: "optimized-v1",
        expected_decision: "PASS",
        input: {
          factory_run_id: "RUN-002",
          candidate_id: "CANDIDATE-PARALLEL",
          scenario: "optimized-v1",
          release_version: "v1-optimized",
          evaluation_window_start: windowStart,
          evaluation_window_end: windowEnd,
          tests: {
            total: 12,
            passed: 12,
            failed: 0,
            schema_valid: true,
            provider_truth_match: true,
          },
          docs_health: { fields_present: true, schema_valid: true },
        },
      },
      {
        name: "pricing-v2-break",
        expected_decision: "FAIL",
        input: {
          factory_run_id: "RUN-003",
          candidate_id: "BASELINE",
          scenario: "pricing-v2-break",
          release_version: "v1-optimized",
          evaluation_window_start: windowStart,
          evaluation_window_end: windowEnd,
          tests: {
            total: 12,
            passed: 4,
            failed: 8,
            schema_valid: false,
            provider_truth_match: false,
          },
        },
      },
      {
        name: "pricing-v2-repaired",
        expected_decision: "PASS",
        input: {
          factory_run_id: "RUN-004",
          candidate_id: "CANDIDATE-PRICING-V2",
          scenario: "pricing-v2-repaired",
          release_version: "v2-pricing-compatible",
          evaluation_window_start: windowStart,
          evaluation_window_end: windowEnd,
          tests: {
            total: 12,
            passed: 12,
            failed: 0,
            schema_valid: true,
            provider_truth_match: true,
          },
          docs_health: { fields_present: true, schema_valid: true },
        },
      },
    ];

    const results = [];
    for (const scenario of scenarios) {
      const output = await runEvaluation(scenario.input);
      results.push({
        scenario: scenario.name,
        expected_decision: scenario.expected_decision,
        actual_decision: output.decision,
        match: output.decision === scenario.expected_decision,
        score: output.score,
        p95_latency_ms: output.p95_latency_ms,
        failure_reason: output.failure_reason,
      });
    }

    res.json({
      all_match: results.every((r) => r.match),
      results,
    });
  });

  return app;
}

export function startServer(port = Number(process.env.EVALUATOR_PORT ?? 8090)): void {
  const app = createApp();
  app.listen(port, () => {
    console.log(`Evaluator listening on http://localhost:${port}`);
    console.log(`  POST /evaluate`);
    console.log(`  POST /evaluate/scenarios`);
  });
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  startServer();
}
