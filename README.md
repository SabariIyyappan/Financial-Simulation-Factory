# API Guardian — Person A surface

Person A's slice of the Zero Downtime Hackathon build: the **software under repair**.
The app, three deterministic mock provider APIs, the provider adapters, and the test +
evaluation surface the coding agent repairs live during the demo.

Person B owns SigNoz/telemetry/fitness scoring. Person C owns Port/Bright Data/
orchestration. The three-way plan lives at the repo root — start with
[`MASTER_PLAN.md`](MASTER_PLAN.md), then
[`PERSON_A_APP_AND_MOCK_APIS.md`](PERSON_A_APP_AND_MOCK_APIS.md).

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

Writes `evaluation-input.json` in the exact shape Person B's evaluator expects — verified
key-for-key against
[`evaluation-input.example.json`](observability/contracts/evaluation-input.example.json).
POST it to the evaluator at `http://localhost:8090/evaluate`.

Deliberately contains **no latency assertion** — latency is proven from SigNoz telemetry,
never from wall-clock assertions here.

Verified behavior in both states:

| | baseline-v1 | pricing-v2-break |
|---|---|---|
| `tests.passed` | 8 / 8 | 8 / 8 |
| `tests.schema_valid` | `true` | `false` |
| upstream duration | ~2.75s | fails at pricing |

Unit tests still pass during the incident — correctly. The adapter's *unit contract* isn't
broken (it rejects V2 exactly as specified); the *integration* is. `tests.schema_valid`
is what trips Person B's correctness hard gate. Worth saying out loud in the demo, or
"8/8 passing" during an incident reads as a broken test suite.

## Layout

```
packages/
  domain-contracts/      ProductSnapshot, provider payload shapes (V1/V2), typed errors
  provider-clients/      Catalog / Pricing / Availability adapters + unit tests
  telemetry/             Person B's OTel/SigNoz package — their surface, not edited here
services/
  mock-providers/        HTTP server, fixed delays (700/900/1100ms), pricing mode control
apps/
  api-guardian/          Next.js: /api/snapshot, /api/health, operator dashboard
                         src/instrumentation.ts boots Person B's OTel SDK at startup
observability/           Person B's SigNoz stack, evaluator service, contracts
scripts/
  run-evaluation.ts      Produces evaluation-input.json (Contract C)
  demo-control.ts        reset / pricing-v2 / status
```

Two tsconfig bases, deliberately: `tsconfig.base.json` (NodeNext, builds to `dist`) for
Person B's telemetry package and evaluator; `tsconfig.app.json` (bundler, typecheck-only)
for Person A's packages, which ship raw TS for Next to transpile.

## Person B integration — done

The app calls Person B's package directly, per
[`TELEMETRY_CONTRACT.md`](observability/contracts/TELEMETRY_CONTRACT.md):

- `src/instrumentation.ts` calls `initTelemetry()` once at server startup
- `buildProductSnapshot` wraps work in `withProductSnapshot` / `withProviderCall`
- adapter failures emit `logProviderError(ctx, provider, code, message)` **inside** the
  active span, so `trace_id` / `span_id` land on the log record
- `releaseVersion` flows from the query string into `FactoryContext`

Verified: `[telemetry] OTel SDK initialised, exporting to http://localhost:4318` on boot.
Spans go nowhere until SigNoz is up (`npm run signoz:up`), which is expected.

Error codes emitted: `SCHEMA_FIELD_MISSING` (adapter can't parse), `PROVIDER_UNAVAILABLE`
(HTTP/network), `UNKNOWN_ERROR`.

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
