# API Guardian — Person A working rules

**Person A's** surface: the app, the three mock provider APIs, the adapters, and the
test/evaluation surface Claude repairs live during the demo. Person B's telemetry and
observability work is merged in and integrated. Person C (Port/Bright Data/orchestration)
hasn't landed yet.

Plan docs live at the repo root. `PERSON_A_APP_AND_MOCK_APIS.md` is the source of truth
for this surface — **read it before making structural changes**;
`observability/contracts/TELEMETRY_CONTRACT.md` is the frozen A↔B interface.

## What's in this repo right now

```
packages/
  domain-contracts/     Shared TS types: ProductSnapshot, provider payload shapes (V1/V2)
  provider-clients/     Adapters: Catalog / Pricing / Availability. Pricing V1 adapter must
                         fail CLEARLY on V2 input — do not make it silently coerce V2.
  telemetry/            PERSON B'S PACKAGE. Real OTel/SigNoz export. Do not edit — if the
                         API needs to change, that's a contract discussion with B.
services/
  mock-providers/       Standalone HTTP server: Catalog (~700ms), Pricing (~900ms),
                         Availability (~1100ms). Exposes deterministic mode control
                         (POST /control/pricing-mode) — this IS the "external world changing"
                         the whole demo depends on. Never make it non-deterministic.
apps/
  api-guardian/          Next.js app: Product Snapshot endpoint + thin operator dashboard.
                         src/instrumentation.ts boots B's OTel SDK (must live under src/,
                         Next does not pick it up from the app root when src/ exists).
observability/          PERSON B'S AREA. SigNoz docker stack, evaluator service, frozen
                         contracts. Read observability/contracts/, don't edit it.
*.md at repo root       The frozen three-way spec. Do not edit.
scripts/
  run-evaluation.ts      Produces the evaluation-input.json artifact Person B's evaluator
                         consumes (Contract C in MASTER_PLAN.md).
  demo-control.ts        CLI to flip pricing mode / reset state without touching JSON by hand.
```

## Hard rules (from PERSON_A_APP_AND_MOCK_APIS.md section 12 — do not relax these)

1. Follow `PERSON_A_APP_AND_MOCK_APIS.md` as the source of truth for this
   surface. Don't redesign the architecture without an explicit reason discussed with
   the team.
2. Do not edit Person B's or Person C's owned areas. `packages/telemetry/` and
   `observability/` are Person B's — merged in and working; consume their API, don't
   change it. Port blueprints/workflows and Bright Data scraping are Person C's and
   aren't in this repo yet.
3. **Do not prematurely parallelize the baseline `apps/api-guardian` provider calls.**
   Sequential Catalog → Pricing → Availability is intentional — it's the whole reason
   the first AVO-lite repair (sequential → parallel) has something to fix. The
   parallelization is supposed to happen live, as a candidate change, during the demo.
4. **Do not make the Pricing V1 adapter accept V2 payloads.** The V1 adapter must fail
   clearly (a typed error, not a silent wrong value) when it receives the nested
   `pricing.amount` / `pricing.currency` shape. That failure is the second AVO-lite
   repair's entire premise.
5. Preserve deterministic failure modes. `services/mock-providers` must always give the
   same output for the same input in the same mode — no randomness, no real network
   calls to anything outside this repo.
6. Latency is proven with SigNoz telemetry (Person B's job), not with unit test
   assertions. Don't write a test that asserts on wall-clock timing.
7. Prefer small, reviewable commits per phase. Stop at each phase's exit criteria
   (see the Person A doc, section 8) before moving to the next.

## Local dev

```bash
npm install
npm run dev:providers   # mock-providers on :4001
npm run dev:app         # Next.js app on :3000, calls mock-providers
```

`apps/api-guardian/.env.local` (copy from `.env.example`): `MOCK_PROVIDERS_URL=http://localhost:4001`

## Conventions

- TypeScript strict everywhere. No `any` without narrowing immediately.
- No comments explaining *what* — only *why*, and only when non-obvious (e.g. why the
  Pricing V1 adapter must reject V2 rather than coerce it).
- Every provider call goes through Person B's `withProviderCall`, and the whole snapshot
  through `withProductSnapshot`. Never call a provider outside those wrappers — an
  unwrapped call is invisible to SigNoz, and the fitness function scores observability
  completeness.
- Adapter failures must call `logProviderError` **inside** the active span (see the inner
  try/catch in `snapshot.ts`). Logging after the span closes loses `trace_id`/`span_id`,
  which is what makes a failure traceable back to a request.
- Two tsconfig bases on purpose: `tsconfig.base.json` (NodeNext → `dist`) is Person B's,
  for packages that compile; `tsconfig.app.json` (bundler, `noEmit`) is Person A's, for
  packages that ship raw TS. Extend the right one; don't merge them.
