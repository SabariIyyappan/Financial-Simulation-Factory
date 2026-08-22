# Person A - API Guardian App, Mock APIs, and Repair Surface

## 0. Your Mission

You own the **software under repair**.

Your job is to deliver:

1. the API Guardian MVP application,
2. the three deterministic mock external APIs,
3. the provider adapters,
4. the Product Snapshot business flow,
5. the test suite and validation surface,
6. the exact code paths the coding agent will optimize and repair.

You do **not** own SigNoz configuration, Port orchestration, or Bright Data scraping.

This file is written so it can be handed directly to Claude Code as your execution brief.

---

## 1. Ownership Boundaries

### You own

Suggested owned areas:

- `apps/api-guardian/`
- `services/mock-providers/`
- `packages/provider-clients/`
- `packages/domain-contracts/`
- application tests under your owned directories.

Exact directory names may differ, but ownership must remain equivalent.

### You may consume but must not modify without coordination

From Person B:

- telemetry helper/package,
- required trace/span conventions,
- environment variables needed for OTel export.

From Person C:

- factory run ID,
- candidate ID,
- scenario name,
- normalized Bright Data migration evidence during repair flows.

### You must not own

- SigNoz dashboards or alert rules,
- candidate score calculation,
- Port blueprints/workflows,
- Bright Data scraper or docs self-healing logic,
- release approval state machine.

---

## 2. Product Behavior You Must Build

### Main operation: Product Snapshot

Input:

- product ID,
- factory run ID,
- candidate ID,
- demo scenario.

The application obtains independent information from three providers and returns one normalized response.

### Normalized output contract

Required fields:

- product ID,
- name,
- category,
- description,
- price amount,
- currency,
- in-stock boolean,
- quantity,
- estimated ship days,
- provider versions used,
- snapshot generated timestamp.

Do not expose provider-specific schema quirks to the user-facing response. All provider differences belong inside adapters.

### Thin dashboard

The UI should show only what strengthens the demo:

- current Product Snapshot,
- Catalog / Pricing / Availability health,
- current latency,
- current error state,
- current factory/release state supplied by integration endpoints,
- last repair result.

Do not spend excessive time on frontend polish.

---

## 3. Mock API Design

Build one deterministic mock-provider environment exposing three logically separate APIs.

The services may live in one deployable server as long as the routes, spans, docs, and provider behavior remain independent.

## API 1 - Catalog

### Input

Product ID, for example `sku-123`.

### Baseline output

- `product_id`
- `name`
- `category`
- `description`
- `api_version: v1`

### Fixed artificial delay

About 700 ms.

### Failure behavior

No schema failure is required in the core MVP.

### Why this provider matters

It contributes to sequential latency and gives the aggregate response real composition.

---

## API 2 - Pricing

### Baseline V1 output

- `product_id`
- `price`
- `currency`
- `api_version: v1`

### V2 breaking output

- `product_id`
- `pricing.amount`
- `pricing.currency`
- `api_version: v2`

### Fixed artificial delay

About 900 ms.

### Scenario switch

The mock environment must support a deterministic switch between V1 and V2 behavior without rewriting code during the demo.

Preferred behavior:

- one control endpoint or control flag sets Pricing provider mode,
- current mode can be queried,
- mode change is visible in terminal/demo UI,
- switch is deterministic and immediate.

### Failure expectation

Before repair, the V1 adapter should not silently coerce V2 into a valid result.

It should produce a clearly diagnosable failure such as:

- adapter parse error, or
- normalized snapshot schema failure.

The failure must be visible to Person B's instrumentation.

---

## API 3 - Availability

### Baseline output

- `product_id`
- `in_stock`
- `quantity`
- `estimated_ship_days`
- `api_version: v1`

### Fixed artificial delay

About 1,100 ms.

### Failure behavior

No schema change needed in MVP.

---

## 4. Demo Scenarios You Must Support

Your code must expose deterministic scenario behavior matching these names or equivalent frozen names agreed by the team.

### `baseline-v1`

- all providers V1,
- calls are sequential,
- correct result,
- intentionally poor latency.

Expected upstream time:

- Catalog ~700ms,
- Pricing ~900ms,
- Availability ~1,100ms,
- total roughly 2.7 seconds.

### `optimized-v1`

- all providers V1,
- calls are parallel,
- same correct normalized output,
- latency roughly bounded by slowest provider.

Expected upstream time:

about 1.1 seconds plus small overhead.

### `pricing-v2-break`

- Pricing returns V2 nested schema,
- current adapter still assumes V1,
- request fails clearly.

### `pricing-v2-repaired`

- external API remains V2,
- repaired adapter supports V2,
- normalized snapshot passes validation,
- latency remains within threshold.

---

## 5. Application Design Constraint: Make the Latency Repair Obvious

The initial implementation must call:

1. Catalog,
2. then Pricing,
3. then Availability,

serially even though they are independent.

This is intentional.

The first AVO-lite repair must have an obvious, bounded optimization:

> execute the three independent provider calls concurrently and combine the results after all return.

Do not pre-optimize this before the factory demo exists.

The point is to let SigNoz objectively reject a correct but slow candidate.

---

## 6. Telemetry Integration Contract With Person B

Person B owns the telemetry implementation. You own calling it at the correct application boundaries.

You need instrumentation around:

- root Product Snapshot operation,
- Catalog provider call,
- Pricing provider call,
- Availability provider call,
- normalization/validation failure,
- final success/failure.

### Required root span

`api_guardian.product_snapshot`

### Required child spans

- `provider.catalog`
- `provider.pricing`
- `provider.availability`

### Required context you pass into the telemetry helper

- factory run ID,
- candidate ID,
- demo scenario,
- provider name,
- provider version,
- outcome/status.

### Your responsibility

The business logic must preserve trace context across provider calls.

### Person B's responsibility

Export, dashboards, metric derivation, alerting, and SigNoz queries.

---

## 7. Test Surface You Must Build

The factory needs deterministic verification. Build tests before the repair loops.

### Unit tests

For each adapter:

- valid expected provider payload normalizes correctly,
- malformed payload fails clearly,
- current supported versions behave as expected.

### Contract tests

Against each mock API mode:

- endpoint responds,
- response shape matches declared provider version,
- artificial delay occurs within a reasonable tolerance,
- mode switch is visible.

### Product Snapshot integration tests

Baseline V1:

- all normalized fields exist,
- values match provider truth.

Pricing V2 before repair:

- expected fail state occurs.

Pricing V2 after repair:

- expected normalized result succeeds.

### Important

Do not make latency a unit-test assertion. Person B owns real latency verification through SigNoz evaluation windows.

---

## 8. Phase-by-Phase Work

## Phase A0 - Freeze your contracts

### Inputs

- `MASTER_PLAN.md`,
- span convention from Person B,
- IDs/scenario convention from Person C.

### Tasks

- Freeze Product Snapshot input/output.
- Freeze three mock provider schemas.
- Freeze scenario switch behavior.
- Freeze provider delay values.
- Freeze adapter boundaries so Claude repairs a small isolated surface.

### Output

A short provider contract reference in your owned area.

### Handoff

Send Person B:

- endpoint names,
- provider call locations,
- expected delay values.

Send Person C:

- scenario names,
- control endpoint/command for switching Pricing V1/V2.

---

## Phase A1 - Build mock providers

### Tasks

Implement Catalog, Pricing, Availability with fixed data for at least `sku-123`.

Build mode controls.

Ensure the same input always gives the same output in the same mode.

### Input

`sku-123`.

### Expected outputs

Catalog V1 returns stable metadata.

Pricing V1 returns flat price fields.

Pricing V2 returns nested pricing fields.

Availability V1 returns stable inventory/ETA.

### Exit criteria

All provider routes can be exercised independently and mode can be changed without source edits.

### Handoff to Person C

Give Person C exact Pricing V1 and V2 schemas so the provider docs site describes the real behavior accurately.

---

## Phase A2 - Build baseline API Guardian

### Tasks

- Build provider clients/adapters.
- Build Product Snapshot aggregator.
- Build normalized response validator.
- Call providers sequentially.
- Add thin UI/endpoint.

### Input

Product ID `sku-123`, scenario `baseline-v1`.

### Expected output

Correct normalized Product Snapshot in roughly 2.7+ seconds.

### Exit criteria

Correctness passes while latency is intentionally poor.

### Handoff to Person B

Provide runnable evaluation endpoint and exact request needed to generate baseline traces.

---

## Phase A3 - Integrate Person B telemetry package

### Input from Person B

- telemetry helper/package,
- span naming convention,
- required context fields,
- environment configuration.

### Tasks

- Wrap root request.
- Wrap each provider call.
- Emit structured application error on adapter/schema failure.
- Propagate factory/candidate/scenario IDs.

### Expected output

One trace per Product Snapshot with three provider child spans.

### Verification with Person B

Baseline sequential trace should show child spans one after another.

### Exit criteria

Person B confirms trace structure and logs are usable.

---

## Phase A4 - Provide baseline evaluation hooks

### Tasks

Expose or generate test result output that Person B's evaluator can consume.

Required data:

- total tests,
- passed,
- failed,
- normalized schema valid yes/no,
- provider truth comparison pass/fail,
- evaluation window timestamps.

### Expected baseline result

Correctness PASS.

Latency decision is left to Person B.

### Handoff to Person B

Provide deterministic evaluation command/endpoint and test result artifact format.

---

## Phase A5 - First repair surface: sequential to parallel

Do not manually implement this before the repair demo is ready.

### Trigger from Person C

Port/Claude receives Person B's evaluation stating:

- correctness PASS,
- p95 FAIL,
- serialized provider spans visible.

### Expected candidate change

Only change orchestration of independent provider requests from sequential to parallel.

### Your role

- ensure code structure makes this repair safe and local,
- review that Claude did not alter contracts,
- run tests,
- provide candidate to Person B for evaluation.

### Expected output

Same Product Snapshot values with significantly lower latency.

### Handoff to Person B

Candidate ID + evaluation endpoint.

### Handoff to Person C

Candidate commit/reference + test results.

---

## Phase A6 - Trigger Pricing V2 incident

### Tasks

Flip mock Pricing provider to V2 using your deterministic control.

Do not modify API Guardian adapter.

### Expected input to existing adapter

Nested Pricing V2 payload.

### Expected app result

Clearly failed Product Snapshot due to Pricing adapter/validation.

### Handoff to Person B

Tell B exact timestamp and scenario so they can confirm error spike and trace.

### Handoff to Person C

Tell C Pricing V2 is active so Port can open the repair flow and Bright Data evidence can be collected.

---

## Phase A7 - Second repair surface: Pricing V2 migration

### Inputs from Person C

Bright Data evidence including:

- old field path,
- new field path,
- migration summary,
- provider version.

### Inputs from Person B

- failing trace ID,
- provider error details,
- baseline error rate.

### Claude task

Repair the Pricing adapter so the app supports V2 while preserving the normalized Product Snapshot contract.

### Constraints

- do not weaken validation,
- do not change Product Snapshot schema,
- do not bypass provider adapter abstraction,
- do not replace mock APIs,
- do not touch Port/SigNoz/Bright Data areas.

### Expected output

Product Snapshot succeeds against Pricing V2.

### Handoff to Person B

Repaired candidate ID + request/evaluation window.

### Handoff to Person C

Candidate commit/reference + test result output.

---

## Phase A8 - Demo hardening

### Tasks

Create a deterministic operator path for:

- reset to Pricing V1,
- flip Pricing to V2,
- show current provider mode,
- run Product Snapshot,
- reset application test state.

### Avoid

- manual editing of JSON during demo,
- changing environment variables live if avoidable,
- restarting multiple services just to trigger a scenario.

### Exit criteria

A teammate can follow the demo script without understanding implementation internals.

---

## 9. Your Required Inputs From Teammates

## From Person B

You need:

- final telemetry package/helper interface,
- required span/context fields,
- OTel environment configuration,
- expected evaluation window protocol,
- how to tell B which candidate/scenario is running.

If B changes span names or required fields, they must tell you before integration.

## From Person C

You need:

- factory run ID/candidate ID/scenario values,
- Bright Data migration evidence for Pricing V2 repair,
- exact candidate lifecycle state when Claude is allowed to act,
- confirmation of when release has been approved.

---

## 10. What You Must Send Teammates

## To Person B

For every evaluation:

- endpoint/request,
- factory run ID,
- candidate ID,
- scenario,
- evaluation start/end,
- test result artifact.

For incidents:

- provider mode,
- known expected provider behavior.

## To Person C

For every candidate:

- candidate ID,
- commit/reference,
- test summary,
- supported provider versions,
- demo scenario used.

For control:

- exact command/endpoint to flip Pricing V1/V2,
- exact command/endpoint to reset provider state.

---

## 11. Definition of Done for Person A

Your work is complete when:

- three deterministic mock APIs run reliably,
- provider mode switching works,
- baseline Product Snapshot is correct and sequential,
- provider adapters isolate external schemas,
- telemetry hooks are integrated,
- tests provide deterministic evidence,
- parallel candidate can be evaluated without changing contracts,
- Pricing V2 causes a reproducible real failure,
- repaired Pricing adapter passes tests,
- demo controls are one-command/one-click operations,
- you have not taken ownership of B or C's systems.

---

## 12. Claude Guardrails for Your Branch

When giving this document to Claude Code, tell Claude:

- follow this file as the source of truth,
- do not redesign the architecture,
- do not edit Person B/C owned areas,
- do not prematurely parallelize the baseline implementation,
- do not make Pricing V1 adapter magically support V2 before the repair phase,
- preserve deterministic failure modes,
- prefer small, reviewable commits per phase,
- stop at each phase exit criteria before moving forward.
