# API Guardian - Autonomous Reliability Factory

**Hackathon Project**: Multi-sponsor AI-powered API reliability system
**Branch**: `person-c/port-brightdata-orchestration`  
**Status**: Phase C1 Complete ✅ (18% overall progress)

## Overview

API Guardian is an autonomous reliability product that detects when third-party API integrations degrade or break, gathers evidence from telemetry and live provider documentation, proposes repairs, objectively verifies candidates, and requires human approval before release.

### The AVO-lite Software Factory

This project implements an **AVO-lite autonomous software factory** control loop:

1. **Inspect** - Gather context and evidence from multiple sources
2. **Plan** - AI agent generates hypothesis for improvement
3. **Act** - AI agent implements code changes
4. **Evaluate** - Objective verification via tests and telemetry
5. **Diagnose** - Analyze failures with evidence
6. **Repair** - Retry with new candidates
7. **Preserve** - Release only when objectives pass
8. **Human Approval** - Gate final releases

## Sponsor Technologies

- **Port** - Context Lake, governance, workflows, approval gates
- **Bright Data** - Scraper Studio collector, terminal-driven, with AI self-healing when the target site's HTML changes
- **SigNoz** - Distributed tracing, metrics, logs, observability
- **Claude (Anthropic)** - AI coding agent for repairs

## Architecture

### The Application (Proof Surface)

**API Guardian** monitors an application that depends on three external APIs:
- **Catalog API** - Product metadata (~700ms latency)
- **Pricing API** - Price information (~900ms latency) - *breaks during demo*
- **Availability API** - Stock/ETA information (~1100ms latency)

The app exposes one operation: **Build Product Snapshot** - fetches data from all three providers and returns a normalized result.

### The Factory (Submission)

The orchestration system that monitors, diagnoses, repairs, and releases improvements:

```
Port (Context & Governance)
  ↓
Factory Loop Orchestrator
  ↓
├─→ SigNoz (Telemetry Evidence)
├─→ Bright Data (Docs Evidence)
└─→ Claude Agent (Code Repairs)
  ↓
Objective Evaluation
  ↓
Human Approval Gate
  ↓
Release
```

## Data Pipeline (Bright Data Scraper Studio)

The factory's raw material is the Pricing provider's public migration docs. That
page is a live dependency: when the provider redesigns it, a scraper trained on
the old markup silently starts returning nothing. The pipeline is built to notice
that and repair itself.

### The collector

| | |
|---|---|
| Collector ID | `c_mt4xbkwsrxt8czehu` |
| Built with | `bdata scraper create` (Bright Data's AI, 9-stage build) |
| Target | `$DOCS_PUBLIC_URL/api/docs/pricing` |
| Output | `provider_name`, `api_version`, `migration_guidance`, `changelog_date`, `field_mappings[]` |

Nothing about it is hand-written: Bright Data's AI generated the extraction code
from a natural-language description, and Bright Data's AI rewrites it when the
page changes. The collector id survives every repair, so integrations that
reference it keep working.

### The loop

```
run collector ──→ validate required fields ──→ healthy? ──→ evidence
                          │                                    ↑
                       degraded                                 │
                          ↓                                     │
              heal (Bright Data AI rewrites the code)           │
                          ↓                                     │
                   re-run + revalidate ──────────────────────────
                          ↓
                    still degraded → no evidence (never stale data)
```

Breakage is detected by a **required-field contract**, not by waiting for a
crash — a stale collector returns HTTP 200 with null fields, which is the
failure mode that would otherwise poison the factory with silent gaps.

### Run it

```bash
# 1. docs site + public tunnel (Bright Data's cloud cannot reach localhost)
python provider-docs-site/server.py
cloudflared tunnel --url http://localhost:8001   # put URL in DOCS_PUBLIC_URL

# 2. the pipeline
python demo/scripts/run_scraper_pipeline.py --status   # health check
python demo/scripts/run_scraper_pipeline.py            # break → heal → recover
```

A full run flips the docs to the other layout, watches the collector degrade,
heals it, and re-extracts — typically 2-4 minutes, entirely in the terminal.

Scraper configuration, the heal procedure, and the CLI quirk that breaks
`--auto-approve` are all documented in [CLAUDE.md](CLAUDE.md), so the coding
agent reuses them automatically.

## Demo Scenarios (3-5 minutes)

### Scene 1: Baseline Performance Problem
- App works correctly but sequential API calls cause ~2.7s latency
- SigNoz shows waterfall trace
- Factory rejects candidate due to poor performance

### Scene 2: AI Optimization
- Claude detects independent calls are serialized
- Proposes parallelization
- Latency improves to ~1.1s
- SigNoz proves improvement
- Human approves release

### Scene 3: External API Breaks
- Pricing API schema changes (V1 → V2: `price` becomes `pricing.amount`)
- App fails with parsing errors
- SigNoz detects error spike in Pricing provider

### Scene 4: Self-Healing Documentation
`python demo/scripts/run_scraper_pipeline.py`
- Scraper Studio collector extracts the migration docs cleanly
- The docs site ships a redesign — same words, different HTML
- The collector's output degrades: `api_version`, `migration_guidance`,
  `changelog_date` come back null and `field_mappings` is empty
- Bright Data's AI rewrites the collector's extraction code in place
- Evidence recovered from the new markup, same collector id

### Scene 5: AI Repair
- Claude receives evidence from SigNoz + Bright Data
- Proposes Pricing adapter fix
- Tests pass, telemetry verifies recovery
- Human approves release

## Project Structure

```
├── port/                      # Port blueprints, workflows, entities
│   ├── blueprints/            # Entity definitions
│   ├── workflows/             # Orchestration workflows
│   └── entities/              # Sample entity data
├── integrations/
│   ├── port/                  # Port API client
│   └── brightdata/
│       ├── scraper_studio.py  # Scraper Studio pipeline (build/run/heal)
│       ├── client.py          # Evidence normalization + validation
│       └── extractor.py       # Offline selector fallback (not the pipeline)
├── provider-docs-site/        # Mock Pricing API documentation
│   ├── layouts/v1/            # Initial HTML layout
│   ├── layouts/v2/            # Changed HTML (same content)
│   └── content/               # Migration documentation
├── orchestration/
│   ├── factory/               # AVO-lite factory loop
│   └── evaluator/             # Mock evaluation (until Person B ready)
├── demo/
│   ├── scripts/
│   │   ├── run_factory_loop.py      # Port candidate lifecycle demo
│   │   ├── run_scraper_pipeline.py  # Scraper Studio break/heal demo
│   │   └── run_docs_selfheal.py     # Offline self-heal (no Bright Data)
│   └── states/                # State snapshots
├── docs/                      # Architecture documentation
├── config/                    # Configuration files
└── tests/                     # Integration tests
```

## Team Structure

- **Person A** - API Guardian app, mock APIs, provider adapters
- **Person B** - SigNoz instrumentation, telemetry, evaluation
- **Person C** (this branch) - Port, Bright Data, orchestration, demo

## Current Progress

### ✅ Completed Phases

**Phase C0: Setup & Credentials** — Port and Bright Data credentials configured,
connection tests passing.

**Phase C1: Port Foundation** — 6 blueprints deployed; API Guardian service and
3 External API entities (Catalog, Pricing, Availability) created and verified.

**Phase C2: Factory Workflow** — Full candidate lifecycle driven into Port from
the terminal. Both PASS and FAIL paths exercised end to end.

**Phase C3: Provider Docs Site** — FastAPI docs site with two HTML layouts that
carry byte-identical visible text under materially different DOM structures.

**Phase C4: Bright Data Scraper Studio** — Live AI-built collector with working
self-healing. See [Data Pipeline](#data-pipeline-bright-data-scraper-studio).

**Phase C8: Docs Self-Healing** — Break/detect/heal/recover demo runs in one
command.

### 🔄 Next Phase: C5 — Evaluation Integration
Swap the mock evaluator for Person B's real evaluation object and attach Bright
Data evidence to the FactoryRun entity in Port.

### 📊 Progress: 6/11 phases complete (55%)

See [docs/PHASE_TRACKER.md](docs/PHASE_TRACKER.md) for phase-by-phase detail.

---

## Getting Started

### Prerequisites

- Python 3.11+
- Docker & Docker Compose (optional)
- Port account (getport.io) ✅ Configured
- Bright Data account ✅ Configured
- Anthropic API key (Claude) - Optional for now

### Setup

1. Clone and checkout this branch:
```bash
git checkout person-c/port-brightdata-orchestration
```

2. Copy environment template:
```bash
cp config/env.template .env
```

3. Configure credentials in `.env`:
```bash
# Port
PORT_CLIENT_ID=your_client_id
PORT_CLIENT_SECRET=your_client_secret

# Bright Data - the token needs ADMIN permission, not read-only:
# a read-only token cannot create zones or heal collectors
BRIGHTDATA_API_TOKEN=your_token
BRIGHTDATA_COLLECTOR_ID=c_mt4xbkwsrxt8czehu   # Scraper Studio collector
BRIGHTDATA_ZONE=api_guardian_docs             # Web Unlocker zone

# Public URL Bright Data scrapes; changes each tunnel restart
DOCS_PUBLIC_URL=https://<your-tunnel>.trycloudflare.com

# Claude
ANTHROPIC_API_KEY=your_key
```

4. Install dependencies:
```bash
pip install -r requirements.txt
```

5. Setup Port workspace (already done in Phase C1):
```bash
python scripts/setup_port.py
```

6. Verify setup:
```bash
python -m pytest tests/ -q
```

### Running the Demo

```bash
# terminal 1 - provider docs site
python provider-docs-site/server.py

# terminal 2 - public tunnel, then put the URL in DOCS_PUBLIC_URL
cloudflared tunnel --url http://localhost:8001

# terminal 3 - the demos
python demo/scripts/run_factory_loop.py --both --auto-approve   # Port lifecycle
python demo/scripts/run_scraper_pipeline.py                     # scraper self-heal
```

## Objective Fitness Function

Every candidate is scored out of 100 points:

- **Correctness (40pts)** - Schema valid, tests pass, matches provider truth
- **Reliability (20pts)** - Error rate < 1%, no adapter exceptions
- **Latency (20pts)** - p95 ≤ 1.6s (full), ≤ 2.2s (partial)
- **Data Pipeline (10pts)** - Bright Data extraction healthy
- **Observability (10pts)** - Complete traces with run/candidate IDs

**Release Requirements:**
- Correctness must pass (hard gate)
- Reliability must pass (hard gate)
- Score ≥ 90
- Human approval granted

## Candidate Lifecycle

```
DETECTED → INVESTIGATING → PLANNED → IMPLEMENTED → 
EVALUATING → [REJECTED | READY_FOR_APPROVAL] → 
APPROVED → RELEASED
```

## Development

### Port Blueprints

Located in `port/blueprints/`:
- `service.json` - API Guardian service
- `external_api.json` - Catalog, Pricing, Availability dependencies
- `factory_run.json` - Factory execution instances
- `candidate_version.json` - Code change candidates
- `evaluation.json` - Objective test results
- `release.json` - Approved releases

### Bright Data Integration

The scraper extracts structured migration evidence from the Pricing API docs site:
- Provider name and version
- Old/new field mappings
- Migration guidance
- Changelog information

Self-healing demonstration:
1. Layout V1 - scraper works
2. Switch to Layout V2 - scraper breaks
3. Trigger Self-Healing - scraper repairs
4. Extraction succeeds again

## Contributing

This is a hackathon project with clear ownership boundaries:
- Do not edit Person A's mock APIs or business logic
- Do not edit Person B's SigNoz instrumentation
- Coordinate contract changes with all team members

## Development Status

### What's Working
- ✅ Port API integration
- ✅ Bright Data API client (ready for scraper)
- ✅ Mock evaluator for testing
- ✅ Factory loop orchestrator (ready)
- ✅ State machine implementation
- ✅ Provider docs site (ready to start)

### What's Next
- 🔄 Start provider docs site server
- 🔄 Configure Bright Data scraper
- 🔄 Test self-healing workflow
- ⏳ Port workflows
- ⏳ Factory loop integration
- ⏳ Demo orchestration

## License

MIT License - Hackathon Project

## Project Documentation

- [Master Plan](MASTER_PLAN.md) - Overall project architecture
- [Person C Tasks](PERSON_C_PORT_BRIGHTDATA_ORCHESTRATION.md) - Detailed task breakdown
- [Phase Tracker](docs/PHASE_TRACKER.md) - Current phase status
- [Progress Report](docs/PROGRESS_REPORT.md) - Detailed accomplishments

## External Resources

- [Port Documentation](https://docs.getport.io)
- [Port Dashboard](https://app.getport.io) - View our workspace
- [Bright Data Scraper Studio](https://brightdata.com/products/scraper-studio)
- [SigNoz Documentation](https://signoz.io/docs/)
- [Anthropic Claude](https://www.anthropic.com/claude)

## Quick Links

- **Port Workspace**: https://app.getport.io (6 blueprints, 4 entities deployed)
- **Repository**: https://github.com/SabariIyyappan/Financial-Simulation-Factory
- **Branch**: `person-c/port-brightdata-orchestration`
