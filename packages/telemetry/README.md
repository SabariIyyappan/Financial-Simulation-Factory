# @api-guardian/telemetry

OpenTelemetry helper package for Person A's API Guardian application.

## Install (monorepo)

```typescript
import {
  initTelemetry,
  withProductSnapshot,
  withProviderCall,
  logProviderError,
} from "@api-guardian/telemetry";
```

## Setup

```typescript
initTelemetry(); // reads OTEL_EXPORTER_OTLP_ENDPOINT, OTEL_SERVICE_NAME
```

## Usage

See [`observability/contracts/TELEMETRY_CONTRACT.md`](../../observability/contracts/TELEMETRY_CONTRACT.md) for full contract.

**`logProviderError`:** call inside `withProviderCall` (active span) so logs get `trace_id` / `span_id`.

## Build

```bash
npm run build -w @api-guardian/telemetry
```
