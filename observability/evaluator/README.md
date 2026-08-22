# Evaluator Service (Person B → Person C)

HTTP API that combines Person A test results with SigNoz telemetry to produce objective candidate fitness scores.

## Start

```bash
npm install
npm run build
npm run evaluator:start
```

Dev mode with hot reload:

```bash
npm run evaluator:dev
```

Default port: **8090** (override with `EVALUATOR_PORT`).

## API

### `GET /health`

Health check.

### `POST /evaluate`

Primary integration point for Person C's Port workflow.

**Request body** — see [`../contracts/evaluation-input.example.json`](../contracts/evaluation-input.example.json).

**Response** — see [`../contracts/evaluation-output.example.json`](../contracts/evaluation-output.example.json).

Example:

```bash
curl -s -X POST http://localhost:8090/evaluate \
  -H 'Content-Type: application/json' \
  -d @observability/contracts/evaluation-input.example.json | jq
```

### `POST /evaluate/scenarios`

Runs all four demo scenarios against current SigNoz data (with scenario fallback when SigNoz is unavailable). Returns expected PASS/FAIL alignment.

```bash
curl -s -X POST http://localhost:8090/evaluate/scenarios | jq
```

### `GET /contracts/evaluation-input` and `/contracts/evaluation-output`

Serve frozen contract examples.

## Scoring

| Category | Max points | Gate |
|----------|------------|------|
| Correctness | 40 | Hard gate |
| Reliability | 20 | Hard gate (error rate &lt; 1%) |
| Latency | 20 | p95 ≤1.6s = 20; ≤2.2s = 10 |
| Docs health | 10 | Optional from C via `docs_health` |
| Observability | 10 | Spans + ID correlation |

**PASS** requires correctness + reliability gates and total score ≥ 90.

**ERROR** means SigNoz telemetry could not be queried (missing API key, no traces in window, etc.). Scores are **not** inferred from `scenario` name.

## Environment

```bash
cp observability/evaluator/.env.example observability/evaluator/.env
# Edit observability/evaluator/.env and set SIGNOZ_API_KEY
```

`npm run evaluator:start` loads `observability/evaluator/.env` automatically (via dotenv).

| Variable | Default | Description |
|----------|---------|-------------|
| `EVALUATOR_PORT` | `8090` | HTTP listen port |
| `SIGNOZ_QUERY_URL` | `http://localhost:8080` | SigNoz query service (UI + API) |
| `SIGNOZ_API_KEY` | — | **Required** for `POST /api/v5/query_range`. Create in SigNoz → Settings → Service Accounts → Keys |
| `OTEL_SERVICE_NAME` | `api-guardian` | Service filter for traces |

Traces are fetched via `POST {SIGNOZ_QUERY_URL}/api/v5/query_range` (falls back to v4/v3), **not** `/api/v1/traces` (returns HTML on v0.94).

## Idempotency

Repeated `POST /evaluate` with the same `(factory_run_id, candidate_id, evaluation_window_start)` is idempotent (header `X-Evaluation-Idempotent: true` on repeat).
