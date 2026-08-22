# Person B - SigNoz, OpenTelemetry, Alerts, and Objective Fitness

## 0. Your Mission

You own the **measurement and truth layer**.

Your job is to make the factory objectively answer:

- What is slow?
- What failed?
- Which provider caused it?
- Did the candidate improve the system?
- Is the candidate safe to release?

You deliver SigNoz traces, metrics, logs, dashboards, alert/evaluation logic, and the machine-readable candidate fitness result consumed by Person C's Port workflow.

You do **not** own application business logic, provider adapters, Port workflows, or Bright Data scraping.

This file is designed to be handed directly to Claude Code as your implementation brief.

---

## 1. Ownership Boundaries

### You own

Suggested areas:

- `packages/telemetry/`
- `observability/signoz/`
- `observability/dashboards/`
- `observability/evaluator/`
- telemetry/evaluation docs in your area.

### You consume from Person A

- Product Snapshot endpoint,
- provider endpoints,
- test result artifact,
- evaluation start/end times,
- factory/candidate/scenario IDs propagated through app.

### You consume from Person C

- canonical FactoryRun/Candidate IDs,
- Port callback/input format for evaluation results,
- lifecycle expectation for PASS/FAIL,
- optional remediation webhook destination if used.

### You do not edit

- provider business logic,
- mock API schemas,
- Port blueprints/workflows,
- Bright Data scraper logic.

---

## 2. Observability Model

Use OpenTelemetry as the common instrumentation model and SigNoz as the source of truth for runtime evidence.

The demo must show three telemetry types:

1. **Traces** - where time was spent and where failure occurred.
2. **Metrics** - p95 latency, error rate, request count, recovery indicators.
3. **Logs** - structured failure context correlated by trace/run/candidate.

---

## 3. Required Trace Structure

One Product Snapshot request should look like:

`api_guardian.product_snapshot`

with child spans:

- `provider.catalog`
- `provider.pricing`
- `provider.availability`

Optional useful child spans if they remain simple:

- `snapshot.normalize`
- `snapshot.validate`

### Sequential baseline visual

Provider spans must appear one after another.

Expected rough timing:

- Catalog 0.0-0.7s
- Pricing 0.7-1.6s
- Availability 1.6-2.7s

### Parallel candidate visual

Provider spans should start at approximately the same time.

Expected rough timing:

- Catalog 0.0-0.7s
- Pricing 0.0-0.9s
- Availability 0.0-1.1s

This before/after waterfall is one of the main demo visuals.

---

## 4. Required Attributes and Correlation

Every relevant span/log/metric evaluation must be attributable to:

- factory run ID,
- candidate ID,
- scenario,
- release version if present.

Required span attributes:

- `factory.run_id`
- `candidate.id`
- `demo.scenario`
- `provider.name`
- `provider.version`
- `provider.status`

Required structured log fields:

- timestamp,
- severity,
- trace ID,
- span ID,
- factory run ID,
- candidate ID,
- scenario,
- stage,
- provider,
- concise error code/message.

For Pricing V2 failure, a judge should be able to go:

Product Snapshot trace -> failing `provider.pricing` span -> correlated error log.

---

## 5. Metrics You Must Provide

Keep the metric set small and useful.

### Application metrics

- Product Snapshot request count.
- Product Snapshot error count / error rate.
- Product Snapshot latency histogram suitable for p50/p95.

### Provider metrics

- provider request count by provider.
- provider error count by provider.
- provider latency by provider.

### Factory/demo metrics

At minimum derive or expose:

- candidate p95 latency,
- candidate error rate,
- evaluation pass/fail,
- recovery time if easy to calculate.

Optional if straightforward:

- factory retries total,
- scraper repair count supplied by Person C as an event/metric.

Do not spend time building a large metrics taxonomy.

---

## 6. Dashboard Requirements

Build one primary SigNoz dashboard that tells the whole story.

### Panel 1 - Product Snapshot p95 latency

Should visibly show:

- baseline around 2.7s,
- optimized around 1.1-1.3s.

### Panel 2 - Error rate

Should visibly show:

- near-zero errors in healthy states,
- clear spike when Pricing switches to V2,
- return to near-zero after adapter repair.

### Panel 3 - Provider latency / health

Show Catalog, Pricing, Availability separately.

Purpose:

- demonstrate external calls remain roughly same latency,
- prove speedup came from orchestration, not fake faster mock APIs.

### Panel 4 - Candidate / scenario filtering

Make it easy to filter or group by:

- candidate ID,
- demo scenario.

### Trace view

The main dashboard can link/lead into traces. The actual before/after waterfall should be shown in trace explorer during the demo.

---

## 7. Alert / Failure Feedback Requirements

SigNoz must do more than display charts. Its evidence must influence the factory.

### Latency failure condition

For the baseline evaluation window:

- p95 > 2.2 seconds -> FAIL.

Preferred release target:

- p95 <= 1.6 seconds.

### Error condition

For the Pricing V2 incident:

- error rate > 1% during evaluation or incident window -> FAIL.

Because the demo intentionally creates a strong failure, the observed error rate may be much higher.

### Provider-specific failure evidence

The evaluation should identify `pricing` as the failing provider when its spans/logs contain adapter/schema errors.

### Optional real-time alert

If reliable in the hackathon environment, configure SigNoz webhook alert to Person C's Port remediation endpoint/workflow.

If webhook wiring becomes risky, do not fake it. Use a deterministic evaluation/query step initiated by Port that reads the same SigNoz evidence.

The essential judging proof is:

**SigNoz evidence changes the next factory decision.**

---

## 8. Candidate Fitness Function

You own the objective score calculation.

### Inputs from Person A

- total tests,
- passed tests,
- failed tests,
- schema valid yes/no,
- provider truth comparison pass/fail,
- evaluation window start/end,
- candidate/run/scenario IDs.

### Inputs from SigNoz

- p50 Product Snapshot latency,
- p95 Product Snapshot latency,
- Product Snapshot error rate,
- provider error breakdown,
- trace completeness,
- representative failing trace ID if present.

### Optional input from Person C

- Bright Data docs extraction health yes/no.

If C provides it, include it in the score. If not available, C can add the final data-health points before storing evaluation in Port. Agree this in Phase 0.

### Score

#### Correctness - 40

- normalized schema valid: 20.
- test suite passes: 10.
- provider truth comparison passes: 10.

Hard gate: any correctness failure prevents release.

#### Reliability - 20

- error rate under 1%: 10.
- no provider adapter exceptions during verification: 10.

#### Latency - 20

- p95 <= 1.6s: 20.
- p95 >1.6s and <=2.2s: 10.
- p95 >2.2s: 0.

#### Docs/data health - 10

- supplied by C or computed jointly.

#### Observability completeness - 10

- expected spans present: 5.
- run/candidate correlation present: 5.

### Candidate decision

Output PASS only when:

- correctness hard gate passes,
- reliability hard gate passes,
- total score >= 90.

---

## 9. Evaluation Output Contract to Person C

For each candidate produce one normalized object/report containing:

- `factory_run_id`
- `candidate_id`
- `scenario`
- `score`
- `decision`: PASS or FAIL
- `correctness_status`
- `tests_passed`
- `tests_failed`
- `p50_latency_ms`
- `p95_latency_ms`
- `error_rate`
- `failed_provider`
- `failure_reason`
- `representative_trace_id`
- `evaluation_window_start`
- `evaluation_window_end`
- `observability_complete`

The format can be JSON internally, but this plan is not prescribing code.

### Failure reason examples

Latency baseline:

> Product Snapshot correctness passed, but p95 latency exceeded 2.2s. Provider spans were healthy and individually stable; trace waterfall shows independent provider calls serialized.

Pricing V2 incident:

> Product Snapshot reliability failed. Errors are concentrated in provider.pricing. Representative trace shows Pricing adapter schema/field failure after provider version changed to v2.

These reasons should be concise and machine-consumable enough to pass to the coding agent.

---

## 10. Phase-by-Phase Work

## Phase B0 - Freeze telemetry conventions

### Inputs

- Master plan,
- Person A endpoints and provider delays,
- Person C run/candidate lifecycle IDs.

### Tasks

- freeze span names,
- freeze required attributes,
- freeze log schema,
- freeze evaluator input/output,
- freeze latency thresholds.

### Outputs

Telemetry contract delivered to Person A.

Evaluation output example delivered to Person C.

### Exit criteria

A and C can integrate without knowing SigNoz internals.

---

## Phase B1 - SigNoz / OTel foundation

### Tasks

- establish SigNoz environment,
- create telemetry helper package,
- verify traces reach SigNoz,
- verify logs are correlated,
- verify latency histogram / metrics are queryable.

### Initial test

Use a minimal synthetic operation if Person A app is not ready.

### Output

Screenshot/query proof that traces, metrics, and logs arrive.

### Handoff to Person A

Give:

- package/helper interface,
- environment variables,
- exact fields A must pass.

---

## Phase B2 - Integrate baseline Product Snapshot

### Input from Person A

Runnable baseline endpoint with telemetry hooks integrated.

### Tasks

- run `baseline-v1` repeatedly enough to create a small evaluation window,
- verify sequential trace shape,
- verify provider delays are visible,
- verify p95 is above failure threshold,
- verify correctness remains outside your telemetry responsibility and comes from A's tests.

### Expected output

- p95 around 2.7+ seconds,
- zero/near-zero errors,
- trace spans serialized.

### Exit criteria

The system can objectively say: "correct, but too slow."

---

## Phase B3 - Build first candidate evaluation

### Input from A

- candidate/run/scenario IDs,
- test result artifact,
- evaluation window.

### Tasks

Compute candidate score.

Expected baseline score:

below 90 because latency gets 0 points.

### Output to C

FAIL evaluation with failure reason that points to serialized calls.

### Exit criteria

Port can consume your evaluation and choose repair rather than release.

---

## Phase B4 - Verify parallel candidate

### Input from A/C

Candidate `CANDIDATE-PARALLEL`, same provider delays, same functional test data.

### Tasks

- run equivalent evaluation load,
- verify provider spans overlap,
- verify provider-specific latency is unchanged,
- verify root Product Snapshot latency drops near slowest provider,
- calculate score.

### Expected output

- p95 roughly 1.1-1.3s,
- error rate near zero,
- correctness PASS from A,
- score >= 90,
- decision PASS.

### Output to C

PASS evaluation + representative improved trace ID.

### Demo asset

Save exact trace filters/links for baseline vs parallel views.

---

## Phase B5 - Detect Pricing V2 break

### Input from A

Pricing provider flipped to V2, existing adapter still V1.

### Tasks

- generate several Product Snapshot attempts,
- verify error rate spike,
- verify failing Pricing child span,
- verify structured log contains schema/field problem,
- generate incident evaluation.

### Expected output

- failed provider: `pricing`,
- correctness/reliability FAIL,
- representative trace ID,
- clear error reason.

### Output to C

Failure evaluation that Port can attach to remediation run.

### Output to A

Representative trace/log details for repair context.

---

## Phase B6 - Verify Pricing V2 repaired candidate

### Input from A

Repaired adapter candidate.

### Tasks

- run same Pricing V2 mode,
- verify error rate returns under threshold,
- verify Pricing spans succeed,
- verify p95 stays within optimized range,
- calculate final score.

### Expected output

PASS, score >= 90.

### Output to C

Final evaluation object.

### Exit criteria

Port can move candidate to human approval using objective evidence.

---

## Phase B7 - Build demo dashboard and saved views

### Tasks

Prepare reliable views for:

1. baseline p95,
2. optimized p95,
3. sequential trace,
4. parallel trace,
5. Pricing V2 error spike,
6. failing Pricing trace/log,
7. recovery after repair.

### Important

Do not depend on manually constructing complex queries live.

Have saved filters/dashboards ready.

### Exit criteria

A teammate can open the correct evidence in one or two clicks.

---

## Phase B8 - Alert/remediation wiring

### Preferred flow

SigNoz alert/evaluation -> Port remediation workflow.

### If using webhook

Coordinate with C on:

- destination,
- expected payload,
- run/candidate mapping,
- deduplication.

### If not using webhook

Provide a deterministic evaluation endpoint/query that C invokes after a run.

### Non-negotiable output

SigNoz evidence must be machine-consumed by the factory; it cannot be dashboard-only.

---

## 11. Your Required Inputs From Teammates

## From Person A

For every evaluation:

- request endpoint,
- run ID,
- candidate ID,
- scenario,
- test result artifact,
- evaluation timestamps.

For Pricing incident:

- confirmation V2 is active,
- expected provider truth.

## From Person C

You need:

- canonical lifecycle IDs,
- evaluation callback/input destination,
- whether docs-health score is supplied separately,
- whether real alert webhook is required.

---

## 12. What You Must Send Teammates

## To Person A

- telemetry helper interface,
- required context fields,
- OTel setup/config,
- representative trace/log details after failures,
- evaluation timing protocol.

## To Person C

For each candidate:

- normalized evaluation object,
- PASS/FAIL,
- score,
- failure reason,
- representative trace ID,
- key before/after metrics.

For alert integration:

- payload format or evaluator invocation contract.

---

## 13. Definition of Done for Person B

Your work is complete when:

- traces, metrics, and logs are active in SigNoz,
- run/candidate/scenario IDs correlate across signals,
- sequential trace is visibly sequential,
- parallel trace is visibly parallel,
- p95 improvement is objectively measured,
- Pricing V2 failure is localized to Pricing,
- error spike and recovery are visible,
- evaluator emits deterministic PASS/FAIL + score,
- Person C can consume the evaluation,
- dashboard views are prebuilt for demo,
- observability influences the factory's next action.

---

## 14. Claude Guardrails for Your Branch

When handing this to Claude Code:

- do not alter Person A's business logic to improve metrics,
- do not change provider delays,
- do not alter Port workflow state,
- keep metric set minimal,
- optimize for a reliable demo rather than exhaustive observability,
- treat telemetry as objective evidence, not decorative graphs,
- stop at each phase exit criteria before moving forward.
