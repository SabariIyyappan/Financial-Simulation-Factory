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

## Build

```bash
npm run build -w @api-guardian/telemetry
```
