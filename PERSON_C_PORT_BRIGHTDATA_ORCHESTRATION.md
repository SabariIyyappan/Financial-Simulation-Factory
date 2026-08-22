# Person C - Port, Bright Data, AVO-lite Orchestration, and Demo Control

## 0. Your Mission

You own the **factory control plane**.

Your job is to connect:

- Port context and governance,
- Bright Data live documentation evidence,
- SigNoz evaluation results from Person B,
- Claude/coding-agent actions on Person A's application,
- human approval and release lineage.

You are also responsible for making the full 3-5 minute demo deterministic and understandable.

You do **not** own product business logic or SigNoz instrumentation internals.

This file is written to be handed directly to Claude Code as your execution brief.

---

## 1. Ownership Boundaries

### You own

Suggested areas:

- `port/`
- `integrations/port/`
- `integrations/brightdata/`
- `provider-docs-site/`
- `orchestration/`
- `demo/`
- Port entity/workflow definitions,
- agent project rules related to Bright Data usage.

### You consume from Person A

- Product Snapshot endpoint,
- mock provider scenario controls,
- Pricing V1 and V2 schemas,
- candidate code/commit references,
- test result artifact.

### You consume from Person B

- evaluation objects,
- representative SigNoz trace IDs,
- score/decision,
- failure reason,
- optional alert/webhook event.

### You must not edit

- provider adapter implementation,
- mock API business logic,
- telemetry package internals,
- SigNoz dashboard definitions unless B explicitly hands them off.

---

## 2. Port Context Model

Keep the catalog small and directly useful to the factory.

### Blueprint/entity 1 - Service

Example: `api-guardian`.

Fields:

- repository,
- owner/team,
- current release,
- current health,
- current score.

Relationships:

- depends on three ExternalAPIs,
- has FactoryRuns,
- has Releases.

### Blueprint/entity 2 - ExternalAPI

Create three:

- Catalog API,
- Pricing API,
- Availability API.

Fields:

- base URL,
- current version,
- docs URL,
- owner/provider,
- health.

### Blueprint/entity 3 - FactoryRun

Fields:

- run ID,
- scenario,
- trigger reason,
- status,
- started/finished timestamps,
- current candidate,
- incident reason.

### Blueprint/entity 4 - CandidateVersion

Fields:

- candidate ID,
- parent release/candidate,
- hypothesis/plan,
- commit/reference,
- status,
- score,
- decision.

### Blueprint/entity 5 - Evaluation

Fields:

- score,
- correctness,
- p95 latency,
- error rate,
- failed provider,
- trace ID,
- decision,
- failure reason.

### Blueprint/entity 6 - Release

Fields:

- version,
- candidate ID,
- approved by,
- approval timestamp,
- score,
- release status.

Keep relationships obvious so Port can show lineage:

Service -> FactoryRun -> CandidateVersion -> Evaluation -> Release.

---

## 3. Candidate Lifecycle

Port is the single owner of lifecycle state.

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

Rules:

- Claude cannot mark its own candidate approved.
- Person A cannot directly release by changing a status flag.
- Person B only returns evidence/decision, not release state.
- Port moves candidate to `READY_FOR_APPROVAL` only after objective PASS.
- Human approval is required before `RELEASED`.

---

## 4. AVO-lite Workflow You Must Implement

## Step 1 - Inspect

Collect:

- service context from Port,
- current released version,
- provider dependencies,
- previous candidate/evaluation lineage,
- Person B's latest evaluation,
- Bright Data docs evidence when relevant.

## Step 2 - Plan

Have the coding agent produce a concise hypothesis and change plan.

The plan should answer:

- What is failing or suboptimal?
- What evidence supports the diagnosis?
- What smallest code change should improve it?
- What tests/metrics must remain healthy?

Store the plan on CandidateVersion.

## Step 3 - Act

Invoke Claude/coding agent to modify Person A's repair surface.

The agent receives only relevant context, not a giant unstructured prompt.

## Step 4 - Evaluate

Trigger Person A's test/evaluation run.

Collect Person B's objective evaluation.

## Step 5 - Decide

If FAIL:

- store score and reason,
- mark candidate REJECTED,
- optionally create one retry candidate using the new evidence.

If PASS:

- mark READY_FOR_APPROVAL.

## Step 6 - Human approval

Require explicit approval in Port.

## Step 7 - Release

Record Release entity and update Service current release/score.

This loop must be runnable for both:

- latency optimization,
- Pricing V2 schema repair.

---

## 5. Bright Data Responsibilities

Bright Data is not a random web scraper in this project. It provides **live provider-change evidence**.

Your owned public docs site should simulate a third-party provider developer portal for the Pricing API.

### Required docs content

The page must contain:

- current Pricing API version,
- migration note from V1 to V2,
- old fields `price` / `currency`,
- new paths `pricing.amount` / `pricing.currency`,
- brief migration guidance,
- changelog date/version.

### Bright Data structured output

Normalize extraction into an evidence object with:

- provider,
- version,
- breaking change summary,
- old field/path,
- new field/path,
- migration guidance,
- source timestamp,
- scraper health,
- self-heal attempted.

### Coding-agent rules

Store Bright Data usage requirements in the project rules file used by your coding agent, such as `CLAUDE.md` or equivalent.

Rules should state:

- Bright Data Scraper Studio is the approved provider-doc retrieval method,
- expected output schema,
- validation requirements,
- do not replace with raw fetch/Playwright just because scraper fails,
- on invalid/missing extraction, trigger Bright Data Self-Healing,
- revalidate before feeding evidence into repair workflow.

This is important for the hackathon judging criteria.

---

## 6. Docs Layout Failure You Must Build

Create two HTML structures with identical human-visible migration content.

### `docs-layout-v1`

The initial layout used when creating/configuring the scraper.

### `docs-layout-v2`

Change:

- container structure,
- class names/selectors,
- nesting/order,

while preserving the same visible content.

The same logical docs URL should ideally return different layouts based on a deterministic control mode.

### Failure expectation

When switched to layout V2:

- current extraction should fail required-field validation,
- the failure must be visible in terminal and/or factory evidence,
- then Bright Data Self-Healing is invoked,
- extraction is run again,
- evidence validates.

Do not manually edit the scraper during the demo.

---

## 7. Integration Contracts

## From Person A to you

You need:

- Pricing V1/V2 schema truth,
- provider control command/endpoint,
- Product Snapshot evaluation command/endpoint,
- candidate commit/reference,
- test result artifact,
- supported scenario names.

## From Person B to you

You need one evaluation object per candidate containing:

- run ID,
- candidate ID,
- scenario,
- score,
- PASS/FAIL,
- correctness status,
- p95 latency,
- error rate,
- failed provider,
- failure reason,
- representative trace ID.

## From you to Person A / Claude

For repairs you provide:

- Port service/dependency context,
- current candidate/release lineage,
- SigNoz failure evidence from B,
- Bright Data migration evidence if relevant,
- explicit objective that must improve,
- constraints that must not regress.

## From you to Person B

For each evaluation request provide:

- run ID,
- candidate ID,
- scenario,
- evaluation start/trigger,
- expected docs-health state if included in score.

---

## 8. Phase-by-Phase Work

## Phase C0 - Freeze Port and evidence contracts

### Inputs

- Master plan,
- Person A provider schemas/scenarios,
- Person B evaluation object.

### Tasks

- freeze Port blueprints,
- freeze lifecycle states,
- freeze Bright Data evidence shape,
- freeze demo scenario names,
- freeze candidate/run ID format,
- decide whether SigNoz failure reaches Port by webhook or explicit evaluator invocation.

### Outputs

- Port model reference,
- evidence contract,
- lifecycle rules.

### Handoff

Send A/B canonical run/candidate/scenario IDs.

---

## Phase C1 - Build Port workspace foundation

### Tasks

Create:

- Service entity,
- three ExternalAPI entities,
- FactoryRun,
- CandidateVersion,
- Evaluation,
- Release.

Create relationships.

Seed:

- API Guardian service,
- Catalog/Pricing/Availability dependencies.

### Expected output

A Port view where a judge can see API Guardian and its three dependencies.

### Exit criteria

Entities can be created/updated by workflow steps.

---

## Phase C2 - Build factory workflow skeleton

### Tasks

Create workflow stages:

- create FactoryRun,
- attach triggering evaluation/failure,
- create CandidateVersion,
- store plan,
- mark implemented,
- request evaluation,
- store evaluation,
- branch PASS/FAIL,
- human approval,
- release record.

### Input

Use mock evaluation objects until B's real evaluator is connected.

### Expected output

Both PASS and FAIL paths can be exercised independently.

---

## Phase C3 - Build Pricing provider docs site

### Input from A

Exact Pricing V1 and V2 schemas.

### Tasks

Create public provider docs/changelog page describing the real mock API migration.

Create deterministic layout V1/V2 control.

### Output

Public URL usable by Bright Data.

### Exit criteria

Humans can read the migration; layout can switch without changing semantic content.

---

## Phase C4 - Configure Bright Data extraction

### Tasks

- create Scraper Studio scraper for Pricing docs,
- define required structured fields,
- run from terminal/script path used by project,
- validate output,
- persist approved scraper usage rules in coding-agent project rules.

### Expected output

Normalized evidence object for Pricing V2 migration.

### Handoff to A

Share evidence object sample so A can confirm it accurately describes provider truth.

---

## Phase C5 - Integrate Person B evaluation into Port

### Input from B

Real evaluation object from baseline-v1.

### Tasks

- create Evaluation entity,
- link to FactoryRun/Candidate,
- update score/decision,
- if FAIL, open diagnosis/repair path,
- store representative trace ID and failure reason.

### Baseline expected result

- correctness PASS,
- latency FAIL,
- score below 90.

### Exit criteria

Port makes a decision using B's evidence rather than a hard-coded demo button.

---

## Phase C6 - Run AVO-lite latency optimization

### Inspect inputs

- Service context,
- current baseline candidate,
- B's FAIL evaluation,
- sequential trace evidence.

### Plan expectation

Agent identifies serialized independent provider calls.

### Act

Claude modifies A-owned application repair surface to parallelize calls.

### Evaluate

Trigger A's evaluation flow and B's measurement.

### Expected result

- p95 improves from ~2.7s to ~1.1-1.3s,
- correctness stays PASS,
- score >= 90.

### Port action

- READY_FOR_APPROVAL,
- human approves,
- create release.

### Demo asset

Port should show baseline candidate rejected and parallel candidate accepted.

---

## Phase C7 - Run external Pricing V2 incident

### Trigger

Use A's deterministic control to switch Pricing API to V2.

### Inputs from B

Expected failure evaluation:

- provider.pricing fails,
- error rate spikes,
- representative trace ID,
- candidate/release degraded.

### Port actions

- create new FactoryRun,
- set DETECTED -> INVESTIGATING,
- attach SigNoz evidence.

### Exit criteria

The factory is visibly responding to a real application failure.

---

## Phase C8 - Break docs scraper and self-heal

### Step 1

Run Bright Data extraction successfully on docs-layout-v1.

### Step 2

Switch same docs content to docs-layout-v2.

### Step 3

Run existing scraper.

Expected:

- required migration fields missing or invalid,
- evidence validation fails.

### Step 4

Invoke Bright Data Self-Healing.

### Step 5

Re-run extraction and validate.

### Expected output

Healthy migration evidence recovered without manual scraper rewrite.

### Port action

Attach recovered evidence to current FactoryRun.

### Demo proof

The judge sees a second independent recovery:

- app integration failure,
- scraper structure failure,
- scraper repairs itself,
- then software repair can proceed.

---

## Phase C9 - Run AVO-lite Pricing adapter repair

### Context sent to Claude

#### Port context

- affected service,
- affected dependency Pricing API,
- current release/candidate,
- candidate lineage.

#### SigNoz evidence from B

- failing provider: Pricing,
- trace ID,
- error reason,
- error rate.

#### Bright Data evidence

- API version V2,
- old fields,
- new fields,
- migration guidance.

#### Constraints

- preserve normalized Product Snapshot contract,
- preserve optimized latency,
- all tests must pass,
- do not modify mock provider to make app pass.

### Expected plan

Update Pricing adapter to V2 nested paths.

### Evaluate

Trigger A + B evaluation.

### Expected result

- tests PASS,
- error rate healthy,
- p95 healthy,
- score >= 90.

### Port action

READY_FOR_APPROVAL -> human approval -> RELEASED.

---

## Phase C10 - Port dashboards / scorecards / audit polish

### Views to create

#### Service overview

Show:

- API Guardian health,
- current release,
- current score,
- three dependencies.

#### Factory run history

Show:

- baseline latency run,
- parallel optimization run,
- Pricing V2 incident,
- repaired candidate.

#### Candidate lineage

Example:

- BASELINE - rejected - latency score low.
- PARALLEL - approved/released - score high.
- PRICING-V2-FAIL - degraded incident state.
- PRICING-V2-REPAIR - approved/released.

#### Approval

Have an unmistakable human approval action/gate.

### Exit criteria

Port visibly communicates context, decisions, history, and governance.

---

## Phase C11 - Final demo orchestration

Create one runbook with exact commands/clicks and rollback/reset operations.

### Scene 1 - Baseline latency

- reset provider to V1,
- run baseline sequential candidate,
- open SigNoz sequential trace,
- show Port FAIL evaluation.

### Scene 2 - Performance repair

- trigger AVO-lite candidate,
- evaluate parallel version,
- show SigNoz overlapping spans and p95 improvement,
- show score increase,
- approve in Port.

### Scene 3 - Breaking API

- switch Pricing to V2,
- run Product Snapshot,
- show SigNoz Pricing failure,
- Port opens remediation.

### Scene 4 - Docs layout break

- show Bright Data successful extraction,
- switch docs layout,
- show invalid extraction,
- trigger self-heal,
- show recovered structured migration evidence.

### Scene 5 - Software repair

- agent gets Port + SigNoz + Bright Data context,
- candidate repairs Pricing adapter,
- tests/evaluation pass,
- SigNoz shows recovery,
- Port approval/release.

### Final summary view

Show at once or in fast sequence:

- p95 ~2.7s -> ~1.1s,
- Pricing error -> recovered,
- scraper broken -> self-healed,
- objective score increased,
- two candidate approvals/releases,
- audit trail intact.

---

## 9. Demo Reliability Rules

- Every external failure must be deterministic.
- Have reset commands for provider mode and docs layout.
- Have exact saved SigNoz views from B.
- Have Port seeded/cleaned before recording.
- Do not rely on an unpredictable real public API changing.
- Do not let Claude take unlimited iterations during the recorded demo; constrain to one planned repair and at most one retry.
- If live agent editing is too slow/unreliable, record the agent action as part of the factory run but keep the workflow real and the candidate commit auditable.
- The factory must never fake objective PASS; B's evaluator remains authoritative.

---

## 10. Your Required Inputs From Teammates

## From Person A

- provider schemas,
- public/local provider URLs,
- Pricing V1/V2 switch command,
- Product Snapshot run/evaluation command,
- test result format,
- candidate commit/reference,
- reset behavior.

## From Person B

- evaluation object schema,
- baseline latency FAIL evidence,
- optimized latency PASS evidence,
- Pricing V2 failure evidence,
- repaired candidate PASS evidence,
- representative trace IDs,
- alert webhook contract if used.

---

## 11. What You Must Send Teammates

## To Person A

For repair cycles:

- run ID,
- candidate ID,
- lifecycle state,
- SigNoz evidence from B,
- Bright Data docs evidence,
- explicit repair objective/constraints.

## To Person B

For evaluation cycles:

- run ID,
- candidate ID,
- scenario,
- evaluation trigger/start,
- docs-health state if included in score.

For alerts:

- Port destination/workflow contract.

---

## 12. Definition of Done for Person C

Your work is complete when:

- Port models context/dependencies/candidates/evaluations/releases,
- lifecycle and human approval work,
- Bright Data returns structured Pricing docs evidence,
- docs layout can intentionally break scraper extraction,
- Bright Data Self-Healing restores extraction,
- Port consumes B's evaluation result,
- AVO-lite latency repair can move from FAIL to approval,
- Pricing V2 failure creates a new remediation run,
- Claude receives both SigNoz and Bright Data evidence,
- repaired candidate is objectively evaluated and gated,
- final demo runbook is deterministic,
- Port shows meaningful history rather than decorative metadata.

---

## 13. Claude Guardrails for Your Branch

When giving this document to Claude Code:

- do not redesign the locked AVO-lite architecture,
- do not edit Person A/B owned code,
- keep Port entity model minimal,
- use Bright Data rather than replacing it with raw scraping,
- preserve the deliberate docs-layout failure for the self-heal demo,
- never mark a candidate PASS without Person B's evaluation,
- never release without human approval,
- keep repair loops bounded and demo-safe,
- stop at each phase exit criteria before continuing.
