# SigNoz Saved Views — API Guardian Demo

Pre-built filters for the 3–5 minute demo. Open SigNoz UI at http://localhost:8080.

## Trace views

### 1. Baseline sequential waterfall

- **Service:** `api-guardian`
- **Operation:** `api_guardian.product_snapshot`
- **Filter:** `demo.scenario = baseline-v1`, `candidate.id = BASELINE`
- **Expected:** child spans `provider.catalog` → `provider.pricing` → `provider.availability` serialized (~2.7s)

### 2. Optimized parallel waterfall

- **Filter:** `demo.scenario = optimized-v1`, `candidate.id = CANDIDATE-PARALLEL`
- **Expected:** three provider spans overlapping; root ~1.1–1.3s

### 3. Pricing V2 error spike

- **Filter:** `demo.scenario = pricing-v2-break`
- **Expected:** `provider.pricing` span status ERROR; error logs with `error.code = SCHEMA_FIELD_MISSING`

### 4. Failing Pricing trace + log correlation

- Open failing trace from view #3
- Click `provider.pricing` span → Logs tab
- **Expected:** structured log with `provider = pricing`, `stage = adapter.parse`

### 5. Recovery after repair

- **Filter:** `demo.scenario = pricing-v2-repaired`, `candidate.id = CANDIDATE-PRICING-V2`
- **Expected:** all provider spans OK, p95 ~1.1–1.3s

### 6. Factory run lineage

- **Filter:** `factory.run_id = RUN-001` (baseline) through `RUN-004` (repaired)
- Compare scores in Port dashboard alongside these traces

### 7. Provider latency unchanged

- **Operations:** `provider.catalog`, `provider.pricing`, `provider.availability`
- **Expected:** individual provider durations remain ~700/900/1100ms across baseline and optimized scenarios

## Dashboard

Import [`api-guardian-primary.json`](./api-guardian-primary.json) via SigNoz → Dashboards → Import.

## Quick links (after local run)

| View | SigNoz path |
|------|-------------|
| Traces | http://localhost:8080/traces |
| Metrics | http://localhost:8080/services/api-guardian |
| Dashboards | http://localhost:8080/dashboard |

## Generate telemetry for all views

```bash
npm run signoz:up
npm run telemetry:scenarios
```
