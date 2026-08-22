# SigNoz Local Stack

Local observability for API Guardian. UI: **http://localhost:8080**

## Quick start

### Option A — Bundled Docker Compose (recommended)

```bash
# From repo root
npm run signoz:up
```

Wait ~60s for ClickHouse and services to become healthy, then open http://localhost:8080.

**First launch:** complete the one-time SigNoz setup wizard in the browser (create admin account). Until then, `setupCompleted` stays false in the API.

OTLP endpoints:
- HTTP (recommended): `localhost:4318`
- gRPC: `localhost:4317`

### Option B — SigNoz Foundry (official, optional)

```bash
# Install foundryctl: https://signoz.io/docs/install/docker/
foundryctl cast -f observability/signoz/casting.yaml
cd observability/signoz/pours/deployment && docker compose up -d
```

## Environment

Copy env vars for local development:

```bash
cp observability/signoz/.env.example .env
```

## Smoke test

Generates a sequential Product Snapshot trace (700 + 900 + 1100 ms) before Person A's app exists:

```bash
npm install
npm run signoz:up
# wait for healthy stack
npm run telemetry:smoke
```

Open SigNoz → Traces → filter `service.name = api-guardian` and `name = api_guardian.product_snapshot`.

## Scenario verification

Runs all four demo scenarios and prints evaluator decisions:

```bash
npm run telemetry:scenarios
```

## Stop

```bash
npm run signoz:down
```

## Troubleshooting

- **Port conflicts**: ensure 8080, 4317, 4318 are free.
- **Slow startup**: ClickHouse init can take 1–2 minutes on first run.
- **No traces**: confirm `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318` and collector is running (`docker ps | grep otel`).
