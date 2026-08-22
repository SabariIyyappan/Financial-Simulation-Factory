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
- **Bright Data** - Live documentation scraping with self-healing
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
- Bright Data scraper extracts migration docs successfully
- Docs site HTML structure changes
- Scraper breaks
- Bright Data Self-Healing automatically fixes scraper
- Migration evidence recovered

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
│   └── brightdata/            # Bright Data scraper client
├── provider-docs-site/        # Mock Pricing API documentation
│   ├── layouts/v1/            # Initial HTML layout
│   ├── layouts/v2/            # Changed HTML (same content)
│   └── content/               # Migration documentation
├── orchestration/
│   ├── factory/               # AVO-lite factory loop
│   └── evaluator/             # Mock evaluation (until Person B ready)
├── demo/
│   ├── scripts/               # Demo control scripts
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

**Phase C0: Setup & Credentials**
- Port API credentials configured and tested
- Bright Data API credentials configured and tested
- Connection tests passing for both services

**Phase C1: Port Foundation**
- ✅ 6 Port blueprints created and deployed
- ✅ API Guardian service entity created
- ✅ 3 External API entities created (Catalog, Pricing, Availability)
- ✅ All entities verified in Port dashboard
- ✅ Port API client fully implemented

### 🔄 Next Phase: C3 - Provider Docs Site
- Start FastAPI docs site server
- Test layout V1 and V2
- Prepare for Bright Data scraper configuration

### 📊 Progress: 2/11 phases complete (18%)

See [docs/PROGRESS_REPORT.md](docs/PROGRESS_REPORT.md) for detailed progress.

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
cp .env.example .env
```

3. Configure credentials in `.env`:
```bash
# Port
PORT_CLIENT_ID=your_client_id
PORT_CLIENT_SECRET=your_client_secret

# Bright Data
BRIGHTDATA_API_TOKEN=your_token

# Claude
ANTHROPIC_API_KEY=your_key
```

4. Install dependencies:
```bash
pip install -r requirements.txt
```

5. Start services:
```bash
docker-compose up -d
```

6. Setup Port workspace (already done in Phase C1):
```bash
python scripts/setup_port.py
```

7. Verify Port setup:
```bash
python tests/test_connections.py
```

### Running the Demo

See [demo/RUNBOOK.md](demo/RUNBOOK.md) for step-by-step demo instructions.

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
