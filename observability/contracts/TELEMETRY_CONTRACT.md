# Telemetry Contract (Person B → Person A / Person C)

Frozen interface for API Guardian observability. Changes require acknowledgment from all three owners.

## Environment variables

Person A must set these before starting the application:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Yes | `http://localhost:4318` | OTLP HTTP collector endpoint |
| `OTEL_SERVICE_NAME` | No | `api-guardian` | Service name in SigNoz |
| `OTEL_LOG_LEVEL` | No | `info` | SDK log level |

## Span names (Contract B)

| Span name | When |
|-----------|------|
| `api_guardian.product_snapshot` | Root span for each Product Snapshot request |
| `provider.catalog` | Catalog provider HTTP call |
| `provider.pricing` | Pricing provider HTTP call |
| `provider.availability` | Availability provider HTTP call |

Optional child spans: `snapshot.normalize`, `snapshot.validate`.

## Required span attributes

Every root and provider span must include:

| Attribute | Example | Source |
|-----------|---------|--------|
| `factory.run_id` | `RUN-001` | Person C / request context |
| `candidate.id` | `BASELINE` | Person C / request context |
| `demo.scenario` | `baseline-v1` | Request context |
| `provider.name` | `pricing` | Provider spans only |
| `provider.version` | `v1` | Provider spans only |
| `provider.status` | `ok` / `error` | Set on span end |

Optional on root span: `release.version` when present.

## Structured log fields

On adapter or schema failures (especially Pricing V2), emit a structured log with:

| Field | Example |
|-------|---------|
| `timestamp` | ISO-8601 |
| `severity` | `ERROR` |
| `trace_id` | OTel trace ID |
| `span_id` | OTel span ID |
| `factory.run_id` | `RUN-001` |
| `candidate.id` | `BASELINE` |
| `scenario` | `pricing-v2-break` |
| `stage` | `adapter.parse` |
| `provider` | `pricing` |
| `error.code` | `SCHEMA_FIELD_MISSING` |
| `error.message` | Concise human-readable message |

## Metrics

Person B's telemetry package records these automatically when helpers are used:

| Metric | Type | Labels |
|--------|------|--------|
| `api_guardian.product_snapshot.duration` | Histogram (ms) | `factory.run_id`, `candidate.id`, `demo.scenario` |
| `api_guardian.product_snapshot.errors` | Counter | same |
| `api_guardian.provider.duration` | Histogram (ms) | `provider.name`, `provider.version` |
| `api_guardian.provider.errors` | Counter | `provider.name` |

## Person A integration

```typescript
import {
  initTelemetry,
  withProductSnapshot,
  withProviderCall,
  logProviderError,
  type FactoryContext,
} from "@api-guardian/telemetry";

initTelemetry();

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
  // ... pricing, availability
});
```

On Pricing adapter failure:

```typescript
logProviderError(ctx, "pricing", "SCHEMA_FIELD_MISSING", "Expected root field 'price' not found in V2 response");
```

## Evaluation input (Contract C: A → B)

See [`evaluation-input.example.json`](./evaluation-input.example.json).

Person A supplies test results and evaluation window timestamps after each run. Person C may optionally add `docs_health`:

```json
{
  "docs_health": {
    "fields_present": true,
    "schema_valid": true
  }
}
```

If omitted, the evaluator scores 0/10 for docs health and sets `docs_health_note: "not_supplied"`.

## Evaluation output (Contract D: B → C)

See [`evaluation-output.example.json`](./evaluation-output.example.json).

Person C consumes this via `POST http://localhost:8090/evaluate` (evaluator service).

### Decision rules

- **PASS**: correctness hard gate passes, reliability hard gate passes, total score ≥ 90
- **FAIL**: otherwise

### Latency thresholds

| p95 | Latency points |
|-----|----------------|
| ≤ 1.6s | 20 |
| > 1.6s and ≤ 2.2s | 10 |
| > 2.2s | 0 |

### Reliability thresholds

- Error rate must be < 1% for reliability gate
- No provider adapter exceptions during verification window

## Canonical IDs and scenarios

| Field | Examples |
|-------|----------|
| `factory_run_id` | `RUN-001`, `RUN-002` |
| `candidate_id` | `BASELINE`, `CANDIDATE-PARALLEL`, `CANDIDATE-PRICING-V2` |
| `scenario` | `baseline-v1`, `optimized-v1`, `pricing-v2-break`, `pricing-v2-repaired` |
