# Person B — SigNoz, Telemetry, and Fitness Evaluation

Implementation guide for the **measurement and objective scoring layer** of API Guardian. Person A owns the app; Person C owns Port/Bright Data orchestration. This README is the integration entry point for both.

Planning context: [`PERSON_B_SIGNOZ_AND_FITNESS.md`](PERSON_B_SIGNOZ_AND_FITNESS.md) · [`MASTER_PLAN.md`](MASTER_PLAN.md)

---

## What this delivers

| Deliverable | Location |
|-------------|----------|
| OpenTelemetry helper package | [`packages/telemetry/`](packages/telemetry/) |
| Local SigNoz stack (Docker) | [`observability/signoz/`](observability/signoz/) |
| Fitness evaluator HTTP API | [`observability/evaluator/`](observability/evaluator/) |
| Frozen contracts (A↔B↔C) | [`observability/contracts/`](observability/contracts/) |
| Demo dashboards + saved views | [`observability/dashboards/`](observability/dashboards/) |
| Optional SigNoz alerts | [`observability/signoz/alerts/`](observability/signoz/alerts/) |

Person B does **not** edit app business logic, mock APIs, Port workflows, or Bright Data scrapers.

---

## Quick start (Person B)

**Prerequisites:** Node 20+, Docker Desktop running.

```bash
npm install
npm run build
npm run signoz:up          # wait ~60–90s for healthy containers
```

Open **http://localhost:8080** and complete the one-time SigNoz setup wizard (create admin account).

```bash
npm run telemetry:smoke    # sequential baseline trace (~2.7s)
npm run telemetry:scenarios # all four demo scenarios
npm run evaluator:start     # fitness API on :8090
```

Verify:

```bash
curl http://localhost:8090/health
curl -X POST http://localhost:8090/evaluate/scenarios | jq
```

SigNoz UI: **http://localhost:8080** → Traces → filter `service.name = api-guardian`.

Stop SigNoz:

```bash
npm run signoz:down
```

---

## Environment variables

Copy [`observability/signoz/.env.example`](observability/signoz/.env.example) to `.env` at repo root (optional).

| Variable | Default | Used by |
|----------|---------|---------|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://localhost:4318` | Person A app + smoke scripts (HTTP OTLP) |
| `OTEL_SERVICE_NAME` | `api-guardian` | Telemetry + evaluator |
| `SIGNOZ_QUERY_URL` | `http://localhost:8080` | Evaluator (trace queries) |
| `EVALUATOR_PORT` | `8090` | Evaluator HTTP server |
| `PORT_REMEDIATION_WEBHOOK_URL` | — | SigNoz alerts → Person C (optional) |

**Note:** Telemetry uses **OTLP HTTP on port 4318**, not gRPC 4317. If you set `4317`, the package auto-maps to `4318`.

---

## Integration for Person A

### 1. Install and initialize telemetry

```typescript
import {
  initTelemetry,
  withProductSnapshot,
  withProviderCall,
  logProviderError,
  type FactoryContext,
} from "@api-guardian/telemetry";

initTelemetry();
```

### 2. Propagate factory context on every Product Snapshot request

Required on every request (from Person C or your API layer):

- `factory_run_id` — e.g. `RUN-001`
- `candidate_id` — e.g. `BASELINE`, `CANDIDATE-PARALLEL`
- `scenario` — `baseline-v1` | `optimized-v1` | `pricing-v2-break` | `pricing-v2-repaired`

### 3. Wrap spans

```typescript
const ctx: FactoryContext = {
  factoryRunId: req.factory_run_id,
  candidateId: req.candidate_id,
  scenario: req.scenario,
  releaseVersion: req.release_version,
};

return withProductSnapshot(ctx, async () => {
  const catalog = await withProviderCall(ctx, "catalog", { version: "v1" }, () =>
    catalogClient.fetch(productId)
  );
  // pricing, availability — same pattern
});
```

### 4. Emit structured errors on adapter failures (Pricing V2 demo)

```typescript
logProviderError(ctx, "pricing", "SCHEMA_FIELD_MISSING", "Expected root field 'price' not found");
```

### 5. Supply evaluation input after test runs

After integration tests, POST this shape to Person B’s evaluator (or hand JSON to Person C). See [`observability/contracts/evaluation-input.example.json`](observability/contracts/evaluation-input.example.json).

```json
{
  "factory_run_id": "RUN-001",
  "candidate_id": "BASELINE",
  "scenario": "baseline-v1",
  "evaluation_window_start": "2026-08-22T20:00:00.000Z",
  "evaluation_window_end": "2026-08-22T20:05:00.000Z",
  "tests": {
    "total": 12,
    "passed": 12,
    "failed": 0,
    "schema_valid": true,
    "provider_truth_match": true
  }
}
```

Full contract: [`observability/contracts/TELEMETRY_CONTRACT.md`](observability/contracts/TELEMETRY_CONTRACT.md)

### Person A checklist

- [ ] `initTelemetry()` at app startup
- [ ] Root span `api_guardian.product_snapshot` per request
- [ ] Child spans `provider.catalog`, `provider.pricing`, `provider.availability`
- [ ] Attributes `factory.run_id`, `candidate.id`, `demo.scenario` on spans
- [ ] Test artifact + evaluation window timestamps after each run
- [ ] SigNoz running locally (`npm run signoz:up`) during dev

---

## Integration for Person C

### Primary path: call the evaluator after each factory run

```bash
POST http://localhost:8090/evaluate
Content-Type: application/json

# Body = evaluation-input (Contract C from Person A + optional docs_health from you)
```

Response = [`evaluation-output`](observability/contracts/evaluation-output.example.json) with `score`, `decision` (`PASS`/`FAIL`), `failure_reason`, `p95_latency_ms`, `representative_trace_id`, etc.

Example:

```bash
curl -s -X POST http://localhost:8090/evaluate \
  -H 'Content-Type: application/json' \
  -d @observability/contracts/evaluation-input.example.json | jq
```

Contract examples also served at:

- `GET http://localhost:8090/contracts/evaluation-input`
- `GET http://localhost:8090/contracts/evaluation-output`

### Optional: docs health score (10 points)

Include on the evaluate request when Bright Data docs extraction is healthy:

```json
"docs_health": {
  "fields_present": true,
  "schema_valid": true
}
```

If omitted, evaluator scores 0/10 for docs health and sets `docs_health_note: "not_supplied"`.

### Optional: SigNoz alert webhooks

Configure alerts using [`observability/signoz/alerts/`](observability/signoz/alerts/). Set:

```bash
export PORT_REMEDIATION_WEBHOOK_URL=http://localhost:3001/webhooks/signoz
```

Person C should accept webhook payloads documented in [`observability/signoz/alerts/README.md`](observability/signoz/alerts/README.md).

**Primary source of truth for PASS/FAIL remains `POST /evaluate`**, not alerts alone.

### Canonical IDs (agreed)

| Field | Examples |
|-------|----------|
| `factory_run_id` | `RUN-001`, `RUN-002`, … |
| `candidate_id` | `BASELINE`, `CANDIDATE-PARALLEL`, `CANDIDATE-PRICING-V2` |
| `scenario` | `baseline-v1`, `optimized-v1`, `pricing-v2-break`, `pricing-v2-repaired` |

### Person C checklist

- [ ] Invoke `POST /evaluate` after each factory run with run/candidate/scenario + A’s test artifact
- [ ] Store evaluation output on Port `Evaluation` entity
- [ ] Provide `PORT_REMEDIATION_WEBHOOK_URL` if using SigNoz alerts
- [ ] Pass `docs_health` when Bright Data extraction is part of the score

---

## Fitness scoring (100 points)

| Category | Points | Gate |
|----------|--------|------|
| Correctness | 40 | Hard gate (schema, tests, provider truth) |
| Reliability | 20 | Hard gate (error rate &lt; 1%) |
| Latency | 20 | p95 ≤1.6s = 20; ≤2.2s = 10; &gt;2.2s = 0 |
| Docs health | 10 | From Person C `docs_health` |
| Observability | 10 | Spans + run/candidate correlation |

**PASS** requires correctness + reliability gates and total score ≥ 90.

---

## Demo scenarios (expected evaluator results)

| Scenario | Expected decision | Why |
|----------|-------------------|-----|
| `baseline-v1` | FAIL | Correct but p95 &gt; 2.2s (sequential calls) |
| `optimized-v1` | PASS | Parallel calls, p95 ~1.1s |
| `pricing-v2-break` | FAIL | Correctness/reliability fail (Pricing adapter) |
| `pricing-v2-repaired` | PASS | Repaired adapter, V2 pricing |

Run synthetic telemetry for all scenarios:

```bash
npm run telemetry:scenarios
```

---

## Repository layout (Person B owned)

```
packages/telemetry/           # @api-guardian/telemetry
observability/
  contracts/                  # TELEMETRY_CONTRACT.md + JSON examples
  signoz/                     # docker-compose, smoke tests, alerts
  evaluator/                  # scorer + POST /evaluate
  dashboards/                 # demo dashboard JSON + saved views
  common/                     # SigNoz ClickHouse/collector configs (required for Docker)
```

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `signoz:up` fails on `config.xml` mount | Ensure `observability/common/` exists (committed in repo) |
| No traces in SigNoz | Docker running; use `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318` |
| Connection reset on 4317 | Expected — use HTTP 4318 (default in telemetry package) |
| `setupCompleted: false` | Complete wizard at http://localhost:8080 |
| Evaluator returns round numbers like 2750 ms | May be using scenario fallback if SigNoz trace API query fails |
| Port 8080 in use | Stop conflicting service or change SigNoz port mapping |

---

## Testing status

**Smoke-tested:** Docker stack, OTLP ingest, smoke/scenario scripts, evaluator `/evaluate/scenarios`.

**Not yet integrated:** Person A real app, Person C Port workflow, live SigNoz trace API scoring (fallback stubs used when query fails), alert webhooks.

**No automated unit test suite** — add `npm test` before production hardening if needed.

---

## npm scripts reference

| Script | Description |
|--------|-------------|
| `npm run build` | Build telemetry + evaluator packages |
| `npm run signoz:up` | Start SigNoz Docker stack |
| `npm run signoz:down` | Stop SigNoz |
| `npm run telemetry:smoke` | Emit one sequential baseline trace |
| `npm run telemetry:scenarios` | Emit all four demo scenarios |
| `npm run evaluator:start` | Start evaluator on :8090 |
| `npm run evaluator:dev` | Evaluator with hot reload |

---

## Questions?

- Telemetry API: [`packages/telemetry/README.md`](packages/telemetry/README.md)
- Evaluator API: [`observability/evaluator/README.md`](observability/evaluator/README.md)
- SigNoz local setup: [`observability/signoz/README.md`](observability/signoz/README.md)
- Demo trace filters: [`observability/dashboards/saved-views.md`](observability/dashboards/saved-views.md)
