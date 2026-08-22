# Zero Downtime Hackathon — MVP Build Plan

## Project

**Name:** Financial Simulation Factory  
**Demo App:** Portfolio Stress Lab  
**Team Size:** 2 people  
**Primary Coding Tool:** Claude Code (Cursor can also use this file as project context)  
**Goal:** Build the smallest complete system that clearly demonstrates the hackathon’s core idea: an autonomous software factory that can build, evaluate, repair, and evolve a working application.

---

# 1. One-Sentence Pitch

A user describes a portfolio stress-test experiment in plain English, and our AVO-lite software factory builds a working interactive simulator, verifies it, repairs failed candidates, uses live web data through Bright Data, observes everything in SigNoz, and requires human approval in Port before release.

---

# 2. What We Are Actually Building

We are **not** building a general-purpose app generator.

We are building a constrained factory that creates and modifies one type of application:

> **Interactive portfolio stress-testing simulators.**

The generated simulator should let a user change a small number of inputs and immediately see the result.

### MVP simulator inputs

- Starting capital
- Tech allocation
- Bond/cash allocation
- Crash severity
- Rebalancing frequency
- Dip-buy threshold
- Dip-buy percentage

### MVP simulator outputs

- Portfolio value over time
- Maximum drawdown
- Final portfolio value
- Recovery time
- Number of rebalance/dip-buy actions

The app should be visually simple and easy to understand in less than 20 seconds.

---

# 3. Core User Story

### Initial build request

The user gives the factory a request such as:

> “Build a simulator that shows how a tech-heavy portfolio behaves during a market crash, with adjustable crash severity, rebalancing, and dip-buying.”

The factory should:

1. Store the request in Port.
2. Create a structured implementation plan.
3. Give the plan and context to Claude Code.
4. Build or modify the simulator.
5. Run deterministic tests.
6. Run the simulator and collect telemetry in SigNoz.
7. Score the candidate.
8. If it fails, diagnose and repair it.
9. If it passes, wait for human approval in Port.
10. Mark the candidate as released.

### Change request

After the simulator is working, demonstrate a second request:

> “Add a feature that invests 25% of remaining cash every time the market falls another 10%.”

That becomes a new factory run.

The point of the demo is to show that the factory can **evolve the software**, not just create it once.

---

# 4. Locked AVO-Lite Architecture

We use AVO as an architectural inspiration only. We are not reproducing NVIDIA AVO.

The control loop is:

**Inspect → Plan → Act → Evaluate → Diagnose → Repair → Retry → Approve → Release**

### Architecture roles

- **Port** = context, factory state, workflow, candidate history, approvals
- **Claude Code** = main implementation agent
- **Bright Data** = live/changing web-data source + scraper self-healing
- **SigNoz** = telemetry + objective feedback
- **Tests** = deterministic correctness gates
- **Human** = final release approval

### Simple architecture

```text
User brief / change request
          |
          v
        PORT
  context + workflow
          |
          v
     Claude Code
          |
          v
 Build / modify simulator
          |
          +-------------------+
          |                   |
          v                   v
      Tests              Bright Data
          |            live market/event data
          |                   |
          +---------+---------+
                    |
                    v
                  SigNoz
          traces + logs + metrics
                    |
                    v
               EVALUATE
              /        \
           PASS        FAIL
            |            |
            v            v
       Port approval   Diagnose
            |            |
            v            v
         Release      Repair + Retry
```

---

# 5. What Makes This AVO-Lite

We only need five AVO-style behaviors.

## 5.1 Persistent context

Port stores:

- Current app
- Current request
- Current candidate
- Previous candidate
- Latest evaluation result
- Release status

## 5.2 Candidate loop

Each factory run produces a candidate version.

Example:

- Candidate V1 — failed correctness check
- Candidate V2 — tests pass but latency too high
- Candidate V3 — tests pass and telemetry healthy

## 5.3 Objective evaluation

The agent does not decide that its own work is good.

The candidate passes only when measurable gates pass.

### MVP gates

- Required feature exists
- Simulator produces valid numeric results
- Deterministic simulation tests pass
- Bright Data result matches expected schema
- Simulator API/page loads successfully
- No critical runtime errors in SigNoz
- Latency below a simple threshold

## 5.4 Repair loop

If a candidate fails:

1. Collect failing test output and/or SigNoz evidence.
2. Feed the evidence back to Claude Code.
3. Ask Claude Code to diagnose and repair.
4. Re-run the same evaluation.

Limit to a small number of retries in the MVP.

## 5.5 Human release gate

Even after a candidate passes, Port should show:

**Ready for approval**

A human clicks approve before the candidate is considered released.

---

# 6. Port MVP

Port is the factory control center. Do not build a huge catalog.

## Required entities

### SimulationApp

Represents the generated simulator.

Fields:

- Name
- Status
- Current version
- Last successful factory run
- Latest candidate score/status

### FactoryRun

Represents one build or change request.

Fields:

- Request
- Status
- Current phase
- Candidate version
- Evaluation result
- Retry count
- Approval status

### DataSource

Represents the Bright Data source.

Fields:

- Name
- Collector ID
- Health
- Last successful scrape
- Last self-heal status

That is enough for the MVP.

## Required Port workflow

One workflow only:

**Build / Change Simulation**

Stages:

1. Receive request
2. Mark run as planning
3. Invoke/hand context to Claude Code
4. Mark run as building
5. Run verification
6. Evaluate result
7. If failed → repair and retry
8. If passed → waiting for approval
9. Human approves
10. Mark released

## Port judge demo

During the demo, visibly show:

1. The request stored in Port.
2. The current FactoryRun moving through stages.
3. Candidate status / evaluation result.
4. A failed attempt or retry.
5. Final **human approval**.
6. Final released state.

That is the Port story. Do not spend time building extra dashboards unless the core loop is already working.

---

# 7. Bright Data MVP

Bright Data must be a real dependency of the simulator, not a decorative integration.

## Data use case

Create one external page that represents **Market Context**.

The page can contain structured values such as:

- Current risk regime
- Suggested tech shock
- Suggested bond response
- Volatility level
- A headline/event label

The simulator should expose a button/preset such as:

**Load Current Market Scenario**

Bright Data scrapes the page and returns structured JSON.

The simulator uses that result to prefill its stress-test inputs.

Example conceptual output:

```text
Current Market Scenario
- Tech shock: -30%
- Bond response: +6%
- Volatility: High
- Regime: Risk-off
```

The important requirement is that the Bright Data output **changes what the simulator does**.

## Terminal workflow

The project must allow Claude Code / the team to:

- Trigger the scraper from the terminal
- Validate structured output
- Detect missing/invalid fields
- Trigger Bright Data self-healing
- Re-run the same scraper

## Version-controlled scraper rules

Document Bright Data usage in the coding-agent project rules (`CLAUDE.md` and optionally Cursor rules).

The rules should state:

- Which Bright Data collector to use
- Expected output fields
- How to validate the result
- What constitutes scraper failure
- That the existing Bright Data collector should be healed rather than replaced with an unrelated local scraper

## Bright Data judge demo

The Bright Data demo must be extremely explicit.

### Demo sequence

1. Show the terminal successfully retrieving structured market data.
2. Show the simulator consuming that data.
3. Change the external page HTML so the scraper fails or returns an invalid field.
4. Show validation failure.
5. Show Bright Data Self-Healing repairing the scraper.
6. Run the same scraper again.
7. Show valid structured output again.
8. Refresh/re-run the simulator and show the market preset working again.

This is the sponsor’s “changing web → self-healing scraper” story.

---

# 8. SigNoz MVP

SigNoz is the evidence layer for both the factory and the generated simulator.

Do not build too many metrics. Build a few clear signals that judges can understand immediately.

## Required traces

### Factory trace

A factory run should be traceable through major stages such as:

- factory.run
- plan
- build
- scrape.market-context
- test
- evaluate
- repair (when needed)
- release

### Simulation trace

A simulator run should include:

- simulation.run
- load.market-context
- compute.portfolio
- compute.metrics

## Required metrics

Keep it small:

- factory_runs_total
- factory_retries_total
- factory_failures_total
- scraper_failures_total
- scraper_repairs_total
- simulation_runs_total
- simulation_error_rate
- simulation_latency

## Required logs

Every important log should include identifiers such as:

- factory_run_id
- candidate_version
- stage
- retry_number

## Required alert/feedback behavior

At least one SigNoz-detected failure must cause action.

Simplest MVP:

- scraper or simulation error exceeds threshold
- SigNoz alert/webhook is emitted
- Port marks the FactoryRun as requiring remediation
- repair/retry flow runs

Even if the wiring is simple, the judge must clearly see:

**SigNoz detected something → the factory reacted.**

## SigNoz judge demo

Show:

1. A trace for a successful simulator/factory run.
2. A failure appearing in SigNoz.
3. The corresponding retry/repair event.
4. The recovered healthy run afterward.
5. One dashboard containing the small set of useful metrics above.

Avoid spending time making a large observability dashboard.

---

# 9. The One Software Failure We Intentionally Demonstrate

We need one deterministic candidate failure to prove AVO-lite repair.

Do not rely on Claude randomly making a mistake.

Create a controlled failing requirement/test scenario.

Recommended demo:

### Change request

> “Add dip-buying: invest 25% of remaining cash every additional 10% market drop.”

The initial implementation should fail a deterministic correctness test or validation condition.

Example type of failure:

- Dip-buy rule triggers at the wrong threshold
- Cash balance becomes negative
- Dip-buy triggers twice for the same threshold

Then:

```text
Candidate fails
    ↓
Tests / SigNoz show evidence
    ↓
AVO-lite evaluation rejects candidate
    ↓
Claude Code receives failure context
    ↓
Claude repairs implementation
    ↓
Tests pass
    ↓
SigNoz healthy
    ↓
Port waits for approval
```

This is the clearest proof that we built an autonomous repair loop rather than a scripted generator.

---

# 10. The Two Recovery Loops We Must Demo

The entire project should revolve around two easy-to-explain loops.

## Loop A — Software repair

```text
New requirement
→ Claude builds candidate
→ candidate fails test/evaluation
→ SigNoz/tests expose failure
→ AVO-lite rejects candidate
→ Claude repairs
→ verification passes
→ Port approval
```

## Loop B — Web-data repair

```text
External market page changes
→ Bright Data extraction becomes invalid
→ validation/SigNoz detect failure
→ Bright Data Self-Healing
→ same scraper works again
→ simulator gets valid data again
```

If both loops work live, the architecture story is strong enough.

---

# 11. MVP Repository Structure

Keep the project in one repository.

Recommended logical areas:

```text
/app
  Financial simulator UI and API

/factory
  Factory orchestration helpers
  Candidate evaluation
  Build/change request state

/integrations/port
  Port interactions and workflow integration

/integrations/brightdata
  Scraper trigger, validation, healing workflow

/observability
  OpenTelemetry/SigNoz setup and helpers

/tests
  Simulation correctness tests
  Factory acceptance tests

/demo-source
  Controlled external market-context webpage

CLAUDE.md
README.md
build_plan.md
```

Do not create unnecessary services or microservices for the MVP.

---

# 12. Team Split

## Person 1 — Factory / Port / Claude Code

Primary ownership:

- Repository setup
- Simulator generation/change flow
- Port entities and workflow
- Factory state
- Candidate evaluation
- Claude Code repair loop
- Human approval/release state
- Final demo orchestration

## Person 2 — Bright Data / SigNoz / Demo Environment

Primary ownership:

- External market-context demo page
- Bright Data collector
- Terminal scraper workflow
- Self-Healing demo
- OpenTelemetry instrumentation
- SigNoz dashboard
- SigNoz failure alert/webhook
- Failure injection controls

## Shared

Both people should jointly own:

- Simulator correctness
- End-to-end integration
- Demo rehearsal
- README
- Video recording

Avoid waiting for one another. Each person should build against simple interface contracts and integrate as soon as the first working slice exists.

---

# 13. Phase-by-Phase Build Order

## Phase 1 — Build the simulator first

Goal: Have a standalone Portfolio Stress Lab that works before sponsor integrations.

Build:

- Simple simulator UI
- Core deterministic simulation logic
- Inputs and outputs listed earlier
- One graph
- Numerical summary metrics
- Deterministic tests

Acceptance:

- User can change parameters and run simulation
- Results change correctly
- Tests pass
- Judges can understand the app immediately

Do not build factory logic until this works.

---

## Phase 2 — Build the basic factory shell

Goal: Turn the working simulator into something the factory can modify.

Build:

- FactoryRun concept
- Request input
- Candidate version/status
- Basic stages: plan, build, verify, approval, release
- Claude Code instructions for modifying the simulator

Acceptance:

- A change request can start a FactoryRun
- Claude Code has enough project context to implement it
- Candidate can be marked pass/fail

---

## Phase 3 — Port integration

Goal: Make Port the visible control center.

Build:

- SimulationApp entity
- FactoryRun entity
- DataSource entity
- One build/change workflow
- Human approval step

Acceptance:

- New request is visible in Port
- FactoryRun status updates during execution
- Candidate evaluation is visible
- Final release waits for human approval

At this point, record a short backup demo clip of Port working.

---

## Phase 4 — Bright Data integration

Goal: Make live web data a real simulator input.

Build:

- Market-context demo page
- Bright Data collector
- Terminal scraper trigger
- Structured result validation
- Simulator “Load Current Market Scenario” behavior
- `CLAUDE.md` Bright Data rules

Acceptance:

- Terminal returns structured JSON
- Simulator consumes that JSON
- Changing the data changes simulation presets

---

## Phase 5 — Bright Data Self-Healing demo

Goal: Complete the strongest sponsor-specific failure demo.

Build:

- A controlled V1 and V2 HTML layout for market-context page
- Ability to switch layouts deliberately
- Validation failure when the current scraper no longer extracts expected data
- Self-Healing trigger
- Poll/verify healing completion
- Re-run same collector

Acceptance:

- Working scrape before HTML change
- Failed/invalid scrape after change
- Self-Healing repair
- Working structured output after repair
- Simulator receives valid data again

Do not proceed until this demo is reliable.

---

## Phase 6 — SigNoz instrumentation

Goal: Make the factory and simulator observable.

Build:

- OpenTelemetry instrumentation
- Factory spans
- Simulator spans
- Structured logs
- Small metric set
- One SigNoz dashboard

Acceptance:

- Factory run trace is visible
- Simulator run trace is visible
- Scraper failure is visible
- Recovery is visible
- Useful metrics update live

---

## Phase 7 — Close the AVO-lite repair loop

Goal: Prove the system can reject and repair a bad software candidate.

Build:

- Candidate evaluation gates
- Controlled dip-buying change request
- Deterministic failing test or validation
- Repair context passed to Claude Code
- Retry counter
- Candidate history

Acceptance:

- Candidate V1 fails
- Failure evidence is captured
- Claude repairs
- Candidate V2 passes
- Port shows latest candidate ready for approval
- SigNoz shows fail → repair → healthy sequence

This phase is the architectural centerpiece.

---

## Phase 8 — Connect SigNoz failure to remediation

Goal: Show that observability is active, not decorative.

Build the simplest reliable path:

- SigNoz alert/webhook on chosen failure signal
- Port or factory receives the signal
- FactoryRun enters remediation/retry state

Acceptance:

- Trigger known failure
- SigNoz surfaces it
- Factory visibly reacts

Do not make this more complicated than necessary.

---

## Phase 9 — Demo polish

Goal: Make the system understandable in one viewing.

Polish only:

- Simulator title and labels
- Port page naming
- SigNoz dashboard naming
- Terminal commands/output readability
- Demo-source switch for webpage V1/V2
- One-click/reset script for demo state

Do not add new features.

---

# 14. Exact Demo Story

Target: roughly 4 minutes.

## Part 1 — Explain architecture (20–30 seconds)

Say:

> “We built an AVO-inspired autonomous software factory. Port stores context and governs the workflow, Claude Code acts, Bright Data represents the changing external web, and SigNoz is the objective feedback layer. The loop is inspect, plan, act, evaluate, repair, retry, and human approval.”

Show one architecture slide/diagram only.

---

## Part 2 — Show the app (20–30 seconds)

Open Portfolio Stress Lab.

Change:

- Starting capital
- Tech allocation
- Crash severity

Run simulation.

Show:

- chart
- drawdown
- final value
- recovery time

Judges now understand the app.

Move on quickly.

---

## Part 3 — Port / factory demo (45–60 seconds)

Submit change request:

> “Add dip-buying: invest 25% of remaining cash every additional 10% market drop.”

Show:

- FactoryRun in Port
- Claude Code performing the change
- Candidate V1 failing verification
- repair/retry
- Candidate V2 passing
- Port showing waiting for approval
- human clicks approve

This proves the AVO-lite software-repair loop.

---

## Part 4 — Bright Data sponsor demo (45–60 seconds)

Terminal:

- Run scraper
- Show valid market scenario JSON
- Show simulator consuming it

Then switch demo website to V2 HTML.

- Re-run scraper
- Show invalid/missing field
- Trigger Bright Data Self-Healing
- Re-run same collector
- Show valid JSON again
- Show simulator working again

This is the clearest Bright Data evidence.

---

## Part 5 — SigNoz sponsor demo (35–45 seconds)

Open SigNoz.

Show:

- Factory trace
- Failed candidate / scraper failure
- repair/retry span
- successful run after recovery
- small metrics dashboard

Explicitly state:

> “SigNoz is not just visualization. Its failure signal feeds the remediation workflow.”

---

## Part 6 — Closing (15 seconds)

Return to Port or architecture view.

Say:

> “The simulator is the test run. The real product is the factory: it can build the software, observe real-world change, reject bad candidates, repair itself, verify the result, and keep humans in control.”

End.

---

# 15. Sponsor Demo Checklist

## Port

Before submission, verify we can visibly demonstrate:

- [ ] Clear project/application entity
- [ ] User brief/change request
- [ ] FactoryRun state
- [ ] Workflow progression
- [ ] Candidate result
- [ ] Retry after failure
- [ ] Human approval
- [ ] Released state

## Bright Data

Before submission, verify we can visibly demonstrate:

- [ ] Terminal-driven scraper execution
- [ ] Version-controlled scraper instructions in project rules
- [ ] Structured output
- [ ] Output actually used in simulator
- [ ] Controlled webpage structure change
- [ ] Scraper failure/invalid extraction
- [ ] Self-Healing
- [ ] Same collector works afterward

## SigNoz

Before submission, verify we can visibly demonstrate:

- [ ] Factory traces
- [ ] Simulator traces
- [ ] Logs
- [ ] Metrics
- [ ] Failure clearly visible
- [ ] Repair/retry clearly visible
- [ ] Healthy run after recovery
- [ ] Failure signal connected to remediation or escalation

---

# 16. What We Explicitly Do Not Build

To keep the project finishable, do not build:

- Multiple simulator types
- Arbitrary code generation for any domain
- Complex multi-agent debates
- Large vector-memory systems
- Multiple Bright Data collectors
- Complex Port catalog models
- Multiple SigNoz dashboards
- Automated production deployment infrastructure
- Financial advice functionality
- User accounts
- Billing
- Complex authentication
- Real brokerage integrations
- Huge UI system
- Full NVIDIA AVO implementation

The MVP is one excellent closed loop, not a broad platform.

---

# 17. Claude Code / Cursor Working Rules

Claude Code should treat this file as the implementation specification.

General rules:

1. Build phases in order.
2. Do not redesign the architecture without an explicit reason.
3. Do not add dependencies or infrastructure unless required by the current phase.
4. Preserve deterministic demo behavior.
5. Keep Port, Bright Data, and SigNoz integrations visible and independently demonstrable.
6. Do not hide failures — failures are part of the demo.
7. Every repair must be followed by the same verification that originally failed.
8. Human approval must remain before final release.
9. Prefer simple implementations that are easy to explain over production-grade abstractions.
10. Maintain a clean commit history after every meaningful phase.

For every phase Claude Code should report:

- What was implemented
- Files changed
- How to test it
- Whether acceptance criteria pass
- Any remaining blocker before the next phase

---

# 18. Definition of Done

The project is done when all of the following work reliably from a clean demo state:

1. Portfolio Stress Lab works as a normal interactive app.
2. A user can submit a software change request.
3. Port visibly tracks the factory run.
4. Claude Code modifies the simulator.
5. A controlled candidate fails verification.
6. The AVO-lite loop repairs and retries it.
7. The repaired candidate passes objective checks.
8. Port requires human approval before release.
9. Bright Data provides structured market context used by the simulator.
10. We can deliberately break the source page HTML.
11. Bright Data Self-Healing repairs the same collector.
12. The simulator receives valid data again.
13. SigNoz shows traces, logs, metrics, failure, and recovery.
14. At least one SigNoz failure signal causes a remediation/retry/escalation action.
15. The complete story can be demonstrated cleanly in 3–5 minutes.
16. Repository contains README, CLAUDE.md, build_plan.md, and meaningful commit history.

---

# Final Priority

If time becomes tight, preserve these four things above everything else:

1. **Working simulator**
2. **Port factory flow with human approval**
3. **Bright Data scraper break → Self-Healing → recovery**
4. **SigNoz failure → repair evidence**

Everything else is optional polish.

The winning story is simple:

> **A brief becomes working software. A bad candidate gets rejected and repaired. The external web changes and the data layer heals. SigNoz proves what happened. Port keeps the process governed.**
