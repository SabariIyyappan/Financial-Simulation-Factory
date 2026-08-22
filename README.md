# API Guardian — Person A surface

Person A's slice of the Zero Downtime Hackathon build: the **software under repair**.
The app, three deterministic mock provider APIs, the provider adapters, and the test +
evaluation surface the coding agent repairs live during the demo.

Person B owns SigNoz/telemetry/fitness scoring. Person C owns Port/Bright Data/
orchestration. The three-way plan lives in [`docs/plan/`](docs/plan/) — start with
[`MASTER_PLAN.md`](docs/plan/MASTER_PLAN.md), then
[`PERSON_A_APP_AND_MOCK_APIS.md`](docs/plan/PERSON_A_APP_AND_MOCK_APIS.md).

TypeScript throughout, strict mode, npm workspaces. No Python anywhere.

## Quick start

```bash
npm install
```

Two terminals:

```bash
npm run dev:providers
```

```bash
npm run dev:app
```

Then open http://localhost:3000 and click **Build Product Snapshot**.

## The two failures this repo exists to produce

### 1. Correct but slow (~2.7s) — AVO-lite repair #1

`apps/api-guardian/src/lib/snapshot.ts` calls Catalog → Pricing → Availability
**sequentially**, even though all three are independent. Measured: **2752 ms**.
Parallelizing brings it to ~1.1s (bounded by the slowest provider). This is deliberate
and must not be pre-optimized — the factory's first candidate change is what fixes it,
and SigNoz's p95 is what proves the improvement objectively.

### 2. Breaking schema change — AVO-lite repair #2

```bash
npm run demo:break-pricing   # Pricing provider flips to V2 nested schema
npm run demo:reset           # back to V1
```

Pricing V1 returns `{ price, currency }` at the root. V2 returns
`{ pricing: { amount, currency } }`. The adapter understands V1 only and **fails loudly**
rather than coercing:

```json
{
  "ok": false,
  "failure": {
    "provider": "pricing",
    "errorType": "ProviderSchemaError",
    "message": "Pricing adapter expected root-level 'price' (number) and 'currency' (string), got neither. Received keys: product_id, pricing, api_version"
  }
}
```

A silent wrong price would be invisible to the factory. Loud, typed, and localized to
`pricing` is the whole point.

## Producing the evaluation artifact (Contract C → Person B)

```bash
npm run evaluate -- --run RUN-001 --candidate BASELINE --scenario baseline-v1
```

Writes `evaluation-input.json` with test counts, schema validity, provider-truth match,
and the evaluation window. Person B combines this with SigNoz telemetry to compute the
candidate fitness score.

Deliberately contains **no latency assertion** — latency is proven from SigNoz telemetry,
never from wall-clock assertions here.

Verified behavior in both states:

| | baseline-v1 | pricing-v2-break |
|---|---|---|
| `tests_passed` | 8 / 8 | 8 / 8 |
| `normalized_schema_valid` | `true` | `false` |
| `requests_succeeded` | 3 / 3 | 0 / 3 |
| `last_failure` | `null` | localized to `pricing` |

Unit tests still pass during the incident — correctly. The adapter's *unit contract* isn't
broken (it rejects V2 exactly as specified); the *integration* is. `normalized_schema_valid`
is what trips Person B's correctness hard gate.

## Layout

```
packages/
  domain-contracts/      ProductSnapshot, provider payload shapes (V1/V2), typed errors
  provider-clients/      Catalog / Pricing / Availability adapters + unit tests
  telemetry-interface/   The seam Person B swaps into — console no-op ships by default
services/
  mock-providers/        HTTP server, fixed delays (700/900/1100ms), pricing mode control
apps/
  api-guardian/          Next.js: /api/snapshot, /api/health, operator dashboard
scripts/
  run-evaluation.ts      Produces evaluation-input.json (Contract C)
  demo-control.ts        reset / pricing-v2 / status
docs/plan/               The frozen three-way spec this repo implements
```

## For Person B — the telemetry handoff

Everything already routes through `packages/telemetry-interface`. Provide a TypeScript
implementation of the `Telemetry` interface (`withSpan` / `recordLog`) and register it
once at app startup:

```ts
import { setTelemetry } from "@api-guardian/telemetry-interface";
setTelemetry(yourSignozImplementation);
```

No call-site changes needed. The span names and attributes the app already emits match
[`PERSON_B_SIGNOZ_AND_FITNESS.md`](docs/plan/PERSON_B_SIGNOZ_AND_FITNESS.md) §3–4:
root `api_guardian.product_snapshot`, children `provider.catalog` / `provider.pricing` /
`provider.availability`, with `factory.run_id`, `candidate.id`, `demo.scenario`,
`provider.name` attributes.

## For Person C — the control surface

```bash
npx tsx scripts/demo-control.ts status        # current pricing mode
npx tsx scripts/demo-control.ts pricing-v2    # trigger the incident
npx tsx scripts/demo-control.ts reset         # restore V1
```

Run identity flows through query params on the snapshot endpoint:

```
/api/snapshot?productId=sku-123&factoryRunId=RUN-001&candidateId=CANDIDATE-PARALLEL&scenario=optimized-v1
```

Products available: `sku-123`, `sku-456`, `sku-789`.

## Status

Done: mock providers with deterministic mode control, all three adapters, sequential
baseline aggregator, snapshot + health endpoints, operator dashboard, 8 passing unit
tests, evaluation artifact producer, demo control CLI. Typechecks and builds clean.

Not done (intentionally): the parallel candidate and the Pricing V2 adapter repair —
both are what the factory produces live during the demo.
