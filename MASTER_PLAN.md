# API Guardian MVP - Master Plan

## 0. Purpose

Build a hackathon-ready MVP of **API Guardian**, an autonomous reliability product that detects when a third-party API integration degrades or breaks, gathers evidence from telemetry and live provider documentation, proposes a repair, objectively verifies the candidate, and requires human approval before release.

The **application is the proof surface**. The **AVO-lite software factory is the submission**.

This plan is designed for a team of three working in parallel without code ownership conflicts.

---

## 1. Locked Architecture

We are using an **AVO-lite autonomous software factory** because it directly maps to the hackathon criteria without recreating NVIDIA AVO in full.

### Control loop

1. **Inspect** current system context and evidence.
2. **Plan** the smallest change that could improve the objective.
3. **Act** by creating a candidate change.
4. **Evaluate** with deterministic tests and SigNoz telemetry.
5. **Diagnose** if the candidate regresses or still fails.
6. **Repair / retry** with a new candidate.
7. **Preserve improvement** only when objective checks pass.
8. **Human approval** gates final release.

### Sponsor roles

- **Port** = context, state, workflow orchestration, candidate lineage, governance, human approval, audit trail.
- **Bright Data** = live changing external environment; structured provider docs/changelog extraction; self-healing scraper when docs HTML changes.
- **SigNoz** = objective evidence; traces, logs, metrics, alerts, before/after verification.
- **Claude Code / coding agent** = actor that inspects evidence, edits the integration, runs tests, and proposes a repair.

---

## 2. MVP Product

### What API Guardian does

API Guardian monitors an application that depends on three external APIs. It identifies integration health problems and produces a repair candidate with evidence.

The MVP application exposes a single business operation:

**Build Product Snapshot**

Given a product ID, the app fetches:

1. product metadata from Catalog API,
2. price from Pricing API,
3. availability / ETA from Availability API,

and returns one normalized product snapshot.

### Example normalized result

- Product ID: `sku-123`
- Name: `Zero Downtime Router`
- Category: `networking`
- Price: `129.99 USD`
- In stock: `true`
- Quantity: `42`
- Estimated ship days: `2`

The user-facing dashboard shows:

- integration health for all three providers,
- current aggregate latency,
- current error rate,
- current factory score,
- last incident,
- current repair candidate,
- verification result,
- release approval state.

The UI should remain thin. The demo value comes from the factory loop.

---

## 3. Three Mock External APIs

We intentionally use **three deterministic mock providers** so every failure is reproducible during a 3-5 minute demo.

### API 1 - Catalog API

Purpose: stable product metadata.

Baseline endpoint behavior:

- Input: product ID.
- Output: product ID, name, category, description.
- Artificial latency: about **700 ms**.
- Does not change schema during the primary demo.

Why it exists:

- contributes to the sequential latency problem,
- demonstrates three-provider composition,
- remains stable so the audience can isolate failures in other providers.

### API 2 - Pricing API

Purpose: current price and currency.

Baseline V1 output:

- `product_id`
- `price`
- `currency`

Artificial latency: about **900 ms**.

Breaking V2 output:

- `product_id`
- `pricing.amount`
- `pricing.currency`

Artificial latency remains about **900 ms**.

Primary schema-break failure:

- API Guardian initially expects `price` and `currency` at the root.
- Provider flips to V2.
- Parsing fails or produces an invalid normalized snapshot.
- SigNoz shows errors concentrated inside `provider.pricing`.
- Bright Data retrieves the updated pricing migration documentation.
- Claude patches the Pricing adapter.
- Tests and telemetry verify recovery.

### API 3 - Availability API

Purpose: stock, quantity, and ETA.

Baseline output:

- `product_id`
- `in_stock`
- `quantity`
- `estimated_ship_days`

Artificial latency: about **1,100 ms**.

It remains schema-stable in the MVP.

Why it exists:

- creates a clear sequential-vs-parallel optimization opportunity,
- makes the SigNoz trace waterfall visually obvious.

---

## 4. Deterministic Demo Modes

Do not depend on random production failures. The mock provider environment must have explicit demo modes.

### Mode `baseline-v1`

- Catalog V1.
- Pricing V1.
- Availability V1.
- Fixed latencies 700 / 900 / 1,100 ms.
- API Guardian calls providers **sequentially**.
- Expected total upstream time: roughly **2.7 seconds** plus application overhead.
- Correctness passes, latency fitness fails.

### Mode `optimized-v1`

- Same API responses and delays.
- API Guardian calls all independent providers **in parallel**.
- Expected total upstream time: roughly **1.1 seconds** plus overhead.
- Correctness passes and latency fitness passes.

### Mode `pricing-v2-break`

- Catalog unchanged.
- Pricing flips to nested `pricing.amount` / `pricing.currency` schema.
- Availability unchanged.
- Parallel request behavior remains.
- Expected outcome before repair: snapshot validation failure or Pricing adapter error.

### Mode `pricing-v2-repaired`

- Same Pricing V2 external behavior.
- API Guardian adapter is repaired.
- Correctness, latency, and error-rate checks pass.

### Docs layout modes

The public provider docs site must also support:

- `docs-layout-v1`: structure matching the original Bright Data scraper.
- `docs-layout-v2`: same human-visible migration information, but DOM structure / selectors materially changed.

This is the required Bright Data self-healing demonstration.

---

## 5. Objective Fitness Function

The factory must not accept an LLM saying "looks good." Every candidate receives an objective evaluation.

### Candidate fitness: 100 points

#### Correctness - 40 points

- 20: normalized Product Snapshot schema is valid.
- 10: all contract/integration tests pass.
- 10: Pricing result matches provider truth in current demo mode.

Hard gate: if correctness fails, candidate cannot be released.

#### Reliability - 20 points

- 10: request error rate under 1% during evaluation window.
- 10: no provider adapter exceptions during verification run.

#### Latency - 20 points

- 20: p95 Product Snapshot latency <= 1.6 seconds.
- 10: p95 <= 2.2 seconds.
- 0: p95 > 2.2 seconds.

#### Data pipeline / docs health - 10 points

- 5: Bright Data returns required migration fields.
- 5: extracted migration schema validates.

#### Observability / trace completeness - 10 points

- 5: expected root + provider spans are present.
- 5: run/candidate IDs correlate traces, metrics, and logs.

### Release conditions

A candidate is eligible for approval only if:

- correctness gate passes,
- reliability gate passes,
- score >= 90,
- score is not worse than currently released version,
- Port human approval is granted.

---

## 6. Team Ownership - No-Conflict Split

### Person A - Product + Mock Providers + Repair Surface

Owns:

- API Guardian application behavior,
- UI / product snapshot endpoint,
- provider client/adapters,
- three mock API services,
- deterministic demo controls for provider behavior,
- unit / contract / integration tests,
- code surface Claude will repair,
- application-side integration of the telemetry helper interface supplied by Person B.

Person A does **not** configure SigNoz, Port, or Bright Data.

### Person B - SigNoz + Objective Evaluation

Owns:

- OpenTelemetry package / conventions,
- SigNoz deployment/configuration,
- traces, metrics, logs,
- dashboards,
- alert thresholds,
- evaluation evidence collector,
- candidate fitness calculation from test results + telemetry,
- before/after latency verification.

Person B does **not** edit provider business logic or Port/Bright Data workflows.

### Person C - Port + Bright Data + AVO-lite Orchestration

Owns:

- Port blueprints/catalog/context,
- FactoryRun / CandidateVersion / Evaluation / Release entities,
- Port workflows and human approval,
- Bright Data Scraper Studio integration,
- public provider docs/changelog site,
- docs layout break and self-healing demonstration,
- AVO-lite orchestration between evidence, Claude, evaluation, retry, and approval,
- final demo orchestration script/runbook.

Person C does **not** edit API business logic or SigNoz instrumentation internals.

---

## 7. Shared Contracts

These contracts are frozen in Phase 0. Changes require all three people to acknowledge them.

### Contract A - Run identity

Every factory/evaluation request carries:

- `factory_run_id`
- `candidate_id`
- `scenario`
- `release_version`

These identifiers must appear in:

- app logs,
- traces,
- evaluation payloads,
- Port entities.

### Contract B - Provider span names

Person A invokes the telemetry helper around each provider call. Person B owns the helper implementation and conventions.

Required span names:

- `api_guardian.product_snapshot`
- `provider.catalog`
- `provider.pricing`
- `provider.availability`

Required span attributes:

- `factory.run_id`
- `candidate.id`
- `demo.scenario`
- `provider.name`
- `provider.version`
- `provider.status`

### Contract C - Evaluation input from A to B

After an evaluation run, Person A makes deterministic test results available:

- total tests,
- passed tests,
- failed tests,
- normalized schema valid yes/no,
- provider truth comparison pass/fail,
- evaluation window start/end timestamp.

Person B combines this with SigNoz telemetry to calculate the candidate score.

### Contract D - Evaluation output from B to C

Person B publishes one evaluation object containing:

- candidate ID,
- scenario,
- score,
- correctness status,
- p50/p95 latency,
- error rate,
- failed provider if any,
- relevant trace ID(s),
- evaluation decision: PASS / FAIL,
- concise machine-readable failure reason.

Person C consumes this object in Port.

### Contract E - Bright Data evidence from C to Claude / repair loop

For a breaking API incident, Person C makes a normalized docs evidence object available:

- provider,
- current provider version,
- breaking change summary,
- old field/path,
- new field/path,
- migration guidance,
- source timestamp,
- scraper health,
- self-heal attempted yes/no.

This evidence is passed to the coding agent together with SigNoz evidence.

### Contract F - Candidate lifecycle

Allowed states:

1. `DETECTED`
2. `INVESTIGATING`
3. `PLANNED`
4. `IMPLEMENTED`
5. `EVALUATING`
6. `REJECTED`
7. `READY_FOR_APPROVAL`
8. `APPROVED`
9. `RELEASED`

Only Person C's Port workflow changes lifecycle state.

---

## 8. Phase-by-Phase Execution

## Phase 0 - Freeze contracts and repo ownership

Goal: all three people can work independently after this phase.

### Inputs

- this master plan,
- hackathon criteria,
- chosen sponsor accounts/environments.

### Work

- Agree directory ownership.
- Freeze three mock API schemas.
- Freeze span names and IDs.
- Freeze evaluation object schema.
- Freeze Port candidate lifecycle.
- Agree exact demo scenario names.
- Create one shared `INTEGRATION_CONTRACTS.md` only if needed; otherwise use this section as source of truth.

### Outputs

- no ambiguous ownership,
- exact interfaces between A/B/C,
- branches or worktrees ready.

### Exit criteria

Each person can state exactly what they produce and what they consume.

---

## Phase 1 - Build independent foundations

Goal: create three independently testable vertical foundations.

### Person A

Build:

- three mock provider APIs,
- baseline Product Snapshot application,
- sequential provider call implementation,
- deterministic provider modes,
- integration tests.

Expected baseline behavior:

- functional result correct,
- latency intentionally slow around 2.7 seconds upstream.

### Person B

Build:

- OTel/SigNoz foundation,
- telemetry conventions/helper package,
- dashboard skeleton,
- metrics and log field definitions,
- evaluation calculator that can initially consume placeholder telemetry.

### Person C

Build:

- Port entity model,
- FactoryRun/Candidate/Evaluation workflow skeleton,
- public provider docs site,
- Bright Data scraper against docs-layout-v1,
- normalized docs evidence shape.

### Integration checkpoint

A gives B:

- runnable app endpoint,
- provider endpoints,
- required telemetry integration points.

B gives A:

- telemetry helper interface and required environment/config inputs.

B gives C:

- provisional evaluation output example.

C gives A/B:

- factory run ID + candidate ID propagation rules.

### Exit criteria

All three foundations work independently.

---

## Phase 2 - Baseline end-to-end observability

Goal: produce the first complete run with intentionally bad latency.

### Flow

1. Port creates FactoryRun `RUN-001` / candidate `BASELINE`.
2. API Guardian executes Product Snapshot in `baseline-v1`.
3. Catalog, Pricing, Availability are called sequentially.
4. SigNoz captures one root span and three non-overlapping provider child spans.
5. Test correctness passes.
6. SigNoz p95 is above threshold.
7. Person B's evaluator gives a score below release threshold due to latency.
8. Port records the evaluation as FAIL and starts diagnosis.

### Expected evidence

SigNoz trace waterfall clearly shows:

- Catalog ~700ms,
- then Pricing ~900ms,
- then Availability ~1,100ms,
- aggregate ~2.7s.

### Expected machine-readable diagnosis input

- correctness: PASS,
- p95 latency: FAIL,
- provider errors: none,
- likely optimization clue: independent provider spans are serialized.

### Exit criteria

We can prove: **the application is correct but the factory rejects it because telemetry says performance is poor.**

---

## Phase 3 - AVO-lite repair #1: sequential to parallel

Goal: demonstrate telemetry-driven software improvement.

### Inspect

Port/agent receives:

- current candidate metadata,
- SigNoz evaluation object,
- trace IDs,
- test results,
- service context.

### Plan

Expected plan hypothesis:

> Catalog, Pricing, and Availability requests are independent and currently serialized. Run them concurrently while preserving normalized output and error handling.

### Act

Claude creates candidate `CANDIDATE-PARALLEL` by modifying only Person A-owned application integration logic.

### Evaluate

- Run all tests.
- Execute same fixed-latency scenario.
- SigNoz captures provider spans overlapping in time.
- Expected aggregate p95 near 1.1-1.3s.
- Error rate remains low.
- Correctness remains PASS.

### Decision

Expected score: >= 90.

Port marks candidate `READY_FOR_APPROVAL`.

### Human gate

Human approves.

### Output

Release `v1-optimized` becomes current best candidate.

### Demo proof

Before:

- sequential trace,
- p95 ~2.7s,
- score below threshold.

After:

- parallel trace,
- p95 ~1.1s,
- score above threshold.

This is the clearest AVO-lite feedback-loop demonstration.

---

## Phase 4 - Breaking API incident

Goal: show runtime failure caused by the external world changing.

### Trigger

Person A flips Pricing provider to `pricing-v2-break`.

### External change

Old:

- `price`
- `currency`

New:

- `pricing.amount`
- `pricing.currency`

### Expected application failure

- Pricing adapter cannot normalize response.
- Product Snapshot fails validation or emits a provider parsing error.

### SigNoz evidence

Expected:

- error-rate increase,
- failing `provider.pricing` spans,
- structured error log identifying missing expected field,
- trace correlation back to the Product Snapshot request.

### Port behavior

- creates incident/factory run,
- marks candidate degraded,
- enters `INVESTIGATING`.

### Exit criteria

A judge can see **exactly which external integration broke and why** from SigNoz.

---

## Phase 5 - Bright Data evidence + scraper self-healing

Goal: satisfy the Bright Data requirement and supply repair context.

### Part A - Normal docs retrieval

Bright Data scrapes Pricing API documentation/changelog and returns structured evidence:

- provider version V2,
- old path `price`,
- new path `pricing.amount`,
- old path `currency`,
- new path `pricing.currency`,
- migration note.

This evidence is attached to the Port incident.

### Part B - Deliberately break docs HTML

Flip docs site from `docs-layout-v1` to `docs-layout-v2` while preserving the same human-visible content.

Expected initial result:

- Bright Data scraper returns missing/invalid required fields.
- data-quality validation fails.
- scraper failure appears in telemetry / factory evidence.

### Part C - Self-heal

- Invoke Bright Data Self-Healing.
- Wait for repair completion.
- Re-run extraction.
- Validate required migration fields.

### Output

A healthy normalized docs evidence object is available again without manually rewriting the scraper.

### Exit criteria

We visibly demonstrate:

**the external API changed, and the documentation website structure also changed; the data acquisition layer recovers itself.**

---

## Phase 6 - AVO-lite repair #2: schema migration

Goal: use both telemetry and live docs evidence to repair application code.

### Inspect

Claude receives:

- failing Pricing trace/log evidence from SigNoz,
- normalized Bright Data migration evidence,
- current provider adapter source,
- contract tests,
- current candidate lineage from Port.

### Plan

Expected hypothesis:

> Pricing V2 nested amount/currency under `pricing`. Update adapter to support V2 while preserving the API Guardian normalized Product Snapshot contract.

### Act

Claude patches only the Pricing adapter and associated tests.

### Evaluate

- unit tests pass,
- integration tests pass against Pricing V2,
- schema validation passes,
- SigNoz error rate returns under threshold,
- p95 remains under latency threshold,
- fitness score >= 90.

### Decision

- If FAIL: Port sends evaluation reason back to agent for one retry.
- If PASS: Port moves candidate to `READY_FOR_APPROVAL`.

### Human gate

Human approves repaired release.

### Output

`v2-pricing-compatible` released.

---

## Phase 7 - Dashboard, lineage, and audit polish

Goal: make the system understandable in seconds.

### Port must show

- application/service,
- three external dependencies,
- current released version,
- FactoryRun history,
- CandidateVersion lineage,
- before/after fitness scores,
- approval state,
- current incident,
- evaluation summaries.

### SigNoz must show

- trace waterfall before parallelization,
- trace waterfall after parallelization,
- p95 latency chart,
- error-rate spike during Pricing V2 break,
- provider-specific error span,
- recovery to healthy state,
- scraper/factory relevant events if practical.

### API Guardian UI must show

- three integration status cards,
- Product Snapshot,
- current p95 / error rate / score,
- last repair summary,
- current release status.

### Exit criteria

Someone unfamiliar with the project can understand state and history without reading terminal output.

---

## Phase 8 - Demo rehearsal and hardening

Goal: a deterministic 3-5 minute story.

### Demo sequence

#### Scene 1 - Show healthy product but poor performance

- API Guardian builds Product Snapshot correctly.
- SigNoz trace shows sequential providers.
- p95 fails target.
- Port candidate score is rejected.

#### Scene 2 - AVO-lite optimization

- Agent diagnoses serialization.
- Candidate parallelizes requests.
- Same tests and same mock delays.
- SigNoz proves p95 improvement.
- Port score improves.
- Human approves.

#### Scene 3 - External API breaks

- Flip Pricing API to V2.
- Product request fails.
- SigNoz highlights Pricing adapter error.
- Port opens remediation workflow.

#### Scene 4 - External docs also change

- Flip docs layout.
- Bright Data extraction breaks.
- Trigger Self-Healing.
- Extraction recovers with migration evidence.

#### Scene 5 - Software repair

- Agent uses SigNoz + Bright Data evidence.
- Pricing adapter repaired.
- Tests pass.
- SigNoz verifies error rate and p95.
- Port marks candidate ready.
- Human approves.

#### Final screen

Show:

- latency: ~2.7s -> ~1.1s,
- Pricing incident: FAILED -> RECOVERED,
- docs scraper: BROKEN -> SELF-HEALED,
- factory score improvement,
- release approved,
- complete run history.

---

## 9. Hackathon Requirement Coverage

### Agentic factory

Demonstrated by:

- context-aware planning,
- agent action on code,
- objective evaluation,
- retry/rejection loop,
- candidate lineage,
- human approval,
- repeatable runs.

### Port

Demonstrated by:

- Context Lake entities,
- service/dependency relationships,
- FactoryRun/Candidate/Evaluation/Release state,
- workflows,
- governance,
- approval,
- dashboard/audit history,
- agent-facing context.

### Bright Data

Demonstrated by:

- terminal-operated Scraper Studio flow,
- structured fresh provider docs/changelog data,
- scraper configuration captured in coding-agent project rules,
- deliberate docs DOM break,
- invalid extraction detection,
- Bright Data Self-Healing,
- successful post-repair extraction.

### SigNoz

Demonstrated by:

- traces,
- metrics,
- logs,
- provider/API instrumentation,
- latency regression,
- error spike,
- correlated root-cause evidence,
- alerts/evaluation feedback that changes the next agent action,
- before/after recovery verification.

### Human control

Demonstrated by:

- agent can plan and repair,
- objective checks determine eligibility,
- release still requires explicit Port approval.

### Repeatability

Demonstrated by deterministic mock provider modes and rerunnable FactoryRuns.

---

## 10. Definition of MVP Done

The MVP is done only when all of the following can be demonstrated without manual code editing during the demo:

- Three mock APIs are live and deterministic.
- Baseline app returns correct data sequentially.
- SigNoz proves latency failure.
- Agent-generated candidate parallelizes calls.
- SigNoz proves latency improvement.
- Pricing API can flip to a breaking V2 schema.
- SigNoz detects and localizes the failure.
- Bright Data extracts migration evidence.
- Docs HTML can change under the same logical content.
- Bright Data Self-Healing restores extraction.
- Agent repairs Pricing adapter using telemetry + docs evidence.
- Tests pass.
- SigNoz verifies recovery.
- Port records candidate lineage, score, and approval.
- Human approval gates release.
- Git history shows meaningful incremental work.
- README documents architecture, setup, demo modes, and recovery loop.
- 3-5 minute demo can be executed deterministically.

---

## 11. Team Operating Rules

- No person edits another person's owned directories without explicit handoff.
- Contract changes are discussed before implementation.
- Each phase ends with a runnable artifact, not an unfinished branch.
- Every handoff includes sample input and expected output.
- Use deterministic mock failures; do not depend on random timing or public API changes.
- Prefer one strong workflow over multiple partially working workflows.
- Prefer visible objective evidence over AI-generated narration.
- Never allow Claude to redesign the locked architecture unless the team explicitly decides to change it.
