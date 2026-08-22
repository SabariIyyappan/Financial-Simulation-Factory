# API Guardian — Person A working rules

This repo, as currently scaffolded, covers **Person A's** surface only: the app,
the three mock provider APIs, the adapters, and the test/evaluation surface Claude
repairs live during the demo. Person B (SigNoz/telemetry/fitness) and Person C
(Port/Bright Data/orchestration) own separate surfaces — see `/docs/plan/` for the
full three-way plan. Full context: `/docs/plan/MASTER_PLAN.md` and
`/docs/plan/PERSON_A_APP_AND_MOCK_APIS.md` — **the latter is the source of truth
for this repo's implementation. Read it before making structural changes.**

## What's in this repo right now

```
packages/
  domain-contracts/     Shared TS types: ProductSnapshot, provider payload shapes (V1/V2)
  provider-clients/     Adapters: Catalog / Pricing / Availability. Pricing V1 adapter must
                         fail CLEARLY on V2 input — do not make it silently coerce V2.
  telemetry-interface/  The seam Person A codes against. A no-op default implementation
                         ships here so the app runs before Person B's real SigNoz package
                         exists. DO NOT implement real OTel/SigNoz export in this package —
                         that's Person B's package to swap in.
services/
  mock-providers/       Standalone HTTP server: Catalog (~700ms), Pricing (~900ms),
                         Availability (~1100ms). Exposes deterministic mode control
                         (POST /control/pricing-mode) — this IS the "external world changing"
                         the whole demo depends on. Never make it non-deterministic.
apps/
  api-guardian/          Next.js app: Product Snapshot endpoint + thin operator dashboard.
docs/plan/               The four planning documents this repo implements. Do not edit them
                         here — they're the frozen spec, copied in for agent context.
scripts/
  run-evaluation.ts      Produces the evaluation-input.json artifact Person B's evaluator
                         consumes (Contract C in MASTER_PLAN.md).
  demo-control.ts        CLI to flip pricing mode / reset state without touching JSON by hand.
```

## Hard rules (from PERSON_A_APP_AND_MOCK_APIS.md section 12 — do not relax these)

1. Follow `/docs/plan/PERSON_A_APP_AND_MOCK_APIS.md` as the source of truth for this
   surface. Don't redesign the architecture without an explicit reason discussed with
   the team.
2. Don't edit anything that would become Person B's or Person C's owned area
   (SigNoz/OTel export config, Port blueprints/workflows, Bright Data scraping) —
   this repo currently has stubs/placeholders for those, not real implementations.
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
- Every provider call goes through `telemetry-interface`'s `withSpan` wrapper, even
  though it's a no-op today — this is what makes swapping in Person B's real package a
  drop-in change instead of a rewrite.
