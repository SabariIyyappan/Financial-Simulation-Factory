# API Guardian

An autonomous reliability factory for third-party API integrations. It detects when an
integration degrades or breaks, gathers evidence from telemetry and live provider docs,
proposes a repair, verifies the candidate against objective gates, and requires a human
to approve release.

Built for the Zero Downtime Hackathon (Port + Bright Data Scraper Studio + SigNoz).
**The application is the proof surface. The factory is the submission.**

> Setting up for the demo? Go straight to **[DEMO_SETUP.md](DEMO_SETUP.md)**.

## The loop

```
Inspect → Plan → Act → Evaluate → Diagnose → Repair → Retry → Approve → Release
```

- **Port** — context, candidate lineage, governance, the human approval gate
- **Bright Data** — live provider docs/changelog extraction, self-healing when the docs
  site restructures
- **SigNoz** — objective evidence: traces, metrics, logs, before/after verification
- **Claude Code** — the actor that reads the evidence and proposes the repair

Nothing an LLM says decides a release. Correctness is schema validation and tests,
reliability is a measured error rate, latency is a measured p95. The agent proposes;
the fitness function disposes; a human approves.

## The two recovery loops we demonstrate

**Loop A — software repair.** The app calls three independent providers *sequentially*
(~2.7s). SigNoz shows the staircase, the fitness gate rejects it on latency, the agent
parallelizes, and the same measurement proves the fix (~1.1s).

**Loop B — web-data repair.** The Pricing provider ships a breaking schema change
(`price`/`currency` → `pricing.amount`/`pricing.currency`). The adapter fails loudly and
localizes to `pricing` in SigNoz. Bright Data fetches the migration guidance — and when
the docs site itself restructures, the scraper self-heals rather than being rewritten.

## Layout

```
apps/api-guardian/       Next.js app under repair — /api/snapshot, operator dashboard
services/mock-providers/ Deterministic Catalog/Pricing/Availability (700/900/1100ms)
packages/
  domain-contracts/      Shared types, provider payload shapes (V1/V2), typed errors
  provider-clients/      The adapters the factory repairs
  telemetry/             OTel/SigNoz instrumentation package
observability/
  signoz/                Self-hosted SigNoz stack (docker compose)
  evaluator/             Fitness scoring service (:8090)
  contracts/             Frozen A↔B interfaces
port/                    Blueprints + scorecard
integrations/
  port/                  Port client (Python) + lifecycle guards
  brightdata/            Scraper Studio client, extraction, self-heal
orchestration/factory/   The AVO-lite loop and candidate state machine
provider-docs-site/      The provider docs the scraper reads (v1/v2 layouts)
demo/scripts/            Runnable demo steps
```

TypeScript for the app and telemetry; Python for orchestration. The Python orchestrator
drives the TypeScript services over HTTP — deliberate, not an accident of merging.

## Ports

| Service | Port |
|---|---|
| API Guardian app | 3000 |
| Mock providers | 4001 |
| Provider docs site | 8001 |
| SigNoz UI / query API | 8080 |
| OTLP ingest (traces/metrics/logs) | 4318 |
| Fitness evaluator | 8090 |

## Fitness function

100 points. Release requires the correctness gate, the reliability gate, **and** ≥ 90.

| Component | Points |
|---|---|
| Correctness (schema valid, tests pass, provider truth) | 40 — hard gate |
| Reliability (error rate < 1%, no adapter exceptions) | 20 — hard gate |
| Latency (p95 ≤ 1.6s → 20; ≤ 2.2s → 10; else 0) | 20 |
| Docs/data health (Bright Data extraction valid) | 10 |
| Observability (expected spans + run correlation) | 10 |

Baseline scores 70 and fails on latency. That is the intended starting state.

## Verify it works

```bash
npm install
npm run build -w @api-guardian/telemetry
npm test          # TypeScript: adapters + Port lifecycle guards
pytest            # Python: extraction, factory loop
```

## Docs

- **[DEMO_SETUP.md](DEMO_SETUP.md)** — full setup and the demo runbook
- [CLAUDE.md](CLAUDE.md) — project rules, ownership boundaries, Bright Data gotchas
- [MASTER_PLAN.md](MASTER_PLAN.md) — architecture and phase plan
- [observability/contracts/TELEMETRY_CONTRACT.md](observability/contracts/TELEMETRY_CONTRACT.md) — span/log/evaluation contracts
- [port/README.md](port/README.md) — Port entity model and governance
