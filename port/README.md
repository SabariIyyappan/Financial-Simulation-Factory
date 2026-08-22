# Port integration

**Drafted by Person A as a handoff to Person C.** Port is Person C's surface — this is a
starting point, not a claim on ownership. Adapt or replace anything here.

It exists because the entity model was already fully specified in
`PERSON_C_PORT_BRIGHTDATA_ORCHESTRATION.md` §2–3, so the blueprints and lifecycle guards
were mechanical to write. Nothing here touches a Port account — that part needs C's
credentials and judgment.

## What's here

```
port/blueprints/       Six blueprints, numbered in dependency order
port/scorecards/       Release-readiness scorecard (see "risk factors" below)
integrations/port/     TypeScript client + lifecycle state machine, 11 passing tests
scripts/port-bootstrap.ts   Creates all of the above in a workspace, one command
```

## Setup

1. Port → Settings → Credentials → create an API key.
2. Put the values in `.env.local` at the repo root:
   ```
   PORT_CLIENT_ID=...
   PORT_CLIENT_SECRET=...
   ```
3. Run:
   ```bash
   npm run port:bootstrap
   ```

That creates the six blueprints, the scorecard, and seeds the `api-guardian` Service plus
the three ExternalAPI entities with the dependency relations wired. Safe to re-run —
existing blueprints are skipped, entities are upserted.

## Entity model

Lineage matches the plan: `Service → FactoryRun → CandidateVersion → Evaluation → Release`

| Blueprint | Purpose |
|---|---|
| `externalApi` | Catalog / Pricing / Availability. Carries `currentVersion` and `health` — flip Pricing to `v2` / `breaking` during the incident and the catalog shows it. |
| `service` | `api-guardian`, with `dependsOn` relations to all three providers, plus current release and score. |
| `factoryRun` | One build-or-repair run. Scenario, trigger reason, retry count. |
| `candidateVersion` | One attempt. Carries the nine-state lifecycle, hypothesis, score, decision, and a self-relation to its parent candidate so lineage renders as a chain. |
| `evaluation` | Person B's evaluator output, stored verbatim — including `representativeTraceId`, which links a decision back to the SigNoz trace it was based on. |
| `release` | Version, `approvedBy`, `approvedAt`. |

## Governance is enforced in code, not just documented

`integrations/port/src/lifecycle.ts` implements the §3 rules as guards that throw:

- **Illegal transitions are rejected.** A candidate cannot skip `EVALUATING` to reach
  approval, and `RELEASED` is terminal.
- **A passing candidate goes to `READY_FOR_APPROVAL`, never `APPROVED`.** Passing the
  fitness gate makes a candidate *eligible* for a human to approve. It cannot approve
  itself. This is the hackathon brief's "keep humans in control where it matters", made
  mechanical.
- **`approve()` requires a named approver.** Releases must be attributable.
- **`release()` refuses unless the candidate is already `APPROVED`.**

All four are covered by tests: `npm test -w @api-guardian/port` (11 passing). Worth
running on camera if a judge asks how the human gate is enforced — the answer is a test,
not a promise.

## Usage from the orchestrator

```ts
import { PortClient, FactoryLifecycle } from "@api-guardian/port";

const lifecycle = new FactoryLifecycle(PortClient.fromEnv());

await lifecycle.startRun({
  runId: "RUN-001",
  serviceId: "api-guardian",
  scenario: "baseline-v1",
  triggerReason: "manual",
  status: "running",
  startedAt: new Date().toISOString(),
});

await lifecycle.upsertCandidate({
  candidateId: "CANDIDATE-PARALLEL",
  runId: "RUN-001",
  parentCandidateId: "BASELINE",
  hypothesis: "Provider calls are independent but serialized; run them concurrently.",
  status: "IMPLEMENTED",
});

await lifecycle.transition("CANDIDATE-PARALLEL", "EVALUATING");

// Person B's evaluator response drops straight in — EvaluationOutput matches Contract D.
const result = await lifecycle.recordEvaluation(evaluatorResponse);
// result.movedTo === "READY_FOR_APPROVAL" on PASS, "REJECTED" on FAIL

// Human step. Nothing above can do this.
await lifecycle.approve("CANDIDATE-PARALLEL", "kenil");
await lifecycle.release("CANDIDATE-PARALLEL", "v1-optimized", "kenil", 92);
```

## On "risk factors"

The Best Port Integration criterion asks for *"goals, technical choices, risk factors,
and cataloged services."* The plan's entity model covers goals, choices, and services,
but nothing modelled **risk** — so `port/scorecards/release-readiness.json` adds it:
Bronze (objectively evaluated, not rejected), Silver (PASS, score ≥ 90), Gold (human
approved). A judge scanning the workspace sees at a glance which candidates are safe.

## Not done — needs C's account or judgment

- Importing this into an actual workspace and confirming it renders well.
- The `learn-tool` equivalent as a real Port **Action**, so a run can be triggered *from*
  Port rather than only reported into it. This is what makes it a re-runnable workflow
  instead of an audit log, and the brief grades "whether it can run again".
- Connecting a coding agent to Port over **MCP** — called out in the brief and worth more
  in the demo than any REST call.
- The SigNoz alert → Port remediation webhook (Phase C7/C8).
