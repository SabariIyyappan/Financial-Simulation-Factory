# Person B — Observability Layer

Measurement and objective evaluation for API Guardian.

**Start here:** [`PERSON_B_README.md`](../../PERSON_B_README.md) (integration guide for Person A and C).

## Structure

| Path | Purpose |
|------|---------|
| [`contracts/`](contracts/) | Frozen telemetry + evaluation contracts |
| [`signoz/`](signoz/) | Local SigNoz Docker stack, smoke tests, alerts |
| [`evaluator/`](evaluator/) | Fitness scorer + `POST /evaluate` HTTP API |
| [`dashboards/`](dashboards/) | Demo dashboard JSON + saved trace views |
| [`common/`](common/) | SigNoz ClickHouse/collector configs (required for `signoz:up`) |

## Quick start

```bash
npm install
npm run build
npm run signoz:up          # requires Docker; then complete UI setup at :8080
npm run telemetry:smoke
npm run evaluator:start
```

## Handoffs

- **Person A:** [`contracts/TELEMETRY_CONTRACT.md`](contracts/TELEMETRY_CONTRACT.md) + `@api-guardian/telemetry`
- **Person C:** `POST http://localhost:8090/evaluate` — see [`evaluator/README.md`](evaluator/README.md)
